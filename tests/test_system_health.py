"""Derived _system_health_label."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from system_health import derive_system_health_label  # noqa: E402


class TestSystemHealth(unittest.TestCase):
    def test_empty_claims_degraded(self):
        self.assertEqual(
            derive_system_health_label({"claims": [], "_guest_decision_trace": {}}),
            "CLAIM_DEGRADED",
        )

    def test_healthy_minimal(self):
        r = {
            "claims": [{"id": "c1", "text": "Environmental design beats motivation for habit persistence."}],
            "_claim_quality": {"score": 0.85, "warning": False},
            "_sgv_rewrite_count": 0,
            "_sgv_status": "OK",
            "_guest_decision_trace": {
                "decision_primary_cause": "ISSUE_AXIS_DOMINANT",
                "guest_generation_effective": True,
                "anchor_collapse_gate_fired": False,
                "anchor_alignment_score": 0.15,
            },
            "output_mode": "full",
        }
        self.assertEqual(derive_system_health_label(r), "HEALTHY")


if __name__ == "__main__":
    unittest.main()
