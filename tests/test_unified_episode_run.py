"""Tests for unified episode orchestration (no Ollama required)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import unified_episode_run as uer  # noqa: E402


class TestUnifiedEpisodeRun(unittest.TestCase):
    def test_canonicalize_workflow_fills_list_keys(self):
        raw = {"metadata": {"x": 1}, "highlights": "bad"}
        out = uer.canonicalize_workflow_report(raw)
        self.assertIsInstance(out["highlights"], list)
        self.assertEqual(out["highlights"], [])
        self.assertIsInstance(out["evidence_map"], list)

    def test_build_unified_episode_bundle_shape(self):
        v3 = {
            "report_v3": {"output_mode": "full", "signal_mode": "HIGH_SIGNAL", "meta": {"structured_intelligence_source": "atomic_pipeline"}},
            "brief": {"episode_snapshot": {"title": "T"}},
            "episode_spine": {"thesis": "x", "claims": []},
            "markdown_v3": "# v3",
            "markdown": "# net",
            "markdown_export": "",
            "warnings": ["a"],
            "meta": {"generated_at": "g", "title": "T", "creator": "c", "genre": "G"},
            "model": "m",
            "workflow_version": "3",
        }
        wf = {
            "metadata": {"source_warnings": ["a", "b"], "workflow_mode": "local+ai", "workflow_enrichment_tier": "full"},
            "highlights": [{"id": "h1"}],
            "evidence_map": [],
            "markdown_export": "# unified\n",
        }
        b = uer.build_unified_episode_bundle(v3_out=v3, workflow_report=wf, transcript="hello world " * 30)
        self.assertEqual(b["bundle_version"], uer.UNIFIED_BUNDLE_VERSION)
        self.assertIn("report_v3", b)
        self.assertIn("workflow_report", b)
        self.assertEqual(b["markdown_export"], "# unified\n")
        self.assertEqual(b["markdown_v3"], "# v3")
        self.assertIn("b", b["warnings"])
        self.assertIn("pipeline", b)
        self.assertIn("dialin", b)
        self.assertEqual(b["pipeline"]["transcript_chars"], len("hello world " * 30))

    @patch("soapboxx_v3_workflow.soapboxx_v3_workflow_local")
    @patch("episode_report_v3.generate_episode_report_v3")
    def test_run_unified_episode_pipeline_order(self, gen_v3, wf_local):
        gen_v3.return_value = {
            "report_v3": {"claims": []},
            "brief": {},
            "episode_spine": {},
            "markdown_v3": "",
            "markdown": "",
            "markdown_export": "",
            "warnings": [],
            "meta": {},
            "model": "test",
            "workflow_version": "3",
        }
        wf_local.return_value = {
            "metadata": {"source_warnings": [], "workflow_mode": "local"},
            "markdown_export": "# u",
            "highlights": [],
            "evidence_map": [],
        }
        out = uer.run_unified_episode_pipeline(
            "word " * 80,
            {"title": "Ep", "creator": "C", "genre": "G", "trace_id": "tid-1"},
            strict_references=False,
            include_v2_markdown=False,
            validate_workflow=False,
        )
        gen_v3.assert_called_once()
        wf_local.assert_called_once()
        kwargs = wf_local.call_args.kwargs
        self.assertIn("report_v3", kwargs)
        self.assertEqual(kwargs["brief_warnings"], [])
        self.assertEqual(out["markdown_export"], "# u")


if __name__ == "__main__":
    unittest.main()
