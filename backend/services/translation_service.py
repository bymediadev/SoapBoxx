"""Translation layer — structural coaching copy (Day 7, rule-based only)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures, EpisodeTranslation
from backend.services.coaching_report_service import (
    build_coaching_report,
    synthesis_insight_text,
)
from backend.services.pipeline_status import (
    STATUS_READY,
    record_event,
    set_episode_status,
)


@dataclass
class TranslationResult:
    episode_id: int
    template_id: str
    insight_text: str


from backend.services.template_classification import template_id_from_features


def run_translation(db: Session, episode_id: int) -> TranslationResult:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    features = db.get(EpisodeFeatures, episode_id)
    if not features:
        raise ValueError("Episode has no features; run feature extraction first")

    report = build_coaching_report(db, features)
    template_id = template_id_from_features(features)
    text = synthesis_insight_text(report)

    row = db.get(EpisodeTranslation, episode_id)
    if not row:
        row = EpisodeTranslation(episode_id=episode_id)
        db.add(row)
    row.template_id = template_id
    row.insight_text = text
    set_episode_status(db, episode, STATUS_READY, commit=False)
    record_event(
        db,
        "pipeline.ready",
        f"Insight ready: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        meta={"template_id": template_id},
        commit=False,
    )
    db.commit()
    return TranslationResult(
        episode_id=episode_id,
        template_id=template_id,
        insight_text=text,
    )
