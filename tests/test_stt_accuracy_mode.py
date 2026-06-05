"""STT accuracy mode + AssemblyAI diarization formatting."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.services.assemblyai_format import format_diarized_utterances
from backend.services.assemblyai_stt import (
    assemblyai_base_url,
    assemblyai_keyterms,
    assemblyai_speech_models,
    transcribe_assemblyai_audio,
)
from backend.stt_config import (
    accuracy_mode_enabled,
    cloud_stt_soft_bytes,
    groq_whisper_model,
    local_whisper_model,
    stt_http_timeout_seconds,
)

pytestmark = pytest.mark.not_integration


def test_assemblyai_diarization_labels():
    text, segments = format_diarized_utterances(
        [
            {"speaker": "A", "text": "Welcome to the show.", "start": 0, "end": 2000},
            {"speaker": "B", "text": "Thanks for having me.", "start": 2000, "end": 4500},
            {"speaker": "A", "text": "Let's dive in.", "start": 4500, "end": 6000},
        ]
    )
    assert "Host: Welcome to the show." in text
    assert "Guest: Thanks for having me." in text
    assert text.count("Host:") == 2
    assert len(segments) == 3
    assert segments[1]["start_time"] == 2.0


def test_accuracy_mode_defaults(monkeypatch):
    monkeypatch.delenv("SOAPBOXX_STT_ACCURACY_MODE", raising=False)
    monkeypatch.delenv("SOAPBOXX_GROQ_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("SOAPBOXX_LOCAL_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("SOAPBOXX_STT_HTTP_TIMEOUT", raising=False)
    monkeypatch.delenv("SOAPBOXX_STT_SOFT_BYTES", raising=False)

    assert accuracy_mode_enabled() is False
    assert groq_whisper_model() == "whisper-large-v3-turbo"
    assert local_whisper_model() == "base"
    assert stt_http_timeout_seconds() == 300.0
    assert cloud_stt_soft_bytes(25 * 1024 * 1024) == int(25 * 1024 * 1024 * 0.92)


def test_accuracy_mode_enabled_overrides(monkeypatch):
    monkeypatch.setenv("SOAPBOXX_STT_ACCURACY_MODE", "true")
    monkeypatch.delenv("SOAPBOXX_GROQ_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("SOAPBOXX_LOCAL_WHISPER_MODEL", raising=False)
    monkeypatch.delenv("SOAPBOXX_STT_HTTP_TIMEOUT", raising=False)

    assert accuracy_mode_enabled() is True
    assert groq_whisper_model() == "whisper-large-v3"
    assert local_whisper_model() == "medium"
    assert stt_http_timeout_seconds() == 600.0
    assert cloud_stt_soft_bytes(25 * 1024 * 1024) == int(25 * 1024 * 1024 * 0.98)


def test_assemblyai_speech_models_default(monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_SPEECH_MODELS", raising=False)
    assert assemblyai_speech_models() == ["universal-3-pro", "universal-2"]


def test_assemblyai_speech_models_override(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_SPEECH_MODELS", "universal-2")
    assert assemblyai_speech_models() == ["universal-2"]


def test_assemblyai_base_url_and_keyterms(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_BASE", "https://api.eu.assemblyai.com")
    monkeypatch.setenv("SOAPBOXX_ASSEMBLYAI_KEYTERMS", "Planet Money, NPR")
    assert assemblyai_base_url() == "https://api.eu.assemblyai.com"
    assert assemblyai_keyterms() == ["Planet Money", "NPR"]


def test_assemblyai_http_submit_includes_speech_models(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_SPEECH_MODELS", "universal-3-pro,universal-2")

    upload_resp = MagicMock(status_code=200)
    upload_resp.json.return_value = {"upload_url": "https://cdn.example/upload"}

    submit_resp = MagicMock(status_code=200)
    submit_resp.json.return_value = {"id": "tx-1"}

    poll_resp = MagicMock()
    poll_resp.json.return_value = {
        "status": "completed",
        "text": "Hello world",
        "utterances": [
            {"speaker": "A", "text": "Hello world", "start": 0, "end": 1000},
        ],
    }

    with patch(
        "backend.services.assemblyai_stt._transcribe_sdk",
        side_effect=ImportError("no sdk"),
    ):
        with patch("requests.post", side_effect=[upload_resp, submit_resp]) as mock_post:
            with patch("requests.get", return_value=poll_resp):
                result = transcribe_assemblyai_audio(
                    b"fake-audio",
                    api_key="test-key",
                    language="en",
                    verbose=True,
                )

    assert "Host: Hello world" in result["transcript"]
    submit_call = mock_post.call_args_list[1]
    assert submit_call.kwargs["json"]["speech_models"] == [
        "universal-3-pro",
        "universal-2",
    ]
    assert submit_call.kwargs["json"]["speaker_labels"] is True
