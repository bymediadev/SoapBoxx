"""Unit tests for frontend.recovery_hints."""

from __future__ import annotations

import os
import sys

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_frontend = os.path.join(_repo_root, "frontend")
for _p in (_repo_root, _frontend):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from recovery_hints import infer_recovery  # noqa: E402


def test_infer_openai_key_recovery():
    h = infer_recovery("STT", "Service unavailable", "OpenAI API returned 401 unauthorized")
    assert "OpenAI" in h.informative_text
    assert h.offer_open_settings is True


def test_infer_ollama_recovery():
    h = infer_recovery("Workflow", "SOAPBOXX_OLLAMA_MODEL is not set", None)
    assert "Ollama" in h.informative_text or "offline" in h.informative_text.lower()
    assert h.offer_open_settings is True


def test_infer_no_hints_for_generic():
    h = infer_recovery("Misc", "Something else happened", "timeout waiting")
    assert h.informative_text == ""
    assert h.offer_open_settings is False
