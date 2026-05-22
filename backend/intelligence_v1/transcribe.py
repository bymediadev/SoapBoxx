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
        or "openai"
    )
    effective, _ = resolve_stt_for_coach(raw)
    return effective


def transcribe_file(file_path: str | Path) -> Dict[str, Any]:
    """
    Transcribe an audio file.

    Returns ``{"transcript": str, "segments": list, "service": str}``.
    Segments are empty unless a future STT backend provides them.
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
    text = tr.transcribe(audio_data)
    if not text or str(text).startswith("Error"):
        raise RuntimeError(str(text or "Transcription failed"))

    return {
        "transcript": str(text).strip(),
        "segments": [],
        "service": service,
        "source_path": str(path.resolve()),
    }
