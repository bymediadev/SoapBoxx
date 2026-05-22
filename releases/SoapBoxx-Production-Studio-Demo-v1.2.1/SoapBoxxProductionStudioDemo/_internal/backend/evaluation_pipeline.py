"""
Snapshot-based evaluation pipeline for workflow export decisions.

This module centralizes evaluation into a single pure-function path:
snapshot builder -> evaluator -> finalizer.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from .decision_engine import (
        DecisionConfig,
        decision_result_to_dict,
        evaluate_decision,
        validate_limited_reason_consistency,
    )
except ImportError:
    from decision_engine import (  # type: ignore
        DecisionConfig,
        decision_result_to_dict,
        evaluate_decision,
        validate_limited_reason_consistency,
    )

try:
    from .retry_policy import compute_retry_blocked
    from .system_contracts import (
        EVALUATION_OUTPUT_SCHEMA,
        EVALUATION_VERSION,
        INPUT_QUALITY_COMPONENTS_V1_KEYS,
        SYSTEM_VERSION,
    )
except ImportError:
    from retry_policy import compute_retry_blocked  # type: ignore
    from system_contracts import (  # type: ignore
        EVALUATION_OUTPUT_SCHEMA,
        EVALUATION_VERSION,
        INPUT_QUALITY_COMPONENTS_V1_KEYS,
        SYSTEM_VERSION,
    )

EVALUATION_SNAPSHOT_VERSION = "1"
EVALUATION_RESOLVER_VERSION = "1"
GROUNDING_RULE_VERSION = "1"

# Below this composite score, limited exports treat the run as an **input** problem (thin/unreadable
# signal) rather than a **content** problem (weak episode on adequate text). Tunable; keep in sync
# with tests.
INPUT_QUALITY_INPUT_THRESHOLD = 0.3

# Extraction dominates: length is a floor, grounding confirms structure at non-trivial claim count.
_INPUT_QUALITY_W_LENGTH = 0.2
_INPUT_QUALITY_W_EXTRACTION = 0.5
_INPUT_QUALITY_W_GROUNDING = 0.3

# Decision policy thresholds (single source of truth for :mod:`decision_engine`).
DECISION_EXTRACTION_MIN = 0.4
DECISION_GROUNDING_SOFT_MIN = 0.5
DECISION_GROUNDING_HARD_MIN = 0.3
DECISION_MODERATE_THRESHOLD = 0.7
DECISION_STRONG_THRESHOLD = 0.85


def build_decision_config() -> DecisionConfig:
    """Thresholds for :func:`decision_engine.evaluate_decision` — keeps pipeline and policy aligned."""
    return DecisionConfig(
        input_threshold=INPUT_QUALITY_INPUT_THRESHOLD,
        extraction_min=DECISION_EXTRACTION_MIN,
        grounding_soft_min=DECISION_GROUNDING_SOFT_MIN,
        grounding_hard_min=DECISION_GROUNDING_HARD_MIN,
        moderate_threshold=DECISION_MODERATE_THRESHOLD,
        strong_threshold=DECISION_STRONG_THRESHOLD,
    )


def _clamp_unit_interval(x: float) -> float:
    if x != x:  # NaN
        return 0.0
    return max(0.0, min(1.0, float(x)))


def _compute_input_quality_parts(
    transcript_word_count: int,
    claim_count: int,
    evidence_count: int,
) -> Tuple[float, float, float, float]:
    """
    Returns
    ``(input_quality_score, transcript_length_score, extraction_success_score, grounding_density_score)``.
    """
    twc = max(0, int(transcript_word_count))
    cc = max(0, int(claim_count))
    ev = max(0, int(evidence_count))

    transcript_length_score = _clamp_unit_interval(twc / 1500.0)

    denom = max(1.0, twc / 200.0)
    extraction_raw = (cc + ev) / denom
    extraction_success_score = _clamp_unit_interval(extraction_raw)

    ratio = ev / max(1, cc)
    sample_damp = min(1.0, cc / 5.0)
    grounding_density_score = _clamp_unit_interval(ratio * sample_damp)

    iqs = round(
        _clamp_unit_interval(
            _INPUT_QUALITY_W_LENGTH * transcript_length_score
            + _INPUT_QUALITY_W_EXTRACTION * extraction_success_score
            + _INPUT_QUALITY_W_GROUNDING * grounding_density_score
        ),
        6,
    )
    return (iqs, transcript_length_score, extraction_success_score, grounding_density_score)


def compute_input_quality_components(
    transcript_word_count: int,
    claim_count: int,
    evidence_count: int,
) -> Dict[str, float]:
    """Expose sub-scores for :mod:`decision_engine` and analytics."""
    iqs, tl, ex, gd = _compute_input_quality_parts(
        transcript_word_count, claim_count, evidence_count
    )
    return sanitize_input_quality_components_v1(
        {
            "input_quality_score": float(iqs),
            "transcript_length_score": float(tl),
            "extraction_success_score": float(ex),
            "grounding_density_score": float(gd),
        }
    )


def sanitize_input_quality_components_v1(raw: Dict[str, Any]) -> Dict[str, float]:
    """Only :data:`INPUT_QUALITY_COMPONENTS_V1_KEYS` — no extra dynamic keys."""
    out: Dict[str, float] = {}
    for k in INPUT_QUALITY_COMPONENTS_V1_KEYS:
        if k not in raw:
            continue
        try:
            out[k] = float(raw[k])
        except (TypeError, ValueError):
            continue
    return out


def compute_input_quality_score(
    transcript_word_count: int,
    claim_count: int,
    evidence_count: int,
) -> float:
    """
    Deterministic 0–1 composite: transcript depth, extraction yield vs length, grounded density.

    Weights (see module constants): length 0.2, extraction 0.5, grounding 0.3. Grounding is
    damped when ``claim_count`` is small so sparse claims do not look artificially perfect.

    Used for ``limited_reason`` (input vs content) and as a stable product signal for UI / ranking.
    """
    return float(_compute_input_quality_parts(transcript_word_count, claim_count, evidence_count)[0])


def derive_structure_state(evidence_rows: int, segments: int) -> str:
    if evidence_rows == 0 and segments == 0:
        return "FAIL"
    if evidence_rows < 2 or segments < 1:
        return "WEAK"
    return "STRONG"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_counts(
    workflow_report: Dict[str, Any], report_v3: Dict[str, Any]
) -> Tuple[int, int, int, int]:
    try:
        try:
            from .episode_report_v3 import bundle_grounded_evidence_counts
        except ImportError:
            from episode_report_v3 import bundle_grounded_evidence_counts  # type: ignore
    except ImportError:
        n_evidence = 0
        n_wf = 0
        n_r3 = 0
    else:
        n_evidence, n_wf, n_r3 = bundle_grounded_evidence_counts(
            {"workflow_report": workflow_report or {}, "report_v3": report_v3 or {}}
        )

    wf_segments = (workflow_report or {}).get("segments") or []
    r3_segments = (report_v3 or {}).get("segments") or []
    n_wf_seg = len(wf_segments)
    n_r3_seg = len(r3_segments)
    n_segments = max(n_wf_seg, n_r3_seg)
    return int(n_evidence), int(n_segments), int(n_wf), int(n_r3)


def build_evaluation_snapshot(
    workflow_report: Dict[str, Any],
    report_v3: Dict[str, Any],
    meta: Dict[str, Any],
) -> Dict[str, Any]:
    """Build canonical immutable evaluation input."""
    n_evidence, n_segments, n_wf_evidence, n_r3_evidence = _canonical_counts(
        workflow_report or {}, report_v3 or {}
    )
    r3 = report_v3 or {}
    wf = workflow_report or {}
    wmeta = (wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}) or {}
    rc = (wmeta.get("v3_reality_check") if isinstance(wmeta.get("v3_reality_check"), dict) else {}) or {}

    wf_segments = (wf.get("segments") if isinstance(wf.get("segments"), list) else []) or []
    r3_segments = (r3.get("segments") if isinstance(r3.get("segments"), list) else []) or []
    n_wf_segments = len(wf_segments)
    n_r3_segments = len(r3_segments)

    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    rr_metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    transcript_word_count = int(rr_metrics.get("transcript_word_count") or 0)
    readiness_band = str(rr.get("band") or "").strip().lower()
    claim_count = int(rr_metrics.get("claim_count") or 0)
    if claim_count <= 0:
        cl = r3.get("claims")
        if isinstance(cl, list):
            claim_count = len([x for x in cl if isinstance(x, dict)])

    snapshot_core: Dict[str, Any] = {
        "snapshot_version": EVALUATION_SNAPSHOT_VERSION,
        "resolver_version": EVALUATION_RESOLVER_VERSION,
        "grounding_rule_version": GROUNDING_RULE_VERSION,
        "run_id": str(meta.get("run_id") or ""),
        "trace_id": str(meta.get("trace_id") or ""),
        "created_at": _utc_now_iso(),
        "episode_id": str(meta.get("episode_id") or meta.get("title") or ""),
        "meta_context": {
            "title": str(meta.get("title") or ""),
            "creator": str(meta.get("creator") or ""),
            "genre": str(meta.get("genre") or ""),
        },
        "canonical_evidence_count": n_evidence,
        "canonical_segment_count": n_segments,
        "transcript_word_count": transcript_word_count,
        "readiness_band": readiness_band,
        "claim_count": claim_count,
        "source_discrepancies": {
            "evidence_count": {
                "workflow": n_wf_evidence,
                "report_v3": n_r3_evidence,
                "delta": abs(n_wf_evidence - n_r3_evidence),
                "mismatch": n_wf_evidence != n_r3_evidence,
            },
            "segment_count": {
                "workflow": n_wf_segments,
                "report_v3": n_r3_segments,
                "delta": abs(n_wf_segments - n_r3_segments),
                "mismatch": n_wf_segments != n_r3_segments,
            },
        },
        "strict_export_enabled": bool(meta.get("strict_export_enabled", True)),
        "report_v3_output_mode": str(r3.get("output_mode") or ""),
        "v3_reality_check": {
            "present": bool(rc),
            "passed": bool(rc.get("passed")) if "passed" in rc else None,
            "failures": [str(x) for x in (rc.get("failures") or []) if str(x).strip()],
            "would_ship": bool(rc.get("would_ship")) if "would_ship" in rc else None,
            "ship_blockers": [str(x) for x in (rc.get("ship_blockers") or []) if str(x).strip()],
            "rules_source": str(rc.get("rules_source") or ""),
        },
        # Inputs for integrity checks.
        "workflow_evidence_map": wf.get("evidence_map") if isinstance(wf.get("evidence_map"), list) else [],
        "workflow_follow_up_questions": wf.get("follow_up_questions")
        if isinstance(wf.get("follow_up_questions"), list)
        else [],
        # Runtime transport outcome (excluded from snapshot_hash — observability only).
        "ollama_transport_degraded": bool(wmeta.get("ollama_transport_degraded")),
        "ollama_last_transport_failure_code": str(wmeta.get("ollama_last_transport_failure_code") or ""),
    }
    # Snapshot hash must be deterministic across equivalent inputs; exclude runtime-only fields.
    hash_basis = {
        "snapshot_version": snapshot_core["snapshot_version"],
        "resolver_version": snapshot_core["resolver_version"],
        "grounding_rule_version": snapshot_core["grounding_rule_version"],
        "episode_id": snapshot_core["episode_id"],
        "meta_context": snapshot_core["meta_context"],
        "canonical_evidence_count": snapshot_core["canonical_evidence_count"],
        "canonical_segment_count": snapshot_core["canonical_segment_count"],
        "transcript_word_count": snapshot_core["transcript_word_count"],
        "readiness_band": snapshot_core["readiness_band"],
        "claim_count": snapshot_core["claim_count"],
        "source_discrepancies": snapshot_core["source_discrepancies"],
        "strict_export_enabled": snapshot_core["strict_export_enabled"],
        "report_v3_output_mode": snapshot_core["report_v3_output_mode"],
        "v3_reality_check": snapshot_core["v3_reality_check"],
        "workflow_evidence_map": snapshot_core["workflow_evidence_map"],
        "workflow_follow_up_questions": snapshot_core["workflow_follow_up_questions"],
    }
    snapshot_hash = _stable_hash(hash_basis)
    snap = dict(snapshot_core)
    snap["snapshot_hash"] = snapshot_hash
    return snap


def _is_structural_count_failure(msg: str) -> bool:
    low = (msg or "").lower()
    return ("evidence rows" in low and "min_evidence_rows" in low) or (
        "segments" in low and "min_segments" in low
    )


def _is_output_mode_blocker(msg: str) -> bool:
    low = (msg or "").lower()
    return "output_mode is diagnostic" in low or "not shippable as a full brief" in low


def compute_limited_reason(
    *,
    user_export_mode: str,
    export_status: str,
    snapshot: Dict[str, Any],
    export_blockers: List[str],
    blockers_by_source: Dict[str, Any],
    input_quality_score: float,
) -> Optional[str]:
    """
    Subtype for **limited** exports only: who owns the fix (creator vs input vs pipeline).

    - ``content`` — adequate input signal; weak structure / editorial extraction vs length.
    - ``input`` — composite :func:`input_quality_score` below :data:`INPUT_QUALITY_INPUT_THRESHOLD`.
    - ``system`` — transport/model/pipeline limits; retry before rewriting the episode.
    """
    if str(user_export_mode or "") != "limited":
        return None

    es = str(export_status or "").strip().lower()
    bbs = blockers_by_source if isinstance(blockers_by_source, dict) else {}
    ot = bbs.get("ollama_transport") or []
    if es == "degraded":
        return "system"
    if isinstance(ot, list) and any(str(x).strip() for x in ot):
        return "system"

    blob = " ".join(str(x) for x in (export_blockers or [])).lower()
    if any(
        k in blob
        for k in (
            "ollama transport",
            "transport exhausted",
            "timeout",
            "connection refused",
            "model unreachable",
        )
    ):
        return "system"

    iqs = _clamp_unit_interval(float(input_quality_score))
    if iqs < INPUT_QUALITY_INPUT_THRESHOLD:
        return "input"
    return "content"


def _integrity_checks(snapshot: Dict[str, Any]) -> Dict[str, bool]:
    evidence = snapshot.get("workflow_evidence_map")
    if not isinstance(evidence, list):
        evidence = []
    fu = snapshot.get("workflow_follow_up_questions")
    if not isinstance(fu, list):
        fu = []

    claim_keys: set[str] = set()
    duplicate_claim = False
    evidence_ids: set[str] = set()
    for idx, row in enumerate(evidence):
        if not isinstance(row, dict):
            continue
        claim = str(row.get("claim") or "").strip().lower()
        quote = str(row.get("evidence") or "").strip().lower()
        if claim and quote:
            key = f"{claim}|{quote}"
            if key in claim_keys:
                duplicate_claim = True
            claim_keys.add(key)
        rid = str(row.get("id") or f"row-{idx}").strip()
        if rid:
            evidence_ids.add(rid)

    orphaned = False
    unlinked_reasoning = False
    for q in fu:
        if not isinstance(q, dict):
            continue
        claim_id = str(q.get("claim_id") or "").strip()
        if not claim_id:
            unlinked_reasoning = True
            continue
        if evidence_ids and claim_id not in evidence_ids:
            orphaned = True

    # Conservative deterministic placeholder; deep contradiction detection can be added later.
    contradictory_claim_chain = False
    return {
        "no_duplicate_claims": not duplicate_claim,
        "no_orphaned_evidence": not orphaned,
        "no_contradictory_claim_chain": not contradictory_claim_chain,
        "no_unlinked_reasoning_steps": not unlinked_reasoning,
    }


def evaluate_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Single authoritative evaluator for snapshot state."""
    n_evidence = int(snapshot.get("canonical_evidence_count") or 0)
    n_segments = int(snapshot.get("canonical_segment_count") or 0)
    structure_state = derive_structure_state(n_evidence, n_segments)

    strict = bool(snapshot.get("strict_export_enabled", True))
    rc = snapshot.get("v3_reality_check") if isinstance(snapshot.get("v3_reality_check"), dict) else {}
    rc = rc or {}

    ollama_transport_blockers: List[str] = []
    if bool(snapshot.get("ollama_transport_degraded")):
        code = str(snapshot.get("ollama_last_transport_failure_code") or "").strip()
        ollama_transport_blockers.append(
            f"Ollama transport exhausted retries ({code})." if code else "Ollama transport exhausted retries."
        )

    v3_reality_blockers: List[str] = []
    rc_passed = rc.get("passed")
    if rc_passed is False:
        for msg in [str(x) for x in (rc.get("failures") or []) if str(x).strip()]:
            # Structural min rows/segments from report_v3 are stale for unified post-bootstrap evaluation.
            if _is_structural_count_failure(msg):
                continue
            v3_reality_blockers.append(msg)

    workflow_structure_blockers: List[str] = []
    if n_evidence < 2:
        workflow_structure_blockers.append(f"grounded evidence rows {n_evidence} < 2 (canonical)")
    if n_segments < 1:
        workflow_structure_blockers.append(f"segments {n_segments} < 1 (canonical)")

    output_mode = str(snapshot.get("report_v3_output_mode") or "").strip().lower()
    output_mode_valid = output_mode != "diagnostic"
    output_mode_blockers: List[str] = []
    if not output_mode_valid:
        output_mode_blockers.append("FAIL: output_mode is diagnostic — not shippable as a full brief.")

    unified_export_blockers: List[str] = []
    if rc.get("would_ship") is False:
        for msg in [str(x) for x in (rc.get("ship_blockers") or []) if str(x).strip()]:
            if _is_output_mode_blocker(msg):
                output_mode_blockers.append(msg)
                continue
            unified_export_blockers.append(msg)

    checks = _integrity_checks(snapshot)
    integrity_pass = all(bool(v) for v in checks.values())
    integrity_state = "pass" if integrity_pass else "fail"
    semantic_delta_valid = n_evidence > 0 and n_segments > 0

    all_blockers: List[str] = []
    blockers_by_source = {
        "v3_reality": v3_reality_blockers,
        "workflow_structure": workflow_structure_blockers,
        "unified_export": unified_export_blockers,
        "output_mode": output_mode_blockers,
        "ollama_transport": ollama_transport_blockers,
    }
    for src, vals in blockers_by_source.items():
        if src == "output_mode":
            continue
        all_blockers.extend(vals)

    transport_degraded = bool(snapshot.get("ollama_transport_degraded"))
    if transport_degraded:
        export_status = "degraded"
    elif strict:
        export_status = "insufficient_signal" if all_blockers else "ok"
    else:
        export_status = "ok"

    signal_valid = export_status == "ok" and integrity_pass
    evaluation_eligible = signal_valid and semantic_delta_valid
    production_candidate = evaluation_eligible and output_mode_valid

    # User-facing tier: "full" = network-grade export; "limited" = best-effort + confidence (never empty).
    user_export_mode = "full" if production_candidate else "limited"

    twc_i = int(snapshot.get("transcript_word_count") or 0)
    cc_i = int(snapshot.get("claim_count") or 0)
    ev_i = int(snapshot.get("canonical_evidence_count") or 0)
    iq_components = compute_input_quality_components(twc_i, cc_i, ev_i)
    input_quality_score = float(iq_components["input_quality_score"])

    dconf = build_decision_config()
    decision_raw = evaluate_decision(
        input_quality_score,
        float(iq_components["extraction_success_score"]),
        float(iq_components["grounding_density_score"]),
        export_status=str(export_status),
        config=dconf,
    )
    decision_payload: Dict[str, Any] = decision_result_to_dict(
        decision_raw,
        export_status=str(export_status),
        metrics_ref="input_quality_components",
    )

    limited_reason = compute_limited_reason(
        user_export_mode=user_export_mode,
        export_status=str(export_status),
        snapshot=snapshot,
        export_blockers=all_blockers,
        blockers_by_source=blockers_by_source,
        input_quality_score=input_quality_score,
    )

    unified_failure_category = validate_limited_reason_consistency(
        limited_reason=limited_reason,
        decision=decision_payload,
    )

    return {
        "structure_state": structure_state,
        "structure_diagnostics": {
            "evidence_rows": n_evidence,
            "segments": n_segments,
            "structure_state": structure_state,
        },
        "export_status": export_status,
        "export_blockers": all_blockers,
        "export_blockers_by_source": blockers_by_source,
        "signal_integrity_check": integrity_state,
        "signal_integrity_checks": checks,
        "signal_valid": signal_valid,
        "semantic_delta_valid": semantic_delta_valid,
        "evaluation_eligible": evaluation_eligible,
        "output_mode_valid": output_mode_valid,
        "production_candidate": production_candidate,
        "production_blockers": output_mode_blockers,
        "user_export_mode": user_export_mode,
        "limited_reason": limited_reason,
        "input_quality_score": input_quality_score,
        "input_quality_components": iq_components,
        "decision": decision_payload,
        "unified_failure_category": unified_failure_category,
        "retry_blocked": compute_retry_blocked(decision_payload, budget=None),
        "evaluation_version": EVALUATION_VERSION,
        "system_version": SYSTEM_VERSION,
        "schema_version": EVALUATION_OUTPUT_SCHEMA,
    }


def _set_final_field(meta_out: Dict[str, Any], key: str, value: Any) -> None:
    """
    Guarded setter for final evaluation fields.

    Only code executing from this module may write final evaluation fields via this helper.
    """
    caller = inspect.currentframe().f_back  # type: ignore[union-attr]
    caller_mod = caller.f_globals.get("__name__", "") if caller else ""
    if caller_mod != __name__:
        raise RuntimeError(f"final field write denied for {key}: caller={caller_mod}")
    meta_out[key] = value


def finalize_evaluation(
    meta_out: Dict[str, Any],
    snapshot: Dict[str, Any],
    evaluation: Dict[str, Any],
    profile_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Single-writer finalizer for evaluation-owned metadata fields."""
    _set_final_field(meta_out, "structure_state", str(evaluation.get("structure_state") or "FAIL"))
    _set_final_field(
        meta_out, "structure_diagnostics", dict(evaluation.get("structure_diagnostics") or {})
    )
    _set_final_field(
        meta_out, "export_status", str(evaluation.get("export_status") or "insufficient_signal")
    )
    _set_final_field(meta_out, "export_blockers", list(evaluation.get("export_blockers") or []))
    _set_final_field(
        meta_out, "export_blockers_by_source", dict(evaluation.get("export_blockers_by_source") or {})
    )
    _set_final_field(
        meta_out, "signal_integrity_check", str(evaluation.get("signal_integrity_check") or "fail")
    )
    _set_final_field(
        meta_out, "signal_integrity_checks", dict(evaluation.get("signal_integrity_checks") or {})
    )
    _set_final_field(meta_out, "signal_valid", bool(evaluation.get("signal_valid")))
    _set_final_field(meta_out, "semantic_delta_valid", bool(evaluation.get("semantic_delta_valid")))
    _set_final_field(meta_out, "evaluation_eligible", bool(evaluation.get("evaluation_eligible")))
    _set_final_field(meta_out, "output_mode_valid", bool(evaluation.get("output_mode_valid")))
    _set_final_field(
        meta_out, "production_candidate", bool(evaluation.get("production_candidate"))
    )
    _set_final_field(
        meta_out, "production_blockers", list(evaluation.get("production_blockers") or [])
    )
    _set_final_field(
        meta_out, "user_export_mode", str(evaluation.get("user_export_mode") or "limited")
    )
    _set_final_field(meta_out, "limited_reason", evaluation.get("limited_reason"))
    _set_final_field(
        meta_out,
        "input_quality_score",
        float(evaluation.get("input_quality_score") or 0.0),
    )
    _iqc = evaluation.get("input_quality_components")
    _set_final_field(
        meta_out,
        "input_quality_components",
        sanitize_input_quality_components_v1(_iqc if isinstance(_iqc, dict) else {}),
    )
    _set_final_field(meta_out, "decision", dict(evaluation.get("decision") or {}))
    _set_final_field(
        meta_out, "source_discrepancies", dict(snapshot.get("source_discrepancies") or {})
    )
    _set_final_field(meta_out, "evaluation_snapshot_version", str(snapshot.get("snapshot_version") or ""))
    _set_final_field(meta_out, "evaluation_snapshot_hash", str(snapshot.get("snapshot_hash") or ""))
    _set_final_field(meta_out, "evaluation_finalized", True)
    _set_final_field(meta_out, "evaluation_finalized_at", _utc_now_iso())

    _set_final_field(meta_out, "system_version", str(evaluation.get("system_version") or SYSTEM_VERSION))
    _set_final_field(meta_out, "evaluation_version", str(evaluation.get("evaluation_version") or EVALUATION_VERSION))
    _set_final_field(meta_out, "schema_version", str(evaluation.get("schema_version") or EVALUATION_OUTPUT_SCHEMA))
    _set_final_field(meta_out, "retry_blocked", bool(evaluation.get("retry_blocked")))
    ufc = evaluation.get("unified_failure_category")
    if ufc is not None:
        _set_final_field(meta_out, "unified_failure_category", str(ufc))
    else:
        dec = evaluation.get("decision") if isinstance(evaluation.get("decision"), dict) else {}
        _set_final_field(
            meta_out,
            "unified_failure_category",
            validate_limited_reason_consistency(
                limited_reason=evaluation.get("limited_reason"),
                decision=dec,
            ),
        )
    if profile_context is not None:
        try:
            from .report_renderer import resolve_editorial_profile_key
        except ImportError:
            from report_renderer import resolve_editorial_profile_key  # type: ignore
        _set_final_field(
            meta_out,
            "editorial_profile",
            str(resolve_editorial_profile_key(profile_context)),
        )
    return meta_out

