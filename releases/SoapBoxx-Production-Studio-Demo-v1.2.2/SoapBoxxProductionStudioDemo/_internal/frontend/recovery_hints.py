"""Classify common SoapBoxx failures and attach actionable recovery hints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RecoveryHints:
    """Extra UI copy and whether to offer jumping to Settings."""

    informative_text: str
    offer_open_settings: bool


def infer_recovery(
    title: str, message: str, detail: Optional[str] = None
) -> RecoveryHints:
    """Infer recovery hints from error title/message/detail (best-effort)."""
    blob = f"{title or ''}\n{message or ''}\n{detail or ''}".lower()
    parts: list[str] = []
    open_settings = False

    # Ollama / offline LLM
    if any(
        x in blob
        for x in (
            "soapboxx_ollama_model",
            "ollama model",
            "/api/chat",
            "connection refused",
        )
    ) or (
        "ollama" in blob
        and any(
            x in blob
            for x in (
                "not set",
                "not configured",
                "missing",
                "refused",
                "unreachable",
                "failed",
            )
        )
    ):
        parts.append(
            "Offline LLM: open Settings and set Offline model (e.g. llama3.1:8b), "
            "ensure Ollama is running, then run `ollama pull <model>` in a terminal."
        )
        open_settings = True

    # Question extraction explicitly in offline mode (caller passes mode=offline)
    if "question extraction" in blob and "offline" in blob:
        parts.append(
            "Question extraction (offline): set SOAPBOXX_OLLAMA_MODEL or the Offline model "
            "field in Settings, confirm Ollama is reachable at OLLAMA_HOST."
        )
        open_settings = True

    # OpenAI / Whisper API
    if (
        any(x in blob for x in ("openai", "whisper", "gpt-", "api key"))
        and any(
            x in blob
            for x in (
                "401",
                "403",
                "unauthorized",
                "authentication",
                "invalid",
                "not configured",
                "missing",
                "incorrect api key",
                "rate limit",
            )
        )
    ) or ("openai api key not configured" in blob):
        parts.append(
            "OpenAI: set OPENAI_API_KEY in your environment or repo-root `.env`, "
            "then restart SoapBoxx (Settings shows current readiness)."
        )
        open_settings = True

    # Question extraction openai mode
    if "question extraction" in blob and "openai" in blob:
        parts.append(
            "Question extraction (OpenAI): ensure OPENAI_API_KEY is valid and the "
            "OpenAI client is available in this install."
        )
        open_settings = True

    # Azure Speech (optional SDK)
    if "azure" in blob and any(
        x in blob for x in ("not available", "not configured", "sdk", "speech")
    ):
        parts.append(
            "Azure Speech: install `azure-cognitiveservices-speech` and configure "
            "credentials per SoapBoxx/Azure docs."
        )

    # AssemblyAI
    if "assemblyai" in blob and any(
        x in blob for x in ("not available", "not configured", "api")
    ):
        parts.append(
            "AssemblyAI: set your AssemblyAI API key in the environment as required "
            "by your SoapBoxx setup, then retry."
        )

    # Local Whisper path
    if "local" in blob and any(
        x in blob for x in ("whisper", "transcription", "transcribe", "model")
    ):
        parts.append(
            "Local STT: verify local Whisper dependencies/models are installed "
            "(see project README) or switch STT to OpenAI in Settings."
        )

    # Backend / core unavailable
    if any(
        x in blob
        for x in (
            "backend not available",
            "backend initialization failed",
            "initialization failed",
            "soapboxxcore",
        )
    ):
        parts.append(
            "Backend startup: confirm Python dependencies are installed, review "
            "the terminal log for the first traceback, then retry after fixing imports/env."
        )

    if not parts:
        return RecoveryHints("", False)

    deduped: list[str] = []
    for p in parts:
        if p not in deduped:
            deduped.append(p)

    informative = "\n".join(f"- {p}" for p in deduped)
    text = f"What you can try:\n{informative}"
    return RecoveryHints(text, open_settings)
