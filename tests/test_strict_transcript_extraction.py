# tests/test_strict_transcript_extraction.py
import json
import unittest

from strict_transcript_extraction import (
    auto_repair,
    build_extraction_prompt,
    build_retry_suffix,
    repair_key_quotes,
    repair_score,
    render_strict_json_to_markdown,
    run_strict_extraction_pipeline,
    validate_strict_extraction,
)


def _minimal_valid_payload() -> dict:
    return {
        "episode": {
            "title": "T",
            "guest_name": "",
            "host_name": "",
            "date": "",
            "duration": "",
        },
        "segments": [
            {
                "id": "1",
                "topic": "Intro",
                "start_time": "",
                "end_time": "",
                "speaker_blocks": [
                    {
                        "speaker": "Host",
                        "text": "Hello world today.",
                        "quotes": [{"text": "Hello world today.", "timestamp": ""}],
                    }
                ],
            }
        ],
        "key_quotes": [
            {
                "text": "Hello world today.",
                "speaker": "Host",
                "timestamp": "",
                "topic": "Intro",
            }
        ],
        "entities": {"people": [], "companies": [], "topics": []},
    }


class TestStrictTranscriptExtraction(unittest.TestCase):
    def test_prompt_contains_transcript(self):
        t = "alpha beta"
        p = build_extraction_prompt(t)
        self.assertIn(t, p)
        self.assertIn("VERBATIM", p)

    def test_validate_ok(self):
        tr = "Hello world today."
        data = _minimal_valid_payload()
        ok, res = validate_strict_extraction(data, tr)
        self.assertTrue(ok)
        self.assertIsInstance(res, dict)

    def test_validate_rejects_non_verbatim_quote(self):
        tr = "Hello world today."
        data = _minimal_valid_payload()
        data["key_quotes"][0]["text"] = "Not in transcript"
        ok, res = validate_strict_extraction(data, tr)
        self.assertFalse(ok)
        self.assertIsInstance(res, str)

    def test_validate_overlap(self):
        tr = "Hello world today we go."
        data = _minimal_valid_payload()
        data["key_quotes"] = [
            {
                "text": "Hello world",
                "speaker": "",
                "timestamp": "",
                "topic": "",
            },
            {
                "text": "Hello world today",
                "speaker": "",
                "timestamp": "",
                "topic": "",
            },
        ]
        data["segments"][0]["speaker_blocks"][0]["text"] = tr
        data["segments"][0]["speaker_blocks"][0]["quotes"] = [{"text": tr, "timestamp": ""}]
        ok, res = validate_strict_extraction(data, tr)
        self.assertFalse(ok)
        self.assertIn("Overlapping", str(res))

    def test_repair_dedupes_and_overlap(self):
        tr = "Hello world today we go."
        data = _minimal_valid_payload()
        data["key_quotes"] = [
            {"text": "Hello world today", "speaker": "A", "timestamp": "", "topic": ""},
            {"text": "Hello world today", "speaker": "B", "timestamp": "", "topic": ""},
            {"text": "Hello world", "speaker": "C", "timestamp": "", "topic": ""},
        ]
        data["segments"][0]["speaker_blocks"][0]["text"] = tr
        data["segments"][0]["speaker_blocks"][0]["quotes"] = [{"text": tr, "timestamp": ""}]
        fixed = auto_repair(data, tr)
        ok, _ = validate_strict_extraction(fixed, tr)
        self.assertTrue(ok)
        self.assertEqual(len(fixed["key_quotes"]), 1)

    def test_repair_key_quotes_matches_auto_repair(self):
        tr = "Hello world today we go."
        data = _minimal_valid_payload()
        data["key_quotes"] = [
            {"text": "Hello world today", "speaker": "", "timestamp": "", "topic": ""},
            {"text": "Hello world today", "speaker": "", "timestamp": "", "topic": ""},
        ]
        data["segments"][0]["speaker_blocks"][0]["text"] = tr
        data["segments"][0]["speaker_blocks"][0]["quotes"] = []
        a = auto_repair(data, tr)
        b = repair_key_quotes(data, tr)
        self.assertEqual(a["key_quotes"], b["key_quotes"])

    def test_repair_score(self):
        original = {"key_quotes": [{"text": "a"}, {"text": "b"}]}
        repaired = {"key_quotes": [{"text": "a"}]}
        self.assertEqual(repair_score(original, repaired), 0.5)
        self.assertEqual(repair_score({"key_quotes": []}, {"key_quotes": []}), 1.0)

    def test_pipeline_auto_repair_avoids_extra_llm_call(self):
        tr = "Hello world today we go."
        payload = _minimal_valid_payload()
        payload["segments"][0]["speaker_blocks"][0]["text"] = tr
        payload["segments"][0]["speaker_blocks"][0]["quotes"] = [
            {"text": "Hello world today", "timestamp": ""},
        ]
        payload["key_quotes"] = [
            {"text": "Hello world today", "speaker": "A", "timestamp": "", "topic": ""},
            {"text": "Hello world today", "speaker": "B", "timestamp": "", "topic": ""},
        ]
        calls: list[int] = []

        def llm(_prompt: str) -> str:
            calls.append(1)
            return json.dumps(payload)

        out = run_strict_extraction_pipeline(tr, llm, max_retries=3)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(out["key_quotes"]), 1)

    def test_repair_score_min_forces_retry(self):
        tr = "Hello world today we go."
        payload = _minimal_valid_payload()
        payload["segments"][0]["speaker_blocks"][0]["text"] = tr
        payload["segments"][0]["speaker_blocks"][0]["quotes"] = [
            {"text": "Hello world today", "timestamp": ""},
        ]
        payload["key_quotes"] = [
            {"text": "Hello world today", "speaker": "A", "timestamp": "", "topic": ""},
            {"text": "Hello world today", "speaker": "B", "timestamp": "", "topic": ""},
            {"text": "Hello world", "speaker": "C", "timestamp": "", "topic": ""},
        ]
        calls: list[int] = []

        def llm(_prompt: str) -> str:
            calls.append(1)
            return json.dumps(payload)

        with self.assertRaises(ValueError) as ctx:
            run_strict_extraction_pipeline(
                tr, llm, max_retries=2, repair_score_min=0.5
            )
        self.assertIn("repair_score", str(ctx.exception))
        self.assertEqual(len(calls), 2)

    def test_pipeline_retries_then_succeeds(self):
        tr = "One two three."
        good = _minimal_valid_payload()
        good["segments"][0]["speaker_blocks"][0]["text"] = tr
        good["segments"][0]["speaker_blocks"][0]["quotes"] = [{"text": tr, "timestamp": ""}]
        good["key_quotes"] = [
            {"text": tr, "speaker": "", "timestamp": "", "topic": ""},
        ]

        calls = []

        def llm(prompt: str) -> str:
            calls.append(prompt)
            if len(calls) == 1:
                return "not json"
            return json.dumps(good)

        out = run_strict_extraction_pipeline(tr, llm, max_retries=3, enable_auto_repair=False)
        self.assertEqual(out["key_quotes"][0]["text"], tr)
        self.assertGreater(len(calls), 1)
        self.assertIn("Your previous output failed validation", calls[1])

    def test_render_is_deterministic_subset(self):
        data = _minimal_valid_payload()
        md = render_strict_json_to_markdown(data)
        self.assertIn("Hello world today.", md)
        self.assertIn("## Key quotes", md)

    def test_retry_suffix(self):
        s = build_retry_suffix("bad overlap")
        self.assertIn("bad overlap", s)


if __name__ == "__main__":
    unittest.main()
