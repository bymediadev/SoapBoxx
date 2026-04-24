"""Unit tests for spine-first + critic brief mapping (no Ollama)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_intelligence as ei  # noqa: E402
import spine_first_brief as sfb  # noqa: E402


class TestSpineFirstBrief(unittest.TestCase):
    def test_validate_pass1_rejects_bad_envelope(self):
        ok, err = sfb.validate_spine_pass1({"data": {}, "metadata": {}})
        self.assertFalse(ok)
        self.assertIn("claims", err)

    def test_validate_pass1_accepts_minimal(self):
        obj = {
            "data": {
                "thesis": "Policy X drives outcome Y because incentives shift behavior.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Administrative burden reduces compliance among small districts significantly.",
                        "evidence": "Host cites survey showing 40% delay.",
                        "timestamp": "12:40",
                    }
                ],
            },
            "metadata": {"quality": {}, "warnings": []},
        }
        self.assertTrue(sfb.validate_spine_pass1(obj)[0])

    def test_map_merges_critic_into_v2(self):
        p1 = {
            "data": {
                "thesis": "Funding volatility forces schools to optimize for optics over learning outcomes.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Short-term grants create planning horizons shorter than one academic cycle.",
                        "evidence": "Example of mid-year program cuts.",
                        "timestamp": "05:10",
                    }
                ],
            },
            "metadata": {"warnings": ["weak_thesis"]},
        }
        p2 = {
            "data": {
                "thesis_review": {
                    "status": "weak",
                    "issues": ["Overbroad causality"],
                    "rewrite": "Tighter thesis about grant cycles and curriculum stability.",
                },
                "claims_review": [
                    {
                        "id": "c1",
                        "status": "strong",
                        "issue": "",
                        "suggestion": "",
                    }
                ],
                "logic_gaps": ["Jumps from anecdote to system claim without intermediate step."],
                "counterarguments": ["Correlation between volatility and outcomes may be confounded."],
                "evidence_review": {"overall": "mixed", "issues": ["anecdotal_only"]},
            },
            "metadata": {"critic_mode": "hostile", "confidence": "medium"},
        }
        v2 = sfb.map_spine_critic_to_v2_brief(
            p1,
            p2,
            {"title": "School Finance Episode", "creator": "Host Co", "genre": "Education"},
        )
        self.assertIn("argument_spine", v2)
        self.assertIn("argument_critic", v2)
        self.assertEqual(v2["episode_snapshot"]["title"], "School Finance Episode")
        self.assertTrue(v2.get("claims"))
        self.assertEqual(v2["claims"][0]["id"], "c1")
        self.assertIn("Funding volatility", v2["episode_snapshot"]["primary_topic"])
        eg = v2.get("evidence_gaps") or {}
        weak = " ".join(str(x).lower() for x in (eg.get("weak_or_unsupported") or []))
        self.assertIn("anecdotal", weak)
        self.assertTrue(v2.get("production_moves", {}).get("risk_note"))

    def test_generate_episode_brief_uses_spine_when_flagged(self):
        p1 = {
            "data": {
                "thesis": "Market structure shapes incentives so participants optimize rent-seeking.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Concentrated liquidity pools amplify tail risk during stress events.",
                        "evidence": "Panel discusses flash events and dealer inventory.",
                        "timestamp": "00:15",
                    }
                ],
            },
            "metadata": {
                "warnings": [],
                "quality": {
                    "thesis_valid": True,
                    "claims_count": 1,
                    "argument_coherence": "medium",
                },
            },
        }
        p2 = {
            "data": {
                "thesis_review": {"status": "weak", "issues": ["vague"], "rewrite": ""},
                "claims_review": [
                    {"id": "c1", "status": "strong", "issue": "", "suggestion": ""},
                ],
                "logic_gaps": [],
                "counterarguments": [],
                "evidence_review": {"overall": "strong", "issues": []},
            },
            "metadata": {"critic_mode": "hostile", "confidence": "high"},
        }
        seq = [json.dumps(p1, ensure_ascii=False), json.dumps(p2, ensure_ascii=False)]

        def fake_invoke(system: str, user: str, **kwargs):
            return seq.pop(0)

        with patch.dict(
            os.environ,
            {
                "SOAPBOXX_OLLAMA_MODEL": "stub",
                "SOAPBOXX_BRIEF_STRICT_CONTRACT": "1",
                "SOAPBOXX_BRIEF_SPINE_FIRST": "1",
                "SOAPBOXX_BRIEF_SPINE_REFINE": "0",
                "SOAPBOXX_OFFLINE": "0",
            },
            clear=False,
        ):
            with patch.object(ei, "_ollama_chat_invoke", side_effect=fake_invoke):
                r = ei.generate_episode_brief(
                    "transcript " * 80,
                    {"title": "Markets Episode", "creator": "AC", "genre": "Business"},
                )
        brief = r["brief"]
        self.assertIn("argument_spine", brief)
        self.assertIn("argument_critic", brief)
        self.assertTrue(brief.get("claims"))
        self.assertNotIn("argument_refined", brief)

    def test_validate_refiner_rejects_hard_failure_envelope(self):
        bad = {"data": {}, "metadata": {"error": "failed_to_generate"}}
        self.assertFalse(sfb.validate_refiner_pass3(bad)[0])

    def test_map_refined_adds_argument_refined_and_norms_a_ids(self):
        p1 = {
            "data": {
                "thesis": "Original thesis is too broad for the evidence shown.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "First pass claim text that is long enough to validate easily here.",
                        "evidence": "Host statement.",
                        "timestamp": "01:00",
                    },
                    {
                        "id": "c2",
                        "claim": "Second pass claim about grants and school planning cycles in the episode.",
                        "evidence": "Budget segment.",
                        "timestamp": "03:00",
                    },
                ],
            },
            "metadata": {},
        }
        p2 = {
            "data": {
                "thesis_review": {"status": "weak", "issues": ["too broad"], "rewrite": "narrow"},
                "claims_review": [],
                "logic_gaps": [],
                "counterarguments": [],
                "evidence_review": {"overall": "weak", "issues": []},
            },
            "metadata": {},
        }
        p3 = {
            "data": {
                "thesis": "Narrow fiscal shocks force short-term optics that crowd out curriculum depth.",
                "claims": [
                    {
                        "id": "a1",
                        "claim": "First pass claim text tightened for clarity without changing substance.",
                        "evidence": "Discussion of mid-year rescissions.",
                        "timestamp": "06:00",
                    },
                    {
                        "id": "a2",
                        "claim": "Second pass claim about grants and school planning cycles tightened here.",
                        "evidence": "Budget segment.",
                        "timestamp": "07:00",
                    },
                ],
                "counterpoints": [{"point": "Confounding by local politics", "response": "Acknowledged as residual risk."}],
            },
            "metadata": {
                "refinement": {"thesis_changed": True, "claims_reduced": True, "issues_remaining": []},
                "warnings": [],
            },
        }
        v2 = sfb.map_spine_critic_refined_to_v2_brief(
            p1,
            p2,
            p3,
            {"title": "Test Episode Title Here", "creator": "AC", "genre": "Education"},
        )
        self.assertIn("argument_refined", v2)
        self.assertEqual(v2["claims"][0]["id"], "c1")
        self.assertIn("First pass claim text that is long enough", v2["claims"][0]["text"])
        self.assertIn("tightened for clarity", (v2["claims"][0].get("refined_text") or "").lower())
        self.assertIn("Narrow fiscal", v2["episode_snapshot"]["argument_topic"])
        self.assertNotIn("Grant horizons", v2["claims"][0]["text"])
        sup = " ".join(v2["evidence_gaps"]["supported"])
        self.assertIn("Counterpoint", sup)

    def test_promotion_false_refiner_advisory_only(self):
        p1 = {
            "data": {
                "thesis": "Policy design shapes compliance behavior in school districts.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Administrative burden reduces compliance among small districts significantly.",
                        "evidence": "Survey.",
                        "timestamp": "1:00",
                    },
                    {
                        "id": "c2",
                        "claim": "Second administrative claim about paperwork and reporting delays in districts.",
                        "evidence": "Interview.",
                        "timestamp": "2:00",
                    },
                ],
            },
            "metadata": {},
        }
        p2 = {
            "data": {
                "thesis_review": {"status": "strong", "issues": [], "rewrite": ""},
                "claims_review": [],
                "logic_gaps": [],
                "counterarguments": [],
                "evidence_review": {"overall": "strong", "issues": []},
            },
            "metadata": {},
        }
        p3 = {
            "data": {
                "thesis": "Totally different thesis about moon rocks.",
                "claims": [
                    {"id": "c1", "claim": "Moon rocks drive compliance.", "evidence": "x", "timestamp": ""},
                    {"id": "c2", "claim": "Second moon claim about rocks and schools.", "evidence": "y", "timestamp": ""},
                ],
                "counterpoints": [],
            },
            "metadata": {"refinement": {"issues_remaining": []}},
        }
        v2 = sfb.map_spine_critic_refined_to_v2_brief(p1, p2, p3, {"title": "Education Policy Hour", "creator": "AC", "genre": "Education"})
        self.assertFalse(v2["claims"][0].get("refined_text"))
        self.assertTrue(any("advisory" in str(x).lower() for x in (v2.get("evidence_gaps") or {}).get("supported") or []))
        self.assertIn("policy", (v2["episode_snapshot"].get("argument_topic") or "").lower())
        self.assertNotIn("moon", (v2["episode_snapshot"].get("argument_topic") or "").lower())

    def test_empty_pass3_claims_sets_refinement_failed(self):
        p1 = {
            "data": {
                "thesis": "Thesis one sentence causal claim about policy and outcomes here.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Administrative burden reduces compliance among small districts significantly.",
                        "evidence": "Survey.",
                        "timestamp": "1:00",
                    }
                ],
            },
            "metadata": {},
        }
        p2 = {"data": {"thesis_review": {"status": "weak", "issues": [], "rewrite": ""}}, "metadata": {}}
        p3 = {"data": {"thesis": None, "claims": [], "counterpoints": []}, "metadata": {"refinement": {}}}
        v2 = sfb.map_spine_critic_refined_to_v2_brief(
            p1, p2, p3, {"title": "Education Policy Hour", "creator": "AC", "genre": "Education"}
        )
        ar = v2.get("argument_refined") or {}
        rf = (ar.get("metadata") or {}).get("refinement") or {}
        self.assertEqual(rf.get("status"), "failed")
        self.assertEqual(rf.get("reason"), "no_defensible_claims")

    def test_is_semantic_drift_detects_unrelated_text(self):
        self.assertTrue(sfb.is_semantic_drift("cats and dogs on mars", "quantitative easing reduces bank lending"))
        self.assertFalse(
            sfb.is_semantic_drift(
                "Soft budgets defer cuts until pressure spikes.",
                "Soft budgets let managers defer cuts until funding pressure spikes.",
            )
        )

    def test_generate_episode_brief_three_pass_when_refine_on(self):
        p1 = {
            "data": {
                "thesis": "Incentives shape outcomes when monitoring is costly.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Soft budgets let managers defer hard tradeoffs until external pressure spikes.",
                        "evidence": "Case walkthrough.",
                        "timestamp": "02:00",
                    },
                    {
                        "id": "c2",
                        "claim": "Incentive gaps widen when oversight is costly and reporting is delayed in firms.",
                        "evidence": "Panel segment.",
                        "timestamp": "03:00",
                    },
                ],
            },
            "metadata": {"warnings": [], "quality": {"argument_coherence": "medium"}},
        }
        p2 = {
            "data": {
                "thesis_review": {"status": "weak", "issues": [], "rewrite": "Tighter"},
                "claims_review": [{"id": "c1", "status": "weak", "issue": "Vague", "suggestion": "Name mechanism"}],
                "logic_gaps": [],
                "counterarguments": ["Selection on observables"],
                "evidence_review": {"overall": "mixed", "issues": []},
            },
            "metadata": {"confidence": "medium"},
        }
        p3 = {
            "data": {
                "thesis": "When monitoring is costly, incentive misalignment produces delayed corrections.",
                "claims": [
                    {
                        "id": "c1",
                        "claim": "Soft budgets let managers defer hard tradeoffs until external pressure spikes.",
                        "evidence": "Narrative case.",
                        "timestamp": "02:05",
                    },
                    {
                        "id": "c2",
                        "claim": "Incentive gaps widen when oversight is costly and reporting is delayed.",
                        "evidence": "Panel note.",
                        "timestamp": "03:00",
                    },
                ],
                "counterpoints": [],
            },
            "metadata": {"refinement": {"thesis_changed": True, "claims_reduced": False, "issues_remaining": []}, "warnings": []},
        }
        seq = [json.dumps(x, ensure_ascii=False) for x in (p1, p2, p3)]
        call_n = {"i": 0}

        def fake_invoke(system: str, user: str, **kwargs):
            call_n["i"] += 1
            if call_n["i"] == 3:
                self.assertNotIn("TRANSCRIPT", user or "")
                self.assertIn("pass_2_hostile_critique", user)
            return seq.pop(0)

        with patch.dict(
            os.environ,
            {
                "SOAPBOXX_OLLAMA_MODEL": "stub",
                "SOAPBOXX_BRIEF_STRICT_CONTRACT": "1",
                "SOAPBOXX_BRIEF_SPINE_FIRST": "1",
                "SOAPBOXX_BRIEF_SPINE_REFINE": "1",
                "SOAPBOXX_OFFLINE": "0",
            },
            clear=False,
        ):
            with patch.object(ei, "_ollama_chat_invoke", side_effect=fake_invoke):
                r = ei.generate_episode_brief(
                    "transcript " * 80,
                    {
                        "title": "Organizational incentives under pressure",
                        "creator": "AC",
                        "genre": "Business",
                    },
                )
        brief = r["brief"]
        self.assertIn("argument_refined", brief)
        self.assertTrue(brief.get("claims"))
        thesis_r = str((brief.get("argument_refined") or {}).get("data", {}).get("thesis") or "")
        self.assertIn("monitoring", thesis_r.lower())


if __name__ == "__main__":
    unittest.main()
