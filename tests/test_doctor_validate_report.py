"""Tests for scripts/doctor_validate_report.py (report JSON gates)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from doctor_validate_report import validate_report  # noqa: E402


class TestDoctorValidateReport(unittest.TestCase):
    def test_missing_summary_fails(self):
        errs = validate_report(
            {
                "score": 50,
                "highlights": [{"id": "h1", "insight": "x"}],
                "evidence_map": [
                    {
                        "id": "c1",
                        "claim": "a",
                        "evidence": "b",
                        "type": "x",
                    }
                ],
                "follow_up_questions": [{"question": "q", "question_type": "counter", "claim_id": "c1"}],
                "analytics": {"storylines": ["s"], "topic_signals": [], "actionable_steps": []},
            }
        )
        self.assertTrue(any("summary" in e.lower() for e in errs))

    def test_invalid_score_fails(self):
        errs = validate_report(
            {
                "summary": "ok",
                "score": 101,
                "highlights": [{"id": "h1", "insight": "x"}],
                "evidence_map": [
                    {
                        "id": "c1",
                        "claim": "a",
                        "evidence": "b",
                        "type": "x",
                    }
                ],
                "follow_up_questions": [{"question": "q", "question_type": "counter", "claim_id": "c1"}],
                "analytics": {"storylines": ["s"], "topic_signals": [], "actionable_steps": []},
            }
        )
        self.assertTrue(any("score" in e.lower() for e in errs))

    def test_valid_minimal_passes(self):
        errs = validate_report(
            {
                "summary": "Episode summary line.",
                "score": 42,
                "highlights": [{"id": "h1", "insight": "Insight one."}],
                "evidence_map": [
                    {
                        "id": "c1",
                        "claim": "Claim text here.",
                        "evidence": "Evidence quote from transcript.",
                        "type": "critique",
                    }
                ],
                "follow_up_questions": [
                    {"question": "q1", "question_type": "counter", "claim_id": "c1"},
                    {"question": "q2", "question_type": "validation", "claim_id": "c1"},
                    {"question": "q3", "question_type": "application", "claim_id": "c1"},
                ],
                "analytics": {
                    "storylines": ["a"],
                    "topic_signals": [],
                    "actionable_steps": [],
                },
            }
        )
        self.assertEqual(errs, [])

    def test_insufficient_signal_export_passes(self):
        errs = validate_report(
            {
                "metadata": {"export_status": "insufficient_signal", "export_blockers": ["segments: 0"]},
                "summary": "Export withheld: insufficient grounded signal for a network-grade report (see metadata.export_blockers).",
                "score": 0,
                "markdown_export": "# SoapBoxx — insufficient signal\n\nReason: test.\n",
            }
        )
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
