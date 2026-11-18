from datetime import datetime, timedelta, timezone
import unittest

from studio_distribution import check_brief, check_placement


class DistributionTest(unittest.TestCase):
    def setUp(self):
        self.public_at = datetime(2026, 11, 19, tzinfo=timezone.utc)
        self.now = self.public_at + timedelta(days=2)
        self.published = {("youtube", "abcdefghijk"): ("world-detail", self.public_at)}
        self.brief = {
            "cut": "world-detail",
            "platform": "youtube",
            "post_url": "https://youtube.com/shorts/abcdefghijk?si=share",
            "venue_url": "https://example.org/clips",
            "venue_basis": "rules_allow",
            "rules_checked_at": "2026-11-19T01:00:00Z",
            "rules_evidence": "Read the pinned clips thread rule.",
            "publisher": "After the Spike",
            "audience_fit": "The thread discusses world details.",
            "copy": "I edited a short about how the truck bed carries groceries.",
            "disclosure": "I made the edit for After the Spike.",
            "measurement": "Native outbound clicks and External traffic.",
        }

    def make_readback(self, plan):
        return {
            "brief_sha256": plan["brief_sha256"],
            "placement_url": "https://www.example.org/clips/posts/7",
            "linked_post_url": "https://youtube.com/shorts/abcdefghijk",
            "publisher": self.brief["publisher"],
            "copy": self.brief["copy"],
            "placed_at": "2026-11-19T01:05:00Z",
            "verified_at": "2026-11-19T06:37:00+05:30",
            "evidence": "Read the clipped scene and public link back in the intended thread.",
        }

    def test_organic_brief_and_readback_bind_verified_post_and_exact_copy(self):
        plan = check_brief(self.brief, self.published, self.now)
        readback = self.make_readback(plan)
        receipt = check_placement(plan, readback, self.now)
        self.assertEqual(receipt["post_url"], "https://www.youtube.com/shorts/abcdefghijk")
        self.assertEqual(receipt["post_age_seconds_at_placement"], 3900)
        changed = check_brief({**self.brief, "copy": "Changed"}, self.published, self.now)
        with self.assertRaisesRegex(ValueError, "different brief"):
            check_placement(changed, readback, self.now)

    def test_rejects_mismatched_release_or_unverified_venue(self):
        failures = (
            ({"cut": "different"}, "Cut does not match"),
            ({"post_url": "https://youtube.com/shorts/01234567890"}, "no verified"),
            ({"venue_basis": "unknown"}, "explicitly permitted"),
            ({"rules_checked_at": "2026-12-19T01:00:00Z"}, "in the future"),
            ({"venue_url": "https://name@example.org/clips"}, "without credentials"),
        )
        for fields, message in failures:
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, message):
                check_brief({**self.brief, **fields}, self.published, self.now)
        with self.assertRaisesRegex(KeyError, "campaign_distribution_terms"):
            check_brief({**self.brief, "campaign": "marketplace-1"}, self.published, self.now)

    def test_same_host_different_community_cannot_pass_readback(self):
        plan = check_brief({**self.brief, "venue_url": "https://reddit.com/r/gaming"},
                           self.published, self.now)
        readback = {**self.make_readback(plan), "placement_url": "https://www.reddit.com/r/other/comments/x",
                    "observed_venue_url": plan["venue_url"]}
        with self.assertRaisesRegex(ValueError, "outside the planned community"):
            check_placement(plan, readback, self.now)
        readback["placement_url"] = "https://www.reddit.com/r/gaming/comments/x"
        self.assertEqual(check_placement(plan, readback, self.now)["post_url"], plan["post_url"])

    def test_rejects_readbacks_for_other_venue_or_release_and_impossible_times(self):
        plan = check_brief(self.brief, self.published, self.now)
        readback = self.make_readback(plan)
        failures = (
            ({"placement_url": "https://another.example/clips/7"}, "planned venue"),
            ({"placement_url": "https://www.example.org/clips/?from=share"}, "own permalink"),
            ({"linked_post_url": "https://youtube.com/shorts/01234567890"}, "different release"),
            ({"publisher": "Another account"}, "publisher does not match"),
            ({"copy": "Different copy"}, "Visible copy does not match"),
            ({"placed_at": "2026-11-19T00:03:00Z"}, "follow publication and the rule"),
        )
        for fields, message in failures:
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, message):
                check_placement(plan, {**readback, **fields}, self.now)
