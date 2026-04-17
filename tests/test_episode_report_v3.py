"""Tests for episode report v3 (no API calls for pure functions)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_report_v3 as v3  # noqa: E402


class TestEpisodeReportV3(unittest.TestCase):
    """Brief-fixture tests use legacy brief claims; isolate env from other modules (e.g. reality golden)."""

    @classmethod
    def setUpClass(cls):
        cls._saved_atomic_gt = os.environ.get("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH")
        os.environ["SOAPBOXX_V3_ATOMIC_GROUND_TRUTH"] = "0"

    @classmethod
    def tearDownClass(cls):
        if cls._saved_atomic_gt is None:
            os.environ.pop("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH", None)
        else:
            os.environ["SOAPBOXX_V3_ATOMIC_GROUND_TRUTH"] = cls._saved_atomic_gt

    def test_apply_identity_consistency_resets_off_topic_thesis(self):
        report = {
            "meta": {"title": "Nez Perce War"},
            "episode_snapshot": {
                "title": "Chief Joseph & the Nez Perce War",
                "primary_topic": "Nez Perce resistance and forced relocation",
                "genre": "History",
            },
            "narrative_reconstruction": {
                "core_thesis": "Agricultural commodity futures and crop insurance reshape rural economies.",
            },
            "coach_report": {
                "episode_thesis": "Agricultural commodity futures and crop insurance reshape rural economies.",
            },
            "clean_insights": [],
        }
        out = v3.apply_identity_consistency_to_report_v3(report)
        self.assertTrue(out.get("_consistency_fix_applied"))
        self.assertIn("Nez", str(out["narrative_reconstruction"]["core_thesis"]))
        self.assertIn("Nez", str(out["coach_report"]["episode_thesis"]))
        self.assertIsInstance(out.get("_consistency_drift_notes"), list)

    def test_compressed_action_bullets_fallback_when_no_derived_signal(self):
        out = v3.compressed_action_bullets({"report_v3": {}}, {})
        self.assertEqual(len(out), 1)
        self.assertIn("No actionable steps could be derived", out[0])
        self.assertIn("next episode", out[0])

    def test_compressed_export_includes_if_you_had_to_act_anyway(self):
        """Compressed tier adds practical bullets from existing signal only (no new inference)."""
        old_c = os.environ.get("SOAPBOXX_EXPORT_COMPRESSION")
        old_s = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_EXPORT_COMPRESSION"] = "1"
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "1"
            r3 = {
                "episode_snapshot": {"title": "Action test"},
                "signal_mode": "LOW_SIGNAL",
                "report_readiness": {"metrics": {"transcript_word_count": 200}},
                "segments": [{"segment_title": "Open"}],
                "evidence_mapping": [
                    {
                        "claim": "First grounded claim line is long enough for export checks.",
                        "evidence": "First evidence quote from the transcript is long enough here.",
                    },
                    {
                        "claim": "Second grounded claim line is long enough for export checks.",
                        "evidence": "Second evidence quote from the transcript is long enough here.",
                    },
                ],
                "coach_report": {
                    "episode_thesis": "One clear thesis the episode keeps circling.",
                },
            }
            md = v3.render_unified_episode_export_markdown({"report_v3": r3})
            self.assertIn("If You Had to Act Anyway", md)
            self.assertIn("Rebuild the open", md)
        finally:
            if old_c is None:
                os.environ.pop("SOAPBOXX_EXPORT_COMPRESSION", None)
            else:
                os.environ["SOAPBOXX_EXPORT_COMPRESSION"] = old_c
            if old_s is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old_s

    def test_export_structural_tier_compresses_on_low_signal(self):
        old = os.environ.get("SOAPBOXX_EXPORT_COMPRESSION")
        try:
            os.environ["SOAPBOXX_EXPORT_COMPRESSION"] = "1"
            b = {
                "report_v3": {
                    "signal_mode": "LOW_SIGNAL",
                    "report_readiness": {"metrics": {"transcript_word_count": 2000}},
                    "evidence_mapping": [
                        {
                            "claim": "A long enough grounded claim line for the gate.",
                            "evidence": "A long enough evidence quote from the transcript here.",
                        },
                        {
                            "claim": "Second grounded claim line that passes length checks.",
                            "evidence": "Second evidence quote from the transcript passes checks.",
                        },
                    ],
                }
            }
            self.assertEqual(v3.export_structural_tier(b), "compressed")
            b2 = dict(b)
            b2["report_v3"] = {
                **b["report_v3"],
                "signal_mode": "HIGH_SIGNAL",
                "evidence_mapping": b["report_v3"]["evidence_mapping"]
                + [
                    {
                        "claim": "Third grounded claim line for density.",
                        "evidence": "Third evidence quote from the transcript passes checks.",
                    }
                ],
            }
            self.assertEqual(v3.export_structural_tier(b2), "full")
        finally:
            if old is None:
                os.environ.pop("SOAPBOXX_EXPORT_COMPRESSION", None)
            else:
                os.environ["SOAPBOXX_EXPORT_COMPRESSION"] = old

    def test_blueprint_strategist_does_not_bypass_truth_gate(self):
        old = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "1"
            r3 = {"episode_snapshot": {"title": "Thin"}, "evidence_mapping": [], "segments": []}
            bp = {
                "strategist_report": {
                    "punchline_header": "Would ship if gate were ignored.",
                    "snapshot": {"overall_score": 9, "signal_strength": "High", "diagnosis": "x"},
                }
            }
            md = v3.render_unified_episode_export_markdown(
                {"report_v3": r3, "blueprint_v1": bp, "workflow_report": {}, "meta": {}}
            )
            self.assertIn("insufficient signal", md.lower())
            self.assertIn("Master Blueprint", md)
        finally:
            if old is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old

    def test_strategist_truth_gate_unified_counts_workflow_and_report_v3(self):
        """Single gate: max(workflow, report_v3) for evidence rows and segments."""
        old = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "1"
            thin = {"report_v3": {"evidence_mapping": [], "segments": []}, "workflow_report": {}}
            ins, rs = v3.strategist_truth_gate_bundle(thin)
            self.assertTrue(ins)
            self.assertTrue(any("evidence rows 0" in x for x in rs))
            row = {
                "claim": "A long enough claim line here for the gate.",
                "evidence": "A long enough evidence quote from the transcript here.",
            }
            ok_wf = {
                "workflow_report": {
                    "evidence_map": [row, dict(row)],
                    "segments": [{"segment_id": "s1"}],
                },
                "report_v3": {"evidence_mapping": [], "segments": []},
            }
            self.assertFalse(v3.strategist_truth_gate_bundle(ok_wf)[0])
        finally:
            if old is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old

    def test_detect_signal_mode_two_claims_high(self):
        brief = {
            "claims": [
                {
                    "id": "c1",
                    "text": "Systems outperform goals because routines persist when motivation drops.",
                    "confidence": "medium",
                },
                {
                    "id": "c2",
                    "text": "Removing friction for positive actions increases consistency across weeks.",
                    "confidence": "medium",
                },
            ]
        }
        self.assertEqual(v3.detect_signal_mode(brief), "HIGH_SIGNAL")

    def test_detect_signal_mode_two_thin_claims_low(self):
        brief = {
            "claims": [
                {"id": "c1", "text": "Productivity has many factors.", "confidence": "medium"},
                {"id": "c2", "text": "Burnout is also relevant.", "confidence": "medium"},
            ]
        }
        self.assertEqual(v3.detect_signal_mode(brief), "LOW_SIGNAL")

    def test_clean_key_highlights_dedupes(self):
        raw = [
            "The speaker argues that money corrupts some ministries.",
            "The speaker says that money corrupts some ministries.",
            "The speaker argues that money corrupts some ministries.",
        ]
        out = v3.clean_key_highlights(raw)
        self.assertLessEqual(len(out), 2)
        self.assertTrue(all(len(x.split()) <= 28 for x in out))

    def test_low_signal_fragment_truncated_mid_clause(self):
        self.assertTrue(
            v3._is_low_signal_fragment(
                "What it is that I'm talking about here, just around four or five months ago, at."
            )
        )

    def test_clean_key_highlights_drops_transcript_junk(self):
        raw = [
            "Oh, Oh, Oh, the whole world to me.",
            "Forward to talking to you in about 3 minutes.",
            "Making love that we don't even feel.",
            "Police accountability requires clear rules and independent oversight when force is used.",
        ]
        out = v3.clean_key_highlights(raw)
        self.assertEqual(len(out), 1)
        self.assertIn("Police accountability", out[0])

    def test_is_low_signal_insight_line(self):
        self.assertTrue(v3.is_low_signal_insight_line("Oh, Oh, Oh, the whole world to me."))
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "Transcript length ~7047 words."
            )
        )
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "Run with API key for claim mapping and production moves."
            )
        )
        self.assertFalse(
            v3.is_low_signal_insight_line(
                "Independent oversight matters when institutions face public trust tests."
            )
        )

    def test_remove_semantic_duplicates(self):
        items = ["duplicate claim", "duplicate claim", "unique claim"]
        out = v3.remove_semantic_duplicates(items, threshold=0.95)
        self.assertEqual(len(out), 2)

    def test_validate_references_bad_id(self):
        ok, errs = v3.validate_references(
            {"claims": [{"id": "c1"}], "body": "Listener Q&A [c17]"},
            valid_claim_ids={"c1"},
        )
        self.assertFalse(ok)
        self.assertTrue(any("c17" in e for e in errs))

    def test_validate_references_ok(self):
        ok, errs = v3.validate_references(
            {
                "claims": [{"id": "c1"}],
                "engagement_questions": {"c1": {"counterpunch": "x"}},
            },
            valid_claim_ids={"c1"},
        )
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_generate_engagement_questions_triad(self):
        q = v3.generate_engagement_questions(
            {"text": "Ministry should be transparent about money."}
        )
        self.assertIn("counterpunch", q)
        self.assertIn("validation", q)
        self.assertIn("application", q)

    def test_map_guest_to_claim(self):
        g = v3.map_guest_to_claim(
            {"name": "N.T. Wright", "title": "Scholar", "angle": ""},
            {"id": "c1", "text": "Money and ministry need accountability."},
        )
        self.assertEqual(g["guest"], "N.T. Wright")
        self.assertIn("Money and ministry", g["target_claim"])

    def test_build_v3_report_offline_brief(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "p",
                "why_it_matters": "w",
            },
            "narrative": ["First line of story.", "First line of story."],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "s", "goal": "g"},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        r = v3.build_v3_report(brief, "some transcript about money and church", metadata={})
        v3.validate_v3_report_or_raise(r)
        self.assertIn("report_readiness", r)
        self.assertIn("band", r["report_readiness"])
        self.assertIn("dual_lens", r)
        self.assertIn(r["dual_lens"]["episode_lens_type"], ("NARRATIVE", "ANALYTICAL", "HYBRID"))
        md = v3.render_episode_report_v3_markdown(r)
        self.assertIn("## 0. Readiness & expectations", md)
        self.assertIn("## 1. Episode Diagnosis", md)
        self.assertIn("## 10. Bottom Line", md)
        self.assertIn("## 11. Dual lens", md)
        self.assertEqual(r.get("signal_mode"), "LOW_SIGNAL")
        self.assertEqual(r.get("output_mode"), "diagnostic")
        self.assertEqual(r.get("report_readiness", {}).get("output_mode"), "diagnostic")
        self.assertIn("coach_report", r)
        self.assertIn("narrative_reconstruction", r)
        self.assertTrue(r.get("takeaway"))
        self.assertIn("Diagnostic mode", r.get("takeaway", ""))
        gt = r.get("_guest_decision_trace") or {}
        self.assertIn("anchor_alignment_score", gt)
        self.assertIn("guest_trigger_source", gt)
        self.assertIn("guest_trigger_source_raw", gt)
        self.assertIn("guest_generation_effective", gt)
        self.assertIn("decision_primary_cause", gt)
        self.assertIn("guest_generation_confidence", gt)
        sp = gt.get("anchor_stability_profile") or {}
        self.assertIn("min_jaccard", sp)
        self.assertIn("mean_jaccard", sp)
        self.assertIn("variance_jaccard", sp)
        self.assertIsInstance(gt.get("decision_steps"), list)
        self.assertGreater(len(gt["decision_steps"]), 3)
        self.assertEqual(gt["decision_steps"][0], "EVAL_ISSUE_AXIS")
        cq = r.get("_claim_quality") or {}
        self.assertIn("score", cq)
        self.assertIn("warning", cq)
        self.assertEqual(r.get("_system_health_label"), "CLAIM_DEGRADED")
        inv = r.get("_invariant_contract_check") or {}
        self.assertIn("violations", inv)
        self.assertFalse(inv.get("contract_satisfied"))
        codes = {v.get("code") for v in (inv.get("violations") or [])}
        self.assertIn("CLAIM_SET_EMPTY", codes)

    def test_atomic_ground_truth_ignores_brief_claims_and_attaches_envelope(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "p",
                "why_it_matters": "w",
            },
            "narrative": [],
            "claims": [
                {
                    "id": "c1",
                    "text": "Brief-only claim that must not appear when atomic ground truth is on.",
                    "claim_type": "interpretation",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "s", "goal": "g"},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        transcript = (
            "[12.0s] In 1877 federal policy forced removal of the Nez Perce from their homeland. "
            "[20.0s] Military campaigns targeted the band during that removal."
        )
        r = v3.build_v3_report(brief, transcript, metadata={}, atomic_ground_truth=True)
        self.assertEqual(r.get("meta", {}).get("structured_intelligence_source"), "atomic_pipeline")
        self.assertIsInstance(r.get("atomic_pipeline"), dict)
        claim_ids = [str(c.get("id")) for c in (r.get("claims") or []) if isinstance(c, dict)]
        self.assertNotIn("c1", claim_ids)
        self.assertTrue(any(cid.startswith("a") for cid in claim_ids), msg=claim_ids)

    def test_narrative_reconstruction_skips_offline_tooling_bullets(self):
        brief = {
            "episode_snapshot": {
                "title": "News hour",
                "creator": "Host",
                "genre": "News & Politics",
                "primary_topic": "Ottawa police",
                "why_it_matters": "w",
            },
            "narrative": [
                "Transcript length ~7047 words.",
                "Run with API key for claim mapping and production moves.",
            ],
            "claims": [
                {
                    "id": "c1",
                    "text": "Law enforcement actions against public figures raise accountability questions.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "m",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "S", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        r = v3.build_v3_report(
            brief,
            "Police moved to detain a former official amid questions about evidence and timing.",
            metadata={},
        )
        n = r.get("narrative_reconstruction") or {}
        self.assertNotIn("Transcript length", str(n.get("core_thesis", "")))
        self.assertNotIn("API key", str(n.get("supporting_mechanism", "")))
        for h in r.get("clean_insights") or []:
            self.assertNotIn("Transcript length", h)
            self.assertNotIn("API key", h)

    def test_forced_narrative_reconstruction_when_missing(self):
        brief = {
            "episode_snapshot": {
                "title": "Habits",
                "creator": "Host",
                "genre": "Talk",
                "primary_topic": "habits",
                "why_it_matters": "w",
            },
            "narrative": ["No clear narrative detected"],
            "claims": [
                {
                    "id": "c1",
                    "text": "Environmental design beats motivation for consistent habits.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "m",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "S", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        r = v3.build_v3_report(brief, "Systems and environment change behavior more than motivation.")
        n = r.get("narrative_reconstruction") or {}
        self.assertIn("core_thesis", n)
        self.assertTrue(n.get("core_thesis"))
        self.assertIn("supporting_mechanism", n)
        self.assertIn("practical_translation", n)

    def test_evidence_mapping_has_function_and_usage(self):
        claims = [{"id": "c1", "text": "Preparation reduces failure rates.", "claim_type": "fact"}]
        rows = v3.build_evidence_mapping(claims, "[10.5s] Preparation reduces failure rates in recurring workflows.")
        self.assertTrue(rows)
        self.assertIn("function", rows[0])
        self.assertIn("usage", rows[0])

    def test_evidence_mapping_prefers_distinct_snippets(self):
        claims = [
            {"id": "c1", "text": "Preparation reduces failures because teams rehearse execution.", "claim_type": "fact"},
            {"id": "c2", "text": "Chaos breaks plans when social pressure rewards shortcuts.", "claim_type": "interpretation"},
        ]
        transcript = (
            "[10.0s] Preparation reduces failures because teams rehearse execution before launch.\n"
            "[28.0s] Plans fail in chaos when social pressure rewards shortcuts over process."
        )
        rows = v3.build_evidence_mapping(claims, transcript)
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["evidence"], rows[1]["evidence"])
        self.assertLessEqual(len(rows[0]["evidence"].split()), 25)
        self.assertLessEqual(len(rows[1]["evidence"].split()), 25)
        self.assertIn("confidence", rows[0])
        self.assertIn("source_type", rows[0])

    def test_strategy_layer_and_takeaway(self):
        strategies = v3.inject_strategy_layer(["Preparation reduces failure rates."])
        self.assertEqual(len(strategies), 1)
        self.assertIn("application", strategies[0])
        self.assertIn("content_angle", strategies[0])
        takeaway = v3.generate_takeaway({"core_thesis": "You do not rise to goals you fall to systems that you actually run."})
        self.assertLessEqual(len(takeaway.split()), 15)

    def test_tension_questions_are_claim_specific(self):
        claims = [
            {"id": "c1", "text": "Remove friction for positive actions to make routines consistent."}
        ]
        q = v3.generate_questions(claims, mode="tension")["c1"]
        val = (q.get("validation") or "").lower()
        self.assertIn("remove friction", val)
        self.assertIn("positive actions", val)
        self.assertNotIn("'ai about replacing", val)

    def test_parse_timestamp_bracket_hms_strips_cleanly(self):
        ts, rest = v3._parse_timestamp_line("[00:02:00] Let me share three practical steps.")
        self.assertEqual(ts, 120.0)
        self.assertTrue(rest.startswith("Let me share"))
        self.assertNotIn(":02:00]", rest)

    def test_evidence_prefers_lines_with_distinctive_terms(self):
        """Costs/learning-curve claim must not anchor to a generic 'tech giants' line."""
        claims = [
            {
                "id": "c1",
                "text": "Business leaders often misunderstand the costs and learning curves associated with AI.",
                "claim_type": "interpretation",
            },
        ]
        transcript = (
            "[00:01:00] Here's what I think many business leaders are missing: AI isn't just for tech giants anymore.\n"
            "[00:02:30] Are you worried about the cost, the learning curve, or something else entirely?"
        )
        rows = v3.build_evidence_mapping(claims, transcript)
        self.assertEqual(len(rows), 1)
        ev = rows[0]["evidence"].lower()
        self.assertIn("cost", ev)
        self.assertIn("learning curve", ev)
        self.assertNotIn("tech giants", ev)

    def test_clean_evidence_snippet_no_trailing_ellipsis(self):
        long = " ".join(["word"] * 40)
        s = v3._clean_evidence_snippet(long, max_words=25)
        self.assertFalse(s.endswith("..."))
        self.assertFalse(s.endswith("…"))

    def test_golden_e2e_report_quality_assertions(self):
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
                "Test one routine change next week.",
            ],
            "claims": [
                {"id": "c1", "text": "Systems beat goals when motivation drops.", "claim_type": "interpretation", "confidence": "medium", "why_it_matters": "m"},
                {"id": "c2", "text": "Habits survive low motivation because routines automate behavior.", "claim_type": "interpretation", "confidence": "high", "why_it_matters": "m"},
                {"id": "c3", "text": "Remove friction for good actions and add friction for bad ones.", "claim_type": "interpretation", "confidence": "high", "why_it_matters": "m"},
                {"id": "c4", "text": "Systems break in chaotic environments with adverse social pressure.", "claim_type": "interpretation", "confidence": "medium", "why_it_matters": "m"},
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "s", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        transcript = (
            "Host: Systems beat goals when motivation drops. "
            "Guest: Habits survive low motivation because routines automate behavior. "
            "Host: What should listeners do tomorrow? "
            "Guest: Remove friction for good actions and add friction for bad ones. "
            "Host: Where does this break? "
            "Guest: It breaks in chaotic environments where social pressure rewards old behavior."
        )
        r = v3.build_v3_report(brief, transcript, metadata={})
        self.assertEqual(r.get("output_mode"), "full")

        evidence = r.get("evidence_mapping") or []
        self.assertGreaterEqual(len(evidence), 3)
        snippets = [str(e.get("evidence") or "") for e in evidence]
        self.assertEqual(len(snippets), len(set(snippets)))
        self.assertTrue(all(len(s.split()) <= 25 for s in snippets))
        self.assertTrue(
            all(float(e.get("confidence") or 0.0) >= v3.MIN_EVIDENCE_CONFIDENCE for e in evidence)
        )

        questions = r.get("engagement_questions") or {}
        self.assertTrue(questions)
        generic = {
            "What would a domain expert disagree with in this claim?",
            "What evidence would confirm or disprove this in real use?",
            "What should someone change tomorrow if they accept this claim?",
        }
        all_q = []
        for _, tri in questions.items():
            all_q.extend([str(tri.get("counterpunch") or ""), str(tri.get("validation") or ""), str(tri.get("application") or "")])
        self.assertTrue(all(q not in generic for q in all_q))

    def test_merge_workflow_followups_into_engagement(self):
        r3 = {
            "engagement_questions": {
                "c1": {
                    "counterpunch": "old counter",
                    "validation": "old val",
                    "application": "old app",
                }
            }
        }
        wf = {
            "follow_up_questions": [
                {"claim_id": "c1", "question_type": "counter", "question": "new counter sharp"},
                {"claim_id": "c1", "question_type": "validation", "question": "new val sharp"},
                {"claim_id": "c1", "question_type": "application", "question": "new app sharp"},
            ]
        }
        v3.merge_workflow_followups_into_engagement(r3, wf)
        tri = r3["engagement_questions"]["c1"]
        self.assertEqual(tri["counterpunch"], "new counter sharp")
        self.assertEqual(tri["validation"], "new val sharp")
        self.assertEqual(tri["application"], "new app sharp")

    def test_dedupe_repeated_sentences(self):
        raw = "Hello. Hello. Hello. Next sentence."
        self.assertEqual(
            v3._dedupe_repeated_sentences(raw),
            "Hello. Next sentence.",
        )

    def test_atmospheric_intro_not_a_highlight(self):
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "The kind that waits for you in the spaces between tasks, in the silence after the lights go out."
            )
        )
        self.assertTrue(v3.is_low_signal_insight_line("Tonight we are going to sit with a man who understood suffering."))
        self.assertFalse(v3._is_broken_evidence_claim_line("Preparation reduces failure rates."))

    def test_polish_thesis_strips_filler_and_one_sentence(self):
        out = v3._polish_thesis_one_sentence(
            "This episode argues that regulation lags markets. Second sentence should drop."
        )
        self.assertTrue(out.endswith("."))
        self.assertNotIn("Second sentence", out)
        self.assertNotIn("This episode argues", out.lower())

    def test_coach_report_has_thesis_uncomfortable_and_compact_stakes(self):
        brief = {
            "episode_snapshot": {
                "title": "Systems vs Goals",
                "creator": "Alex",
                "genre": "Education",
                "primary_topic": "habit systems",
                "why_it_matters": "w",
            },
            "narrative": [
                "Systems outperform goals when motivation is unreliable.",
                "Friction design determines whether routines stick.",
            ],
            "claims": [
                {
                    "id": "c1",
                    "text": "Systems beat goals when motivation drops.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "m",
                },
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "s", "goal": "g"},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        transcript = "[00:00:10] Systems beat goals when motivation drops."
        r = v3.build_v3_report(brief, transcript, metadata={})
        cr = r.get("coach_report") or {}
        self.assertTrue(str(cr.get("episode_thesis") or "").strip())
        self.assertIn("uncomfortable_insight", cr)
        self.assertIn("title", cr.get("uncomfortable_insight") or {})
        self.assertIsInstance(cr.get("claim_stakes"), list)
        self.assertTrue(cr.get("claim_stakes"))
        md = v3.render_episode_report_v3_markdown(r)
        self.assertIn("## 1a.", md)
        self.assertIn("## 1c. Claim stakes", md)
        self.assertIn("For **Alex**", md)
        old_strict = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "0"
            unified = v3.render_unified_episode_export_markdown({"report_v3": r})
        finally:
            if old_strict is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old_strict
        self.assertIn("## Podcast Performance Insight", unified)

    def test_render_unified_export_no_legacy_v2_only_line(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "topic",
                "why_it_matters": "w",
            },
            "narrative": ["Line one.", "Line two."],
            "claims": [
                {
                    "id": "c1",
                    "text": "Systems outperform goals because routines persist.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "m",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "s", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        r = v3.build_v3_report(brief, "[00:00:10] Systems outperform goals because routines persist.")
        old_strict = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "0"
            md = v3.render_unified_episode_export_markdown({"report_v3": r})
        finally:
            if old_strict is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old_strict
        self.assertIn("## Podcast performance & growth intelligence", md)
        self.assertIn("## Snapshot", md)
        self.assertNotIn("only supported", md.lower())
        self.assertNotIn("Readiness & expectations", md)

    def test_render_unified_includes_master_blueprint_v1_section(self):
        brief = {
            "episode_snapshot": {
                "title": "Habits",
                "creator": "Host",
                "genre": "Talk",
                "primary_topic": "habits",
                "why_it_matters": "Listeners tune in for repeatable behavior change.",
            },
            "narrative": ["Systems beat willpower when life gets chaotic."],
            "claims": [
                {
                    "id": "c1",
                    "text": "Environmental design beats motivation for consistent habits.",
                    "claim_type": "interpretation",
                    "confidence": "high",
                    "why_it_matters": "m",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "s", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        r = v3.build_v3_report(
            brief,
            "Host argues that environmental design beats motivation for consistent habits when stress returns.",
            metadata={},
        )
        # Truth gate applies to blueprint exports too (≥2 grounded evidence rows, ≥1 segment).
        em = [e for e in (r.get("evidence_mapping") or []) if isinstance(e, dict)]
        n_ok = sum(1 for e in em if v3.evidence_mapping_row_is_export_grounded(e))
        if n_ok < 2:
            r.setdefault("evidence_mapping", [])
            r["evidence_mapping"] = list(r["evidence_mapping"]) + [
                {
                    "id": "gate_c2",
                    "claim": "Environmental design beats motivation for consistent habits under stress.",
                    "evidence": "Host argues that environmental design beats motivation for consistent habits when stress returns.",
                    "timestamp": 30.0,
                    "type": "spoken_claim",
                }
            ]
        if len(r.get("segments") or []) < 1:
            r["segments"] = [{"segment_title": "Opening beat", "trigger_clip": "c1"}]
        bp = {
            "product_positioning": "A podcast performance and growth intelligence layer",
            "strategist_report": {
                "punchline_header": "This episode underperforms due to weak positioning and lack of clear takeaway, but can be significantly improved with stronger framing, sharper questions, and more structured delivery.",
                "snapshot": {"overall_score": 7, "signal_strength": "Moderate", "diagnosis": "Solid topic, weak tension framing."},
                "core_breakdown": {
                    "thesis": "This episode argues that environmental design beats motivation for consistent habits under stress.",
                    "key_claims": ["Design beats motivation when stress returns."],
                    "evidence_anchors": [
                        {
                            "claim": "Design beats motivation when stress returns.",
                            "anchor": "Host argues that environmental design beats motivation when stress returns.",
                        }
                    ],
                    "tension_position": {
                        "implicit_argument": "This episode treats motivation as the main driver of consistency.",
                        "stronger_position": "But the stronger position is that environment design drives consistency under stress.",
                    },
                },
                "what_working": ["Strong lived examples.", "Clear host cadence.", "Good practical intent."],
                "what_missing": ["Thesis arrives too late.", "Counterargument is underdeveloped.", "Closing takeaway is generic."],
                "upgrade_plan": {
                    "reposition_episode": "This episode should be about designing habit systems that survive stress.",
                    "structure_fix": {
                        "opening_hook": "Lead with a failed willpower moment.",
                        "midpoint_tension": "Challenge the claim with an exception case.",
                        "closing_takeaway": "Commit one environment tweak for seven days.",
                    },
                    "clip_opportunities": ["Design beats motivation when stress returns."],
                },
                "audience_engagement_intelligence": {
                    "listener_takeaway_gap": "Listeners need one specific weekly behavior to test.",
                    "behavior_change": "Pick one trigger-action pair and run it daily.",
                    "weekly_improvement_insight": "Ship one thesis, one tension beat, one takeaway per episode.",
                },
                "question_upgrade": [
                    "What breaks first when motivation drops: intention, environment, or accountability?",
                    "Which behavior can you verify changed because of environment design alone?",
                    "What tradeoff are listeners accepting when they rely on motivation over systems?",
                ],
                "guest_content_opportunities": [
                    {
                        "who_type": "Behavioral scientist",
                        "why_they_matter": "Adds evidence beyond anecdotes.",
                        "what_they_unlock": "More defensible claims and stronger clips.",
                    }
                ],
                "strategic_value_for_network": {
                    "what_improving_unlocks": "Repeatable growth framing and stronger retention.",
                    "where_it_underperforms": "Clip moments are present but under-packaged.",
                },
                "network_level_insight": [
                    "Weak positioning across shows",
                    "Lack of shareable moments",
                    "Structural engagement issues",
                    "High-upside opportunities",
                ],
                "network_rollout_line": "If we applied this across your network, we would identify which shows are underperforming, which episodes are most shareable, and where audience growth is being lost.",
                "one_line_fix": "If this episode were reframed around a clear argument and structured for tension, it would become significantly more engaging and shareable.",
                "conviction_statement": "This episode underperforms because it refuses to take a hard side on systems versus motivation.",
            },
        }
        old_comp = os.environ.get("SOAPBOXX_EXPORT_COMPRESSION")
        try:
            os.environ["SOAPBOXX_EXPORT_COMPRESSION"] = "0"
            md = v3.render_unified_episode_export_markdown(
                {"report_v3": r, "blueprint_v1": bp, "workflow_report": {}, "meta": {}}
            )
        finally:
            if old_comp is None:
                os.environ.pop("SOAPBOXX_EXPORT_COMPRESSION", None)
            else:
                os.environ["SOAPBOXX_EXPORT_COMPRESSION"] = old_comp
        self.assertIn("## Podcast performance & growth intelligence", md)
        self.assertIn("Podcast Performance Insight", md)
        self.assertIn("A podcast performance and growth intelligence layer", md)
        self.assertIn("Design beats motivation when stress returns.", md)
        self.assertIn("Evidence Anchors", md)
        self.assertIn("Tension Call", md)
        self.assertIn("Conviction", md)
        self.assertIn("1-Line Fix", md)

    def test_unified_export_skips_broken_evidence_quote(self):
        r3 = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "",
                "primary_topic": "",
            },
            "report_readiness": {
                "band": "weak",
                "notes": [],
                "suggested_actions": [],
                "metrics": {},
            },
            "evidence_mapping": [
                {
                    "id": "c1",
                    "claim": "A complete spoken claim here.",
                    "evidence": "truncated mid clause at 2 in the.",
                    "timestamp": 1.0,
                    "type": "spoken_claim",
                }
            ],
            "clean_insights": [],
            "claims": [],
        }
        old_strict = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "0"
            md = v3.render_unified_episode_export_markdown(
                {"report_v3": r3, "workflow_report": {}, "meta": {}}
            )
        finally:
            if old_strict is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old_strict
        self.assertIn("## Podcast Performance Insight", md)
        self.assertIn("## 1-Line Fix", md)


class TestTranscriptNormalize(unittest.TestCase):
    def test_normalize_drops_consecutive_duplicate_lines(self):
        raw = "line a\nline a\nline b"
        self.assertEqual(v3.normalize_transcript_for_v3(raw), "line a\nline b")

    def test_normalize_keeps_duplicate_after_blank(self):
        raw = "line a\n\nline a"
        self.assertEqual(v3.normalize_transcript_for_v3(raw), "line a\n\nline a")

    def test_normalize_collapses_many_blank_lines(self):
        out = v3.normalize_transcript_for_v3("a\n\n\n\n\n\nb")
        parts = out.split("\n")
        self.assertEqual(parts[0], "a")
        self.assertEqual(parts[-1], "b")
        empties_between = sum(1 for p in parts[1:-1] if p == "")
        self.assertLessEqual(empties_between, 2)

    def test_transcript_pipeline_default_normalizes_duplicates(self):
        old = os.environ.get("SOAPBOXX_TRANSCRIPT_NORMALIZE")
        try:
            os.environ.pop("SOAPBOXX_TRANSCRIPT_NORMALIZE", None)
            self.assertEqual(v3.transcript_for_v3_pipeline("a\na"), "a")
        finally:
            if old is not None:
                os.environ["SOAPBOXX_TRANSCRIPT_NORMALIZE"] = old

    def test_transcript_pipeline_disabled_keeps_duplicates(self):
        old = os.environ.get("SOAPBOXX_TRANSCRIPT_NORMALIZE")
        try:
            os.environ["SOAPBOXX_TRANSCRIPT_NORMALIZE"] = "0"
            self.assertEqual(v3.transcript_for_v3_pipeline("a\na"), "a\na")
        finally:
            os.environ.pop("SOAPBOXX_TRANSCRIPT_NORMALIZE", None)
            if old is not None:
                os.environ["SOAPBOXX_TRANSCRIPT_NORMALIZE"] = old

    def test_transcript_pipeline_env_explicit_on(self):
        old = os.environ.get("SOAPBOXX_TRANSCRIPT_NORMALIZE")
        try:
            os.environ["SOAPBOXX_TRANSCRIPT_NORMALIZE"] = "1"
            self.assertEqual(v3.transcript_for_v3_pipeline("a\na"), "a")
        finally:
            os.environ.pop("SOAPBOXX_TRANSCRIPT_NORMALIZE", None)
            if old is not None:
                os.environ["SOAPBOXX_TRANSCRIPT_NORMALIZE"] = old

    def test_broken_evidence_quote_line_truncation(self):
        self.assertTrue(v3._is_broken_evidence_quote_line("Lead text that ends at 2 in the."))

    def test_generalize_sentence_strips_full_bracket_timestamp(self):
        out = v3._generalize_sentence(
            "[00:00:15] Let me start by asking what you think about AI in business today?"
        )
        self.assertNotIn("00:00:15]", out)
        self.assertNotIn("[00:00:15]", out)
        self.assertIn("Let me start", out)


if __name__ == "__main__":
    unittest.main()
