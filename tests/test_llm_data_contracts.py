"""Semantic validators for LLM ``data`` payloads (opt-in via env in callers)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import llm_data_contracts as ldc  # noqa: E402


class TestBriefV2Semantics(unittest.TestCase):
    def test_valid_minimal_shape(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "", "goal": ""},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        ldc.validate_brief_v2_semantics(brief)

    def test_missing_top_level_key_raises(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "", "goal": ""},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
        }
        with self.assertRaises(ValueError) as ctx:
            ldc.validate_brief_v2_semantics(brief)
        self.assertIn("action_plan_7d", str(ctx.exception))

    def test_empty_primary_topic_raises(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "  ",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "", "goal": ""},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        with self.assertRaises(ValueError) as ctx:
            ldc.validate_brief_v2_semantics(brief)
        self.assertIn("primary_topic", str(ctx.exception))


class TestWorkflowKnownKeys(unittest.TestCase):
    def test_overlap_required(self):
        ldc.validate_workflow_data_has_known_keys(
            {"highlights": []},
            expected=ldc.WORKFLOW_LLM_KNOWN_KEYS,
        )

    def test_no_overlap_raises(self):
        with self.assertRaises(ValueError):
            ldc.validate_workflow_data_has_known_keys(
                {"foo": 1},
                expected=ldc.WORKFLOW_LLM_KNOWN_KEYS,
            )


if __name__ == "__main__":
    unittest.main()
