"""Invariant tests: atomic-backed v3 reports must not lose SSOT in workflow AI enrichment."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import soapboxx_v3_workflow as wf  # noqa: E402


class TestAtomicStructureLock(unittest.TestCase):
    def test_lock_detection(self):
        self.assertFalse(wf._atomic_structure_lock_from_report_v3(None))
        self.assertFalse(wf._atomic_structure_lock_from_report_v3({}))
        self.assertTrue(
            wf._atomic_structure_lock_from_report_v3(
                {"meta": {"structured_intelligence_source": "atomic_pipeline"}}
            )
        )
        self.assertTrue(wf._atomic_structure_lock_from_report_v3({"atomic_pipeline": {"claims": []}}))

    @patch.object(wf, "generate_analytics", return_value={})
    @patch.object(wf, "generate_segments", return_value=[])
    @patch.object(wf, "generate_follow_up_questions", return_value=[])
    @patch.object(wf, "generate_guest_recommendations")
    @patch.object(wf, "generate_evidence_map")
    @patch.object(wf, "generate_highlights")
    def test_full_enrich_preserves_evidence_and_guests_when_locked(
        self, mock_hl, mock_em, mock_gr, *_mocks
    ):
        mock_hl.return_value = [
            {
                "id": "h1",
                "insight": (
                    "Systems outperform goals when motivation is unreliable over long horizons "
                    "for working creators."
                ),
                "length_words": 14,
                "priority": "high",
            }
        ]
        mock_em.return_value = [
            {
                "id": "bad1",
                "claim": "LLM claim",
                "evidence": "nope",
                "timestamp": None,
                "type": "other",
                "strength": 1,
            }
        ]
        mock_gr.return_value = [
            {
                "name": "LLM Guest",
                "title": "X",
                "role": "X",
                "claim_id": "bad1",
                "angle": "wrong",
            }
        ]
        body = {
            "highlights": [],
            "evidence_map": [
                {
                    "id": "a1",
                    "claim": "truth",
                    "evidence": "verbatim from tape",
                    "timestamp": 1.0,
                    "type": "other",
                    "strength": 9,
                }
            ],
            "guest_recommendations": [
                {
                    "name": "Atomic Guest",
                    "title": "Historian",
                    "role": "historian",
                    "claim_id": "a1",
                    "angle": "graph-backed",
                }
            ],
            "follow_up_questions": [],
            "segments": [],
            "analytics": {},
        }
        r3 = {"meta": {"structured_intelligence_source": "atomic_pipeline"}}
        transcript = "host says something substantive about the episode topic. " * 30
        with patch.dict(os.environ, {"SOAPBOXX_WORKFLOW_EVIDENCE_MODE": "full"}):
            out = wf.enrich_workflow_report_with_ai(transcript, body, report_v3=r3)
        self.assertEqual(out["evidence_map"][0]["claim"], "truth")
        self.assertEqual(out["guest_recommendations"][0]["name"], "Atomic Guest")
        self.assertEqual(out["guests"][0]["name"], "Atomic Guest")
        self.assertIn("Systems outperform goals", out["highlights"][0]["insight"])
        mock_em.assert_not_called()
        mock_gr.assert_not_called()

    @patch.object(wf, "call_llm_json")
    def test_minimal_enrich_does_not_replace_evidence_map_when_locked(self, mock_llm):
        mock_llm.return_value = {
            "highlights": [{"id": "h1", "insight": "x", "length_words": 1, "priority": "high"}],
            "evidence_map": [
                {
                    "id": "z9",
                    "claim": "bad",
                    "evidence": "bad",
                    "timestamp": None,
                    "type": "other",
                    "strength": 1,
                }
            ],
            "follow_up_questions": [],
        }
        body = {
            "highlights": [],
            "evidence_map": [
                {
                    "id": "keep",
                    "claim": "good",
                    "evidence": "ok",
                    "timestamp": None,
                    "type": "other",
                    "strength": 8,
                }
            ],
            "follow_up_questions": [],
        }
        r3 = {"atomic_pipeline": {"claims": [{"id": "a1"}]}}
        transcript = "word " * 200
        with patch.dict(os.environ, {"SOAPBOXX_WORKFLOW_EVIDENCE_MODE": "anchors"}):
            out = wf.enrich_workflow_report_minimal(transcript, body, report_v3=r3)
        self.assertEqual(out["evidence_map"][0]["id"], "keep")

    @patch.object(wf, "generate_analytics", return_value={})
    @patch.object(wf, "generate_segments", return_value=[])
    @patch.object(wf, "generate_follow_up_questions", return_value=[])
    @patch.object(wf, "generate_guest_recommendations")
    @patch.object(wf, "generate_evidence_map")
    @patch.object(wf, "generate_highlights")
    def test_lock_does_not_restore_empty_guest_baseline_over_mapper_guests(
        self, mock_hl, mock_em, mock_gr, *_mocks
    ):
        """Empty guest snapshot must not wipe non-empty ``guest_recommendations`` from ``body``."""
        mock_hl.return_value = [
            {
                "id": "h1",
                "insight": "Host discusses the episode with enough words for the gate.",
                "length_words": 12,
                "priority": "high",
            }
        ]
        body = {
            "highlights": [],
            "evidence_map": [
                {
                    "id": "a1",
                    "claim": "kept claim",
                    "evidence": "verbatim",
                    "timestamp": 1.0,
                    "type": "other",
                    "strength": 9,
                }
            ],
            "guest_recommendations": [
                {
                    "name": "Tier3 Guest",
                    "title": "Historian",
                    "role": "subject_matter_expert",
                    "claim_id": "a1",
                    "angle": "from mapper",
                    "source": "subject_fallback_tier3",
                }
            ],
            "follow_up_questions": [],
            "segments": [],
            "analytics": {},
        }
        orig_snap = wf._snapshot_workflow_rows

        def snap_guest_baseline_empty(rows):
            if rows is body["guest_recommendations"]:
                return []
            return orig_snap(rows)

        r3 = {"meta": {"structured_intelligence_source": "atomic_pipeline"}}
        transcript = "host says something substantive about the episode topic. " * 30
        with patch.dict(os.environ, {"SOAPBOXX_WORKFLOW_EVIDENCE_MODE": "full"}):
            with patch.object(wf, "_snapshot_workflow_rows", side_effect=snap_guest_baseline_empty):
                out = wf.enrich_workflow_report_with_ai(transcript, body, report_v3=r3)
        self.assertEqual(out["guest_recommendations"][0]["name"], "Tier3 Guest")
        self.assertEqual(out["guests"][0]["name"], "Tier3 Guest")
        self.assertEqual(out["evidence_map"][0]["claim"], "kept claim")
        mock_em.assert_not_called()
        mock_gr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
