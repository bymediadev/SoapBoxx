"""Queue episodes for weekly batch processing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import LibraryDB


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue_episode(
    *,
    source_type: str,
    source_ref: str,
    category: str = "general",
    show_title: str = "",
    author: str = "",
    episode_title: str = "",
    podcast_id: Optional[int] = None,
    db: Optional[LibraryDB] = None,
) -> Dict[str, Any]:
    """
    Add one episode to the batch queue (skips duplicate source_type + source_ref).
    """
    from backend.intelligence_v1.categories import normalize_category

    database = db or LibraryDB()
    database.init_schema()
    st = (source_type or "paste").strip().lower()
    ref = (source_ref or "").strip()
    if not ref:
        raise ValueError("source_ref is required")

    with database.connect() as conn:
        existing = conn.execute(
            "SELECT id, status FROM episode_queue WHERE source_type = ? AND source_ref = ?",
            (st, ref),
        ).fetchone()
        if existing:
            return {
                "queue_id": int(existing["id"]),
                "status": existing["status"],
                "duplicate": True,
            }
        cur = conn.execute(
            """
            INSERT INTO episode_queue (
                podcast_id, category, show_title, author, episode_title,
                source_type, source_ref, status, added_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                podcast_id,
                normalize_category(category),
                (show_title or "Untitled show").strip(),
                (author or "").strip(),
                (episode_title or "").strip(),
                st,
                ref,
                _utc_now(),
            ),
        )
        return {"queue_id": int(cur.lastrowid), "status": "pending", "duplicate": False}


def list_pending_queue(db: Optional[LibraryDB] = None) -> List[Dict[str, Any]]:
    database = db or LibraryDB()
    database.init_schema()
    with database.connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM episode_queue
            WHERE status = 'pending'
            ORDER BY added_at
            """
        ).fetchall()
    return [dict(r) for r in rows]
