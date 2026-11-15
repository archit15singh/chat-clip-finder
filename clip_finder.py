#!/usr/bin/env python3
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory

BUCKET_SECONDS = 10
BASELINE_BUCKETS = 30
MIN_HISTORY_BUCKETS = 3


@dataclass(frozen=True)
class Candidate:
    start_seconds: float
    end_seconds: float
    peak_seconds: float
    messages: int
    baseline: float
    ratio: float


def command_output(*command):
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode:
        detail = result.stderr.strip()
        raise ValueError(f"{command[0]} failed: {detail or result.returncode}")
    return result.stdout


def video_duration(video):
    if not video.is_file():
        raise ValueError(f"Video file not found: {video}")
    probe = json.loads(command_output(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(video),
    ))
    if not probe.get("streams"):
        raise ValueError(f"No video stream in {video}")
    duration = float(probe.get("format", {}).get("duration", "nan"))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Could not read a positive video duration from {video}")
    return duration


def chat_counts(chat, duration):
    data = json.loads(chat.read_text(encoding="utf-8-sig"))
    comments = data.get("comments") if isinstance(data, dict) else None
    if not isinstance(comments, list):
        raise ValueError("Expected a TwitchDownloader JSON export with a comments list")

    counts = Counter()
    for index, comment in enumerate(comments, start=1):
        offset = comment.get("content_offset_seconds") if isinstance(comment, dict) else None
        if type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0:
            raise ValueError(f"Invalid content_offset_seconds on chat message {index}")
        if offset >= duration:
            raise ValueError(
                f"Chat message {index} falls beyond the recording. Use the matching untrimmed VOD."
            )
        counts[int(offset // BUCKET_SECONDS)] += 1
    return counts


def chat_candidates(counts, duration, min_messages, min_ratio, before, after, limit):
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
        if any(peak.start_seconds < other.end_seconds and other.start_seconds < peak.end_seconds
               for other in selected):
            continue
        selected.append(peak)
        if len(selected) == limit:
            break
    return selected


def render_clip(video, candidate, output):
    fit = (
        "scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1"
    )
    command_output(
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
        "-ss", str(candidate.start_seconds), "-i", str(video),
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
    duration = video_duration(args.video)
    counts = chat_counts(args.chat, duration)
    clips = chat_candidates(
        counts, duration, args.min_messages, args.min_ratio,
        args.before, args.after, args.limit,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists():
        raise ValueError(f'Output directory already exists: {args.out}')
    settings = {
        "bucket_seconds": BUCKET_SECONDS,
        "baseline_seconds": BASELINE_BUCKETS * BUCKET_SECONDS,
        "min_messages": args.min_messages,
        "min_ratio": args.min_ratio,
        "before_seconds": args.before,
        "after_seconds": args.after,
        "limit": args.limit,
    }
    rows = []
    for rank, clip in enumerate(clips, start=1):
        filename = f"clip-{rank:02d}-{int(clip.peak_seconds):06d}s.mp4"
        rows.append({
            "rank": rank, **asdict(clip), "file": None if args.preview else filename,
        })

    report_path = args.out / "clips.json"
    reserved = [report_path, *(args.out / row["file"] for row in rows if row["file"])]

    # Encode in temporary files so a failed run leaves no apparently finished clip.
    with TemporaryDirectory(dir=args.out.parent) as temp:
        staging = Path(temp)
        for clip, row in zip(clips, rows):
            if row["file"]:
                render_clip(args.video, clip, staging / row["file"])
        report = {
            "video_duration_seconds": duration,
            "settings": settings,
            "clips": rows,
        }
        (staging / report_path.name).write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8",
        )
        args.out.mkdir()
        for path in reserved[1:] + [report_path]:
            (staging / path.name).replace(path)

    for row in rows:
        clip = clips[row["rank"] - 1]
        print(f'{row["rank"]:2}. {clip.start_seconds:8.1f}s–{clip.end_seconds:8.1f}s'
              f'  {clip.messages} messages ({clip.ratio:.1f}× baseline)')
    print(f"{len(rows)} candidate(s). Report: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Find Twitch VOD highlights from chat spikes.")
    parser.add_argument("--video", type=Path, required=True, help="local, untrimmed VOD")
    parser.add_argument("--chat", type=Path, required=True, help="TwitchDownloader JSON export")
    parser.add_argument("--out", type=Path, default=Path("clips"))
    parser.add_argument("--preview", action="store_true", help="write selections without encoding")
    parser.add_argument("--limit", type=positive_int, default=5)
    parser.add_argument("--min-messages", type=positive_int, default=10)
    parser.add_argument("--min-ratio", type=positive, default=3)
    parser.add_argument("--before", type=positive, default=20)
    parser.add_argument("--after", type=positive, default=20)
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
