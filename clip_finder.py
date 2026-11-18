#!/usr/bin/env python3
import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit, urlunsplit

BUCKET_SECONDS = 10
BASELINE_BUCKETS = 30
MIN_HISTORY_BUCKETS = 3
CHAT_TAIL_TOLERANCE_SECONDS = 10
SPEECH_GAP_SECONDS = 0.25
SPEECH_POSTROLL_SECONDS = 0.35
SRT_TIMESTAMP = r"\d{2,}:\d{2}:\d{2}[,.]\d{3}"
SRT_TIMING = re.compile(rf"^({SRT_TIMESTAMP})\s+-->\s+({SRT_TIMESTAMP})(?:\s+.*)?$")


@dataclass(frozen=True)
class Candidate:
    start_seconds: float
    end_seconds: float
    peak_seconds: float
    messages: int | None = None
    baseline: float | None = None
    ratio: float | None = None


def command_output(*command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        detail = result.stderr.strip()
        raise ValueError(f"{command[0]} failed: {detail or result.returncode}")
    return result.stdout


def video_duration(video):
    if isinstance(video, Path) and not video.is_file():
        raise ValueError(f"Video file not found: {video}")
    network_options = ("-rw_timeout", "15000000") if isinstance(video, str) else ()
    probe = json.loads(command_output(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=start_time,duration:format=start_time,duration",
        "-of", "json", *network_options, str(video),
    ))
    if not probe.get("streams"):
        raise ValueError(f"No video stream in {video}")
    container = probe.get("format", {})
    duration = float(container.get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Could not read a positive video duration from {video}")
    # FFmpeg seeks relative to the container start. Audio can continue after the
    # first video stream ends, so use the video end when the probe reports it.
    stream = probe["streams"][0]
    try:
        video_end = (
            float(stream["start_time"]) - float(container["start_time"])
            + float(stream["duration"])
        )
    except (KeyError, ValueError):
        return duration
    if math.isfinite(video_end) and video_end > 0:
        return min(duration, video_end)
    return duration


def video_url(value):
    try:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username is not None:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError("expected an HTTP or HTTPS video URL without credentials") from None
    return value


def is_media_url(url):
    return Path(urlsplit(url).path).suffix.lower() in {
        ".mp4", ".mov", ".mkv", ".webm", ".m3u8",
    }


def page_video_duration(url):
    metadata = json.loads(command_output(
        "yt-dlp", "--ignore-config", "--no-playlist", "--skip-download", "--dump-single-json", "--", url,
    ))
    if metadata.get("_type") in ("playlist", "multi_video") or metadata.get("is_live"):
        raise ValueError("Use a single completed video or VOD")
    duration = metadata.get("duration")
    if type(duration) in (int, float) and math.isfinite(duration) and duration > 0:
        return duration
    media = metadata.get("url")
    if isinstance(media, str) and metadata.get("protocol") in ("http", "https"):
        return video_duration(media)
    raise ValueError("Could not determine the video duration. Use a completed VOD or direct media URL.")


def render_page_clip(url, clip, output):
    length = clip.end_seconds - clip.start_seconds
    with TemporaryDirectory(dir=output.parent) as work:
        result = command_output(
            "yt-dlp", "--ignore-config", "--no-playlist", "--no-progress", "--no-simulate",
            "--match-filter", "!is_live",
            "--download-sections", f"*{clip.start_seconds:.6f}-{clip.end_seconds:.6f}",
            "--force-keyframes-at-cuts", "--print", "after_move:filepath",
            "--output", str(Path(work) / "section.%(ext)s"), "--", url,
        ).splitlines()
        if len(result) != 1:
            raise ValueError("Expected exactly one downloaded clip section")
        section = Path(result[0])
        if section.parent.resolve() != Path(work).resolve():
            raise ValueError("Downloaded section is outside the staging directory")
        if video_duration(section) + min(0.35, length / 2) < length:
            raise ValueError("Downloaded section is shorter than the requested clip")
        render_clip(section, Candidate(0, length, 0), output)


def chat_counts(chat, duration, vod_start=None):
    data = json.loads(chat.read_text(encoding="utf-8-sig"))
    comments = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(comments, list):
        raise ValueError("Expected a TwitchDownloader JSON export with a comments list")

    vod = data.get("video")
    metadata = vod if isinstance(vod, dict) else {}
    export_duration = metadata.get("length")
    if vod_start is not None:
        export_start, export_end = metadata.get("start"), metadata.get("end")
        if (type(export_start) not in (int, float) or type(export_end) not in (int, float)
                or not math.isfinite(export_start) or not math.isfinite(export_end)
                or export_start != vod_start or export_end <= export_start
                or abs(export_end - export_start - duration) > CHAT_TAIL_TOLERANCE_SECONDS):
            raise ValueError("--vod-start needs a TwitchDownloader export trimmed to the matching video interval")
        export_duration = export_end - export_start
    matching_duration = (
        type(export_duration) in (int, float)
        and abs(export_duration - duration) <= CHAT_TAIL_TOLERANCE_SECONDS
    )
    counts = Counter()
    skipped_tail_messages = 0
    for index, comment in enumerate(comments, start=1):
        offset = comment.get("content_offset_seconds") if isinstance(comment, dict) else None
        if type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0:
            raise ValueError(f"Invalid content_offset_seconds on chat message {index}")
        if vod_start is not None:
            offset -= vod_start
            if offset < 0:
                raise ValueError(f"Chat message {index} precedes the trimmed video start")
        if offset >= duration:
            if matching_duration and offset - duration <= CHAT_TAIL_TOLERANCE_SECONDS:
                skipped_tail_messages += 1
                continue
            raise ValueError(
                f"Chat message {index} falls beyond the recording. Use the matching untrimmed VOD or specify --vod-start for a matching excerpt."
            )
        counts[int(offset // BUCKET_SECONDS)] += 1
    return counts, skipped_tail_messages


def overlap(start, end, other_start, other_end):
    return start < other_end and other_start < end


def chat_candidates(counts, duration, min_messages, min_ratio, before, after, limit,
                    excluded_ranges=()):
    peaks = []
    for bucket, messages in counts.items():
        if bucket < MIN_HISTORY_BUCKETS or messages < min_messages:
            continue
        history = range(max(0, bucket - BASELINE_BUCKETS), bucket)
        baseline = max(1.0, statistics.median(counts[index] for index in history))
        ratio = messages / baseline
        if ratio >= min_ratio:
            peak = bucket * BUCKET_SECONDS
            peaks.append(Candidate(
                max(0, peak - before), min(duration, peak + after),
                peak, messages, baseline, ratio,
            ))

    selected = []
    for peak in sorted(peaks, key=lambda c: (-c.ratio, -c.messages, c.peak_seconds)):
        if any(overlap(peak.start_seconds, peak.end_seconds, start, end)
               for start, end in excluded_ranges):
            continue
        if any(overlap(peak.start_seconds, peak.end_seconds, other.start_seconds, other.end_seconds)
               for other in selected):
            continue
        selected.append(peak)
        if len(selected) == limit:
            break
    return selected


def timestamp(value):
    parts = value.split(":")
    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) in (2, 3):
            seconds = float(parts[-1])
            minutes = int(parts[-2])
            hours = int(parts[0]) if len(parts) == 3 else 0
            if not 0 <= seconds < 60 or minutes < 0 or hours < 0:
                raise ValueError
            if len(parts) == 3 and minutes >= 60:
                raise ValueError
            seconds += 60 * minutes + 3600 * hours
        else:
            raise ValueError
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError
    except (ValueError, OverflowError):
        raise argparse.ArgumentTypeError("expected seconds, MM:SS, or HH:MM:SS") from None
    return seconds


def timestamp_range(value):
    try:
        start, end = (timestamp(bound) for bound in value.split("-", 1))
    except (ValueError, argparse.ArgumentTypeError):
        raise argparse.ArgumentTypeError("expected a START-END timestamp range") from None
    if start >= end:
        raise argparse.ArgumentTypeError("range end must be after its start")
    return start, end


def speech_spans(srt):
    text = srt.read_text(encoding="utf-8-sig").strip()
    cues = []
    for index, block in enumerate(re.split(r"\n[ \t]*\n", text) if text else (), 1):
        lines = block.splitlines()
        timing = 1 if lines[0].strip().isdigit() else 0
        match = SRT_TIMING.fullmatch(lines[timing].strip()) if timing < len(lines) else None
        if not match:
            raise ValueError(f"Invalid SRT timing at cue {index} in {srt.name}")
        try:
            start, end = (timestamp(value.replace(",", ".")) for value in match.groups())
        except argparse.ArgumentTypeError:
            raise ValueError(f"Invalid SRT timing at cue {index} in {srt.name}") from None
        if end <= start:
            raise ValueError(f"Invalid SRT timing at cue {index} in {srt.name}")
        spoken = re.sub(r"<[^>]*>|\[[^]]*\]", "", " ".join(lines[timing + 1:]))
        if any(character.isalnum() for character in spoken):
            cues.append((start, end))

    spans = []
    for start, end in sorted(cues):
        if spans and start <= spans[-1][1] + SPEECH_GAP_SECONDS:
            spans[-1] = (spans[-1][0], max(spans[-1][1], end))
        else:
            spans.append((start, end))
    return spans


def finish_reaction(clip, spans, duration):
    for index, (start, end) in enumerate(spans):
        if start <= clip.end_seconds < end:
            next_start = spans[index + 1][0] if index + 1 < len(spans) else duration
            out = min(duration, round(end + SPEECH_POSTROLL_SECONDS, 3))
            if next_start < duration:
                out = min(out, round(next_start - 0.04, 3))
            return replace(clip, end_seconds=out), {
                "requested_end_seconds": clip.end_seconds,
                "speech_end_seconds": end,
                "source_limited": duration < end,
            }
    return clip, None


def marked_candidates(marks, duration, before, after):
    selected = []
    for mark in marks:
        if mark >= duration:
            raise ValueError(f"Timestamp {mark:g}s falls outside the {duration:g}s recording")
        selected.append(Candidate(max(0, mark - before), min(duration, mark + after), mark))
    return selected


def render_clip(video, candidate, output):
    fit = (
        "scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    network_options = ("-rw_timeout", "15000000") if isinstance(video, str) else ()
    command_output(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-ss", str(candidate.start_seconds), *network_options, "-i", str(video),
        "-t", str(candidate.end_seconds - candidate.start_seconds),
        "-map", "0:v:0", "-map", "0:a:0?", "-vf", fit, "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-movflags", "+faststart", str(output),
    )


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("expected a finite number greater than zero")
    return number


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("expected an integer greater than zero")
    return number


def run(args):
    if args.out.exists():
        raise ValueError(f'Output directory already exists: {args.out}')
    video = args.video_url if args.video_url is not None else args.video
    page_url = args.video_url is not None and not is_media_url(args.video_url)
    duration = page_video_duration(video) if page_url else video_duration(video)
    skipped_tail_messages = 0
    chat_activity = None
    if args.chat:
        counts, skipped_tail_messages = chat_counts(args.chat, duration, args.vod_start)
        maximum = max((count for bucket, count in counts.items()
                       if bucket >= MIN_HISTORY_BUCKETS), default=0)
        chat_activity = {
            "messages_counted": sum(counts.values()),
            "buckets_with_messages": len(counts),
            "maximum_messages_in_rankable_bucket": maximum,
        }
        clips = chat_candidates(
            counts, duration, args.min_messages, args.min_ratio,
            args.before, args.after, args.limit, args.exclude,
        )
        mode = "chat"
    elif args.at:
        clips = marked_candidates(args.at, duration, args.before, args.after)
        mode = "timestamp"
    else:
        clips = []
        for start, end in args.range:
            if end > duration:
                raise ValueError(f"Clip end {end:g}s falls outside the {duration:g}s recording")
            clips.append(Candidate(start, end, start))
        mode = "range"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    settings = {
        "bucket_seconds": BUCKET_SECONDS,
        "baseline_seconds": BASELINE_BUCKETS * BUCKET_SECONDS,
        "min_messages": args.min_messages,
        "min_ratio": args.min_ratio,
        "before_seconds": args.before,
        "after_seconds": args.after,
        "limit": args.limit,
        "excluded_ranges_seconds": args.exclude,
        "vod_start_seconds": args.vod_start if args.vod_start is not None else 0,
    }
    reactions = [None] * len(clips)
    if args.speech_srt and clips:
        spans = speech_spans(args.speech_srt)
        clips, reactions = zip(*(finish_reaction(clip, spans, duration) for clip in clips))
    rows = []
    for rank, (clip, reaction) in enumerate(zip(clips, reactions), start=1):
        filename = f"clip-{rank:02d}-{int(clip.peak_seconds):06d}s.mp4"
        rows.append({
            "rank": rank, **asdict(clip), "file": None if args.preview else filename,
        })
        if reaction:
            rows[-1]["speech_tail"] = reaction

    report_path = args.out / "clips.json"
    reserved = [report_path, *(args.out / row["file"] for row in rows if row["file"])]

    # Encode in temporary files so a failed run leaves no apparently finished clip.
    with TemporaryDirectory(dir=args.out.parent) as temp:
        staging = Path(temp)
        for clip, row in zip(clips, rows):
            if row["file"]:
                if page_url:
                    render_page_clip(video, clip, staging / row["file"])
                else:
                    render_clip(video, clip, staging / row["file"])
        report = {
            "mode": mode,
            "video_duration_seconds": duration,
            "skipped_tail_messages": skipped_tail_messages,
            "chat_activity": chat_activity,
            "settings": settings,
            "clips": rows,
        }
        if args.video_url is not None:
            parts = urlsplit(args.video_url)
            report["source_url"] = (args.video_url if page_url else
                                    urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))
        (staging / report_path.name).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8",
        )
        args.out.mkdir()
        for path in reserved[1:] + [report_path]:
            (staging / path.name).replace(path)

    for rank, clip in enumerate(clips, start=1):
        span = f"{rank:2}. {clip.start_seconds:8.1f}s–{clip.end_seconds:8.1f}s"
        if clip.ratio is None:
            print(f"{span}  marked at {clip.peak_seconds:.2f}s")
        else:
            print(f"{span}  {clip.messages} messages ({clip.ratio:.1f}× baseline)")
    if skipped_tail_messages:
        print(f"Skipped {skipped_tail_messages} chat message(s) at or just after the video end.")
    if chat_activity is not None and not clips and maximum < args.min_messages:
        print(f"No rankable 10-second bucket reached --min-messages {args.min_messages} "
              f"(maximum {maximum}).")
    print(f"{len(rows)} candidate(s). Report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Cut gameplay clips from chat spikes or marked moments.")
    video = parser.add_mutually_exclusive_group(required=True)
    video.add_argument("--video", type=Path, help="local video file")
    video.add_argument("--video-url", type=video_url, help="authorized direct media or completed video URL")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--chat", type=Path, help="TwitchDownloader JSON export paired with the video")
    source.add_argument("--at", action="append", type=timestamp, metavar="TIME",
                        help="mark a timestamp (seconds, MM:SS or HH:MM:SS); repeat to cut more clips")
    source.add_argument("--range", action="append", type=timestamp_range, metavar="START-END",
                        help="cut an exact source interval; repeat to cut more clips")
    parser.add_argument("--speech-srt", type=Path, metavar="SRT",
                        help="extend a marked range through speech, using cues on the source video clock")
    parser.add_argument("--out", type=Path, default=Path("clips"))
    parser.add_argument("--preview", action="store_true", help="write selections without encoding")
    parser.add_argument("--exclude", action="append", type=timestamp_range, default=[],
                        metavar="START-END", help="skip chat picks overlapping this interval; repeatable")
    parser.add_argument("--vod-start", type=timestamp, metavar="TIME",
                        help="original VOD timestamp where this matching video and chat excerpt starts")
    parser.add_argument("--limit", type=positive_int, default=5)
    parser.add_argument("--min-messages", type=positive_int, default=10)
    parser.add_argument("--min-ratio", type=positive, default=3)
    parser.add_argument("--before", type=positive, default=20)
    parser.add_argument("--after", type=positive, default=20)
    args = parser.parse_args()
    if args.speech_srt and args.chat:
        parser.error("--speech-srt requires --range or --at")
    if not args.chat and (args.exclude or args.vod_start is not None):
        parser.error("--exclude and --vod-start require --chat")
    try:
        run(args)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
