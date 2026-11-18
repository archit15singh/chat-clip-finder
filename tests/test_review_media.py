import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from review_media import artifact_digest, review_export


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "needs FFmpeg and ffprobe")
class MediaReviewTest(unittest.TestCase):
    def fixture(self, path, color="red", audio=False, size="90x160"):
        command = [
            "ffmpeg", "-v", "error", "-f", "lavfi", "-i",
            f"color={color}:s={size}:d=1:r=24",
        ]
        if audio:
            command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac"]
        subprocess.run([*command, "-c:v", "libx264", str(path)], check=True)

    def test_review_binds_export_and_shows_visible_revision(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            first = root / "first.mp4"
            revision = root / "revision.mp4"
            self.fixture(first, audio=True)
            self.fixture(revision, color="blue")

            report = review_export(first, root / "first-review", (0, 0.5), audio_evidence=True)
            data = json.loads(report.read_text())
            self.assertEqual(data["artifact_sha256"], artifact_digest(first))
            self.assertTrue(data["full_decode_passed"])
            self.assertTrue(data["audio_present"])
            self.assertEqual([frame["requested_seconds"] for frame in data["frames"]], [0, 0.5])
            for name in [data["contact_sheet"], *data["audio_evidence"]]:
                self.assertGreater((report.parent / name).stat().st_size, 0)
            self.assertIn("max_volume:", (report.parent / "audio-statistics.txt").read_text())

            revised = review_export(revision, root / "revised-review", (0, 0.5), audio_evidence=True)
            revised_data = json.loads(revised.read_text())
            self.assertFalse(revised_data["audio_present"])
            self.assertEqual(revised_data["audio_evidence"], [])
            self.assertNotEqual(data["artifact_sha256"], revised_data["artifact_sha256"])
            self.assertNotEqual(
                (report.parent / "frame-01.png").read_bytes(),
                (revised.parent / "frame-01.png").read_bytes(),
            )

    def test_failure_leaves_no_review_to_mistake_for_a_pass(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            corrupt = root / "corrupt.mp4"
            corrupt.write_bytes(b"not a movie")
            landscape = root / "landscape.mp4"
            self.fixture(landscape, size="160x90")
            output = root / "review"
            with self.assertRaisesRegex(ValueError, "ffprobe failed"):
                review_export(corrupt, output)
            with self.assertRaisesRegex(ValueError, "portrait"):
                review_export(landscape, output)
            self.assertFalse(output.exists())
