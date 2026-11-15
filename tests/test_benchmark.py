import unittest

from benchmark import compare_case


class BenchmarkTest(unittest.TestCase):
    def test_a_gain_does_not_hide_a_lost_label(self):
        labels = [
            {"start_seconds": 10, "anchor_seconds": 15, "end_seconds": 20},
            {"start_seconds": 60, "anchor_seconds": 65, "end_seconds": 70},
        ]
        before = {"video_duration_seconds": 100, "clips": [
            {"start_seconds": 5, "end_seconds": 25},
        ]}
        after = {"video_duration_seconds": 100, "clips": [
            {"start_seconds": 50, "end_seconds": 80},
        ]}
        result = compare_case({"id": "case", "max_review_seconds": 25}, before, after, labels)
        self.assertEqual({item["label_number"] for item in result["lost"]}, {1})
        self.assertEqual({item["label_number"] for item in result["gained"]}, {2})
        self.assertEqual(result["baseline"]["fully_covered"], result["candidate"]["fully_covered"])
        self.assertTrue(result["over_review_budget"])
