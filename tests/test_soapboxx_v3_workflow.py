"""Tests for soapboxx_v3_workflow (validation only; no API)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import soapboxx_v3_workflow as soapboxx_v3_workflow  # noqa: E402

from soapboxx_v3_workflow import (  # noqa: E402
    WORKFLOW_SPEC_VERSION,
    _align_missing_timestamps_with_cues,
    _attach_unified_markdown_export,
    _groq_api_key,
    _llm_available,
    _workflow_llm_backend,
    _workflow_title_for_coach_strategy_guest,
    _booking_oriented_guest_rows,
    _compute_structure_diagnostics,
    _editorial_pass_enabled,
    _derive_structure_state,
    _merge_capitalized_spans,
    _safe_claim_text,
    _should_emit_guest_outreach_targets,
    _topic_specific_guest_fallback,
    generate_guest_archetypes_from_issues,
    should_generate_guests,
    validate_json,
    workflow_guest_rows,
    workflow_report_from_v3_report,
)
from guest_generation_decision import build_guest_decision_trace  # noqa: E402


class TestWorkflowLlmBackendRouting(unittest.TestCase):
    def test_workflow_backend_forced_ollama(self):
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "x",
                "SOAPBOXX_OLLAMA_MODEL": "m",
                "SOAPBOXX_WORKFLOW_LLM_BACKEND": "ollama",
            },
            clear=True,
        ):
            self.assertEqual(_workflow_llm_backend(), "ollama")
            self.assertTrue(_llm_available())


class TestCueTimestampAlignment(unittest.TestCase):
    def test_aligns_missing_timestamps_from_cues(self):
        rows = [
            {
                "id": "c1",
                "claim": "AI change is accelerating quickly.",
                "evidence": "AI change is accelerating quickly and founders need a weekly operating rhythm.",
                "timestamp": None,
            },
            {
                "id": "c2",
                "claim": "Already timestamped row",
                "evidence": "this row should remain untouched",
                "timestamp": 12.4,
            },
        ]
        cues = [
            {
                "timestamp": "00:01:21.900",
                "start_sec": 81.9,
                "text": "AI change is accelerating quickly and founders need a weekly operating rhythm.",
            }
        ]
        n = _align_missing_timestamps_with_cues(rows, cues)
        self.assertEqual(n, 1)
        self.assertEqual(rows[0]["timestamp"], 81.9)
        self.assertEqual(rows[1]["timestamp"], 12.4)

    def test_workflow_backend_defaults_groq_when_key_present(self):
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "test-key",
                "SOAPBOXX_OLLAMA_MODEL": "",
            },
            clear=True,
        ):
            self.assertEqual(_workflow_llm_backend(), "groq")
            self.assertTrue(_llm_available())
            self.assertEqual(_groq_api_key(), "test-key")

    def test_workflow_backend_ollama_without_groq(self):
        with patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "",
                "SOAPBOXX_GROQ_API_KEY": "",
                "SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b",
            },
            clear=True,
        ):
            self.assertEqual(_workflow_llm_backend(), "ollama")
            self.assertTrue(_llm_available())


class TestCoachStrategyGuestTitles(unittest.TestCase):
    def test_known_name_gets_professional_title_not_suggested(self):
        self.assertEqual(
            _workflow_title_for_coach_strategy_guest("Diane Ravitch"),
            "Education policy historian",
        )
        self.assertEqual(
            _workflow_title_for_coach_strategy_guest("Jonathan Kozol"),
            "Author & public education advocate",
        )

    def test_unknown_full_name_gets_booking_target_label(self):
        self.assertEqual(
            _workflow_title_for_coach_strategy_guest("Alex Morgan"),
            "Expert guest (booking target)",
        )


class TestCallLlmJsonEnvelope(unittest.TestCase):
    def test_requires_non_empty_data_without_text_fallback(self):
        with patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "0"}, clear=False):
            with patch.object(
                soapboxx_v3_workflow,
                "call_llm_with_retry",
                return_value={"text": '{"k": true}', "data": {}},
            ):
                with self.assertRaises(ValueError) as ctx:
                    soapboxx_v3_workflow.call_llm_json("prompt", client=None)
                self.assertIn("non-empty", str(ctx.exception))

    def test_parses_text_when_fallback_enabled(self):
        with patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "1"}, clear=False):
            with patch.object(
                soapboxx_v3_workflow,
                "call_llm_with_retry",
                return_value={"text": '{"k": true}', "data": {}},
            ):
                r = soapboxx_v3_workflow.call_llm_json("prompt", client=None)
                self.assertTrue(r.get("k"))

    def test_strict_mode_prefers_data_over_text(self):
        with patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "0"}, clear=False):
            with patch.object(
                soapboxx_v3_workflow,
                "call_llm_with_retry",
                return_value={
                    "text": '{"wrong": true}',
                    "data": {"right": 1, "highlights": []},
                },
            ):
                r = soapboxx_v3_workflow.call_llm_json("prompt", client=None)
                self.assertEqual(r.get("right"), 1)
                self.assertIsNone(r.get("wrong"))

    def test_legacy_mode_raises_when_data_and_text_both_empty(self):
        with patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "1"}, clear=False):
            with patch.object(
                soapboxx_v3_workflow,
                "call_llm_with_retry",
                return_value={"text": "", "data": {}},
            ):
                with self.assertRaises(ValueError) as ctx:
                    soapboxx_v3_workflow.call_llm_json("prompt", client=None)
                self.assertIn("nothing to parse", str(ctx.exception))

    def test_validate_workflow_data_rejects_unknown_keys_only(self):
        with patch.dict(
            os.environ,
            {
                "SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "0",
                "SOAPBOXX_LLM_VALIDATE_WORKFLOW_DATA": "1",
            },
            clear=False,
        ):
            with patch.object(
                soapboxx_v3_workflow,
                "call_llm_with_retry",
                return_value={"text": "", "data": {"not_a_workflow_key": 1}},
            ):
                with self.assertRaises(ValueError) as ctx:
                    soapboxx_v3_workflow.call_llm_json("prompt", client=None)
                self.assertIn("recognized keys", str(ctx.exception))


class TestWorkflowGuestRowsFilter(unittest.TestCase):
    def test_workflow_guest_rows_strips_episode_grounded_person(self):
        wf = {
            "guests": [
                {
                    "name": "Jesse James",
                    "title": "Named in this episode (verbatim text)",
                    "source": "episode_grounded_person",
                    "claim_id": "c1",
                    "relevance": 10,
                }
            ]
        }
        rows = workflow_guest_rows(wf)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("source"), "expert_placeholder_after_verbatim_filter")
        self.assertNotIn("jesse", str(rows[0].get("name", "")).lower())

    def test_booking_oriented_keeps_atomic_pipeline_rows(self):
        rows = _booking_oriented_guest_rows(
            [
                {
                    "name": "Historian — Topic",
                    "source": "atomic_pipeline",
                    "claim_id": "a1",
                }
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].get("source"), "atomic_pipeline")


class TestWorkflowGuestAlias(unittest.TestCase):
    def test_workflow_guest_rows_self_heals_when_lists_diverge(self):
        """Rogue reassignment of one key: getter re-binds both to one list (canonical wins if non-empty)."""
        wf = {
            "guests": [{"name": "Canonical"}],
            "guest_recommendations": [{"name": "Legacy"}],
        }
        rows = workflow_guest_rows(wf)
        self.assertEqual(rows[0]["name"], "Canonical")
        self.assertIs(wf["guests"], wf["guest_recommendations"])

    def test_workflow_guest_rows_prefers_legacy_when_canonical_empty(self):
        wf = {
            "guests": [],
            "guest_recommendations": [{"name": "OnlyLegacy"}],
        }
        rows = workflow_guest_rows(wf)
        self.assertEqual(rows[0]["name"], "OnlyLegacy")
        self.assertIs(wf["guests"], wf["guest_recommendations"])


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
        gr = workflow_guest_rows(wf)
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

    def test_workflow_analytics_drops_crime_storyline_when_title_signals_education(self):
        r3 = {
            "episode_snapshot": {
                "title": "Brainwash Rockefeller School Psyop Special",
                "creator": "H",
                "genre": "Entertainment",
                "primary_topic": "Criminal enterprise, law enforcement, and accountability",
                "why_it_matters": "Listeners want clarity.",
            },
            "claims": [
                {
                    "id": "a1",
                    "text": "School boards adopted vendor-driven testing regimes under visible federal pressure over a decade.",
                }
            ],
            "clean_insights": [],
            "evidence_mapping": [],
            "engagement_questions": {},
            "segments": [{"segment_title": "Open"}],
            "analytics_actionable": {
                "what_worked": [
                    "Criminal enterprise, law enforcement, and accountability",
                    "A distinct line about vendor incentives in school procurement is visible on the tape.",
                ],
                "what_failed": [],
                "next_move": ["Cut one tangent per episode"],
            },
        }
        wf = workflow_report_from_v3_report(r3)
        sl = wf.get("analytics", {}).get("storylines") or []
        joined = " ".join(str(x).lower() for x in sl)
        self.assertNotIn("criminal enterprise", joined)
        self.assertTrue(
            "vendor" in joined or "school" in joined or "through-line" in joined,
            msg=joined,
        )

    def test_workflow_guests_passthrough_atomic_envelope_when_v3_guests_empty(self):
        """Atomic SSOT must reach workflow even if v3 ``guests`` list is empty (mapping drift)."""
        r3 = {
            "clean_insights": [],
            "evidence_mapping": [],
            "engagement_questions": {},
            "claims": [{"id": "a1", "text": "Federal policy shaped removal timelines in 1877."}],
            "guests": [],
            "segments": [],
            "coach_report": {},
            "episode_snapshot": {"title": "History test"},
            "analytics_actionable": {},
            "atomic_pipeline": {
                "claims": [
                    {"id": "a1", "raw_statement": "Federal policy shaped removal timelines in 1877."}
                ],
                "topic_graph": {
                    "nodes": [
                        {
                            "topic_id": "t1",
                            "label": "Federal Removal Policy",
                            "evidence_claim_ids": ["a1"],
                            "category": "history",
                            "weight": 0.75,
                        }
                    ],
                    "edges": [],
                },
                "guest_recommendations": [
                    {
                        "guest_type": "historian",
                        "target_topic_id": "t1",
                        "relevance_score": 0.82,
                        "recommendation_reason": {
                            "primary_angle": "Primary source framing for policy cluster.",
                            "what_they_would_challenge": "",
                        },
                        "ideal_questions": [],
                    }
                ],
            },
        }
        wf = workflow_report_from_v3_report(r3)
        gr = workflow_guest_rows(wf)
        self.assertGreaterEqual(len(gr), 1)
        self.assertEqual(gr[0].get("source"), "atomic_pipeline")
        nm = str(gr[0].get("name") or "")
        self.assertTrue(
            any(x in nm for x in ("Jill", "David", "Pekka", "Tom", "Bradford", "Paul", "Anne", "Michael")),
            msg=nm,
        )
        self.assertNotIn("Historian —", nm)
        self.assertEqual(str(gr[0].get("claim_id") or ""), "a1")

    def test_workflow_guests_subject_fallback_when_atomic_envelope_empty(self):
        """When atomic graph guests are empty, map claim entities → domain expert archetypes (not tape names)."""
        r3 = {
            "clean_insights": [],
            "evidence_mapping": [],
            "engagement_questions": {},
            "claims": [
                {
                    "id": "c1",
                    "text": "Robert Wright and Billy discussed Jesse Evans with Jim Miller.",
                }
            ],
            "guests": [],
            "segments": [],
            "coach_report": {},
            "episode_snapshot": {"title": "Test"},
            "analytics_actionable": {},
            "atomic_pipeline": {
                "claims": [
                    {
                        "id": "c1",
                        "raw_statement": "Robert Wright and Billy discussed Jesse Evans with Jim Miller.",
                    }
                ],
                "topic_graph": {"nodes": [], "edges": []},
                "guest_recommendations": [],
            },
        }
        wf = workflow_report_from_v3_report(r3)
        gr = workflow_guest_rows(wf)
        self.assertGreaterEqual(len(gr), 1)
        self.assertTrue(wf.get("guests_from_subject_fallback"))
        self.assertEqual(gr[0].get("source"), "subject_fallback_tier3")
        names_flat = " ".join(str(g.get("name") or "") for g in gr if isinstance(g, dict))
        self.assertTrue(
            any(x in names_flat for x in ("Tom Clavin", "T.J. Stiles", "Michael Wallis", "Anne F. Hyde")),
            msg=names_flat,
        )
        for bad in ("Robert Wright", "Billy", "Jesse Evans", "Jim Miller"):
            self.assertNotIn(bad, names_flat)
        sig = str(gr[0].get("entity_signals") or "")
        self.assertTrue(sig)  # claim entities inform domain mapping, not guest `name`
        oo = wf.get("guest_outreach_targets") or {}
        self.assertEqual(oo.get("domain_key"), "outlaw_history")
        experts = oo.get("experts") or []
        self.assertTrue(any("Tom Clavin" in str(e.get("name")) for e in experts))
        pods = oo.get("podcasts") or []
        self.assertTrue(any("Legends of the Old West" in str(p.get("name")) for p in pods))

    def test_merge_capitalized_spans_does_not_bridge_over_lowercase(self):
        words = "Robert met Billy at the Jesse Evans office".replace(",", " ").split()
        merged = _merge_capitalized_spans(words)
        self.assertIn("Robert", merged)
        self.assertIn("Billy", merged)
        self.assertIn("Jesse Evans", merged)
        self.assertNotIn("Robert Billy", merged)

    def test_merge_capitalized_spans_strips_boundary_punctuation(self):
        """Comma-/quote-attached tokens normalize before cap checks (punctuation-heavy transcripts)."""
        words = ['"Robert', "Wright,", "said", "the", "sheriff."]
        merged = _merge_capitalized_spans(words)
        self.assertIn("Robert Wright", merged)
        self.assertNotIn("Wright", merged)

    def test_outreach_trigger_loose_tier3_source_and_fallback_flag(self):
        """Outreach attaches if ``guests_from_subject_fallback`` or ``tier3`` appears in source."""
        self.assertTrue(
            _should_emit_guest_outreach_targets(
                [{"source": "SUBJECT_FALLBACK_TIER3", "name": "x"}],
                guests_from_subject_fallback=False,
                claim_rows_for_subjects=[{"id": "c1", "text": "a"}],
            )
        )
        self.assertTrue(
            _should_emit_guest_outreach_targets(
                [{"source": "other", "name": "x"}],
                guests_from_subject_fallback=True,
                claim_rows_for_subjects=[{"id": "c1", "text": "a"}],
            )
        )
        self.assertFalse(
            _should_emit_guest_outreach_targets(
                [{"source": "atomic_pipeline", "name": "x"}],
                guests_from_subject_fallback=False,
                claim_rows_for_subjects=[{"id": "c1", "text": "a"}],
            )
        )

    def test_safe_claim_text_dict_and_nested(self):
        self.assertEqual(_safe_claim_text("plain"), "plain")
        self.assertEqual(_safe_claim_text({"text": "A", "raw_statement": "B"}), "A")
        nested = {"text": {"raw_statement": "Robert Wright discussed the matter."}}
        self.assertIn("Robert Wright", _safe_claim_text(nested))
        t = _safe_claim_text(nested)
        self.assertIsInstance(t.replace(",", " ").split(), list)

    def test_workflow_guests_subject_fallback_without_atomic_pipeline(self):
        """Subject fallback must run when ``atomic_pipeline`` is absent (not only inside atomic branch)."""
        r3 = {
            "clean_insights": [],
            "evidence_mapping": [],
            "engagement_questions": {},
            "claims": [{"id": "c1", "text": "Robert Wright discussed the case with Jim Miller."}],
            "guests": [],
            "segments": [],
            "coach_report": {},
            "episode_snapshot": {"title": "Test"},
            "analytics_actionable": {},
        }
        wf = workflow_report_from_v3_report(r3)
        gr = workflow_guest_rows(wf)
        self.assertGreaterEqual(len(gr), 1)
        self.assertTrue(wf.get("guests_from_subject_fallback"))
        self.assertEqual(gr[0].get("source"), "subject_fallback_tier3")
        nm0 = str(gr[0].get("name") or "")
        self.assertTrue(any(x in nm0 for x in ("Tom Clavin", "T.J. Stiles", "Michael Wallis", "Anne F. Hyde")), msg=nm0)

    def test_subject_fallback_uses_evidence_mapping_when_top_level_claims_empty(self):
        """UI may show evidence rows while ``claims`` is empty — guests must still extract entities."""
        r3 = {
            "clean_insights": [],
            "claims": [],
            "evidence_mapping": [
                {
                    "id": "c1",
                    "claim": "Robert Wright and Jim Miller discussed the filing.",
                    "evidence": "quote",
                    "timestamp": None,
                    "type": "other",
                    "strength": 7,
                }
            ],
            "engagement_questions": {},
            "guests": [],
            "segments": [],
            "coach_report": {},
            "episode_snapshot": {"title": "Test"},
            "analytics_actionable": {},
        }
        wf = workflow_report_from_v3_report(r3)
        gr = workflow_guest_rows(wf)
        self.assertGreaterEqual(len(gr), 1)
        self.assertTrue(wf.get("guests_from_subject_fallback"))
        self.assertEqual(gr[0].get("source"), "subject_fallback_tier3")
        names_flat = " ".join(str(g.get("name") or "") for g in gr if isinstance(g, dict))
        self.assertTrue(
            any(x in names_flat for x in ("Tom Clavin", "T.J. Stiles", "Michael Wallis", "Anne F. Hyde")),
            msg=names_flat,
        )

    def test_workflow_guests_nested_claim_text_does_not_crash(self):
        """Structured or nested ``text`` fields must not break ``.replace`` / extraction."""
        r3 = {
            "clean_insights": [],
            "evidence_mapping": [],
            "engagement_questions": {},
            "claims": [
                {
                    "id": "c1",
                    "text": {"raw_statement": "Robert Wright and Jim Miller met about the case."},
                }
            ],
            "guests": [],
            "segments": [],
            "coach_report": {},
            "episode_snapshot": {"title": "Test"},
            "analytics_actionable": {},
        }
        wf = workflow_report_from_v3_report(r3)
        gr = workflow_guest_rows(wf)
        self.assertGreaterEqual(len(gr), 1)
        self.assertTrue(wf.get("guests_from_subject_fallback"))
        self.assertEqual(gr[0].get("source"), "subject_fallback_tier3")
        names_flat = " ".join(str(g.get("name") or "") for g in gr if isinstance(g, dict))
        self.assertTrue(
            any(x in names_flat for x in ("Tom Clavin", "T.J. Stiles", "Michael Wallis", "Anne F. Hyde")),
            msg=names_flat,
        )


class TestV3RealityChecksInWorkflow(unittest.TestCase):
    def test_metadata_contains_v3_reality_check(self):
        import episode_report_v3 as v3
        from soapboxx_v3_workflow import soapboxx_v3_workflow_local

        old_gt = os.environ.get("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH")
        os.environ["SOAPBOXX_V3_ATOMIC_GROUND_TRUTH"] = "0"
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
        try:
            r3 = v3.build_v3_report(brief, transcript, metadata={}, atomic_ground_truth=False)
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
        finally:
            if old_gt is None:
                os.environ.pop("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH", None)
            else:
                os.environ["SOAPBOXX_V3_ATOMIC_GROUND_TRUTH"] = old_gt

        chk = (wf.get("metadata") or {}).get("v3_reality_check") or {}
        self.assertIn("passed", chk)
        self.assertIn("rules_source", chk)
        self.assertIn("report_v3_output_mode", chk)
        self.assertIn("diagnostic_reasons", chk)
        self.assertIn("good_clean_insight_lines", chk)
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


class TestAttachUnifiedMarkdownExport(unittest.TestCase):
    def test_diagnostic_mode_uses_coach_markdown_not_empty_bundle_v3(self):
        """Regression: bundle has no markdown_v3; diagnostic must still emit markdown_export."""
        r3 = {
            "episode_snapshot": {
                "title": "Brainwash!",
                "creator": "Julian Dorey",
                "genre": "Education",
                "primary_topic": "School systems",
            },
            "output_mode": "diagnostic",
            "report_readiness": {"output_mode": "diagnostic"},
        }
        report: dict = {"metadata": {"title": "Brainwash!"}, "highlights": [], "evidence_map": []}
        with patch.dict(os.environ, {"SOAPBOXX_MODE": "truth"}, clear=False):
            with patch("episode_progress.prepare_bundle_for_export", lambda bundle: None):
                with patch(
                    "episode_progress.attach_export_telemetry_to_metadata",
                    lambda meta, bundle: None,
                ):
                    with patch(
                        "episode_progress.persist_episode_progress_after_export",
                        lambda bundle: None,
                    ):
                        with patch(
                            "episode_report_v3.render_episode_report_v3_markdown",
                            return_value="# Coach-only export\n",
                        ) as coach:
                            with patch(
                                "episode_report_v3.render_unified_episode_export_markdown"
                            ) as unified:
                                _attach_unified_markdown_export(
                                    report,
                                    r3,
                                    {
                                        "title": "Brainwash!",
                                        "creator": "Julian Dorey",
                                        "genre": "Education",
                                    },
                                )
            unified.assert_not_called()
            coach.assert_called_once()
            self.assertEqual(report["markdown_export"], "# Coach-only export\n")


if __name__ == "__main__":
    unittest.main()
