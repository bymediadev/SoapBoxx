"""Behavior locks for semantic claim–thesis alignment (deterministic local embed, mocked LLM)."""

from __future__ import annotations

import hashlib
import math
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import semantic_alignment as sa  # noqa: E402

# Python str hash is per-process; fallback embed uses it. Tests use a deterministic token hash.
_orig_embed = sa.embed


def _deterministic_embed(text: str, dim: int = 128) -> list:
    vec = [0.0] * dim
    toks = sa._tokenize(text)
    for tok in toks:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0:
        return vec
    return [v / norm for v in vec]


def setUpModule() -> None:  # type: ignore[no-untyped-def]
    sa.embed = _deterministic_embed  # type: ignore[assignment]


def tearDownModule() -> None:  # type: ignore[no-untyped-def]
    sa.embed = _orig_embed  # type: ignore[assignment]


def mock_support(_prompt: str) -> dict:
    return {"relation": "supports"}


def mock_mixed(prompt: str) -> dict:
    if "introduces" in prompt:
        return {"relation": "unrelated"}
    return {"relation": "weakly_supports"}


def mock_unrelated(_prompt: str) -> dict:
    return {"relation": "unrelated"}


class TestSemanticAlignmentCore(unittest.TestCase):
    def test_renormalization_without_llm_does_not_punish(self):
        # When the LLM path is off, (e, n) weights should renormalize to sum to 1 (not leave a 0.2 hole).
        with (
            patch.object(sa, "embedding_score", return_value=0.5),
            patch.object(sa, "nli_score", return_value=0.2),
        ):
            without = sa.semantic_alignment("t", "c", None)
            with_llm = sa.semantic_alignment("t", "c", mock_support)
        expected = (0.5 * 0.5 + 0.3 * 0.2) / (0.5 + 0.3)
        self.assertAlmostEqual(without, expected, places=5)
        # With a supports LLM, full 3-way mix should match the fixed 0.5/0.3/0.2 blend
        self.assertAlmostEqual(with_llm, 0.5 * 0.5 + 0.3 * 0.2 + 0.2 * 1.0, places=5)

    def test_top_k_focus_reduces_sway_of_garbage_claims(self):
        thesis = "x"
        # Ten claims: first five high scorers, last five near-zero; real semantic would vary.
        claims = [f"claim {i} with enough text for length gate over ten characters" for i in range(10)]
        with patch.object(sa, "semantic_alignment", side_effect=[0.9] * 5 + [0.01] * 5):
            score = sa.claim_alignment_score(thesis, claims, None)
        n = 10
        k = min(n, min(5, max(3, n // 3)))  # 3
        self.assertEqual(k, 3)
        # top_k_mean=0.9, support_ratio=0.5, raw=0.78, pstdev ≈0.445, dispersion_penalty ≈0.11125
        self.assertGreater(score, 0.5)
        self.assertAlmostEqual(score, 0.66875, places=4)

    def test_alignment_strong(self):
        thesis = "China is the main threat due to economic leverage and espionage against national security"
        claims = [
            "China economic leverage through trade dominance is a primary threat and shapes global policy "
            "toward China as a strategic rival in many regions",
            "Espionage operations linked to China target sensitive sectors and reinforce the view of China as "
            "the main threat alongside economic pressure in national security assessments",
        ]
        score = sa.claim_alignment_score(thesis, claims, mock_support)
        self.assertGreaterEqual(score, 0.7, msg=score)

    def test_alignment_mixed(self):
        thesis = "China is the main threat due to economic leverage and espionage"
        claims = [
            "China uses trade dominance to influence global policy and economic relationships in many regions",
            "The host introduces China policy by comparing economic leverage against smaller nations and "
            "reviewing espionage indicators that matter for national security audiences in this episode",
            "There are concerns about espionage tradecraft and state-linked activity tied to China over time "
            "in national security assessments",
        ]
        score = sa.claim_alignment_score(thesis, claims, mock_mixed)
        # Tighter top-k, support ratio, and dispersion can land mid-episode scores lower than
        # peak-only or tail-penalty-only models.
        self.assertGreaterEqual(score, 0.28, msg=score)
        self.assertLessEqual(score, 0.55, msg=score)

    def test_alignment_fail(self):
        thesis = "China; Israel; US Foreign Policy"
        claims = [
            "You can build a CRM using Odoo and customize modules for sales workflows in your business",
            "This guest is very interesting and brings a unique background to the conversation about many topics",
            "Pick the plan that works for your business and scale as you grow your team over time",
        ]
        score = sa.claim_alignment_score(thesis, claims, mock_unrelated)
        self.assertLess(score, 0.4, msg=score)

    def test_strong_episode_no_llm_not_silently_penalized_vs_old_formula(self):
        thesis = "China is the main threat due to economic leverage and espionage against national security"
        claims = [
            "China economic leverage through trade dominance is a primary threat and shapes global policy "
            "toward China as a strategic rival in many regions",
            "Espionage operations linked to China target sensitive sectors and reinforce the view of China as "
            "the main threat alongside economic pressure in national security assessments",
        ]
        with_llm = sa.claim_alignment_score(thesis, claims, mock_support)
        without = sa.claim_alignment_score(thesis, claims, None)
        # Without LLM, scores should be in the same ballpark as the LLM case (no missing-weight hole).
        self.assertGreaterEqual(without, 0.55, msg=without)
        self.assertLess(abs(with_llm - without), 0.2, msg=(with_llm, without))


class TestLowSupportCount(unittest.TestCase):
    def test_low_support_count_in_detail(self):
        claims = [f"claim {i} padded to exceed ten characters" for i in range(3)]
        with patch.object(sa, "semantic_alignment", side_effect=[0.35, 0.8, 0.7]):
            d = sa.claim_alignment_detail("thesis with enough words for the gate in this test", claims, None)
        self.assertEqual(d.get("low_support_count"), 1)


class TestAggregateAlignment(unittest.TestCase):
    def test_aggregate_stability_vector_numpy(self):
        s = [0.9] * 5 + [0.01] * 5
        score, dbg = sa.aggregate_alignment(s)
        self.assertAlmostEqual(score, 0.66875, places=4)
        self.assertEqual(dbg["n"], 10)
        self.assertEqual(dbg["k"], 3)


class TestSanityEpisodeShapes(unittest.TestCase):
    def test_sanity_a_strong_episode(self):
        thesis = (
            "China poses the primary long-term strategic threat to the US due to "
            "economic leverage and espionage capabilities."
        )
        claims = [
            "China invests heavily in global infrastructure that expands its economic and political influence.",
            "China conducts state-linked cyber espionage against government and private sector targets.",
            "US defense planning treats strategic competition with China as a top modernization driver.",
            "Persistent trade and capital imbalances shape leverage in technology and security policy.",
        ]
        with patch.object(sa, "semantic_alignment", return_value=0.8):
            d = sa.claim_alignment_detail(thesis, claims, mock_support)
        self.assertEqual(d["support_ratio"], 1.0, msg=d)
        self.assertEqual(d["std_dev"], 0.0, msg=d)
        self.assertGreaterEqual(d["score"], 0.7, msg=d)

    def test_sanity_c_half_noise_support_ratio(self):
        claims = [f"claim {i} padded enough for the minimum length" for i in range(8)]
        with patch.object(sa, "semantic_alignment", side_effect=[0.8] * 4 + [0.2] * 4):
            d = sa.claim_alignment_detail(
                "A thesis with enough words to clear the length gate in this sanity test", claims, None
            )
        self.assertAlmostEqual(d["support_ratio"], 0.5, places=1)


if __name__ == "__main__":
    unittest.main()
