"""Smoke tests for backend.llm_service facade."""

from __future__ import annotations

from backend import llm_service


def test_llm_service_exports_call_llm():
    assert callable(llm_service.call_llm)
    assert callable(llm_service.call_llm_json)
    assert callable(llm_service.call_llm_text)
