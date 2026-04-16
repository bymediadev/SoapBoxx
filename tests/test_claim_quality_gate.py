"""Pre-SGV claim substrate checks."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from claim_quality_gate import apply_claim_quality_gate, assess_claim_quality  # noqa: E402


class TestClaimQualityGate(unittest.TestCase):
    def test_empty_claims_warns(self):
        a = assess_claim_quality([])
        self.assertTrue(a["warning"])
        self.assertLessEqual(a["score"], 0.1)

    def test_solid_claims_no_warning(self):
        claims = [
            {"id": "c1", "text": "Environmental design reduces friction so habits persist when motivation drops."},
            {"id": "c2", "text": "Removing obstacles for good actions increases follow-through by 40 percent in some studies."},
        ]
        a = assess_claim_quality(claims)
        self.assertGreater(a["score"], 0.6)
        self.assertFalse(a["signals"]["redundant_pair"])

    def test_fragments_lower_score(self):
        claims = [
            {"id": "c1", "text": "ok"},
            {"id": "c2", "text": "hi"},
        ]
        a = assess_claim_quality(claims)
        self.assertTrue(a["warning"])
        self.assertGreater(a["signals"]["fragment_ratio"], 0.5)

    def test_apply_stamp_on_report(self):
        r = {
            "claims": [{"id": "c1", "text": "A complete sentence with enough words to pass fragment checks easily."}],
        }
        old = os.environ.get("SOAPBOXX_CLAIM_QUALITY_GATE")
        try:
            os.environ.pop("SOAPBOXX_CLAIM_QUALITY_GATE", None)
            out = apply_claim_quality_gate(r)
            self.assertIn("score", out["_claim_quality"])
        finally:
            if old is not None:
                os.environ["SOAPBOXX_CLAIM_QUALITY_GATE"] = old


if __name__ == "__main__":
    unittest.main()
