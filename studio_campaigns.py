#!/usr/bin/env python3
"""Check campaign handoffs against the brief and the local publishing queue."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit

from studio_observations import timestamp
from studio_queue import PLATFORMS, QUEUE_PATH, permalink, read_json, require_text


PROVIDERS = {
    "content-rewards": ("contentrewards.com", "whop.com"),
    "vyro": ("vyro.com",),
    "clipster": ("clipster.com",),
}
CHECKS = ("active_and_joined", "account_eligibility", "source_rights", "editorial_rules", "payout_route")


def verified_brief(brief, now, *, live=True):
    provider = require_text(brief, "provider")
    link = urlsplit(require_text(brief, "campaign_url"))
    domains = PROVIDERS.get(provider, ())
    if link.scheme != "https" or link.username is not None or not any(
        link.hostname == domain or (link.hostname or "").endswith("." + domain) for domain in domains
    ):
        raise ValueError("Campaign URL must be on the selected provider")
    accounts = brief["accounts"]
    if not isinstance(accounts, dict) or not accounts or set(accounts) - set(PLATFORMS):
        raise ValueError("Name the exact supported accounts cleared for this campaign")
    targets = brief["submission_platforms"]
    if not isinstance(targets, list) or not targets or len(set(targets)) != len(targets) or set(targets) - set(accounts):
        raise ValueError("Name unique submission platforms among the campaign accounts")
    for platform in accounts:
        require_text(brief["accounts"], platform)
    sources = brief["allowed_source_ids"]
    if not isinstance(sources, list) or not sources or any(
        not isinstance(source_id, str) or not source_id.strip() for source_id in sources
    ):
        raise ValueError("Record the eligible source IDs before commissioning a cut")
    for check in CHECKS:
        require_text(brief["checks"], check)
    commissioned = timestamp(require_text(brief, "commissioned_at"))
    recheck = timestamp(require_text(brief, "recheck_at"))
    closes = timestamp(brief["closes_at"]) if brief.get("closes_at") is not None else None
    minutes = brief["submission_window_minutes"]
    if minutes is not None and (type(minutes) is not int or not 0 < minutes <= 525600):
        raise ValueError("Use a positive minute window or null if the verified brief has none")
    if provider == "content-rewards" and (minutes is None or minutes > 30):
        raise ValueError("Content Rewards post link deadline is at most 30 minutes after publication")
    if not commissioned <= now or recheck <= commissioned or (closes and closes <= commissioned):
        raise ValueError("Invalid commission or campaign timing")
    if live and (now >= recheck or (closes and now >= closes)):
        raise ValueError("Campaign closed or brief stale. Recheck the live campaign before proceeding.")
    return commissioned, closes, minutes


def read_cut(database, cut_id):
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as connection:
        cut = connection.execute(
            "SELECT package, reviewer, fingerprint, replaced_by FROM cuts WHERE id = ?", (cut_id,)
        ).fetchone()
        if cut is None:
            raise ValueError("Unknown cut")
        receipts = {
            platform: json.loads(receipt)
            for platform, receipt in connection.execute(
                "SELECT platform, receipt FROM deliveries WHERE cut_id = ? AND state = 'verified'", (cut_id,)
            )
        }
    package, reviewer, fingerprint, replaced_by = cut
    return json.loads(package), reviewer, fingerprint, replaced_by, receipts


def prepare(brief, cut_id, cut, now, *, phase, platform=None, readback=None):
    commissioned, closes, minutes = verified_brief(brief, now, live=phase != "readback")
    package, reviewer, fingerprint, replaced_by, receipts = cut
    if "edit" in package and package.get("campaign_url") != brief.get("campaign_url"):
        raise ValueError("Campaign must match the campaign URL sealed into the cut")
    if not reviewer or fingerprint != require_text(brief, "package_sha256"):
        raise ValueError("Campaign handoff requires the independently approved exact package")
    if phase == "preflight" and replaced_by:
        raise ValueError("The upload package has been superseded")
    if package["source"]["id"] not in brief["allowed_source_ids"]:
        raise ValueError("Cut source is outside the commissioned brief")
    accounts = brief["accounts"]
    destinations = package["destinations"]
    if set(destinations) != set(accounts) or any(
        destinations[key]["account"] != account for key, account in accounts.items()
    ):
        raise ValueError("Approved destinations and accounts must match the campaign handoff")
    approval = brief.get("draft_approval")
    approval_at = None
    preapproval = brief.get("preapproval_required")
    if type(preapproval) is not bool:
        raise ValueError("Confirm whether the campaign requires a prepublication draft")
    if preapproval:
        if not approval or require_text(approval, "package_sha256") != fingerprint:
            raise ValueError("Campaign draft approval must identify this exact package")
        require_text(approval, "reference")
        approval_at = timestamp(require_text(approval, "approved_at"))
        if not commissioned <= approval_at <= now:
            raise ValueError("Invalid draft approval time")

    result = {"provider": brief["provider"], "campaign_url": brief["campaign_url"], "cut": cut_id,
              "package_sha256": fingerprint}
    if phase == "preflight":
        if (platform is None and receipts) or platform in receipts:
            raise ValueError("Upload preflight must happen before publication")
        if platform is not None and platform not in accounts:
            raise ValueError("Upload preflight requires an approved campaign destination")
        return {**result, "status": "ready-for-uploader", "submission_platforms": brief["submission_platforms"]}

    if platform not in brief["submission_platforms"] or platform not in receipts:
        raise ValueError("Submission requires a verified receipt on an eligible platform")
    receipt = receipts[platform]
    if receipt["account"] != brief["accounts"][platform] or receipt["visibility"] != "public":
        raise ValueError("Post receipt account or visibility differs from the campaign handoff")
    _, public_url = permalink(platform, receipt["public_url"])
    public_at = timestamp(receipt["public_at"])
    deadline = public_at + timedelta(minutes=minutes) if minutes is not None else None
    deadline = min(deadline, closes) if deadline and closes else deadline or closes
    if not commissioned <= public_at <= now or (approval_at and public_at < approval_at):
        raise ValueError("Verified post predates campaign commissioning or required draft approval")
    at = now if readback is None else timestamp(require_text(readback, "submitted_at"))
    if not public_at <= at <= now or (deadline and at >= deadline):
        raise ValueError("Past or outside the verified submission window")
    result.update(platform=platform, public_url=public_url, public_at=public_at.isoformat(),
                  submit_by=deadline.isoformat() if deadline else None)
    if phase == "submission":
        return {**result, "status": "ready-to-submit"}

    _, observed_url = permalink(platform, require_text(readback, "public_url"))
    if observed_url != public_url or require_text(readback, "campaign_url") != result["campaign_url"]:
        raise ValueError("Submission readback must match the campaign and verified post")
    observed_at = timestamp(require_text(readback, "observed_at"))
    if not at <= observed_at <= now:
        raise ValueError("Invalid readback observation time")
    status = require_text(readback, "status")
    if status not in {"pending", "approved", "rejected", "credited", "paid"}:
        raise ValueError("Use a verified provider submission or payout status")
    result.update(status=status, submission_id=require_text(readback, "submission_id"),
                  submitted_at=at.isoformat(), observed_at=observed_at.isoformat(),
                  evidence=require_text(readback, "evidence"))
    if status in {"credited", "paid"}:
        amount = require_text(readback, "amount")
        currency = require_text(readback, "currency")
        numeric = Decimal(amount)
        if not numeric.is_finite() or numeric <= 0 or not re.fullmatch(r"[A-Z]{3}", currency):
            raise ValueError("Record the positive provider-reported amount and its currency")
        result.update(amount=amount, currency=currency)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    commands = parser.add_subparsers(dest="phase", required=True)
    for name in ("preflight", "submission", "readback"):
        command = commands.add_parser(name)
        command.add_argument("brief", type=Path)
        command.add_argument("cut")
        if name != "preflight":
            command.add_argument("platform", choices=PLATFORMS)
        if name == "readback":
            command.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        result = prepare(
            read_json(args.brief), args.cut, read_cut(args.queue, args.cut),
            datetime.now(timezone.utc), phase=args.phase,
            platform=getattr(args, "platform", None),
            readback=read_json(args.evidence) if args.phase == "readback" else None,
        )
    except (OSError, sqlite3.Error, KeyError, TypeError, AttributeError, OverflowError, ValueError, InvalidOperation) as error:
        parser.exit(2, f"studio campaigns: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
