"""Pipeline status — living system counts."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.config import get_settings
from backend.api.deps import get_db, get_session_factory
from backend.api.schemas import (
    BacklogDispatchResponse,
    ProcessBatchResponse,
    RssSyncResponse,
)
from backend.services.rss_service import sync_saved_rss_feeds
from backend.services.episode_pipeline_service import (
    clear_and_requeue_for_published_path,
    drain_pending_pipeline,
    process_queued_episodes,
)
from backend.services.system_state_service import get_pipeline_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


def _kick_backlog_on_boot() -> None:
    """Drain pending episodes after deploy (Celery if worker live, else sync)."""
    settings = get_settings()
    limit = settings.pipeline_boot_dispatch_limit
    if limit <= 0:
        return

    def _run() -> None:
        db = get_session_factory()()
        try:
            from backend.services.episode_pipeline_service import celery_worker_available

            # Without a worker, prefer sync so Redis does not collect dead jobs.
            prefer = celery_worker_available()
            # Sync path is heavy on free tier — process a small batch only.
            sync_limit = min(limit, 2) if not prefer else limit
            out = drain_pending_pipeline(
                db,
                limit=sync_limit,
                trigger="api_boot",
                prefer_celery=prefer,
            )
            logger.info("Boot backlog dispatch: %s", out)
        except Exception:
            logger.exception("Boot backlog dispatch failed")
        finally:
            db.close()

    threading.Thread(target=_run, name="pipeline-boot-dispatch", daemon=True).start()


def register_pipeline_startup() -> None:
    """Call from app factory — dispatches pending episodes when configured."""
    settings = get_settings()
    if settings.pipeline_boot_dispatch_limit <= 0:
        return
    try:
        from backend.api.deps import check_redis

        if check_redis().get("status") != "connected":
            logger.info(
                "Skipping boot backlog dispatch (Redis not connected — use POST /pipeline/process)"
            )
            return
    except Exception:
        logger.info("Skipping boot backlog dispatch (Redis check failed)")
        return
    _kick_backlog_on_boot()


@router.get("/status")
def pipeline_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Episode counts by lifecycle state + active processing."""
    return get_pipeline_status(db)


@router.post("/dispatch-backlog", response_model=BacklogDispatchResponse)
def dispatch_backlog(
    limit: int = Query(
        100,
        ge=1,
        le=400,
        description="Max pending episodes to queue for Celery (requires worker + Redis)",
    ),
    sync_fallback: bool = Query(
        True,
        description="If Celery unavailable, process up to limit on this API instance",
    ),
    db: Session = Depends(get_db),
) -> BacklogDispatchResponse:
    """
    Queue ingested-but-unprocessed episodes (e.g. Planet Money backlog).

    Prefer Celery; optionally runs pipeline synchronously when no worker/Redis.
    """
    try:
        out = drain_pending_pipeline(
            db,
            limit=limit,
            trigger="api_dispatch_backlog",
            prefer_celery=True,
        )
        if sync_fallback and out.get("mode") == "none":
            out = drain_pending_pipeline(
                db,
                limit=min(limit, 10),
                trigger="api_dispatch_backlog_sync",
                prefer_celery=False,
            )
        elif sync_fallback and out.get("dispatched", 0) == 0 and out.get("pending", 0) > 0:
            sync_out = drain_pending_pipeline(
                db,
                limit=min(limit, 5),
                trigger="api_dispatch_backlog_sync",
                prefer_celery=False,
            )
            out["processed"] = sync_out.get("processed", 0)
            out["mode"] = sync_out.get("mode", out.get("mode"))
            if sync_out.get("results"):
                out["results"] = sync_out["results"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return BacklogDispatchResponse(
        pending=int(out.get("pending", 0)),
        dispatched=int(out.get("dispatched", 0)),
        processed=int(out.get("processed", 0)),
        mode=str(out.get("mode", "none")),
        episode_ids=list(out.get("episode_ids") or []),
    )


@router.post("/sync-feeds", response_model=RssSyncResponse)
def sync_feeds(
    x_cron_secret: str | None = Header(default=None, alias="X-Cron-Secret"),
    db: Session = Depends(get_db),
) -> RssSyncResponse:
    """
    Re-ingest every stored RSS feed and dispatch processing for new episodes.

    Requires ``SOAPBOXX_CRON_SECRET`` on the API and matching ``X-Cron-Secret`` header.
    Prefer Celery beat on ``soapboxx-worker`` (``soapboxx.sync_rss_feeds``) when running.
    """
    settings = get_settings()
    secret = (settings.cron_secret or os.environ.get("SOAPBOXX_CRON_SECRET") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SOAPBOXX_CRON_SECRET not configured on API",
        )
    if (x_cron_secret or "").strip() != secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-Cron-Secret",
        )
    try:
        summary = sync_saved_rss_feeds(db, dispatch_processing=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return RssSyncResponse(**summary.to_dict())


@router.post("/process", response_model=ProcessBatchResponse)
def process_queued(
    limit: int = Query(
        1,
        ge=1,
        le=25,
        description="Max episodes to process synchronously on API",
    ),
    db: Session = Depends(get_db),
) -> ProcessBatchResponse:
    """Run transcribe → features → translate (+ audio motion) on episodes without translation."""
    try:
        payload = process_queued_episodes(db, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return ProcessBatchResponse(**payload)


@router.post("/reset-queue")
def reset_queue(
    process_limit: int = Query(
        3,
        ge=0,
        le=10,
        description="After reset, sync-process this many episodes with published transcripts (0 = reset only)",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Clear dead Celery/Redis jobs and reset unfinished episodes onto the
    published-transcript sync path (no paid worker / no huge Whisper downloads).
    """
    try:
        return clear_and_requeue_for_published_path(db, process_limit=process_limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
