#!/usr/bin/env python3
"""Hand an independently reviewed export to one browser publisher at a time."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sqlite3
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit
from uuid import uuid4

from review_media import MIN_SIGNAL_PEAK_DBFS, artifact_digest


PLATFORMS = ("youtube", "instagram")
QUEUE_PATH = Path(".improvement/studio/queue.sqlite3")
LEASE_SECONDS = 600
PUBLIC_TIMESTAMP_TOLERANCE = 120
SCHEMA = """
CREATE TABLE IF NOT EXISTS cuts (
    id TEXT PRIMARY KEY,
    scene TEXT NOT NULL,
    package TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    artifact TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    reviewer TEXT,
    review_evidence TEXT,
    replaced_by TEXT REFERENCES cuts(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_current_revision ON cuts(scene) WHERE replaced_by IS NULL;
CREATE TABLE IF NOT EXISTS deliveries (
    cut_id TEXT NOT NULL REFERENCES cuts(id),
    platform TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN (
        'ready', 'claimed', 'submitting', 'reconcile', 'verified', 'invalid', 'superseded'
    )),
    attempt_id TEXT REFERENCES attempts(id),
    external_id TEXT,
    receipt TEXT,
    PRIMARY KEY(cut_id, platform),
    UNIQUE(platform, external_id)
);
CREATE TABLE IF NOT EXISTS attempts (
    id TEXT PRIMARY KEY,
    cut_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    worker TEXT NOT NULL,
    claimed_at REAL NOT NULL,
    expires REAL NOT NULL,
    began_at REAL,
    ended_at REAL,
    result TEXT,
    reconciliation_reason TEXT,
    remote_post_id TEXT,
    FOREIGN KEY(cut_id, platform) REFERENCES deliveries(cut_id, platform)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_browser_writer
    ON deliveries((1)) WHERE state IN ('claimed', 'submitting', 'reconcile');
"""


def read_json(path):
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def serialize(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def require_text(mapping, key):
    value = mapping[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be nonempty text")
    return value.strip()


def slug(mapping, key):
    value = require_text(mapping, key)
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError(f"{key} must be a lowercase slug")
    return value


def package_data(path):
    raw = read_json(path)
    source = raw["source"]
    start, end = source["start"], source["end"]
    if not all(type(x) in (int, float) and math.isfinite(x) for x in (start, end)) or not 0 <= start < end:
        raise ValueError("Source requires finite seconds with 0 <= start < end")
    clock = require_text(source, "clock")
    if clock not in {"vod-offset", "unix", "recording-offset"}:
        raise ValueError("Use vod-offset, unix, or recording-offset")
    targets = raw["destinations"]
    if not isinstance(targets, dict) or not targets or set(targets) - set(PLATFORMS):
        raise ValueError("Provide at least one supported destination: YouTube or Instagram")

    destinations = {}
    for platform, destination in targets.items():
        if destination.get("reuse_cleared") is not True:
            raise ValueError(f"Confirm and record reuse scope for {platform}")
        keys = ["account", "caption", "rights_evidence"]
        if platform == "youtube":
            keys.append("title")
        destinations[platform] = {key: require_text(destination, key) for key in keys}

    report = (path.parent / require_text(raw, "media_review")).resolve(strict=True)
    report_bytes = report.read_bytes()
    review = json.loads(report_bytes)
    artifact = (path.parent / require_text(raw, "artifact")).resolve(strict=True)
    if artifact.suffix.lower() != ".mp4" or not artifact.is_file():
        raise ValueError("Artifact must be a local MP4")
    digest = artifact_digest(artifact)
    if (
        review.get("schema_version") != 1 or review.get("full_decode_passed") is not True
        or review.get("artifact_sha256") != digest or not review.get("frames")
        or not isinstance(review.get("audio_present"), bool)
    ):
        raise ValueError("Artifact must match a passing review_media.py report")
    names = [review["contact_sheet"], *(row["file"] for row in review["frames"]), *review["audio_evidence"]]
    if len(set(names)) != len(names) or any(
        not re.fullmatch(r"[a-z0-9_-]+\.(png|txt)", name) or not (report.parent / name).is_file()
        for name in names
    ):
        raise ValueError("Media review must include its contact sheet, frames, and listed diagnostics")
    evidence = {"review.json": report_bytes}
    evidence.update({name: (report.parent / name).read_bytes() for name in names})

    package = {
        "id": slug(raw, "id"),
        "scene": slug(raw, "scene"),
        "supersedes": slug(raw, "supersedes") if raw.get("supersedes") else None,
        "editor": require_text(raw, "editor"),
        "source": {
            **{key: require_text(source, key) for key in ("id", "creator", "reference", "credit")},
            "clock": clock, "start": start, "end": end,
        },
        "editorial_choice": require_text(raw, "editorial_choice"),
        "experiment": require_text(raw, "experiment"),
        "audio_present": review["audio_present"],
        "artifact_sha256": digest,
        "media_review_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "destinations": destinations,
    }
    package["media_review_files"] = {name: hashlib.sha256(body).hexdigest() for name, body in evidence.items()}
    if "sound" in raw:
        sound = raw["sound"]
        package["sound"] = {key: require_text(sound, key) for key in ("mode", "reason")}
        if package["sound"]["mode"] != "silent":
            package["sound"]["rights_evidence"] = require_text(sound, "rights_evidence")
    if "edit" in raw:
        edit = raw["edit"]
        package["edit"] = {key: edit[key] for key in (
            "duration_seconds", "hook_seconds", "payoff_seconds", "source_spans",
        )}
        if "campaign_url" in raw:
            package["campaign_url"] = require_text(raw, "campaign_url")
    return package, artifact, evidence


def finite_seconds(value):
    return type(value) in (float, int) and math.isfinite(value) and value >= 0


def check_edit(package, report):
    edit = package.get("edit")
    if not edit:
        raise ValueError("Declare the edit duration, hook, payoff, and source spans")
    duration, hook, payoff = (edit[key] for key in ("duration_seconds", "hook_seconds", "payoff_seconds"))
    if not all(map(finite_seconds, (duration, hook, payoff))) or not hook <= payoff < duration:
        raise ValueError("Hook and payoff must be ordered timestamps within the edit")
    if not finite_seconds(report.get("video_seconds")) or abs(duration - report["video_seconds"]) > 0.05:
        raise ValueError("Rendered duration differs from the edit plan")
    source = package["source"]
    spans = edit["source_spans"]
    if not isinstance(spans, list) or not spans or any(
        not isinstance(span, list) or len(span) != 2 or not all(map(finite_seconds, span))
        or not source["start"] <= span[0] < span[1] <= source["end"] for span in spans
    ):
        raise ValueError("Each source span must be within the declared source bounds")
    marks = [row["requested_seconds"] for row in report["frames"]]
    if not all(any(finite_seconds(mark) and abs(mark - beat) < 0.001 for mark in marks)
               for beat in (hook, payoff)):
        raise ValueError("Media report must sample both declared hook and payoff")


def check_sound(package, report):
    sound = package.get("sound")
    if not sound or sound["mode"] not in {"source", "original", "silent"}:
        raise ValueError("Declare sound mode as source, original, or intentionally silent")
    if sound["mode"] == "silent":
        if package["audio_present"]:
            raise ValueError("An intentionally silent export must omit the audio track")
        return
    peak = report.get("audio_peak_dbfs")
    if not package["audio_present"] or type(peak) not in (float, int) or not (
        math.isfinite(peak) and MIN_SIGNAL_PEAK_DBFS < peak <= 0
    ):
        raise ValueError("Regenerate the review report and verify non-silent audio in the final export")
    tracks = {track["codec_type"]: track for track in report["probe"]["streams"]}
    video_start, video_end = stream_bounds(tracks["video"])
    audio_start, audio_end = stream_bounds(tracks["audio"])
    if abs(video_start - audio_start) > 0.25 or abs(video_end - audio_end) > 0.25:
        raise ValueError("Audio track must cover the picture from start to finish")
    signal = report.get("audio_signal_seconds")
    if not finite_seconds(signal) or signal < min(0.5, (video_end - video_start) / 2):
        raise ValueError("Audible export needs more than a brief spike in an otherwise silent track")


def stream_bounds(track):
    start = float(track["start_time"])
    duration = float(track["duration"])
    if not math.isfinite(start) or not finite_seconds(duration) or duration == 0:
        raise ValueError("Audio and video need measurable stream timing")
    return start, start + duration



def permalink(platform, value):
    url = urlsplit(value)
    hosts, path, pattern = {
        "youtube": ({"youtube.com", "www.youtube.com"}, "shorts", r"/shorts/([A-Za-z0-9_-]{11})/?"),
        "instagram": ({"instagram.com", "www.instagram.com"}, "reel", r"/reels?/([A-Za-z0-9_-]+)/?"),
    }[platform]
    match = re.fullmatch(pattern, url.path)
    if url.scheme != "https" or url.netloc not in hosts or not match:
        raise ValueError(f"Expected a public {platform} permalink")
    post_id = match[1]
    host = "www.youtube.com" if platform == "youtube" else "www.instagram.com"
    return post_id, f"https://{host}/{path}/{post_id}"


class Queue:
    def __init__(self, connection, spool, clock=time.time):
        self.db = connection
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        with self.transaction():
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                if self.db.execute("SELECT 1 FROM sqlite_master WHERE name = 'cuts'").fetchone():
                    raise ValueError("This is a pre-release queue. Preserve it and choose a fresh database.")
                for statement in SCHEMA.strip().rstrip(";").split(";"):
                    self.db.execute(statement)
                self.db.execute("PRAGMA user_version = 1")
            elif version != 1:
                raise ValueError(f"Unsupported queue version {version}")
        self.spool = spool.resolve()
        self.clock = clock

    @contextmanager
    def transaction(self):
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            yield

    def snapshot(self, source, digest, evidence, fingerprint):
        directory = self.spool / digest
        directory.mkdir(parents=True, exist_ok=True)
        artifact = directory / "export.mp4"
        if not artifact.exists():
            with TemporaryDirectory(dir=directory) as temporary:
                copied = Path(temporary) / "export.mp4"
                shutil.copyfile(source, copied)
                if artifact_digest(copied) != digest:
                    raise ValueError("Export changed while staging")
                copied.chmod(0o444)
                copied.replace(artifact)
        if artifact_digest(artifact) != digest:
            raise ValueError("Spool artifact is damaged")
        bundle = directory / fingerprint
        if not bundle.exists():
            with TemporaryDirectory(dir=directory) as temporary:
                temporary_bundle = Path(temporary) / "review"
                temporary_bundle.mkdir()
                for name, body in evidence.items():
                    (temporary_bundle / name).write_bytes(body)
                temporary_bundle.rename(bundle)
        return artifact

    def stage(self, manifest):
        package, source, evidence = package_data(manifest)
        serialized = serialize(package)
        fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
        cut, scene, supersedes = (package[key] for key in ("id", "scene", "supersedes"))
        digest = package["artifact_sha256"]
        with self.transaction():
            previous = self.db.execute("SELECT fingerprint FROM cuts WHERE id = ?", (cut,)).fetchone()
            if previous:
                if previous["fingerprint"] != fingerprint:
                    raise ValueError("Cut ID already names a different package. Use a new revision ID.")
                return {"cut": cut, "package_sha256": fingerprint}
            report = json.loads(evidence["review.json"])
            check_sound(package, report)
            check_edit(package, report)
            if self.db.execute(
                "SELECT 1 FROM cuts WHERE artifact_sha256 = ? AND scene != ?", (digest, scene),
            ).fetchone():
                raise ValueError("These exact media bytes already belong to a different scene")
            current = self.db.execute(
                "SELECT id FROM cuts WHERE scene = ? AND replaced_by IS NULL", (scene,),
            ).fetchone()
            if supersedes != (current["id"] if current else None):
                raise ValueError("Name the current cut of this scene in supersedes")
            if current and self.db.execute(
                "SELECT 1 FROM deliveries WHERE cut_id = ? AND state IN ('claimed','submitting','reconcile')",
                (supersedes,),
            ).fetchone():
                raise ValueError("Resolve the active attempt before staging a replacement")
            artifact = self.snapshot(source, digest, evidence, fingerprint)
            if supersedes:
                # The outgoing revision can point to the new one until transaction commit.
                self.db.execute("PRAGMA defer_foreign_keys = ON")
                self.db.execute("UPDATE cuts SET replaced_by = ? WHERE id = ?", (cut, supersedes))
                self.db.execute(
                    "UPDATE deliveries SET state = 'superseded' WHERE cut_id = ? AND state != 'verified'",
                    (supersedes,),
                )
            self.db.execute(
                "INSERT INTO cuts(id,scene,package,fingerprint,artifact,artifact_sha256) VALUES (?,?,?,?,?,?)",
                (cut, scene, serialized, fingerprint, str(artifact), digest),
            )
            already_public = self.db.execute(
                """SELECT platform FROM deliveries JOIN cuts ON cuts.id = deliveries.cut_id
                   WHERE cuts.scene = ? AND deliveries.state = 'verified'""", (scene,),
            )
            shipped = {row["platform"] for row in already_public}
            self.db.executemany(
                "INSERT INTO deliveries(cut_id,platform,state) VALUES (?,?,'ready')",
                [(cut, platform) for platform in package["destinations"] if platform not in shipped],
            )
        return {"cut": cut, "package_sha256": fingerprint}

    def inspect(self, cut_id):
        row = self.db.execute("SELECT * FROM cuts WHERE id = ?", (cut_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown cut ID")
        result = dict(row)
        result["package"] = json.loads(result["package"])
        result["media_review"] = str(Path(row["artifact"]).parent / row["fingerprint"] / "review.json")
        return result

    @staticmethod
    def intact(row):
        artifact = Path(row["artifact"])
        try:
            return artifact_digest(artifact) == row["artifact_sha256"]
        except OSError:
            return False

    def review(self, cut_id, decision):
        review = read_json(decision)
        reviewer = require_text(review, "reviewer")
        evidence = require_text(review, "evidence")
        with self.transaction():
            cut = self.inspect(cut_id)
            if (
                cut["replaced_by"] or review.get("package_sha256") != cut["fingerprint"]
                or review.get("verdict") != "approve"
            ):
                raise ValueError("Approve the current exact package fingerprint")
            if reviewer.casefold() == cut["package"]["editor"].casefold():
                raise ValueError("An independent reviewer must approve the package")
            if not self.intact(cut):
                raise ValueError("Spool artifact is missing or changed")
            bundle = Path(cut["media_review"]).parent
            if not all(
                (bundle / name).is_file() and artifact_digest(bundle / name) == digest
                for name, digest in cut["package"]["media_review_files"].items()
            ):
                raise ValueError("Review evidence changed after staging")
            if "edit" in cut["package"]:
                if not isinstance(review.get("checks"), dict):
                    raise ValueError("Record independent review evidence in checks")
                checks = {key: require_text(review["checks"], key) for key in (
                    "source_and_rights", "hook_and_payoff", "sound_and_sync",
                )}
                evidence = serialize({"summary": evidence, "checks": checks})
            if cut["reviewer"]:
                if (reviewer, evidence) != (cut["reviewer"], cut["review_evidence"]):
                    raise ValueError("This package already has a different approval")
            else:
                self.db.execute(
                    "UPDATE cuts SET reviewer = ?, review_evidence = ? WHERE id = ?",
                    (reviewer, evidence, cut_id),
                )
        return cut_id

    def expire(self, now):
        for row in self.db.execute(
            """SELECT state, attempt_id FROM deliveries JOIN attempts ON attempts.id = deliveries.attempt_id
               WHERE state IN ('claimed','submitting') AND attempts.expires <= ?""", (now,),
        ).fetchall():
            target = "ready" if row["state"] == "claimed" else "reconcile"
            self.transition(row["attempt_id"], target, now, {"evidence": "Lease expired"})

    def transition(self, token, state, now, result, post_id=None):
        self.db.execute(
            """UPDATE deliveries SET state = ?, external_id = ?, receipt = ?,
               attempt_id = CASE WHEN ? = 'reconcile' THEN attempt_id ELSE NULL END WHERE attempt_id = ?""",
            (state, post_id, serialize(result) if post_id else None, state, token),
        )
        self.db.execute(
            """UPDATE attempts SET ended_at = ?, result = ?,
               reconciliation_reason = COALESCE(reconciliation_reason, ?) WHERE id = ?""",
            (now, serialize({"state": state, **result}), result.get("evidence") if state == "reconcile" else None, token),
        )

    def claim(self, worker):
        worker = require_text({"worker": worker}, "worker")
        with self.transaction():
            now = self.clock()
            self.expire(now)
            if self.db.execute(
                "SELECT 1 FROM deliveries WHERE state IN ('claimed','submitting','reconcile')",
            ).fetchone():
                return None
            candidates = self.db.execute(
                """SELECT cuts.*, deliveries.platform FROM deliveries JOIN cuts ON cuts.id = deliveries.cut_id
                   WHERE deliveries.state = 'ready' AND cuts.reviewer IS NOT NULL
                   ORDER BY cuts.rowid, deliveries.platform DESC""",
            ).fetchall()
            for row in candidates:
                cut_id, platform = row["id"], row["platform"]
                if not self.intact(row):
                    self.db.execute(
                        "UPDATE deliveries SET state = 'invalid' WHERE cut_id = ? AND state = 'ready'", (cut_id,),
                    )
                    continue
                token, expires = uuid4().hex, now + LEASE_SECONDS
                self.db.execute(
                    "INSERT INTO attempts(id,cut_id,platform,worker,claimed_at,expires) VALUES (?,?,?,?,?,?)",
                    (token, cut_id, platform, worker, now, expires),
                )
                self.db.execute(
                    "UPDATE deliveries SET state = 'claimed', attempt_id = ? WHERE cut_id = ? AND platform = ?",
                    (token, cut_id, platform),
                )
                package = json.loads(row["package"])
                return {
                    "cut": cut_id, "platform": platform, "token": token, "expires": expires,
                    "artifact": row["artifact"], "artifact_sha256": row["artifact_sha256"],
                    "package_sha256": row["fingerprint"], "source": package["source"],
                    "destination": package["destinations"][platform],
                }
        return None

    def attempt(self, token):
        row = self.db.execute(
            """SELECT attempts.*, deliveries.state, deliveries.attempt_id, cuts.package, cuts.artifact,
                      cuts.artifact_sha256, cuts.fingerprint, cuts.reviewer, cuts.replaced_by FROM attempts
               JOIN deliveries USING(cut_id,platform) JOIN cuts ON cuts.id = attempts.cut_id
               WHERE attempts.id = ?""", (token,),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown attempt")
        return row

    def begin(self, token, preflight=None):
        return self.extend(token, begin=True, preflight=preflight)

    def check_upload(self, row, package, preflight, now):
        if preflight is None:
            raise ValueError("Provide an upload preflight for this cut")
        proof = read_json(preflight)
        platform = row["platform"]
        if (proof.get("platform") != platform
            or proof.get("account") != package["destinations"][platform]["account"]):
            raise ValueError("Upload preflight does not match the selected account and platform")
        if proof.get("package_sha256") != row["fingerprint"]:
            raise ValueError("Upload preflight must identify the approved package")
        upload = (preflight.parent / require_text(proof, "upload_file")).resolve()
        if artifact_digest(upload) != row["artifact_sha256"]:
            raise ValueError("Selected upload file differs from the approved artifact")
        if "campaign_url" in package:
            from studio_campaigns import prepare
            if "campaign_brief" not in proof:
                raise ValueError("Upload preflight requires a campaign_brief")
            brief = read_json(preflight.parent / require_text(proof, "campaign_brief"))
            receipts = {
                target: json.loads(receipt)
                for target, receipt in self.db.execute(
                    "SELECT platform, receipt FROM deliveries WHERE cut_id = ? AND state = 'verified'",
                    (row["cut_id"],),
                )
            }
            cut = (package, row["reviewer"], row["fingerprint"], row["replaced_by"], receipts)
            prepare(
                brief, row["cut_id"], cut, datetime.fromtimestamp(now, timezone.utc),
                phase="preflight", platform=platform,
            )

    def renew(self, token):
        return self.extend(token, begin=False)

    def extend(self, token, *, begin, preflight=None):
        with self.transaction():
            now = self.clock()
            row = self.attempt(token)
            state = row["state"]
            if row["attempt_id"] != token or row["expires"] <= now or state not in {"claimed", "submitting"}:
                raise ValueError("A current publisher lease is required")
            if not self.intact(row):
                target = "invalid" if state == "claimed" else "reconcile"
                self.transition(token, target, now, {"evidence": "Spool artifact changed or is missing"})
                if target == "invalid":
                    self.db.execute(
                        "UPDATE deliveries SET state = 'invalid' WHERE cut_id = ? AND state = 'ready'",
                        (row["cut_id"],),
                    )
                return {"state": target}
            package = json.loads(row["package"])
            if begin and "edit" in package:
                self.check_upload(row, package, preflight, now)
            expires = now + LEASE_SECONDS
            if begin:
                self.db.execute("UPDATE deliveries SET state = 'submitting' WHERE attempt_id = ?", (token,))
            self.db.execute(
                "UPDATE attempts SET expires = ?, began_at = COALESCE(began_at, ?) WHERE id = ?",
                (expires, now if begin else None, token),
            )
            return {"state": "submitting" if begin else state, "expires": expires}

    def release(self, token, evidence):
        evidence = require_text({"evidence": evidence}, "evidence")
        with self.transaction():
            now = self.clock()
            self.expire(now)
            row = self.attempt(token)
            if row["attempt_id"] != token or row["state"] not in {"claimed", "submitting"}:
                raise ValueError("A current publisher lease is required")
            state = "ready" if row["state"] == "claimed" else "reconcile"
            self.transition(token, state, now, {"evidence": evidence})
        return state

    def remember(self, token, public_url):
        with self.transaction():
            now = self.clock()
            row = self.attempt(token)
            if row["attempt_id"] != token or row["state"] != "submitting" or row["expires"] <= now:
                raise ValueError("A current submitting lease is required")
            post_id, _ = permalink(row["platform"], public_url)
            if row["remote_post_id"] not in (None, post_id):
                raise ValueError("Attempt already has a different platform post ID")
            if self.db.execute(
                "SELECT 1 FROM deliveries WHERE platform = ? AND external_id = ?", (row["platform"], post_id),
            ).fetchone():
                raise ValueError("That platform post already has a delivery receipt")
            self.db.execute("UPDATE attempts SET remote_post_id = ? WHERE id = ?", (post_id, token))
            return post_id

    def record(self, token, receipt, *, recovery=False):
        proof = read_json(receipt)
        with self.transaction():
            now = self.clock()
            self.expire(now)
            row = self.attempt(token)
            platform = row["platform"]
            package = json.loads(row["package"])
            target = package["destinations"][platform]
            evidence = require_text(proof, "evidence")
            if require_text(proof, "account") != target["account"]:
                raise ValueError("Readback account differs from the reviewed destination")
            if recovery and proof.get("prior_worker_stopped") is not True:
                raise ValueError("Confirm the earlier publisher has stopped before resolving the attempt")
            result = {"account": target["account"], "evidence": evidence}
            post_id = None
            if recovery and proof.get("outcome") == "absent":
                if proof.get("pending_uploads_checked") is not True or proof.get("public_posts_checked") is not True:
                    raise ValueError("Check both drafts/pending uploads and public posts before retry")
                next_state = "ready"
            else:
                for key in ("caption", "title"):
                    if key in target and require_text(proof, key) != target[key]:
                        raise ValueError(f"Readback {key} differs from reviewed copy")
                if proof.get("visibility") != "public" or proof.get("artifact_sha256") != row["artifact_sha256"]:
                    raise ValueError("Confirm public visibility and the uploaded local artifact hash")
                if "edit" in package:
                    playback = proof.get("playback", {})
                    played_duration = playback.get("duration_seconds")
                    if (playback.get("played") is not True or playback.get("hook_and_payoff_seen") is not True
                        or not finite_seconds(played_duration)
                        or abs(played_duration - package["edit"]["duration_seconds"]) > 1):
                        raise ValueError("Public playback must show the reviewed hook, payoff and duration")
                    if playback.get("sound_heard") is not package["audio_present"]:
                        raise ValueError("Public playback sound must match the approved cut")
                    result["playback"] = {key: playback[key] for key in (
                        "played", "hook_and_payoff_seen", "duration_seconds", "sound_heard",
                    )}
                post_id, url = permalink(platform, require_text(proof, "public_url"))
                if row["remote_post_id"] not in (None, post_id):
                    raise ValueError("Receipt differs from the post ID recorded during upload")
                published = datetime.fromisoformat(require_text(proof, "public_at").replace("Z", "+00:00"))
                if published.utcoffset() is None:
                    raise ValueError("public_at requires an ISO timestamp with time zone")
                if row["began_at"] is None or not (
                    row["began_at"] - PUBLIC_TIMESTAMP_TOLERANCE <= published.timestamp()
                    <= now + PUBLIC_TIMESTAMP_TOLERANCE
                ):
                    raise ValueError("Publication timestamp does not match this attempt")
                result.update(
                    public_url=url, public_at=published.isoformat(), visibility="public",
                    artifact_sha256=row["artifact_sha256"], caption=target["caption"],
                )
                if "title" in target:
                    result["title"] = target["title"]
                next_state = "verified"
            if recovery:
                result["prior_worker_stopped"] = True
                if next_state == "ready":
                    result.update(outcome="absent", pending_uploads_checked=True, public_posts_checked=True)
            if row["result"] == serialize({"state": next_state, **result}):
                return next_state
            if row["attempt_id"] != token or row["state"] != ("reconcile" if recovery else "submitting"):
                raise ValueError("Attempt is inactive or requires reconciliation")
            self.transition(token, next_state, now, result, post_id)
        return next_state

    def finish(self, token, receipt):
        return self.record(token, receipt)

    def reconcile(self, token, receipt):
        return self.record(token, receipt, recovery=True)

    def milestones(self):
        schedule = []
        for delivery in self.status():
            receipt = delivery["receipt"]
            if delivery["state"] != "verified" or not receipt:
                continue
            published_at = datetime.fromisoformat(receipt["public_at"])
            for age in (24, 72, 168):
                schedule.append({
                    "cut": delivery["cut_id"], "platform": delivery["platform"],
                    "public_url": receipt["public_url"], "age_hours": age,
                    "due_at": (published_at + timedelta(hours=age)).isoformat(),
                })
        return sorted(schedule, key=lambda sample: datetime.fromisoformat(sample["due_at"]))

    def history(self):
        records = [dict(row) for row in self.db.execute("SELECT * FROM attempts ORDER BY rowid")]
        for record in records:
            if record["result"]:
                record["result"] = json.loads(record["result"])
        return records

    def status(self):
        with self.transaction():
            self.expire(self.clock())
            rows = self.db.execute(
                """SELECT deliveries.cut_id, deliveries.platform, deliveries.state, cuts.reviewer, deliveries.receipt,
                          attempts.id AS token, attempts.worker, attempts.expires, attempts.remote_post_id, attempts.result
                   FROM deliveries JOIN cuts ON cuts.id = deliveries.cut_id
                   LEFT JOIN attempts ON attempts.id = deliveries.attempt_id
                   ORDER BY cuts.rowid, deliveries.platform DESC""",
            )
            result = [dict(row) for row in rows]
        for row in result:
            for key in ("receipt", "result"):
                if row[key]:
                    row[key] = json.loads(row[key])
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("stage").add_argument("manifest", type=Path)
    commands.add_parser("inspect").add_argument("cut_id")
    review = commands.add_parser("review")
    review.add_argument("cut_id")
    review.add_argument("decision", type=Path)
    commands.add_parser("claim").add_argument("--worker", required=True)
    for name in ("begin", "renew", "remember", "release", "finish", "reconcile"):
        command = commands.add_parser(name)
        command.add_argument("token")
        if name == "begin":
            command.add_argument("--preflight", type=Path)
        elif name == "release":
            command.add_argument("--evidence", required=True)
        elif name == "remember":
            command.add_argument("public_url")
        elif name in {"finish", "reconcile"}:
            command.add_argument("receipt", type=Path)
    commands.add_parser("status")
    commands.add_parser("history")
    commands.add_parser("milestones")
    args = vars(parser.parse_args())
    database = args.pop("queue").resolve()
    command = args.pop("command")
    try:
        database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(database, timeout=15) as connection:
            queue = Queue(connection, database.with_suffix(database.suffix + ".media"))
            result = getattr(queue, command)(**args)
    except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError, OverflowError) as error:
        parser.exit(2, f"studio queue: {error}\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
