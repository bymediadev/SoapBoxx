"""Unit tests for episode brief pipeline (no API calls)."""

import json
import os
import sys
import unittest
from unittest.mock import patch

# backend on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import episode_intelligence as ei  # noqa: E402
import strict_episode_contract as sec  # noqa: E402
from episode_intelligence import (  # noqa: E402
    PRIMARY_EPISODE_REPORT_WORKFLOW_VERSION,
    REPORT_WORKFLOW_VERSION,
    chunk_transcript,
    generate_episode_brief,
    render_markdown,
)


class TestLlmEnvelope(unittest.TestCase):
    def test_empty_text_and_data_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            ei.coerce_ollama_message_to_envelope('{"text":"","data":{}}')
        self.assertIn("Empty envelope", str(ctx.exception))

    @patch.dict(os.environ, {"SOAPBOXX_LLM_STRICT_USEFULNESS": "1"}, clear=False)
    def test_strict_rejects_short_text_when_data_empty(self):
        with self.assertRaises(ValueError) as ctx:
            ei.coerce_ollama_message_to_envelope('{"text":"hi","data":{}}')
        self.assertIn("Uninformative", str(ctx.exception))

    def test_coerce_wraps_legacy_root_brief(self):
        root = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
        }
        e = ei.coerce_ollama_message_to_envelope(root)
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_camel_case_root_brief_without_text_key(self):
        """Llama-class models often emit ``episodeSnapshot`` / ``Claims`` at root with no envelope."""
        root = {
            "episodeSnapshot": {
                "title": "Wild West",
                "creator": "Host",
                "genre": "Education",
                "primary_topic": "Outlaws",
                "why_it_matters": "History",
            },
            "Narrative": ["a", "b"],
            "Claims": [],
        }
        e = ei.coerce_ollama_message_to_envelope(json.dumps(root, ensure_ascii=False))
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "Wild West")
        self.assertIsInstance(e["data"].get("claims"), list)

    def test_coerce_finds_brief_deep_under_nested_wrappers(self):
        brief = {
            "episode_snapshot": {
                "title": "Deep",
                "creator": "c",
                "genre": "g",
                "primary_topic": "p",
                "why_it_matters": "w",
            },
            "claims": [],
        }
        root = {"analysis": {"steps": [{"payload": brief}]}}
        e = ei.coerce_ollama_message_to_envelope(json.dumps(root, ensure_ascii=False))
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "Deep")

    def test_coerce_data_array_skips_garbage_then_picks_brief(self):
        junk = {"not_a_brief": True}
        good = {
            "episode_snapshot": {
                "title": "Z",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        root = {"data": [junk, good]}
        e = ei.coerce_ollama_message_to_envelope(json.dumps(root, ensure_ascii=False))
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "Z")

    def test_coerce_output_key_stringified_brief_json(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        packed = json.dumps(inner, ensure_ascii=False)
        root = {"output": packed}
        e = ei.coerce_ollama_message_to_envelope(json.dumps(root, ensure_ascii=False))
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_ollama_content_uses_loose_parse_when_strict_fails(self):
        """Ollama sometimes returns trailing commas or minor glitches; still coerce to envelope."""
        raw = (
            '{"text": "ok", "data": {"episode_snapshot": '
            '{"title": "T", "creator": "", "genre": "G", "primary_topic": "P", "why_it_matters": "W"}},}'
        )
        e = ei.coerce_ollama_message_to_envelope(raw)
        self.assertEqual(e.get("text"), "ok")
        self.assertIsInstance(e.get("data", {}).get("episode_snapshot"), dict)

    def test_coerce_string_json_envelope(self):
        s = json.dumps({"text": "note", "data": {"x": 1}})
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "note")
        self.assertEqual(e["data"]["x"], 1)

    def test_coerce_Text_Data_key_aliases(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        s = json.dumps({"Text": "hi", "Data": inner}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "hi")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_nested_response_data_brief(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        s = json.dumps({"response": {"data": inner}}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_snapshot_root_without_episode_snapshot_key(self):
        snap = {
            "title": "T",
            "creator": "",
            "genre": "G",
            "primary_topic": "P",
            "why_it_matters": "W",
        }
        root = {"snapshot": snap, "claims": [{"id": "c1", "text": "x"}]}
        e = ei.coerce_ollama_message_to_envelope(json.dumps(root))
        self.assertIn("episode_snapshot", e["data"])
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_data_only_envelope_omits_text_key(self):
        """Ollama JSON mode often returns only ``data``; text is optional transport metadata."""
        inner = {"episode_snapshot": {"x": 1}, "claims": []}
        s = json.dumps({"data": inner}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"], inner)

    def test_coerce_text_null_becomes_empty_string(self):
        s = json.dumps({"text": None, "data": {"k": 1}})
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["k"], 1)

    def test_coerce_stringified_data_field(self):
        inner = {"episode_snapshot": {"title": "T"}, "claims": []}
        packed = json.dumps(inner, ensure_ascii=False)
        s = json.dumps({"data": packed})
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_nested_response_wrapper(self):
        inner = {"episode_snapshot": {"title": "T"}, "claims": []}
        s = json.dumps({"response": inner}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "")
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_single_element_json_array_root(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        s = json.dumps([{"text": "", "data": inner}], ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_data_null_then_root_brief(self):
        """``data: null`` with a v2-shaped root should still lift the brief."""
        root = {
            "data": None,
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        e = ei.coerce_ollama_message_to_envelope(json.dumps(root))
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_data_as_single_element_array(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        s = json.dumps({"text": "", "data": [inner]}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_json_wrapper_array_inner(self):
        inner = {"episode_snapshot": {"title": "T"}, "claims": []}
        s = json.dumps({"json": [inner]}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_stringified_wrapper_with_prose_prefix(self):
        inner = {"episodeSnapshot": {"title": "T"}, "claims": []}
        blob = "Here is the payload:\n```json\n" + json.dumps(inner, ensure_ascii=False) + "\n```"
        s = json.dumps({"result": blob}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    def test_coerce_missing_text_uses_content_string_as_text_fallback(self):
        s = json.dumps({"role": "assistant", "content": "one-line summary"}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "one-line summary")
        self.assertEqual(e["data"], {})

    def test_coerce_missing_text_preserves_unknown_nonempty_payload(self):
        s = json.dumps({"foo": {"bar": 1}}, ensure_ascii=False)
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["text"], "")
        self.assertIn("foo", e["data"])

    def test_brief_from_envelope_camel_case_episode_snapshot(self):
        env = {
            "text": "",
            "data": {
                "episodeSnapshot": {
                    "title": "T",
                    "creator": "",
                    "genre": "G",
                    "primary_topic": "P",
                    "why_it_matters": "W",
                },
                "Claims": [],
            },
        }
        b = ei._brief_from_llm_envelope(env)
        self.assertEqual(b["episode_snapshot"]["title"], "T")
        self.assertIsInstance(b.get("claims"), list)

    def test_brief_from_envelope_guests_only_no_snapshot(self):
        env = {
            "text": "summary",
            "data": {
                "guests": [
                    {"name": "A", "title": "t", "angle": "x", "maps_to_claim_id": ""},
                ],
            },
        }
        b = ei._brief_from_llm_envelope(env)
        self.assertEqual(len(b.get("guests") or []), 1)

    def test_brief_from_envelope_lift_brief_wrapper(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        env = {"text": "", "data": {"brief": inner}}
        b = ei._brief_from_llm_envelope(env)
        self.assertEqual(b["episode_snapshot"]["title"], "T")

    def test_coerce_brief_keys_beside_text_not_under_data(self):
        s = json.dumps(
            {
                "text": "",
                "episode_snapshot": {
                    "title": "T",
                    "creator": "",
                    "genre": "G",
                    "primary_topic": "P",
                    "why_it_matters": "W",
                },
                "claims": [],
            },
            ensure_ascii=False,
        )
        e = ei.coerce_ollama_message_to_envelope(s)
        self.assertEqual(e["data"]["episode_snapshot"]["title"], "T")

    @patch.dict(os.environ, {"SOAPBOXX_LLM_VALIDATE_BRIEF_SCHEMA": "1"}, clear=False)
    def test_maybe_validate_brief_schema_rejects_empty_primary_topic(self):
        bad = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "", "goal": ""},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        with self.assertRaises(ValueError) as ctx:
            ei._maybe_validate_brief_semantics(bad)
        self.assertIn("primary_topic", str(ctx.exception))

    def test_brief_from_envelope_prefers_data(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "Morning",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "S", "goal": "g"},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        b = ei._brief_from_llm_envelope({"text": "", "data": inner})
        self.assertEqual(b["episode_snapshot"]["primary_topic"], "Morning")

    def test_brief_from_envelope_partial_data_without_snapshot(self):
        """Local models sometimes omit episode_snapshot; normalize() fills from METADATA later."""
        partial = {
            "claims": [{"id": "c1", "text": "A claim", "claim_type": "fact"}],
            "narrative": [],
        }
        b = ei._brief_from_llm_envelope({"text": "", "data": partial})
        self.assertNotIn("episode_snapshot", b)
        self.assertEqual(len(b["claims"]), 1)

    @patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "1"}, clear=False)
    def test_brief_from_envelope_text_recovery_when_fallback_enabled(self):
        """When data is empty, parse v2 brief from text if SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1."""
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
        }
        text = json.dumps(inner, ensure_ascii=False)
        b = ei._brief_from_llm_envelope({"text": text, "data": {}})
        self.assertEqual(b["episode_snapshot"]["title"], "T")

    @patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "0"}, clear=False)
    def test_brief_from_envelope_strict_rejects_text_only(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
        }
        text = json.dumps(inner, ensure_ascii=False)
        with self.assertRaises(ValueError):
            ei._brief_from_llm_envelope({"text": text, "data": {}})

    @patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "0"}, clear=False)
    def test_brief_plain_text_summary_no_parse_failed_message(self):
        """Prompt allows a one-line summary in ``text``; do not mis-report JSON parse errors."""
        with self.assertRaises(ValueError) as ctx:
            ei._brief_from_llm_envelope(
                {"text": "Plain one-line summary with no JSON.", "data": {}}
            )
        self.assertNotIn("parse failed", str(ctx.exception).lower())

    @patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "1"}, clear=False)
    def test_brief_plain_text_summary_fallback_when_enabled(self):
        b = ei._brief_from_llm_envelope(
            {"text": "Plain one-line summary with no JSON.", "data": {}}
        )
        self.assertIsInstance(b.get("narrative"), list)
        self.assertTrue((b.get("narrative") or [])[0].startswith("Plain one-line summary"))

    def test_brief_coerces_flat_snapshot_fields_at_root(self):
        partial = {
            "title": "Wild West",
            "creator": "Host",
            "primary_topic": "Frontier history",
            "why_it_matters": "Because",
            "claims": [{"id": "c1", "text": "A claim line", "claim_type": "fact"}],
        }
        b = ei._brief_from_llm_envelope({"text": "", "data": partial})
        self.assertEqual(b["episode_snapshot"]["title"], "Wild West")
        self.assertEqual(b["episode_snapshot"]["primary_topic"], "Frontier history")
        self.assertEqual(len(b["claims"]), 1)

    @patch.dict(os.environ, {"SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK": "1"}, clear=False)
    def test_brief_text_full_envelope_unwrapped(self):
        """Sometimes the model JSON-encodes the whole envelope into ``text``."""
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
        }
        wrapped = {"text": "", "data": inner}
        text = json.dumps(wrapped, ensure_ascii=False)
        b = ei._brief_from_llm_envelope({"text": text, "data": {}})
        self.assertEqual(b["episode_snapshot"]["title"], "T")

    def test_brief_coerces_double_nested_data_key(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "C",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "narrative": [],
            "claims": [],
        }
        b = ei._brief_from_llm_envelope({"text": "", "data": {"data": inner}})
        self.assertEqual(b["episode_snapshot"]["title"], "T")

    def test_brief_recovers_nested_payload_from_unknown_data_wrapper(self):
        inner = {
            "episode_snapshot": {
                "title": "T",
                "creator": "",
                "genre": "G",
                "primary_topic": "P",
                "why_it_matters": "W",
            },
            "claims": [],
        }
        env = {"text": "", "data": {"foo": {"bar": inner}}}
        b = ei._brief_from_llm_envelope(env)
        self.assertEqual(b["episode_snapshot"]["title"], "T")


class TestBriefLlmEnvelopeRetry(unittest.TestCase):
    @patch.dict(os.environ, {"SOAPBOXX_BRIEF_ENVELOPE_RETRIES": "1"}, clear=False)
    @patch("episode_intelligence._ollama_chat_invoke")
    def test_retries_after_bad_first_response(self, mock_invoke):
        bad = "not json"
        good = json.dumps(
            {
                "text": "ok",
                "data": {
                    "episode_snapshot": {
                        "title": "T",
                        "creator": "",
                        "genre": "",
                        "primary_topic": "P",
                        "why_it_matters": "W",
                    },
                    "narrative": [],
                    "claims": [],
                },
            }
        )
        mock_invoke.side_effect = [bad, good]
        out = ei._brief_llm_envelope("sys", "user")
        self.assertEqual(out["text"], "ok")
        self.assertEqual(mock_invoke.call_count, 2)

    @patch.dict(os.environ, {"SOAPBOXX_BRIEF_ENVELOPE_RETRIES": "0"}, clear=False)
    @patch("episode_intelligence._ollama_chat_invoke")
    def test_zero_retries_raises_on_first_failure(self, mock_invoke):
        mock_invoke.return_value = "bad"
        with self.assertRaises(ValueError):
            ei._brief_llm_envelope("s", "u")
        self.assertEqual(mock_invoke.call_count, 1)


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

    def test_primary_topic_reset_when_crime_template_conflicts_education_title(self):
        snap = {
            "title": "Brainwash! - The Rockefeller's School Psyop WORSE Than You Think",
            "primary_topic": "Criminal enterprise, law enforcement, and accountability",
            "why_it_matters": "Why",
        }
        ei._sanitize_episode_snapshot(snap, [])
        self.assertIn("Rockefeller", snap["primary_topic"])
        self.assertNotIn("Criminal enterprise", snap["primary_topic"])

    def test_heuristic_primary_topic_prefers_narrative_over_title(self):
        """When the snapshot carries a clean narrative bullet, it should beat the clickbait title."""
        snap = {
            "title": '"Brainwash!" - The Rockefeller\'s School Psyop WORSE Than You Think',
            "primary_topic": "Criminal enterprise, law enforcement, and accountability",
            "narrative": [
                "Centralised philanthropic funding steered U.S. public schooling toward compliance over inquiry.",
            ],
        }
        ei._sanitize_episode_snapshot(snap, [])
        self.assertIn("Centralised", snap["primary_topic"])
        self.assertNotIn("Brainwash", snap["primary_topic"])

    def test_override_primary_topic_with_storyline_uses_analytics(self):
        """Post-analytics override picks the first clean storyline when the snap is still wrong."""
        snap = {
            "title": "Rockefeller school psyop",
            "primary_topic": "Criminal enterprise, law enforcement, and accountability",
        }
        storylines = [
            "The Rockefeller family's influence on education is a form of psychological manipulation.",
        ]
        ei.override_primary_topic_with_storyline(snap, storylines=storylines)
        self.assertIn("Rockefeller family", snap["primary_topic"])

    def test_override_primary_topic_with_storyline_noop_when_current_is_good(self):
        """Do not overwrite an already-good primary_topic even if storylines exist."""
        snap = {
            "title": "Kalshi normalizes sports betting",
            "primary_topic": "Prediction markets and the normalization of retail gambling",
        }
        storylines = ["Something completely different"]
        ei.override_primary_topic_with_storyline(snap, storylines=storylines)
        self.assertNotIn("Something completely different", snap["primary_topic"])

    def test_override_primary_topic_cleans_analyst_stem_and_tag_cloud(self):
        """Messy storyline text ("The core theme of this episode is X; Y; Z; ...") is trimmed to a label."""
        snap = {
            "title": "Rockefeller school psyop",
            "primary_topic": "Criminal enterprise, law enforcement, and accountability",
        }
        storylines = [
            "The core theme of this episode is Rockefeller family; education system; "
            "Prussian model of education; centralization of power; decentralization.",
        ]
        ei.override_primary_topic_with_storyline(snap, storylines=storylines)
        pt = snap["primary_topic"]
        self.assertNotIn("The core theme of this episode is", pt)
        self.assertIn("Rockefeller family", pt)
        # Semicolon tag clouds are clamped to the first two chunks (not five).
        self.assertLessEqual(pt.count(";"), 1)

    def test_clean_storyline_for_primary_topic_handles_various_prefixes(self):
        cs = ei._clean_storyline_for_primary_topic
        self.assertEqual(
            cs("This episode is about the weaponization of education."),
            "The weaponization of education",
        )
        self.assertEqual(
            cs("Storyline: how prediction markets became 'sports betting with extra steps'"),
            "How prediction markets became 'sports betting with extra steps'",
        )
        self.assertEqual(
            cs("Main topic: decentralization vs. centralization."),
            "Decentralization vs. centralization",
        )
        # Clean single-sentence storylines pass through un-molested (minus trailing punctuation).
        self.assertEqual(
            cs("The Rockefeller family's influence on the U.S. education system."),
            "The Rockefeller family's influence on the U.S. education system",
        )


class TestNewSurfaceFilters(unittest.TestCase):
    def test_asr_artifact_doubled_the_their(self):
        # "the their" — doubled function words are the classic ASR splice signature.
        self.assertTrue(
            ei._is_asr_artifact_line(
                "The Rockefeller, , the their foundation is still invested in local school board meetings."
            )
        )

    def test_asr_artifact_repeated_comma(self):
        self.assertTrue(ei._is_asr_artifact_line("Yeah like, , I had saved up from impulsive enough."))

    def test_asr_artifact_accepts_clean_appositive(self):
        # Normal appositive should NOT be flagged ("Rockefeller, the foundation,").
        self.assertFalse(
            ei._is_asr_artifact_line(
                "The Rockefeller Foundation, a 20th-century philanthropic engine, shaped U.S. schools."
            )
        )

    def test_dangling_pronoun_line(self):
        self.assertTrue(ei._is_dangling_pronoun_line("You don't see him around as much anymore."))

    def test_dangling_pronoun_line_keeps_when_proper_noun_present(self):
        self.assertFalse(
            ei._is_dangling_pronoun_line("You don't see the Rockefellers around as much anymore.")
        )

    def test_production_chatter_line(self):
        self.assertTrue(
            ei._is_production_chatter_line(
                "Then like back engineering how to do all the equipment on a podcast going off about 10 to 15 shows."
            )
        )

    def test_production_chatter_keeps_on_thesis_line(self):
        self.assertFalse(
            ei._is_production_chatter_line(
                "The Rockefeller foundation invests in local school board elections."
            )
        )


class TestTrimAnchorDisplayText(unittest.TestCase):
    def test_strips_leading_filler(self):
        out = ei._trim_anchor_display_text("Yeah like well, the Rockefeller foundation is real.")
        self.assertTrue(out.startswith("The Rockefeller foundation"))

    def test_handles_empty_and_none(self):
        self.assertEqual(ei._trim_anchor_display_text(""), "")
        self.assertEqual(ei._trim_anchor_display_text(None), "")  # type: ignore[arg-type]

    def test_preserves_already_clean_sentence(self):
        s = "The Rockefeller foundation shapes local school boards."
        self.assertEqual(ei._trim_anchor_display_text(s), s)

    def test_caps_very_long_anchors_with_ellipsis(self):
        long = " ".join(["word"] * 80)
        out = ei._trim_anchor_display_text(long, max_chars=80)
        self.assertTrue(out.endswith("…"))
        self.assertLessEqual(len(out), 82)


class TestGenreRefinement(unittest.TestCase):
    def test_generic_entertainment_refined_for_education_title(self):
        g = ei._refine_genre_from_title(
            '"Brainwash!" - The Rockefeller School Psyop',
            "Entertainment",
        )
        self.assertIn("Education", g)

    def test_generic_entertainment_refined_for_gambling_title(self):
        g = ei._refine_genre_from_title(
            "Kalshi sports betting and prediction markets",
            "Entertainment",
        )
        self.assertIn("Business", g)

    def test_meaningful_genre_not_overridden(self):
        g = ei._refine_genre_from_title(
            "Brainwash! Rockefeller School Psyop",
            "History",
        )
        self.assertEqual(g, "History")

    def test_blank_title_returns_current(self):
        self.assertEqual(ei._refine_genre_from_title("", "Entertainment"), "Entertainment")


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

    def test_clean_claim_text_normalizes_cuzut_asr_glitch(self):
        raw = "It was crazy cuzut was like the best thing you could possibly do."
        self.assertIn("cuz it", ei._clean_claim_text(raw).lower())

    def test_repeated_count_stutter_claim_is_dropped(self):
        raw = (
            "One out of five, One out of five, One out of five, that's like any kids like what, "
            "like 10 to 18 or maybe in that area?"
        )
        self.assertTrue(ei._is_garbage_claim_text(raw))

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
        with patch.dict(os.environ, {"SOAPBOXX_CLAIM_FILTER_V2": "0"}, clear=False):
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

    def test_transcript_grounded_fallback_builds_claims(self):
        transcript = (
            "We moved toward centralization of education policy and media authority over decades. "
            "The guest argues this concentration of power reduces local accountability. "
            "History shows centralized schooling systems can drift away from parent and community control."
        )
        meta = {
            "title": "Rockefeller school centralization and media authority",
            "creator": "Julian Dorey",
            "genre": "Entertainment",
        }
        claims = ei._extract_transcript_grounded_claims(transcript, meta)
        self.assertGreaterEqual(len(claims), 2)
        self.assertTrue(any("centralization" in str(c.get("text", "")).lower() for c in claims))

    def test_enrich_brief_with_transcript_grounding_when_claims_empty(self):
        brief = {
            "episode_snapshot": {
                "title": "Rockefeller school centralization and media authority",
                "creator": "Julian Dorey",
                "genre": "Entertainment",
                "primary_topic": "",
                "why_it_matters": "",
            },
            "narrative": [],
            "claims": [],
            "evidence_gaps": {"supported": [], "weak_or_unsupported": [], "proof_needed": []},
            "production_moves": {
                "segment_to_run": {"name": "", "goal": ""},
                "host_questions": [],
                "clip_candidates": [],
                "risk_note": "",
            },
            "guests": [],
            "action_plan_7d": [],
        }
        transcript = (
            "The discussion says centralized schooling can make social narratives easier to control. "
            "The speaker argues that distributed decision-making gives families better agency."
        )
        used = ei._enrich_brief_with_transcript_grounding(brief, transcript, brief["episode_snapshot"])
        self.assertTrue(used)
        self.assertGreaterEqual(len(brief.get("claims") or []), 1)
        self.assertTrue(str((brief.get("episode_snapshot") or {}).get("primary_topic") or "").strip())

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
        with patch.dict(os.environ, {"SOAPBOXX_CLAIM_FILTER_V2": "0"}, clear=False):
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
        strict_ready_json = (
            '{"episode_snapshot":{"title":"Episode Title Alpha","creator":"Creator Name","genre":"Education",'
            '"primary_topic":"Morning mindset and disciplined behavior change for founders",'
            '"why_it_matters":"Listeners need concrete behavior changes they can test this week to improve outcomes."},'
            '"narrative":["The episode argues that routines determine strategic clarity under pressure.",'
            '"It contrasts reactive hustle with deliberate weekly planning anchored to measurable outcomes."],'
            '"claims":[{"id":"c1","text":"Deliberate weekly planning reduces avoidable decision fatigue for founders.",'
            '"claim_type":"interpretation","confidence":"medium","why_it_matters":"Without a plan, context switching erodes execution.",'
            '"counter_angle":"Some teams thrive with looser structures in uncertain markets.","next_action":"verify"},'
            '{"id":"c2","text":"A fixed review cadence improves alignment between priorities and daily actions.",'
            '"claim_type":"interpretation","confidence":"medium","why_it_matters":"Cadence prevents drift from stated goals.",'
            '"counter_angle":"Too-rigid cadence can miss emergent opportunities.","next_action":"challenge"}],'
            '"evidence_gaps":{"supported":[],"weak_or_unsupported":[],"proof_needed":[]},'
            '"production_moves":{"segment_to_run":{"name":"Weekly Planning Drill","goal":"Demonstrate one planning loop listeners can copy."},'
            '"host_questions":["What tradeoff are you making by not planning weekly?",'
            '"Which metric proves your routine is working?"],'
            '"clip_candidates":["Planning beats panic when uncertainty spikes.","Cadence turns goals into repeated behavior."],'
            '"risk_note":"Avoid implying one routine fits every team context."},'
            '"guests":[{"name":"Operations coach","title":"Founder advisor","angle":"Translates planning discipline into weekly practice.","maps_to_claim_id":"c1"}],'
            '"action_plan_7d":[{"day":"Day 1","task":"Define one metric for planning quality."},{"day":"Day 3","task":"Run one weekly planning session with your team."},{"day":"Day 7","task":"Review outcomes and adjust the cadence."}]}'
        )
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b",
                "SOAPBOXX_OFFLINE": "0",
                "SOAPBOXX_BRIEF_STRICT_CONTRACT": "0",
                "SOAPBOXX_CLAIM_FILTER_V2": "0",
            },
            clear=False,
        ):
            with patch.object(
                ei,
                "_brief_llm_envelope",
                return_value={"text": "", "data": json.loads(strict_ready_json)},
            ):
                r = generate_episode_brief("word " * 100, {"title": "Ep"})
        self.assertEqual(r.get("model"), "ollama:llama3.1:8b")
        self.assertTrue(str((r["brief"]["episode_snapshot"] or {}).get("primary_topic") or "").strip())
        self.assertNotIn("hard failure after schema retries", " ".join(r.get("warnings") or []).lower())

    @patch.dict(os.environ, {"SOAPBOXX_OFFLINE": "1"})
    def test_offline_skips_llm_brief(self):
        r = generate_episode_brief("some transcript text " * 20, {"title": "Y"})
        self.assertEqual(r.get("model"), "offline")
        self.assertIn("SOAPBOXX_OFFLINE", " ".join(r.get("warnings") or []))
        self.assertEqual(r["brief"].get("claims"), [])
        self.assertEqual(r.get("workflow_version"), REPORT_WORKFLOW_VERSION)


class TestStrictEpisodeContract(unittest.TestCase):
    def test_validate_rejects_missing_keys(self):
        ok, err = sec.validate_strict_episode_contract({"data": {}})
        self.assertFalse(ok)
        self.assertIn("top-level keys", err)

    def test_validate_accepts_minimal_valid(self):
        obj = {
            "data": {
                "episode_snapshot": {
                    "title": "Episode Alpha",
                    "core_thesis": "A concrete claim about measurable listener behavior.",
                    "summary": "A concise summary that still clears the strict minimum length.",
                },
                "key_topics": ["listener behavior"],
                "key_moments": [{"timestamp": "", "description": "A usable clip moment with concrete takeaway."}],
                "insights": ["Listeners respond better when the episode states one falsifiable claim."],
                "actionable_takeaways": ["Test one claim against evidence before publishing."],
                "notable_quotes": [],
                "guest_profile": {"name": "Guest", "role": "Analyst", "expertise": ["media analysis"]},
            },
            "metadata": {"model": "", "warnings": [], "error": ""},
        }
        self.assertTrue(sec.validate_strict_episode_contract(obj)[0])

    def test_enforce_strict_contract_envelope_wraps_flat_payload(self):
        flat = {"episode_snapshot": {"title": "T"}, "claims": []}
        wrapped = sec.enforce_strict_contract_envelope(flat)
        self.assertIn("data", wrapped)
        self.assertIn("metadata", wrapped)
        self.assertEqual(wrapped["data"]["episode_snapshot"]["title"], "T")

    def test_map_to_v2_brief_from_contract(self):
        contract = {
            "data": {
                "episode_snapshot": {
                    "title": "Wild",
                    "core_thesis": "History shapes memory.",
                    "summary": "Episode covers frontier violence.",
                },
                "key_topics": ["outlaws", "lawmen"],
                "key_moments": [{"timestamp": "00:01", "description": "Cold open"}],
                "insights": ["Many figures are forgotten compared to famous names."],
                "actionable_takeaways": ["Name one counterexample."],
                "notable_quotes": [],
                "guest_profile": {"name": "Dr. Jane", "role": "Historian", "expertise": ["US West"]},
            }
        }
        v2 = sec.map_strict_contract_to_v2_brief(contract, {"title": "Wild", "creator": "Host", "genre": "History"})
        self.assertEqual(v2["episode_snapshot"]["title"], "Wild")
        self.assertTrue(v2.get("claims"))
        self.assertTrue(v2.get("guests"))

    def test_strict_contract_invalid_is_rejected_without_internal_repair(self):
        bad = {"data": {"episode_snapshot": {}}}
        with patch.dict(
            os.environ,
            {"SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b", "SOAPBOXX_BRIEF_STRICT_CONTRACT": "1"},
            clear=False,
        ):
            with patch.object(ei, "_ollama_chat_invoke", return_value=json.dumps(bad)) as inv:
                with self.assertRaises(ValueError) as ctx:
                    ei._generate_brief_via_strict_contract(
                        None,
                        True,
                        "transcript words " * 30,
                        {"title": "Ep", "creator": "C", "genre": "G"},
                    )
        self.assertEqual(inv.call_count, 1)
        self.assertIn("strict episode contract invalid", str(ctx.exception))

    def test_strict_contract_retries_then_hard_fails_on_invalid_shape(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b",
                "SOAPBOXX_OFFLINE": "0",
                "SOAPBOXX_BRIEF_STRICT_CONTRACT": "1",
            },
            clear=False,
        ):
            with patch.object(
                ei,
                "_generate_brief_via_strict_contract",
                side_effect=ValueError('strict episode contract invalid: missing top-level "data"'),
            ) as strict_gen:
                r = generate_episode_brief(
                    "transcript words " * 50,
                    {"title": "Ep", "creator": "C", "genre": "G"},
                )
        warns = " ".join(r.get("warnings") or []).lower()
        self.assertEqual(strict_gen.call_count, ei._BRIEF_SCHEMA_MAX_RETRIES + 1)
        self.assertIn("hard failure after schema retries", warns)
        self.assertNotIn("weak structured output detected", warns)

    def test_generate_hard_failure_warning_no_weak_structured_mask(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "SOAPBOXX_OLLAMA_MODEL": "llama3.1:8b",
                "SOAPBOXX_OFFLINE": "0",
                "SOAPBOXX_BRIEF_STRICT_CONTRACT": "1",
            },
            clear=False,
        ):
            with patch.object(
                ei,
                "_generate_brief_via_strict_contract",
                side_effect=ValueError('strict episode contract invalid: missing top-level "data"'),
            ):
                r = generate_episode_brief(
                    "transcript words " * 40,
                    {"title": "Step one deterministic test", "creator": "Creator", "genre": "Education"},
                )
        warns = " ".join(r.get("warnings") or []).lower()
        self.assertIn("hard failure after schema retries", warns)
        self.assertNotIn("weak structured output detected", warns)


if __name__ == "__main__":
    unittest.main()
