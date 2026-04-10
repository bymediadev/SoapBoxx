"""Tests for episode report v3 (no API calls for pure functions)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_report_v3 as v3  # noqa: E402


class TestEpisodeReportV3(unittest.TestCase):
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
        md = v3.render_episode_report_v3_markdown(r)
        self.assertIn("## 0. Readiness & expectations", md)
        self.assertIn("## 1. Episode Diagnosis", md)
        self.assertIn("## 10. Bottom Line", md)
        self.assertEqual(r.get("signal_mode"), "LOW_SIGNAL")
        self.assertEqual(r.get("output_mode"), "diagnostic")
        self.assertEqual(r.get("report_readiness", {}).get("output_mode"), "diagnostic")
        self.assertIn("coach_report", r)
        self.assertIn("narrative_reconstruction", r)
        self.assertTrue(r.get("takeaway"))
        self.assertIn("Diagnostic mode", r.get("takeaway", ""))

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
        unified = v3.render_unified_episode_export_markdown({"report_v3": r})
        self.assertIn("For **Alex**", unified)

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
        md = v3.render_unified_episode_export_markdown({"report_v3": r})
        self.assertIn("SoapBoxx Episode Intelligence", md)
        self.assertIn("network_episode_brief_v3.md", md)
        self.assertNotIn("only supported", md.lower())
        self.assertIn("## 1. Key Highlights", md)


if __name__ == "__main__":
    unittest.main()
