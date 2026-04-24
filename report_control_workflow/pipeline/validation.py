# report_control_workflow/pipeline/validation.py
"""Gates and contract checks (pure; no mutation of reports)."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Sequence

from report_control_workflow.constants import (
    CORE_INSIGHT_MAX_WORDS,
    DEFAULT_CLAIM_STRENGTH_MIN,
    DEFAULT_EVIDENCE_SCORE_MIN,
    DEFAULT_EVIDENCE_STRENGTH_MIN,
    DEFAULT_INSIGHT_NOVELTY_MIN,
    DEFAULT_THESIS_MIN_WORDS,
    DUPLICATE_CLAIM_SIMILARITY,
    MIN_CLAIMS,
    MIN_CLIPS_CONTRACT,
    _DIRECTIONAL,
    _INTERNAL_ACTION_BANNED,
    _PAST_PART,
    _VERB_LIKE,
    _WEAK_OPENERS,
)
from report_control_workflow.core.models import ClaimRow, ControlReport
from report_control_workflow.core.utils import text_similarity
from report_control_workflow.intelligence.clips import validate_clip_diversity
from report_control_workflow.intelligence.contrarian import has_thesis_tension
from report_control_workflow.intelligence.relationships import classify_relationship_hybrid, is_relevant
from report_control_workflow.pipeline.scoring import (
    score_claim_strength,
    score_evidence_strength,
    score_insight_novelty,
)


def has_subject_verb_structure(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 12:
        return False
    if _VERB_LIKE.search(t):
        return True
    if _PAST_PART.search(t):
        return True
    return len(t.split()) >= 12


def contains_directional_claim(text: str) -> bool:
    return bool(_DIRECTIONAL.search(text or ""))


def is_valid_thesis(thesis: str) -> bool:
    t = (thesis or "").strip()
    if len(t.split()) < 10:
        return False
    if not has_subject_verb_structure(t):
        return False
    if not contains_directional_claim(t):
        return False
    if score_claim_strength(t) < 0.45:
        return False
    return True


def is_valid_claim(
    text: str,
    *,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
) -> bool:
    s = (text or "").strip()
    if len(s) < 20:
        return False
    if s[0].isalpha() and not s[0].isupper():
        return False
    if not s.endswith("."):
        return False
    words = s.split()
    if len(words) < 8:
        return False
    low = s.lower()
    if re.search(r"\b(like|you know|i mean|sort of|kind of)\b", low):
        return False
    if _WEAK_OPENERS.search(s):
        return False
    if not has_subject_verb_structure(s):
        return False
    if score_claim_strength(s) < claim_strength_min:
        return False
    if score_insight_novelty(s) < insight_novelty_min:
        return False
    return True


def is_valid_action(action: str) -> bool:
    s = (action or "").strip()
    if len(s.split()) < 6:
        return False
    if _INTERNAL_ACTION_BANNED.search(s):
        return False
    first = s.split()[0] if s.split() else ""
    allowed = (
        "Check",
        "Look",
        "Find",
        "Test",
        "Try",
        "Schedule",
        "Book",
        "Read",
        "Call",
        "Email",
        "Record",
        "Post",
        "Share",
    )
    return first.startswith(allowed)


def validate_claims(
    claims: Sequence[ClaimRow],
    *,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
) -> List[str]:
    errs: List[str] = []
    for i, c in enumerate(claims):
        tx = (c.text or "").strip()
        if not tx:
            errs.append(f"Claim[{i}] empty")
            continue
        if not is_valid_claim(
            tx,
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
        ):
            errs.append(f"Claim[{i}] failed is_valid_claim (not a testable claim line)")
    return errs


def validate_output_contract(data: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    if "thesis" not in data:
        errs.append("output_contract: missing thesis")
    th = str(data.get("thesis") or "").strip()
    if not th:
        errs.append("output_contract: thesis empty")
    cl = data.get("claims")
    if not isinstance(cl, list) or len(cl) < MIN_CLAIMS:
        n = len(cl) if isinstance(cl, list) else 0
        errs.append(f"output_contract: claims need >={MIN_CLAIMS}, got {n}")
    insight = str(data.get("core_insight") or "").strip()
    if not insight:
        errs.append("output_contract: core_insight empty")
    elif len(insight.split()) > CORE_INSIGHT_MAX_WORDS + 1:
        errs.append("output_contract: core_insight exceeds word budget")
    if insight.endswith("?"):
        errs.append("output_contract: core_insight should be declarative (not a question)")
    clips = data.get("clips")
    if not isinstance(clips, list) or len(clips) < MIN_CLIPS_CONTRACT:
        n = len(clips) if isinstance(clips, list) else 0
        errs.append(f"output_contract: clips need >={MIN_CLIPS_CONTRACT}, got {n}")
    elif isinstance(clips, list) and len(clips) >= 2 and not validate_clip_diversity(clips):
        errs.append("output_contract: clips are too similar (pairwise dedupe)")
    return errs


def enforce_output_contract(data: Dict[str, Any]) -> Dict[str, Any]:
    errs = validate_output_contract(data)
    if errs:
        raise ValueError("; ".join(errs))
    return data


def validate_report(
    report: ControlReport,
    *,
    thesis_min_words: int = DEFAULT_THESIS_MIN_WORDS,
    evidence_score_min: float = DEFAULT_EVIDENCE_SCORE_MIN,
    min_claims: int = MIN_CLAIMS,
    validate_actions: bool = True,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    evidence_strength_min: float = DEFAULT_EVIDENCE_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
    require_substantive_thesis: bool = True,
    require_contrarian: bool = False,
) -> List[str]:
    errs: List[str] = []
    th = (report.thesis or "").strip()
    if len(th.split()) < thesis_min_words:
        errs.append(f"Thesis too short: need >= {thesis_min_words} words")
    if th and require_substantive_thesis and not is_valid_thesis(th):
        errs.append(
            "Thesis failed is_valid_thesis (need >=10 words, predicate structure, "
            "directional language, and non-vacuous strength)"
        )

    if len(report.claims) < min_claims:
        errs.append(f"Insufficient claims after repair: need >= {min_claims}, got {len(report.claims)}")

    for i, c in enumerate(report.claims):
        tx = (c.text or "").strip()
        if not tx:
            errs.append(f"Claim[{i}] empty")
            continue
        if not is_valid_claim(
            tx,
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
        ):
            errs.append(f"Claim[{i}] failed is_valid_claim (structure, strength, or insight novelty)")
            continue
        if len(tx.split()) < 8:
            errs.append(f"Claim[{i}] is not a complete sentence (need >= 8 words)")
            continue
        if th and not is_relevant(tx, th, relationship_llm_fn=relationship_llm_fn):
            errs.append(f"Claim[{i}] not connected to thesis (must support or contradict)")
            continue
        if not (c.evidence or "").strip():
            errs.append(f"Claim[{i}] missing evidence")
            continue
        if classify_relationship_hybrid(tx, c.evidence, relationship_llm_fn) != "supports":
            errs.append(f"Claim[{i}] evidence does not support claim (relationship gate)")
            continue
        if c.score < evidence_score_min:
            errs.append(f"Claim[{i}] evidence similarity {c.score:.2f} < {evidence_score_min}")
        evs = score_evidence_strength(tx, c.evidence)
        if evs < evidence_strength_min:
            errs.append(
                f"Claim[{i}] evidence strength {evs:.2f} < {evidence_strength_min} (too generic to prove)"
            )

    for i, a in enumerate(report.claims):
        for j, b in enumerate(report.claims):
            if j <= i:
                continue
            if a.text and text_similarity(a.text, b.text) >= DUPLICATE_CLAIM_SIMILARITY:
                errs.append("Duplicate content detected among claims")
                break

    if validate_actions and report.actions:
        for i, act in enumerate(report.actions):
            if not is_valid_action(act):
                errs.append(
                    f"Action[{i}] is not a valid external action "
                    f"(use imperative like Look/Find/Test…, >=6 words, not internal thesis checks)"
                )

    if require_contrarian and th and report.claims:
        if not has_thesis_tension(report.claims, th, relationship_llm_fn=relationship_llm_fn):
            errs.append(
                "No qualifying tension claim present (need hard contradicts or soft hedge/exception)"
            )

    seen: set = set()
    uniq: List[str] = []
    for e in errs:
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return uniq
