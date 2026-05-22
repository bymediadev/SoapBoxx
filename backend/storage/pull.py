"""Read everything stored for an episode, show, or full library."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from backend.library.catalog import get_library_tree
from backend.library.db import LibraryDB


def _parse_metrics_raw(metrics_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metrics_row:
        return {}
    raw = metrics_row.get("raw_json")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def pull_episode(episode_id: int, *, db: Optional[LibraryDB] = None) -> Optional[Dict[str, Any]]:
    """
    Full pull: episode, transcript, source fields, metrics, tier, coach, podcast shelf.
    """
    database = db or LibraryDB()
    database.init_schema()
    bundle = database.get_episode_bundle(episode_id)
    if not bundle:
        return None

    ep = bundle["episode"]
    podcast = None
    pid = ep.get("podcast_id")
    if pid:
        with database.connect() as conn:
            row = conn.execute(
                "SELECT * FROM podcasts WHERE id = ?", (int(pid),)
            ).fetchone()
            if row:
                podcast = dict(row)

    metrics_row = bundle.get("metrics") or {}
    out: Dict[str, Any] = {
        "episode_id": episode_id,
        "episode": ep,
        "transcript": ep.get("transcript"),
        "source": {
            "type": ep.get("source_type"),
            "ref": ep.get("source_ref"),
            "path": ep.get("source_path"),
            "metadata": ep.get("metadata") or {},
        },
        "measurements": _parse_metrics_raw(metrics_row) or {
            k: metrics_row.get(k)
            for k in (
                "hook_time",
                "guest_talk_pct",
                "host_talk_pct",
                "question_count",
                "followup_count",
                "story_count",
                "interruptions",
                "topic_changes",
                "cta_present",
            )
            if metrics_row.get(k) is not None
        },
        "metrics_row": metrics_row,
        "prediction": bundle.get("prediction"),
        "coach_report": bundle.get("coach_report"),
        "podcast": podcast,
    }
    return out


def pull_podcast(podcast_id: int, *, db: Optional[LibraryDB] = None) -> Optional[Dict[str, Any]]:
    """All stored episodes and measurements for one show (source)."""
    database = db or LibraryDB()
    database.init_schema()
    with database.connect() as conn:
        pod = conn.execute(
            "SELECT * FROM podcasts WHERE id = ?", (podcast_id,)
        ).fetchone()
        if not pod:
            return None
        eps = conn.execute(
            "SELECT id FROM episodes WHERE podcast_id = ? ORDER BY created_at",
            (podcast_id,),
        ).fetchall()
    episodes: List[Dict[str, Any]] = []
    for row in eps:
        pulled = pull_episode(int(row["id"]), db=database)
        if pulled:
            episodes.append(pulled)
    return {"podcast": dict(pod), "episodes": episodes}


def export_library_snapshot(*, db: Optional[LibraryDB] = None) -> Dict[str, Any]:
    """Tree + benchmarks + episode count for export/API."""
    database = db or LibraryDB()
    database.init_schema()
    tree = get_library_tree(database)
    with database.connect() as conn:
        n_ep = conn.execute("SELECT COUNT(*) AS c FROM episodes").fetchone()["c"]
        n_met = conn.execute("SELECT COUNT(*) AS c FROM metrics").fetchone()["c"]
        n_coach = conn.execute(
            "SELECT COUNT(*) AS c FROM coach_reports"
        ).fetchone()["c"]
        benches = conn.execute(
            "SELECT category, metric_name, avg_value, sample_size FROM benchmarks"
        ).fetchall()
    return {
        "library_tree": tree,
        "counts": {
            "episodes": int(n_ep),
            "with_metrics": int(n_met),
            "with_coach": int(n_coach),
        },
        "benchmarks": [dict(r) for r in benches],
    }
