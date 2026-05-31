"""Ingestion routes — Day 3 RSS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.config import get_settings
from backend.api.deps import get_db
from backend.api.schemas import RssIngestRequest, RssIngestResponse
from backend.services.rss_service import (
    dispatch_processing_for_episodes,
    ingest_rss_feed,
)

router = APIRouter(prefix="/ingest", tags=["ingest"])


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
    return RssIngestResponse(
        podcast_id=result.podcast_id,
        episodes_created=result.created,
        episodes_skipped=result.skipped,
        episodes_dispatched=len(dispatched_ids) + backlog_dispatched,
        episode_ids=result.episode_ids,
    )
