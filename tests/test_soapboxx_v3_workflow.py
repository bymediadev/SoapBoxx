"""Tests for soapboxx_v3_workflow (validation only; no API)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from soapboxx_v3_workflow import (  # noqa: E402
    WORKFLOW_SPEC_VERSION,
    _topic_specific_guest_fallback,
    validate_json,
)


class TestValidateJson(unittest.TestCase):
    def _minimal_valid(self):
        return {
            "highlights": [{"id": "h1", "insight": "Fairness matters in ministry debates."}],
            "evidence_map": [
                {
                    "id": "c1",
                    "claim": "Rumors spread without verification.",
                    "evidence": "People repeat rumors without checking.",
                    "timestamp": None,
                    "type": "critique",
                    "strength": 7,
                }
            ],
            "follow_up_questions": [
                {
                    "question": "What would a critic say is wrong with this framing?",
                    "question_type": "counter",
                    "claim_id": "c1",
                },
                {
                    "question": "What evidence would confirm or refute this claim?",
                    "question_type": "validation",
                    "claim_id": "c1",
                },
                {
                    "question": "What should listeners do differently next week?",
                    "question_type": "application",
                    "claim_id": "c1",
                },
            ],
        }

    def test_validate_ok(self):
        r = validate_json(self._minimal_valid())
        self.assertIn("evidence_map", r)

    def test_workflow_spec_version_constant(self):
        self.assertEqual(WORKFLOW_SPEC_VERSION, "3")

    def test_invalid_claim_ref(self):
        bad = self._minimal_valid()
        bad["follow_up_questions"][0]["claim_id"] = "c99"
        with self.assertRaises(ValueError):
            validate_json(bad)

    def test_missing_question_type(self):
        bad = self._minimal_valid()
        bad["follow_up_questions"] = bad["follow_up_questions"][:2]
        with self.assertRaises(ValueError):
            validate_json(bad)

    def test_guest_fallback_news_politics_not_business_celebrities(self):
        r3 = {
            "episode_snapshot": {
                "title": "BREAKING: Ottawa Police Move Against Former Politician",
                "primary_topic": "News & Politics",
            },
            "clean_insights": [],
            "claims": [{"id": "c1", "text": "Example claim about enforcement."}],
        }
        rows = _topic_specific_guest_fallback(r3, "c1")
        blob = " ".join(str(r.get("name")) + " " + str(r.get("angle")) for r in rows).lower()
        self.assertNotIn("adam grant", blob)
        self.assertNotIn("simon sinek", blob)
        self.assertNotIn("cal newport", blob)
        self.assertIn("journalist", blob)

    def test_guest_fallback_gambling_not_crime_news_template(self):
        r3 = {
            "episode_snapshot": {
                "title": "America's Newest Addiction: How Kalshi Normalizes Betting on Everything",
                "primary_topic": "Prediction markets and gambling normalization",
            },
            "clean_insights": [],
            "claims": [{"id": "c1", "text": "Election markets blur the line between investing and gambling."}],
        }
        rows = _topic_specific_guest_fallback(r3, "c1")
        names = " ".join(str(r.get("name")) for r in rows).lower()
        self.assertIn("gambling", names)
        self.assertNotIn("civil liberties", names)
        self.assertNotIn("criminal or civil litigator", names)


if __name__ == "__main__":
    unittest.main()
