from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from tempfile import TemporaryDirectory
import unittest

from review_media import review_export
from studio_queue import LEASE_SECONDS, Queue


SCRIPT = Path(__file__).resolve().parent.parent / "studio_queue.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs FFmpeg and ffprobe")
class StudioQueueTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workspace = TemporaryDirectory()
        cls.addClassCleanup(workspace.cleanup)
        root = Path(workspace.name)
        cls.media = []
        for color in ("red", "blue"):
            video = root / f"{color}.mp4"
            subprocess.run([
                "ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color={color}:s=90x160:d=1",
                "-c:v", "libx264", str(video),
            ], check=True)
            cls.media.append((video, review_export(video, root / color, (0,))))

    def setUp(self):
        workspace = TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.db_path = self.root / "queue.sqlite3"
        database = sqlite3.connect(self.db_path)
        self.addCleanup(database.close)
        self.now = time.time()
        self.queue = Queue(database, self.db_path.with_suffix(".sqlite3.media"), lambda: self.now)

    def write(self, filename, value):
        path = self.root / filename
        path.write_text(json.dumps(value))
        return path

    def manifest(self, cut="first", scene="scene", *, media=0, supersedes=None, caption="A specific hook"):
        artifact, report = self.media[media]
        return self.write(f"{cut}.json", {
            "id": cut, "scene": scene, "supersedes": supersedes, "editor": "editor",
            "artifact": str(artifact), "media_review": str(report),
            "source": {"id": "vod", "creator": "Creator", "reference": "local test",
                       "credit": "Creator on Twitch", "clock": "vod-offset", "start": 18, "end": 19},
            "editorial_choice": "Open on the red frame", "experiment": "Test the opening",
            "destinations": {
                "youtube": {"account": "channel", "title": "Title", "caption": caption,
                            "reuse_cleared": True, "rights_evidence": "Original synthetic fixture"},
                "instagram": {"account": "@profile", "caption": "Instagram-specific caption",
                              "reuse_cleared": True, "rights_evidence": "Original synthetic fixture"},
            },
        })

    def approve(self, staged, reviewer="independent"):
        return self.queue.review(staged["cut"], self.write("decision.json", {
            "reviewer": reviewer, "evidence": "Checked the opening, credit and phone-size frames",
            "verdict": "approve", "package_sha256": staged["package_sha256"],
        }))

    def receipt(self, claim, url, **overrides):
        copy = claim["destination"]
        data = {
            "account": copy["account"], "caption": copy["caption"], "visibility": "public",
            "artifact_sha256": claim["artifact_sha256"], "evidence": "Reopened the public post",
            "public_url": url, "public_at": datetime.fromtimestamp(self.now, timezone.utc).isoformat(),
        }
        if "title" in copy:
            data["title"] = copy["title"]
        return self.write("receipt.json", {**data, **overrides})

    def test_review_binds_copy_and_revision(self):
        manifest = self.manifest()
        staged = self.queue.stage(manifest)
        self.assertEqual(self.queue.stage(manifest), staged)
        self.assertIsNone(self.queue.claim("worker"))
        with self.assertRaisesRegex(ValueError, "independent"):
            self.approve(staged, "EDITOR")
        with self.assertRaisesRegex(ValueError, "different package"):
            self.queue.stage(self.manifest(caption="Different text"))
        with self.assertRaisesRegex(ValueError, "current cut"):
            self.queue.stage(self.manifest(cut="no-link"))
        revised = self.queue.stage(self.manifest(cut="revision", supersedes="first", caption="Different text"))
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            self.approve({**revised, "package_sha256": staged["package_sha256"]})
        self.approve(revised)
        self.assertEqual(self.queue.claim("worker")["destination"]["caption"], "Different text")

    def test_independent_cli_workers_and_expired_claim(self):
        self.approve(self.queue.stage(self.manifest()))
        command = [sys.executable, str(SCRIPT), "--queue", str(self.db_path), "claim", "--worker"]
        workers = [
            subprocess.Popen([*command, name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for name in ("one", "two")
        ]
        claims = []
        for worker in workers:
            out, err = worker.communicate(timeout=10)
            self.assertEqual(worker.returncode, 0, err)
            claims.append(json.loads(out))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        old = next(claim for claim in claims if claim is not None)
        self.now = old["expires"] + 1
        fresh = self.queue.claim("replacement")
        self.assertNotEqual(old["token"], fresh["token"])
        with self.assertRaisesRegex(ValueError, "current"):
            self.queue.begin(old["token"])

    def test_two_commands_initialize_a_fresh_database(self):
        fresh = self.root / "fresh.sqlite3"
        command = [sys.executable, str(SCRIPT), "--queue", str(fresh), "status"]
        workers = [
            subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for _ in range(2)
        ]
        for worker in workers:
            out, err = worker.communicate(timeout=10)
            self.assertEqual(worker.returncode, 0, err)
            self.assertEqual(json.loads(out), [])

    def test_spooled_frame_must_still_match_the_staged_review(self):
        staged = self.queue.stage(self.manifest())
        review = Path(self.queue.inspect(staged["cut"])["media_review"])
        frame = review.parent / "frame-01.png"
        self.assertTrue(frame.is_file())
        frame.write_bytes(b"replaced")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            self.approve(staged)

    def test_public_readback_and_ambiguous_second_platform(self):
        self.approve(self.queue.stage(self.manifest()))
        youtube = self.queue.claim("worker")
        self.assertEqual(self.queue.begin(youtube["token"])["state"], "submitting")
        yt_url = "https://youtube.com/shorts/abcdefghijk?si=one"
        self.assertEqual(self.queue.remember(youtube["token"], yt_url), "abcdefghijk")
        with self.assertRaisesRegex(ValueError, "post ID"):
            self.queue.finish(youtube["token"], self.receipt(youtube, "https://youtube.com/shorts/abcdefghijl"))
        with self.assertRaisesRegex(ValueError, "timestamp"):
            self.queue.finish(youtube["token"], self.receipt(youtube, yt_url, public_at="2000-01-01T00:00:00Z"))
        with self.assertRaisesRegex(ValueError, "caption"):
            self.queue.finish(youtube["token"], self.receipt(youtube, yt_url, caption="Wrong"))
        proof = self.receipt(youtube, yt_url)
        self.assertEqual(self.queue.finish(youtube["token"], proof), "verified")
        self.assertEqual(self.queue.finish(youtube["token"], proof), "verified")
        instagram = self.queue.claim("worker")
        self.assertEqual(instagram["platform"], "instagram")
        self.queue.begin(instagram["token"])
        self.now += LEASE_SECONDS + 1
        self.assertIsNone(self.queue.claim("other-worker"))
        states = {row["platform"]: row["state"] for row in self.queue.status()}
        self.assertEqual(states, {"youtube": "verified", "instagram": "reconcile"})
        schedule = self.queue.milestones()
        self.assertEqual([(row["platform"], row["age_hours"]) for row in schedule],
                         [("youtube", age) for age in (24, 72, 168)])
        published_at = datetime.fromisoformat(json.loads(proof.read_text())["public_at"])
        self.assertEqual(datetime.fromisoformat(schedule[0]["due_at"]) - published_at, timedelta(days=1))
        absent = {"account": "@profile", "outcome": "absent", "prior_worker_stopped": True,
                  "evidence": "Checked owner account and creation flow",
                  "pending_uploads_checked": True, "public_posts_checked": True}
        with self.assertRaisesRegex(ValueError, "pending"):
            self.queue.reconcile(instagram["token"], self.write("absent.json", {
                **absent, "pending_uploads_checked": False,
            }))
        self.assertEqual(self.queue.reconcile(instagram["token"], self.write("absent.json", absent)), "ready")
        result = self.queue.history()[-1]
        self.assertEqual(result["reconciliation_reason"], "Lease expired")
        self.assertEqual(result["result"]["outcome"], "absent")

        replacement = self.queue.stage(self.manifest(cut="revised-copy", supersedes="first"))
        self.approve(replacement)
        new = self.queue.claim("replacement")
        self.assertEqual((new["cut"], new["platform"]), ("revised-copy", "instagram"))
        self.queue.begin(new["token"])
        self.queue.release(new["token"], "Lost upload result")
        restored = self.receipt(
            new, "https://instagram.com/reels/xyz/", prior_worker_stopped=True,
        )
        self.assertEqual(self.queue.reconcile(new["token"], restored), "verified")
        self.assertIsNone(self.queue.claim("anything-left"))

    def test_same_external_post_cannot_verify_two_deliveries(self):
        for cut, media in (("first", 0), ("second", 1)):
            self.approve(self.queue.stage(self.manifest(cut=cut, scene=cut, media=media)))
        first = self.queue.claim("worker")
        self.queue.begin(first["token"])
        youtube = "https://www.youtube.com/shorts/abcdefghijk?si=one"
        self.queue.finish(first["token"], self.receipt(first, youtube))
        instagram = self.queue.claim("worker")
        self.queue.begin(instagram["token"])
        self.queue.finish(instagram["token"], self.receipt(instagram, "https://instagram.com/reel/one"))
        second = self.queue.claim("worker")
        self.queue.begin(second["token"])
        with self.assertRaises(sqlite3.IntegrityError):
            proof = self.receipt(second, "https://youtube.com/shorts/abcdefghijk/?si=two")
            self.queue.finish(second["token"], proof)

    def test_changed_snapshot_does_not_block_next_scene(self):
        first = self.queue.stage(self.manifest())
        self.approve(first)
        with self.assertRaisesRegex(ValueError, "different scene"):
            self.queue.stage(self.manifest(cut="same-media", scene="another"))
        self.approve(self.queue.stage(self.manifest(cut="later", scene="later", media=1)))
        claim = self.queue.claim("worker")
        path = Path(claim["artifact"])
        path.chmod(0o600)
        path.write_bytes(b"changed")
        self.assertEqual(self.queue.begin(claim["token"])["state"], "invalid")
        self.assertEqual(self.queue.claim("other")["cut"], "later")
