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
from studio_campaigns import CHECKS
from studio_queue import LEASE_SECONDS, SCHEMA, Queue


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
            cls.media.append((video, review_export(video, root / color, (0, 0.5))))

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
            "edit": {"duration_seconds": 1, "hook_seconds": 0, "payoff_seconds": 0.5,
                     "source_spans": [[18, 19]]},
            "editorial_choice": "Open on the red frame", "experiment": "Test the opening",
            "sound": {"mode": "silent", "reason": "Generated fixture contains picture only"},
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
            "checks": {"source_and_rights": "Matched synthetic source",
                       "hook_and_payoff": "Checked frames at 0 and 0.5",
                       "sound_and_sync": "Confirmed trackless fixture"},
        }))

    def preflight(self, claim, **overrides):
        return self.write("preflight.json", {
            "platform": claim["platform"], "account": claim["destination"]["account"],
            "upload_file": claim["artifact"], "package_sha256": claim["package_sha256"], **overrides,
        })

    def begin(self, claim):
        return self.queue.begin(claim["token"], self.preflight(claim))

    def receipt(self, claim, url, **overrides):
        copy = claim["destination"]
        data = {
            "account": copy["account"], "caption": copy["caption"], "visibility": "public",
            "artifact_sha256": claim["artifact_sha256"], "evidence": "Reopened the public post",
            "playback": {"played": True, "hook_and_payoff_seen": True,
                         "duration_seconds": 1, "sound_heard": False},
            "public_url": url, "public_at": datetime.fromtimestamp(self.now, timezone.utc).isoformat(),
        }
        if "title" in copy:
            data["title"] = copy["title"]
        return self.write("receipt.json", {**data, **overrides})

    def test_one_platform_campaign_does_not_create_another_delivery(self):
        manifest = self.manifest()
        package = json.loads(manifest.read_text())
        instagram = package["destinations"].pop("instagram")
        package["destinations"]["other"] = instagram
        manifest.write_text(json.dumps(package))
        with self.assertRaisesRegex(ValueError, "supported destination"):
            self.queue.stage(manifest)
        package["destinations"].pop("other")
        manifest.write_text(json.dumps(package))
        self.approve(self.queue.stage(manifest))
        self.assertEqual([row["platform"] for row in self.queue.status()], ["youtube"])
        self.assertEqual(self.queue.claim("publisher")["platform"], "youtube")

    def test_audio_is_required_unless_the_export_is_intentionally_silent(self):
        manifest = self.manifest()
        package = json.loads(manifest.read_text())
        package.pop("sound")
        manifest.write_text(json.dumps(package))
        with self.assertRaisesRegex(ValueError, "Declare sound mode"):
            self.queue.stage(manifest)
        package["sound"] = {"mode": "source", "reason": "Preserve reaction", "rights_evidence": "Cleared"}
        manifest.write_text(json.dumps(package))
        with self.assertRaisesRegex(ValueError, "non-silent audio"):
            self.queue.stage(manifest)
        for track, peak_required in (("anullsrc", False), ("sine=frequency=440", True)):
            audio_file = self.root / ("tone.mp4" if peak_required else "blank.mp4")
            subprocess.run([
                "ffmpeg", "-v", "error", "-i", str(self.media[0][0]), "-f", "lavfi", "-i", track,
                "-t", "1", "-c:v", "copy", "-c:a", "aac", str(audio_file),
            ], check=True)
            evidence = review_export(audio_file, audio_file.with_suffix(""), (0, 0.5))
            package.update(artifact=str(audio_file), media_review=str(evidence))
            manifest.write_text(json.dumps(package))
            if peak_required:
                self.assertEqual(self.queue.stage(manifest)["cut"], "first")
            else:
                with self.assertRaisesRegex(ValueError, "non-silent audio"):
                    self.queue.stage(manifest)
        package.update(id="original", supersedes="first", sound={
            "mode": "original", "reason": "Use a generated score", "rights_evidence": "Generated tone",
        })
        manifest.write_text(json.dumps(package))
        with self.assertRaisesRegex(ValueError, "source_audio_omission"):
            self.queue.stage(manifest)
        package["sound"]["source_audio_omission"] = "No broadcast audio in the source fixture"
        manifest.write_text(json.dumps(package))
        self.queue.stage(manifest)
        self.assertEqual(self.queue.inspect("original")["package"]["sound"], package["sound"])
        self.queue.stage(self.manifest(cut="silent", scene="silent"))

    def test_edit_must_match_source_bounds_runtime_and_reviewed_beats(self):
        file = self.manifest()
        manifest = json.loads(file.read_text())
        for edit, reason in (
            ({**manifest["edit"], "source_spans": [[17, 19]]}, "source bounds"),
            ({**manifest["edit"], "duration_seconds": 1.1}, "duration differs"),
            ({**manifest["edit"], "payoff_seconds": 0.75}, "sample both"),
        ):
            with self.subTest(edit=edit), self.assertRaisesRegex(ValueError, reason):
                self.queue.stage(self.write("wrong-edit.json", {**manifest, "edit": edit}))
        staged = self.queue.stage(file)
        with self.assertRaisesRegex(ValueError, "independent review evidence"):
            self.queue.review(staged["cut"], self.write("incomplete.json", {
                "reviewer": "different", "evidence": "summary", "verdict": "approve",
                "package_sha256": staged["package_sha256"],
            }))
        self.assertIsNone(self.queue.claim("publisher"))

    def test_loud_but_short_track_cannot_enter_queue(self):
        manifest = json.loads(self.manifest().read_text())
        audio_file = self.root / "short-sound.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(self.media[0][0]), "-f", "lavfi",
            "-i", "sine=frequency=440:duration=0.2", "-c:v", "copy", "-c:a", "aac", str(audio_file),
        ], check=True)
        evidence = review_export(audio_file, self.root / "short-sound-review", (0, 0.5))
        manifest.update(artifact=str(audio_file), media_review=str(evidence), sound={
            "mode": "original", "reason": "Test truncated sound", "rights_evidence": "Generated tone",
            "source_audio_omission": "No broadcast audio in the source fixture",
        })
        with self.assertRaisesRegex(ValueError, "cover the picture"):
            self.queue.stage(self.write("short-sound.json", manifest))

        padded = self.root / "padded-sound.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(audio_file), "-af", "apad=whole_dur=1",
            "-c:v", "copy", "-c:a", "aac", str(padded),
        ], check=True)
        evidence = review_export(padded, self.root / "padded-sound-review", (0, 0.5))
        manifest.update(artifact=str(padded), media_review=str(evidence))
        with self.assertRaisesRegex(ValueError, "brief spike"):
            self.queue.stage(self.write("padded-sound.json", manifest))

    def test_upload_preflight_and_campaign_are_bound_before_first_mutation(self):
        manifest = json.loads(self.manifest().read_text())
        manifest["destinations"].pop("instagram")
        campaign = "https://contentrewards.com/c/campaigns/example"
        manifest["campaign_url"] = campaign
        staged = self.queue.stage(self.write("campaign-cut.json", manifest))
        self.approve(staged)
        claim = self.queue.claim("browser")
        with self.assertRaisesRegex(ValueError, "selected account"):
            self.queue.begin(claim["token"], self.preflight(claim, account="wrong"))
        with self.assertRaisesRegex(ValueError, "approved package"):
            self.queue.begin(claim["token"], self.preflight(claim, package_sha256="stale"))
        with self.assertRaisesRegex(ValueError, "upload file differs"):
            self.queue.begin(claim["token"], self.preflight(claim, upload_file=str(self.media[1][0])))
        with self.assertRaisesRegex(ValueError, "campaign_brief"):
            self.begin(claim)
        now = datetime.fromtimestamp(self.now, timezone.utc)
        brief = {
            "provider": "content-rewards", "campaign_url": campaign,
            "accounts": {"youtube": claim["destination"]["account"]}, "submission_platforms": ["youtube"],
            "allowed_source_ids": ["vod"], "checks": {key: "Fixture evidence" for key in CHECKS},
            "commissioned_at": (now - timedelta(hours=1)).isoformat(),
            "recheck_at": (now + timedelta(minutes=1)).isoformat(),
            "submission_window_minutes": 30, "preapproval_required": False,
            "package_sha256": staged["package_sha256"],
        }
        preflight = self.preflight(claim, campaign_brief="campaign.json")
        self.write("campaign.json", {**brief, "campaign_url": campaign + "-other"})
        with self.assertRaisesRegex(ValueError, "sealed into the cut"):
            self.queue.begin(claim["token"], preflight)
        self.write("campaign.json", {**brief, "recheck_at": (now - timedelta(minutes=1)).isoformat()})
        with self.assertRaisesRegex(ValueError, "stale"):
            self.queue.begin(claim["token"], preflight)
        self.assertEqual(self.queue.status()[0]["state"], "claimed")
        self.write("campaign.json", brief)
        self.assertEqual(self.queue.begin(claim["token"], preflight)["state"], "submitting")
        self.queue.release(claim["token"], "Processing")
        with self.assertRaisesRegex(ValueError, "Only YouTube showcase"):
            self.queue.defer_processing(claim["token"], self.write("paid-processing.json", {
                "evidence": "Shows processing",
            }))

    def test_twitch_native_delivery_checks_clip_layout_and_rendition(self):
        manifest = json.loads(self.manifest().read_text())
        clip = "https://www.twitch.tv/creator/clip/Original"
        manifest["twitch_native_clip"] = clip
        staged = self.queue.stage(self.write("native.json", manifest))
        self.approve(staged)
        claim = self.queue.claim("browser")
        self.assertEqual(claim["twitch_native_clip"], clip)
        base = {
            "platform": claim["platform"], "account": claim["destination"]["account"],
            "package_sha256": claim["package_sha256"], "twitch_native_clip": clip + "?range=7d",
            "layout": "portrait", "portrait_rendition": claim["artifact"],
        }
        for change, error in (
            ({"twitch_native_clip": clip + "Other"}, "approved clip"),
            ({"layout": "landscape"}, "portrait layout"),
            ({"portrait_rendition": str(self.media[1][0])}, "rendition differs"),
        ):
            proof = self.write("native-preflight.json", {**base, **change})
            with self.assertRaisesRegex(ValueError, error):
                self.queue.begin(claim["token"], proof)
        proof = self.write("native-preflight.json", base)
        self.assertEqual(self.queue.begin(claim["token"], proof)["state"], "submitting")

    def test_handoff_and_native_scene_identity(self):
        clip = "https://www.twitch.tv/creator/clip/Original"
        manifest = json.loads(self.manifest().read_text())
        manifest["twitch_native_clip"] = clip
        staged = self.queue.stage(self.write("native.json", manifest))
        other = json.loads(self.manifest(cut="other", scene="another", media=1).read_text())
        other["twitch_native_clip"] = clip + "/?range=7d"
        with self.assertRaisesRegex(ValueError, "Twitch clip already belongs"):
            self.queue.stage(self.write("native-duplicate.json", other))

        handoff = self.queue.handoff()
        self.assertEqual(handoff["awaiting_review"], [
            {"cut": staged["cut"], "platforms": ["youtube", "instagram"]},
        ])
        self.assertEqual(handoff["ready_to_publish"], [])
        self.approve(staged)
        claim = self.queue.claim("browser")
        handoff = self.queue.handoff()
        self.assertEqual(handoff["active_delivery"]["token"], claim["token"])
        self.assertEqual(handoff["awaiting_review"], [])
        self.assertEqual(handoff["ready_to_publish"], [{"cut": staged["cut"], "platform": "instagram"}])

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
        self.assertEqual(self.begin(youtube)["state"], "submitting")
        yt_url = "https://youtube.com/shorts/abcdefghijk?si=one"
        self.assertEqual(self.queue.remember(youtube["token"], yt_url), "abcdefghijk")
        with self.assertRaisesRegex(ValueError, "post ID"):
            self.queue.finish(youtube["token"], self.receipt(youtube, "https://youtube.com/shorts/abcdefghijl"))
        with self.assertRaisesRegex(ValueError, "timestamp"):
            self.queue.finish(youtube["token"], self.receipt(youtube, yt_url, public_at="2000-01-01T00:00:00Z"))
        with self.assertRaisesRegex(ValueError, "caption"):
            self.queue.finish(youtube["token"], self.receipt(youtube, yt_url, caption="Wrong"))
        with self.assertRaisesRegex(ValueError, "Public playback"):
            self.queue.finish(youtube["token"], self.receipt(youtube, yt_url, playback={}))
        with self.assertRaisesRegex(ValueError, "sound must match"):
            self.queue.finish(youtube["token"], self.receipt(youtube, yt_url, playback={
                "played": True, "hook_and_payoff_seen": True, "duration_seconds": 1, "sound_heard": True,
            }))
        proof = self.receipt(youtube, yt_url)
        self.assertEqual(self.queue.finish(youtube["token"], proof), "verified")
        self.assertEqual(self.queue.finish(youtube["token"], proof), "verified")
        instagram = self.queue.claim("worker")
        self.assertEqual(instagram["platform"], "instagram")
        self.begin(instagram)
        self.now += LEASE_SECONDS + 1
        self.assertIsNone(self.queue.claim("other-worker"))
        states = {row["platform"]: row["state"] for row in self.queue.status()}
        self.assertEqual(states, {"youtube": "verified", "instagram": "reconcile"})
        schedule = self.queue.milestones()
        handoff = self.queue.handoff()
        self.assertEqual(handoff["active_delivery"]["state"], "reconcile")
        self.assertEqual(handoff["analytics_schedule"], schedule)
        self.assertEqual(handoff["verified_posts"][0]["public_url"], "https://www.youtube.com/shorts/abcdefghijk")
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
        self.begin(new)
        self.queue.release(new["token"], "Lost upload result")
        restored = self.receipt(
            new, "https://instagram.com/reels/xyz/", prior_worker_stopped=True,
        )
        self.assertEqual(self.queue.reconcile(new["token"], restored), "verified")
        self.assertIsNone(self.queue.claim("anything-left"))

    def test_known_youtube_processing_can_yield_the_browser_slot(self):
        self.approve(self.queue.stage(self.manifest()))
        youtube = self.queue.claim("publisher")
        self.begin(youtube)
        token = youtube["token"]
        url = "https://www.youtube.com/shorts/abcdefghijk"
        other_url = "https://www.youtube.com/shorts/abcdefghijl"
        proof = {
            "public_url": url, "account": "channel", "processing": True,
            "prior_worker_stopped": True, "evidence": "Exact upload shows processing in Studio",
        }
        self.queue.remember(token, url)
        with self.assertRaisesRegex(ValueError, "already be in reconciliation"):
            self.queue.defer_processing(token, self.write("pending.json", proof))
        self.queue.release(token, "Waiting for Studio processing")
        self.assertIsNone(self.queue.claim("other-publisher"))
        for override, error in (
            ({"public_url": other_url}, "exact post ID"),
            ({"account": "another"}, "reviewed destination"),
            ({"prior_worker_stopped": False}, "has stopped"),
            ({"processing": False}, "processing"),
        ):
            with self.subTest(override=override), self.assertRaisesRegex(ValueError, error):
                self.queue.defer_processing(token, self.write("pending.json", {**proof, **override}))
        self.assertEqual(
            self.queue.defer_processing(token, self.write("pending.json", proof)), "processing_deferred",
        )
        self.assertEqual(self.queue.defer_processing(token, self.write("pending.json", proof)), "processing_deferred")
        handoff = self.queue.handoff()
        self.assertIsNone(handoff["active_delivery"])
        self.assertEqual(handoff["awaiting_processing"][0]["remote_post_id"], "abcdefghijk")
        instagram = self.queue.claim("other-publisher")
        self.assertEqual(instagram["platform"], "instagram")
        self.assertIsNone(self.queue.claim("third-publisher"))
        with self.assertRaisesRegex(ValueError, "active attempt"):
            self.queue.stage(self.manifest(cut="replacement", supersedes="first"))
        self.begin(instagram)
        self.queue.finish(instagram["token"], self.receipt(instagram, "https://www.instagram.com/reel/one"))
        self.approve(self.queue.stage(self.manifest(cut="second", scene="second", media=1)))
        another_youtube = self.queue.claim("other-publisher")
        self.begin(another_youtube)
        with self.assertRaisesRegex(ValueError, "already has a delivery"):
            self.queue.remember(another_youtube["token"], url)
        with self.assertRaises(sqlite3.IntegrityError):
            self.queue.finish(another_youtube["token"], self.receipt(another_youtube, url))
        with self.assertRaisesRegex(ValueError, "recorded post ID"):
            self.queue.reconcile(token, self.write("absent.json", {
                "account": "channel", "outcome": "absent", "prior_worker_stopped": True,
                "evidence": "No longer listed", "pending_uploads_checked": True, "public_posts_checked": True,
            }))
        with self.assertRaisesRegex(ValueError, "post ID"):
            self.queue.reconcile(token, self.receipt(youtube, other_url, prior_worker_stopped=True))
        self.assertEqual(
            self.queue.reconcile(token, self.receipt(youtube, url, prior_worker_stopped=True)), "verified",
        )
        self.assertEqual(self.queue.handoff()["awaiting_processing"], [])
        self.queue.release(another_youtube["token"], "Upload result is unknown")
        with self.assertRaisesRegex(ValueError, "exact post ID"):
            self.queue.defer_processing(another_youtube["token"], self.write("pending.json", proof))
        self.assertIsNone(self.queue.claim("blocked-publisher"))

    def test_migrate_v1_without_deferring_existing_attempts(self):
        old_path = self.root / "legacy.sqlite3"
        legacy = sqlite3.connect(old_path)
        self.addCleanup(legacy.close)
        legacy.executescript(SCHEMA)
        legacy.execute("PRAGMA user_version = 1")
        legacy.execute(
            """INSERT INTO cuts (id, scene, package, fingerprint, artifact, artifact_sha256)
               VALUES ('legacy', 'legacy', '{}', 'hash', 'unused', 'hash')""",
        )
        legacy.execute("INSERT INTO deliveries (cut_id, platform, state) VALUES ('legacy', 'youtube', 'reconcile')")
        legacy.execute(
            """INSERT INTO attempts (id, cut_id, platform, worker, claimed_at, expires, remote_post_id)
               VALUES ('legacy-attempt', 'legacy', 'youtube', 'publisher', 0, 1, 'abcdefghijk')""",
        )
        legacy.execute("UPDATE deliveries SET attempt_id = 'legacy-attempt' WHERE cut_id = 'legacy'")
        legacy.commit()
        migrated = Queue(legacy, self.root / "legacy.media")
        self.assertEqual(legacy.execute("PRAGMA user_version").fetchone()[0], 2)
        self.assertEqual(legacy.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(migrated.handoff()["active_delivery"]["remote_post_id"], "abcdefghijk")
        self.assertEqual(migrated.handoff()["awaiting_processing"], [])
        self.assertIsNone(migrated.claim("next-publisher"))

    def test_same_external_post_cannot_verify_two_deliveries(self):
        for cut, media in (("first", 0), ("second", 1)):
            self.approve(self.queue.stage(self.manifest(cut=cut, scene=cut, media=media)))
        first = self.queue.claim("worker")
        self.begin(first)
        youtube = "https://www.youtube.com/shorts/abcdefghijk?si=one"
        self.queue.finish(first["token"], self.receipt(first, youtube))
        instagram = self.queue.claim("worker")
        self.begin(instagram)
        self.queue.finish(instagram["token"], self.receipt(instagram, "https://instagram.com/reel/one"))
        second = self.queue.claim("worker")
        self.begin(second)
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
