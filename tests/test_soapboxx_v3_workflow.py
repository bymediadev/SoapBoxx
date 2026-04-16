"""Tests for soapboxx_v3_workflow (validation only; no API)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from soapboxx_v3_workflow import (  # noqa: E402
    WORKFLOW_SPEC_VERSION,
    _compute_structure_diagnostics,
    _editorial_pass_enabled,
    _derive_structure_state,
    _topic_specific_guest_fallback,
    generate_guest_archetypes_from_issues,
    should_generate_guests,
    validate_json,
    workflow_report_from_v3_report,
)
from guest_generation_decision import build_guest_decision_trace  # noqa: E402


class TestValidateJson(unittest.TestCase):
    def _minimal_valid(self):
        return {
            "highlights": [{"id": "h1", "insight": "Fairness matters in ministry debates."}],
            "evidence_map": [
                {
                    "id": "c1",
                    "claim": "Rumors spread without verification.",
                    "evidence": "People repeat rumors without checking.",
                    "timestamp": None,
                    "type": "critique",
                    "strength": 7,
                }
            ],
            "follow_up_questions": [
                {
                    "question": "What would a critic say is wrong with this framing?",
                    "question_type": "counter",
                    "claim_id": "c1",
                },
                {
                    "question": "What evidence would confirm or refute this claim?",
                    "question_type": "validation",
                    "claim_id": "c1",
                },
                {
                    "question": "What should listeners do differently next week?",
                    "question_type": "application",
                    "claim_id": "c1",
                },
            ],
        }

    def test_validate_ok(self):
        r = validate_json(self._minimal_valid())
        self.assertIn("evidence_map", r)

    def test_should_generate_guests_when_coach_issues_present(self):
        r3 = {
            "episode_snapshot": {"title": "T"},
            "coach_report": {"where_it_breaks": {"issues": ["Narrative drift"]}},
            "segments": [{"segment_title": "A"}],
            "report_readiness": {"band": "strong"},
        }
        self.assertTrue(should_generate_guests(r3))

    def test_should_generate_guests_high_signal_rich_no_issues(self):
        """Resilience: HIGH_SIGNAL + several insights + empty issues — needs strong anchor alignment."""
        r3 = {
            "signal_mode": "HIGH_SIGNAL",
            # Short strings keep gather_issue_blob under 40 chars so primary path stays off.
            "clean_insights": ["a", "b", "c"],
            "coach_report": {"where_it_breaks": {"issues": []}},
            "report_readiness": {"band": "strong"},
            # Enrichment-only path requires min Jaccard from identity consistency samples.
            "_consistency_jaccard_samples": [
                {"field": "narrative_reconstruction.core_thesis", "jaccard": 0.15, "tier": "ok"},
            ],
        }
        self.assertTrue(should_generate_guests(r3))

    def test_should_not_guest_nudge_when_not_high_signal(self):
        r3 = {
            "signal_mode": "MEDIUM_SIGNAL",
            "clean_insights": ["a", "b", "c"],
            "coach_report": {"where_it_breaks": {"issues": []}},
            "report_readiness": {"band": "strong"},
        }
        self.assertFalse(should_generate_guests(r3))

    def test_high_signal_guest_suppressed_when_anchor_alignment_low(self):
        """Cross-axis: HIGH_SIGNAL enrichment does not fire when identity Jaccard is weak."""
        r3 = {
            "signal_mode": "HIGH_SIGNAL",
            "clean_insights": ["a", "b", "c"],
            "coach_report": {"where_it_breaks": {"issues": []}},
            "report_readiness": {"band": "strong"},
            "_consistency_jaccard_samples": [
                {"field": "narrative_reconstruction.core_thesis", "jaccard": 0.04, "tier": "collapse"},
            ],
        }
        self.assertFalse(should_generate_guests(r3))

    def test_issue_axis_suppressed_at_anchor_collapse(self):
        """Symmetric gate: extreme anchor collapse suppresses issue-axis too (min_j < 0.05)."""
        r3 = {
            "signal_mode": "HIGH_SIGNAL",
            "clean_insights": ["a", "b", "c"],
            "coach_report": {"where_it_breaks": {"issues": ["Narrative drift"]}},
            "_consistency_jaccard_samples": [
                {"field": "narrative_reconstruction.core_thesis", "jaccard": 0.04, "tier": "collapse"},
            ],
        }
        self.assertFalse(should_generate_guests(r3))

    def test_issue_axis_fires_when_above_collapse_but_below_high_signal_gate(self):
        """Issue-axis still allowed in repair/soft band (between collapse and enrichment thresholds)."""
        r3 = {
            "signal_mode": "HIGH_SIGNAL",
            "clean_insights": ["a", "b", "c"],
            "coach_report": {"where_it_breaks": {"issues": ["Narrative drift"]}},
            "_consistency_jaccard_samples": [
                {"field": "narrative_reconstruction.core_thesis", "jaccard": 0.06, "tier": "repair"},
            ],
        }
        self.assertTrue(should_generate_guests(r3))

    def test_variance_rescue_outlier_min_does_not_structural_collapse(self):
        """Low min + high cross-field variance: issue-axis can remain on; primary cause is rescue."""
        r3 = {
            "signal_mode": "HIGH_SIGNAL",
            "clean_insights": ["a", "b", "c"],
            "coach_report": {"where_it_breaks": {"issues": ["Narrative drift"]}},
            "_consistency_jaccard_samples": [
                {"field": "narrative_reconstruction.core_thesis", "jaccard": 0.04, "tier": "collapse"},
                {"field": "narrative_reconstruction.supporting_mechanism", "jaccard": 0.82, "tier": "ok"},
            ],
        }
        self.assertTrue(should_generate_guests(r3))
        tr = build_guest_decision_trace(r3)
        self.assertEqual(tr.get("decision_primary_cause"), "ANCHOR_RESCUE_OVERRIDE")
        self.assertEqual(tr.get("anchor_collapse_reason"), "min_below_but_high_variance_outlier")

    def test_workflow_spec_version_constant(self):
        self.assertEqual(WORKFLOW_SPEC_VERSION, "3")

    def test_invalid_claim_ref(self):
        bad = self._minimal_valid()
        bad["follow_up_questions"][0]["claim_id"] = "c99"
        with self.assertRaises(ValueError):
            validate_json(bad)

    def test_missing_question_type(self):
        bad = self._minimal_valid()
        bad["follow_up_questions"] = bad["follow_up_questions"][:2]
        with self.assertRaises(ValueError):
            validate_json(bad)

    def test_guest_fallback_news_politics_not_business_celebrities(self):
        r3 = {
            "episode_snapshot": {
                "title": "BREAKING: Ottawa Police Move Against Former Politician",
                "primary_topic": "News & Politics",
            },
            "clean_insights": [],
            "claims": [{"id": "c1", "text": "Example claim about enforcement."}],
        }
        rows = _topic_specific_guest_fallback(r3, "c1")
        blob = " ".join(str(r.get("name")) + " " + str(r.get("angle")) for r in rows).lower()
        self.assertNotIn("adam grant", blob)
        self.assertNotIn("simon sinek", blob)
        self.assertNotIn("cal newport", blob)
        self.assertIn("journalist", blob)

    def test_generate_guest_archetypes_from_episode_issues(self):
        r3 = {
            "episode_snapshot": {
                "title": "Chief Joseph and the Nez Perce War",
                "primary_topic": "Nez Perce resistance and forced relocation",
                "genre": "History",
            },
            "coach_report": {
                "where_it_breaks": {
                    "issues": [
                        "Narrative drift across themes",
                        "Weak structure and unclear arc",
                        "Mixed themes: history + philosophy + religion",
                    ],
                },
            },
            "clean_insights": ["The episode jumps between timelines without a clear through-line."],
            "claims": [{"id": "c1", "text": "Federal policy pressured removal."}],
        }
        rows = generate_guest_archetypes_from_issues(r3, "c1")
        self.assertGreaterEqual(len(rows), 2)
        self.assertLessEqual(len(rows), 3)
        self.assertTrue(str(rows[0].get("commitment_line") or "").startswith("**Start with this:**"))
        self.assertIn("segments", str(rows[0].get("next_episode_move") or "").lower())
        self.assertEqual(rows[0].get("guest_sequence"), "primary")
        self.assertEqual(rows[0].get("sequence_label"), "Primary guest (start here)")
        if len(rows) > 1:
            self.assertEqual(rows[1].get("guest_sequence"), "secondary")
            self.assertEqual(rows[1].get("sequence_label"), "Secondary guest (next step)")
            self.assertIsNone(rows[1].get("next_episode_move"))
        for g in rows:
            self.assertTrue(g.get("guest_archetype"))
            self.assertTrue(g.get("what_it_fixes"))
            self.assertTrue(g.get("angle"))
            self.assertTrue(g.get("topic_angle"))
            self.assertTrue(g.get("archetype_kind"))

    def test_workflow_report_uses_archetypes_when_issues_and_no_guest_rows(self):
        r3 = {
            "episode_snapshot": {
                "title": "Test episode",
                "primary_topic": "A test topic",
                "genre": "Education",
            },
            "clean_insights": ["Insight about structure drifting mid-episode."],
            "claims": [{"id": "c1", "text": "A sample claim."}],
            "evidence_mapping": [],
            "engagement_questions": {},
            "segments": [],
            "coach_report": {
                "where_it_breaks": {
                    "issues": [
                        "Narrative drift",
                        "No clear arc or chapter beats",
                    ],
                },
            },
            "guests": [],
        }
        wf = workflow_report_from_v3_report(r3)
        gr = wf.get("guest_recommendations") or []
        self.assertGreaterEqual(len(gr), 2)
        self.assertTrue(any(isinstance(g, dict) and g.get("guest_archetype") for g in gr))
        self.assertTrue(str(gr[0].get("commitment_line") or "").startswith("**Start with this:**"))

    def test_guest_fallback_gambling_not_crime_news_template(self):
        r3 = {
            "episode_snapshot": {
                "title": "America's Newest Addiction: How Kalshi Normalizes Betting on Everything",
                "primary_topic": "Prediction markets and gambling normalization",
            },
            "clean_insights": [],
            "claims": [{"id": "c1", "text": "Election markets blur the line between investing and gambling."}],
        }
        rows = _topic_specific_guest_fallback(r3, "c1")
        names = " ".join(str(r.get("name")) for r in rows).lower()
        self.assertIn("gambling", names)
        self.assertNotIn("civil liberties", names)
        self.assertNotIn("criminal or civil litigator", names)


class TestV3RealityChecksInWorkflow(unittest.TestCase):
    def test_metadata_contains_v3_reality_check(self):
        import episode_report_v3 as v3
        from soapboxx_v3_workflow import soapboxx_v3_workflow_local

        brief = {
            "episode_snapshot": {
                "title": "Systems vs Goals",
                "creator": "Test",
                "genre": "Education",
                "primary_topic": "habit systems",
                "why_it_matters": "w",
            },
            "narrative": [
                "Systems outperform goals when motivation is unreliable.",
                "Friction design determines whether routines stick.",
            ],
            "claims": [
                {"id": "c1", "text": "Systems beat goals when motivation drops.", "claim_type": "interpretation", "confidence": "medium", "why_it_matters": "m"},
                {"id": "c2", "text": "Habits survive low motivation because routines automate behavior.", "claim_type": "interpretation", "confidence": "high", "why_it_matters": "m"},
                {"id": "c3", "text": "Remove friction for good actions and add friction for bad ones.", "claim_type": "interpretation", "confidence": "high", "why_it_matters": "m"},
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "s", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        transcript = (
            "Host: Systems beat goals when motivation drops. "
            "Guest: Habits survive low motivation because routines automate behavior. "
            "Host: Remove friction for good actions and add friction for bad ones."
        )
        r3 = v3.build_v3_report(brief, transcript, metadata={})
        meta = {"title": "Systems vs Goals", "creator": "Test", "genre": "Education"}
        old_ai = os.environ.get("SOAPBOXX_WORKFLOW_USE_AI")
        old_rc = os.environ.get("SOAPBOXX_V3_REALITY_CHECK")
        try:
            os.environ["SOAPBOXX_V3_REALITY_CHECK"] = "1"
            os.environ["SOAPBOXX_WORKFLOW_USE_AI"] = "0"
            wf = soapboxx_v3_workflow_local(
                transcript,
                meta,
                validate=False,
                strict_references=False,
                report_v3=r3,
                brief_warnings=[],
            )
        finally:
            if old_ai is not None:
                os.environ["SOAPBOXX_WORKFLOW_USE_AI"] = old_ai
            else:
                os.environ.pop("SOAPBOXX_WORKFLOW_USE_AI", None)
            if old_rc is not None:
                os.environ["SOAPBOXX_V3_REALITY_CHECK"] = old_rc
            else:
                os.environ.pop("SOAPBOXX_V3_REALITY_CHECK", None)

        chk = (wf.get("metadata") or {}).get("v3_reality_check") or {}
        self.assertIn("passed", chk)
        self.assertIn("rules_source", chk)
        self.assertTrue(chk.get("passed"), msg=str(chk.get("failures")))


class TestStructureDiagnostics(unittest.TestCase):
    def test_weak_structure_detects_partial_case(self):
        self.assertEqual(_derive_structure_state(1, 0), "WEAK")
        diag = _compute_structure_diagnostics(
            {
                "evidence_map": [
                    {
                        "claim": "Claim with enough words to be grounded here.",
                        "evidence": "Evidence quote long enough to satisfy the grounded evidence threshold.",
                    }
                ],
                "segments": [],
            },
            {"segments": []},
        )
        self.assertEqual(diag["evidence_rows"], 1)
        self.assertEqual(diag["segments"], 0)
        self.assertEqual(diag["structure_state"], "WEAK")

    def test_strong_structure_detects_full_case(self):
        self.assertEqual(_derive_structure_state(2, 1), "STRONG")
        diag = _compute_structure_diagnostics(
            {
                "evidence_map": [
                    {
                        "claim": "First grounded claim with enough content to pass checks.",
                        "evidence": "First supporting evidence quote long enough to count as grounded.",
                    },
                    {
                        "claim": "Second grounded claim with enough content to pass checks.",
                        "evidence": "Second supporting evidence quote long enough to count as grounded.",
                    },
                ],
                "segments": [{"id": "s1"}],
            },
            {"segments": []},
        )
        self.assertEqual(diag["evidence_rows"], 2)
        self.assertEqual(diag["segments"], 1)
        self.assertEqual(diag["structure_state"], "STRONG")

    def test_fail_structure_detects_empty_case(self):
        self.assertEqual(_derive_structure_state(0, 0), "FAIL")
        diag = _compute_structure_diagnostics(
            {"evidence_map": [], "segments": []},
            {"segments": []},
        )
        self.assertEqual(diag["evidence_rows"], 0)
        self.assertEqual(diag["segments"], 0)
        self.assertEqual(diag["structure_state"], "FAIL")


class TestEditorialPassToggle(unittest.TestCase):
    def test_editorial_off_when_env_zero_even_if_model_set(self):
        old_ed = os.environ.get("SOAPBOXX_EDITORIAL_PASS")
        old_m = os.environ.get("SOAPBOXX_OLLAMA_MODEL")
        try:
            os.environ["SOAPBOXX_OLLAMA_MODEL"] = "llama:test"
            os.environ["SOAPBOXX_EDITORIAL_PASS"] = "0"
            self.assertFalse(_editorial_pass_enabled())
        finally:
            if old_ed is not None:
                os.environ["SOAPBOXX_EDITORIAL_PASS"] = old_ed
            else:
                os.environ.pop("SOAPBOXX_EDITORIAL_PASS", None)
            if old_m is not None:
                os.environ["SOAPBOXX_OLLAMA_MODEL"] = old_m
            else:
                os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)

    def test_editorial_on_when_model_set_and_env_unset(self):
        old_ed = os.environ.get("SOAPBOXX_EDITORIAL_PASS")
        old_m = os.environ.get("SOAPBOXX_OLLAMA_MODEL")
        try:
            os.environ.pop("SOAPBOXX_EDITORIAL_PASS", None)
            os.environ["SOAPBOXX_OLLAMA_MODEL"] = "llama:test"
            self.assertTrue(_editorial_pass_enabled())
        finally:
            if old_ed is not None:
                os.environ["SOAPBOXX_EDITORIAL_PASS"] = old_ed
            if old_m is not None:
                os.environ["SOAPBOXX_OLLAMA_MODEL"] = old_m
            else:
                os.environ.pop("SOAPBOXX_OLLAMA_MODEL", None)


if __name__ == "__main__":
    unittest.main()
