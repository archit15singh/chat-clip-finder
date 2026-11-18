#!/usr/bin/env python3
"""Attach cleared source audio to an existing picture cut without re-encoding video."""

import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory

from clip_finder import command_output, video_duration


def span(value):
    try:
        start, end = map(float, value.split(":"))
    except ValueError:
        raise argparse.ArgumentTypeError("Use start:end in source-file seconds") from None
    if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end):
        raise argparse.ArgumentTypeError("Use finite, nonnegative and increasing source times")
    return start, end


def restore_audio(picture, source, spans, output):
    picture = picture.resolve(strict=True)
    source = source.resolve(strict=True)
    output = output.resolve()
    if output.suffix.lower() != ".mp4" or output.exists():
        raise ValueError("Choose a new MP4 output path")
    duration = video_duration(picture)
    total = sum(end - start for start, end in spans)
    if not spans or abs(total - duration) > 0.05:
        raise ValueError("The summed sound edit must match the picture duration within 50 ms")
    probe = json.loads(command_output(
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=start_time,duration:format=start_time",
        "-of", "json", str(source),
    ))
    if not probe.get("streams"):
        raise ValueError("Source has no audio track")
    stream = probe["streams"][0]
    first_sample = float(stream["start_time"]) - float(probe["format"]["start_time"])
    last_sample = first_sample + float(stream["duration"])
    if any(start < first_sample - 0.002 or end > last_sample + 0.002 for start, end in spans):
        raise ValueError("A sound edit extends beyond the source audio")

    # Use the same container-relative seek clock as the original picture edits.
    inputs = []
    filters = []
    for index, (start, end) in enumerate(spans, 1):
        length = end - start
        fade = min(length / 4, 0.006)
        inputs.extend(("-ss", str(start), "-t", str(length), "-i", str(source)))
        filters.append(
            f"[{index}:a:0]atrim=duration={length:.9f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={fade:.9f},afade=t=out:st={length-fade:.9f}:d={fade:.9f}[a{index}]"
        )
    labels = "".join(f"[a{index}]" for index in range(1, len(spans) + 1))
    filters.append(f"{labels}concat=n={len(spans)}:v=0:a=1[audio]")
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as work:
        draft = Path(work) / "mixed.mp4"
        command_output(
            "ffmpeg", "-v", "error", "-nostdin", "-xerror", "-i", str(picture), *inputs,
            "-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[audio]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-map_metadata", "-1", "-map_chapters", "-1", "-write_tmcd", "0",
            "-movflags", "+faststart", str(draft),
        )
        output.hardlink_to(draft)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("picture", type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("--span", action="append", type=span, required=True, help="ordered source start:end")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(restore_audio(args.picture, args.source, args.span, args.out))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"source audio: {error}\n")


if __name__ == "__main__":
    main()
