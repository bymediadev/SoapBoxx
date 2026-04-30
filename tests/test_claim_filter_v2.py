"""Unit tests for backend/claim_filter_v2 (SOAPBOXX v2 claim entry gate)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import claim_filter_v2 as cf  # noqa: E402


class TestClaimFilterV2(unittest.TestCase):
    def test_output_shape(self):
        out = cf.filter_claim_candidates(
            [
                {"source_segment_id": "s0", "text": "irrelevant"},
            ],
            mode="debug",
        )
        self.assertIn("accepted_claims", out)
        self.assertIn("rejected_claims", out)
        self.assertEqual(out.get("stage"), cf.STAGE_CLAIM_FILTER)
        self.assertIsInstance(out["accepted_claims"], list)
        self.assertIsInstance(out["rejected_claims"], list)
        for side in (out["accepted_claims"], out["rejected_claims"]):
            for row in side:
                self.assertIn("text", row)
                self.assertIn("source_segment_id", row)
                self.assertIn("decision", row)
                self.assertIn("reason_codes", row)
                self.assertIn("stage", row)
                self.assertIn("score_breakdown", row)

    def test_accepts_substantive_assertion(self):
        t = (
            "Policy pressure means public agencies often delay sensitive disclosures after elections "
            "because the perceived timing cost outweighs the transparency benefit in the short term."
        )
        r = cf.filter_claim_candidates([("s1", t)], mode="debug")
        self.assertEqual(len(r["accepted_claims"]), 1, msg=r)
        row = r["accepted_claims"][0]
        self.assertEqual(row.get("decision"), "ACCEPTED")
        self.assertIn("HIGH_INFORMATION_WEIGHT", row.get("reason_codes") or [])
        self.assertEqual(len(r["rejected_claims"]), 0)

    def test_rejects_filler(self):
        r = cf.filter_claim_candidates([("s2", "yeah")])
        self.assertEqual(len(r["rejected_claims"]), 1)
        self.assertEqual(r["rejected_claims"][0]["rejection_reason"], cf.R_FILLER)

    def test_rejects_welcome_scaffolding(self):
        r = cf.filter_claim_candidates(
            [("s3", "Welcome to the show, we are so glad you could join us this evening for this conversation.")]
        )
        # Either hard list or broad structural_speech; must not land in accepted
        self.assertEqual(len(r["accepted_claims"]), 0)
        self.assertEqual(len(r["rejected_claims"]), 1)
        self.assertIn(
            r["rejected_claims"][0]["rejection_reason"],
            (cf.R_HARD_PODCAST_SCAFFOLD, cf.R_STRUCTURAL_SPEECH),
        )

    def test_rejects_host_framing(self):
        r = cf.filter_claim_candidates(
            [("s4", "Today we are talking about leadership and we have a great conversation ahead.")]
        )
        self.assertEqual(len(r["accepted_claims"]), 0)

    def test_rejects_meta_commentary(self):
        r = cf.filter_claim_candidates(
            [("s5", "What I want to talk about is how we might frame the next segment without a real thesis.")]
        )
        self.assertEqual(r["rejected_claims"][0]["rejection_reason"], cf.R_HARD_META_COMMENTARY)

    def test_rejects_emotional_praise(self):
        r = cf.filter_claim_candidates([("s6", "It was amazing.")])
        self.assertEqual(r["rejected_claims"][0]["rejection_reason"], cf.R_HARD_EMOTIONAL_FILLER)

    def test_rejects_promo_pattern(self):
        r = cf.filter_claim_candidates(
            [("s7", "You should use our free trial and sign up for the CRM onboarding flow today.")]
        )
        self.assertEqual(r["rejected_claims"][0]["rejection_reason"], cf.R_HARD_PROMO_BUSINESS)

    def test_rejects_multi_topic_drift(self):
        t = "Farm policy shifts soil incentives; foreign exchange volatility affects import prices in urban retail."
        r = cf.filter_claim_candidates([("s8", t)])
        self.assertEqual(r["rejected_claims"][0]["rejection_reason"], cf.R_MULTI_TOPIC_DRIFT)

    def test_tuple_and_dict_segments(self):
        r1 = cf.filter_claim_candidates([("a", "Short.")])
        r2 = cf.filter_claim_candidates([{"id": "b", "text": "Short."}])
        self.assertEqual(r1["rejected_claims"][0]["source_segment_id"], "a")
        self.assertEqual(r2["rejected_claims"][0]["source_segment_id"], "b")

    def test_explain_verdict(self):
        d = cf.explain_verdict("A substantive claim is needed because the mechanism matters for the outcome here.")
        self.assertTrue(d["semantic_complete"])
        self.assertTrue(d["information_weight_present"])
        self.assertTrue(d.get("is_causal_claim"))

    def test_rejects_non_causal_topic_label_when_score_passes(self):
        t = (
            "This means logistics automation timelines compress hiring windows across Midwest distribution hubs "
            "while vendor contracts stay fixed for renewal cycles under current procurement rules."
        )
        r = cf.filter_claim_candidates([("nc", t)], mode="debug")
        self.assertEqual(len(r["accepted_claims"]), 0, msg=r)
        self.assertEqual(r["rejected_claims"][0].get("rejection_reason"), cf.R_NOT_CAUSAL)
        self.assertIn("NON_CAUSAL_STATEMENT", r["rejected_claims"][0].get("reason_codes") or [])

    def test_non_causal_gate_off_accepts_topic_coherence(self):
        t = (
            "This means logistics automation timelines compress hiring windows across Midwest distribution hubs "
            "while vendor contracts stay fixed for renewal cycles under current procurement rules."
        )
        with patch.dict(os.environ, {"SOAPBOXX_CLAIM_REQUIRE_CAUSAL": "0"}):
            r = cf.filter_claim_candidates([("nc2", t)], mode="debug")
        self.assertEqual(len(r["accepted_claims"]), 1, msg=r)

    def test_production_mode_includes_slim_rejects(self):
        out = cf.filter_claim_candidates(
            [("s1", "yeah")], mode="production", return_internal_debug_trace=True
        )
        self.assertNotIn("score_breakdown", out["rejected_claims"][0])
        self.assertIn("reason_codes", out["rejected_claims"][0])
        self.assertIn("_claim_filter_debug_full", out)
        self.assertIn("score_breakdown", out["_claim_filter_debug_full"]["rejected_claims"][0])


class TestPipelineRealityStrings(unittest.TestCase):
    """Category A–C examples (failure-mode calibration; strings from product spec)."""

    def _one(self, text: str) -> tuple:
        out = cf.filter_claim_candidates([("t", text)])
        return out["accepted_claims"], out["rejected_claims"]

    def test_category_a_rejects(self):
        a1 = (
            "There's a lot of people that I get excited to interview and you are the top of the list."
        )
        a2 = (
            "Folks, if you are a small business owner, you understand the challenges that come with that job."
        )
        a3 = "You can build a custom CRM on ODO that helps manage clients."
        for t in (a1, a2, a3):
            acc, rej = self._one(t)
            self.assertEqual(len(acc), 0, msg=repr(t))
            self.assertEqual(len(rej), 1, msg=repr(t))

    def test_category_b(self):
        b1 = "Israel believes it is alone in the world, even though it is not."
        b2 = "The US defense budget is a little over $1 trillion."
        b3 = "China is the greatest threat to US national security."
        a1, r1 = self._one(b1)
        a2, r2 = self._one(b2)
        a3, r3 = self._one(b3)
        self.assertEqual(len(a1), 0, "high-abstraction nation belief should not pass the gate as-is")
        self.assertEqual(len(r1), 1)
        self.assertEqual(len(a2), 1, "numeric budget line should pass as factual_tentative")
        self.assertGreaterEqual(a2[0].get("claim_score", 0), cf.CLAIM_SCORE_MIN)
        self.assertEqual(len(a3), 0, "opinion-as-superlative security claim should be rejected or flagged")
        self.assertEqual(len(r3), 1)

    def test_category_c_accepts(self):
        c1 = "He told me I was being monitored by intelligence services during prior meetings."
        c2 = (
            "The guest states that US foreign policy decisions are influenced more by intelligence agencies "
            "than elected officials."
        )
        c3 = "The speaker describes being instructed to attend a meeting where they believed they could be harmed."
        for t in (c1, c2, c3):
            acc, rej = self._one(t)
            self.assertEqual(len(acc), 1, msg=repr(t))
            self.assertGreaterEqual(acc[0].get("claim_score", 0), cf.CLAIM_SCORE_MIN, msg=repr(t))


class TestApplyToBriefHook(unittest.TestCase):
    def test_apply_drops_social_scaffold(self):
        data = {
            "claims": [
                {"id": "c1", "text": "He told me I was monitored during the meetings."},
                {
                    "id": "c2",
                    "text": "There's a lot of people that I get excited to interview and you are the top of the list.",
                },
            ],
            "_quality_warnings": [],
        }
        with patch.dict(
            os.environ,
            {
                "SOAPBOXX_CLAIM_FILTER_V2": "1",
                "SOAPBOXX_CLAIM_FILTER_MODE": "debug",
            },
        ):
            cf.apply_claim_filter_v2_to_brief(data, transcript_context="x x x")
        self.assertEqual(len(data["claims"]), 1)
        self.assertEqual(data["claims"][0]["id"], "c1")
        tr = data.get("_claim_filter_v2") or {}
        self.assertEqual(tr.get("n_in"), 2)
        self.assertEqual(tr.get("n_out"), 1)


if __name__ == "__main__":
    unittest.main()
