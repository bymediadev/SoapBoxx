"""Tests for creator-facing v3 report reality checks (quality + golden expectations)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_report_v3 as v3  # noqa: E402
import report_reality_checks as rr  # noqa: E402


def _systems_vs_goals_fixture():
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
    return brief, transcript


class TestReportRealityChecks(unittest.TestCase):
    def test_default_reality_rules_file_loads(self):
        rules = rr.load_default_reality_rules()
        self.assertIsInstance(rules, dict)
        self.assertTrue(rules.get("forbid_generic_thesis"))
        self.assertTrue(rr.default_reality_rules_path().is_file())

    def test_is_generic_detects_filler(self):
        self.assertTrue(rr.is_generic_creator_text("We should delve into the landscape of ideas here."))
        self.assertFalse(rr.is_generic_creator_text("Systems beat goals when motivation is unreliable."))

    def test_thesis_grounding_ratio(self):
        self.assertGreaterEqual(
            rr.thesis_grounding_ratio("Systems beat goals when motivation drops", "systems goals motivation"),
            0.5,
        )
        self.assertLess(
            rr.thesis_grounding_ratio("Quantum telepathy reorganizes fiscal incentives", "systems goals motivation"),
            0.3,
        )

    def test_would_ship_v3_passes_on_strong_fixture(self):
        brief, transcript = _systems_vs_goals_fixture()
        report = v3.build_v3_report(brief, transcript, metadata={})
        ok, reasons = rr.would_ship_v3(report, transcript)
        self.assertTrue(ok, msg="; ".join(reasons))

    def test_validate_reality_golden_json_fixture(self):
        brief, transcript = _systems_vs_goals_fixture()
        report = v3.build_v3_report(brief, transcript, metadata={})
        base = os.path.join(os.path.dirname(__file__), "golden", "episode_001", "v3_reality_expected.json")
        with open(base, encoding="utf-8") as f:
            rules = json.load(f)
        fails = rr.validate_reality_golden(report, transcript, rules)
        self.assertEqual(fails, [], msg="; ".join(fails))

    def test_validate_reality_golden_surfaces_exact_reason(self):
        brief, transcript = _systems_vs_goals_fixture()
        report = v3.build_v3_report(brief, transcript, metadata={})
        fails = rr.validate_reality_golden(
            report,
            transcript,
            {"expected_thesis_contains": ["definitely-not-in-thesis-xyz"]},
        )
        self.assertEqual(len(fails), 1)
        self.assertIn("missing expected phrase", fails[0])

    def test_strong_clip_proxy(self):
        self.assertTrue(rr.strong_clip_proxy("I didn't realize the habit was actually protecting me."))
        self.assertFalse(rr.strong_clip_proxy("Habits are good for wellness and balance."))


if __name__ == "__main__":
    unittest.main()
