#!/usr/bin/env python3
"""Rank ten-second chat surges from a TwitchDownloader VOD export."""

import argparse
from collections import Counter
import json
from math import ceil, floor
from pathlib import Path
import re
from statistics import median


WINDOW_SECONDS = 10
BASELINE_WINDOWS = 6
MIN_MESSAGES = 10
MIN_RATIO = 3
GIFT_NOTICE = re.compile(
    r"\w+ (?:is gifting [\d,]+ Tier [123] Subs to \w+'s community!"
    r"(?: They've gifted a total of [\d,]+ in the channel!)?"
    r"|gifted a Tier [123] sub to \w+!)",
    re.IGNORECASE,
)


def rank_replay(
    export, limit, min_separation=WINDOW_SECONDS, *,
    exclude_gift_notices=False, exclude_chat_commands=(),
):
    video = export["video"]
    start = ceil(video["start"])
    end = floor(video["end"])
    if end - start < WINDOW_SECONDS * (BASELINE_WINDOWS + 1):
        raise ValueError("Export at least 70 complete seconds of chat")

    counts = Counter()
    gift_notices_excluded = 0
    chat_commands_excluded = 0
    excluded_commands = {command.casefold() for command in exclude_chat_commands}
    filter_messages = exclude_gift_notices or excluded_commands
    for comment in export["comments"]:
        body = (comment.get("message") or {}).get("body") if filter_messages else None
        if isinstance(body, str):
            body = body.strip()
            if exclude_gift_notices and GIFT_NOTICE.fullmatch(body):
                gift_notices_excluded += 1
                continue
            if excluded_commands and body and body.split(maxsplit=1)[0].casefold() in excluded_commands:
                chat_commands_excluded += 1
                continue
        counts[floor(comment["content_offset_seconds"])] += 1
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
        if any(
            abs(candidate["start_vod_seconds"] - picked["start_vod_seconds"]) < min_separation
            for picked in selected
        ):
            continue
        candidate["ratio"] = round(candidate["ratio"], 3)
        selected.append(candidate)
        if len(selected) == limit:
            break
    result = {"vod_id": video["id"], "export_start": start, "export_end": end, "peaks": selected}
    if exclude_gift_notices:
        result["gift_notices_excluded"] = gift_notices_excluded
    if excluded_commands:
        result["chat_commands_excluded"] = chat_commands_excluded
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("chat", type=Path)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument(
        "--exclude-gift-notices", action="store_true",
        help="omit recognized English gift-sub announcements from replay counts",
    )
    parser.add_argument(
        "--exclude-chat-command", action="append", default=[], metavar="COMMAND",
        help="omit messages that start with this confirmed !command (repeatable)",
    )
    parser.add_argument(
        "--min-separation", type=int, default=WINDOW_SECONDS, metavar="SECONDS",
        help="minimum time between selected window starts (default: %(default)s)",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.min_separation < WINDOW_SECONDS:
        parser.error(f"--min-separation must be at least {WINDOW_SECONDS} seconds")
    if any(not re.fullmatch(r"!\w[\w-]*", command) for command in args.exclude_chat_command):
        parser.error("--exclude-chat-command requires a single !command token")
    try:
        export = json.loads(args.chat.read_text(encoding="utf-8-sig"))
        result = rank_replay(
            export, args.limit, args.min_separation, exclude_gift_notices=args.exclude_gift_notices,
            exclude_chat_commands=args.exclude_chat_command,
        )
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
