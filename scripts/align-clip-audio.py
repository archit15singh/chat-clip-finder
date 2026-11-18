#!/usr/bin/env python3
"""Match an exact clip to a bounded replay excerpt using independent audio anchors."""

import argparse
import json
import subprocess
from pathlib import Path


SAMPLE_RATE = 16000
ANCHOR_SECONDS = 2
MIN_CORRELATION = 0.8


def pcm(path, np):
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0",
         "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-"],
        check=True, stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<i2").astype("float64")


def align(clip, replay, np):
    width = SAMPLE_RATE * ANCHOR_SECONDS
    if len(clip) < 3 * width or len(replay) < len(clip):
        raise ValueError("Use a clip of at least six seconds and a replay excerpt that contains it")

    # Restrict candidate offsets to those where the complete clip fits.
    offsets = len(replay) - len(clip) + 1
    length = 1 << (len(replay) + width - 1).bit_length()
    spectrum = np.fft.rfft(replay, length)
    sums = np.r_[0.0, replay.cumsum()]
    squares = np.r_[0.0, (replay * replay).cumsum()]
    matches = []
    for start in np.linspace(0, len(clip) - width, 3, dtype=int):
        anchor = clip[start:start + width].copy()
        anchor -= anchor.mean()
        power = np.linalg.norm(anchor)
        if not power:
            raise ValueError("An anchor is silent")

        stop = start + offsets
        means = sums[start + width:stop + width] - sums[start:stop]
        energy = squares[start + width:stop + width] - squares[start:stop]
        energy = np.sqrt(np.maximum(energy - means**2 / width, 1))
        corr = np.fft.irfft(spectrum * np.fft.rfft(anchor[::-1], length), length)
        scores = corr[start + width - 1:stop + width - 1] / (power * energy)
        offset = int(scores.argmax())
        confidence = float(scores[offset])
        alternate = scores.copy()
        radius = int(0.05 * SAMPLE_RATE)
        alternate[max(0, offset - radius):offset + radius + 1] = -1
        if confidence < MIN_CORRELATION or alternate.max() > confidence - 0.03:
            raise ValueError("An anchor has no clear unique match")
        matches.append((offset, confidence))

    positions = sorted(offset for offset, _ in matches)
    if positions[-1] - positions[0] > SAMPLE_RATE * 0.05:
        raise ValueError("Audio anchors disagree on the clip offset")
    return positions[1] / SAMPLE_RATE, matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", type=Path)
    parser.add_argument("replay", type=Path, help="Bounded replay excerpt containing the clip")
    parser.add_argument("--replay-start", required=True, type=float, help="Verified VOD offset in seconds")
    args = parser.parse_args()
    try:
        import numpy as np

        if not np.isfinite(args.replay_start) or args.replay_start < 0:
            raise ValueError("Replay start must be a finite nonnegative number")
        clip = pcm(args.clip, np)
        offset, matches = align(clip, pcm(args.replay, np), np)
    except (ImportError, OSError, subprocess.CalledProcessError, ValueError) as error:
        parser.exit(1, f"Audio alignment failed: {error}\n")
    start = args.replay_start + offset
    print(json.dumps({
        "vod_start": round(start, 6),
        "vod_end": round(start + len(clip) / SAMPLE_RATE, 6),
        "anchors": [
            {"offset_seconds": offset / SAMPLE_RATE, "correlation": round(score, 4)}
            for offset, score in matches
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
