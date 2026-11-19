#!/usr/bin/env python3
"""Capture a short Twitch replay preview with local frames and speech cues."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys


def capture_output(command, failure):
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError(failure)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vod_id", help="Numeric Twitch VOD ID")
    parser.add_argument("--start", type=int, required=True, help="Requested VOD offset in seconds")
    parser.add_argument("--duration", type=int, required=True, help="Preview length in seconds (1–180)")
    parser.add_argument("--out", type=Path, required=True, help="New local output directory")
    parser.add_argument("--model", type=Path, required=True, help="Local Whisper GGML model")
    parser.add_argument("--language", default="en", help="Whisper language code or auto")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+", args.vod_id):
        parser.error("Use a numeric Twitch VOD ID")
    if args.start < 0 or not 1 <= args.duration <= 180:
        parser.error("Start must be nonnegative and duration must be 1–180 seconds")
    if not args.model.is_file():
        parser.error(f"Model not found: {args.model}")

    reference = f"https://www.twitch.tv/videos/{args.vod_id}"
    preview = args.out / "preview.mp4"
    ffmpeg = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error"]
    try:
        args.out.mkdir()
        stream = capture_output([
            "yt-dlp", "--ignore-config", "--socket-timeout", "8", "--retries", "0",
            "-f", "worst", "-g", reference,
        ], "Could not resolve an accessible Twitch replay")
        if not stream.startswith("https://") or "\n" in stream:
            raise ValueError("Expected a single HTTPS media stream")
        capture = subprocess.run([
            *ffmpeg, "-rw_timeout", "12000000", "-ss", str(args.start), "-i", stream,
            "-t", str(args.duration), "-map", "0:v:0", "-map", "0:a:0",
            "-vf", "setsar=1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "21",
            "-c:a", "aac", str(preview),
        ], stderr=subprocess.DEVNULL, timeout=120)
        if capture.returncode:
            raise ValueError("Could not capture video and audio from the requested replay window")
        duration = float(capture_output([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
            "stream=duration", "-of", "default=nw=1:nk=1", str(preview),
        ], "Could not measure the preview"))
        if duration < args.duration - 0.25:
            raise ValueError(f"Replay window ended early ({duration:.3f} of {args.duration}s)")
        subprocess.run([
            *ffmpeg, "-i", str(preview), "-vf",
            f"fps=16/{args.duration}:start_time=0,scale=320:-2,tile=4x4",
            "-frames:v", "1", "-update", "1", str(args.out / "frames.jpg"),
        ], check=True)
        (args.out / "source.json").write_text(json.dumps({
            "reference": reference,
            "requested_vod_start_seconds": args.start,
            "preview_duration_seconds": duration,
        }, indent=2) + "\n", encoding="utf-8")
        subprocess.run([
            sys.executable, str(Path(__file__).with_name("transcribe-clip.py")), str(preview),
            "--model", str(args.model), "--language", args.language,
            "--out", str(args.out / "speech.srt"),
        ], check=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Replay scout failed: {error}\n")
    except subprocess.TimeoutExpired:
        parser.exit(1, "Replay scout timed out while fetching or capturing media\n")
    print(args.out / "source.json")


if __name__ == "__main__":
    main()
