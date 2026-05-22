"""Episode lifecycle + system activity (truth layer for UI)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from backend.models import Episode, SystemEvent

# Lifecycle: new → ingested → queued → transcribing → measured → ready (+ ingesting, failed)
STATUS_NEW = "new"
STATUS_INGESTING = "ingesting"
STATUS_INGESTED = "ingested"
STATUS_QUEUED = "queued"
STATUS_TRANSCRIBING = "transcribing"
STATUS_MEASURED = "measured"
STATUS_READY = "ready"
STATUS_FAILED = "failed"

ALL_STATUSES = (
    STATUS_NEW,
    STATUS_INGESTING,
    STATUS_INGESTED,
    STATUS_QUEUED,
    STATUS_TRANSCRIBING,
    STATUS_MEASURED,
    STATUS_READY,
    STATUS_FAILED,
)


def set_episode_status(
    db: Session,
    episode: Episode,
    status: str,
    *,
    error: Optional[str] = None,
    commit: bool = True,
) -> None:
    if status not in ALL_STATUSES:
        raise ValueError(f"Invalid pipeline status: {status}")
    episode.pipeline_status = status
    episode.pipeline_error = error
    episode.pipeline_updated_at = datetime.now(timezone.utc)
    if commit:
        db.commit()


def record_event(
    db: Session,
    event_type: str,
    message: str,
    *,
    podcast_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
    commit: bool = True,
) -> SystemEvent:
    row = SystemEvent(
        event_type=event_type,
        message=message,
        podcast_id=podcast_id,
        episode_id=episode_id,
        meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def resolve_episode_status(episode: Episode) -> str:
    """Stored status + derived truth from pipeline artifacts (legacy-safe)."""
    if episode.translation is not None:
        return STATUS_READY
    if episode.features is not None:
        return STATUS_MEASURED
    stored = (episode.pipeline_status or "").strip()
    if stored == STATUS_FAILED:
        return STATUS_FAILED
    if stored == STATUS_TRANSCRIBING:
        return STATUS_TRANSCRIBING
    if stored == STATUS_INGESTING:
        return STATUS_INGESTING
    if (episode.full_transcript or "").strip():
        return STATUS_QUEUED
    if stored in ALL_STATUSES:
        return stored
    return STATUS_NEW


def episode_state_payload(db: Session, episode_id: int) -> Dict[str, Any]:
    from sqlalchemy.orm import joinedload

    episode = (
        db.query(Episode)
        .options(
            joinedload(Episode.features),
            joinedload(Episode.translation),
            joinedload(Episode.podcast),
        )
        .filter(Episode.id == episode_id)
        .first()
    )
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")

    status = resolve_episode_status(episode)
    steps = {
        "ingested": status
        in (
            STATUS_INGESTED,
            STATUS_QUEUED,
            STATUS_TRANSCRIBING,
            STATUS_MEASURED,
            STATUS_READY,
        ),
        "transcribed": bool((episode.full_transcript or "").strip()),
        "measured": episode.features is not None,
        "insight_ready": episode.translation is not None,
    }
    return {
        "episode_id": int(episode.id),
        "podcast_id": int(episode.podcast_id),
        "podcast_name": episode.podcast.name if episode.podcast else "",
        "title": episode.title,
        "status": status,
        "pipeline_error": episode.pipeline_error,
        "pipeline_updated_at": (
            episode.pipeline_updated_at.isoformat()
            if episode.pipeline_updated_at
            else None
        ),
        "steps": steps,
        "next_action": _next_action(status, steps),
    }


def _next_action(status: str, steps: Dict[str, bool]) -> Optional[str]:
    if status == STATUS_FAILED:
        return "retry"
    if status == STATUS_TRANSCRIBING or status == STATUS_INGESTING:
        return "wait"
    if status == STATUS_READY:
        return None
    if steps.get("measured") and not steps.get("insight_ready"):
        return "translate"
    if steps.get("transcribed") and not steps.get("measured"):
        return "features"
    if status in (STATUS_QUEUED, STATUS_INGESTED, STATUS_NEW):
        return "transcribe"
    return None


def queue_episode(db: Session, episode_id: int) -> Episode:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    set_episode_status(db, episode, STATUS_QUEUED, commit=False)
    record_event(
        db,
        "episode.queued",
        f"Queued for processing: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        commit=False,
    )
    db.commit()
    db.refresh(episode)
    return episode
