#!/usr/bin/env python3
"""Check analytics readings against verified posts and calculate their actual age."""

import argparse
from contextlib import closing
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


# Allow a practical collection window while keeping late readbacks out of matched-age comparisons.
MILESTONE_LAG_HOURS = {24: 1, 72: 3, 168: 7}


def checked_milestone(row, age_seconds):
    if "milestone_hours" not in row:
        return {}
    hours = row["milestone_hours"]
    if type(hours) is not int or hours not in MILESTONE_LAG_HOURS:
        raise ValueError("Use a 24, 72 or 168 hour milestone")
    if not hours * 3600 <= age_seconds <= (hours + MILESTONE_LAG_HOURS[hours]) * 3600:
        raise ValueError("Actual post age is outside the named milestone window")
    return {"milestone_hours": hours}


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
            age = (observed - public_at).total_seconds()
            milestone = checked_milestone(row, age)
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
            "age_seconds": age, **milestone,
            "metric_source": source, "metrics": metrics,
        })
    return checked


def read_verified_posts(database):
    uri = database.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
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
