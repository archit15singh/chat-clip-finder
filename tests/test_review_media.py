import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from restore_source_audio import restore_audio
from review_media import MIN_SIGNAL_PEAK_DBFS, artifact_digest, review_export


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
            self.assertGreater(data["audio_peak_dbfs"], MIN_SIGNAL_PEAK_DBFS)
            self.assertEqual([frame["requested_seconds"] for frame in data["frames"]], [0, 0.5])
            for name in [data["contact_sheet"], *data["audio_evidence"]]:
                self.assertGreater((report.parent / name).stat().st_size, 0)
            statistics = (report.parent / "audio-statistics.txt").read_text()
            self.assertIn("max_volume:", statistics)
            self.assertRegex(statistics, r"\bI:\s*-\d+\.\d+ LUFS")
            self.assertRegex(statistics, r"True peak:\s+Peak:\s*-\d+\.\d+ dBFS")

            revised = review_export(revision, root / "revised-review", (0, 0.5), audio_evidence=True)
            revised_data = json.loads(revised.read_text())
            self.assertFalse(revised_data["audio_present"])
            self.assertIsNone(revised_data["audio_peak_dbfs"])
            self.assertEqual(revised_data["audio_evidence"], [])
            self.assertNotEqual(data["artifact_sha256"], revised_data["artifact_sha256"])
            self.assertNotEqual(
                (report.parent / "frame-01.png").read_bytes(),
                (revised.parent / "frame-01.png").read_bytes(),
            )

    def test_restores_audio_without_changing_video(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            picture = root / "picture.mp4"
            source = root / "source.mp4"
            output = root / "restored.mp4"
            self.fixture(picture)
            self.fixture(source, audio=True)
            with self.assertRaisesRegex(ValueError, "Source has no audio"):
                restore_audio(picture, picture, [(0, 1)], output)
            with self.assertRaisesRegex(ValueError, "match the picture"):
                restore_audio(picture, source, [(0, 0.5)], output)
            self.assertFalse(output.exists())
            restore_audio(picture, source, [(0.1, 0.6), (0.5, 1)], output)
            report = json.loads(review_export(output, root / "restored-review", (0,)).read_text())
            self.assertGreater(report["audio_peak_dbfs"], MIN_SIGNAL_PEAK_DBFS)

            def video_hash(path):
                return subprocess.check_output([
                    "ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
                    "-c", "copy", "-f", "hash", "-",
                ])

            self.assertEqual(video_hash(picture), video_hash(output))

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
