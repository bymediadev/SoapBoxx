"""Run full V1 episode pipeline: transcribe → features → translate."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures, EpisodeTranslation, TranscriptSegment
from backend.services.feature_service import run_feature_extraction
from backend.services.transcription_service import transcribe_episode
from backend.services.translation_service import run_translation
from backend.services.pipeline_status import STATUS_FAILED


@dataclass
class EpisodePipelineResult:
    episode_id: int
    status: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    transcript_length: int = 0
    segment_count: int = 0
    template_id: Optional[str] = None
    insight_preview: Optional[str] = None
    transcript_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "status": self.status,
            "steps": self.steps,
            "transcript_length": self.transcript_length,
            "segment_count": self.segment_count,
            "template_id": self.template_id,
            "insight_preview": self.insight_preview,
            "transcript_source": self.transcript_source,
        }


def _transcript_segment_count(db: Session, episode_id: int) -> int:
    return (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.episode_id == episode_id)
        .count()
    )


def episode_needs_stt(
    episode: Episode,
    *,
    transcript: Optional[str] = None,
    force_retranscribe: bool = False,
) -> bool:
    """True when pipeline would call STT (slow on long audio / Railway proxy timeout)."""
    if transcript is not None:
        return False
    if force_retranscribe:
        return True
    return not bool((episode.full_transcript or "").strip())


# Worker liveness is checked at most once per TTL — a broadcast ping costs
# up to `timeout` seconds and the answer rarely changes between requests.
_WORKER_PING_TTL_SECONDS = 30.0
_worker_ping_cache: Optional[tuple[float, bool]] = None
_worker_ping_lock = threading.Lock()


def celery_worker_available(*, timeout: float = 1.0) -> bool:
    """
    True only when at least one Celery worker answers a ping.

    ``task.delay()`` succeeds with zero workers (it just publishes to Redis),
    which leaves episodes stuck on "queued" forever when no worker process
    runs (e.g. Railway API service without a worker service).
    """
    global _worker_ping_cache
    now = time.monotonic()
    with _worker_ping_lock:
        if _worker_ping_cache and now - _worker_ping_cache[0] < _WORKER_PING_TTL_SECONDS:
            return _worker_ping_cache[1]
    try:
        from backend.workers.celery_app import celery_app

        ok = bool(celery_app.control.ping(timeout=timeout))
    except Exception:
        ok = False
    with _worker_ping_lock:
        _worker_ping_cache = (now, ok)
    return ok


def try_dispatch_episode_to_celery(
    db: Session,
    episode_id: int,
    *,
    trigger: str,
) -> bool:
    """Queue one episode on Celery when Redis + a live worker are available."""
    if not celery_worker_available():
        return False

    from backend.services.rss_service import dispatch_processing_for_episodes

    dispatched = dispatch_processing_for_episodes(db, [episode_id], trigger=trigger)
    return episode_id in dispatched


def _log_pipeline_step(
    episode_id: int,
    step: str,
    *,
    duration_ms: float,
    skipped: bool = False,
) -> None:
    skip_tag = " skipped" if skipped else ""
    print(
        f"pipeline episode_id={episode_id} step={step}{skip_tag} duration_ms={duration_ms:.0f}",
        flush=True,
    )


def run_episode_pipeline(
    db: Session,
    episode_id: int,
    *,
    transcript: Optional[str] = None,
    force_retranscribe: bool = False,
) -> EpisodePipelineResult:
    """
    Run follow-up for one episode: STT (or pasted transcript) → 7 metrics → template insight.

    Skips transcription when a transcript already exists unless ``force_retranscribe`` or
    ``transcript`` is provided. Always runs feature extraction and translation when possible.
    """
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")

    steps: List[Dict[str, Any]] = []
    has_transcript = bool((episode.full_transcript or "").strip())
    transcript_source: Optional[str] = None

    t0 = time.perf_counter()
    if transcript is not None or force_retranscribe or not has_transcript:
        if transcript is not None:
            transcribe_reason = "pasted_transcript"
            transcript_source = "pasted"
        elif force_retranscribe:
            transcribe_reason = "force_retranscribe"
            transcript_source = "stt"
        else:
            transcribe_reason = "no_transcript"
            transcript_source = "stt"

        tr = transcribe_episode(db, episode_id, transcript=transcript)
        _log_pipeline_step(episode_id, "transcribe", duration_ms=(time.perf_counter() - t0) * 1000)
        steps.append(
            {
                "step": "transcribe",
                "ok": True,
                "reason": transcribe_reason,
                "reused": False,
                "transcript_length": tr.transcript_length,
                "segment_count": tr.segment_count,
            }
        )
        transcript_length = tr.transcript_length
        segment_count = tr.segment_count
    else:
        transcript_length = len((episode.full_transcript or "").strip())
        segment_count = _transcript_segment_count(db, episode_id)
        transcript_source = "existing"
        _log_pipeline_step(
            episode_id,
            "transcribe",
            duration_ms=(time.perf_counter() - t0) * 1000,
            skipped=True,
        )
        steps.append(
            {
                "step": "transcribe",
                "ok": True,
                "skipped": True,
                "reason": "existing_transcript",
                "reused": True,
                "transcript_length": transcript_length,
                "segment_count": segment_count,
            }
        )

    db.refresh(episode)
    t0 = time.perf_counter()
    feat = run_feature_extraction(db, episode_id)
    _log_pipeline_step(episode_id, "features", duration_ms=(time.perf_counter() - t0) * 1000)
    steps.append(
        {
            "step": "features",
            "ok": True,
            "recomputed": True,
            "metrics": feat.features,
        }
    )

    t0 = time.perf_counter()
    trans = run_translation(db, episode_id)
    _log_pipeline_step(episode_id, "translate", duration_ms=(time.perf_counter() - t0) * 1000)
    preview = trans.insight_text[:240] + ("…" if len(trans.insight_text) > 240 else "")
    steps.append(
        {
            "step": "translate",
            "ok": True,
            "recomputed": True,
            "template_id": trans.template_id,
        }
    )

    audio_step = _schedule_audio_motion_if_enabled(episode_id)
    if audio_step is not None:
        steps.append({"step": "audio_motion", **audio_step})

    db.refresh(episode)
    final = "ready" if db.get(EpisodeTranslation, episode_id) else "measured"

    return EpisodePipelineResult(
        episode_id=episode_id,
        status=final,
        steps=steps,
        transcript_length=transcript_length,
        segment_count=segment_count,
        template_id=trans.template_id,
        insight_preview=preview,
        transcript_source=transcript_source,
    )


def _schedule_audio_motion_if_enabled(episode_id: int) -> Optional[dict]:
    """Optional Layer 2 — runs in a background thread so HTTP /process returns quickly."""
    from backend.api.config import get_settings

    if not get_settings().auto_audio_motion_on_process:
        return None

    def _run() -> None:
        from backend.api.deps import get_session_factory

        db = get_session_factory()()
        try:
            episode = db.get(Episode, episode_id)
            if episode:
                _maybe_run_audio_motion(db, episode_id, episode)
        finally:
            db.close()

    threading.Thread(
        target=_run,
        name=f"audio-motion-{episode_id}",
        daemon=True,
    ).start()
    return {"ok": True, "skipped": False, "scheduled": True, "reason": "background"}


def _maybe_run_audio_motion(db: Session, episode_id: int, episode: Episode) -> Optional[dict]:
    """Optional Layer 2 — parallel to transcript pipeline; failures do not abort."""
    from backend.models import EpisodeAudioMotion

    if not (episode.audio_url or "").strip():
        return {"ok": True, "skipped": True, "reason": "no_audio_url"}
    if db.get(EpisodeAudioMotion, episode_id):
        return {"ok": True, "skipped": True, "reason": "existing"}

    t0 = time.perf_counter()
    try:
        from backend.services.audio_motion_service import run_audio_motion_extraction

        run_audio_motion_extraction(db, episode_id)
        _log_pipeline_step(
            episode_id, "audio_motion", duration_ms=(time.perf_counter() - t0) * 1000
        )
        return {"ok": True, "skipped": False}
    except Exception as exc:
        _log_pipeline_step(
            episode_id, "audio_motion", duration_ms=(time.perf_counter() - t0) * 1000
        )
        return {"ok": False, "skipped": False, "error": str(exc)}


def find_pending_episode_ids(db: Session, *, limit: int = 10) -> List[int]:
    """Episodes ingested but not yet fully processed (no translation)."""
    cap = max(1, min(limit, 25))
    rows = (
        db.query(Episode.id)
        .outerjoin(EpisodeTranslation, EpisodeTranslation.episode_id == Episode.id)
        .filter(EpisodeTranslation.episode_id.is_(None))
        .filter(Episode.pipeline_status != STATUS_FAILED)
        .order_by(Episode.id.asc())
        .limit(cap)
        .all()
    )
    return [int(row[0]) for row in rows]


def drain_pending_pipeline(
    db: Session,
    *,
    limit: int,
    trigger: str,
    prefer_celery: bool = True,
    exclude_episode_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Queue or run pipeline for backlog episodes (e.g. Planet Money already in DB).

    Uses Celery when Redis + worker are available; otherwise processes synchronously
    (cron / local without worker).
    """
    exclude = set(exclude_episode_ids or [])
    pending_ids = [eid for eid in find_pending_episode_ids(db, limit=limit) if eid not in exclude]
    if not pending_ids:
        return {"pending": 0, "dispatched": 0, "processed": 0, "mode": "none"}

    if prefer_celery:
        from backend.services.rss_service import dispatch_processing_for_episodes

        dispatched = dispatch_processing_for_episodes(db, pending_ids, trigger=trigger)
        if dispatched:
            return {
                "pending": len(pending_ids),
                "dispatched": len(dispatched),
                "processed": 0,
                "mode": "celery",
                "episode_ids": dispatched,
            }

    results: List[Dict[str, Any]] = []
    for eid in pending_ids:
        try:
            out = run_episode_pipeline(db, eid)
            results.append({"episode_id": eid, "ok": True, "status": out.status})
        except Exception as exc:
            results.append({"episode_id": eid, "ok": False, "error": str(exc)})

    processed = sum(1 for r in results if r.get("ok"))
    return {
        "pending": len(pending_ids),
        "dispatched": 0,
        "processed": processed,
        "mode": "sync",
        "results": results,
    }


def process_queued_episodes(
    db: Session,
    *,
    limit: int = 1,
) -> Dict[str, Any]:
    """Process up to ``limit`` episodes that do not yet have a translation."""
    pending = (
        db.query(Episode)
        .outerjoin(EpisodeTranslation, EpisodeTranslation.episode_id == Episode.id)
        .filter(EpisodeTranslation.episode_id.is_(None))
        .order_by(Episode.id.asc())
        .limit(max(1, min(limit, 25)))
        .all()
    )

    results: List[Dict[str, Any]] = []
    for ep in pending:
        try:
            out = run_episode_pipeline(db, int(ep.id))
            results.append({"episode_id": int(ep.id), "ok": True, **out.to_dict()})
        except Exception as exc:
            results.append(
                {
                    "episode_id": int(ep.id),
                    "ok": False,
                    "error": str(exc),
                    "title": ep.title,
                }
            )

    ok_count = sum(1 for r in results if r.get("ok"))
    return {
        "requested": limit,
        "attempted": len(pending),
        "succeeded": ok_count,
        "failed": len(pending) - ok_count,
        "results": results,
    }
