"""Tests for backend.question_extraction."""

from __future__ import annotations

import pytest

from backend.question_extraction import extract_questions_from_transcript


def test_extract_skips_short_transcript():
    assert extract_questions_from_transcript("hi", backend="auto") is None


def test_extract_openai_without_key_returns_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SOAPBOXX_OLLAMA_MODEL", raising=False)
    assert extract_questions_from_transcript(
        "a" * 60, backend="openai"
    ) is None
