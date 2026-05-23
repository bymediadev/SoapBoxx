"""
STT resolution for Record → Transcribe → Episode Coach Report.

Azure Speech is not supported on this path (SDK path is not implemented). Map to
openai or local when Settings still reference azure.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

COACH_SUPPORTED_STT: Tuple[str, ...] = ("openai", "groq", "local", "assemblyai")

_AZURE_COACH_MSG = (
    "Azure Speech is not supported for Studio transcription or the Coach loop. "
    "Use openai or local in Settings (or set OPENAI_API_KEY / SOAPBOXX_OLLAMA_MODEL)."
)


def _ollama_configured() -> bool:
    return bool((os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip())


def _openai_configured() -> bool:
    return bool((os.getenv("OPENAI_API_KEY") or "").strip())


def _groq_configured() -> bool:
    return bool(
        (os.getenv("SOAPBOXX_GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or "").strip()
    )


def resolve_stt_for_coach(requested: str) -> Tuple[str, Optional[str]]:
    """
    Return (effective_service, warning_message).

    ``azure`` is remapped to ``local`` when Ollama is configured, else ``openai``.
    """
    raw = (requested or "").strip().lower()
    if raw in COACH_SUPPORTED_STT:
        if raw == "openai" and not _openai_configured() and _groq_configured():
            return (
                "groq",
                "OPENAI_API_KEY not set; using Groq Whisper (free tier).",
            )
        return raw, None
    if raw == "azure":
        if _ollama_configured():
            return (
                "local",
                "Azure Speech is not supported for Coach. Using local transcription.",
            )
        if _groq_configured():
            return (
                "groq",
                "Azure Speech is not supported for Coach. Using Groq Whisper.",
            )
        if _openai_configured():
            return (
                "openai",
                "Azure Speech is not supported for Coach. Using OpenAI transcription.",
            )
        return "local", _AZURE_COACH_MSG
    if _groq_configured():
        return "groq", None
    if _ollama_configured():
        return "local", None
    if _openai_configured():
        return "openai", None
    return "openai", None


def coach_stt_validation_error(service: str) -> Optional[str]:
    """Non-empty when Settings should block save for this STT/transcription choice."""
    if (service or "").strip().lower() == "azure":
        return _AZURE_COACH_MSG
    return None
