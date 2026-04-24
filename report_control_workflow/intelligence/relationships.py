# report_control_workflow/intelligence/relationships.py
"""Supports / contradicts / irrelevant classification (pure)."""

from __future__ import annotations

import re
from typing import Callable, Optional

from report_control_workflow.core.utils import text_similarity, token_overlap_ratio
from report_control_workflow.constants import HYBRID_RELATIONSHIP_SIM_HIGH, RELATIONSHIP_CLASSIFY_PROMPT


def classify_relationship(hypothesis: str, passage: str) -> str:
    h = (hypothesis or "").strip()
    p = (passage or "").strip()
    if not h or not p:
        return "irrelevant"
    sim = text_similarity(h, p)
    overlap = token_overlap_ratio(h, p)
    lowp = p.lower()
    neg_p = bool(
        re.search(
            r"\b(?:not|never|no|nothing|isn't|aren't|wasn't|weren't|without|lack(?:s|ing)?|fails?)\b",
            lowp,
        )
    )
    neg_h = bool(
        re.search(
            r"\b(?:not|never|no|nothing|isn't|aren't|wasn't|weren't|without|lack(?:s|ing)?|fails?)\b",
            h.lower(),
        )
    )
    if sim >= 0.5 and overlap >= 0.18 and neg_p != neg_h:
        return "contradicts"
    if sim >= 0.62 and overlap >= 0.22:
        return "supports"
    if sim >= 0.78 and overlap >= 0.12:
        return "supports"
    if sim >= 0.72 and overlap >= 0.08:
        return "supports"
    return "irrelevant"


def classify_relationship_llm(
    hypothesis: str,
    passage: str,
    llm_fn: Callable[[str], str],
) -> str:
    prompt = RELATIONSHIP_CLASSIFY_PROMPT.format(
        hypothesis=(hypothesis or "").strip()[:1200],
        passage=(passage or "").strip()[:1200],
    )
    raw = (llm_fn(prompt) or "").strip().lower()
    m = re.match(r"^(supports|contradicts|irrelevant)\b", raw)
    if m:
        return m.group(1)
    return classify_relationship(hypothesis, passage)


def classify_relationship_hybrid(
    hypothesis: str,
    passage: str,
    llm_fn: Optional[Callable[[str], str]] = None,
) -> str:
    h = (hypothesis or "").strip()
    p = (passage or "").strip()
    if not h or not p:
        return "irrelevant"
    if text_similarity(h, p) > HYBRID_RELATIONSHIP_SIM_HIGH:
        return classify_relationship(h, p)
    if llm_fn is not None:
        return classify_relationship_llm(h, p, llm_fn)
    return classify_relationship(h, p)


def is_relevant(
    claim_text: str,
    thesis: str,
    *,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> bool:
    th = (thesis or "").strip()
    if not th:
        return True
    rel = classify_relationship_hybrid(th, claim_text, relationship_llm_fn)
    return rel in ("supports", "contradicts")
