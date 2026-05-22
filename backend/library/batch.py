"""Weekly batch: process queued episodes into the library (measurement-first)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .catalog import get_or_create_podcast
from .db import LibraryDB
from .queue import list_pending_queue


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _weekly_label() -> str:
    d = datetime.now(timezone.utc)
    return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"


def _ingest_queue_item(item: Dict[str, Any]) -> Dict[str, Any]:
    from backend.episode_ingest import (
        ingest_from_audio_file,
        ingest_from_text,
        ingest_from_transcript_file,
        ingest_from_youtube_url,
    )

    st = str(item["source_type"])
    ref = str(item["source_ref"])
    if st == "youtube":
        return ingest_from_youtube_url(ref).to_dict()
    if st == "transcript_file":
        return ingest_from_transcript_file(ref).to_dict()
    if st == "audio_file":
        return ingest_from_audio_file(ref).to_dict()
    if st == "paste":
        return ingest_from_text(ref).to_dict()
    raise ValueError(f"Unsupported queue source_type: {st}")


def _batch_coach_enabled() -> bool:
    return os.getenv("SOAPBOXX_BATCH_COACH", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def run_weekly_batch(
    *,
    label: Optional[str] = None,
    db: Optional[LibraryDB] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process all ``pending`` queue items: ingest → rule-based metrics → library shelf.

    Coach reports are **off** unless ``SOAPBOXX_BATCH_COACH=1``.
    """
    from backend.intelligence_v1.analyzer import compute_category_benchmarks
    from backend.intelligence_v1.categories import normalize_category, resolve_benchmarks
    from backend.intelligence_v1.metrics_extractor import extract_metrics
    from backend.intelligence_v1.pipeline import _tier_enabled
    from backend.intelligence_v1.predictor import predict_tier

    database = db or LibraryDB()
    database.init_schema()
    pending = list_pending_queue(database)
    if limit is not None:
        pending = pending[: max(0, int(limit))]

    batch_id = database.start_batch(label or _weekly_label())
    results: List[Dict[str, Any]] = []
    ok = fail = 0

    for item in pending:
        qid = int(item["id"])
        try:
            with database.connect() as conn:
                conn.execute(
                    "UPDATE episode_queue SET status = 'processing', batch_id = ? WHERE id = ?",
                    (batch_id, qid),
                )

            ingested = _ingest_queue_item(item)
            transcript = str(ingested.get("transcript") or "").strip()
            if len(transcript) < 40:
                raise ValueError("Transcript too short after ingest")

            category = normalize_category(
                item.get("category") or ingested.get("genre") or "general"
            )
            author = (
                (item.get("author") or "").strip()
                or ingested.get("creator")
                or "Unknown"
            )
            show_title = (item.get("show_title") or "").strip() or "Untitled show"
            ep_title = (
                (item.get("episode_title") or "").strip()
                or ingested.get("title")
                or "Episode"
            )

            podcast_id = int(item["podcast_id"]) if item.get("podcast_id") else None
            if not podcast_id:
                podcast_id = get_or_create_podcast(
                    category=category,
                    author=author,
                    show_title=show_title,
                    db=database,
                )

            metrics = extract_metrics(transcript)
            episode_id = database.insert_episode_library(
                podcast_id=podcast_id,
                title=ep_title,
                category=category,
                transcript=transcript,
                author=author,
                source_path=ingested.get("source_ref") or str(item["source_ref"]),
                batch_id=batch_id,
            )
            database.save_metrics(episode_id, metrics)
            database.update_episode_storage(
                episode_id,
                source_type=str(ingested.get("source_type") or item.get("source_type")),
                source_ref=str(ingested.get("source_ref") or item.get("source_ref")),
                source_path=str(
                    ingested.get("source_ref") or item.get("source_ref") or ""
                ),
                metadata={
                    "title": ep_title,
                    "creator": author,
                    "video_id": ingested.get("video_id"),
                    "warnings": ingested.get("warnings"),
                    "extra": ingested.get("extra"),
                    "batch_id": batch_id,
                    "queue_id": qid,
                },
            )

            computed, sample_size = compute_category_benchmarks(
                category, db=database, persist=True
            )
            benchmarks, _note = resolve_benchmarks(
                category, computed, sample_size=sample_size
            )
            if _tier_enabled():
                pred = predict_tier(metrics, benchmarks)
                database.save_prediction(
                    episode_id,
                    tier=str(pred["tier"]),
                    confidence=float(pred["confidence"]),
                    reasoning=list(pred.get("reasoning") or []),
                )

            coach_id = None
            if _batch_coach_enabled():
                try:
                    from backend.feedback_engine import FeedbackEngine

                    fe = FeedbackEngine()
                    if hasattr(fe, "generate_episode_coach_report"):
                        fe.generate_episode_coach_report(
                            transcript, title=ep_title, creator=author
                        )
                        coach_id = episode_id
                except Exception:
                    pass

            with database.connect() as conn:
                conn.execute(
                    """
                    UPDATE episode_queue
                    SET status = 'done', episode_id = ?, error_message = NULL
                    WHERE id = ?
                    """,
                    (episode_id, qid),
                )

            ok += 1
            results.append(
                {
                    "queue_id": qid,
                    "episode_id": episode_id,
                    "podcast_id": podcast_id,
                    "status": "done",
                    "title": ep_title,
                }
            )
        except Exception as exc:
            fail += 1
            with database.connect() as conn:
                conn.execute(
                    """
                    UPDATE episode_queue SET status = 'failed', error_message = ?
                    WHERE id = ?
                    """,
                    (str(exc)[:500], qid),
                )
            results.append(
                {"queue_id": qid, "status": "failed", "error": str(exc)}
            )

    summary = {
        "batch_id": batch_id,
        "label": label or _weekly_label(),
        "processed": ok,
        "failed": fail,
        "total": len(pending),
        "results": results,
    }
    database.finish_batch(batch_id, summary, status="done" if fail == 0 else "partial")
    from .catalog import get_library_tree

    summary["library_tree"] = get_library_tree(database)
    return summary
