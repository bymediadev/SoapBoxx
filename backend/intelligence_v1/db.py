"""SQLite persistence for Phase 1 intelligence loop."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .config import default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL,
    transcript TEXT NOT NULL,
    source_path TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    episode_id INTEGER PRIMARY KEY,
    hook_time REAL NOT NULL DEFAULT 0,
    guest_talk_pct REAL NOT NULL DEFAULT 0,
    host_talk_pct REAL NOT NULL DEFAULT 0,
    question_count INTEGER NOT NULL DEFAULT 0,
    followup_count INTEGER NOT NULL DEFAULT 0,
    story_count INTEGER NOT NULL DEFAULT 0,
    interruptions INTEGER NOT NULL DEFAULT 0,
    topic_changes INTEGER NOT NULL DEFAULT 0,
    cta_present INTEGER NOT NULL DEFAULT 0,
    raw_json TEXT,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS predictions (
    episode_id INTEGER PRIMARY KEY,
    predicted_tier TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0,
    reasoning TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS benchmarks (
    category TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    avg_value REAL NOT NULL DEFAULT 0,
    p90_value REAL NOT NULL DEFAULT 0,
    p10_value REAL NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (category, metric_name)
);

CREATE TABLE IF NOT EXISTS coach_reports (
    episode_id INTEGER PRIMARY KEY,
    markdown TEXT NOT NULL DEFAULT '',
    report_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE
);
"""

_EPISODE_COLUMN_MIGRATIONS = (
    ("source_type", "TEXT"),
    ("source_ref", "TEXT"),
    ("metadata_json", "TEXT"),
)


class IntelligenceDB:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path or default_db_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)
            self._migrate_episode_columns(conn)

    def _migrate_episode_columns(self, conn: sqlite3.Connection) -> None:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
        for name, decl in _EPISODE_COLUMN_MIGRATIONS:
            if name not in cols:
                conn.execute(f"ALTER TABLE episodes ADD COLUMN {name} {decl}")

    def update_episode_storage(
        self,
        episode_id: int,
        *,
        source_type: Optional[str] = None,
        source_ref: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        source_path: Optional[str] = None,
    ) -> None:
        """Attach source-layer fields for re-fetch and export."""
        sets: List[str] = []
        vals: List[Any] = []
        if source_type is not None:
            sets.append("source_type = ?")
            vals.append(source_type)
        if source_ref is not None:
            sets.append("source_ref = ?")
            vals.append(source_ref)
        if source_path is not None:
            sets.append("source_path = ?")
            vals.append(source_path)
        if metadata is not None:
            sets.append("metadata_json = ?")
            vals.append(json.dumps(metadata))
        if not sets:
            return
        vals.append(episode_id)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE episodes SET {', '.join(sets)} WHERE id = ?",
                vals,
            )

    def save_coach_report(
        self,
        episode_id: int,
        *,
        markdown: str,
        report: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO coach_reports (episode_id, markdown, report_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    episode_id,
                    markdown,
                    json.dumps(report) if report else None,
                    now,
                ),
            )

    def get_coach_report(self, episode_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM coach_reports WHERE episode_id = ?",
                (episode_id,),
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        if out.get("report_json"):
            try:
                out["report"] = json.loads(out["report_json"])
            except json.JSONDecodeError:
                out["report"] = {}
        return out

    def insert_episode(
        self,
        *,
        title: str,
        category: str,
        transcript: str,
        source_path: Optional[str] = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO episodes (title, category, created_at, transcript, source_path)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, category, now, transcript, source_path),
            )
            return int(cur.lastrowid)

    def save_metrics(self, episode_id: int, metrics: Dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO metrics (
                    episode_id, hook_time, guest_talk_pct, host_talk_pct,
                    question_count, followup_count, story_count,
                    interruptions, topic_changes, cta_present, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    episode_id,
                    float(metrics.get("hook_time_seconds", 0)),
                    float(metrics.get("guest_talk_percentage", 0)),
                    float(metrics.get("host_talk_percentage", 0)),
                    int(metrics.get("question_count", 0)),
                    int(metrics.get("followup_question_count", 0)),
                    int(metrics.get("story_count", 0)),
                    int(metrics.get("interruptions", 0)),
                    int(metrics.get("topic_changes", 0)),
                    1 if metrics.get("cta_present") else 0,
                    json.dumps(metrics),
                ),
            )

    def save_prediction(
        self,
        episode_id: int,
        *,
        tier: str,
        confidence: float,
        reasoning: List[str],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO predictions (episode_id, predicted_tier, confidence, reasoning)
                VALUES (?, ?, ?, ?)
                """,
                (episode_id, tier, confidence, json.dumps(reasoning)),
            )

    def upsert_benchmarks(
        self, category: str, stats: Dict[str, Dict[str, float]], sample_size: int
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            for metric_name, vals in stats.items():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO benchmarks
                    (category, metric_name, avg_value, p90_value, p10_value, sample_size, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        category,
                        metric_name,
                        float(vals.get("avg", 0)),
                        float(vals.get("p90", 0)),
                        float(vals.get("p10", 0)),
                        sample_size,
                        now,
                    ),
                )

    def list_episodes_in_category(self, category: str) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.id, e.title, e.category, e.created_at,
                       m.hook_time, m.guest_talk_pct, m.host_talk_pct,
                       m.question_count, m.followup_count, m.story_count,
                       m.interruptions, m.topic_changes, m.cta_present
                FROM episodes e
                JOIN metrics m ON m.episode_id = e.id
                WHERE e.category = ?
                ORDER BY e.created_at
                """,
                (category,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stored_benchmarks(self, category: str) -> Dict[str, Dict[str, float]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT metric_name, avg_value, p90_value, p10_value FROM benchmarks WHERE category = ?",
                (category,),
            ).fetchall()
        out: Dict[str, Dict[str, float]] = {}
        for r in rows:
            out[str(r["metric_name"])] = {
                "avg": float(r["avg_value"]),
                "p90": float(r["p90_value"]),
                "p10": float(r["p10_value"]),
            }
        return out

    def get_episode_bundle(self, episode_id: int) -> Optional[Dict[str, Any]]:
        with self.connect() as conn:
            ep = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
            if not ep:
                return None
            met = conn.execute(
                "SELECT * FROM metrics WHERE episode_id = ?", (episode_id,)
            ).fetchone()
            pred = conn.execute(
                "SELECT * FROM predictions WHERE episode_id = ?", (episode_id,)
            ).fetchone()
        ep_d = dict(ep)
        if ep_d.get("metadata_json"):
            try:
                ep_d["metadata"] = json.loads(ep_d["metadata_json"])
            except json.JSONDecodeError:
                ep_d["metadata"] = {}
        bundle = {"episode": ep_d, "metrics": dict(met) if met else None}
        coach = self.get_coach_report(episode_id)
        if coach:
            bundle["coach_report"] = coach
        if pred:
            p = dict(pred)
            try:
                p["reasoning"] = json.loads(p.get("reasoning") or "[]")
            except json.JSONDecodeError:
                p["reasoning"] = []
            bundle["prediction"] = p
        return bundle
