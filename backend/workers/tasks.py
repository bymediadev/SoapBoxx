"""Celery tasks — Day 4+."""

from __future__ import annotations

from backend.workers.celery_app import celery_app


@celery_app.task(name="soapboxx.transcribe_episode")
def transcribe_episode_task(episode_id: int) -> dict:
    from backend.api.deps import get_session_factory
    from backend.services.transcription_service import transcribe_episode

    db = get_session_factory()()
    try:
        result = transcribe_episode(db, episode_id)
        return {
            "episode_id": result.episode_id,
            "transcript_length": result.transcript_length,
            "segment_count": result.segment_count,
        }
    finally:
        db.close()


@celery_app.task(name="soapboxx.process_episode")
def process_episode_task(episode_id: int) -> dict:
    from backend.api.deps import get_session_factory
    from backend.services.episode_pipeline_service import run_episode_pipeline

    db = get_session_factory()()
    try:
        result = run_episode_pipeline(db, episode_id)
        return result.to_dict()
    finally:
        db.close()
