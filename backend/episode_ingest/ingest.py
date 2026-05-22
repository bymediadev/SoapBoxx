"""Unified episode ingestion for the post-record analytics product."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class IngestResult:
    """Normalized output every ingestion path must produce."""

    transcript: str
    title: str = ""
    creator: str = ""
    source_type: str = "paste"  # youtube | transcript_file | audio_file | paste
    source_ref: str = ""
    video_id: str = ""
    warnings: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript": self.transcript,
            "title": self.title,
            "creator": self.creator,
            "source_type": self.source_type,
            "source_ref": self.source_ref,
            "video_id": self.video_id,
            "warnings": list(self.warnings),
            "extra": dict(self.extra),
        }


def ingest_from_text(
    text: str,
    *,
    title: str = "",
    source_ref: str = "paste",
) -> IngestResult:
    from backend.episode_coach_report import prepare_coach_transcript

    body, import_title = prepare_coach_transcript(text)
    return IngestResult(
        transcript=body,
        title=(title or import_title or "Pasted episode").strip(),
        creator="",
        source_type="paste",
        source_ref=source_ref,
    )


def ingest_from_transcript_file(path: str | Path, *, title: str = "") -> IngestResult:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Transcript not found: {p}")
    raw = p.read_text(encoding="utf-8", errors="replace")
    out = ingest_from_text(raw, title=title or p.stem, source_ref=str(p.resolve()))
    out.source_type = "transcript_file"
    return out


def ingest_from_audio_file(path: str | Path, *, title: str = "") -> IngestResult:
    from backend.intelligence_v1.transcribe import transcribe_file

    p = Path(path)
    tr = transcribe_file(p)
    tx = str(tr.get("transcript") or "").strip()
    if not tx:
        raise RuntimeError("Transcription returned empty text")
    return IngestResult(
        transcript=tx,
        title=(title or p.stem).strip(),
        creator="",
        source_type="audio_file",
        source_ref=str(p.resolve()),
        extra={"stt_service": tr.get("service")},
    )


def ingest_from_youtube_url(
    url: str,
    *,
    title: str = "",
    creator: str = "",
    transcript_mode: str = "auto",
    cache_dir: Optional[Path] = None,
) -> IngestResult:
    from .youtube_source import fetch_youtube_episode

    return fetch_youtube_episode(
        url,
        title=title,
        creator=creator,
        transcript_mode=transcript_mode,
        cache_dir=cache_dir,
    )
