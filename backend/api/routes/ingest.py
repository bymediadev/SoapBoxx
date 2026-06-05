"""Ingestion routes — Day 3 RSS."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.config import get_settings
from backend.api.deps import get_db
from backend.api.schemas import (
    PodcastSearchHitRead,
    PodcastSearchResponse,
    RssIngestRequest,
    RssIngestResponse,
)
from backend.services.podcast_discovery_service import search_podcasts_by_name
from backend.models import Podcast
from backend.services.rss_service import (
    dispatch_processing_for_episodes,
    ingest_rss_feed,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.get("/podcasts/search", response_model=PodcastSearchResponse)
def search_podcasts(
    q: str = Query(..., min_length=2, max_length=200, description="Podcast name"),
    limit: int = Query(15, ge=1, le=50),
) -> PodcastSearchResponse:
    """Find podcasts by name; each result includes an RSS feed URL for ingest."""
    try:
        hits = search_podcasts_by_name(q, limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Podcast search unavailable: {exc}",
        ) from exc
    return PodcastSearchResponse(
        query=q.strip(),
        results=[PodcastSearchHitRead(**h.to_dict()) for h in hits],
    )


@router.post("/rss", response_model=RssIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_rss(body: RssIngestRequest, db: Session = Depends(get_db)) -> RssIngestResponse:
    """Fetch RSS feed and create episodes (metadata only). Idempotent on guid."""
    try:
        result = ingest_rss_feed(
            db,
            body.rss_url.strip(),
            podcast_id=body.podcast_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"RSS ingest failed: {exc}",
        ) from exc
    settings = get_settings()
    dispatched_ids = (
        dispatch_processing_for_episodes(
            db,
            result.created_episode_ids,
            trigger="rss_ingest",
        )
        if settings.auto_process_on_ingest and result.created_episode_ids
        else []
    )
    backlog_dispatched = 0
    if settings.auto_process_on_ingest:
        from backend.services.episode_pipeline_service import drain_pending_pipeline

        backlog = drain_pending_pipeline(
            db,
            limit=settings.pipeline_sync_batch_size,
            trigger="rss_ingest_backlog",
            prefer_celery=True,
            exclude_episode_ids=dispatched_ids,
        )
        backlog_dispatched = backlog.get("dispatched", 0) + backlog.get("processed", 0)
    pod = db.get(Podcast, result.podcast_id)
    return RssIngestResponse(
        podcast_id=result.podcast_id,
        podcast_name=(pod.name if pod else "") or "",
        episodes_created=result.created,
        episodes_skipped=result.skipped,
        episodes_updated=result.updated,
        episodes_dispatched=len(dispatched_ids) + backlog_dispatched,
        episode_ids=result.episode_ids,
    )
