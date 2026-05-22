"""Library aggregates for web UI (Lovable)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from backend.models import Episode, EpisodeFeatures, Podcast, TaxonomyNode
from backend.services.pipeline_status import resolve_episode_status


def get_library_stats(db: Session) -> Dict[str, Any]:
    episodes_total = int(db.scalar(select(func.count()).select_from(Episode)) or 0)
    shows_total = int(db.scalar(select(func.count()).select_from(Podcast)) or 0)
    domains_total = int(
        db.scalar(
            select(func.count()).select_from(TaxonomyNode).where(
                TaxonomyNode.node_type == "domain"
            )
        )
        or 0
    )

    measured_count = int(
        db.scalar(select(func.count()).select_from(EpisodeFeatures)) or 0
    )
    queued_count = int(
        db.scalar(
            select(func.count())
            .select_from(Episode)
            .where(Episode.pipeline_status.in_(("queued", "ingested", "new")))
        )
        or 0
    )
    processing_count = int(
        db.scalar(
            select(func.count())
            .select_from(Episode)
            .where(Episode.pipeline_status.in_(("transcribing", "ingesting")))
        )
        or 0
    )

    measured_pct = (
        round(100.0 * measured_count / episodes_total, 1) if episodes_total else 0.0
    )

    return {
        "episodes_total": episodes_total,
        "shows_total": shows_total,
        "domains_total": domains_total,
        "measured_count": measured_count,
        "measured_pct": measured_pct,
        "queued_count": queued_count,
        "processing_count": processing_count,
    }


def list_episodes(
    db: Session,
    *,
    podcast_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    q = (
        db.query(Episode)
        .options(
            joinedload(Episode.features),
            joinedload(Episode.translation),
            joinedload(Episode.podcast),
        )
        .order_by(Episode.published_at.desc().nullslast(), Episode.id.desc())
    )
    if podcast_id is not None:
        q = q.filter(Episode.podcast_id == podcast_id)
    rows = q.offset(offset).limit(min(limit, 200)).all()

    out: List[Dict[str, Any]] = []
    for ep in rows:
        out.append(
            {
                "id": int(ep.id),
                "podcast_id": int(ep.podcast_id),
                "podcast_name": ep.podcast.name if ep.podcast else "",
                "title": ep.title,
                "description": ep.description,
                "audio_url": ep.audio_url,
                "published_at": ep.published_at.isoformat() if ep.published_at else None,
                "status": resolve_episode_status(ep),
            }
        )
    return out
