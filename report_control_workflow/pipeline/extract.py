# report_control_workflow/pipeline/extract.py
"""
Transcript cleaning, chunking, claim extraction, evidence mapping (pure transforms).

``clean_transcript`` is the **canonical** ASR/filler hygiene implementation; the package root
re-exports it for convenience, but production call sites that only need cleaning should import
from this module so resolution stays explicit.
"""

from __future__ import annotations

import re
from typing import Callable, List, Optional, Sequence

from report_control_workflow.constants import (
    DEFAULT_CLAIM_STRENGTH_MIN,
    DEFAULT_EVIDENCE_SCORE_MIN,
    DEFAULT_EVIDENCE_STRENGTH_MIN,
    DEFAULT_INSIGHT_NOVELTY_MIN,
    DEFAULT_RELEVANCE_MIN,
    DEFAULT_SEMANTIC_DEDUP,
    _COMMA_STUTTER,
    _FILLER_PHRASES,
    _MULTI_SPACE,
    _REPEAT_WORD,
    _YEAR_STUTTER,
)
from report_control_workflow.core.models import ClaimRow
from report_control_workflow.core.utils import text_similarity
from report_control_workflow.intelligence.relationships import classify_relationship_hybrid, is_relevant
from report_control_workflow.pipeline.scoring import score_evidence_strength
from report_control_workflow.pipeline.validation import is_valid_claim


def clean_transcript(text: str) -> str:
    try:
        from backend.episode_report_v3 import normalize_transcript_for_v3
    except ImportError:  # pragma: no cover
        from episode_report_v3 import normalize_transcript_for_v3  # type: ignore

    t = normalize_transcript_for_v3(text or "")
    t = _COMMA_STUTTER.sub(", ", t)
    t = _YEAR_STUTTER.sub(r"\1", t)
    for _ in range(4):
        nxt = _REPEAT_WORD.sub(r"\1", t)
        if nxt == t:
            break
        t = nxt
    t = _FILLER_PHRASES.sub(" ", t)
    t = _MULTI_SPACE.sub(" ", t)
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*", ", ", t)
    return t.strip()


def chunk_transcript(clean_text: str, max_chunk_chars: int = 900) -> List[str]:
    t = (clean_text or "").strip()
    if not t:
        return []
    paras = [p.strip() for p in re.split(r"\n{2,}", t) if p.strip()]
    if not paras:
        paras = [t]
    chunks: List[str] = []
    for p in paras:
        if len(p) <= max_chunk_chars:
            chunks.append(p)
            continue
        for i in range(0, len(p), max_chunk_chars):
            chunks.append(p[i : i + max_chunk_chars].strip())
    return [c for c in chunks if c]


def extract_claims(
    clean_text: str,
    *,
    max_items: int = 32,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
) -> List[ClaimRow]:
    t = (clean_text or "").strip()
    if not t:
        return []
    parts = re.split(r"(?<=[.!?])\s+", t)
    out: List[ClaimRow] = []
    seen: set = set()
    for p in parts:
        s = re.sub(r"\s+", " ", p.strip())
        if not s.endswith((".", "!", "?")):
            s = s + "." if s else s
        if s and s[0].isalpha() and s[0].islower():
            s = s[0].upper() + s[1:]
        if not is_valid_claim(
            s,
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
        ):
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ClaimRow(text=s, evidence="", score=0.0))
        if len(out) >= max_items:
            break
    return out


def map_evidence(
    claims: Sequence[ClaimRow],
    transcript_chunks: Sequence[str],
    *,
    score_min: float = DEFAULT_EVIDENCE_SCORE_MIN,
    require_supports: bool = True,
    evidence_strength_min: float = DEFAULT_EVIDENCE_STRENGTH_MIN,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> List[ClaimRow]:
    chunks = [c for c in transcript_chunks if (c or "").strip()]
    if not chunks:
        return [ClaimRow(text=c.text, evidence=c.evidence, score=c.score) for c in claims]
    out: List[ClaimRow] = []
    for c in claims:
        best_s = 0.0
        best_ex = ""
        for ch in chunks:
            sc = text_similarity(c.text, ch)
            if sc > best_s:
                best_s = sc
                best_ex = ch[:520].strip()
        if best_s < score_min:
            out.append(ClaimRow(text=c.text, evidence="", score=0.0))
            continue
        ev_strength = score_evidence_strength(c.text, best_ex)
        if ev_strength < evidence_strength_min:
            out.append(ClaimRow(text=c.text, evidence="", score=0.0))
            continue
        rel = classify_relationship_hybrid(c.text, best_ex, relationship_llm_fn)
        if require_supports and rel != "supports":
            out.append(ClaimRow(text=c.text, evidence="", score=0.0))
        else:
            combined = min(best_s, ev_strength)
            out.append(ClaimRow(text=c.text, evidence=best_ex, score=combined))
    return out


def filter_relevance(
    claims: Sequence[ClaimRow],
    thesis: str,
    *,
    min_thesis_overlap: float = DEFAULT_RELEVANCE_MIN,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> List[ClaimRow]:
    _ = min_thesis_overlap
    th = (thesis or "").strip()
    if not th:
        return list(claims)
    return [c for c in claims if is_relevant(c.text, th, relationship_llm_fn=relationship_llm_fn)]


def deduplicate(items: Sequence[str], *, threshold: float = DEFAULT_SEMANTIC_DEDUP) -> List[str]:
    out: List[str] = []
    for it in items:
        s = str(it).strip()
        if not s:
            continue
        if any(text_similarity(s, o) >= threshold for o in out):
            continue
        out.append(s)
    return out
