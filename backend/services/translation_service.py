"""Translation layer — structural meaning only (Day 7)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures, EpisodeTranslation
from backend.services.pipeline_status import (
    STATUS_FAILED,
    STATUS_READY,
    record_event,
    set_episode_status,
)

_FORBIDDEN = re.compile(
    r"\b(good|bad|best|worst|score|rank|rating|should improve|you must)\b",
    re.I,
)


@dataclass
class TranslationResult:
    episode_id: int
    template_id: str
    insight_text: str


def _template_from_features(f: EpisodeFeatures) -> tuple[str, str]:
    ratio = float(f.host_guest_ratio or 0.5)
    questions = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)

    if ratio >= 0.62 and questions < 14:
        return (
            "A",
            "This episode has a high guest dominance structure, where the guest "
            "controls most of the narrative flow. The host contributes primarily "
            "through short guiding questions rather than extended commentary. "
            "The structure is consistent with conversational interview formats "
            "rather than scripted or segmented shows.",
        )
    if questions >= 18 and turns >= 8:
        return (
            "B",
            "This episode follows a highly structured interview pattern with "
            "frequent guiding questions from the host. Turn-taking is active, "
            "and the conversation advances through explicit question-and-answer "
            "cycles rather than long monologue blocks.",
        )
    return (
        "C",
        "This episode is narrative-driven with lower question density. "
        "Speaking turns are fewer and longer, suggesting extended explanation "
        "or storytelling segments rather than rapid interview pacing.",
    )


def run_translation(db: Session, episode_id: int) -> TranslationResult:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    features = db.get(EpisodeFeatures, episode_id)
    if not features:
        raise ValueError("Episode has no features; run feature extraction first")

    template_id, text = _template_from_features(features)
    if _FORBIDDEN.search(text):
        raise RuntimeError("Translation template violated forbidden language")

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
