#!/usr/bin/env python3
"""Save local review evidence for the exact vertical export a viewer will see."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from shutil import copy2
import subprocess
from tempfile import TemporaryDirectory

from clip_finder import command_output, video_duration


MAX_FRAMES = 12
THUMBNAIL = (
    "scale=270:480:force_original_aspect_ratio=decrease:force_divisible_by=2,"
    "pad=270:480:(ow-iw)/2:(oh-ih)/2,setsar=1"
)


def artifact_digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as media:
        for block in iter(lambda: media.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_export(media, *, twitch_native=False):
    probe = json.loads(command_output(
        "ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(media),
    ))
    streams = probe["streams"]
    video = [stream for stream in streams if stream["codec_type"] == "video"]
    audio = [stream for stream in streams if stream["codec_type"] == "audio"]
    if media.suffix.lower() != ".mp4" or "mp4" not in probe["format"]["format_name"].split(","):
        raise ValueError("Expected an MP4 export")
    if len(video) != 1 or len(audio) > 1 or len(streams) != len(video) + len(audio):
        raise ValueError("Expected one video stream and at most one audio stream")
    picture = video[0]
    codecs = {"h264", "hevc"} if twitch_native else {"h264"}
    if (
        picture["codec_name"] not in codecs
        or picture["height"] <= picture["width"]
        or picture.get("sample_aspect_ratio", "1:1") not in {"1:1", "0:1", "N/A"}
        or any(item.get("rotation", 0) % 360 for item in picture.get("side_data_list", []))
    ):
        expected = "H.264 or HEVC" if twitch_native else "H.264"
        raise ValueError(f"Expected {expected} video encoded directly in portrait orientation")
    if audio and audio[0]["codec_name"] != "aac":
        raise ValueError("Expected AAC audio in the MP4 export")
    return probe, bool(audio)


MIN_SIGNAL_PEAK_DBFS = -60.0


def measure_audio(media, ffmpeg):
    result = subprocess.run(
        (*ffmpeg, "-i", str(media), "-vn", "-af", f"silencedetect=noise={MIN_SIGNAL_PEAK_DBFS}dB:d=0.05,volumedetect",
         "-f", "null", "-"),
        capture_output=True, text=True,
    )
    if result.returncode:
        raise ValueError(f"Audio measurement failed: {result.stderr.strip()}")
    statistics = "\n".join(
        line for line in result.stderr.splitlines()
        if "silencedetect" in line or "volumedetect" in line
    ) + "\n"
    peak = re.search(r"max_volume: (-?\d+(?:\.\d+)?) dB", statistics)
    if peak is None:
        raise ValueError("Could not measure decoded audio peak")
    silent_seconds = sum(map(float, re.findall(r"silence_duration: ([0-9.]+)", statistics)))
    return float(peak[1]), silent_seconds, statistics


def save_audio_evidence(media, directory, ffmpeg, statistics):
    (directory / "audio-statistics.txt").write_text(statistics)
    graphics = {
        "waveform.png": "showwavespic=s=900x180:split_channels=1",
        "spectrogram.png": "showspectrumpic=s=900x360:scale=log:fscale=log",
    }
    for name, filters in graphics.items():
        command_output(*ffmpeg, "-loglevel", "error", "-i", str(media),
                       "-filter_complex", filters, "-frames:v", "1", str(directory / name))
    return ["audio-statistics.txt", *graphics]


def review_export(media, output, timestamps=(), audio_evidence=False, *, twitch_native=False):
    media = media.resolve(strict=True)
    if not media.is_file():
        raise ValueError("Media must be a local file")
    output = output.resolve()
    if output.exists():
        raise ValueError(f"Choose a new output directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    digest = artifact_digest(media)
    ffmpeg = ("ffmpeg", "-hide_banner", "-nostdin", "-xerror")
    with TemporaryDirectory(prefix=".review-", dir=output.parent) as workspace:
        workspace = Path(workspace)
        # Review a stable snapshot so every image and measurement binds to the same bytes.
        if media.suffix.lower() != ".mp4":
            raise ValueError("Expected an MP4 export")
        snapshot = workspace / "export.mp4"
        copy2(media, snapshot)
        if artifact_digest(snapshot) != digest:
            raise ValueError("Export changed while taking the review snapshot")
        directory = workspace / "evidence"
        directory.mkdir()
        probe, has_audio = probe_export(snapshot, twitch_native=twitch_native)
        duration = video_duration(snapshot)
        marks = list(timestamps) or [duration * (index + 0.5) / 6 for index in range(6)]
        marks = sorted(set(marks))
        if len(marks) > MAX_FRAMES or any(not math.isfinite(t) or not 0 <= t < duration for t in marks):
            raise ValueError(f"Use up to {MAX_FRAMES} distinct timestamps within the video")
        command_output(*ffmpeg, "-loglevel", "error", "-i", str(snapshot), "-map", "0:v:0",
                       "-map", "0:a:0?", "-abort_on", "empty_output_stream", "-f", "null", "-")

        frames = []
        for seconds in marks:
            filename = f"frame-{len(frames) + 1:02d}.png"
            frame = directory / filename
            command_output(*ffmpeg, "-loglevel", "error", "-ss", f"{seconds:.9f}", "-i", str(snapshot),
                           "-map", "0:v:0", "-vf", THUMBNAIL, "-frames:v", "1", str(frame))
            if not frame.is_file():
                if timestamps:
                    raise ValueError(f"No frame at or after {seconds:.9f} seconds")
                continue
            frames.append({"requested_seconds": seconds, "file": filename})
        if not frames:
            raise ValueError("No review frames were written")
        columns = min(3, len(frames))
        rows = math.ceil(len(frames) / columns)
        command_output(*ffmpeg, "-loglevel", "error", "-framerate", "1", "-i", str(directory / "frame-%02d.png"),
                       "-vf", f"tile={columns}x{rows}:padding=6:margin=6", "-frames:v", "1",
                       str(directory / "contact-sheet.png"))

        peak, silent_seconds, statistics = measure_audio(snapshot, ffmpeg) if has_audio else (None, 0, "")
        audio_duration = next(
            (float(track["duration"]) for track in probe["streams"] if track["codec_type"] == "audio"), 0,
        )
        measurements = save_audio_evidence(snapshot, directory, ffmpeg, statistics) if has_audio and audio_evidence else []
        if artifact_digest(media) != digest:
            raise ValueError("Export changed during review")
        manifest = {
            "schema_version": 1,
            **({"twitch_native": True} if twitch_native else {}),
            "artifact": str(media),
            "artifact_sha256": digest,
            "video_seconds": duration,
            "full_decode_passed": True,
            "audio_present": has_audio,
            "audio_peak_dbfs": peak,
            "audio_signal_seconds": max(0, audio_duration - silent_seconds),
            "audio_evidence": measurements,
            "frames": frames,
            "contact_sheet": "contact-sheet.png",
            "probe": probe,
        }
        (directory / "review.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if output.exists():
            raise ValueError(f"Choose a new output directory: {output}")
        directory.rename(output)
    return output / "review.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new evidence directory")
    parser.add_argument("--at", type=float, action="append", default=[],
                        help="export-relative seconds to sample, repeat up to 12 times")
    parser.add_argument("--audio-evidence", action="store_true",
                        help="save audio diagnostics for authorized audio")
    parser.add_argument("--twitch-native", action="store_true", help="Review an official Twitch portrait rendition")
    arguments = parser.parse_args(argv)
    try:
        print(review_export(arguments.media, arguments.out, arguments.at,
                            arguments.audio_evidence, twitch_native=arguments.twitch_native))
    except (OSError, ValueError) as error:
        parser.exit(1, f"Review failed: {error}\n")


if __name__ == "__main__":
    main()
