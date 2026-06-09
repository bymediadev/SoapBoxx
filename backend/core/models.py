"""Standard schemas for transcription provider outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TranscriptSegment:
    start_time: float
    end_time: float
    text: str
    speaker: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class Transcript:
    text: str
    segments: List[TranscriptSegment] = field(default_factory=list)
    speaker_labels: Optional[List[str]] = None
    confidence: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "segments": [
                {
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "text": seg.text,
                    **({"speaker": seg.speaker} if seg.speaker else {}),
                    **({"confidence": seg.confidence} if seg.confidence is not None else {}),
                }
                for seg in self.segments
            ],
            "speaker_labels": self.speaker_labels,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transcript":
        segments = []
        for raw in data.get("segments") or []:
            if not isinstance(raw, dict):
                continue
            segments.append(
                TranscriptSegment(
                    start_time=float(raw.get("start_time", raw.get("start", 0.0)) or 0.0),
                    end_time=float(raw.get("end_time", raw.get("end", 0.0)) or 0.0),
                    text=str(raw.get("text") or "").strip(),
                    speaker=raw.get("speaker"),
                    confidence=raw.get("confidence"),
                )
            )
        return cls(
            text=str(data.get("text") or "").strip(),
            segments=segments,
            speaker_labels=data.get("speaker_labels"),
            confidence=data.get("confidence"),
            metadata=dict(data.get("metadata") or {}),
        )
