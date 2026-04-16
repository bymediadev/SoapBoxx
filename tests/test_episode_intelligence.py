"""Unit tests for episode brief pipeline (no API calls)."""

import os
import sys
import unittest
from unittest.mock import patch

# backend on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_intelligence as ei  # noqa: E402
from episode_intelligence import (  # noqa: E402
    PRIMARY_EPISODE_REPORT_WORKFLOW_VERSION,
    REPORT_WORKFLOW_VERSION,
    chunk_transcript,
    generate_episode_brief,
    render_markdown,
)


class TestParseJsonLoose(unittest.TestCase):
    def test_trailing_comma_and_markdown_fence(self):
        raw = 'Here is the JSON:\n```json\n{"a": 1, "b": 2,}\n```\n'
        d = ei._parse_json_loose(raw)
        self.assertEqual(d.get("a"), 1)
        self.assertEqual(d.get("b"), 2)

    def test_extract_first_object_ignores_braces_in_strings(self):
        # `{` inside a string must not end extraction early
        raw = '{"k": "use { braces } literally", "x": 1}'
        d = ei._parse_json_loose(raw)
        self.assertEqual(d.get("x"), 1)
        self.assertIn("{ braces }", d.get("k", ""))

    @unittest.skipUnless(
        getattr(ei, "_json_repair_loads", None) is not None,
        "json_repair not installed",
    )
    def test_repairs_unescaped_quotes_in_values(self):
        # Invalid JSON: quotes around "spy" are not escaped — std json.loads fails
        broken = '{"text": "He said ' + '"' + 'spy' + '"' + ' inside"}'
        d = ei._parse_json_loose(broken)
        self.assertIn("spy", str(d.get("text", "")))


class TestSanitizeEpisodeSnapshot(unittest.TestCase):
    def test_primary_topic_reset_when_crime_template_conflicts_gambling_title(self):
        snap = {
            "title": "America's Newest Addiction: How Kalshi Normalizes Betting on Everything",
            "primary_topic": "Criminal enterprise, law enforcement, and accountability",
            "why_it_matters": "Why",
        }
        ei._sanitize_episode_snapshot(snap, [])
        self.assertIn("Kalshi", snap["primary_topic"])
        self.assertNotIn("Criminal enterprise", snap["primary_topic"])


class TestEpisodeIntelligence(unittest.TestCase):
    def test_chunk_transcript_overlap(self):
        text = "word " * 2000
        chunks = chunk_transcript(text, max_chars=100, overlap=20)
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(isinstance(c[1], str) and c[1] for c in chunks))

    def test_render_markdown_minimal(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": ["n1"],
            "claims": [
                {
                    "id": "c1",
                    "text": "claim",
                    "claim_type": "belief",
                    "confidence": "low",
                    "why_it_matters": "m",
                    "counter_angle": "alt view",
                    "next_action": "challenge",
                }
            ],
            "evidence_gaps": {
                "supported": [],
                "weak_or_unsupported": [],
                "proof_needed": [],
            },
            "production_moves": {
                "segment_to_run": {"name": "S", "goal": "g"},
                "host_questions": ["q1", "q2", "q3"],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [{"day": "Day 1", "task": "t"}],
        }
        md = render_markdown(brief, "2026-01-01T00:00:00Z")
        self.assertIn("SoapBoxx", md)
        self.assertIn("c1", md)
        self.assertIn("q1", md)
        self.assertIn(REPORT_WORKFLOW_VERSION, md)
        self.assertIn("Primary episode workflow", md)
        self.assertIn(PRIMARY_EPISODE_REPORT_WORKFLOW_VERSION, md)
        self.assertIn("network_episode_brief_v3.md", md)
        self.assertIn("How this brief was built", md)
        self.assertIn("network brief format v2", md)
        self.assertIn("Counter-angle", md)
        self.assertIn("Follow-up questions (by claim)", md)
        self.assertIn("**[c1]**", md)
        self.assertIn("**Ref:**", md)

    def test_clean_claim_text_strips_speaker_prefix(self):
        raw = "The speaker argues that pastors should disclose finances."
        self.assertEqual(
            ei._clean_claim_text(raw),
            "pastors should disclose finances.",
        )

    def test_garbage_claims_dropped_in_normalize(self):
        brief = {
            "episode_snapshot": {
                "title": "News Hour",
                "creator": "Host",
                "genre": "News",
                "primary_topic": "No clear narrative detected — insufficient signal",
                "why_it_matters": "x",
            },
            "narrative": [],
            "claims": [
                {
                    "id": "c1",
                    "text": 'has a bullpen if you will of little tentacle smaller private investigations firms',
                    "claim_type": "belief",
                    "confidence": "low",
                    "why_it_matters": "m",
                    "counter_angle": "",
                    "next_action": "challenge",
                },
                {
                    "id": "c2",
                    "text": "Institutional accountability requires document trails and named sources when allegations involve public figures.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "m",
                    "counter_angle": "",
                    "next_action": "challenge",
                },
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "S", "goal": "g"},
                "host_questions": ["q1", "q2", "q3"],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        nb = ei._normalize_brief(brief, {})
        self.assertEqual(len(nb["claims"]), 1)
        self.assertIn("Institutional accountability", nb["claims"][0]["text"])

    def test_normalize_brief_replaces_meta_primary_topic(self):
        brief = {
            "episode_snapshot": {
                "title": "Habits and behavior change",
                "creator": "Host",
                "genre": "Talk",
                "primary_topic": "No clear narrative detected — insufficient signal",
                "why_it_matters": "Brief unavailable without OpenAI API.",
            },
            "narrative": ["No clear narrative detected — insufficient signal"],
            "claims": [
                {
                    "id": "c1",
                    "text": "Small environment changes beat willpower for lasting habits.",
                    "claim_type": "interpretation",
                    "confidence": "medium",
                    "why_it_matters": "m",
                    "counter_angle": "",
                    "next_action": "challenge",
                }
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "S", "goal": "g"},
                "host_questions": ["q1", "q2", "q3"],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        nb = ei._normalize_brief(brief, {})
        self.assertNotIn("insufficient signal", nb["episode_snapshot"]["primary_topic"])
        self.assertNotIn("Brief unavailable", nb["episode_snapshot"]["why_it_matters"])
        self.assertEqual(len(nb["guests"]), 2)
        self.assertFalse(any("No clear narrative" in str(x) for x in nb["narrative"]))

    def test_dedupe_claims_and_guest_remap(self):
        brief = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [
                {
                    "id": "c9",
                    "text": "The speaker says that Money drives some ministries.",
                    "claim_type": "belief",
                    "confidence": "medium",
                    "why_it_matters": "m",
                    "counter_angle": "",
                    "next_action": "challenge",
                },
                {
                    "id": "c2",
                    "text": "The speaker says that money drives some ministries.",
                    "claim_type": "belief",
                    "confidence": "medium",
                    "why_it_matters": "m",
                    "counter_angle": "",
                    "next_action": "challenge",
                },
            ],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "S", "goal": "g"},
                "host_questions": ["q1", "q2", "q3"],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [
                {
                    "name": "G",
                    "title": "T",
                    "angle": "a",
                    "maps_to_claim_id": "c17",
                }
            ],
            "action_plan_7d": [],
        }
        nb = ei._normalize_brief(brief, {})
        self.assertEqual(len(nb["claims"]), 1)
        self.assertEqual(nb["claims"][0]["id"], "c1")
        self.assertEqual(nb["guests"][0]["maps_to_claim_id"], "c1")
        md = render_markdown(nb, "2026-01-01T00:00:00Z")
        self.assertEqual(md.count("**[c1]**"), 1)

    @patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "", "SOAPBOXX_OLLAMA_MODEL": "", "SOAPBOXX_OFFLINE": "0"},
        clear=False,
    )
    def test_generate_without_ollama_returns_empty_brief_shell(self):
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "", "SOAPBOXX_OLLAMA_MODEL": "", "SOAPBOXX_OFFLINE": "0"},
            clear=False,
        ):
            r = generate_episode_brief(
                "hello world test transcript here.", {"title": "X"}
            )
        self.assertTrue(r.get("brief"))
        self.assertTrue(r.get("markdown"))
        self.assertTrue(r.get("warnings"))
        self.assertEqual(r.get("workflow_version"), REPORT_WORKFLOW_VERSION)
        self.assertEqual(r.get("model"), "brief-unavailable")
        self.assertEqual(r["brief"].get("narrative"), [])
        self.assertEqual(r["brief"].get("claims"), [])
        self.assertIn("SOAPBOXX_OLLAMA_MODEL", " ".join(r.get("warnings") or []))

    def test_generate_brief_with_ollama_mock(self):
        minimal_json = (
            '{"episode_snapshot":{"title":"X","creator":"","genre":"G",'
            '"primary_topic":"Morning mindset","why_it_matters":"W"},'
            '"narrative":["One arc."],"claims":[],"evidence_gaps":'
            '{"supported":[],"weak_or_unsupported":[],"proof_needed":[]},'
            '"production_moves":{"segment_to_run":{"name":"S","goal":"g"},'
            '"host_questions":["q1","q2","q3"],"clip_candidates":[],"risk_note":""},'
            '"guests":[],"action_plan_7d":[]}'
        )
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b",
                "SOAPBOXX_OFFLINE": "0",
            },
            clear=False,
        ):
            with patch.object(ei, "_openai_chat_with_retry", return_value=minimal_json):
                r = generate_episode_brief("word " * 100, {"title": "Ep"})
        self.assertEqual(r.get("model"), "ollama:llama3.1:8b")
        self.assertEqual(r["brief"]["episode_snapshot"]["primary_topic"], "Morning mindset")

    @patch.dict(os.environ, {"SOAPBOXX_OFFLINE": "1"})
    def test_offline_skips_llm_brief(self):
        r = generate_episode_brief("some transcript text " * 20, {"title": "Y"})
        self.assertEqual(r.get("model"), "offline")
        self.assertIn("SOAPBOXX_OFFLINE", " ".join(r.get("warnings") or []))
        self.assertEqual(r["brief"].get("claims"), [])
        self.assertEqual(r.get("workflow_version"), REPORT_WORKFLOW_VERSION)


if __name__ == "__main__":
    unittest.main()
