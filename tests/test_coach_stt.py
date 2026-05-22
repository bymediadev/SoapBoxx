"""Coach loop STT: Azure is not supported; resolve to openai/local."""

import os

import pytest

from backend.coach_stt import (
    coach_stt_validation_error,
    resolve_stt_for_coach,
)


def test_azure_validation_error():
    assert coach_stt_validation_error("azure")
    assert coach_stt_validation_error("azure") is not None
    assert coach_stt_validation_error("openai") is None


def test_resolve_azure_to_openai_when_key_set(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("SOAPBOXX_OLLAMA_MODEL", raising=False)
    svc, warn = resolve_stt_for_coach("azure")
    assert svc == "openai"
    assert warn and "Azure" in warn


def test_resolve_azure_to_local_when_ollama(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SOAPBOXX_OLLAMA_MODEL", "llama3.1:8b")
    svc, warn = resolve_stt_for_coach("azure")
    assert svc == "local"
    assert warn and "Azure" in warn


def test_resolve_openai_passthrough():
    svc, warn = resolve_stt_for_coach("openai")
    assert svc == "openai"
    assert warn is None
