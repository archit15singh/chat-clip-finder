import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from live_clipper import GAME, live_streams, replay


class TwitchCategoryTest(unittest.TestCase):
    def test_filters_a_watchlist_without_losing_stream_identity(self):
        response = {"data": [
            {"user_login": "alpha", "id": "10", "game_name": GAME},
            {"user_login": "beta", "id": "20", "game_name": "Elden Ring"},
            {"user_login": "gamma", "id": "30", "game_name": "Just Chatting"},
        ]}
        channels = ["alpha", "beta", "gamma"]
        with patch("live_clipper.urlopen", side_effect=[
            io.StringIO(json.dumps(response)), io.StringIO(json.dumps(response)),
        ]):
            gta = live_streams(channels, "token", "client", {GAME.casefold()})
            both = live_streams(channels, "token", "client", {GAME.casefold(), "elden ring"})

        self.assertEqual(gta, {"alpha": ("10", GAME)})
        self.assertEqual(both, {"alpha": ("10", GAME), "beta": ("20", "Elden Ring")})


class ReplayTest(unittest.TestCase):
    def test_interleaved_channels_keep_separate_baselines_and_overlap_checks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "chat-buckets.jsonl"
            observations = [
                {"channel": channel, "bucket": bucket, "messages": count, "game": game}
                for bucket, alpha, beta in [
                    (101, 2, 20), (102, 2, 20), (103, 2, 20), (104, 18, 18),
                    (105, 31, 81), (106, 0, 90), (107, 40, 0),
                ]
                for channel, count, game in [("alpha", alpha, GAME), ("beta", beta, "Elden Ring")]
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in observations))
            queue = io.StringIO()
            replay(path, queue)
            cues = [json.loads(line) for line in queue.getvalue().splitlines()]

        self.assertEqual([cue["id"] for cue in cues], ["alpha-1050", "beta-1060", "alpha-1080"])
        self.assertEqual([cue["baseline"] for cue in cues], [2, 20, 2])
        self.assertEqual([cue["game"] for cue in cues], [GAME, "Elden Ring", GAME])
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
