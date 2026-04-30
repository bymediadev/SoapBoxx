"""Tests for episode report v3 (no API calls for pure functions)."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_report_v3 as v3  # noqa: E402


class TestEpisodeReportV3(unittest.TestCase):
    """Brief-fixture tests use legacy brief claims; isolate env from other modules (e.g. reality golden)."""

    @classmethod
    def setUpClass(cls):
        cls._saved_atomic_gt = os.environ.get("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH")
        os.environ["SOAPBOXX_V3_ATOMIC_GROUND_TRUTH"] = "0"
        cls._saved_framing = os.environ.get("SOAPBOXX_V3_FRAMING")
        os.environ["SOAPBOXX_V3_FRAMING"] = "full"

    @classmethod
    def tearDownClass(cls):
        if cls._saved_atomic_gt is None:
            os.environ.pop("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH", None)
        else:
            os.environ["SOAPBOXX_V3_ATOMIC_GROUND_TRUTH"] = cls._saved_atomic_gt
        if getattr(cls, "_saved_framing", None) is None:
            os.environ.pop("SOAPBOXX_V3_FRAMING", None)
        else:
            os.environ["SOAPBOXX_V3_FRAMING"] = cls._saved_framing

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

    def test_derive_strategist_core_does_not_use_raw_title_as_thesis(self):
        """When coach thesis was collapsed to the episode title, strategist export must not repeat it as Thesis (fixed)."""
        bundle = {
            "report_v3": {
                "episode_snapshot": {
                    "title": "Brainwash! - The Rockefeller's School Psyop WORSE Than You Think",
                    "creator": "Julian Dorey",
                    "genre": "Entertainment",
                },
                "claims": [
                    {
                        "id": "c1",
                        "text": "might get into some of the 1800s though, so I don't know.",
                    }
                ],
                "coach_report": {
                    "episode_thesis": "Brainwash! - The Rockefeller's School Psyop WORSE Than You Think",
                },
                "narrative_reconstruction": {},
            },
            "workflow_report": {"evidence_map": []},
        }
        core = v3._derive_strategist_core_from_bundle(bundle)
        th = str(core["core_breakdown"]["thesis"] or "").strip()
        self.assertNotEqual(
            th.lower(),
            "brainwash! - the rockefeller's school psyop worse than you think",
        )
        self.assertTrue(
            "falsifiable" in th.lower() or "packaging" in th.lower(),
            msg=th,
        )

    def test_derive_strategist_core_rejects_host_quote_thesis(self):
        """A transcript speaker line should never survive as strategist Thesis (fixed)."""
        bundle = {
            "report_v3": {
                "episode_snapshot": {
                    "title": "Brainwash! - The Rockefeller School Psyop WORSE Than You Think",
                    "creator": "Julian Dorey",
                    "genre": "Entertainment",
                    "primary_topic": "education centralization",
                },
                "coach_report": {
                    "episode_thesis": "Host: We went down this centralized path where everything in society was moving more and more towards centralization."
                },
                "claims": [
                    {
                        "id": "a1",
                        "text": "Host: We went down this centralized path where everything in society was moving more and more towards centralization.",
                    }
                ],
                "evidence_mapping": [],
            },
            "workflow_report": {"evidence_map": []},
            "meta": {},
        }
        core = v3._derive_strategist_core_from_bundle(bundle)
        th = str((core.get("core_breakdown") or {}).get("thesis") or "")
        self.assertFalse(th.lower().startswith("host:"))
        self.assertNotIn("we went down this centralized path", th.lower())
        self.assertIn("episode_snapshot", core)

    def test_identity_consistency_coerces_when_coach_thesis_is_raw_title(self):
        """Title matches identity anchor (high Jaccard) — must still be coerced off episode_thesis."""
        report = {
            "meta": {"title": "Brainwash! The Test Episode Title Xyz"},
            "episode_snapshot": {
                "title": "Brainwash! The Test Episode Title Xyz",
                "primary_topic": "Brainwash! The Test Episode Title Xyz",
                "genre": "Entertainment",
            },
            "narrative_reconstruction": {
                "core_thesis": "Brainwash! The Test Episode Title Xyz",
                "supporting_mechanism": "mechanism text here for the episode.",
                "practical_translation": "practical text.",
            },
            "coach_report": {
                "episode_thesis": "Brainwash! The Test Episode Title Xyz",
            },
            "clean_insights": [],
        }
        out = v3.apply_identity_consistency_to_report_v3(report)
        et = str((out.get("coach_report") or {}).get("episode_thesis") or "")
        self.assertNotEqual(et.strip().lower(), "brainwash! the test episode title xyz")
        self.assertIn("packaging", et.lower())

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
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "It's like you're just a speck out there in the world where things are simple."
            )
        )
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "It made me realize how much of it was a scop in the sense of, you know, just fear."
            )
        )
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "One out of five, One out of five, One out of five, which is just that's like any kids like what."
            )
        )
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "Like you seem to be drawing on a lot of other themes like out obviously it's focused on "
                "the education system and how it got bastardized but like a lot of themes outside of it "
                "and you bought an Airstream and just traveled the country."
            )
        )
        self.assertTrue(
            v3.is_low_signal_insight_line(
                "It's funny when I have guys like you in here."
            )
        )
        self.assertTrue(v3.is_low_signal_insight_line("Hey guys, three quick things."))
        self.assertTrue(v3.is_low_signal_insight_line("Just went up to like Humble."))

    def test_remove_semantic_duplicates(self):
        items = ["duplicate claim", "duplicate claim", "unique claim"]
        out = v3.remove_semantic_duplicates(items, threshold=0.95)
        self.assertEqual(len(out), 2)

    def test_classify_output_mode_full_when_structural_ok_despite_few_highlights(self):
        """Grounded claims + evidence can carry full packaging when highlight extraction is thin."""
        brief = {"episode_snapshot": {"primary_topic": "topic", "title": "T"}, "narrative": []}
        rr = {
            "band": "moderate",
            "metrics": {
                "claim_count": 3,
                "evidence_row_count": 2,
                "signal_mode": "HIGH_SIGNAL",
            },
        }
        om, dr = v3.classify_output_mode(
            brief,
            signal_mode="HIGH_SIGNAL",
            clean_insights=["Single non-junk highlight with enough words to pass filters here."],
            report_readiness=rr,
        )
        self.assertEqual(om, "full")
        self.assertEqual(dr, [])

    def test_classify_output_mode_full_when_low_signal_but_grounded_structure(self):
        """LOW_SIGNAL + 3+ claims + 2+ evidence rows still ships full (classifier borderline)."""
        brief = {"episode_snapshot": {"primary_topic": "topic", "title": "T"}, "narrative": []}
        rr = {
            "band": "weak",
            "metrics": {
                "claim_count": 4,
                "evidence_row_count": 2,
                "signal_mode": "LOW_SIGNAL",
            },
        }
        om, dr = v3.classify_output_mode(
            brief,
            signal_mode="LOW_SIGNAL",
            clean_insights=["One highlight line with enough words to count as non-junk content here."],
            report_readiness=rr,
        )
        self.assertEqual(om, "full")
        self.assertEqual(dr, [])

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

    def test_validate_references_accepts_aid_when_blob_uses_cid(self):
        """cN references should validate against renumbered aN ids."""
        ok, errs = v3.validate_references(
            {
                "claims": [{"id": "a1"}],
                "body": "Listener Q&A [c1]",
            },
            valid_claim_ids={"a1"},
        )
        self.assertTrue(ok)
        self.assertEqual(errs, [])

    def test_validate_references_rejects_missing_numeric_suffix_even_with_prefix_swap(self):
        """Prefix swap is allowed (a/c), numeric mismatch is not."""
        ok, errs = v3.validate_references(
            {
                "claims": [{"id": "a1"}],
                "body": "Listener Q&A [c2]",
            },
            valid_claim_ids={"a1"},
        )
        self.assertFalse(ok)
        self.assertTrue(any("c2" in e for e in errs))

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
        self.assertIn("## 0b. Producer workflow", md)
        self.assertIn("## 0c. Argument rigor", md)
        self.assertIn("## 12. Producer sign-off", md)
        self.assertEqual(r.get("signal_mode"), "LOW_SIGNAL")
        self.assertEqual(r.get("output_mode"), "diagnostic")
        self.assertEqual(r.get("report_readiness", {}).get("output_mode"), "diagnostic")
        self.assertIn("argument_rigor", r)
        self.assertIn("score", r.get("argument_rigor") or {})
        self.assertIn("argument_rigor_status", r.get("report_readiness") or {})
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

    def test_tension_questions_keep_long_claim_without_mid_sentence_ellipsis(self):
        long_claim = (
            "Oh, the last guy I had in was he was an ESPN basketball writer who fell into the "
            "Epstein story and went bonkers five years ago."
        )
        claims = [{"id": "a1", "text": long_claim}]
        q = v3.generate_questions(claims, mode="tension")["a1"]
        blob = " ".join(
            str(q.get(k) or "")
            for k in ("contrarian", "validation", "application", "counterpunch")
        ).lower()
        self.assertIn("bonkers", blob)
        self.assertIn("basketball", blob)

    def test_dialin_production_warnings_flags_offline(self):
        with patch.dict(os.environ, {"SOAPBOXX_OFFLINE": "1"}, clear=False):
            w = v3.dialin_production_warnings({"report_v3": {"meta": {}}, "model": "offline"})
        self.assertTrue(any("SOAPBOXX_OFFLINE" in x for x in w))

    def test_dialin_brief_unavailable_does_not_blame_missing_ollama_model(self):
        with patch.dict(
            os.environ,
            {"SOAPBOXX_OFFLINE": "0", "SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b"},
            clear=False,
        ):
            w = v3.dialin_production_warnings(
                {"report_v3": {"meta": {}}, "model": "brief-unavailable"}
            )
        blob = " ".join(w)
        self.assertIn("Strict JSON brief failed", blob)
        self.assertNotIn("SOAPBOXX_OLLAMA_MODEL is not set", blob)

    def test_coach_follow_ups_breadth_first_across_claims(self):
        """Do not stack three engagement slots from the same claim before moving to the next."""
        brief = {
            "episode_snapshot": {"primary_topic": "t"},
            "claims": [
                {"id": "c1", "text": "First claim about apples."},
                {"id": "c2", "text": "Second claim about bridges."},
                {"id": "c3", "text": "Third claim about canals."},
            ],
            "production_moves": {},
            "evidence_gaps": {},
        }
        eng = v3.generate_questions(brief["claims"], mode="tension")
        qs = v3._coach_follow_up_questions(
            brief, eng, signal_mode="HIGH_SIGNAL", max_q=6
        )
        self.assertGreaterEqual(len(qs), 3)
        # First three should be counterpunch (or first key) from c1, c2, c3 — not all three triad lines from c1.
        self.assertIn("apples", qs[0].lower())
        self.assertIn("bridges", qs[1].lower())
        self.assertIn("canals", qs[2].lower())

    def test_tension_questions_rotate_templates_by_claim_id(self):
        claims = [
            {"id": "a1", "text": "Centralization of schooling reduces local accountability over time."},
            {"id": "a2", "text": "Centralization of schooling reduces local accountability over time."},
            {"id": "a3", "text": "Centralization of schooling reduces local accountability over time."},
        ]
        q1 = v3.generate_questions(claims, mode="tension")["a1"]["validation"] or ""
        q2 = v3.generate_questions(claims, mode="tension")["a2"]["validation"] or ""
        q3 = v3.generate_questions(claims, mode="tension")["a3"]["validation"] or ""
        self.assertNotEqual(q1.strip(), q2.strip())
        self.assertNotEqual(q2.strip(), q3.strip())

    def test_claim_stakes_compact_skips_prompt_like_lines(self):
        claims = [
            {"id": "a1", "text": "Tell me about preparedness and how important it is as believers to discern the times."},
            {"id": "a2", "text": "Which if I if I forget it, try to remind me to bring me back to dream interpretation."},
            {"id": "a3", "text": "AI adoption changes hiring demand, measured by role cuts over the next 12 months."},
        ]
        out = v3._build_claim_stakes_compact(claims, engagement={}, max_rows=3)
        blob = " ".join(out).lower()
        self.assertIn("[a3]", blob)
        self.assertNotIn("[a1]", blob)
        self.assertNotIn("[a2]", blob)

    def test_segment_planning_title_uses_word_boundary_not_72_char_rip(self):
        long_claim = (
            "Oh, the last guy I had in was he was an ESPN basketball writer who fell into the "
            "Epstein story and went bonkers five years ago."
        )
        segs = v3.build_executable_segments(
            [{"id": "a1", "text": long_claim, "why_it_matters": "Test perception vs evidence."}]
        )
        self.assertEqual(len(segs), 1)
        self.assertIn("bonkers", segs[0]["segment_title"].lower())

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

    def test_finalize_episode_thesis_avoids_host_quote_line(self):
        snap = {"title": "Brainwash! - Rockefeller school psyop", "primary_topic": "schooling centralization"}
        claims = [
            {
                "id": "a1",
                "text": "Host: We went down this centralized path where everything in society was moving more and more towards centralization.",
            }
        ]
        out = v3._finalize_episode_thesis_line(
            snap,
            thesis_quality=None,
            signal_mode="HIGH_SIGNAL",
            claims=claims,
            clean_insights=["Centralization of schooling reduces local accountability over time."],
        )
        self.assertFalse(out.lower().startswith("host:"))
        self.assertNotIn("we went down this centralized path", out.lower())

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

    def test_coach_report_guest_fallback_for_faith_business_title(self):
        brief = {
            "episode_snapshot": {
                "title": "The 2026 Shift That Will Make (or Break) Your Christian Business",
                "creator": "GOSHEN",
                "genre": "Education",
                "primary_topic": "AI; Christian business; discerning the times",
                "why_it_matters": "w",
            },
            "narrative": ["Believers must adapt operations without outsourcing discernment."],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "s", "goal": "g"}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        claims = [
            {
                "id": "a1",
                "text": "AI adoption changes hiring demand, measured by role cuts over the next 12 months.",
            }
        ]
        cr = v3.build_coach_report(
            brief,
            transcript="[00:00:10] AI adoption changes hiring demand in small businesses.",
            signal_mode="HIGH_SIGNAL",
            clean_insights=["Believers must adapt operations without outsourcing discernment."],
            evidence_mapping=[],
            engagement={},
            guests_v3=[],
            analytics={"what_worked": [], "what_failed": [], "next_move": []},
            claims=claims,
            output_mode="full",
            diagnostic_reasons=[],
        )
        gs = cr.get("guest_strategy") or {}
        guests = [str(g.get("guest_type") or "") for g in (gs.get("guests") or []) if isinstance(g, dict)]
        blob = " | ".join(guests).lower()
        self.assertIn("faith-driven business operator", blob)
        self.assertNotIn("diane ravitch", blob)

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
        self.assertIn("## Workflow execution checklist", md)
        self.assertNotIn("only supported", md.lower())
        self.assertNotIn("Readiness & expectations", md)

    def test_workflow_grounded_persons_not_strategist_guest_opportunities(self):
        wf = {
            "guests": [
                {
                    "name": "Jesse James",
                    "title": "Named in this episode (verbatim text)",
                    "role": "Episode figure",
                    "claim_id": "c1",
                    "angle": "Appears in claims.",
                    "topic_angle": "Grounded in episode text — not a model-invented person.",
                    "relevance": 10,
                    "source": "episode_grounded_person",
                }
            ]
        }
        out = v3._workflow_guest_rows_to_strategist_opportunities(wf)
        # Verbatim rows are stripped; a single bookable placeholder remains so exports are never empty.
        self.assertEqual(len(out), 1)
        self.assertNotIn("jesse", str(out[0].get("who_type", "")).lower())
        self.assertIn("historian", str(out[0].get("who_type", "")).lower())

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

    def test_merge_replaces_template_blueprint_strategist_fields(self):
        """Canned blueprint strategist strings are replaced with bundle-derived copy."""
        old = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "0"
            row = {
                "claim": "A long enough grounded claim line for the gate.",
                "evidence": "A long enough evidence quote from the transcript here.",
            }
            r3 = {
                "episode_snapshot": {"title": "Farming Narratives vs Scale", "creator": "Host"},
                "coach_report": {
                    "episode_thesis": "Scale incentives distort which farm stories get funded.",
                    "bottom_line": {"must_change": "State the falsifiable claim in the first minute.", "if_fixed": ""},
                },
                "claims": [{"text": "Consolidation reshapes which narratives investors hear.", "id": "c1"}],
                "evidence_mapping": [
                    dict(row),
                    {
                        "claim": "Second grounded claim line that passes length checks.",
                        "evidence": "Second evidence quote from the transcript passes checks.",
                    },
                ],
                "segments": [{"segment_title": "Open"}],
                "clean_insights": ["Farm consolidation shifts which stories reach funders."],
            }
            bp = {
                "strategist_report": {
                    "punchline_header": (
                        "Strong topic, but the episode keeps shifting claims instead of defending one argument. "
                        "Reframe around one claim and engagement rises."
                    ),
                    "core_problem": "legacy",
                    "snapshot": {
                        "overall_score": 6,
                        "signal_strength": "Moderate",
                        "diagnosis": "This episode underperforms due to weak positioning and lack of clear takeaway.",
                    },
                    "core_breakdown": {
                        "thesis": (
                            "Farming Narratives vs Scale is a claim about who gets protected when incentives "
                            "and rules collide."
                        ),
                        "key_claims": ["Consolidation reshapes which narratives investors hear."],
                        "evidence_anchors": [
                            {
                                "claim": "Consolidation reshapes which narratives investors hear.",
                                "anchor": "In a central scene, the host revisits the same argument without raising the stakes.",
                            }
                        ],
                        "tension_position": {
                            "implicit_argument": "This episode treats this as true: Same spine twice.",
                            "stronger_position": "But the stronger position is this: Same spine twice.",
                        },
                    },
                    "network_level_insight": [
                        "Weak positioning across shows",
                        "Lack of shareable moments",
                        "Structural engagement issues",
                        "High-upside opportunities",
                    ],
                    "one_line_fix": (
                        "If this episode were reframed around a clear argument and structured for tension, "
                        "it would become significantly more engaging and shareable."
                    ),
                    "conviction_statement": "This episode avoids the hard argument, and that avoidance is the main reason it underperforms.",
                    "network_rollout_line": (
                        "If we applied this across your network, we would identify which shows are underperforming."
                    ),
                }
            }
            bundle = {"report_v3": r3, "blueprint_v1": bp, "workflow_report": {}}
            sr = v3._derive_strategist_report_from_bundle(bundle)
        finally:
            if old is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old
        ph = str(sr.get("punchline_header") or "").lower()
        self.assertNotIn("shifting claims instead of defending", ph)
        self.assertIn("farming", ph)
        thesis = str((sr.get("core_breakdown") or {}).get("thesis") or "").lower()
        self.assertNotIn("who gets protected when incentives", thesis)
        self.assertIn("scale incentives", thesis)
        an0 = str(((sr.get("core_breakdown") or {}).get("evidence_anchors") or [{}])[0].get("anchor") or "")
        self.assertNotIn("revisits the same argument", an0.lower())
        nli = [str(x).lower() for x in (sr.get("network_level_insight") or [])]
        self.assertNotIn("weak positioning across shows", nli)
        self.assertNotIn("if we applied this across your network", str(sr.get("network_rollout_line") or "").lower())
        self.assertNotIn("if this episode were reframed around a clear argument", str(sr.get("one_line_fix") or "").lower())
        self.assertNotIn("avoids the hard argument", str(sr.get("conviction_statement") or "").lower())


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


class TestStrategistEvidenceAnchorMarkdown(unittest.TestCase):
    def test_all_redundant_evidence_anchors_collapsed_to_one_gap_block(self):
        old_s = os.environ.get("SOAPBOXX_STRICT_EXPORT")
        try:
            os.environ["SOAPBOXX_STRICT_EXPORT"] = "0"
            bundle = {
                "workflow_report": {
                    "metadata": {"export_status": "ok"},
                    "evidence_map": [
                        {
                            "claim": "Alpha claim is here with enough words for structure scoring.",
                            "evidence": "Alpha claim is here with enough words for structure scoring.",
                        },
                        {
                            "claim": "Beta claim is second with enough words here for export checks.",
                            "evidence": "Beta claim is second with enough words here for export checks.",
                        },
                    ],
                    "highlights": [],
                },
                "report_v3": {
                    "episode_snapshot": {"title": "Episode T", "creator": "C", "genre": "G"},
                    "claims": [
                        {"id": "a1", "text": "Alpha claim is here with enough words for structure scoring."},
                        {"id": "a2", "text": "Beta claim is second with enough words here for export checks."},
                    ],
                    "coach_report": {
                        "episode_thesis": "We argue alpha and beta shape the outcome for listeners today."
                    },
                    "report_readiness": {
                        "metrics": {
                            "transcript_word_count": 500,
                            "claim_count": 2,
                            "evidence_row_count": 2,
                        }
                    },
                },
            }
            md = v3._render_strategist_export_markdown(bundle)
        finally:
            if old_s is None:
                os.environ.pop("SOAPBOXX_STRICT_EXPORT", None)
            else:
                os.environ["SOAPBOXX_STRICT_EXPORT"] = old_s
        self.assertIn("## Evidence Anchors", md)
        self.assertIn("**Gap:**", md)
        self.assertEqual(md.count("Same line as the claim on the tape"), 0)


class TestStrategistTensionMetaThesis(unittest.TestCase):
    def test_meta_thesis_with_praise_claim_uses_generic_implicit(self):
        thesis = "The episode title is packaging — name one falsifiable claim this tape actually proves on mic."
        tp = v3._strategist_tension_from_claims(
            thesis,
            ["I love that about the stage of journalism and entertainment and media we are in."],
        )
        self.assertIn("rapport beats", str(tp.get("implicit_argument") or "").lower())
        self.assertIn("editorial north star", str(tp.get("stronger_position") or "").lower())
        self.assertNotIn("stage of journalism", str(tp.get("implicit_argument") or "").lower())

    def test_meta_thesis_with_substantive_claim_keeps_mic_pairing(self):
        thesis = "The episode title is packaging — name one falsifiable claim this tape actually proves on mic."
        tp = v3._strategist_tension_from_claims(
            thesis,
            ["Standardized testing baked vendor incentives into district procurement over a decade."],
        )
        self.assertIn("leans on listeners", str(tp.get("implicit_argument") or "").lower())
        self.assertIn("standardized", str(tp.get("implicit_argument") or "").lower())


class TestStrategistCoherenceHelpers(unittest.TestCase):
    def test_dedupe_highlights_vs_claims(self):
        claims = ["Same line on mic about schools."]
        hi = ["Same line on mic about schools.", "A distinct production strength is pacing."]
        out = v3._dedupe_strategist_highlights_vs_claims(hi, claims, sim_threshold=0.95)
        self.assertEqual(len(out), 1)
        self.assertIn("pacing", out[0].lower())

    def test_question_upgrade_mentions_spine(self):
        qu = v3._strategist_question_upgrade_from_thesis("Rockefeller influence on schooling is structural, not accidental.")
        self.assertEqual(len(qu), 3)
        self.assertTrue(any("counterargument" in q.lower() for q in qu))


class TestSingleEpisodeReportMarkdownGuard(unittest.TestCase):
    def test_ensure_single_keeps_last_report_block(self):
        first = "# SoapBoxx Episode Report\n\nFirst body.\n"
        second = "# SoapBoxx Episode Report\n\nSecond body.\n"
        merged = "preamble\n\n" + first + "\n---\n\n" + second
        out = v3.ensure_single_episode_report_markdown(merged)
        self.assertEqual(v3._count_episode_report_markdown_h1(out), 1)
        self.assertIn("Second body", out)
        self.assertNotIn("First body", out)

    def test_strict_env_raises_on_duplicate_h1(self):
        dup = "# SoapBoxx Episode Report\nA\n# SoapBoxx Episode Report\nB\n"
        prev = os.environ.get("SOAPBOXX_STRICT_EPISODE_REPORT_HEADER")
        os.environ["SOAPBOXX_STRICT_EPISODE_REPORT_HEADER"] = "1"
        try:
            with self.assertRaises(AssertionError):
                v3._strict_episode_report_h1_pre_check(dup, where="test")
        finally:
            if prev is None:
                os.environ.pop("SOAPBOXX_STRICT_EPISODE_REPORT_HEADER", None)
            else:
                os.environ["SOAPBOXX_STRICT_EPISODE_REPORT_HEADER"] = prev


class TestFinalizeUnifiedMarkdown(unittest.TestCase):
    def test_strips_duplicate_tail_after_workflow_appendix_footer(self):
        base = (
            "# SoapBoxx Episode Report\n\n---\n\n"
            "## Workflow execution checklist\n\n## 1. Key Highlights\n- a\n"
            "*SoapBoxx Episode Intelligence — workflow appendix — v3*\n"
        )
        dup = (
            base
            + "\nCore Narrative: Criminal enterprise, law enforcement, and accountability\n\n"
            "## Workflow execution checklist\n\n## 1. Key Highlights\n- a\n"
        )
        out = v3.finalize_unified_markdown_export(dup)
        self.assertEqual(out.rstrip(), base.rstrip())
        self.assertNotIn("Core Narrative", out)

    def test_strips_core_narrative_tail_without_crime_keywords(self):
        base = (
            "# SoapBoxx Episode Report\n\n"
            "*SoapBoxx Episode Intelligence — workflow appendix — v3*\n"
        )
        dup = base + "\nCore Narrative: Some other wrong template line for this episode.\n\n1. Key Highlights\n- x\n"
        out = v3.finalize_unified_markdown_export(dup)
        self.assertEqual(out.rstrip(), base.rstrip())

    def test_strips_inline_leak_on_same_line_as_appendix_footer(self):
        """Editorial models sometimes glue ``Core Narrative`` to the closing italic without a newline."""
        base = (
            "## 6. Analytics / Narrative Tracking\n\n"
            "*SoapBoxx Episode Intelligence — workflow appendix — v3*"
        )
        dup = base + " Core Narrative: Wrong template\n\n1. Key Highlights\n- x\n"
        out = v3.finalize_unified_markdown_export(dup)
        self.assertEqual(out.rstrip(), base.rstrip())

    def test_strips_episode_comparison_graph_placeholder_anywhere(self):
        """The empty 'Episode Comparison Graph (Optional)' section should be dropped in-body, not only as tail."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            "## 6. Analytics / Narrative Tracking\n\n- themes\n\n"
            "## 7. Episode Comparison Graph (Optional)\n\n"
            "*SoapBoxx Episode Intelligence — workflow appendix — v3*\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertNotIn("Episode Comparison Graph", out)
        self.assertIn("Analytics / Narrative Tracking", out)
        self.assertIn("workflow appendix", out)

    def test_strips_what_this_doesnt_do_section(self):
        """'What this doesn't do (yet)' boilerplate block is removed wherever it sits."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            "## 9. What this doesn't do (yet)\n\n"
            "- Doesn't fully validate claims or sources\n"
            "- Doesn't replace deep research or expert analysis\n\n"
            "## 10. If you want more…\n\n"
            "- Deeper breakdown of claims and source credibility\n\n"
            "*SoapBoxx Episode Intelligence — workflow appendix — v3*\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertNotIn("What this doesn", out)
        self.assertNotIn("If you want more", out)
        self.assertNotIn("Deeper breakdown", out)

    def test_strips_numbered_8_9_10_tail_after_footer(self):
        base = (
            "# SoapBoxx Episode Report\n\n"
            "*SoapBoxx Episode Intelligence — workflow appendix — v3*\n"
        )
        dup = (
            base
            + "Local pipeline highlights, transcript-anchor table, and shipping checklist are hidden while quality gates fail.\n\n"
            + "8. Episode Comparison Graph (Optional)\n"
            + "9. What this doesn’t do (yet)\n"
            + "10. If you want more…\n"
        )
        out = v3.finalize_unified_markdown_export(dup)
        self.assertEqual(out.rstrip(), base.rstrip())

    def test_strips_llm_hallucinated_prelude_lines(self):
        """LLM-injected ``Core Narrative:`` / ``Primary workflow:`` / ``Compact brief:`` lines get removed."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            "Primary workflow: v3 (SoapBoxx Episode Report).\n"
            "Compact brief (v2 filename): network_episode_brief_v2.md — optional one-page export.\n\n"
            "**Title:** Ep\n"
            "**Show / creator:** Show\n"
            "**Genre:** Education / Society\n"
            "**Generated:** 2026-04-20T18:03:08\n\n"
            "Core Narrative: Criminal enterprise, law enforcement, and accountability\n\n"
            "## 1. Key Highlights\n- keep me\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertNotIn("Primary workflow:", out)
        self.assertNotIn("Compact brief (v2 filename):", out)
        self.assertNotIn("Core Narrative:", out)
        self.assertIn("**Title:** Ep", out)
        self.assertIn("keep me", out)

    def test_strips_bold_wrapped_core_narrative_prelude(self):
        """Editorial pass sometimes wraps invented labels in ``**``."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            "**Core Narrative:** Criminal enterprise, law enforcement, and accountability\n\n"
            "## 1. Key Highlights\n- x\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertNotIn("Core Narrative", out)
        self.assertIn("Key Highlights", out)

    def test_syncs_stale_genre_line_from_title(self):
        """``Genre: Entertainment`` is rewritten from ``Title:`` when title cues education."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            'Title: "Brainwash!" - Rockefeller school psyop | Ep 410\n'
            "Creator: Julian Dorey\n"
            "Genre: Entertainment\n"
            "Generated: 2026-04-20T19:43:00\n\n"
            "## 1. Key Highlights\n- a\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertIn("Education / Society", out)
        self.assertNotIn("Genre: Entertainment", out)

    def test_strips_no_worry_publishing_standard_block(self):
        """``No-worry publishing standard`` as a plain-text section header strips its body too."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            "## 7. Execution Layer (MANDATORY)\n\n"
            "body content\n\n"
            "No-worry publishing standard\n\n"
            "Ship confidently when these are true:\n"
            "- Yes — Clear core thesis\n"
            "- Yes — 2-3 strong clip ideas\n"
            "- Gap — Optional: creator profile supplied (personalization)\n\n"
            "## 8. Segment Upgrade\n- keep me\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertNotIn("No-worry publishing standard", out)
        self.assertNotIn("Ship confidently when these are true", out)
        self.assertNotIn("creator profile supplied", out)
        self.assertIn("body content", out)
        self.assertIn("Segment Upgrade", out)
        self.assertIn("keep me", out)

    def test_strips_renumbered_meta_sections_beyond_10(self):
        """Editorial LLM sometimes renumbers meta blocks (e.g. 11/12/13); strip should still match."""
        md = (
            "# SoapBoxx Episode Report\n\n"
            "## 10. Bottom Line\n- real content\n\n"
            "11. Episode Comparison Graph (Optional)\n"
            "12. What this doesn't do (yet)\n"
            "- Doesn't fully validate claims\n"
            "13. If you want more…\n"
            "- Deeper breakdown\n"
        )
        out = v3.finalize_unified_markdown_export(md)
        self.assertNotIn("Episode Comparison Graph", out)
        self.assertNotIn("What this doesn", out)
        self.assertNotIn("If you want more", out)
        self.assertIn("real content", out)

    def test_dedupe_adjacent_comma_clauses_collapses_stutter(self):
        raw = (
            "the Rockefeller, , the their foundation is still , the their foundation is still , "
            "the their foundation is still heavily invested into."
        )
        got = v3._dedupe_adjacent_comma_clauses(raw)
        self.assertNotIn("the their foundation is still , the their foundation", got)
        self.assertIn("heavily invested", got.lower())


class TestClaimRowSpineFilters(unittest.TestCase):
    def test_filter_claim_rows_drops_rapport_filler_on_education_spine(self):
        spine = "Brainwash Rockefeller school education"
        claims = [
            {"id": "x1", "text": "That's nice though, having a place like that to yourself.", "claim_type": "interpretation"},
            {
                "id": "x2",
                "text": "The Rockefeller foundation remained involved in shaping school models.",
                "claim_type": "interpretation",
            },
        ]
        out = v3._filter_claim_rows_after_atomic(claims, spine_hint=spine)
        self.assertTrue(out)
        self.assertTrue(all("rockefeller" in str(c.get("text") or "").lower() for c in out))


class TestAtomicPipelineSpinePrune(unittest.TestCase):
    def test_filter_atomic_pipeline_json_keeps_only_allowed_ids(self):
        ap = {
            "claims": [
                {
                    "id": "c1",
                    "raw_statement": "Tangent about a national park with no cars.",
                    "category": "interpretation",
                    "confidence": "medium",
                    "evidence_basis": "explicit_transcript",
                },
                {
                    "id": "c2",
                    "raw_statement": "Rockefeller foundation influence on school boards is structural.",
                    "category": "interpretation",
                    "confidence": "medium",
                    "evidence_basis": "explicit_transcript",
                },
            ],
            "verification": [{"claim_id": "c1", "status": "unverified", "recommended_action": "keep"}],
            "insights": [],
            "clips": [{"clip_id": "cl1", "source_claim_id": "c1", "hook_line": "h", "why_it_works": "clarity", "risk_level": "safe"}],
            "guest_recommendations": [],
            "actions": [],
            "topic_graph": {
                "nodes": [
                    {
                        "topic_id": "t1",
                        "label": "L",
                        "weight": 0.5,
                        "category": "history",
                        "evidence_claim_ids": ["c1", "c2"],
                    }
                ],
                "edges": [],
            },
            "diagnostics": {},
        }
        out = v3._filter_atomic_pipeline_json_to_claim_allowlist(ap, {"c2"})
        self.assertEqual(len(out["claims"]), 1)
        self.assertEqual(out["claims"][0]["id"], "c2")
        self.assertEqual(out["verification"], [])
        self.assertEqual(out["clips"], [])


class TestThesisKeywordSalad(unittest.TestCase):
    def test_keyword_salad_thesis_normalized_for_education_title(self):
        snap = {"title": "Brainwash Rockefeller School Psyop", "primary_topic": "x"}
        raw = "Rockefeller family; education system; Prussian model; psychological manipulation"
        self.assertTrue(v3._thesis_line_is_keyword_bullet_list(raw))
        out = v3._normalize_keyword_salad_thesis(raw, snap)
        self.assertIn("falsifiable", out.lower())
        self.assertNotIn("prussian model", out.lower())

    def test_keyword_salad_thesis_normalized_for_christian_business_title(self):
        snap = {"title": "The 2026 Shift That Will Make (or Break) Your Christian Business", "primary_topic": "x"}
        raw = "AI; Christian business; discerning the times; Daniel anointing; Joseph anointing"
        self.assertTrue(v3._thesis_line_is_keyword_bullet_list(raw))
        out = v3._normalize_keyword_salad_thesis(raw, snap)
        self.assertIn("measurable", out.lower())
        self.assertIn("ai-era", out.lower())

    def test_refresh_coach_surfaces_syncs_diagnosis_to_coach_thesis(self):
        report = {
            "episode_snapshot": {"title": "Brainwash Rockefeller School Psyop", "genre": "Education"},
            "coach_report": {
                "episode_thesis": "Rockefeller family; education system; centralized control",
                "episode_diagnosis": {
                    "body": [
                        "**Thesis (one sentence):** It's like you're just a speck out there in the world.",
                        "**Retention:** One thesis.",
                    ],
                },
                "uncomfortable_insight": {
                    "title": "u",
                    "body": (
                        "If your thesis is “Tell me about preparedness and how important it is as believers to discern the times.”, "
                        "ask what would make you *wrong* on mic — not just what would make you sound fair."
                    ),
                },
            },
            "narrative_reconstruction": {
                "core_thesis": "Rockefeller family; education system; centralized control",
            },
        }
        v3._refresh_coach_thesis_surfaces_after_identity(report)
        et = str(report["coach_report"]["episode_thesis"])
        thesis_lines = [
            str(x)
            for x in (report["coach_report"]["episode_diagnosis"]["body"] or [])
            if str(x).strip().startswith("**Thesis (one sentence):**")
        ]
        self.assertEqual(thesis_lines, [f"**Thesis (one sentence):** {et}"])
        self.assertIn("falsifiable", et.lower())
        self.assertIn(et[:40], str(report["coach_report"]["uncomfortable_insight"]["body"]))

    def test_claim_conflicts_dont_go_outside_tangent(self):
        spine = "Brainwash Rockefeller school education psyop"
        self.assertTrue(
            v3._claim_conflicts_spine_hint(
                "It was like around the time when they were telling people don't go outside, which is crazy.",
                spine,
            )
        )

    def test_claim_conflicts_filters_community_cta_line(self):
        spine = "Christian business AI discernment and operating risk"
        self.assertTrue(
            v3._claim_conflicts_spine_hint(
                "If you've been looking for a community that takes your faith and your business seriously, it's called Goan.",
                spine,
            )
        )


class TestSpineHintHelpers(unittest.TestCase):
    def test_claim_conflicts_spine_hint_education_vs_epstein_tangent(self):
        spine = "Brainwash Rockefeller school education psyop"
        self.assertTrue(
            v3._claim_conflicts_spine_hint("mentions of them were in the Epstein file", spine)
        )
        self.assertFalse(
            v3._claim_conflicts_spine_hint(
                "The Rockefeller family's foundation influenced local school governance.", spine
            )
        )

    def test_claim_conflicts_spine_hint_education_vs_rothschild_and_covid(self):
        spine = "Brainwash Rockefeller school education psyop"
        self.assertTrue(
            v3._claim_conflicts_spine_hint(
                "I saw how the Rothschilds were kind of like the orchestrator syncing up a lot of the people.",
                spine,
            )
        )
        self.assertTrue(
            v3._claim_conflicts_spine_hint(
                "Like we found going inside and being in the AC was the worst way to spread the virus.",
                spine,
            )
        )

    def test_claim_conflicts_spine_hint_education_vs_trees_outdoors(self):
        spine = "Brainwash Rockefeller school education psyop"
        self.assertTrue(
            v3._claim_conflicts_spine_hint(
                "Those trees, it's they're biggest trees in the world.",
                spine,
            )
        )
        self.assertTrue(
            v3._claim_conflicts_spine_hint(
                "You just get in touch with the outdoors.",
                spine,
            )
        )

    def test_strategist_mic_line_is_praise_or_meta(self):
        self.assertTrue(
            v3._strategist_mic_line_is_praise_or_meta(
                "I love that about the stage of journalism that we're in and just the stage of entertainment and media."
            )
        )

    def test_prompt_like_claim_line_filtered(self):
        self.assertTrue(
            v3._is_prompt_like_claim_line(
                "Tell me about preparedness and how important it is as believers to discern the times."
            )
        )
        self.assertTrue(
            v3._is_prompt_like_claim_line(
                "Which if I if I forget it, try to remind me to bring me back to that concept of dream interpretation."
            )
        )
        self.assertFalse(
            v3._is_prompt_like_claim_line(
                "Centralized policy reduced teacher autonomy and attendance rates in district reports."
            )
        )
        self.assertFalse(
            v3._strategist_mic_line_is_praise_or_meta(
                "The Rockefeller family's influence on the education system is more pervasive than previously thought."
            )
        )

    def test_derive_strategist_key_claims_drop_praise_and_tangents(self):
        bundle = {
            "report_v3": {
                "episode_snapshot": {
                    "title": "Brainwash! Rockefeller School Education Special",
                    "creator": "X",
                },
                "claims": [
                    {
                        "id": "a1",
                        "text": "I love that about the stage of journalism and entertainment and media we are in.",
                    },
                    {
                        "id": "a2",
                        "text": "I was in Zion National Park and there was supposed to be 30,000 people and there was no one.",
                    },
                    {
                        "id": "a3",
                        "text": "Standardized testing baked vendor incentives into district procurement over a decade.",
                    },
                ],
                "coach_report": {"episode_thesis": "One spine about schooling."},
            },
            "workflow_report": {},
        }
        core = v3._derive_strategist_core_from_bundle(bundle)
        kc = core["core_breakdown"]["key_claims"]
        self.assertEqual(len(kc), 1)
        self.assertIn("standardized", kc[0].lower())

    def test_derive_strategist_highlights_drop_off_spine_for_education_title(self):
        bundle = {
            "report_v3": {
                "episode_snapshot": {
                    "title": "Brainwash! Rockefeller School Education Special",
                    "creator": "X",
                },
                "claims": [
                    {
                        "id": "a1",
                        "text": "Standardized testing baked vendor incentives into district procurement over a decade.",
                    },
                ],
                "coach_report": {"episode_thesis": "One spine about schooling."},
                "clean_insights": [],
            },
            "workflow_report": {
                "highlights": [
                    {"insight": "Like we found going inside and being in the AC was the worst way to spread the virus."},
                    {"insight": "District procurement rules quietly rewarded incumbents after testing mandates expanded."},
                ]
            },
        }
        core = v3._derive_strategist_core_from_bundle(bundle)
        wh = core.get("what_working") or []
        self.assertEqual(len(wh), 1)
        self.assertIn("procurement", wh[0].lower())

    def test_distribution_cta_detected(self):
        self.assertTrue(
            v3._is_distribution_cta_claim_line(
                "If you'd like to join my Patreon for early uncensored releases via the link in my description."
            )
        )


class TestTruthModeHardGates(unittest.TestCase):
    def test_truth_gate_detects_label_thesis_and_weak_rows(self):
        report = {
            "episode_snapshot": {"title": "Brainwash!", "primary_topic": "Brainwash!"},
            "coach_report": {"episode_thesis": "Brainwash!"},
            "claims": [{"id": "a1", "text": "they're definitely they get a lot of the credit for the..."}],
            "evidence_mapping": [{"id": "a1", "claim": "vague", "evidence": "another vague statement"}],
            "report_readiness": {"metrics": {"transcript_word_count": 500}},
        }
        passed, reasons, metrics = v3.evaluate_truth_mode_hard_gates(
            report,
            transcript="short transcript with no direct quote alignment",
        )
        self.assertFalse(passed)
        self.assertTrue(any("Thesis is not falsifiable" in r for r in reasons))
        self.assertTrue(any("Atomic claims gate failed" in r for r in reasons))
        self.assertTrue(any("Direct evidence gate failed" in r for r in reasons))
        self.assertFalse(metrics.get("thesis_ok"))

    def test_generate_episode_report_truth_mode_blocks_export_on_gate_failure(self):
        fake_report = {
            "episode_snapshot": {
                "title": "Brainwash!",
                "creator": "Julian Dorey",
                "primary_topic": "Brainwash!",
            },
            "coach_report": {"episode_thesis": "Brainwash!"},
            "narrative_reconstruction": {"core_thesis": "Brainwash!"},
            "claims": [{"id": "a1", "text": "fragment claim"}],
            "evidence_mapping": [{"id": "a1", "claim": "fragment claim", "evidence": "fragment evidence"}],
            "report_readiness": {"metrics": {"transcript_word_count": 500}},
            "meta": {"title": "Brainwash!", "creator": "Julian Dorey"},
            "output_mode": "full",
        }
        base = {"brief": {"episode_snapshot": {}}, "warnings": [], "model": "test", "markdown": "v2"}
        with patch.dict(os.environ, {"SOAPBOXX_MODE": "truth"}, clear=False):
            with patch.object(v3, "generate_episode_brief", return_value=base):
                with patch.object(v3, "build_v3_report", return_value=fake_report):
                    with patch("episode_progress.prepare_bundle_for_export", lambda bundle: None):
                        with patch(
                            "episode_progress.attach_export_telemetry_to_metadata",
                            lambda meta, bundle: None,
                        ):
                            with patch(
                                "episode_progress.persist_episode_progress_after_export",
                                lambda bundle: None,
                            ):
                                out = v3.generate_episode_report_v3(
                                    "test transcript",
                                    {"title": "Brainwash!"},
                                )
        self.assertFalse(out["truth_mode_gate"]["passed"])
        self.assertIn("Truth mode gate: report withheld", out["markdown_export"])
        self.assertEqual(out["markdown_v3"], out["markdown_export"])


class TestCoachSynthMerge(unittest.TestCase):
    def test_merge_inserts_analytical_read_after_thesis(self):
        import coach_synth as cs

        cr = {
            "episode_diagnosis": {"body": ["intro", "**Thesis (one sentence):** x", "tail"]},
            "uncomfortable_insight": {"title": "t", "body": "old"},
            "contrarian_hook": {"title": "c", "body": "old2"},
            "themes": [{"label": "Theme 1", "discussed": "d", "implying": "i", "matters": "m"}],
        }
        patch = {
            "analytical_read": ["First para.", "Second."],
            "uncomfortable_insight_body": "new uncomfortable",
            "contrarian_hook_body": "new contra",
            "themes": [
                {
                    "label": "T1",
                    "discussed": "Specific thread the host keeps returning to.",
                    "implying": "They treat it as causal.",
                    "matters": "Listeners decide whether to buy the mechanism.",
                }
            ],
        }
        meta = cs.merge_coach_synthesis(cr, patch)
        self.assertEqual(meta.get("ok"), "1")
        body = cr["episode_diagnosis"]["body"]
        idx = body.index("**Thesis (one sentence):** x")
        self.assertEqual(body[idx + 1], "")
        self.assertIn("Model read", body[idx + 2])
        self.assertEqual(body[idx + 3], "First para.")
        self.assertEqual(cr["uncomfortable_insight"]["body"], "new uncomfortable")
        self.assertEqual(cr["contrarian_hook"]["body"], "new contra")
        self.assertEqual(len(cr["themes"]), 1)
        self.assertIn("Specific thread", cr["themes"][0]["discussed"])

    def test_merge_replaces_action_plan_fields(self):
        import coach_synth as cs

        cr = {
            "episode_diagnosis": {"body": ["**Thesis (one sentence):** t"]},
            "uncomfortable_insight": {"title": "u", "body": "x"},
            "contrarian_hook": {"title": "c", "body": "y"},
            "themes": [],
            "immediate_fix_plan": ["old1", "old2"],
            "follow_up_questions": ["q0"],
            "segment_upgrade": "old seg",
            "bottom_line": {"good": "g", "must_change": "m", "if_fixed": "i"},
            "where_it_breaks": {"issues": ["old issue"], "rule": "keep this rule"},
            "opportunities": {"clip_moments": ["old clip"], "spinoff_title": "", "spinoff_structure": "", "segment_idea": ""},
        }
        patch = {
            "analytical_read": ["A."],
            "immediate_fix_plan": ["Step one for this show.", "Step two.", "Step three."],
            "follow_up_questions": ["Q1?", "Q2?", "Q3?"],
            "segment_upgrade": "New segment plan for this episode only.",
            "bottom_line": {"good": "G2", "must_change": "M2", "if_fixed": "I2"},
            "where_it_breaks_issues": ["Pressure A", "Pressure B"],
            "clip_moments": ["Clip idea tied to excerpt."],
        }
        cs.merge_coach_synthesis(cr, patch)
        self.assertEqual(cr["immediate_fix_plan"], patch["immediate_fix_plan"])
        self.assertEqual(cr["follow_up_questions"], patch["follow_up_questions"])
        self.assertEqual(cr["segment_upgrade"], patch["segment_upgrade"])
        self.assertEqual(cr["bottom_line"]["good"], "G2")
        self.assertEqual(cr["where_it_breaks"]["rule"], "keep this rule")
        self.assertEqual(cr["where_it_breaks"]["issues"], patch["where_it_breaks_issues"])
        self.assertEqual(cr["opportunities"]["clip_moments"], patch["clip_moments"])

    def test_normalize_synth_payload_drops_themes_when_discussed_too_short(self):
        import coach_synth as cs

        out = cs._normalize_synth_payload(
            {
                "analytical_read": ["One real paragraph here."],
                "themes": [{"discussed": "short", "implying": "y", "matters": "z"}],
            }
        )
        self.assertIn("analytical_read", out)
        self.assertNotIn("themes", out)

    def test_normalize_synth_payload_includes_action_fields(self):
        import coach_synth as cs

        out = cs._normalize_synth_payload(
            {
                "analytical_read": ["P1."],
                "uncomfortable_insight_body": "U",
                "contrarian_hook_body": "C",
                "themes": [{"discussed": "Enough length here.", "implying": "i", "matters": "m"}],
                "immediate_fix_plan": ["a", "b"],
                "follow_up_questions": ["1", "2", "3"],
                "segment_upgrade": "x" * 40,
                "bottom_line": {"good": "g", "must_change": "", "if_fixed": "f"},
                "where_it_breaks_issues": ["i1", "i2"],
                "clip_moments": ["clip1"],
            }
        )
        self.assertEqual(out["immediate_fix_plan"], ["a", "b"])
        self.assertEqual(len(out["follow_up_questions"]), 3)
        self.assertIn("segment_upgrade", out)
        self.assertEqual(out["bottom_line"]["good"], "g")
        self.assertEqual(out["where_it_breaks_issues"], ["i1", "i2"])
        self.assertEqual(out["clip_moments"], ["clip1"])

    def test_coach_synth_backend_forced_groq(self):
        import coach_synth as cs

        with patch.dict(os.environ, {"SOAPBOXX_COACH_SYNTH_BACKEND": "groq"}, clear=False):
            self.assertEqual(cs._coach_synth_backend(), "groq")


class TestReferenceShelf(unittest.TestCase):
    def test_collect_shelf_matches_rockefeller_language(self):
        import episode_reference_shelf as ers

        r = {
            "claims": [{"id": "a1", "text": "The Rockefeller General Education Board shaped centralized schooling."}],
            "evidence_mapping": [],
            "coach_report": {"episode_thesis": "Philanthropy and school governance."},
            "episode_snapshot": {"title": "Brainwash school history", "primary_topic": "education"},
        }
        shelf = ers.collect_reference_shelf(r)
        ids = {e["id"] for e in shelf}
        self.assertIn("rockefeller_archive", ids)

    def test_collect_shelf_matches_cdc_language(self):
        import episode_reference_shelf as ers

        r = {
            "claims": [{"id": "a1", "text": "The CDC youth risk survey reported trends in 2023."}],
            "evidence_mapping": [],
            "coach_report": {},
            "episode_snapshot": {"title": "Teen health", "primary_topic": "health"},
        }
        shelf = ers.collect_reference_shelf(r)
        self.assertTrue(any(e["id"] == "cdc_yrbss" for e in shelf))

    def test_render_includes_appendix_b_when_shelf_present(self):
        r = {
            "signal_mode": "HIGH_SIGNAL",
            "report_readiness": {"band": "strong", "output_mode": "full", "metrics": {}},
            "meta": {"title": "T", "creator": "C", "genre": "G"},
            "episode_snapshot": {"title": "T", "creator": "C", "genre": "G"},
            "coach_report": {
                "signal_mode": "HIGH_SIGNAL",
                "output_mode": "full",
                "episode_diagnosis": {"body": ["**Thesis (one sentence):** x"]},
                "uncomfortable_insight": {"title": "u", "body": "b"},
                "contrarian_hook": {"title": "c", "body": "d"},
                "themes": [],
                "what_worked": [],
                "where_it_breaks": {"issues": [], "rule": "r"},
                "opportunities": {},
                "follow_up_questions": [],
                "guest_strategy": {"intro": "", "guests": []},
                "segment_upgrade": "",
                "immediate_fix_plan": [],
                "bottom_line": {"good": "g", "must_change": "m", "if_fixed": "i"},
            },
            "claims": [{"id": "a1", "text": "Rockefeller foundation grants followed IRS Form 990 disclosures."}],
            "evidence_mapping": [{"id": "a1", "timestamp": None, "type": "x", "claim": "c", "evidence": "e"}],
            "engagement_questions": {},
            "dual_lens": {},
            "reference_shelf": [
                {
                    "id": "test",
                    "mla": "Author, Ann. *Sample Title.* Publisher, 2020.",
                    "find_at": "https://example.invalid/catalog",
                }
            ],
        }
        md = v3.render_episode_report_v3_markdown(r)
        self.assertIn("Appendix B", md)
        self.assertIn("Sample Title", md)

    def test_v3_framing_freebie_preview_order(self):
        prev = os.environ.get("SOAPBOXX_V3_FRAMING")
        try:
            os.environ["SOAPBOXX_V3_FRAMING"] = "freebie"
            r = {
                "meta": {"title": "T", "generated_at": "g"},
                "episode_snapshot": {"title": "T", "creator": "C", "genre": "G"},
                "signal_mode": "HIGH_SIGNAL",
                "report_readiness": {
                    "band": "strong",
                    "output_mode": "full",
                    "notes": ["n1", "n2", "n3"],
                    "suggested_actions": ["a1"],
                },
                "coach_report": {
                    "signal_mode": "HIGH_SIGNAL",
                    "episode_diagnosis": {"body": ["Diagnosis."]},
                    "follow_up_questions": ["Q1?"],
                    "guest_strategy": {
                        "intro": "Guest intro.",
                        "guests": [{"guest_type": "Type", "adds": "Adds"}],
                    },
                    "what_worked": ["w"],
                    "where_it_breaks": {"issues": [], "rule": "r"},
                    "opportunities": {},
                    "segment_upgrade": "",
                    "immediate_fix_plan": [],
                    "bottom_line": {"good": "", "must_change": "", "if_fixed": ""},
                },
                "claims": [{"id": "a1", "text": "Claim one."}],
                "evidence_mapping": [],
                "dual_lens": {
                    "episode_lens_type": "NARRATIVE",
                    "confidence": 0.5,
                    "weights": {"narrative": 0.5, "analytical": 0.5},
                },
            }
            md = v3.render_episode_report_v3_markdown(r)
            self.assertIn("## What this is", md)
            self.assertIn("## 1. Smarter follow-up questions", md)
            self.assertIn("## 4. The spine", md)
            self.assertIn("## 12. Deeper", md)
            self.assertIn("## 13. Dual lens (parallel read + weights)", md)
            self.assertIn("## 14. Producer sign-off (pre-publish)", md)
            self.assertNotIn("## 0. Readiness & expectations", md)
            self.assertLess(md.index("Q1?"), md.index("## 4. The spine"))
        finally:
            if prev is None:
                os.environ.pop("SOAPBOXX_V3_FRAMING", None)
            else:
                os.environ["SOAPBOXX_V3_FRAMING"] = prev

    def test_proper_nouns_drop_common_single_word_fillers(self):
        import episode_reference_shelf as ers

        r = {
            "claims": [
                {
                    "id": "a1",
                    "text": (
                        "Because so for my podcast we hit the Daniel thread. "
                        "Which if I forget it, remind me about Babylon and Israel."
                    ),
                }
            ]
        }
        names = ers.proper_nouns_from_claims(r)
        self.assertIn("Daniel", names)
        self.assertIn("Babylon", names)
        self.assertNotIn("Because", names)
        self.assertNotIn("Which", names)


class TestProducerGradeExport(unittest.TestCase):
    def test_verification_hint_cdc(self):
        h = v3._verification_hint_for_claim_text("The CDC reported one in five kids in 2023.")
        self.assertIn("CDC.gov", h)

    def test_apply_evidence_verification_hints(self):
        r = {
            "evidence_mapping": [
                {
                    "id": "a1",
                    "claim": "CDC reported suicide statistics in 2023.",
                    "evidence": "quote",
                    "type": "factual",
                }
            ]
        }
        v3._apply_evidence_verification_hints(r)
        self.assertIn("verification_note", r["evidence_mapping"][0])

    def test_sensitive_readiness_surfaces_for_health_claims(self):
        r = {
            "claims": [{"id": "a1", "text": "The CDC reported suicide trends among teens."}],
        }
        lines = v3._sensitive_content_readiness_lines(r)
        self.assertTrue(any("Health" in ln for ln in lines))


class TestWorkflowAppendixPolish(unittest.TestCase):
    def test_short_non_actionable_claims_are_filtered_from_beats(self):
        bundle = {
            "report_v3": {
                "episode_snapshot": {"title": "Brainwash", "primary_topic": "education"},
                "claims": [{"id": "a1", "text": "Trying to win local schoolboard elections."}],
                "evidence_mapping": [
                    {
                        "id": "a1",
                        "claim": "Trying to win local schoolboard elections.",
                        "evidence": "Trying to win local schoolboard elections.",
                        "type": "interpretive",
                        "timestamp": None,
                    }
                ],
                "coach_report": {"immediate_fix_plan": [], "segment_upgrade": ""},
                "segments": [],
                "analytics_actionable": {},
                "engagement_questions": {},
            },
            "workflow_report": {"evidence_map": [], "highlights": [], "follow_up_questions": [], "segments": [], "analytics": {}},
        }
        md = v3.render_workflow_execution_appendix_markdown(bundle)
        self.assertIn("## 2. Key beats & pull quotes", md)
        self.assertIn("No evidence rows", md)

    def test_segment_planning_backfills_when_no_segments(self):
        bundle = {
            "report_v3": {
                "episode_snapshot": {"title": "Brainwash", "primary_topic": "education"},
                "claims": [],
                "evidence_mapping": [],
                "coach_report": {
                    "segment_upgrade": "Add a 90-second validation block before the close.",
                    "immediate_fix_plan": ["Confirm thesis vs tape.", "Cut one off-spine beat."],
                },
                "segments": [],
                "analytics_actionable": {},
                "engagement_questions": {},
            },
            "workflow_report": {"evidence_map": [], "highlights": [], "follow_up_questions": [], "segments": [], "analytics": {}},
        }
        md = v3.render_workflow_execution_appendix_markdown(bundle)
        self.assertIn("## 5. Segment Planning", md)
        self.assertIn("validation block", md.lower())


class TestArgumentRigor(unittest.TestCase):
    def test_argument_rigor_fails_on_vague_unmeasured_claim(self):
        r = {
            "coach_report": {
                "episode_thesis": "Centralization is bad for society.",
                "immediate_fix_plan": ["Think more critically."],
                "follow_up_questions": ["What if critics disagree?"],
            },
            "narrative_reconstruction": {},
            "evidence_mapping": [],
            "engagement_questions": {},
            "guests": [],
        }
        out = v3.evaluate_argument_rigor_report(r)
        self.assertIn("status", out)
        self.assertEqual(out["status"], "FAIL")
        self.assertLess(out["score"], 60)

    def test_argument_rigor_passes_structured_claim_and_evidence_mix(self):
        r = {
            "coach_report": {
                "episode_thesis": (
                    "Centralized education policy reduces student engagement, "
                    "measured by attendance rates."
                ),
                "immediate_fix_plan": [
                    "This week, check your district attendance trend report and compare pre/post mandate changes."
                ],
                "follow_up_questions": [
                    "What is the strongest counterargument to this claim and what evidence would overturn it?"
                ],
            },
            "narrative_reconstruction": {
                "supporting_mechanism": (
                    "Standardized curriculum policy -> reduced teacher autonomy -> lower student engagement"
                )
            },
            "evidence_mapping": [
                {
                    "id": "a1",
                    "claim": "CDC and NCES reported attendance and youth risk trends in 2023.",
                    "evidence": "Public table and district case example from 2023.",
                    "verification_note": "Confirm on CDC.gov primary releases.",
                }
            ],
            "engagement_questions": {
                "a1": {
                    "counterpunch": "What is the strongest counterexample and what data would prove us wrong?"
                }
            },
            "guests": [{"guest": "Diane Ravitch", "role": "historian"}],
        }
        out = v3.evaluate_argument_rigor_report(r)
        self.assertIn(out["status"], ("PASS", "REVIEW"))
        self.assertGreaterEqual(out["score"], 60)


class TestProducerReadyHeuristics(unittest.TestCase):
    def test_default_guest_blocks_neuro_not_education(self):
        rows = v3._default_expert_guest_blocks_for_topic(
            {"primary_topic": "neuroplasticity and sensory systems"},
            "Change Your Brain: Neuroscientist Guest | Example Podcast",
        )
        joined = " ".join(str(r.get("guest_type", "")) for r in rows).lower()
        self.assertIn("neuro", joined)
        self.assertNotIn("ravitch", joined)

    def test_thesis_stub_detects_through_line_wrapper(self):
        snap = {"title": "Example Title With Enough Characters Here"}
        self.assertTrue(
            v3._thesis_is_identity_stub(
                "The through-line for listeners: Example Title With Enough Characters Here",
                snap,
            )
        )


class TestSpineAndThesisQualityGates(unittest.TestCase):
    """Spine eligibility + thesis shallow/list coercion (aligned with lexical evidence engine)."""

    def test_promo_claim_tagged_and_omitted_from_spine(self):
        brief = {
            "episode_snapshot": {
                "title": "Habits Episode",
                "creator": "C",
                "genre": "Education",
                "primary_topic": "habits",
                "why_it_matters": "w",
            },
            "narrative": [],
            "claims": [
                {
                    "id": "c1",
                    "text": "Systems beat goals when motivation drops because routines persist.",
                    "claim_type": "interpretation",
                    "confidence": "high",
                    "why_it_matters": "m",
                },
                {
                    "id": "c2",
                    "text": "Sign up for our newsletter and buy the CRM plan pricing today.",
                    "claim_type": "interpretation",
                    "confidence": "high",
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
        transcript = "Host: Systems beat goals when motivation drops because routines persist."
        r = v3.build_v3_report(brief, transcript, metadata={}, atomic_ground_truth=False)
        rows = [c for c in (r.get("claims") or []) if isinstance(c, dict)]
        self.assertTrue(any(str(c.get("_spine_excluded_reason")) == "promo" for c in rows))
        spine = v3.build_episode_spine(r)
        blob = " ".join(str(c.get("line") or "") for c in (spine.get("claims") or [])).lower()
        self.assertIn("systems beat goals", blob)
        self.assertNotIn("crm", blob)

    def test_weak_transcript_anchor_omitted_from_spine(self):
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
                    "text": "Zyglotron flux capacitors reverse planetary entropy fields completely.",
                    "claim_type": "interpretation",
                    "confidence": "high",
                    "why_it_matters": "m",
                },
                {
                    "id": "c2",
                    "text": "Morning sunlight anchors circadian rhythm for better sleep onset.",
                    "claim_type": "interpretation",
                    "confidence": "high",
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
        transcript = (
            "Host: Morning sunlight anchors circadian rhythm for better sleep onset when exposure is early."
        )
        r = v3.build_v3_report(brief, transcript, metadata={}, atomic_ground_truth=False)
        spine = v3.build_episode_spine(r)
        lines = [str(c.get("line") or "") for c in (spine.get("claims") or [])]
        self.assertTrue(any("circadian" in x.lower() for x in lines))
        self.assertFalse(any("zyglotron" in x.lower() for x in lines))

    def test_thesis_list_semicolon_coerced_longer(self):
        snap = {
            "title": "Systems vs Goals Long Enough For Title",
            "creator": "Test",
            "genre": "Education",
            "primary_topic": "habit systems and routines",
            "why_it_matters": "w",
        }
        claims = [
            {
                "id": "c1",
                "text": "Systems beat goals when motivation drops because routines automate behavior daily.",
                "claim_type": "interpretation",
                "confidence": "high",
                "why_it_matters": "m",
            }
        ]
        out = v3._coerce_thesis_avoid_shallow_list_style(
            "topic; angle; stakes",
            snap,
            None,
            "HIGH_SIGNAL",
            claims,
            ["Systems outperform goals when motivation is unreliable."],
        )
        self.assertNotIn(";", out)
        self.assertGreaterEqual(len(out.split()), 6)

    def test_compute_report_readiness_insufficient_tape_metric(self):
        rr = v3.compute_report_readiness(
            "word " * 40,
            signal_mode="HIGH_SIGNAL",
            claim_count=2,
            evidence_row_count=3,
        )
        self.assertTrue((rr.get("metrics") or {}).get("insufficient_tape"))


if __name__ == "__main__":
    unittest.main()
