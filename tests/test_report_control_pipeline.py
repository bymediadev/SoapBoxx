# tests/test_report_control_pipeline.py
import unittest

from report_control_workflow import (
    assemble_report,
    auto_repair,
    classify_relationship,
    classify_relationship_hybrid,
    clean_transcript,
    clear_pipeline_error_log,
    get_pipeline_error_log,
    clear_report_score_history,
    compress_claim_rows,
    deduplicate,
    decide_report_action_v2,
    detect_soft_contradiction,
    enforce_claim_diversity,
    enforce_output_contract,
    extract_claims,
    extract_core_insight,
    extract_contrarian_line,
    has_contrarian_claim,
    has_thesis_tension,
    is_valid_claim,
    is_valid_thesis,
    log_errors,
    map_evidence,
    normalize_score,
    percentile_rank,
    repair_report_with_llm,
    resolve_core_insight,
    run_control_pipeline,
    score_argument_cohesion,
    score_claim_strength,
    score_clip_potential,
    score_evidence_strength,
    score_insight_novelty,
    score_report,
    store_report_score,
    summarize_errors,
    synthesize_core_insight,
    validate_clip_diversity,
    validate_output_contract,
    validate_report,
    ClaimRow,
    ControlReport,
)


class TestCleanTranscript(unittest.TestCase):
    def setUp(self) -> None:
        clear_pipeline_error_log()

    def test_year_stutter(self):
        self.assertIn("2019", clean_transcript("We left in 2019 2019 for the coast."))
        self.assertNotRegex(clean_transcript("We left in 2019 2019 for the coast."), r"2019\s+2019")

    def test_the_the(self):
        self.assertEqual(clean_transcript("It was the the same school.").lower().count("the the"), 0)


class TestMapAndValidate(unittest.TestCase):
    def setUp(self) -> None:
        clear_pipeline_error_log()

    def test_map_evidence_scores(self):
        chunks = [
            "The Rockefeller foundation funded early standardized testing pilots in districts.",
            "Unrelated banter about travel and an Airstream purchase.",
        ]
        claims = [
            ClaimRow(
                text="The Rockefeller foundation funded early standardized testing pilots in school districts.",
                evidence="",
                score=0.0,
            )
        ]
        out = map_evidence(claims, chunks, score_min=0.25, evidence_strength_min=0.35)
        self.assertGreater(out[0].score, 0.25)
        self.assertIn("Rockefeller", out[0].evidence)

    def test_validate_then_auto_repair(self):
        rep = ControlReport(
            title="T",
            thesis="Short",
            claims=[
                ClaimRow(text="x", evidence="", score=0.0),
                ClaimRow(
                    text="Philanthropic foundations shaped mass schooling through boards and grants.",
                    evidence="In 1925 the Rockefeller foundation funded district pilots that expanded testing mandates.",
                    score=0.75,
                ),
            ],
        )
        errs = validate_report(
            rep,
            thesis_min_words=8,
            evidence_score_min=0.6,
            min_claims=0,
            require_substantive_thesis=False,
        )
        self.assertTrue(errs)
        fixed = auto_repair(
            rep,
            errs,
            evidence_score_min=0.6,
            evidence_strength_min=0.35,
            claim_strength_min=0.45,
        )
        errs2 = validate_report(
            fixed,
            thesis_min_words=8,
            evidence_score_min=0.6,
            min_claims=0,
            require_substantive_thesis=False,
        )
        self.assertTrue(any("Thesis too short" in e for e in errs2))


class TestRunControlPipeline(unittest.TestCase):
    def setUp(self) -> None:
        clear_pipeline_error_log()
        clear_report_score_history()

    def test_end_to_end_returns_dict(self):
        tr = (
            "The Rockefeller foundation funded district pilot programs that expanded standardized testing in the 1990s. "
            "State boards later mandated annual assessments tied to those early pilots in several regions. "
            "Philanthropic grants continued to shape curriculum procurement rules through third-party vendors."
        )
        thesis = (
            "This episode argues that philanthropic institutions influenced mass schooling and testing "
            "policy in the United States."
        )
        data, errs, sc = run_control_pipeline(
            tr,
            thesis=thesis,
            title="Ep",
            max_repair_rounds=2,
            return_score=True,
            evidence_strength_min=0.38,
            evidence_score_min=0.38,
            claim_strength_min=0.45,
            relationship_llm_fn=lambda _p: "supports",
        )
        self.assertIn("claims", data)
        self.assertIn("thesis", data)
        self.assertIsInstance(data["claims"], list)
        self.assertGreaterEqual(sc, 0.0)
        self.assertLessEqual(sc, 1.0)
        self.assertIn("core_insight", data)
        self.assertTrue(str(data["core_insight"]).strip())
        self.assertIn("contrarian", data)
        self.assertGreaterEqual(len(data["clips"]), 2)
        self.assertLessEqual(len(data["clips"]), 3)
        self.assertIn("warnings", data)
        self.assertEqual(data["score_raw"], sc)
        self.assertIsInstance(data["score_normalized"], float)

    def test_return_decision_four_tuple(self):
        tr = (
            "The Rockefeller foundation funded district pilot programs that expanded standardized testing in the 1990s. "
            "State boards later mandated annual assessments tied to those early pilots in several regions. "
            "Philanthropic grants continued to shape curriculum procurement rules through third-party vendors."
        )
        thesis = (
            "This episode argues that philanthropic institutions influenced mass schooling and testing "
            "policy in the United States."
        )
        data, errs, sc, decision = run_control_pipeline(
            tr,
            thesis=thesis,
            title="Ep",
            max_repair_rounds=2,
            return_decision=True,
            evidence_strength_min=0.38,
            evidence_score_min=0.38,
            claim_strength_min=0.45,
            relationship_llm_fn=lambda _p: "supports",
        )
        self.assertIn("claims", data)
        self.assertGreaterEqual(sc, 0.0)
        self.assertLessEqual(sc, 1.0)
        self.assertIn(
            decision,
            ("publish", "publish_with_minor_edits", "revise_claims", "reprocess_transcript"),
        )
        self.assertEqual(decision, decide_report_action_v2(sc, errs))


class TestIntelligenceLayer(unittest.TestCase):
    def tearDown(self) -> None:
        clear_pipeline_error_log()
        clear_report_score_history()

    def test_insight_novelty_penalizes_vague(self):
        vague = "The education system has changed over time in various ways and remains important."
        self.assertLess(score_insight_novelty(vague), 0.5)

    def test_clip_potential_favors_short_punchy(self):
        long_line = " ".join(["word"] * 30) + "."
        short = "Rockefeller funding drove testing mandates statewide."
        self.assertGreaterEqual(score_clip_potential(short), score_clip_potential(long_line))

    def test_argument_cohesion_single_claim_neutral(self):
        self.assertGreater(score_argument_cohesion(["Only one complete sentence here."]), 0.0)

    def test_has_contrarian_claim_uses_relationship_fn(self):
        rows = [ClaimRow(text="Any claim.", evidence="", score=0.0)]
        self.assertTrue(has_contrarian_claim(rows, "Thesis.", lambda _a, _b: "contradicts"))
        self.assertFalse(has_contrarian_claim(rows, "Thesis.", lambda _a, _b: "supports"))

    def test_summarize_errors_counts(self):
        clear_pipeline_error_log()
        log_errors(["dup", "dup", "other"], "validate_report")
        agg = summarize_errors()
        self.assertEqual(agg["n"], 3)
        self.assertEqual(agg["error_counts"].get("dup"), 2)
        self.assertEqual(agg["most_common_error"], "dup")

    def test_score_report_accepts_relationship_llm_fn(self):
        rep = ControlReport(
            title="T",
            thesis="School testing expanded because state boards mandated annual assessments in districts.",
            claims=[
                ClaimRow(
                    text="Rockefeller pilots preceded wider district testing mandates in several states.",
                    evidence="The Rockefeller foundation funded district pilot programs that expanded standardized testing.",
                    score=0.75,
                ),
                ClaimRow(
                    text="Third-party vendors captured procurement rules after philanthropic grant conditions tightened.",
                    evidence="Philanthropic grants continued to shape curriculum procurement rules through third-party vendors.",
                    score=0.72,
                ),
                ClaimRow(
                    text="Annual assessments were not universally adopted without local political resistance.",
                    evidence="Some regions delayed mandates despite state board pressure in the 1990s.",
                    score=0.68,
                ),
            ],
            actions=["Look up your district testing timeline and compare it to state board records."],
        )
        s = score_report(rep, relationship_llm_fn=None)
        self.assertGreaterEqual(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_decide_report_action_v2_respects_errors(self):
        self.assertEqual(decide_report_action_v2(0.9, []), "publish")
        self.assertEqual(decide_report_action_v2(0.9, ["still broken"]), "publish_with_minor_edits")

    def test_percentile_rank(self):
        clear_report_score_history()
        store_report_score(0.2)
        store_report_score(0.5)
        store_report_score(0.9)
        self.assertAlmostEqual(percentile_rank(0.9), 1.0)
        self.assertAlmostEqual(percentile_rank(0.2), 1.0 / 3.0)

    def test_compress_claim_rows_drops_near_duplicate(self):
        a = ClaimRow(
            text="The Rockefeller foundation funded district pilot programs that expanded standardized testing.",
            evidence="e1",
            score=0.8,
        )
        b = ClaimRow(
            text="The Rockefeller foundation funded district pilot programs that expanded standardized testing in districts.",
            evidence="e2",
            score=0.78,
        )
        c = ClaimRow(
            text="Philanthropic grants shaped curriculum procurement rules through third-party vendors.",
            evidence="e3",
            score=0.75,
        )
        out = compress_claim_rows([a, b, c], threshold=0.85)
        self.assertGreaterEqual(len(out), 2)
        self.assertLessEqual(len(out), 3)

    def test_assemble_report_fills_surface_fields(self):
        rep = ControlReport(
            title="T",
            thesis="Philanthropic institutions influenced mass schooling and testing policy in the United States.",
            claims=[
                ClaimRow(
                    text="Rockefeller pilots expanded standardized testing mandates in several state systems.",
                    evidence="The Rockefeller foundation funded district pilot programs that expanded standardized testing.",
                    score=0.8,
                ),
                ClaimRow(
                    text="Third-party vendors captured procurement rules after grant conditions tightened.",
                    evidence="Philanthropic grants continued to shape curriculum procurement rules through third-party vendors.",
                    score=0.77,
                ),
                ClaimRow(
                    text="Annual assessments faced political resistance in some regions despite board pressure.",
                    evidence="State boards later mandated annual assessments tied to those early pilots in several regions.",
                    score=0.72,
                ),
            ],
        )
        d = assemble_report(rep)
        self.assertEqual(validate_output_contract(d), [])
        self.assertGreaterEqual(len(d["clips"]), 2)
        self.assertTrue(d["core_insight"].strip())

    def test_enforce_output_contract_raises(self):
        with self.assertRaises(ValueError):
            enforce_output_contract({"thesis": "", "claims": [], "core_insight": "", "clips": []})

    def test_detect_soft_contradiction(self):
        self.assertTrue(
            detect_soft_contradiction(
                "Standardized testing spread widely, however rural districts delayed mandates for years.",
                "x",
            )
        )
        self.assertFalse(detect_soft_contradiction("Standardized testing spread widely across urban districts.", "x"))

    def test_has_thesis_tension_soft(self):
        thesis = "Philanthropic funding always improved every school district without exception."
        rows = [
            ClaimRow(
                text="Philanthropic funding concentrated influence, but local boards sometimes resisted mandates.",
                evidence="e",
                score=0.8,
            )
        ]
        self.assertFalse(
            has_contrarian_claim(rows, thesis, lambda a, b: classify_relationship_hybrid(a, b, None))
        )
        self.assertTrue(has_thesis_tension(rows, thesis, relationship_llm_fn=None))

    def test_extract_contrarian_line_soft_fallback(self):
        thesis = "Policy X succeeded everywhere without tradeoffs."
        rows = [
            ClaimRow(
                text="Policy X succeeded in headline metrics, although implementation lagged in underfunded regions.",
                evidence="e",
                score=0.75,
            )
        ]
        line = extract_contrarian_line(rows, thesis, relationship_llm_fn=None)
        self.assertTrue(line)

    def test_validate_clip_diversity(self):
        self.assertTrue(validate_clip_diversity(["Rockefeller pilots expanded testing.", "Vendors rewrote procurement rules."]))
        self.assertFalse(
            validate_clip_diversity(
                [
                    "The Rockefeller foundation funded district pilot programs that expanded standardized testing.",
                    "The Rockefeller foundation funded district pilot programs that expanded standardized testing in districts.",
                ]
            )
        )

    def test_validate_output_contract_rejects_similar_clips(self):
        bad = {
            "thesis": "This episode argues that philanthropic institutions influenced mass schooling and testing policy.",
            "claims": [{"text": "a", "evidence": "b", "score": 0.7}] * 3,
            "core_insight": "Philanthropic institutions shaped testing adoption through district pilots.",
            "clips": [
                "The Rockefeller foundation funded district pilot programs that expanded standardized testing.",
                "The Rockefeller foundation funded district pilot programs that expanded standardized testing in districts.",
            ],
        }
        errs = validate_output_contract(bad)
        self.assertTrue(any("too similar" in e for e in errs))

    def test_normalize_score_rolling(self):
        self.assertEqual(normalize_score(0.5, []), 0.5)
        self.assertEqual(normalize_score(0.5, [0.5]), 0.5)
        self.assertEqual(normalize_score(0.75, [0.5, 0.5, 1.0]), 0.5)

    def test_synthesize_core_insight_mock(self):
        rows = [
            ClaimRow(
                text="Rockefeller networks funded early district pilots that normalized annual testing windows.",
                evidence="",
                score=0.0,
            ),
            ClaimRow(
                text="Third-party vendors later captured procurement language tied to those same grant conditions.",
                evidence="",
                score=0.0,
            ),
        ]

        def llm(_p: str) -> str:
            return "Grants linked district pilots to vendor-led procurement rules for testing."

        out = synthesize_core_insight(rows, llm)
        self.assertIsNotNone(out)
        self.assertTrue(out.endswith("."))
        self.assertLessEqual(len(out.split()), 20)

    def test_resolve_core_insight_prefers_synthesis_when_triggered(self):
        rows = [
            ClaimRow(
                text="The education system has changed over time in various ways and remains important.",
                evidence="",
                score=0.0,
            ),
            ClaimRow(
                text="Philanthropic grants continued to shape curriculum procurement rules through third-party vendors.",
                evidence="",
                score=0.0,
            ),
        ]

        def llm(_p: str) -> str:
            return "Philanthropic grants steered procurement rules through vendor contracts."

        out = resolve_core_insight(rows, llm_fn=llm, synthesis_novelty_trigger=0.99)
        self.assertIn("Philanthropic", out)


class TestStrictClaimExtraction(unittest.TestCase):
    def test_rejects_discourse_then_like_line(self):
        tr = (
            "Then like back engineering how to do all the equipment on a podcast "
            "going off about ten to fifteen shows is exhausting work."
        )
        out = extract_claims(clean_transcript(tr))
        self.assertEqual(out, [])

    def test_rejects_vacuous_valid_grammar(self):
        weak = "The education system has changed over time in various ways."
        self.assertLess(score_claim_strength(weak), 0.6)
        self.assertFalse(is_valid_claim(weak))


class TestClassifyRelationship(unittest.TestCase):
    def test_centralized_education_vs_society(self):
        claim = "Public education systems became highly centralized in the twentieth century."
        ev = "Society in general moved toward centralization in many institutions over time."
        self.assertEqual(classify_relationship(claim, ev), "irrelevant")

    def test_hybrid_high_similarity_stays_heuristic(self):
        a = "The Rockefeller foundation funded early testing pilots in districts."
        b = "The Rockefeller foundation funded early testing pilots in districts across states."
        h = classify_relationship_hybrid(a, b, llm_fn=lambda _p: "irrelevant")
        self.assertEqual(h, "supports")

    def test_repair_report_with_llm_mock(self):
        rep = ControlReport(title="T", thesis="x", claims=[])
        out, err = repair_report_with_llm(rep, ["bad"], lambda _p: "not json")
        self.assertTrue(any("invalid JSON" in e for e in err))
        self.assertEqual(out.thesis, "x")


class TestThesisAndDiversity(unittest.TestCase):
    def test_is_valid_thesis_requires_substance(self):
        self.assertFalse(is_valid_thesis("Education matters a lot to people every day here."))
        good = (
            "This episode argues that philanthropic funding shaped standardized testing adoption "
            "because districts relied on external grants for early pilot programs."
        )
        self.assertTrue(is_valid_thesis(good))

    def test_enforce_claim_diversity(self):
        rows = [
            ClaimRow(text="Rockefeller grants expanded testing pilots in urban districts.", evidence="e1", score=0.8),
            ClaimRow(
                text="Rockefeller funding expanded standardized testing pilots in city districts.",
                evidence="e2",
                score=0.75,
            ),
            ClaimRow(
                text="State wildlife agencies tracked elk migration across the northern Rockies.",
                evidence="e3",
                score=0.7,
            ),
        ]
        div = enforce_claim_diversity(rows, cluster_threshold=0.82)
        self.assertLessEqual(len(div), len(rows))
        self.assertGreaterEqual(len(div), 1)


class TestLogErrors(unittest.TestCase):
    def tearDown(self) -> None:
        clear_pipeline_error_log()

    def test_log_appends(self):
        clear_pipeline_error_log()
        log_errors(["a"], "unit", extra={"k": 1})
        snap = get_pipeline_error_log()
        self.assertEqual(len(snap), 1)
        self.assertEqual(snap[-1]["stage"], "unit")


class TestDeduplicate(unittest.TestCase):
    def test_dedupe_strings(self):
        self.assertEqual(
            deduplicate(["hello world", "hello world", "totally different phrase"]),
            ["hello world", "totally different phrase"],
        )


class TestEvidenceStrength(unittest.TestCase):
    def test_vague_evidence_scores_lower(self):
        claim = "Rockefeller influence shaped education policy in several states."
        vague = "They have been involved historically in many ways."
        concrete = "In 1925 the foundation funded district pilots tied to standardized testing mandates."
        self.assertLess(score_evidence_strength(claim, vague), score_evidence_strength(claim, concrete))


if __name__ == "__main__":
    unittest.main()
