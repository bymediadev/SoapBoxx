# report_control_workflow/pipeline/control_pipeline.py
"""
Single orchestration entry: ordered gates, repair loop, assembly, scoring, decisions.

**Canonical full pipeline:** import only :func:`run_control_pipeline` for end-to-end execution.
Do not re-sequence gates in callers; that duplicates logic and drifts from tests.

**Transcript hygiene only:** use :func:`report_control_workflow.pipeline.extract.clean_transcript`
when you are not running the full pipeline (SoapBoxx v3 uses that path behind an env flag).

::

    from report_control_workflow.pipeline.control_pipeline import run_control_pipeline
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from report_control_workflow.constants import (
    DEFAULT_CLAIM_STRENGTH_MIN,
    DEFAULT_CLIP_SELECT_K,
    DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER,
    DEFAULT_EVIDENCE_SCORE_MIN,
    DEFAULT_EVIDENCE_STRENGTH_MIN,
    DEFAULT_INSIGHT_NOVELTY_MIN,
    DEFAULT_OUTPUT_COMPRESS_THRESHOLD,
    DEFAULT_THESIS_MIN_WORDS,
    MAX_WARNINGS_IN_OUTPUT,
    MIN_CLAIMS,
)
from report_control_workflow.core.models import ClaimRow, ControlReport
from report_control_workflow.intelligence.contrarian import extract_contrarian_line
from report_control_workflow.intelligence.insight import resolve_core_insight
from report_control_workflow.logging.error_log import log_errors
from report_control_workflow.logging.metrics import REPORT_SCORE_HISTORY, normalize_score, store_report_score
from report_control_workflow.pipeline.assembly import assemble_report
from report_control_workflow.pipeline.extract import (
    chunk_transcript,
    clean_transcript,
    deduplicate,
    extract_claims,
    filter_relevance,
    map_evidence,
)
from report_control_workflow.pipeline.repair import (
    auto_repair,
    compress_claim_rows,
    deduplicate_claim_rows,
    enforce_claim_diversity,
    repair_report_with_llm,
)
from report_control_workflow.pipeline.scoring import score_report
from report_control_workflow.pipeline.validation import is_valid_action, validate_claims, validate_output_contract, validate_report
from report_control_workflow.runtime.decisions import decide_report_action, decide_report_action_v2


def run_control_pipeline(
    transcript: str,
    *,
    thesis: str = "",
    title: str = "",
    initial_claims: Optional[Sequence[ClaimRow]] = None,
    highlights: Optional[Sequence[str]] = None,
    clips: Optional[Sequence[str]] = None,
    actions: Optional[Sequence[str]] = None,
    evidence_score_min: float = DEFAULT_EVIDENCE_SCORE_MIN,
    thesis_min_words: int = DEFAULT_THESIS_MIN_WORDS,
    claim_strength_min: float = DEFAULT_CLAIM_STRENGTH_MIN,
    evidence_strength_min: float = DEFAULT_EVIDENCE_STRENGTH_MIN,
    insight_novelty_min: float = DEFAULT_INSIGHT_NOVELTY_MIN,
    require_contrarian: bool = False,
    max_repair_rounds: int = 2,
    return_score: bool = False,
    return_decision: bool = False,
    llm_repair_fn: Optional[Callable[[str], str]] = None,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
    require_substantive_thesis: bool = True,
    log_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    output_compress_enabled: bool = True,
    output_compress_threshold: float = DEFAULT_OUTPUT_COMPRESS_THRESHOLD,
    clip_select_k: int = DEFAULT_CLIP_SELECT_K,
    derive_clips_from_claims: bool = True,
    track_scores: bool = True,
    use_granular_decision: bool = True,
    core_insight_synthesis_llm_fn: Optional[Callable[[str], str]] = None,
    synthesis_novelty_trigger: float = DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER,
) -> Union[
    Tuple[Dict[str, Any], List[str]],
    Tuple[Dict[str, Any], List[str], float],
    Tuple[Dict[str, Any], List[str], float, str],
]:
    cleaned = clean_transcript(transcript)
    chunks = chunk_transcript(cleaned)
    claims = (
        list(initial_claims)
        if initial_claims is not None
        else extract_claims(
            cleaned,
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
        )
    )
    claims = [
        c
        for c in claims
        if not validate_claims(
            [c],
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
        )
    ]
    claims = map_evidence(
        claims,
        chunks,
        score_min=evidence_score_min,
        require_supports=True,
        evidence_strength_min=evidence_strength_min,
        relationship_llm_fn=relationship_llm_fn,
    )
    claims = filter_relevance(claims, thesis, relationship_llm_fn=relationship_llm_fn)
    claims = deduplicate_claim_rows(claims)
    claims = enforce_claim_diversity(claims)
    if output_compress_enabled:
        compressed = compress_claim_rows(claims, threshold=output_compress_threshold)
        if len(compressed) >= MIN_CLAIMS:
            claims = compressed
    rep = ControlReport(
        title=title,
        thesis=thesis,
        claims=claims,
        highlights=deduplicate(highlights or []),
        clips=deduplicate(clips or []),
        actions=[a for a in (actions or []) if is_valid_action(str(a))],
    )
    errors = validate_report(
        rep,
        thesis_min_words=thesis_min_words,
        evidence_score_min=evidence_score_min,
        validate_actions=bool(actions),
        relationship_llm_fn=relationship_llm_fn,
        claim_strength_min=claim_strength_min,
        evidence_strength_min=evidence_strength_min,
        insight_novelty_min=insight_novelty_min,
        require_substantive_thesis=require_substantive_thesis,
        require_contrarian=require_contrarian,
    )
    if errors:
        log_errors(errors, "validate_report", extra={"title": title}, sink=log_sink)
    rounds = 0
    while errors and rounds < max_repair_rounds:
        rep = auto_repair(
            rep,
            errors,
            evidence_score_min=evidence_score_min,
            evidence_strength_min=evidence_strength_min,
            claim_strength_min=claim_strength_min,
            insight_novelty_min=insight_novelty_min,
            relationship_llm_fn=relationship_llm_fn,
        )
        errors = validate_report(
            rep,
            thesis_min_words=thesis_min_words,
            evidence_score_min=evidence_score_min,
            validate_actions=bool(actions),
            relationship_llm_fn=relationship_llm_fn,
            claim_strength_min=claim_strength_min,
            evidence_strength_min=evidence_strength_min,
            insight_novelty_min=insight_novelty_min,
            require_substantive_thesis=require_substantive_thesis,
            require_contrarian=require_contrarian,
        )
        if errors:
            log_errors(errors, f"validate_report_after_repair_{rounds}", extra={"title": title}, sink=log_sink)
        rounds += 1
    if errors and llm_repair_fn is not None:
        rep, llm_errs = repair_report_with_llm(
            rep,
            errors,
            llm_repair_fn,
            evidence_score_min=evidence_score_min,
            thesis_min_words=thesis_min_words,
            relationship_llm_fn=relationship_llm_fn,
            claim_strength_min=claim_strength_min,
            evidence_strength_min=evidence_strength_min,
            insight_novelty_min=insight_novelty_min,
            require_contrarian=require_contrarian,
            validate_actions=bool(actions),
            require_substantive_thesis=require_substantive_thesis,
        )
        errors = validate_report(
            rep,
            thesis_min_words=thesis_min_words,
            evidence_score_min=evidence_score_min,
            validate_actions=bool(actions),
            relationship_llm_fn=relationship_llm_fn,
            claim_strength_min=claim_strength_min,
            evidence_strength_min=evidence_strength_min,
            insight_novelty_min=insight_novelty_min,
            require_substantive_thesis=require_substantive_thesis,
            require_contrarian=require_contrarian,
        )
        if llm_errs and any("invalid JSON" in e for e in llm_errs):
            errors = list(dict.fromkeys(llm_errs + errors))
        if errors:
            log_errors(errors, "validate_report_after_llm_repair", extra={"title": title}, sink=log_sink)
    rep.core_insight = resolve_core_insight(
        rep.claims,
        llm_fn=core_insight_synthesis_llm_fn,
        synthesis_novelty_trigger=synthesis_novelty_trigger,
    )
    rep.contrarian = extract_contrarian_line(
        rep.claims,
        rep.thesis,
        relationship_llm_fn=relationship_llm_fn,
    )
    data = assemble_report(
        rep,
        clip_select_k=clip_select_k,
        derive_clips_from_claims=derive_clips_from_claims,
        relationship_llm_fn=relationship_llm_fn,
    )
    contract_errs = validate_output_contract(data)
    errors = list(errors) + contract_errs
    if contract_errs:
        log_errors(contract_errs, "output_contract", extra={"title": title}, sink=log_sink)
    sc = score_report(rep, relationship_llm_fn=relationship_llm_fn)
    data["warnings"] = [str(e) for e in errors[:MAX_WARNINGS_IN_OUTPUT]]
    data["score_raw"] = float(sc)
    if track_scores:
        store_report_score(sc)
    data["score_normalized"] = normalize_score(sc, list(REPORT_SCORE_HISTORY))
    if return_decision:
        dec = decide_report_action_v2(sc, errors) if use_granular_decision else decide_report_action(sc)
        return data, errors, sc, dec
    if return_score:
        return data, errors, sc
    return data, errors
