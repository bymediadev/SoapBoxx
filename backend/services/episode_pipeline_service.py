"""Run full V1 episode pipeline: transcribe → features → translate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures, EpisodeTranslation
from backend.services.feature_service import run_feature_extraction
from backend.services.transcription_service import transcribe_episode
from backend.services.translation_service import run_translation


@dataclass
class EpisodePipelineResult:
    episode_id: int
    status: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    transcript_length: int = 0
    segment_count: int = 0
    template_id: Optional[str] = None
    insight_preview: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "status": self.status,
            "steps": self.steps,
            "transcript_length": self.transcript_length,
            "segment_count": self.segment_count,
            "template_id": self.template_id,
            "insight_preview": self.insight_preview,
        }


def run_episode_pipeline(
    db: Session,
    episode_id: int,
    *,
    transcript: Optional[str] = None,
    force_retranscribe: bool = False,
) -> EpisodePipelineResult:
    """
    Run follow-up for one episode: STT (or pasted transcript) → 7 metrics → template insight.

    Skips transcription when a transcript already exists unless ``force_retranscribe`` or
    ``transcript`` is provided. Always runs feature extraction and translation when possible.
    """
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")

    steps: List[Dict[str, Any]] = []
    has_transcript = bool((episode.full_transcript or "").strip())

    if transcript is not None or force_retranscribe or not has_transcript:
        tr = transcribe_episode(db, episode_id, transcript=transcript)
        steps.append(
            {
                "step": "transcribe",
                "ok": True,
                "transcript_length": tr.transcript_length,
                "segment_count": tr.segment_count,
            }
        )
        transcript_length = tr.transcript_length
        segment_count = tr.segment_count
    else:
        transcript_length = len((episode.full_transcript or "").strip())
        segment_count = 0
        steps.append({"step": "transcribe", "ok": True, "skipped": True})

    db.refresh(episode)
    feat = run_feature_extraction(db, episode_id)
    steps.append({"step": "features", "ok": True, "metrics": feat.features})

    trans = run_translation(db, episode_id)
    preview = trans.insight_text[:240] + ("…" if len(trans.insight_text) > 240 else "")
    steps.append(
        {
            "step": "translate",
            "ok": True,
            "template_id": trans.template_id,
        }
    )

    db.refresh(episode)
    final = "ready" if db.get(EpisodeTranslation, episode_id) else "measured"

    return EpisodePipelineResult(
        episode_id=episode_id,
        status=final,
        steps=steps,
        transcript_length=transcript_length,
        segment_count=segment_count,
        template_id=trans.template_id,
        insight_preview=preview,
    )


def process_queued_episodes(
    db: Session,
    *,
    limit: int = 1,
) -> Dict[str, Any]:
    """Process up to ``limit`` episodes that do not yet have a translation."""
    pending = (
        db.query(Episode)
        .outerjoin(EpisodeTranslation, EpisodeTranslation.episode_id == Episode.id)
        .filter(EpisodeTranslation.episode_id.is_(None))
        .order_by(Episode.id.asc())
        .limit(max(1, min(limit, 25)))
        .all()
    )

    results: List[Dict[str, Any]] = []
    for ep in pending:
        try:
            out = run_episode_pipeline(db, int(ep.id))
            results.append({"episode_id": int(ep.id), "ok": True, **out.to_dict()})
        except Exception as exc:
            results.append(
                {
                    "episode_id": int(ep.id),
                    "ok": False,
                    "error": str(exc),
                    "title": ep.title,
                }
            )

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "requested": limit,
        "attempted": len(pending),
        "succeeded": ok_count,
        "failed": len(pending) - ok_count,
        "results": results,
    }
