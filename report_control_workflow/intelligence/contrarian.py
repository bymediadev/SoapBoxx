# report_control_workflow/intelligence/contrarian.py
"""Hard and soft thesis tension detection (pure)."""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from report_control_workflow.core.models import ClaimRow
from report_control_workflow.intelligence.relationships import classify_relationship_hybrid
from report_control_workflow.constants import _SOFT_TENSION_RE


def has_contrarian_claim(
    claims: Sequence[ClaimRow],
    thesis: str,
    relationship_fn: Callable[[str, str], str],
) -> bool:
    th = (thesis or "").strip()
    if not th:
        return True
    for c in claims:
        tx = (c.text or "").strip()
        if not tx:
            continue
        if relationship_fn(th, tx) == "contradicts":
            return True
    return False


def detect_soft_contradiction(claim_text: str, thesis: str) -> bool:
    _ = thesis
    s = (claim_text or "").strip()
    if not s:
        return False
    return bool(_SOFT_TENSION_RE.search(s))


def has_thesis_tension(
    claims: Sequence[ClaimRow],
    thesis: str,
    *,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> bool:
    th = (thesis or "").strip()
    if not th:
        return True
    if has_contrarian_claim(
        claims,
        th,
        lambda a, b: classify_relationship_hybrid(a, b, relationship_llm_fn),
    ):
        return True
    for c in claims:
        tx = (c.text or "").strip()
        if tx and detect_soft_contradiction(tx, th):
            return True
    return False


def extract_contrarian_line(
    claims: Sequence[ClaimRow],
    thesis: str,
    *,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> str:
    th = (thesis or "").strip()
    if not th:
        return ""
    for c in claims:
        tx = (c.text or "").strip()
        if not tx:
            continue
        if classify_relationship_hybrid(th, tx, relationship_llm_fn) == "contradicts":
            return tx
    for c in claims:
        tx = (c.text or "").strip()
        if not tx:
            continue
        if detect_soft_contradiction(tx, th):
            return tx
    return ""
