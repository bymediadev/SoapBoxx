# report_control_workflow/intelligence/clips.py
"""Clip ranking and diversity (pure)."""

from __future__ import annotations

import re
from typing import List, Sequence

from report_control_workflow.core.models import ClaimRow
from report_control_workflow.core.utils import text_similarity
from report_control_workflow.constants import (
    DEFAULT_CLIP_DIVERSITY_THRESHOLD,
    DEFAULT_CLIP_SELECT_K,
    _CLIP_STRONG,
)


def score_clip_potential(text: str) -> float:
    s = (text or "").strip()
    words = s.split()
    length = len(words)
    if length == 0:
        return 0.0
    sc = 0.48
    if length > 25:
        sc -= 0.22
    elif length < 18:
        sc += 0.14
    if _CLIP_STRONG.search(s):
        sc += 0.16
    if s.strip().endswith("?"):
        sc += 0.08
    if re.search(r"\b(?:framework|paradigm|institution|policy|mechanism)\b", s, re.I):
        sc += 0.05
    if length > 32 or re.search(r"\b(?:whereas|notwithstanding|furthermore)\b", s, re.I):
        sc -= 0.08
    return max(0.0, min(1.0, float(sc)))


def select_top_clips(
    claims: Sequence[ClaimRow],
    *,
    k: int = DEFAULT_CLIP_SELECT_K,
    diversity_threshold: float = DEFAULT_CLIP_DIVERSITY_THRESHOLD,
) -> List[str]:
    rows = [c for c in claims if (c.text or "").strip()]
    ranked = sorted(rows, key=lambda c: score_clip_potential(c.text), reverse=True)
    out: List[str] = []
    for c in ranked:
        t = c.text.strip()
        if t in out:
            continue
        if any(text_similarity(t, o) > diversity_threshold for o in out):
            continue
        out.append(t)
        if len(out) >= k:
            break
    return out


def validate_clip_diversity(
    clips: Sequence[str],
    *,
    threshold: float = DEFAULT_CLIP_DIVERSITY_THRESHOLD,
) -> bool:
    cl = [str(x).strip() for x in clips if str(x).strip()]
    for i in range(len(cl)):
        for j in range(i + 1, len(cl)):
            if text_similarity(cl[i], cl[j]) > threshold:
                return False
    return True
