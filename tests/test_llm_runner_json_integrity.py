"""JSON integrity hints for truncated Ollama JSON (serialization contract)."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from blueprint_v1.llm_runner import json_integrity_hint  # noqa: E402


class TestJsonIntegrityHint(unittest.TestCase):
    def test_unterminated_string_flags_truncation(self) -> None:
        bad = '{"a": "hello'
        try:
            json.loads(bad)
        except json.JSONDecodeError as e:
            h = json_integrity_hint(bad, e)
            self.assertTrue(h["likely_token_truncation"])
            self.assertGreater(h["content_chars"], 0)

    def test_valid_json_no_error(self) -> None:
        h = json_integrity_hint('{"ok": true}', None)
        self.assertFalse(h["likely_token_truncation"])


if __name__ == "__main__":
    unittest.main()
