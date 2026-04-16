# tests/test_episode_quality_gates.py
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_quality_gates as qg  # noqa: E402
import episode_report_v3 as v3  # noqa: E402


class TestEpisodeQualityGates(unittest.TestCase):
    def test_religious_mismatch_resets_primary_in_repair(self):
        snap = {
            "title": "Revisiting Sara Underwood",
            "creator": "Girls Next Level",
            "genre": "People & Blogs",
            "primary_topic": "Exploring spiritual principles and theological framing",
            "why_it_matters": "x",
        }
        claims = [
            {
                "id": "c1",
                "text": "Reality-TV alumni revisit casting dynamics and off-camera competition.",
                "claim_type": "interpretation",
            }
        ]
        notes = qg.repair_primary_topic_if_needed(snap, claims)
        self.assertTrue(notes)
        self.assertIn("Revisiting", snap["primary_topic"])

    def test_coherence_low_triggers_repair(self):
        snap = {
            "title": "Kalshi prediction markets and regulation",
            "creator": "Show",
            "genre": "News",
            "primary_topic": "Ottawa police accountability hearings",
            "why_it_matters": "x",
        }
        claims = [{"id": "c1", "text": "Markets price information faster than many regulators expect.", "claim_type": "fact"}]
        notes = qg.repair_primary_topic_if_needed(snap, claims, coherence_min=0.15)
        self.assertTrue(notes)
        self.assertIn("Kalshi", snap["primary_topic"])

    def test_claim_structure_score_prefers_complete_sentences(self):
        good = "Systems outperform goals when motivation is unreliable because routines carry the load."
        bad = "didn't think about it much really if you guys have heard me talk about"
        self.assertGreater(qg.claim_structure_score(good), 0.6)
        self.assertLess(qg.claim_structure_score(bad), 0.4)

    def test_evaluate_v3_forces_diagnostic_on_religious_mismatch(self):
        brief = {
            "episode_snapshot": {
                "title": "Celebrity Interview Weekly",
                "creator": "Host",
                "genre": "Entertainment",
                "primary_topic": "Theological framing of modern relationships",
                "why_it_matters": "x",
            },
            "claims": [
                {"id": "c1", "text": "Hosts compare notes on long-running reality-TV friendships.", "claim_type": "interpretation"},
                {"id": "c2", "text": "Casting competition created real off-camera rivalry among finalists.", "claim_type": "interpretation"},
            ],
            "narrative": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {"segment_to_run": {"name": "", "goal": ""}, "host_questions": [], "clip_candidates": [], "risk_note": ""},
            "guests": [],
            "action_plan_7d": [],
        }
        g = qg.evaluate_v3_quality_gates(brief, "word " * 900)
        self.assertTrue(g.get("force_diagnostic"))

    def test_build_identity_anchor_joins_title_topic_genre(self):
        meta = {"title": "ignored when snapshot has title"}
        snap = {"title": "Nez Perce War", "primary_topic": "Nez Perce resistance", "genre": "History"}
        a = qg.build_identity_anchor(meta, snap)
        self.assertIn("Nez Perce", a)
        self.assertIn("History", a)

    def test_narrative_matches_title_guard(self):
        self.assertTrue(qg.narrative_matches_title("Nez Perce resistance and US policy", "Chief Joseph & the Nez Perce War"))
        self.assertFalse(qg.narrative_matches_title("Agricultural commodity futures and crop insurance reform", "Chief Joseph & the Nez Perce War"))

    def test_top_terms_included_in_identity_anchor(self):
        snap = {
            "title": "Local politics roundup",
            "primary_topic": "city council zoning",
            "genre": "News",
            "creator": "Station",
            "why_it_matters": "x",
            "top_terms": ["zoning", "housing", "council"],
        }
        bullets = ["The housing debate connects directly to council zoning votes this month."]
        kept, _ = qg.clamp_narrative_bullets_to_identity(snap, bullets, min_jaccard=0.07)
        self.assertTrue(kept)

    def test_narrative_clamped_when_misaligned_with_identity(self):
        snap = {
            "title": "Chief Joseph & the Nez Perce War",
            "creator": "The Wild West Extravaganza",
            "genre": "History",
            "primary_topic": "Nez Perce resistance and forced relocation",
            "why_it_matters": "x",
        }
        bad_bullets = [
            "Agricultural risk and livestock disease reshape rural economies.",
        ]
        kept, warns = qg.clamp_narrative_bullets_to_identity(snap, bad_bullets, min_jaccard=0.07)
        self.assertTrue(any("DOMAIN_SHIFT_REJECTED" in w or "LOW_IDENTITY_OVERLAP" in w for w in warns))
        self.assertEqual(len(kept), 1)
        self.assertIn("through-line", kept[0].lower())
        self.assertIn("Nez Perce", kept[0])

    def test_evidence_row_types_use_semantic_labels(self):
        claims = [
            {"id": "c1", "text": "Hosts describe personal growth as partly faith-informed.", "claim_type": "belief"},
            {"id": "c2", "text": "Episode cites a dated contract clause as binding.", "claim_type": "fact"},
            {"id": "c3", "text": "Listeners may read the story as redemption arc.", "claim_type": "interpretation"},
        ]
        t = (
            "[00:01:00] Hosts describe personal growth as partly faith-informed today.\n"
            "[00:02:00] The episode cites a dated contract clause as binding on both parties.\n"
            "[00:03:00] Listeners may read the story as redemption arc for the lead.\n"
        )
        rows = v3.build_evidence_mapping(claims, t)
        types = {r["id"]: r.get("type") for r in rows}
        self.assertEqual(types.get("c1"), "opinion_host")
        self.assertEqual(types.get("c2"), "factual")
        self.assertEqual(types.get("c3"), "interpretive")


if __name__ == "__main__":
    unittest.main()
