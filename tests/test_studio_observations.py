from datetime import datetime, timedelta, timezone
from subprocess import CompletedProcess
import unittest
from unittest.mock import patch

from studio_observations import check_observations, collect_public_observations


class ObservationTest(unittest.TestCase):
    def test_public_probe_requires_a_verified_post_and_requested_age(self):
        link = "https://youtube.com/shorts/abcdefghijk?si=share"
        canonical = "https://www.youtube.com/shorts/abcdefghijk"
        now = datetime.now(timezone.utc)
        published = {("youtube", "abcdefghijk"): ("cut", now - timedelta(hours=24, minutes=10))}
        with patch("studio_observations.subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "No verified publication"):
                collect_public_observations([link], {}, None)
            with self.assertRaisesRegex(ValueError, "outside the named milestone"):
                collect_public_observations([link], published, 72)
            run.assert_not_called()
            run.return_value = CompletedProcess([], 0, '{"id": "other", "view_count": 42}')
            with self.assertRaisesRegex(ValueError, "did not identify"):
                collect_public_observations([link], published, 24)
            run.reset_mock()
            run.return_value = CompletedProcess([], 0, '{"id": "abcdefghijk", "view_count": 0}')
            raw = collect_public_observations([link, canonical], published, 24)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0][-1], canonical)
        checked, = check_observations(raw, published, datetime.now(timezone.utc))
        self.assertEqual(checked["milestone_hours"], 24)
        self.assertEqual(checked["metrics"], {"view_count": 0, "like_count": None, "comment_count": None})

    def test_only_verified_posts_and_real_readback_ages_are_accepted(self):
        published_at = datetime(2026, 11, 19, tzinfo=timezone.utc)
        now = published_at + timedelta(days=2)
        published = {("youtube", "abcdefghijk"): ("cut", published_at)}
        row = {
            "platform": "youtube", "url": "https://youtube.com/shorts/abcdefghijk?si=share",
            "observed_at": "2026-11-20T06:00:00+05:30",
            "metric_source": "Shorts analytics",
            "metrics": {"Views": 0, "Stayed to watch (%)": None},
        }
        checked, = check_observations([{**row, "milestone_hours": 24}], published, now)
        self.assertEqual(checked["milestone_hours"], 24)
        self.assertEqual(checked["age_seconds"], 88200)
        self.assertEqual(checked["url"], "https://www.youtube.com/shorts/abcdefghijk")
        self.assertEqual(checked["metrics"], row["metrics"])
        for overrides, message in (
            ({"url": "https://www.youtube.com/shorts/01234567890"}, "no verified"),
            ({"observed_at": "2026-11-18T00:00:00Z"}, "between publication and now"),
            ({"observed_at": "2026-11-22T00:00:00Z"}, "between publication and now"),
            ({"observed_at": "2026-11-20T01:00:00"}, "time zone"),
            ({"metrics": {"Views": False}}, "nonnegative metrics"),
            ({"observed_at": "2026-11-19T00:10:00Z", "milestone_hours": 24}, "milestone window"),
            ({"observed_at": "2026-11-20T04:00:00Z", "milestone_hours": 24}, "milestone window"),
        ):
            with self.subTest(overrides=overrides), self.assertRaisesRegex(ValueError, message):
                check_observations([{**row, **overrides}], published, now)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            check_observations([row, row], published, now)
