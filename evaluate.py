#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path
import sys


def intervals(rows, duration, description):
    if not isinstance(rows, list):
        raise ValueError(f"Expected a list of {description}")
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Expected an object for {description} #{number}")
        start = row.get("start_seconds")
        end = row.get("end_seconds")
        if (type(start) not in (int, float) or type(end) not in (int, float)
                or not 0 <= start < end <= duration):
            raise ValueError(f"Invalid interval for {description} #{number}")
    return [(row["start_seconds"], row["end_seconds"]) for row in rows]


def evaluate(report, labels):
    duration = report.get("video_duration_seconds") if isinstance(report, dict) else None
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Expected a valid video_duration_seconds in the clip report")
    clips = intervals(report.get("clips"), duration, "candidate clips")
    moments = intervals(labels, duration, "labeled moments")
    if not moments:
        raise ValueError("Need at least one labeled moment")

    outcomes = []
    covering_candidates = set()
    for label, (start, end) in zip(labels, moments):
        full = []
        partial = []
        for rank, (clip_start, clip_end) in enumerate(clips, start=1):
            if clip_start <= start and end <= clip_end:
                full.append(rank)
            elif clip_start < end and start < clip_end:
                partial.append(rank)
        covering_candidates.update(full)
        outcomes.append({**label, "covered_by": full, "partially_covered_by": partial})

    fully_covered = sum(bool(row["covered_by"]) for row in outcomes)
    partially_covered = sum(not row["covered_by"] and bool(row["partially_covered_by"]) for row in outcomes)
    return {
        "candidates": len(clips),
        "labeled_moments": len(moments),
        "fully_covered": fully_covered,
        "partially_covered": partially_covered,
        "missed": len(moments) - fully_covered - partially_covered,
        "full_coverage_rate": fully_covered / len(moments),
        "candidates_covering_a_label": len(covering_candidates),
        "moments": outcomes,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare proposed clips with labeled source moments.")
    parser.add_argument("--report", type=Path, required=True, help="clips.json from any clipper run")
    parser.add_argument("--labels", type=Path, required=True, help="JSON array of intervals in local video time")
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        labels = json.loads(args.labels.read_text(encoding="utf-8"))
        print(json.dumps(evaluate(report, labels), indent=2))
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
