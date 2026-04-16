"""Invariant contract checks."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from report_invariants import validate_v3_invariants  # noqa: E402


class TestReportInvariants(unittest.TestCase):
    def test_primary_cause_required_in_trace(self):
        r = {
            "claims": [{"id": "c1", "text": "Alpha beta gamma delta epsilon zeta."}],
            "narrative_reconstruction": {"core_thesis": "Alpha beta gamma"},
            "_guest_decision_trace": {"decision_primary_cause": ""},
            "_sgv_applied": True,
            "coach_report": {
                "contrarian_hook": {"body": "Alpha beta gamma delta"},
                "opportunities": {"clip_moments": ["Alpha beta"]},
            },
        }
        out = validate_v3_invariants(r)
        self.assertFalse(out["ok"])
        self.assertTrue(any(v["code"] == "PRIMARY_CAUSE_MISSING" for v in out["violations"]))


if __name__ == "__main__":
    unittest.main()
