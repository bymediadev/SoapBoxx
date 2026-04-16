"""Pipeline telemetry window comparison."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pipeline_telemetry import aggregate_pipeline_telemetry, compare_telemetry_windows  # noqa: E402


def _fake_report(trace_pc: str, cq: float, sgv_rw: int, rewritten: bool) -> dict:
    return {
        "_guest_decision_trace": {
            "decision_primary_cause": trace_pc,
            "guest_generation_effective": True,
            "anchor_collapse_gate_fired": False,
            "guest_generation_confidence": 0.7,
            "anchor_stability_profile": {"variance_jaccard": 0.01, "mean_jaccard": 0.12},
        },
        "_claim_quality": {"score": cq, "warning": cq < 0.52, "signals": {}},
        "_sgv_rewrite_count": sgv_rw,
        "_sgv_status": "REWRITTEN" if rewritten else "OK",
    }


class TestPipelineTelemetry(unittest.TestCase):
    def test_compare_detects_drift(self):
        recent_reports = [_fake_report("HIGH_SIGNAL_DOMINANT", 0.8, 4, True) for _ in range(10)]
        base_reports = [_fake_report("ISSUE_AXIS_DOMINANT", 0.8, 0, False) for _ in range(10)]
        rec = aggregate_pipeline_telemetry(recent_reports, window_label="last_10")
        base = aggregate_pipeline_telemetry(base_reports, window_label="prev_10")
        cmp = compare_telemetry_windows(rec, base)
        self.assertTrue(cmp["DRIFT_DETECTED"])
        self.assertIn("sgv_rewrite_rate", cmp["drift_axes"])

    def test_compare_no_drift_similar(self):
        r = [_fake_report("HIGH_SIGNAL_DOMINANT", 0.75, 1, False) for _ in range(5)]
        b = [_fake_report("HIGH_SIGNAL_DOMINANT", 0.76, 1, False) for _ in range(5)]
        cmp = compare_telemetry_windows(
            aggregate_pipeline_telemetry(r, window_label="a"),
            aggregate_pipeline_telemetry(b, window_label="b"),
            abs_delta_claim_quality=0.5,
            abs_delta_sgv_rewrite=5.0,
            abs_delta_high_signal_pct=50.0,
            abs_delta_collapse_pct=50.0,
        )
        self.assertFalse(cmp["DRIFT_DETECTED"])


if __name__ == "__main__":
    unittest.main()
