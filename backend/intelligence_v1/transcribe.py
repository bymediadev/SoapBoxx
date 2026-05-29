"""Audio/video file → transcript (reuses backend Transcriber)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import repo_root


def _resolve_stt_service() -> str:
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


def transcribe_file(file_path: str | Path) -> Dict[str, Any]:
    """
    Transcribe an audio file.

    Returns ``{"transcript": str, "segments": list, "service": str}``.

    When the STT backend supports Whisper ``verbose_json`` (OpenAI/Groq) or local
    Whisper, ``segments`` contains real ``start_time``/``end_time`` timestamps.
    Otherwise segments are empty and the pipeline falls back to text chunking.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")

    import sys

    root = repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    backend = root / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    try:
        from backend.transcriber import Transcriber
    except ImportError:
        from transcriber import Transcriber  # type: ignore

    service = _resolve_stt_service()
    tr = Transcriber(service=service)
    audio_data = path.read_bytes()
    detail = tr.transcribe_detailed(audio_data)
    error = str(detail.get("error") or "").strip()
    text = str(detail.get("transcript") or "").strip()
    if error or not text:
        msg = error.removeprefix("Error: ").strip() if error else "Transcription failed"
        raise ValueError(msg)

    return {
        "transcript": text,
        "segments": list(detail.get("segments") or []),
        "service": service,
        "source_path": str(path.resolve()),
    }
