#!/usr/bin/env python3
"""Rank ten-second chat surges from a TwitchDownloader VOD export."""

import argparse
from collections import Counter
import json
from math import ceil, floor
from pathlib import Path
from statistics import median


WINDOW_SECONDS = 10
BASELINE_WINDOWS = 6
MIN_MESSAGES = 10
MIN_RATIO = 3


def rank_replay(export, limit):
    video = export["video"]
    start = ceil(video["start"])
    end = floor(video["end"])
    if end - start < WINDOW_SECONDS * (BASELINE_WINDOWS + 1):
        raise ValueError("Export at least 70 complete seconds of chat")

    counts = Counter(floor(comment["content_offset_seconds"]) for comment in export["comments"])
    totals = {
        second: sum(counts[i] for i in range(second, second + WINDOW_SECONDS))
        for second in range(start, end - WINDOW_SECONDS + 1)
    }
    candidates = []
    for second in range(start + WINDOW_SECONDS * BASELINE_WINDOWS, end - WINDOW_SECONDS + 1):
        history = [totals[second - i * WINDOW_SECONDS] for i in range(BASELINE_WINDOWS, 0, -1)]
        baseline = median(history)
        messages = totals[second]
        ratio = messages / max(1, baseline)
        if messages < MIN_MESSAGES or ratio < MIN_RATIO:
            continue
        candidates.append({
            "start_vod_seconds": second,
            "end_vod_seconds": second + WINDOW_SECONDS,
            "messages": messages,
            "baseline_windows": history,
            "baseline_median": baseline,
            "ratio": ratio,
        })

    selected = []
    for candidate in sorted(candidates, key=lambda item: (item["ratio"], item["messages"]), reverse=True):
        if any(abs(candidate["start_vod_seconds"] - picked["start_vod_seconds"]) < WINDOW_SECONDS
               for picked in selected):
            continue
        candidate["ratio"] = round(candidate["ratio"], 3)
        selected.append(candidate)
        if len(selected) == limit:
            break
    return {"vod_id": video["id"], "export_start": start, "export_end": end, "peaks": selected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chat", type=Path)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    try:
        export = json.loads(args.chat.read_text(encoding="utf-8-sig"))
        result = rank_replay(export, args.limit)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
