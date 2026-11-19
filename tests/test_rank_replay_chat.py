import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


CLI = Path(__file__).resolve().parents[1] / "scripts" / "rank-replay-chat.py"


class RankReplayChatTest(unittest.TestCase):
    def test_gift_notice_filter_preserves_audience_messages_and_raw_mode(self):
        audience = [
            {"content_offset_seconds": 60, "message": {"body": "wow"}}
            for _ in range(9)
        ]
        comments = [
            *({"content_offset_seconds": offset} for offset in range(0, 60, 10)),
            *audience,
            {"content_offset_seconds": 60, "message": None},
            {"content_offset_seconds": 61, "message": {"body": "I love the gifted sub alerts!"}},
            {"content_offset_seconds": 61, "message": {
                "body": "viewer is gifting 10 Tier 1 Subs to creator's community! "
                "They've gifted a total of 10 in the channel! ",
            }},
            {"content_offset_seconds": 61, "message": {
                "body": "viewer gifted a Tier 1 sub to someone!",
            }},
        ]
        with TemporaryDirectory() as directory:
            chat = Path(directory) / "chat.json"
            chat.write_text(json.dumps({
                "video": {"id": "123", "start": 0, "end": 70},
                "comments": comments,
            }), encoding="utf-8")
            command = [sys.executable, str(CLI), str(chat)]
            raw = json.loads(subprocess.check_output(command))
            filtered = json.loads(subprocess.check_output([*command, "--exclude-gift-notices"]))

        self.assertNotIn("gift_notices_excluded", raw)
        self.assertEqual(raw["peaks"][0]["messages"], 13)
        self.assertEqual(filtered["gift_notices_excluded"], 2)
        self.assertEqual(filtered["peaks"][0]["messages"], 11)
        self.assertEqual(filtered["peaks"][0]["baseline_median"], 1)
