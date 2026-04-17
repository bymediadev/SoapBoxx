"""Unit tests for barebones feedback engine score contract (no PyQt)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.feedback_engine_barebones import (  # noqa: E402
    _validate_feedback_scores_payload,
)


class TestFeedbackScoresPayload(unittest.TestCase):
    def test_accepts_full_scores(self):
        _validate_feedback_scores_payload(
            {
                "clarity": 1.0,
                "engagement": 2.0,
                "structure": 3.0,
                "energy": 4.0,
                "professionalism": 5.0,
                "overall_score": 3.5,
            }
        )

    def test_rejects_missing_key(self):
        with self.assertRaises(ValueError):
            _validate_feedback_scores_payload({"clarity": 1.0})

    def test_rejects_extra_key(self):
        with self.assertRaises(ValueError):
            _validate_feedback_scores_payload(
                {
                    "clarity": 1.0,
                    "engagement": 2.0,
                    "structure": 3.0,
                    "energy": 4.0,
                    "professionalism": 5.0,
                    "overall_score": 3.5,
                    "overal_score": 9.0,
                }
            )

    def test_rejects_non_numeric(self):
        with self.assertRaises(TypeError):
            _validate_feedback_scores_payload(
                {
                    "clarity": "high",
                    "engagement": 2.0,
                    "structure": 3.0,
                    "energy": 4.0,
                    "professionalism": 5.0,
                    "overall_score": 3.5,
                }
            )


if __name__ == "__main__":
    unittest.main()
