# backend/thesis_validator_v2.py
"""
Hard thesis structure gate — **no keyword fallback**.

Rejects title-like three-token theses (e.g. ``China; Israel; US Foreign Policy``) and
demands minimum length plus actor + mechanism + outcome cues (heuristic, no LLM).
"""

from __future__ import annotations

import re
from typing import Optional

from backend.thesis_engine_v2 import _ENTITY_HINT, _MECH_LEX

MIN_THESIS_WORDS = 12
_MAX_SEMICOLON_FRAGMENT_WORDS = 5


_OUTCOME_CUES = re.compile(
    r"(?i)\b("
    r"because|therefore|through|resulting|leads? to|drives?|shapes?|influenc\w*|"
    r"connects?|suggest\w*|align\w*|perception|policy|channels?|narrative|"
    r"repeated|independent|segments|based\s+on"
    r")\b",
)


def _is_keyword_list_thesis(t: str) -> bool:
    """Semicolon-separated short fragments (vapor thesis pattern)."""
    s = (t or "").strip()
    if ";" not in s:
        return False
    parts = [p.strip() for p in s.split(";") if p.strip()]
    if len(parts) < 2:
        return False
    return all(len(p.split()) <= _MAX_SEMICOLON_FRAGMENT_WORDS for p in parts)


def is_valid_thesis(t: Optional[str]) -> bool:
    return thesis_validation_failure_reason(t) is None


def thesis_validation_failure_reason(t: Optional[str]) -> Optional[str]:
    if not t or not str(t).strip():
        return "THESIS_EMPTY"
    s = str(t).strip()
    if _is_keyword_list_thesis(s):
        return "THESIS_KEYWORD_LIST"
    wc = len(s.split())
    if wc < MIN_THESIS_WORDS:
        return "THESIS_TOO_SHORT"
    if not _ENTITY_HINT.search(s):
        return "THESIS_MISSING_ACTOR"
    if not _MECH_LEX.search(s) and not re.search(
        r"(?i)\b(suggest\w*|indicates?|demonstrates?|shows?|means?|implies?|operates?|"
        r"coordinates?|coordinates|shifts?|affects?)\b",
        s,
    ):
        return "THESIS_MISSING_MECHANISM"
    if not _OUTCOME_CUES.search(s):
        return "THESIS_MISSING_OUTCOME_OR_LINK"
    return None


__all__ = [
    "MIN_THESIS_WORDS",
    "is_valid_thesis",
    "thesis_validation_failure_reason",
]
