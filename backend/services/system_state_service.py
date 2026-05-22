"""System visibility: pipeline counts + activity feed."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.models import Episode, SystemEvent
from backend.services.pipeline_status import ALL_STATUSES, resolve_episode_status


def get_pipeline_status(db: Session) -> Dict[str, Any]:
    rows = db.execute(
        select(Episode.pipeline_status, func.count())
        .group_by(Episode.pipeline_status)
    ).all()
    by_status = {str(status): int(cnt) for status, cnt in rows}

    # Include resolved counts for UI (handles legacy rows)
    resolved: Dict[str, int] = {s: 0 for s in ALL_STATUSES}
    episodes = db.query(Episode).all()
    for ep in episodes:
        resolved[resolve_episode_status(ep)] = resolved.get(resolve_episode_status(ep), 0) + 1

    processing = (
        by_status.get("transcribing", 0)
        + by_status.get("ingesting", 0)
        + resolved.get("transcribing", 0)
    )

    return {
        "by_status": {s: resolved.get(s, 0) for s in ALL_STATUSES},
        "processing_count": int(processing),
        "episodes_total": len(episodes),
    }


def get_system_activity(db: Session, *, limit: int = 50) -> List[Dict[str, Any]]:
    limit = min(max(limit, 1), 200)
    events = (
        db.query(SystemEvent)
        .order_by(SystemEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for ev in events:
        meta = None
        if ev.meta_json:
            try:
                meta = json.loads(ev.meta_json)
            except json.JSONDecodeError:
                meta = {"raw": ev.meta_json}
        out.append(
            {
                "id": int(ev.id),
                "event_type": ev.event_type,
                "message": ev.message,
                "podcast_id": ev.podcast_id,
                "episode_id": ev.episode_id,
                "meta": meta,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
        )
    return out
