"""AssemblyAI cloud transcription provider."""

from __future__ import annotations

import os

from backend.providers.constants import TRANSCRIPTION_ASSEMBLYAI
from backend.providers.transcription.transcriber_backed import TranscriberBackedProvider


class AssemblyAITranscriptionProvider(TranscriberBackedProvider):
    """Wraps ``Transcriber(service='assemblyai')``."""

    service = "assemblyai"
    name = TRANSCRIPTION_ASSEMBLYAI

    def is_available(self) -> bool:
        try:
            from backend.services.assemblyai_stt import assemblyai_api_key
        except ImportError:
            return bool((os.getenv("ASSEMBLYAI_API_KEY") or "").strip())
        return bool(assemblyai_api_key())
