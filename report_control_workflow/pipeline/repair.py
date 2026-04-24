# report_control_workflow/pipeline/repair.py
"""Controlled mutation: drop rows, dedupe, compress, LLM repair JSON."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from report_control_workflow.constants import (
    DEFAULT_CLAIM_DIVERSITY_CLUSTER,
    DEFAULT_CLAIM_STRENGTH_MIN,
    DEFAULT_EVIDENCE_SCORE_MIN,
    DEFAULT_EVIDENCE_STRENGTH_MIN,
    DEFAULT_INSIGHT_NOVELTY_MIN,
    DEFAULT_OUTPUT_COMPRESS_THRESHOLD,
    DEFAULT_SEMANTIC_DEDUP,
    DEFAULT_THESIS_MIN_WORDS,
    REPAIR_PROMPT,
)
from report_control_workflow.core.models import ClaimRow, ControlReport
from report_control_workflow.core.utils import text_similarity
from report_control_workflow.intelligence.relationships import classify_relationship_hybrid
from report_control_workflow.pipeline.extract import deduplicate
from report_control_workflow.pipeline.scoring import score_claim_strength, score_evidence_strength
from report_control_workflow.pipeline.validation import is_valid_action, is_valid_claim, validate_report


def deduplicate_claim_rows(rows: Sequence[ClaimRow], *, threshold: float = DEFAULT_SEMANTIC_DEDUP) -> List[ClaimRow]:
    out: List[ClaimRow] = []
    for c in rows:
        if not c.text.strip():
            continue
        if any(text_similarity(c.text, o.text) >= threshold for o in out):
            continue
        out.append(c)
    return out


def enforce_claim_diversity(
    rows: Sequence[ClaimRow],
    *,
    cluster_threshold: float = DEFAULT_CLAIM_DIVERSITY_CLUSTER,
) -> List[ClaimRow]:
    ranked = sorted(
        [c for c in rows if (c.text or "").strip()],
        key=lambda c: score_claim_strength(c.text),
        reverse=True,
    )
    kept: List[ClaimRow] = []
    for c in ranked:
        if any(text_similarity(c.text, k.text) >= cluster_threshold for k in kept):
            continue
        kept.append(c)
    return kept


def compress_claim_rows(
    rows: Sequence[ClaimRow],
    *,
    threshold: float = DEFAULT_OUTPUT_COMPRESS_THRESHOLD,
) -> List[ClaimRow]:
    result: List[ClaimRow] = []
    for c in rows:
        if not (c.text or "").strip():
            continue
        if any(text_similarity(c.text, r.text) >= threshold for r in result):
            continue
        result.append(c)
    return result


def auto_repair(
    report: ControlReport,
    errors: Sequence[str],
    *,
    evidence_score_min: float = DEFAULT_EVIDENCE_SCORE_MIN,
    evidence_strength_min: float = DEFAULT_EVIDENCE_STRENGTH_MIN,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> ControlReport:
    _ = errors
    fixed = deepcopy(report)
    fixed.claims = [
        c
        for c in fixed.claims
        if (c.evidence or "").strip()
        and c.score >= evidence_score_min
        and len((c.text or "").split()) >= 8
        and is_valid_claim(
            c.text,
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
        )
        and score_evidence_strength(c.text, c.evidence) >= evidence_strength_min
        and classify_relationship_hybrid(c.text, c.evidence, relationship_llm_fn) == "supports"
    ]
    fixed.claims = deduplicate_claim_rows(fixed.claims)
    fixed.claims = enforce_claim_diversity(fixed.claims)
    fixed.highlights = deduplicate(fixed.highlights)
    fixed.clips = deduplicate(fixed.clips)
    fixed.actions = [a for a in deduplicate(fixed.actions) if is_valid_action(a)]
    return fixed


def _parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    s = (raw or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def repair_report_with_llm(
    report: ControlReport,
    errors: Sequence[str],
    llm_fn: Callable[[str], str],
    *,
    evidence_score_min: float = DEFAULT_EVIDENCE_SCORE_MIN,
    thesis_min_words: int = DEFAULT_THESIS_MIN_WORDS,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    evidence_strength_min: float = DEFAULT_EVIDENCE_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
    require_contrarian: bool = False,
    validate_actions: bool = True,
    require_substantive_thesis: bool = True,
) -> Tuple[ControlReport, List[str]]:
    payload = report.to_minimal_dict()
    prompt = REPAIR_PROMPT.format(
        report_json=json.dumps(payload, ensure_ascii=False, indent=2),
        errors="\n".join(f"- {e}" for e in errors) if errors else "(none listed)",
    )
    fixed_raw = (llm_fn(prompt) or "").strip()
    obj = _parse_json_object(fixed_raw)
    if not obj:
        return report, ["repair_report_with_llm: invalid JSON from llm_fn"]
    rep2 = ControlReport.from_minimal_dict(obj)
    err2 = validate_report(
        rep2,
        thesis_min_words=thesis_min_words,
        evidence_score_min=evidence_score_min,
        validate_actions=validate_actions,
        relationship_llm_fn=relationship_llm_fn,
        claim_strength_min=claim_strength_min,
        evidence_strength_min=evidence_strength_min,
        insight_novelty_min=insight_novelty_min,
        require_substantive_thesis=require_substantive_thesis,
        require_contrarian=require_contrarian,
    )
    return rep2, err2
