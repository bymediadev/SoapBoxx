"""Transcription provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from backend.core.models import Transcript

AudioInput = Union[bytes, str, Path]


class TranscriptionProvider(ABC):
    """Standard interface for speech-to-text backends."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable provider identifier (e.g. ``whisper``, ``assemblyai``)."""

    @abstractmethod
    def transcribe(self, audio_input: AudioInput) -> Transcript:
        """Transcribe audio and return a standardized ``Transcript``."""

    def is_available(self) -> bool:
        """Return True when the provider can accept work in the current environment."""
        return True
