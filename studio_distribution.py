#!/usr/bin/env python3
"""Validate an organic placement brief and its readback against a verified release."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from studio_observations import read_verified_posts, timestamp
from studio_queue import PLATFORMS, QUEUE_PATH, permalink, read_json, require_text, serialize

VENUE_BASES = ("owned", "rules_allow", "moderator_invited")


def https_url(mapping, key):
    value = require_text(mapping, key)
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username is not None:
        raise ValueError(f"{key} must be an HTTPS URL without credentials")
    return value


def hostname(url):
    return urlsplit(url).hostname.removeprefix("www.")


def check_brief(brief, published, now):
    platform = require_text(brief, "platform")
    if platform not in PLATFORMS:
        raise ValueError("Unknown release platform")
    post_id, post_url = permalink(platform, require_text(brief, "post_url"))
    if (platform, post_id) not in published:
        raise ValueError("Post has no verified publication receipt")
    cut, public_at = published[platform, post_id]
    if require_text(brief, "cut") != cut:
        raise ValueError("Cut does not match the verified publication receipt")

    checked_at = timestamp(require_text(brief, "rules_checked_at"))
    if checked_at > now:
        raise ValueError("Venue rule check cannot be in the future")
    venue_basis = require_text(brief, "venue_basis")
    if venue_basis not in VENUE_BASES:
        raise ValueError("Choose an owned or explicitly permitted venue")

    fields = (
        "rules_evidence", "publisher", "audience_fit", "copy", "disclosure",
        "measurement",
    )
    plan = {field: require_text(brief, field) for field in fields}
    plan.update(
        cut=cut, platform=platform, post_url=post_url, public_at=public_at.isoformat(),
        venue_url=https_url(brief, "venue_url"), venue_basis=venue_basis,
        rules_checked_at=checked_at.isoformat(),
    )
    if brief.get("campaign") is not None:
        plan["campaign"] = require_text(brief, "campaign")
        plan["campaign_distribution_terms"] = require_text(brief, "campaign_distribution_terms")
    canonical = serialize(plan).encode("utf-8")
    return {**plan, "brief_sha256": hashlib.sha256(canonical).hexdigest()}


def check_placement(plan, readback, now):
    if require_text(readback, "brief_sha256") != plan["brief_sha256"]:
        raise ValueError("Placement readback belongs to a different brief")
    placement = https_url(readback, "placement_url")
    if hostname(placement) != hostname(plan["venue_url"]):
        raise ValueError("Placement permalink must be on the planned venue's host")
    if urlsplit(placement).path.rstrip("/") == urlsplit(plan["venue_url"]).path.rstrip("/"):
        raise ValueError("Use the placement's own permalink, not the venue landing page")
    _, post_url = permalink(plan["platform"], require_text(readback, "linked_post_url"))
    if post_url != plan["post_url"]:
        raise ValueError("Placement links to a different release")
    if require_text(readback, "publisher") != plan["publisher"]:
        raise ValueError("Placement publisher does not match the brief")
    if require_text(readback, "copy") != plan["copy"]:
        raise ValueError("Visible copy does not match the brief")

    placed = timestamp(require_text(readback, "placed_at"))
    observed = timestamp(require_text(readback, "verified_at"))
    published_at = timestamp(plan["public_at"])
    if not max(published_at, timestamp(plan["rules_checked_at"])) <= placed <= observed <= now:
        raise ValueError("Placement times must follow publication and the rule check")
    return {
        "brief_sha256": plan["brief_sha256"],
        "cut": plan["cut"],
        "platform": plan["platform"],
        "post_url": post_url,
        "placement_url": placement,
        "publisher": plan["publisher"],
        "placed_at": placed.isoformat(),
        "verified_at": observed.isoformat(),
        "post_age_seconds_at_placement": (placed - published_at).total_seconds(),
        "evidence": require_text(readback, "evidence"),
        "measurement": plan["measurement"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("brief", type=Path)
    parser.add_argument("--readback", type=Path)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    args = parser.parse_args()
    try:
        now = datetime.now(timezone.utc)
        plan = check_brief(read_json(args.brief), read_verified_posts(args.queue), now)
        result = check_placement(plan, read_json(args.readback), now) if args.readback else plan
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.exit(2, f"studio distribution: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
