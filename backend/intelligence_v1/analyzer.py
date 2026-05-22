"""Category benchmarks: avg, p90, p10 from stored metrics."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .db import IntelligenceDB

# DB column → benchmark metric_name
_METRIC_MAP = {
    "hook_time": "hook_time_seconds",
    "guest_talk_pct": "guest_talk_percentage",
    "host_talk_pct": "host_talk_percentage",
    "question_count": "question_count",
    "followup_count": "followup_question_count",
    "story_count": "story_count",
    "interruptions": "interruptions",
    "topic_changes": "topic_changes",
}


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def compute_category_benchmarks(
    category: str,
    *,
    db: IntelligenceDB | None = None,
    persist: bool = True,
) -> Tuple[Dict[str, Dict[str, float]], int]:
    """
    Compute benchmarks from all episodes in ``category`` that have metrics.

    Returns ``({metric_name: {avg, p90, p10}}, sample_size)``.
    """
    database = db or IntelligenceDB()
    database.init_schema()
    rows = database.list_episodes_in_category(category)
    stats: Dict[str, Dict[str, float]] = {}

    for col, name in _METRIC_MAP.items():
        vals = [float(r[col]) for r in rows if r.get(col) is not None]
        if not vals:
            stats[name] = {"avg": 0.0, "p90": 0.0, "p10": 0.0}
            continue
        stats[name] = {
            "avg": round(sum(vals) / len(vals), 2),
            "p90": round(_percentile(vals, 90), 2),
            "p10": round(_percentile(vals, 10), 2),
        }

    if persist and rows:
        database.upsert_benchmarks(category, stats, len(rows))

    return stats, len(rows)


def metrics_row_to_api(metrics_db_row: Dict[str, Any]) -> Dict[str, Any]:
    """Map SQLite metrics row to extractor JSON shape."""
    if not metrics_db_row:
        return {}
    return {
        "hook_time_seconds": float(metrics_db_row.get("hook_time", 0)),
        "guest_talk_percentage": float(metrics_db_row.get("guest_talk_pct", 0)),
        "host_talk_percentage": float(metrics_db_row.get("host_talk_pct", 0)),
        "question_count": int(metrics_db_row.get("question_count", 0)),
        "followup_question_count": int(metrics_db_row.get("followup_count", 0)),
        "story_count": int(metrics_db_row.get("story_count", 0)),
        "interruptions": int(metrics_db_row.get("interruptions", 0)),
        "topic_changes": int(metrics_db_row.get("topic_changes", 0)),
        "cta_present": bool(metrics_db_row.get("cta_present")),
    }
