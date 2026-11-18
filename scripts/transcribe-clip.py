#!/usr/bin/env python3
"""Produce local SubRip speech cues on the source clip's clock."""

import argparse
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import wave


def subrip_time(centiseconds):
    seconds, fraction = divmod(centiseconds, 100)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02},{fraction * 10:03}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--model", type=Path, required=True, help="Local Whisper GGML model")
    parser.add_argument("--language", default="auto", help="Whisper language code or auto")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.video, args.model):
        if not path.is_file():
            parser.error(f"File not found: {path}")
    if args.out.exists():
        parser.error(f"Output already exists: {args.out}")
    try:
        from pywhispercpp.model import Model
    except ImportError:
        parser.error("Install pywhispercpp in the interpreter running this script")

    try:
        with TemporaryDirectory() as directory:
            audio = Path(directory) / "clip.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                "-i", str(args.video.resolve()), "-map", "0:a:0", "-vn",
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(audio),
            ], check=True)
            with wave.open(str(audio), "rb") as decoded:
                audio_end = decoded.getnframes() * 100 // decoded.getframerate()
            model = Model(str(args.model.resolve()), n_threads=4)
            segments = model.transcribe(str(audio), language=args.language)
        cues = []
        adjusted = 0
        for segment in segments:
            spoken = segment.text.strip()
            if not spoken:
                continue
            end = min(segment.t1, audio_end)
            adjusted += end < segment.t1
            if end > segment.t0 >= 0:
                cues.append(
                    f"{len(cues) + 1}\n"
                    f"{subrip_time(segment.t0)} --> {subrip_time(end)}\n{spoken}\n"
                )
        if adjusted:
            print(
                f"Adjusted {adjusted} Whisper cue(s) beyond the decoded audio. "
                "Check the ending against playback.",
                file=sys.stderr,
            )
        if not cues:
            parser.error("Whisper returned no timecoded cues")
        with args.out.open("x", encoding="utf-8") as output:
            output.write("\n".join(cues))
    except (OSError, RuntimeError, subprocess.CalledProcessError, wave.Error) as error:
        parser.exit(1, f"Transcription failed: {error}\n")


if __name__ == "__main__":
    main()
