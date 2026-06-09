"""Unified file transcription — modular providers or legacy Transcriber."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

from backend.core.models import Transcript
from backend.providers.registry import (
    create_transcription_provider,
    get_transcription_provider_name,
    uses_modular_transcription,
)


def _resolve_legacy_stt_service() -> str:
    try:
        from backend.coach_stt import resolve_stt_for_coach
    except ImportError:
        from coach_stt import resolve_stt_for_coach  # type: ignore

    raw = (
        os.getenv("SOAPBOXX_TRANSCRIPTION_SERVICE")
        or os.getenv("SOAPBOXX_EPISODE_ANALYSIS_STT")
        or ""
    ).strip()
    if not raw:
        groq = (os.getenv("SOAPBOXX_GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or "").strip()
        openai = (os.getenv("OPENAI_API_KEY") or "").strip()
        if groq:
            raw = "groq"
        elif openai:
            raw = "openai"
        else:
            raw = "openai"
    effective, _ = resolve_stt_for_coach(raw)
    return effective


def transcript_to_ingest_dict(transcript: Transcript, *, service: str) -> Dict[str, Any]:
    """Format used by V1 ingestion and ``transcription_service``."""
    return {
        "transcript": transcript.text,
        "segments": [
            {
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "text": seg.text,
                **({"speaker": seg.speaker} if seg.speaker else {}),
            }
            for seg in transcript.segments
        ],
        "service": service,
        "source_path": transcript.metadata.get("source_path"),
    }


def transcribe_audio_file(file_path: str | Path) -> Dict[str, Any]:
    """
    Transcribe an audio file to the standard ingest dict.

    Uses ``SOAPBOXX_TRANSCRIPTION_PROVIDER`` when set (``whisper`` | ``assemblyai``);
    otherwise falls back to legacy ``Transcriber`` service resolution.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    source_path = str(path.resolve())

    if uses_modular_transcription():
        provider = create_transcription_provider(get_transcription_provider_name())
        transcript = provider.transcribe(path)
        transcript.metadata.setdefault("source_path", source_path)
        service = str(transcript.metadata.get("service") or provider.provider_name)
        out = transcript_to_ingest_dict(transcript, service=service)
        out["source_path"] = source_path
        return out

    root = Path(__file__).resolve().parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    backend = root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from backend.providers.transcription.utils import load_transcriber

    service = _resolve_legacy_stt_service()
    detail = load_transcriber(service).transcribe_detailed(path.read_bytes())
    error = str(detail.get("error") or "").strip()
    text = str(detail.get("transcript") or "").strip()
    if error or not text:
        msg = error.removeprefix("Error: ").strip() if error else "Transcription failed"
        raise ValueError(msg)

    return {
        "transcript": text,
        "segments": list(detail.get("segments") or []),
        "service": service,
        "source_path": source_path,
    }
