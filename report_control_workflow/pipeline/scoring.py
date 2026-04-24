# report_control_workflow/pipeline/scoring.py
"""Heuristic scores (pure functions; :func:`score_report` composes signals)."""

from __future__ import annotations

import re
from itertools import combinations
from typing import Callable, List, Optional, Sequence

from report_control_workflow.constants import (
    DEFAULT_CONTRARIAN_SCORE_PENALTY,
    DEFAULT_DENSITY_MIN,
    DUPLICATE_CLAIM_SIMILARITY,
    DENSITY_PENALTY_MAX,
    MIN_CLAIMS,
    _EVIDENCE_CONCRETE,
    _EVIDENCE_VAGUE,
    _INSIGHT_GENERIC,
    _PROGRESSION,
    _STRONG_VERBS,
    _VAGUE_WORDS,
)
from report_control_workflow.core.models import ClaimRow, ControlReport
from report_control_workflow.core.utils import report_token_density, text_similarity
from report_control_workflow.intelligence.contrarian import has_thesis_tension
from report_control_workflow.intelligence.relationships import is_relevant


def score_claim_strength(claim: str) -> float:
    s = (claim or "").strip()
    if len(s) < 24:
        return 0.2
    sc = 0.55
    if _VAGUE_WORDS.search(s):
        sc -= 0.22
    if _STRONG_VERBS.search(s):
        sc += 0.18
    if re.search(r"\b(?:percent|%|\d{4}|first|second|third|last)\b", s, re.I):
        sc += 0.08
    if re.search(r"\b(?:not|never|without)\b", s, re.I):
        sc += 0.05
    if re.search(r"\b(?:might|could|maybe|perhaps|seems?)\b", s, re.I):
        sc -= 0.08
    ntok = len(re.findall(r"[a-z0-9']+", s.lower()))
    if ntok >= 18:
        sc += 0.06
    return max(0.0, min(1.0, float(sc)))


def score_evidence_strength(claim: str, evidence: str) -> float:
    c, ev = (claim or "").strip(), (evidence or "").strip()
    if not c or not ev:
        return 0.0
    sc = 0.42 + 0.28 * text_similarity(c, ev)
    if _EVIDENCE_CONCRETE.search(ev):
        sc += 0.14
    if _EVIDENCE_VAGUE.search(ev):
        sc -= 0.18
    if re.search(r"\b(?:because|therefore|after|before|when|led\s+to|caused)\b", ev, re.I):
        sc += 0.06
    if len(ev.split()) < 8:
        sc -= 0.1
    return max(0.0, min(1.0, float(sc)))


def score_insight_novelty(claim: str, corpus: Optional[Sequence[str]] = None) -> float:
    _ = corpus
    s = (claim or "").strip()
    if len(s) < 20:
        return 0.2
    claim_l = s.lower()
    sc = 0.52
    if _INSIGHT_GENERIC.search(claim_l):
        sc -= 0.18
    if _VAGUE_WORDS.search(s):
        sc -= 0.1
    if any(ch.isdigit() for ch in s):
        sc += 0.12
    for w in s.split():
        if len(w) > 2 and w[0].isupper() and w[1:].islower():
            sc += 0.12
            break
    if any(m in claim_l for m in ("because", "leads to", "results in", "drives", "causes")):
        sc += 0.1
    if re.search(r"\b(?:rockefeller|foundation|district|mandate|statute|board|vendor)\b", claim_l):
        sc += 0.06
    ntok = len(re.findall(r"[a-z0-9']+", claim_l))
    if ntok >= 14:
        sc += 0.04
    return max(0.0, min(1.0, float(sc)))


def score_argument_cohesion(claim_texts: Sequence[str]) -> float:
    texts = [str(t).strip() for t in claim_texts if str(t).strip()]
    if len(texts) < 2:
        return 0.55
    sims = [text_similarity(a, b) for a, b in combinations(texts, 2)]
    avg_sim = sum(sims) / len(sims)
    prog_boost = 0.08 if any(_PROGRESSION.search(t) for t in texts) else 0.0
    if avg_sim > 0.88:
        return max(0.0, 0.35 + prog_boost)
    if avg_sim < 0.18:
        return max(0.0, 0.42 + prog_boost)
    return min(1.0, 0.72 + prog_boost + (0.22 - abs(avg_sim - 0.48)) * 0.3)


def information_quality_score(
    density: float,
    avg_claim_strength: float,
    avg_evidence_strength: float,
) -> float:
    return max(
        0.0,
        min(1.0, 0.5 * density + 0.3 * avg_claim_strength + 0.2 * avg_evidence_strength),
    )


def score_report(
    report: ControlReport,
    *,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> float:
    from report_control_workflow.pipeline.validation import is_valid_action

    th = (report.thesis or "").strip()
    claims = list(report.claims)
    if not claims and not th:
        return 0.0
    texts = [c.text for c in claims]
    avg_sc = sum(c.score for c in claims) / max(1, len(claims))
    with_ev = sum(1 for c in claims if (c.evidence or "").strip()) / max(1, len(claims))
    align = (
        sum(1 for c in claims if is_relevant(c.text, th, relationship_llm_fn=relationship_llm_fn))
        / max(1, len(claims))
        if th
        else 1.0
    )
    dup_pen = 0.0
    for i, a in enumerate(claims):
        for j, b in enumerate(claims):
            if j <= i:
                continue
            if a.text and text_similarity(a.text, b.text) >= DUPLICATE_CLAIM_SIMILARITY:
                dup_pen += 0.12
    act_ok = (
        sum(1 for a in report.actions if is_valid_action(a)) / max(1, len(report.actions))
        if report.actions
        else 1.0
    )
    avg_q = sum(score_claim_strength(c.text) for c in claims) / max(1, len(claims))
    ev_rows = [c for c in claims if (c.evidence or "").strip()]
    avg_evq = (
        sum(score_evidence_strength(c.text, c.evidence) for c in ev_rows) / len(ev_rows) if ev_rows else 0.0
    )
    avg_nov = sum(score_insight_novelty(c.text) for c in claims) / max(1, len(claims))
    coh = score_argument_cohesion(texts)
    dens = report_token_density(report)
    info_q = information_quality_score(dens, avg_q, avg_evq)
    density_pen = 0.0
    if dens < DEFAULT_DENSITY_MIN:
        density_pen = min(DENSITY_PENALTY_MAX, (DEFAULT_DENSITY_MIN - dens) * 1.15) * 0.45

    contrarian_pen = 0.0
    if th and claims and not has_thesis_tension(claims, th, relationship_llm_fn=relationship_llm_fn):
        contrarian_pen = DEFAULT_CONTRARIAN_SCORE_PENALTY

    raw = (
        0.18 * avg_sc
        + 0.12 * with_ev
        + 0.12 * align
        + 0.08 * act_ok
        + 0.12 * avg_q
        + 0.10 * avg_evq
        + 0.10 * info_q
        + 0.10 * avg_nov
        + 0.10 * coh
    )
    raw -= min(0.18, dup_pen)
    raw -= density_pen
    raw -= contrarian_pen
    if len(claims) < MIN_CLAIMS:
        raw *= 0.55
    return max(0.0, min(1.0, float(raw)))


__all__ = [
    "score_claim_strength",
    "score_evidence_strength",
    "score_insight_novelty",
    "score_argument_cohesion",
    "information_quality_score",
    "score_report",
]
