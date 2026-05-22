"""Transcription + segmentation — Day 4 (metadata → text)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from backend.models import Episode, TranscriptSegment
from backend.services.pipeline_status import (
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_TRANSCRIBING,
    record_event,
    set_episode_status,
)

_SPEAKER_LINE = re.compile(
    r"^\s*(host|guest|speaker\s*\d+|interviewer|narrator)\s*:\s*",
    re.I,
)
_WPS = 2.5


@dataclass
class TranscriptionResult:
    episode_id: int
    transcript_length: int
    segment_count: int


def _words(text: str) -> int:
    return len((text or "").split())


def _estimate_seconds(word_count: int) -> float:
    return round(max(0.0, word_count / _WPS), 2)


def build_segments_from_transcript(transcript: str) -> List[dict]:
    """
    Build time-estimated segments from transcript text.

    Uses speaker lines or paragraphs; assigns synthetic start/end times.
    """
    text = (transcript or "").strip()
    if not text:
        return []

    chunks: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if _SPEAKER_LINE.match(line.strip()) and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))

    if len(chunks) <= 1:
        chunks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not chunks:
        chunks = [text]

    segments: List[dict] = []
    t = 0.0
    for chunk in chunks:
        dur = _estimate_seconds(_words(chunk))
        segments.append(
            {"start_time": t, "end_time": t + dur, "text": chunk.strip()}
        )
        t += dur
    return segments


def _download_audio(url: str, dest: Path, *, timeout: int = 120) -> None:
    req = Request(url, headers={"User-Agent": "SoapBoxx-V1/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        dest.write_bytes(resp.read())


def transcribe_episode(
    db: Session,
    episode_id: int,
    *,
    transcript: Optional[str] = None,
) -> TranscriptionResult:
    """
    Store full_transcript + transcript_segments on episode.

    If ``transcript`` is provided, skip STT (tests / paste path).
    Else requires ``episode.audio_url`` and runs Transcriber.
    """
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")

    set_episode_status(db, episode, STATUS_TRANSCRIBING, commit=False)
    record_event(
        db,
        "pipeline.transcribing",
        f"Transcribing: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        commit=False,
    )

    try:
        full_text = _run_transcription(episode, transcript)
    except Exception as exc:
        set_episode_status(
            db, episode, STATUS_FAILED, error=str(exc), commit=False
        )
        record_event(
            db,
            "pipeline.failed",
            f"Transcription failed: {exc}",
            podcast_id=int(episode.podcast_id),
            episode_id=int(episode.id),
            commit=False,
        )
        db.commit()
        raise

    segments = build_segments_from_transcript(full_text)
    episode.full_transcript = full_text

    db.query(TranscriptSegment).filter(
        TranscriptSegment.episode_id == episode_id
    ).delete()

    for seg in segments:
        db.add(
            TranscriptSegment(
                episode_id=episode_id,
                start_time=float(seg["start_time"]),
                end_time=float(seg["end_time"]),
                text=str(seg["text"]),
            )
        )
    set_episode_status(db, episode, STATUS_QUEUED, commit=False)
    record_event(
        db,
        "pipeline.transcribed",
        f"Transcript ready: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        meta={"segment_count": len(segments)},
        commit=False,
    )
    db.commit()
    return TranscriptionResult(
        episode_id=episode_id,
        transcript_length=len(full_text),
        segment_count=len(segments),
    )


def _run_transcription(episode: Episode, transcript: Optional[str]) -> str:
    if transcript is not None:
        full_text = transcript.strip()
    else:
        if not episode.audio_url:
            raise ValueError("Episode has no audio_url and no transcript provided")
        import tempfile

        from backend.intelligence_v1.transcribe import transcribe_file

        suffix = ".mp3"
        if "." in episode.audio_url.split("?")[0]:
            suffix = Path(episode.audio_url.split("?")[0]).suffix or suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            _download_audio(episode.audio_url, tmp_path)
            tr = transcribe_file(tmp_path)
            full_text = str(tr.get("transcript") or "").strip()
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    if len(full_text) < 40:
        raise ValueError("Transcript too short")
    return full_text
