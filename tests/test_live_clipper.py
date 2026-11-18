import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from live_clipper import replay


class ReplayTest(unittest.TestCase):
    def test_interleaved_channels_keep_separate_baselines_and_overlap_checks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "chat-buckets.jsonl"
            observations = [
                {"channel": channel, "bucket": bucket, "messages": count}
                for bucket, alpha, beta in [
                    (101, 2, 20), (102, 2, 20), (103, 2, 20), (104, 18, 18),
                    (105, 31, 81), (106, 0, 90), (107, 40, 0),
                ]
                for channel, count in [("alpha", alpha), ("beta", beta)]
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in observations))
            queue = io.StringIO()
            replay(path, queue)
            cues = [json.loads(line) for line in queue.getvalue().splitlines()]

        self.assertEqual([cue["id"] for cue in cues], ["alpha-1050", "beta-1060", "alpha-1080"])
        self.assertEqual([cue["baseline"] for cue in cues], [2, 20, 2])
        self.assertTrue(all(cue["end_unix"] - cue["start_unix"] == 30 for cue in cues))

    def test_reset_starts_a_new_warmup_period(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "chat-buckets.jsonl"
            observations = [
                {"channel": "alpha", "bucket": bucket, "messages": count, "reset": bucket == 104}
                for bucket, count in [
                    (101, 2), (102, 2), (103, 2), (104, 25),
                    (105, 2), (106, 2), (107, 25),
                ]
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in observations))
            queue = io.StringIO()
            replay(path, queue)
            cues = [json.loads(line) for line in queue.getvalue().splitlines()]

        self.assertEqual([cue["id"] for cue in cues], ["alpha-1080"])
