#!/usr/bin/env python3
"""Check analytics readings against verified posts and calculate their actual age."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sqlite3

from studio_queue import PLATFORMS, QUEUE_PATH, permalink, require_text


def timestamp(value):
    moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if moment.utcoffset() is None:
        raise ValueError("Timestamps require a time zone")
    return moment.astimezone(timezone.utc)


def check_observations(rows, published, now):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Expected an array of analytics observations")
    checked = []
    seen = set()
    for index, row in enumerate(rows, 1):
        try:
            platform = require_text(row, "platform")
            if platform not in PLATFORMS:
                raise ValueError("Unknown platform")
            post_id, url = permalink(platform, require_text(row, "url"))
            if (platform, post_id) not in published:
                raise ValueError("Post has no verified publication receipt")
            cut, public_at = published[platform, post_id]
            observed = timestamp(require_text(row, "observed_at"))
            if not public_at <= observed <= now:
                raise ValueError("Observation must fall between publication and now")
            source = require_text(row, "metric_source")
            metrics = row["metrics"]
            if not isinstance(metrics, dict) or not metrics:
                raise ValueError("Provide the platform's metric names and values")
            for label, value in metrics.items():
                if not label.strip() or (value is not None and (
                    type(value) not in (int, float) or not math.isfinite(value) or value < 0
                )):
                    raise ValueError("Expected named nonnegative metrics or null for unavailable")
            key = platform, post_id, observed, source
            if key in seen:
                raise ValueError("Duplicate post, observation time, and metric source")
        except (KeyError, TypeError, AttributeError, OverflowError, ValueError) as error:
            raise ValueError(f"Observation {index}: {error}") from error
        seen.add(key)
        checked.append({
            "cut": cut, "platform": platform, "url": url,
            "published_at": public_at.isoformat(), "observed_at": observed.isoformat(),
            "age_seconds": (observed - public_at).total_seconds(),
            "metric_source": source, "metrics": metrics,
        })
    return checked


def read_verified_posts(database):
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT cut_id, platform, external_id, receipt FROM deliveries WHERE state = 'verified'"
        )
        return {
            (platform, post_id): (cut, timestamp(json.loads(receipt)["public_at"]))
            for cut, platform, post_id, receipt in rows
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("readings", type=Path)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    args = parser.parse_args()
    try:
        checked = check_observations(
            json.loads(args.readings.read_text()), read_verified_posts(args.queue),
            datetime.now(timezone.utc),
        )
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"studio observations: {error}\n")
    print(json.dumps(checked, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
