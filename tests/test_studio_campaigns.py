from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from studio_campaigns import prepare, read_cut
from studio_queue import SCHEMA


class CampaignHandoffTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.queue = Path(self.temp.name) / "queue.sqlite3"
        self.now = datetime(2026, 11, 19, 9, tzinfo=timezone.utc)
        self.url = "https://www.youtube.com/shorts/abcdefghijk"
        self.brief = {
            "provider": "content-rewards",
            "campaign_url": "https://contentrewards.com/c/campaigns/example",
            "commissioned_at": "2026-11-19T08:45:00Z",
            "recheck_at": "2026-11-19T10:00:00Z",
            "closes_at": "2026-11-19T12:00:00Z",
            "submission_window_minutes": 30,
            "preapproval_required": False,
            "package_sha256": "exact-package",
            "allowed_source_ids": ["twitch:vod:123"],
            "accounts": {"youtube": "channel-id", "instagram": "@handle"},
            "submission_platforms": ["youtube", "instagram"],
            "checks": {
                "active_and_joined": "Campaign open and joined",
                "account_eligibility": "Verified accounts",
                "source_rights": "Both destinations approved",
                "editorial_rules": "Reviewed copy and audio",
                "payout_route": "Read eligible route",
            },
        }
        package = {"source": {"id": "twitch:vod:123"}, "destinations": {
            "youtube": {"account": "channel-id"}, "instagram": {"account": "@handle"}
        }}
        with closing(sqlite3.connect(self.queue)) as db, db:
            db.executescript(SCHEMA)
            db.execute(
                "INSERT INTO cuts(id,scene,package,fingerprint,artifact,artifact_sha256,reviewer) VALUES (?,?,?,?,?,?,?)",
                ("cut-v1", "scene", json.dumps(package), "exact-package", "/tmp/campaign.mp4", "digest", "reviewer"),
            )
            db.execute("INSERT INTO deliveries(cut_id,platform,state) VALUES ('cut-v1','youtube','ready')")

    def run_phase(self, phase, *, platform=None, readback=None):
        return prepare(self.brief, "cut-v1", read_cut(self.queue, "cut-v1"), self.now,
                       phase=phase, platform=platform, readback=readback)

    def publish_receipt(self, public_at="2026-11-19T08:50:00Z"):
        receipt = {"public_url": self.url, "public_at": public_at, "visibility": "public",
                   "account": "channel-id"}
        with closing(sqlite3.connect(self.queue)) as db, db:
            db.execute(
                "UPDATE deliveries SET state='verified',receipt=? WHERE cut_id='cut-v1' AND platform='youtube'",
                (json.dumps(receipt),),
            )

    def test_preflight_submission_and_delayed_payout_readback(self):
        self.assertEqual(self.run_phase("preflight")["status"], "ready-for-uploader")
        with self.assertRaisesRegex(ValueError, "verified receipt"):
            self.run_phase("submission", platform="youtube")
        self.publish_receipt()
        ready = self.run_phase("submission", platform="youtube")
        self.assertEqual(ready["status"], "ready-to-submit")
        self.assertEqual(ready["submit_by"], "2026-11-19T09:20:00+00:00")
        with self.assertRaisesRegex(ValueError, "before publication"):
            self.run_phase("preflight")

        self.now = datetime(2026, 11, 23, tzinfo=timezone.utc)
        evidence = {
            "campaign_url": self.brief["campaign_url"],
            "public_url": self.url + "?si=abc123",
            "submission_id": "provider-post-9",
            "submitted_at": "2026-11-19T08:58:00Z",
            "observed_at": "2026-11-22T01:02:00Z",
            "status": "credited", "amount": "1.23", "currency": "USD",
            "evidence": "Read exact submission and wallet credit in the dashboard",
        }
        credited = self.run_phase("readback", platform="youtube", readback=evidence)
        self.assertEqual((credited["public_url"], credited["status"], credited["amount"]),
                         (self.url, "credited", "1.23"))
        with self.assertRaisesRegex(ValueError, "verified post"):
            self.run_phase("readback", platform="youtube",
                           readback={**evidence, "public_url": "https://youtube.com/shorts/aaaaaaaaaaa"})

    def test_checks_brief_identity_and_preapproval(self):
        self.brief["allowed_source_ids"] = ["different-vod"]
        with self.assertRaisesRegex(ValueError, "source is outside"):
            self.run_phase("preflight")
        self.brief["allowed_source_ids"] = ["twitch:vod:123"]
        self.brief["package_sha256"] = "previous-cut"
        with self.assertRaisesRegex(ValueError, "exact package"):
            self.run_phase("preflight")
        self.brief["package_sha256"] = "exact-package"
        self.brief["preapproval_required"] = True
        with self.assertRaisesRegex(ValueError, "draft approval"):
            self.run_phase("preflight")
        self.brief["draft_approval"] = {
            "package_sha256": "exact-package", "reference": "draft-7",
            "approved_at": "2026-11-19T08:55:00Z",
        }
        self.publish_receipt()
        with self.assertRaisesRegex(ValueError, "predates.*draft approval"):
            self.run_phase("submission", platform="youtube")

    def test_blocks_showcase_posts_and_expired_submission_windows(self):
        self.publish_receipt("2026-11-19T08:30:00Z")
        with self.assertRaisesRegex(ValueError, "predates"):
            self.run_phase("submission", platform="youtube")
        self.publish_receipt()
        self.now = datetime(2026, 11, 19, 9, 20, tzinfo=timezone.utc)
        with self.assertRaisesRegex(ValueError, "outside.*window"):
            self.run_phase("submission", platform="youtube")

    def test_single_platform_campaign_requires_exact_publishing_destinations(self):
        self.brief["accounts"] = {"youtube": "channel-id"}
        self.brief["submission_platforms"] = ["youtube"]
        with self.assertRaisesRegex(ValueError, "destinations and accounts"):
            self.run_phase("preflight")
        package, *cut = read_cut(self.queue, "cut-v1")
        package["destinations"].pop("instagram")
        result = prepare(self.brief, "cut-v1", (package, *cut), self.now, phase="preflight")
        self.assertEqual(result["submission_platforms"], ["youtube"])
        self.brief["submission_platforms"] = ["instagram"]
        with self.assertRaisesRegex(ValueError, "among the campaign accounts"):
            prepare(self.brief, "cut-v1", (package, *cut), self.now, phase="preflight")
