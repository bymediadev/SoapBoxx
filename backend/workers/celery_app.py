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

if settings.rss_sync_minutes > 0:
    celery_app.conf.beat_schedule = {
        "soapboxx-sync-rss-feeds": {
            "task": "soapboxx.sync_rss_feeds",
            "schedule": timedelta(minutes=max(5, settings.rss_sync_minutes)),
        }
    }
