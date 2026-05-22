"""Library tables on the same SQLite DB as intelligence_v1."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.intelligence_v1.db import IntelligenceDB
from backend.intelligence_v1.config import default_db_path

_LIBRARY_SCHEMA = """
CREATE TABLE IF NOT EXISTS podcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL DEFAULT 'general',
    author TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    rss_url TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(category, author, title)
);

CREATE TABLE IF NOT EXISTS batch_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    summary_json TEXT
);

CREATE TABLE IF NOT EXISTS episode_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_id INTEGER,
    category TEXT NOT NULL DEFAULT 'general',
    show_title TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    episode_title TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    added_at TEXT NOT NULL,
    batch_id INTEGER,
    episode_id INTEGER,
    error_message TEXT,
    FOREIGN KEY (podcast_id) REFERENCES podcasts(id) ON DELETE SET NULL,
    FOREIGN KEY (batch_id) REFERENCES batch_runs(id) ON DELETE SET NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE SET NULL,
    UNIQUE(source_type, source_ref)
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _weekly_label(dt: Optional[datetime] = None) -> str:
    d = dt or datetime.now(timezone.utc)
    return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"


class LibraryDB(IntelligenceDB):
    """Intelligence DB + library / queue / batch tables."""

    def init_schema(self) -> None:
        super().init_schema()
        self.init_library_schema()

    def init_library_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_LIBRARY_SCHEMA)
            self._migrate_episodes(conn)
            self._migrate_episode_columns(conn)

    def _migrate_episodes(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
        adds = [
            ("podcast_id", "INTEGER"),
            ("author", "TEXT NOT NULL DEFAULT ''"),
            ("published_at", "TEXT"),
            ("processing_status", "TEXT NOT NULL DEFAULT 'processed'"),
            ("batch_id", "INTEGER"),
        ]
        for name, decl in adds:
            if name not in cols:
                conn.execute(f"ALTER TABLE episodes ADD COLUMN {name} {decl}")

    def upsert_podcast(
        self,
        *,
        category: str,
        author: str,
        title: str,
        rss_url: Optional[str] = None,
    ) -> int:
        from backend.intelligence_v1.categories import normalize_category

        cat = normalize_category(category)
        auth = (author or "Unknown").strip()
        show = (title or "Untitled show").strip()
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM podcasts
                WHERE category = ? AND author = ? AND title = ?
                """,
                (cat, auth, show),
            ).fetchone()
            if row:
                return int(row["id"])
            cur = conn.execute(
                """
                INSERT INTO podcasts (category, author, title, rss_url, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (cat, auth, show, rss_url, _utc_now()),
            )
            return int(cur.lastrowid)

    def insert_episode_library(
        self,
        *,
        podcast_id: int,
        title: str,
        category: str,
        transcript: str,
        author: str = "",
        source_path: Optional[str] = None,
        batch_id: Optional[int] = None,
        processing_status: str = "processed",
    ) -> int:
        now = _utc_now()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO episodes (
                    title, category, created_at, transcript, source_path,
                    podcast_id, author, processing_status, batch_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    category,
                    now,
                    transcript,
                    source_path,
                    podcast_id,
                    author,
                    processing_status,
                    batch_id,
                ),
            )
            return int(cur.lastrowid)

    def start_batch(self, label: Optional[str] = None) -> int:
        lbl = (label or _weekly_label()).strip()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO batch_runs (label, started_at, status)
                VALUES (?, ?, 'running')
                """,
                (lbl, _utc_now()),
            )
            return int(cur.lastrowid)

    def finish_batch(self, batch_id: int, summary: Dict[str, Any], *, status: str = "done") -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE batch_runs
                SET completed_at = ?, status = ?, summary_json = ?
                WHERE id = ?
                """,
                (_utc_now(), status, json.dumps(summary), batch_id),
            )
