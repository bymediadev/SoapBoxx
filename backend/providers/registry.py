"""Provider registry — transcription only (V1 insight library)."""

from __future__ import annotations

import os
from typing import Dict, Optional, Type

from backend.providers.constants import (
    DEFAULT_TRANSCRIPTION,
    DEFAULT_TRANSCRIPTION_PROVIDER,
    TRANSCRIPTION_ASSEMBLYAI,
    TRANSCRIPTION_PROVIDER_ASSEMBLYAI,
    TRANSCRIPTION_PROVIDER_WHISPER,
    TRANSCRIPTION_WHISPER,
)
from backend.providers.transcription.assemblyai_provider import AssemblyAITranscriptionProvider
from backend.providers.transcription.base import TranscriptionProvider
from backend.providers.transcription.whisper_provider import WhisperTranscriptionProvider

_TRANSCRIPTION_REGISTRY: Dict[str, Type[TranscriptionProvider]] = {
    TRANSCRIPTION_WHISPER: WhisperTranscriptionProvider,
    TRANSCRIPTION_ASSEMBLYAI: AssemblyAITranscriptionProvider,
}


def _normalize_name(raw: str) -> str:
    return (raw or "").strip().lower().replace("-", "_")


def get_transcription_provider_name() -> Optional[str]:
    """
    Configured transcription provider, or ``None`` for legacy ``Transcriber``
    resolution via ``SOAPBOXX_TRANSCRIPTION_SERVICE`` (assemblyai / local).
    """
    explicit = _normalize_name(os.getenv("SOAPBOXX_TRANSCRIPTION_PROVIDER", ""))
    if explicit in _TRANSCRIPTION_REGISTRY:
        return explicit
    return None


def uses_modular_transcription() -> bool:
    return get_transcription_provider_name() is not None


def load_provider_config() -> Dict[str, str]:
    return {
        "transcription_provider": get_transcription_provider_name() or "legacy",
    }


def create_transcription_provider(name: Optional[str] = None) -> TranscriptionProvider:
    key = _normalize_name(name or get_transcription_provider_name() or DEFAULT_TRANSCRIPTION)
    if key not in _TRANSCRIPTION_REGISTRY:
        known = ", ".join(sorted(_TRANSCRIPTION_REGISTRY))
        raise ValueError(f"Unknown transcription provider '{key}'. Known: {known}")
    return _TRANSCRIPTION_REGISTRY[key]()
