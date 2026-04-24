# report_control_workflow/logging/metrics.py
"""Score history for rolling calibration (side effects isolated here)."""

from __future__ import annotations

from collections import deque
from typing import Deque, List, Optional, Sequence

from report_control_workflow.constants import REPORT_SCORE_HISTORY_MAX

REPORT_SCORE_HISTORY: Deque[float] = deque(maxlen=REPORT_SCORE_HISTORY_MAX)


def store_report_score(score: float) -> None:
    REPORT_SCORE_HISTORY.append(float(score))


def percentile_rank(score: float, *, history: Optional[Sequence[float]] = None) -> Optional[float]:
    seq = list(history) if history is not None else list(REPORT_SCORE_HISTORY)
    if not seq:
        return None
    srt = sorted(seq)
    return sum(1 for x in srt if x <= score) / len(srt)


def normalize_score(score: float, history: Sequence[float]) -> float:
    seq = [float(x) for x in history]
    if not seq:
        return float(score)
    lo, hi = min(seq), max(seq)
    if hi <= lo:
        return float(score)
    return max(0.0, min(1.0, (float(score) - lo) / (hi - lo)))


def clear_report_score_history() -> None:
    REPORT_SCORE_HISTORY.clear()
