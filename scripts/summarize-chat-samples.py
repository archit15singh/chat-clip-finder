#!/usr/bin/env python3
"""Summarize timed browser chat observations without storing chat text."""

import argparse
import json
from pathlib import Path
from statistics import median


def rate(samples):
    return 10000 * sum(count for _, count in samples) / sum(ms for ms, _ in samples)


def summarize(record, baseline_samples, window_samples):
    samples = record["samples"]
    if type(record["ended_unix_ms"]) is not int:
        raise ValueError("The observation end must be a Unix timestamp in milliseconds")
    for elapsed, count in samples:
        if type(elapsed) is not int or elapsed <= 0:
            raise ValueError("Sample duration must be a positive number of milliseconds")
        if count is not None and (type(count) is not int or count < 0):
            raise ValueError("Message count must be a nonnegative integer or null for a gap")

    elapsed_ms = sum(ms for ms, _ in samples)
    result = {
        "sample_seconds": round(elapsed_ms / 1000, 2),
        "observed_messages": sum(count for _, count in samples if count is not None),
        "gaps": sum(count is None for _, count in samples),
    }
    warmup = samples[:baseline_samples]
    if len(warmup) < baseline_samples or any(count is None for _, count in warmup):
        return {**result, "status": "insufficient baseline"}
    baseline = max(1, median(rate([sample]) for sample in warmup))
    end_ms = record["ended_unix_ms"] - elapsed_ms + sum(ms for ms, _ in warmup)
    scored = []
    for end in range(baseline_samples, len(samples)):
        end_ms += samples[end][0]
        start = end + 1 - window_samples
        window = samples[start:end+1]
        if start >= baseline_samples and all(count is not None for _, count in window):
            scored.append((rate(window), end_ms, sum(ms for ms, _ in window)))
    if not scored:
        return {**result, "status": "insufficient observation"}

    peak, peak_end_ms, peak_duration_ms = max(scored, key=lambda sample: sample[0])
    return {
        **result,
        "status": "scored",
        "reference_rate_per_10s": round(baseline, 2),
        "peak_sustained_rate_per_10s": round(peak, 2),
        "peak_sustained_ratio": round(peak / baseline, 2),
        "peak_ended_unix_ms": peak_end_ms,
        "peak_duration_ms": peak_duration_ms,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("samples", type=Path)
    parser.add_argument("--baseline-samples", type=int, required=True)
    parser.add_argument("--window-samples", type=int, required=True)
    args = parser.parse_args()
    if args.baseline_samples < 1 or args.window_samples < 1:
        parser.error("Sample counts must be positive")
    try:
        channels = json.loads(args.samples.read_text(encoding="utf-8"))["channels"]
        if not isinstance(channels, dict):
            raise ValueError("Expected a channels object keyed by channel login")
        report = {
            channel: summarize(record, args.baseline_samples, args.window_samples)
            for channel, record in channels.items()
        }
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
