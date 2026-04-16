"""Smoke tests for blueprint v1 pipeline (no Ollama required)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blueprint_v1.pipeline import run_blueprint_v1  # noqa: E402
from blueprint_v1.schemas import EpisodicInput  # noqa: E402


class TestBlueprintV1Pipeline(unittest.TestCase):
    def test_run_produces_valid_final_report(self):
        os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)
        inp = EpisodicInput.from_metadata_transcript(
            "Host argues systems beat goals. Guest agrees with examples.",
            title="Habits Lab",
            genre="Education",
        )
        r = run_blueprint_v1(inp, max_retries=2)
        self.assertIn(r.classification.type, ("ANALYTICAL", "NARRATIVE", "HYBRID"))
        self.assertGreaterEqual(len(r.thesis), 12)
        self.assertGreaterEqual(len(r.clips), 1)
        self.assertTrue(r.actions)
        self.assertIsInstance(r.strategist_report, dict)
        self.assertIn("punchline_header", r.strategist_report)
        self.assertIn("snapshot", r.strategist_report)
        self.assertIn("upgrade_plan", r.strategist_report)
        self.assertIn("one_line_fix", r.strategist_report)
        self.assertIn("conviction_statement", r.strategist_report)
        self.assertIn("core_problem", r.strategist_report)
        self.assertIn("evidence_anchors", (r.strategist_report.get("core_breakdown") or {}))

    def test_forced_interpretive_mode(self):
        os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)
        os.environ["SOAPBOXX_STRATEGIST_MODE"] = "interpretive"
        try:
            inp = EpisodicInput.from_metadata_transcript(
                "Host chats casually about several topics without one defended claim.",
                title="Loose Conversation",
                genre="Talk",
            )
            r = run_blueprint_v1(inp, max_retries=2)
            self.assertEqual(r.strategist_report.get("report_mode"), "interpretive")
            score = int(((r.strategist_report.get("snapshot") or {}).get("overall_score")) or 0)
            self.assertLessEqual(score, 7)
        finally:
            os.environ.pop("SOAPBOXX_STRATEGIST_MODE", None)

    def test_forced_evidence_mode(self):
        os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)
        os.environ["SOAPBOXX_STRATEGIST_MODE"] = "evidence"
        try:
            inp = EpisodicInput.from_metadata_transcript(
                "Host argues one claim and revisits evidence repeatedly to defend it under challenge.",
                title="Single Claim Episode",
                genre="Business",
            )
            r = run_blueprint_v1(inp, max_retries=2)
            self.assertEqual(r.strategist_report.get("report_mode"), "evidence")
            score = int(((r.strategist_report.get("snapshot") or {}).get("overall_score")) or 0)
            self.assertLessEqual(score, 10)
        finally:
            os.environ.pop("SOAPBOXX_STRATEGIST_MODE", None)

    def test_evidence_mode_hard_gate_on_sparse_anchors(self):
        os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)
        os.environ["SOAPBOXX_STRATEGIST_MODE"] = "evidence"
        try:
            inp = EpisodicInput.from_metadata_transcript(
                "Host gives one broad claim without concrete evidence beats.",
                title="Sparse Evidence Episode",
                genre="Business",
            )
            r = run_blueprint_v1(inp, max_retries=2)
            score = int(((r.strategist_report.get("snapshot") or {}).get("overall_score")) or 0)
            self.assertLessEqual(score, 4)
        finally:
            os.environ.pop("SOAPBOXX_STRATEGIST_MODE", None)


if __name__ == "__main__":
    unittest.main()
