#!/usr/bin/env python3
"""Capture a short Twitch replay preview with local frames and speech cues."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


def capture_output(command, failure):
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError(failure)
    return result.stdout.strip()


def capture_preview(vod_id, start, length, output):
    reference = f"https://www.twitch.tv/videos/{vod_id}"
    preview = output / "preview.mp4"
    ffmpeg = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error"]
    stream = capture_output([
        "yt-dlp", "--ignore-config", "--socket-timeout", "8", "--retries", "0",
        "-f", "worst", "-g", reference,
    ], "Could not resolve an accessible Twitch replay")
    if not stream.startswith("https://") or "\n" in stream:
        raise ValueError("Expected a single HTTPS media stream")
    # Twitch HLS input seeks can skip the first segment of the window.
    # Seek slightly earlier, then decode up to the requested start.
    lead = min(start, 4)
    input_start = start - lead
    seek = ["-ss", str(input_start)] if input_start else []
    trim = ["-ss", str(lead)] if lead else []
    capture = subprocess.run([
        *ffmpeg, "-rw_timeout", "12000000", *seek, "-i", stream, *trim,
        "-t", str(length), "-map", "0:v:0", "-map", "0:a:0",
        "-vf", "setsar=1", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "21",
        "-c:a", "aac", str(preview),
    ], stderr=subprocess.DEVNULL, timeout=120)
    if capture.returncode:
        raise ValueError("Could not capture video and audio from the requested replay window")
    measured = capture_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
        "stream=duration", "-of", "default=nw=1:nk=1", str(preview),
    ], "Could not measure the preview")
    if not measured:
        raise ValueError("Replay capture contains no video frames")
    duration = float(measured)
    if duration < length - 0.25:
        raise ValueError(f"Replay window ended early ({duration:.3f} of {length}s)")
    subprocess.run([
        *ffmpeg, "-i", str(preview), "-vf",
        f"fps=16/{length}:start_time=0,scale=320:-2,tile=4x4",
        "-frames:v", "1", "-update", "1", str(output / "frames.jpg"),
    ], check=True)
    (output / "source.json").write_text(json.dumps({
        "reference": reference,
        "requested_vod_start_seconds": start,
        "preview_duration_seconds": duration,
    }, indent=2) + "\n", encoding="utf-8")


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

    try:
        if args.out.exists() or args.out.is_symlink():
            raise FileExistsError(f"Output already exists: {args.out}")
        with TemporaryDirectory(prefix=".replay-scout-", dir=args.out.parent) as directory:
            output = Path(directory)
            capture_preview(args.vod_id, args.start, args.duration, output)
            output.rename(args.out)
        subprocess.run([
            sys.executable, str(Path(__file__).with_name("transcribe-clip.py")), str(args.out / "preview.mp4"),
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
