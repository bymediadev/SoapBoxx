"""Base implementation for providers backed by ``Transcriber``."""

from __future__ import annotations

from typing import Any, Optional

from backend.core.models import Transcript
from backend.providers.transcription.base import AudioInput, TranscriptionProvider
from backend.providers.transcription.utils import (
    detail_to_transcript,
    load_transcriber,
    read_audio_bytes,
    source_path_for,
)


class TranscriberBackedProvider(TranscriptionProvider):
    """Shared logic for Whisper (local) and AssemblyAI cloud STT."""

    service: str = ""
    name: str = ""

    def __init__(self, *, transcriber: Any = None) -> None:
        self._transcriber = transcriber

    @property
    def provider_name(self) -> str:
        return self.name

    def _get_transcriber(self):
        if self._transcriber is not None:
            return self._transcriber
        self._transcriber = load_transcriber(self.service)
        return self._transcriber

    def transcribe(self, audio_input: AudioInput) -> Transcript:
        audio_data = read_audio_bytes(audio_input)
        detail = self._get_transcriber().transcribe_detailed(audio_data)
        if isinstance(detail, str):
            detail = {"transcript": detail, "segments": [], "service": self.service}
        detail.setdefault("service", self.service)
        return detail_to_transcript(
            detail,
            provider_name=self.name,
            source_path=source_path_for(audio_input),
        )
