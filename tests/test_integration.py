import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

CLI = Path(__file__).resolve().parents[1] / "clip_finder.py"


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs FFmpeg and ffprobe")
class ClipperIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.root = Path(temp.name)
        cls.video = cls.root / "vod.mp4"
        cls.chat = cls.root / "chat.json"
        subprocess.run([
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=5",
            "-f", "lavfi", "-i", "sine=frequency=440", "-t", "105",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(cls.video),
        ], check=True)
        offsets = [*range(0, 105, 10), *([51] * 30), *([60] * 15), *([100] * 12)]
        cls.chat.write_text(json.dumps({
            "comments": [{"content_offset_seconds": offset} for offset in reversed(offsets)],
        }))

    def clip(self, target, *extras, chat=None):
        return subprocess.run([
            sys.executable, str(CLI), "--video", str(self.video),
            "--chat", str(chat or self.chat), "--out", str(target), *extras,
        ], text=True, capture_output=True)

    def test_preview_and_real_encode_agree_and_keep_audio(self):
        preview, output = self.root / "preview", self.root / "render"
        for target, extras in [(preview, ["--preview"]), (output, [])]:
            result = self.clip(target, *extras)
            self.assertEqual(result.returncode, 0, result.stderr)

        dry_rows = json.loads((preview / "clips.json").read_text())["clips"]
        rows = json.loads((output / "clips.json").read_text())["clips"]
        self.assertEqual(list(preview.glob("*.mp4")), [])
        self.assertEqual(
            [(c["peak_seconds"], c["start_seconds"], c["end_seconds"]) for c in rows],
            [(50, 30, 70), (100, 80, 105)],
        )
        self.assertEqual(dry_rows, [dict(row, file=None) for row in rows])
        for row in rows:
            path = output / row["file"]
            probe = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries",
                "stream=codec_type,width,height:format=duration", "-of", "json", str(path),
            ]))
            video, audio = probe["streams"]
            self.assertEqual((video["width"], video["height"]), (1080, 1920))
            self.assertEqual(audio["codec_type"], "audio")
            self.assertAlmostEqual(float(probe["format"]["duration"]),
                                   row["end_seconds"] - row["start_seconds"], delta=0.25)
            subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                            "-f", "null", "-"], check=True)

    def test_mismatched_chat_fails_before_creating_outputs(self):
        chat = self.root / "mismatch.json"
        chat.write_text('{"comments":[{"content_offset_seconds":106}]}')
        output = self.root / "mismatch"
        result = self.clip(output, "--preview", chat=chat)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matching untrimmed VOD", result.stderr)
        self.assertFalse(output.exists())

    def test_marked_gameplay_exports_with_no_chat(self):
        output = self.root / "marks"
        result = subprocess.run([
            sys.executable, str(CLI), "--video", str(self.video), "--out", str(output),
            "--at", "00:01.5", "--at", "0:01:43", "--before", "3", "--after", "4",
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / "clips.json").read_text())
        self.assertEqual(report["mode"], "timestamp")
        self.assertEqual(
            [(row["peak_seconds"], row["start_seconds"], row["end_seconds"]) for row in report["clips"]],
            [(1.5, 0, 5.5), (103, 100, 105)],
        )
        self.assertEqual(len(list(output.glob("*.mp4"))), 2)

    def test_marked_cuts_stop_at_video_end_when_audio_runs_longer(self):
        video = self.root / "audio-tail.mp4"
        subprocess.run([
            "ffmpeg", "-v", "error", "-itsoffset", "1", "-f", "lavfi",
            "-i", "testsrc2=size=160x90:rate=10:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-c:v", "libx264", "-c:a", "aac", str(video),
        ], check=True)
        command = [
            sys.executable, str(CLI), "--video", str(video),
            "--before", "1", "--after", "2",
        ]
        output = self.root / "near-video-end"
        result = subprocess.run([
            *command, "--preview", "--at", "2.5", "--out", str(output),
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / "clips.json").read_text())
        self.assertEqual(report["clips"][0]["end_seconds"], 3)

        tail_output = self.root / "after-video-end"
        result = subprocess.run([
            *command, "--at", "4", "--out", str(tail_output),
        ], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Timestamp 4s falls outside", result.stderr)
        self.assertFalse(tail_output.exists())

    def test_matching_chat_export_can_exceed_video_end_by_a_few_seconds(self):
        source = json.loads(self.chat.read_text())
        source["video"] = {"length": 105}
        source["comments"].extend([
            {"content_offset_seconds": 105}, {"content_offset_seconds": 110},
        ])
        tail_chat = self.root / "tail.json"
        tail_chat.write_text(json.dumps(source))
        output = self.root / "tail"
        result = self.clip(output, "--preview", chat=tail_chat)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / "clips.json").read_text())
        self.assertEqual(report["skipped_tail_messages"], 2)
        self.assertEqual([row["peak_seconds"] for row in report["clips"]], [50, 100])

        source["comments"].append({"content_offset_seconds": 140})
        tail_chat.write_text(json.dumps(source))
        result = self.clip(self.root / "far-tail", "--preview", chat=tail_chat)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matching untrimmed VOD", result.stderr)

    def test_exclusion_replaces_a_pick_even_if_only_its_lead_in_overlaps(self):
        output = self.root / "exclude"
        result = self.clip(output, "--preview", "--exclude", "00:25-00:40")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / "clips.json").read_text())
        self.assertEqual(report["settings"]["excluded_ranges_seconds"], [[25, 40]])
        self.assertEqual([row["peak_seconds"] for row in report["clips"]], [60, 100])

    def test_trimmed_twitch_chat_maps_original_seconds_to_local_cuts(self):
        source = json.loads(self.chat.read_text())
        source["video"] = {"length": 600, "start": 120, "end": 225}
        for comment in source["comments"]:
            comment["content_offset_seconds"] += 120
        chat = self.root / "excerpt.json"
        chat.write_text(json.dumps(source))
        output = self.root / "excerpt"
        result = self.clip(output, "--preview", "--vod-start", "02:00", chat=chat)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((output / "clips.json").read_text())
        self.assertEqual(report["settings"]["vod_start_seconds"], 120)
        self.assertEqual([row["peak_seconds"] for row in report["clips"]], [50, 100])

        result = self.clip(self.root / "wrong-start", "--preview", "--vod-start", "02:01", chat=chat)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matching video interval", result.stderr)

    def test_empty_ranking_explains_that_the_message_cutoff_was_unreachable(self):
        output = self.root / "quiet"
        result = self.clip(output, "--preview", "--min-messages", "50")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--min-messages 50 (maximum 31)", result.stdout)
        report = json.loads((output / "clips.json").read_text())
        self.assertEqual(report["clips"], [])
        self.assertEqual(report["chat_activity"]["maximum_messages_in_rankable_bucket"], 31)
