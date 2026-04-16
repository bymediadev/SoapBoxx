"""Batch telemetry over ``_guest_decision_trace`` (no pipeline side effects)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from guest_decision_telemetry import (  # noqa: E402
    aggregate_guest_decision_traces,
    trace_from_v3_report,
)


class TestGuestDecisionTelemetry(unittest.TestCase):
    def test_empty_window(self):
        out = aggregate_guest_decision_traces([], window_label="test")
        self.assertEqual(out["episode_count"], 0)
        self.assertEqual(out["window_label"], "test")
        self.assertEqual(out["system_bias_profile"]["pct_guest_generation_on"], 0.0)

    def test_aggregate_from_reports_and_traces(self):
        t1 = {
            "decision_primary_cause": "HIGH_SIGNAL_DOMINANT",
            "guest_generation_effective": True,
            "guest_generation_confidence": 0.9,
            "anchor_collapse_gate_fired": False,
            "issue_axis_effective": False,
            "high_signal_axis_effective": True,
            "anchor_stability_profile": {
                "mean_jaccard": 0.2,
                "variance_jaccard": 0.01,
            },
        }
        t2 = {
            "decision_primary_cause": "COLLAPSE_SUPPRESSION",
            "guest_generation_effective": False,
            "guest_generation_confidence": 0.35,
            "anchor_collapse_gate_fired": True,
            "issue_axis_effective": False,
            "high_signal_axis_effective": False,
            "anchor_stability_profile": {"mean_jaccard": 0.03, "variance_jaccard": 0.001},
        }
        wrapped = {"_guest_decision_trace": t1, "workflow_version": "3"}
        out = aggregate_guest_decision_traces([wrapped, t2], window_label="n2")
        self.assertEqual(out["episode_count"], 2)
        prof = out["system_bias_profile"]
        self.assertEqual(prof["pct_driven_high_signal_primary"], 50.0)
        self.assertEqual(prof["pct_collapse_suppressions"], 50.0)
        self.assertEqual(prof["count_collapse_suppressions"], 1)
        self.assertEqual(prof["pct_guest_generation_on"], 50.0)
        self.assertAlmostEqual(prof["mean_guest_generation_confidence"], 0.625, places=3)

    def test_trace_from_v3_report(self):
        self.assertIsNone(trace_from_v3_report({}))
        self.assertEqual(trace_from_v3_report({"_guest_decision_trace": {"a": 1}}), {"a": 1})


if __name__ == "__main__":
    unittest.main()
