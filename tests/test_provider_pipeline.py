"""Tests for modular transcription providers."""

from __future__ import annotations

from backend.core.models import Transcript, TranscriptSegment
from backend.providers.registry import (
    create_transcription_provider,
    load_provider_config,
)
from backend.providers.transcription.base import TranscriptionProvider


class _StubTranscription(TranscriptionProvider):
    @property
    def provider_name(self) -> str:
        return "stub_tx"

    def transcribe(self, audio_input) -> Transcript:
        return Transcript(
            text="Hello from stub transcription.",
            segments=[
                TranscriptSegment(start_time=0.0, end_time=1.5, text="Hello from stub transcription.")
            ],
            metadata={"provider": "stub_tx", "duration_seconds": 1.5},
        )


def test_provider_factory_whisper_and_assemblyai():
    whisper = create_transcription_provider("whisper")
    assembly = create_transcription_provider("assemblyai")
    assert whisper.provider_name == "whisper"
    assert assembly.provider_name == "assemblyai"


def test_load_provider_config_defaults(monkeypatch):
    monkeypatch.delenv("SOAPBOXX_TRANSCRIPTION_PROVIDER", raising=False)
    cfg = load_provider_config()
    assert cfg["transcription_provider"] == "legacy"


def test_load_provider_config_env_override(monkeypatch):
    monkeypatch.setenv("SOAPBOXX_TRANSCRIPTION_PROVIDER", "assemblyai")
    cfg = load_provider_config()
    assert cfg["transcription_provider"] == "assemblyai"


def test_transcript_round_trip_dict():
    original = Transcript(
        text="Line one.",
        segments=[TranscriptSegment(0.0, 2.0, "Line one.", speaker="Host")],
        speaker_labels=["Host"],
        metadata={"provider": "stub"},
    )
    restored = Transcript.from_dict(original.to_dict())
    assert restored.text == original.text
    assert restored.segments[0].speaker == "Host"
