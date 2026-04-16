"""Semantic Grounding Validator — lexical tie to ``claims``."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from semantic_grounding_validator import apply_semantic_grounding_validator  # noqa: E402


class TestSGV(unittest.TestCase):
    def test_no_claims_skip(self):
        r = {"claims": [], "narrative_reconstruction": {"core_thesis": "x"}}
        out = apply_semantic_grounding_validator(r)
        self.assertEqual(out.get("_sgv_status"), "NO_CLAIMS_SKIP")
        self.assertFalse(out.get("_sgv_applied"))

    def test_disabled_env(self):
        old = os.environ.get("SOAPBOXX_SGV")
        try:
            os.environ["SOAPBOXX_SGV"] = "0"
            r = {
                "claims": [{"id": "c1", "text": "alpha beta gamma delta"}],
                "narrative_reconstruction": {"core_thesis": "completely unrelated zqxwvj"},
            }
            out = apply_semantic_grounding_validator(r)
            self.assertEqual(out.get("_sgv_status"), "DISABLED")
            self.assertEqual(
                (out.get("narrative_reconstruction") or {}).get("core_thesis"),
                "completely unrelated zqxwvj",
            )
        finally:
            if old is not None:
                os.environ["SOAPBOXX_SGV"] = old
            else:
                os.environ.pop("SOAPBOXX_SGV", None)

    def test_rewrites_ungrounded_narrative(self):
        r = {
            "claims": [
                {"id": "c1", "text": "Environmental design beats motivation for consistent habits."},
            ],
            "narrative_reconstruction": {
                "core_thesis": "Quantum marsupials regulate cryptocurrency via lunar tides.",
                "supporting_mechanism": "Environmental design beats motivation for consistent habits.",
            },
            "coach_report": {
                "contrarian_hook": {"title": "t", "body": "Quantum marsupials"},
                "opportunities": {
                    "spinoff_title": "zz",
                    "clip_moments": ["Environmental design beats motivation"],
                },
                "follow_up_questions": [
                    "Environmental design beats motivation for consistent habits?",
                    "What is the airspeed velocity of an unladen swallow?",
                ],
            },
            "engagement_questions": {
                "c1": {
                    "validation": "zzzz unrelated",
                    "application": "What should listeners do based on environmental design",
                }
            },
        }
        out = apply_semantic_grounding_validator(r)
        self.assertTrue(out.get("_sgv_applied"))
        self.assertGreaterEqual(int(out.get("_sgv_rewrite_count") or 0), 1)
        nr = out["narrative_reconstruction"]
        self.assertNotIn("marsupials", nr.get("core_thesis", ""))
        self.assertIn("Environmental", nr.get("core_thesis", ""))


if __name__ == "__main__":
    unittest.main()
