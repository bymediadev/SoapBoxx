"""Local Whisper transcription provider."""

from __future__ import annotations

from backend.providers.constants import TRANSCRIPTION_WHISPER
from backend.providers.transcription.transcriber_backed import TranscriberBackedProvider


class WhisperTranscriptionProvider(TranscriberBackedProvider):
    """Wraps ``Transcriber(service='local')``."""

    service = "local"
    name = TRANSCRIPTION_WHISPER

    def is_available(self) -> bool:
        tr = self._get_transcriber()
        info = tr.get_local_model_info() if hasattr(tr, "get_local_model_info") else {}
        return bool(info.get("available"))
