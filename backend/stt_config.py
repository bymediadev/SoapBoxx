"""STT accuracy-mode defaults (Layer 0 — perception only)."""

from __future__ import annotations

import os


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


def accuracy_mode_enabled() -> bool:
    """Prefer fidelity over speed (larger models, longer timeouts, less compression)."""
    return _truthy("SOAPBOXX_STT_ACCURACY_MODE")


def groq_whisper_model() -> str:
    explicit = (os.getenv("SOAPBOXX_GROQ_WHISPER_MODEL") or "").strip()
    if explicit:
        return explicit
    if accuracy_mode_enabled():
        return "whisper-large-v3"
    return "whisper-large-v3-turbo"


def local_whisper_model() -> str:
    explicit = (os.getenv("SOAPBOXX_LOCAL_WHISPER_MODEL") or "").strip()
    if explicit:
        return explicit
    if accuracy_mode_enabled():
        return "medium"
    return "base"


def stt_http_timeout_seconds() -> float:
    raw = (os.getenv("SOAPBOXX_STT_HTTP_TIMEOUT") or "").strip()
    if raw:
        return float(raw)
    return 600.0 if accuracy_mode_enabled() else 300.0


def cloud_stt_soft_bytes(max_bytes: int) -> int:
    """When to start ffmpeg compression before cloud upload."""
    raw = (os.getenv("SOAPBOXX_STT_SOFT_BYTES") or "").strip()
    if raw:
        return int(raw)
    ratio = 0.98 if accuracy_mode_enabled() else 0.92
    return int(max_bytes * ratio)
