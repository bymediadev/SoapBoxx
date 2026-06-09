"""Shared transcription provider helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.core.models import Transcript, TranscriptSegment

AudioInput = Union[bytes, str, Path]


def read_audio_bytes(audio_input: AudioInput) -> bytes:
    if isinstance(audio_input, bytes):
        return audio_input
    path = Path(audio_input)
    if not path.is_file():
        raise FileNotFoundError(f"Audio file not found: {path}")
    return path.read_bytes()


def source_path_for(audio_input: AudioInput) -> Optional[str]:
    if isinstance(audio_input, bytes):
        return None
    return str(Path(audio_input).resolve())


def detail_to_transcript(
    detail: Dict[str, Any],
    *,
    provider_name: str,
    source_path: Optional[str] = None,
) -> Transcript:
    error = str(detail.get("error") or "").strip()
    text = str(detail.get("transcript") or "").strip()
    if error or not text:
        msg = error.removeprefix("Error: ").strip() if error else "Transcription failed"
        raise ValueError(msg)

    segments: List[TranscriptSegment] = []
    speakers: List[str] = []
    for raw in detail.get("segments") or []:
        if not isinstance(raw, dict):
            continue
        speaker = raw.get("speaker")
        if speaker and speaker not in speakers:
            speakers.append(str(speaker))
        segments.append(
            TranscriptSegment(
                start_time=float(raw.get("start_time", raw.get("start", 0.0)) or 0.0),
                end_time=float(raw.get("end_time", raw.get("end", 0.0)) or 0.0),
                text=str(raw.get("text") or "").strip(),
                speaker=str(speaker) if speaker else None,
                confidence=raw.get("confidence"),
            )
        )

    metadata: Dict[str, Any] = {
        "provider": provider_name,
        "service": detail.get("service") or provider_name,
    }
    if source_path:
        metadata["source_path"] = source_path
    if detail.get("diarized"):
        metadata["diarized"] = True
    if segments:
        metadata["duration_seconds"] = segments[-1].end_time

    return Transcript(
        text=text,
        segments=segments,
        speaker_labels=speakers or None,
        confidence=detail.get("confidence"),
        metadata=metadata,
    )


def load_transcriber(service: str):
    try:
        from backend.transcriber import Transcriber
    except ImportError:
        from transcriber import Transcriber  # type: ignore

    return Transcriber(service=service)
