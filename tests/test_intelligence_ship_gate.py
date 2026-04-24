"""Tests for intelligence ship scoring (spine brief artifacts)."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import intelligence_ship_gate as isg  # noqa: E402


# Deterministic alignment metrics for tests that assert full weighted components (avoids Ollama / env).
_PASSING_ALIGNMENT_DETAIL = {
    "score": 0.75,
    "top_k_mean": 0.75,
    "support_ratio": 1.0,
    "std_dev": 0.0,
    "low_support_count": 0,
    "num_claims": 1,
    "n": 1,
    "k": 1,
    "support_score_threshold": 0.65,
}


def _bad_brief_for_alignment_gate() -> dict:
    return {
        "claims": [],
        "argument_spine": {
            "data": {
                "thesis": "A thesis string long enough to satisfy any downstream readers in this test.",
                "claims": [
                    {
                        "claim": "First supporting claim with enough text to be scored as a real claim in the suite.",
                    },
                    {
                        "claim": "Second supporting claim with enough text to be scored as a real claim in the suite.",
                    },
                ],
            }
        },
    }


class TestIntelligenceShipGate(unittest.TestCase):
    def test_absent_spine_returns_none(self):
        self.assertIsNone(isg.assess_brief_intelligence_ship({"claims": []}))

    def test_ship_gate_fails_unstructured_thesis_tag_list(self):
        brief = {
            "argument_spine": {
                "data": {
                    "thesis": (
                        "China; Israel; US Foreign Policy regional security and alliance dynamics in current debate"
                    ),
                    "claims": [
                        {
                            "claim": "Some claim text with enough characters to be scored as a claim in the alignment step.",
                        }
                    ],
                }
            }
        }
        out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("ship_gate"), "FAIL")
        self.assertIn("structured", " ".join(out.get("notes") or []).lower())

    def test_ship_gate_fails_too_short_thesis(self):
        brief = {
            "argument_spine": {
                "data": {
                    "thesis": "Only four words here thesis",
                    "claims": [
                        {
                            "claim": "A claim with enough text here to pass the minimum length for scoring in tests.",
                        }
                    ],
                }
            }
        }
        out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("ship_gate"), "FAIL")
        self.assertIn("vague", " ".join(out.get("notes") or []).lower())

    def test_minimal_spine_returns_pass_or_review(self):
        brief = {
            "episode_snapshot": {"title": "Test Episode Title", "creator": "AB", "genre": "News"},
            "claims": [
                {
                    "id": "c1",
                    "text": "Policy actors delay sensitive disclosures until after elections to reduce backlash risk.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "Because it matters for the story arc and listener takeaway.",
                    "counter_angle": "",
                    "next_action": "verify",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "argument_spine": {
                "thesis": "Policy pressure leads agencies to delay disclosures until after elections.",
                "claims": [],
                "metadata": {},
            },
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "strong", "issues": [], "rewrite": ""},
                    "claims_review": [{"id": "c1", "status": "strong", "issue": "", "suggestion": ""}],
                    "logic_gaps": [],
                    "counterarguments": [],
                    "evidence_review": {"overall": "strong", "issues": []},
                },
                "metadata": {"confidence": "high"},
            },
        }
        with patch.object(isg, "claim_alignment_detail", return_value=dict(_PASSING_ALIGNMENT_DETAIL)):
            out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn(out["ship_gate"], ("PASS", "REVIEW", "FAIL"))
        self.assertGreaterEqual(float(out["ship_score"]), 0.0)
        self.assertIn("thesis_strength", out["components"])
        self.assertIn("claim_alignment", out["components"])
        self.assertGreater(float(out["components"]["claim_alignment"]), 0.4)

    def test_weak_thesis_forces_fail(self):
        brief = {
            "episode_snapshot": {"title": "Test Episode Title", "creator": "AB", "genre": "News"},
            "claims": [
                {
                    "id": "c1",
                    "text": "Policy actors delay sensitive disclosures until after elections to reduce backlash risk.",
                    "claim_type": "interpretation",
                    "confidence": "high",
                    "why_it_matters": "Because it matters for the story arc and listener takeaway.",
                    "counter_angle": "",
                    "next_action": "verify",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "argument_spine": {
                "thesis": "Policy pressure leads agencies to delay disclosures until after elections.",
                "claims": [],
                "metadata": {},
            },
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "weak", "issues": ["vague"], "rewrite": "tighter"},
                    "claims_review": [{"id": "c1", "status": "strong", "issue": "", "suggestion": ""}],
                    "logic_gaps": [],
                    "counterarguments": [],
                    "evidence_review": {"overall": "strong", "issues": []},
                },
                "metadata": {"confidence": "high"},
            },
        }
        with patch.object(isg, "claim_alignment_detail", return_value=dict(_PASSING_ALIGNMENT_DETAIL)):
            out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["ship_gate"], "FAIL")
        self.assertTrue(any("weak thesis" in n.lower() for n in out.get("notes") or []))

    def test_claim_count_dampening_applied(self):
        brief = {
            "episode_snapshot": {"title": "Test Episode Title", "creator": "AB", "genre": "News"},
            "claims": [
                {
                    "id": "c1",
                    "text": "Policy actors delay sensitive disclosures until after elections to reduce backlash risk.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "Because it matters for the story arc and listener takeaway.",
                    "counter_angle": "",
                    "next_action": "verify",
                },
                {
                    "id": "c2",
                    "text": "Election season timing shapes how agencies release sensitive policy information publicly.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "Second claim matters for narrative continuity and listener takeaway.",
                    "counter_angle": "",
                    "next_action": "verify",
                },
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "argument_spine": {
                "thesis": "Policy pressure leads agencies to delay disclosures until after elections.",
                "claims": [],
                "metadata": {},
            },
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "strong", "issues": [], "rewrite": ""},
                    "claims_review": [],
                    "logic_gaps": [],
                    "counterarguments": [],
                    "evidence_review": {"overall": "strong", "issues": []},
                },
                "metadata": {"confidence": "high"},
            },
        }
        out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out.get("claim_count"), 2)
        self.assertEqual(out.get("claim_count_dampening"), 0.9)

    def test_fail_path_low_signal(self):
        brief = {
            "claims": [
                {
                    "id": "c1",
                    "text": "short",
                    "claim_type": "interpretation",
                    "confidence": "low",
                    "why_it_matters": "x",
                    "counter_angle": "",
                    "next_action": "verify",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "argument_spine": {"thesis": None, "claims": [], "metadata": {}},
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "weak", "issues": ["a"], "rewrite": ""},
                    "claims_review": [{"id": "c1", "status": "irrelevant", "issue": "x", "suggestion": ""}],
                    "logic_gaps": ["gap"] * 6,
                    "counterarguments": [],
                    "evidence_review": {"overall": "weak", "issues": ["weak_evidence", "anecdotal_only"]},
                },
                "metadata": {"confidence": "low"},
            },
            "argument_refined": {"data": {}, "metadata": {"refinement": {"status": "failed", "reason": "no_defensible_claims"}}},
        }
        out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertEqual(out["ship_gate"], "FAIL")

    def test_build_v3_report_includes_intelligence_ship(self):
        import episode_report_v3 as v3

        brief = {
            "episode_snapshot": {
                "title": "Episode Title Long Enough",
                "creator": "Host",
                "genre": "News genre",
                "primary_topic": "primary topic phrase long",
                "why_it_matters": "why this matters sentence here long enough",
                "argument_topic": "argument topic for intelligence consumers",
            },
            "narrative": ["First narrative bullet must be eighteen chars."],
            "claims": [
                {
                    "id": "c1",
                    "text": "Claim text here with enough length to pass schema validation rules easily now.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "Matter sentence long enough here.",
                    "counter_angle": "",
                    "next_action": "verify",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "seg", "goal": "goal text here"},
                "host_questions": ["Host question one is long enough?"],
                "clip_candidates": ["Clip candidate line long enough here."],
                "risk_note": "risk",
            },
            "guests": [
                {
                    "name": "Guest Name",
                    "title": "Title role",
                    "angle": "Angle text long enough for schema.",
                    "maps_to_claim_id": "c1",
                }
            ],
            "action_plan_7d": [
                {"day": "Day 1", "task": "Task description long enough for validation."},
                {"day": "Day 2", "task": "Second task description long enough here."},
                {"day": "Day 3", "task": "Third task description long enough here."},
            ],
            "argument_spine": {
                "thesis": "Causal thesis about incentives shaping outcomes in public policy.",
                "claims": [],
                "metadata": {},
            },
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "strong", "issues": [], "rewrite": ""},
                    "claims_review": [],
                    "logic_gaps": [],
                    "counterarguments": [],
                    "evidence_review": {"overall": "strong", "issues": []},
                },
                "metadata": {"confidence": "high"},
            },
        }
        r = v3.build_v3_report(brief, "word " * 400, metadata={})
        ship = (r.get("report_readiness") or {}).get("intelligence_ship")
        self.assertIsInstance(ship, dict)
        self.assertIn("ship_score", ship)
        self.assertIn(ship.get("ship_gate"), ("PASS", "REVIEW", "FAIL"))
        sm = (r.get("report_readiness") or {}).get("suggested_mode")
        self.assertIn(sm, ("internal_only", "review_required", "external_ok"))

    def test_refinement_delta_tracked(self):
        brief = {
            "episode_snapshot": {"title": "Test Episode Title", "creator": "AB", "genre": "News"},
            "claims": [
                {
                    "id": "c1",
                    "text": "Policy actors delay sensitive disclosures until after elections to reduce backlash risk.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "Because it matters for the story arc and listener takeaway.",
                    "counter_angle": "",
                    "next_action": "verify",
                    "refined_text": "Tightened policy disclosure timing claim around elections.",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "argument_spine": {
                "thesis": "Policy pressure leads agencies to delay disclosures until after elections.",
                "claims": [],
                "metadata": {},
            },
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "strong", "issues": [], "rewrite": ""},
                    "claims_review": [],
                    "logic_gaps": [],
                    "counterarguments": [],
                    "evidence_review": {"overall": "strong", "issues": []},
                },
                "metadata": {"confidence": "high"},
            },
            "argument_refined": {"data": {"thesis": "x", "claims": []}, "metadata": {}},
        }
        out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        assert out is not None
        self.assertIn("refinement_score_delta", out)
        self.assertIn("refinement_helped", out)

    def test_ship_gate_fails_low_alignment(self):
        brief = _bad_brief_for_alignment_gate()
        fake_detail = {
            "score": 0.1,
            "top_k_mean": 0.12,
            "support_ratio": 0.5,
            "std_dev": 0.1,
            "low_support_count": 1,
            "num_claims": 2,
            "n": 2,
            "k": 2,
            "support_score_threshold": 0.65,
        }
        with patch.object(isg, "claim_alignment_detail", return_value=fake_detail):
            out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("ship_gate"), "FAIL")
        notes = " ".join(out.get("notes") or [])
        self.assertIn("Low semantic alignment", notes)

    def test_support_coverage_clamp_to_review(self):
        brief = {
            "episode_snapshot": {"title": "Test Episode Title", "creator": "AB", "genre": "News"},
            "claims": [
                {
                    "id": "c1",
                    "text": "Policy actors delay sensitive disclosures until after elections to reduce backlash risk.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "Because it matters for the story arc and listener takeaway.",
                    "counter_angle": "",
                    "next_action": "verify",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "argument_spine": {
                "thesis": "Policy pressure leads agencies to delay disclosures until after elections.",
                "claims": [],
                "metadata": {},
            },
            "argument_critic": {
                "data": {
                    "thesis_review": {"status": "strong", "issues": [], "rewrite": ""},
                    "claims_review": [{"id": "c1", "status": "strong", "issue": "", "suggestion": ""}],
                    "logic_gaps": [],
                    "counterarguments": [],
                    "evidence_review": {"overall": "strong", "issues": []},
                },
                "metadata": {"confidence": "high"},
            },
        }
        d = dict(_PASSING_ALIGNMENT_DETAIL)
        d["support_ratio"] = 0.5
        d["score"] = 0.75
        with patch.object(isg, "claim_alignment_detail", return_value=d):
            out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("ship_gate"), "REVIEW")
        self.assertTrue(any("Support coverage" in n for n in (out.get("notes") or [])))

    def test_ship_gate_fails_low_support_ratio(self):
        brief = _bad_brief_for_alignment_gate()
        fake_detail = {
            "score": 0.85,
            "top_k_mean": 0.9,
            "support_ratio": 0.2,
            "std_dev": 0.12,
            "low_support_count": 8,
            "num_claims": 10,
            "n": 10,
            "k": 3,
            "support_score_threshold": 0.65,
        }
        with patch.object(isg, "claim_alignment_detail", return_value=fake_detail):
            out = isg.assess_brief_intelligence_ship(brief)
        self.assertIsNotNone(out)
        self.assertEqual(out.get("ship_gate"), "FAIL")
        self.assertIn("Most claims do not support thesis", " ".join(out.get("notes") or []))


if __name__ == "__main__":
    unittest.main()
