from contextlib import redirect_stderr
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from live_clipper import BEFORE_SECONDS, GAME, ChatDisconnected, live_streams, replay, watch_connection


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


class TwitchConnectionTest(unittest.TestCase):
    def test_interleaved_irc_frames_produce_replayable_cues(self):
        queue = io.StringIO()
        buckets = io.StringIO()
        chat = MagicMock()
        seconds = 1000
        irc = iter([
            (1000, b":tmi.twitch.tv 001 tester :Welcome\r\nPING :tmi.twitch.tv\r\n"),
            (1011, b":viewer PRIVMSG #alpha :first\r\n" * 2
             + b":viewer PRIVMSG #beta :first\r\n" * 4),
            (1021, b":viewer PRIVMSG #alpha :second\r\n" * 2
             + b":viewer PRIVMSG #beta :second\r\n" * 4),
            (1031, b":viewer PRIVMSG #alpha :third\r\n" * 2
             + b":viewer PRIVMSG #beta :third\r\n" * 4),
            (1041, b":viewer PRIVMSG #alpha :burst\r\n" * 16
             + b":viewer PRIVMSG #beta :burst\r\n" * 19
             + b":viewer PRIVMSG #gamma :untracked\r\n"
             + b":viewer PRIVMSG #alpha :split"),
            (1042, b" message\r\n"),
            (1050, b"PING :tmi.twitch.tv\r\n"),
            (1051, b""),
        ])

        def receive(_size):
            nonlocal seconds
            seconds, frame = next(irc)
            return frame

        chat.recv.side_effect = receive
        streams = {"alpha": ("101", GAME), "beta": ("202", GAME)}
        with (patch("live_clipper.socket.create_connection"),
              patch("live_clipper.ssl.create_default_context") as context,
              patch("live_clipper.live_streams", return_value=streams),
              patch("live_clipper.time.time", side_effect=lambda: seconds),
              patch("live_clipper.time.monotonic", side_effect=lambda: seconds),
              redirect_stderr(io.StringIO()),
              self.assertRaises(ChatDisconnected)):
            context.return_value.wrap_socket.return_value.__enter__.return_value = chat
            watch_connection(["alpha", "beta"], "test-token", "client", "tester",
                             queue, buckets, BEFORE_SECONDS, {GAME.casefold()})

        chat.sendall.assert_any_call(b"JOIN #alpha,#beta\r\n")
        chat.sendall.assert_any_call(b"PONG :tmi.twitch.tv\r\n")
        rows = [json.loads(line) for line in buckets.getvalue().splitlines()]
        self.assertEqual([(row["channel"], row["messages"], row["reset"]) for row in rows], [
            ("alpha", 2, True), ("beta", 4, True),
            ("alpha", 2, False), ("beta", 4, False),
            ("alpha", 2, False), ("beta", 4, False),
            ("alpha", 17, False), ("beta", 19, False),
        ])
        cues = [json.loads(line) for line in queue.getvalue().splitlines()]
        self.assertEqual([(cue["id"], cue["stream_id"], cue["game"]) for cue in cues], [
            ("alpha-1050", "101", GAME), ("beta-1050", "202", GAME),
        ])
        self.assertTrue(all(cue["end_unix"] - cue["start_unix"] == 30 for cue in cues))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "buckets.jsonl"
            path.write_text(buckets.getvalue(), encoding="utf-8")
            replayed = io.StringIO()
            replay(path, replayed)
        self.assertEqual(queue.getvalue(), replayed.getvalue())


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
