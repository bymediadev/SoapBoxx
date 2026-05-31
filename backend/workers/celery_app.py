"""Celery app stub (Day 1 — Redis broker configured, tasks on Day 4)."""

from __future__ import annotations

from datetime import timedelta

from celery import Celery

from backend.api.config import get_settings

settings = get_settings()

celery_app = Celery(
    "soapboxx_v1",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    imports=("backend.workers.tasks",),
)

_beat_schedule: dict = {}

if settings.rss_sync_minutes > 0:
    _beat_schedule["soapboxx-sync-rss-feeds"] = {
        "task": "soapboxx.sync_rss_feeds",
        "schedule": timedelta(minutes=max(5, settings.rss_sync_minutes)),
    }

if settings.pipeline_drain_minutes > 0:
    _beat_schedule["soapboxx-process-pending-queue"] = {
        "task": "soapboxx.process_pending_queue",
        "schedule": timedelta(minutes=max(1, settings.pipeline_drain_minutes)),
    }

if _beat_schedule:
    celery_app.conf.beat_schedule = _beat_schedule
