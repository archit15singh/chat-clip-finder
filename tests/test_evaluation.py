import unittest

from evaluate import evaluate


class EvaluationTest(unittest.TestCase):
    def test_two_partial_clips_do_not_make_a_whole_moment(self):
        report = {"video_duration_seconds": 100, "clips": [
            {"start_seconds": 10, "end_seconds": 20},
            {"start_seconds": 20, "end_seconds": 30},
        ]}
        labels = [
            {"start_seconds": 10, "end_seconds": 20},
            {"start_seconds": 18, "end_seconds": 22},
            {"start_seconds": 30, "end_seconds": 40},
        ]
        score = evaluate(report, labels)
        self.assertEqual((score["fully_covered"], score["partially_covered"], score["missed"]), (1, 1, 1))
        self.assertEqual(score["candidates_covering_a_label"], 1)
        self.assertEqual(score["moments"][1]["partially_covered_by"], [1, 2])
        self.assertEqual(evaluate({**report, "clips": []}, labels)["missed"], 3)
