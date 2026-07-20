"""Pipeline status — living system counts."""

from __future__ import annotations

import logging
import os
import threading
import time
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
    celery_worker_available,
    clear_and_requeue_for_published_path,
    drain_pending_pipeline,
    process_queued_episodes,
)
from backend.services.system_state_service import get_pipeline_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

_sync_drain_lock = threading.Lock()
_sync_drain_started = False


def _run_sync_drain(trigger: str, limit: int) -> dict[str, Any] | None:
    """Process a small published-transcript batch on this API (no Celery worker)."""
    if not _sync_drain_lock.acquire(blocking=False):
        logger.info("Sync drain skipped (already running)")
        return None
    db = get_session_factory()()
    try:
        out = process_queued_episodes(db, limit=max(1, limit))
        logger.info(
            "Sync drain (%s): succeeded=%s failed=%s attempted=%s skipped_no_pub=%s",
            trigger,
            out.get("succeeded"),
            out.get("failed"),
            out.get("attempted"),
            out.get("skipped_no_published_transcript"),
        )
        return out
    except Exception:
        logger.exception("Sync drain failed (%s)", trigger)
        return None
    finally:
        db.close()
        _sync_drain_lock.release()


def _kick_backlog_on_boot() -> None:
    """Drain pending episodes after deploy (Celery if worker live, else sync)."""
    settings = get_settings()
    limit = settings.pipeline_boot_dispatch_limit
    if limit <= 0:
        return

    def _run() -> None:
        try:
            if celery_worker_available():
                db = get_session_factory()()
                try:
                    out = drain_pending_pipeline(
                        db,
                        limit=limit,
                        trigger="api_boot",
                        prefer_celery=True,
                    )
                    logger.info("Boot backlog dispatch: %s", out)
                finally:
                    db.close()
            else:
                # Free path: published transcripts, small batch so boot stays healthy.
                _run_sync_drain("api_boot", min(limit, settings.pipeline_batch_size or 2))
        except Exception:
            logger.exception("Boot backlog dispatch failed")

    threading.Thread(target=_run, name="pipeline-boot-dispatch", daemon=True).start()


def _start_sync_drain_loop() -> None:
    """While no Celery worker is up, periodically drain the queue on this web process."""
    global _sync_drain_started
    settings = get_settings()
    minutes = int(settings.pipeline_drain_minutes or 0)
    if minutes <= 0:
        return
    if _sync_drain_started:
        return
    _sync_drain_started = True
    batch = max(1, int(settings.pipeline_batch_size or 1))
    interval = max(60, minutes * 60)

    def _loop() -> None:
        # Let boot / health settle first.
        time.sleep(45)
        while True:
            try:
                if celery_worker_available(timeout=0.5):
                    logger.debug("Sync drain idle — Celery worker is online")
                else:
                    _run_sync_drain("api_tick", batch)
            except Exception:
                logger.exception("Sync drain tick crashed")
            time.sleep(interval)

    threading.Thread(target=_loop, name="pipeline-sync-drain", daemon=True).start()
    logger.info(
        "Started in-API sync drain every %ss (batch=%s) when no Celery worker",
        interval,
        batch,
    )


def register_pipeline_startup() -> None:
    """Call from app factory — boot drain + periodic sync drain when no worker."""
    settings = get_settings()
    _start_sync_drain_loop()
    if settings.pipeline_boot_dispatch_limit <= 0:
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
