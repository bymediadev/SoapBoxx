# report_control_workflow/logging/error_log.py
"""Bounded error telemetry (side effects isolated here)."""

from __future__ import annotations

from collections import Counter, deque
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence

from report_control_workflow.constants import PIPELINE_ERROR_LOG_MAX

_PIPELINE_ERROR_LOG: Deque[Dict[str, Any]] = deque(maxlen=PIPELINE_ERROR_LOG_MAX)


def log_errors(
    errors: Sequence[str],
    stage: str,
    *,
    extra: Optional[Dict[str, Any]] = None,
    sink: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> None:
    for e in errors:
        row = {"stage": stage, "error": str(e), "extra": dict(extra or {})}
        _PIPELINE_ERROR_LOG.append(row)
        if sink is not None:
            sink(row)


def clear_pipeline_error_log() -> None:
    _PIPELINE_ERROR_LOG.clear()


def get_pipeline_error_log() -> List[Dict[str, Any]]:
    """Snapshot of the bounded in-memory error log (copy; safe for tests and inspection)."""
    return list(_PIPELINE_ERROR_LOG)


def summarize_errors(logs: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    rows = list(logs) if logs is not None else list(_PIPELINE_ERROR_LOG)
    if not rows:
        return {"most_common_error": None, "by_stage": {}, "error_counts": {}, "n": 0}
    err_counts: Counter = Counter(str(r.get("error")) for r in rows)
    stage_counts: Counter = Counter(str(r.get("stage")) for r in rows)
    most_common = err_counts.most_common(1)[0][0]
    return {
        "most_common_error": most_common,
        "error_counts": dict(err_counts),
        "by_stage": dict(stage_counts),
        "n": len(rows),
    }
