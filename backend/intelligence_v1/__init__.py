"""V1 transcription adapter — delegates to provider layer."""

from backend.providers.transcribe import transcribe_audio_file as transcribe_file

__all__ = ["transcribe_file"]
