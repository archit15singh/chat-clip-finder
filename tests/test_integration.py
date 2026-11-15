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
