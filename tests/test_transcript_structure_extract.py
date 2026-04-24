"""Rule-based caption structure bootstrap (no LLM)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import transcript_structure_extract as tse  # noqa: E402


class TestTranscriptStructureExtract(unittest.TestCase):
    def test_clean_caption_strips_header_and_merges(self) -> None:
        raw = (
            "Kind: captions Language: en\n"
            "Hi there. >> How are you?\n"
            "Fine thanks."
        )
        c = tse.clean_caption_transcript(raw)
        self.assertNotIn("Kind:", c)
        self.assertIn("Hi there", c)

    def test_strip_youtube_caption_metadata_repeated_chunks(self) -> None:
        raw = (
            "Kind: captions Language: en When most people think about the Old West.\n"
            "Kind: captions Language: en For every famous gunslinger there were dozens more."
        )
        s = tse.strip_youtube_caption_metadata(raw)
        self.assertNotIn("Kind:", s)
        self.assertIn("Old West", s)
        self.assertIn("gunslinger", s)

    def test_build_rows_two_grounded_minimum(self) -> None:
        # Two substantive sentences with a hint phrase
        raw = (
            "Kind: captions Language: en "
            "Over the last few years we have seen many changes in the market. "
            "The problem is that rates moved faster than expected. "
            "Listeners should track one theme per episode."
        )
        rows = tse.build_rule_based_evidence_rows(raw)
        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(r.get("confidence") == "low" for r in rows))
        self.assertTrue(all(r.get("source") == "rule_based_inference" for r in rows))
        tiers = {r.get("claim_strength") for r in rows}
        self.assertTrue(tiers.issubset({"moderate", "weak"}))
        self.assertTrue(any(r.get("claim_strength") == "moderate" for r in rows))

    def test_transition_fluff_rejected(self) -> None:
        s = "So yeah that's kind of what's been happening recently with the market."
        self.assertFalse(tse.acceptable_bootstrap_sentence(s))

    def test_causal_sentence_accepted(self) -> None:
        s = "Assets fell because interest rates increased faster than anyone expected."
        self.assertTrue(tse.contains_causal_or_directional_language(s))
        self.assertTrue(tse.acceptable_bootstrap_sentence(s))

    def test_jaccard_identity(self) -> None:
        t = tse.norm_claim_tokens("prices fell because interest rates rose quickly")
        self.assertEqual(tse.jaccard_similarity(t, t), 1.0)
        a = tse.norm_claim_tokens("prices fell because interest rates rose")
        b = tse.norm_claim_tokens("interest rates rose and prices fell because")
        self.assertGreater(tse.jaccard_similarity(a, b), 0.7)

    def test_primary_exactly_one(self) -> None:
        raw = (
            "Kind: captions Language: en "
            "Over the last few years we have seen many changes in the market. "
            "The problem is that rates moved faster than expected. "
            "Demand was strong but supply collapsed when policy shifted."
        )
        rows = tse.build_rule_based_evidence_rows(raw)
        self.assertGreaterEqual(len(rows), 2)
        primaries = [r for r in rows if r.get("primary") is True]
        self.assertEqual(len(primaries), 1)

    def test_contrast_boosts_strength(self) -> None:
        s = "Prices appeared stable, but demand actually weakened across the entire sector."
        self.assertTrue(tse.has_contrast_structure(s))

    def test_split_sentences(self) -> None:
        s = tse.split_sentences(
            "One two three four five six seven. "
            "Eight nine ten eleven twelve thirteen fourteen. "
            "Fifteen sixteen seventeen eighteen nineteen twenty."
        )
        self.assertGreaterEqual(len(s), 2)


if __name__ == "__main__":
    unittest.main()
