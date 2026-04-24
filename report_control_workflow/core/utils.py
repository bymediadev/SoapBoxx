# report_control_workflow/core/utils.py
"""Text similarity and density helpers (pure)."""

from __future__ import annotations

import re
from typing import List

from report_control_workflow.core.models import ControlReport

_STOP = frozenset(
    "the a an to of and or for in on at by as is it if we you they he she "
    "was were are be been being this that these those with from than then "
    "into over out up down about".split()
)


def text_similarity(a: str, b: str) -> float:
    try:
        from backend.episode_report_v3 import text_similarity as _ts
    except ImportError:  # pragma: no cover
        from episode_report_v3 import text_similarity as _ts  # type: ignore

    return float(_ts(a, b))


def content_tokens(s: str) -> set:
    return {w for w in re.findall(r"[a-z0-9']{4,}", (s or "").lower()) if w not in _STOP}


def token_overlap_ratio(a: str, b: str) -> float:
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    return inter / max(len(ta), len(tb))


def report_token_density(report: ControlReport) -> float:
    parts: List[str] = []
    if report.thesis:
        parts.append(report.thesis)
    for c in report.claims:
        parts.append(c.text)
        if c.evidence:
            parts.append(c.evidence)
    blob = " ".join(parts).lower()
    toks = [t for t in re.findall(r"[a-z0-9']{3,}", blob) if t not in _STOP]
    if not toks:
        return 1.0
    return len(set(toks)) / len(toks)
