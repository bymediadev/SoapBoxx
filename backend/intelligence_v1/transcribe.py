"""Audio/video file → transcript (delegates to modular provider layer)."""

from __future__ import annotations

from backend.providers.transcribe import transcribe_audio_file as transcribe_file

__all__ = ["transcribe_file"]
