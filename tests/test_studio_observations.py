from datetime import datetime, timedelta, timezone
import unittest

from studio_observations import check_observations


class ObservationTest(unittest.TestCase):
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
        checked, = check_observations([row], published, now)
        self.assertEqual(checked["age_seconds"], 88200)
        self.assertEqual(checked["url"], "https://www.youtube.com/shorts/abcdefghijk")
        self.assertEqual(checked["metrics"], row["metrics"])
        for overrides, message in (
            ({"url": "https://www.youtube.com/shorts/01234567890"}, "no verified"),
            ({"observed_at": "2026-11-18T00:00:00Z"}, "between publication and now"),
            ({"observed_at": "2026-11-22T00:00:00Z"}, "between publication and now"),
            ({"observed_at": "2026-11-20T01:00:00"}, "time zone"),
            ({"metrics": {"Views": False}}, "nonnegative metrics"),
        ):
            with self.subTest(overrides=overrides), self.assertRaisesRegex(ValueError, message):
                check_observations([{**row, **overrides}], published, now)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            check_observations([row, row], published, now)
