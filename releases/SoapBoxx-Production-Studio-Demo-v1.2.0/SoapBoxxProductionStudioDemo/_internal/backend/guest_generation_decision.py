"""
Guest generation: issue-axis vs HIGH_SIGNAL enrichment-axis, with a single arbitration point.

``build_v3_report`` stamps ``_guest_decision_trace`` for observability; ``should_generate_guests``
uses the same rules so workflow behavior matches the trace.

**Symmetry:** both axes respect **extreme** anchor collapse when min Jaccard is in the collapse
band *and* (with 2+ samples) the Jaccard distribution is **tight** (low variance) — consistent
structural drift vs one noisy outlier field.

**Interpretability:** ``decision_primary_cause`` names the decisive narrative; ``anchor_stability_profile``
and ``guest_generation_confidence`` support batch health / ranking (not probabilistic truth claims).

**Unified trace contract** (``_guest_decision_trace``): state + ordering + primary cause + stability +
confidence — sufficient for batch dashboards without scattering flags across callers.
"""

from __future__ import annotations

import os
import statistics
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Enrichment-only: min Jaccard before HIGH_SIGNAL guest generation (aligned with soft-warn band).
_DEFAULT_HIGH_SIGNAL_MIN_ANCHOR = 0.10

# Extreme mismatch band (aligned with ``_CONSISTENCY_COLLAPSE`` in ``episode_report_v3``).
_DEFAULT_COLLAPSE_SUPPRESS = 0.05

# With 2+ Jaccard samples: collapse only if spread is below this (consistent failure vs outlier).
_DEFAULT_COLLAPSE_MAX_VARIANCE = 0.02


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return default


def high_signal_arbitration_threshold() -> float:
    return _env_float("SOAPBOXX_GUEST_HIGH_SIGNAL_MIN_ANCHOR", _DEFAULT_HIGH_SIGNAL_MIN_ANCHOR)


def anchor_collapse_suppress_threshold() -> float:
    return _env_float("SOAPBOXX_GUEST_COLLAPSE_SUPPRESS_THRESHOLD", _DEFAULT_COLLAPSE_SUPPRESS)


def anchor_collapse_max_variance() -> float:
    return _env_float("SOAPBOXX_GUEST_COLLAPSE_MAX_VARIANCE", _DEFAULT_COLLAPSE_MAX_VARIANCE)


def jaccard_values_from_report(r3: Dict[str, Any]) -> List[float]:
    samples = r3.get("_consistency_jaccard_samples")
    if not isinstance(samples, list):
        return []
    vals: List[float] = []
    for s in samples:
        if not isinstance(s, dict):
            continue
        j = s.get("jaccard")
        if isinstance(j, (int, float)):
            vals.append(float(j))
    return vals


def anchor_stability_profile(jaccard_values: Sequence[float]) -> Dict[str, Any]:
    """Distribution summary over identity Jaccard samples (not a semantic embedding)."""
    vals = [float(x) for x in jaccard_values]
    n = len(vals)
    if n == 0:
        return {
            "min_jaccard": None,
            "mean_jaccard": None,
            "variance_jaccard": None,
            "sample_count": 0,
        }
    mn = min(vals)
    mean = sum(vals) / n
    if n == 1:
        var: Optional[float] = 0.0
    else:
        var = statistics.pvariance(vals)
    return {
        "min_jaccard": mn,
        "mean_jaccard": mean,
        "variance_jaccard": var,
        "sample_count": n,
    }


def min_anchor_jaccard_from_report(r3: Dict[str, Any]) -> Optional[float]:
    vals = jaccard_values_from_report(r3)
    if not vals:
        return None
    return min(vals)


def gather_issue_blob_for_guests(r3: Dict[str, Any]) -> str:
    parts: List[str] = []
    cr = r3.get("coach_report") if isinstance(r3.get("coach_report"), dict) else {}
    wb = cr.get("where_it_breaks") if isinstance(cr.get("where_it_breaks"), dict) else {}
    for x in wb.get("issues") or []:
        parts.append(str(x))
    ed = cr.get("episode_diagnosis") if isinstance(cr.get("episode_diagnosis"), dict) else {}
    for para in ed.get("body") or []:
        parts.append(str(para))
    ui = cr.get("uncomfortable_insight") if isinstance(cr.get("uncomfortable_insight"), dict) else {}
    parts.append(str(ui.get("body") or ""))
    for ins in (r3.get("clean_insights") or [])[:6]:
        parts.append(str(ins))
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    for n in rr.get("notes") or []:
        parts.append(str(n))
    return " ".join(parts).lower()


def meaningful_issue_signals_for_guests(r3: Dict[str, Any]) -> bool:
    cr = r3.get("coach_report") if isinstance(r3.get("coach_report"), dict) else {}
    wb = cr.get("where_it_breaks") if isinstance(cr.get("where_it_breaks"), dict) else {}
    issues = wb.get("issues") if isinstance(wb.get("issues"), list) else []
    if any(str(x).strip() for x in issues):
        return True
    return len(gather_issue_blob_for_guests(r3).strip()) >= 40


def high_signal_guest_opportunity(r3: Dict[str, Any]) -> bool:
    if str(r3.get("signal_mode") or "").strip().upper() != "HIGH_SIGNAL":
        return False
    ins = [str(x).strip() for x in (r3.get("clean_insights") or []) if str(x).strip()]
    if len(ins) < 3:
        return False
    cr = r3.get("coach_report") if isinstance(r3.get("coach_report"), dict) else {}
    wb = cr.get("where_it_breaks") if isinstance(cr.get("where_it_breaks"), dict) else {}
    issues = [x for x in (wb.get("issues") or []) if str(x).strip()]
    return len(issues) == 0


def _raw_trigger_source(issue_on: bool, high_on: bool) -> str:
    if issue_on and high_on:
        return "BOTH"
    if issue_on:
        return "ISSUE"
    if high_on:
        return "HIGH_SIGNAL"
    return "NONE"


def _structural_collapse_fired(
    min_j: Optional[float],
    stability: Dict[str, Any],
    collapse_thresh: float,
    max_var: float,
) -> Tuple[bool, str]:
    """
    Collapse = min in collapse band AND (single sample OR tight distribution).
    Returns (fired, reason_note).
    """
    if min_j is None:
        return False, "no_samples"
    if min_j >= collapse_thresh:
        return False, "min_above_threshold"
    n = int(stability.get("sample_count") or 0)
    var = stability.get("variance_jaccard")
    if n < 2:
        return True, "min_below_threshold_single_or_legacy"
    if isinstance(var, (int, float)) and float(var) <= max_var:
        return True, "min_below_threshold_low_variance"
    return False, "min_below_but_high_variance_outlier"


def _decision_primary_cause(
    collapse_fired: bool,
    effective: bool,
    effective_issue: bool,
    effective_high: bool,
    anchor_rescue: bool,
) -> str:
    if collapse_fired:
        return "COLLAPSE_SUPPRESSION"
    if anchor_rescue and effective:
        return "ANCHOR_RESCUE_OVERRIDE"
    if not effective:
        return "NO_GUEST_TRIGGER"
    if effective_issue and effective_high:
        return "MULTI_AXIS_CONVERGENCE"
    if effective_issue:
        return "ISSUE_AXIS_DOMINANT"
    if effective_high:
        return "HIGH_SIGNAL_DOMINANT"
    return "NO_GUEST_TRIGGER"


def _guest_generation_confidence(
    *,
    collapse_fired: bool,
    effective: bool,
    anchor_rescue: bool,
    signal_mode: str,
    stability: Dict[str, Any],
    effective_issue: bool,
    effective_high: bool,
    min_j: Optional[float],
) -> float:
    """Heuristic 0..1 ranking signal for batch dashboards — not calibrated probability."""
    sm = str(signal_mode or "").strip().upper()
    mean_j = stability.get("mean_jaccard")
    var_j = stability.get("variance_jaccard")

    if collapse_fired:
        mj = float(min_j) if isinstance(min_j, (int, float)) else 0.03
        return round(min(0.48, max(0.28, 0.42 - 2.0 * mj)), 3)

    if not effective:
        return 0.38

    c = 0.52
    if sm == "HIGH_SIGNAL":
        c += 0.12
    elif sm == "MEDIUM_SIGNAL":
        c += 0.04

    if isinstance(mean_j, (int, float)):
        mj = float(mean_j)
        c += min(0.14, max(0.0, (mj - 0.06) * 0.55))

    if isinstance(var_j, (int, float)) and float(var_j) < 0.012:
        c += 0.07

    axes = int(bool(effective_issue)) + int(bool(effective_high))
    if axes >= 2:
        c += 0.06
    elif axes == 1:
        c += 0.02

    if anchor_rescue:
        c -= 0.11

    if isinstance(mean_j, (int, float)) and float(mean_j) < 0.08:
        c -= 0.06

    return round(min(0.96, max(0.22, c)), 3)


def build_guest_decision_trace(r3: Dict[str, Any]) -> Dict[str, Any]:
    """
    Snapshot + **decision_steps** (evaluation order): raw axes, collapse gate, HIGH_SIGNAL gate, final.

    Stored on the v3 report as ``_guest_decision_trace`` (metadata / debugging).
    """
    steps: List[str] = []
    jvals = jaccard_values_from_report(r3)
    stability = anchor_stability_profile(jvals)
    min_j = stability.get("min_jaccard")
    if isinstance(min_j, (int, float)):
        min_j_f: Optional[float] = float(min_j)
    else:
        min_j_f = None

    sm = str(r3.get("signal_mode") or "").strip()
    issue_on = meaningful_issue_signals_for_guests(r3)
    high_raw = high_signal_guest_opportunity(r3)
    raw_src = _raw_trigger_source(issue_on, high_raw)
    thresh_high = high_signal_arbitration_threshold()
    collapse_thresh = anchor_collapse_suppress_threshold()
    max_var = anchor_collapse_max_variance()
    notes: List[str] = []

    steps.append("EVAL_ISSUE_AXIS")
    steps.append(f"ISSUE_AXIS_RAW:{'on' if issue_on else 'off'}")
    steps.append("EVAL_HIGH_SIGNAL_AXIS")
    steps.append(f"HIGH_SIGNAL_AXIS_RAW:{'on' if high_raw else 'off'}")

    effective_issue = issue_on
    effective_high = high_raw

    collapse_fired, collapse_reason = _structural_collapse_fired(
        min_j_f, stability, collapse_thresh, max_var
    )

    steps.append("ARBITRATE_ANCHOR_COLLAPSE_GATE")
    steps.append(f"COLLAPSE_RULE:{collapse_reason}")

    anchor_rescue = (
        (not collapse_fired)
        and min_j_f is not None
        and min_j_f < collapse_thresh
        and int(stability.get("sample_count") or 0) >= 2
        and collapse_reason == "min_below_but_high_variance_outlier"
    )

    if collapse_fired:
        effective_issue = False
        effective_high = False
        notes.append(
            f"all_axes_suppressed: structural_collapse ({collapse_reason}; "
            f"min_j={min_j_f:.3f}, threshold={collapse_thresh})"
        )
        steps.append(f"COLLAPSE_SUPPRESS:structural min_j={min_j_f:.3f}")
        steps.append("AXIS_EFFECTIVE_ISSUE:off")
        steps.append("AXIS_EFFECTIVE_HIGH_SIGNAL:off")
    else:
        if min_j_f is None:
            steps.append("COLLAPSE_GATE:no_anchor_samples (not_in_collapse_band)")
        else:
            steps.append(f"COLLAPSE_GATE:pass {collapse_reason} min_j={min_j_f:.3f}")
        if anchor_rescue:
            notes.append(
                "anchor_distribution_rescue: low min_j with high cross-field variance — "
                "treating as outlier noise, not structural collapse"
            )
            steps.append("ANCHOR_RESCUE:variance_blocked_structural_collapse")
        steps.append("ARBITRATE_HIGH_SIGNAL_VS_ANCHOR")
        if high_raw and not issue_on:
            if min_j_f is None:
                effective_high = False
                notes.append("high_signal_guest_suppressed: no_anchor_alignment_samples")
                steps.append("HIGH_SIGNAL_ANCHOR:suppress (no_samples)")
            elif min_j_f < thresh_high:
                effective_high = False
                notes.append(f"high_signal_guest_suppressed: anchor_alignment {min_j_f:.3f} < {thresh_high}")
                steps.append(f"HIGH_SIGNAL_ANCHOR:suppress min_j={min_j_f:.3f}_lt_{thresh_high}")
            else:
                steps.append(f"HIGH_SIGNAL_ANCHOR:pass min_j={min_j_f:.3f}")
        else:
            steps.append("HIGH_SIGNAL_ANCHOR:skipped (issue_axis_on or high_raw_off)")
        steps.append(f"AXIS_EFFECTIVE_ISSUE:{'on' if effective_issue else 'off'}")
        steps.append(f"AXIS_EFFECTIVE_HIGH_SIGNAL:{'on' if effective_high else 'off'}")

    effective = effective_issue or effective_high
    eff_src = _raw_trigger_source(effective_issue, effective_high)

    primary = _decision_primary_cause(
        collapse_fired,
        effective,
        effective_issue,
        effective_high,
        anchor_rescue,
    )

    confidence = _guest_generation_confidence(
        collapse_fired=collapse_fired,
        effective=effective,
        anchor_rescue=anchor_rescue,
        signal_mode=sm,
        stability=stability,
        effective_issue=effective_issue,
        effective_high=effective_high,
        min_j=min_j_f,
    )

    steps.append("ARBITRATE_FINAL_DECISION")
    steps.append(f"PRIMARY_CAUSE:{primary}")
    steps.append(f"GUEST_GENERATION:{'on' if effective else 'off'}")
    if effective_issue and not effective_high:
        steps.append("DOMINANT_AXIS:ISSUE")
    elif effective_high and not effective_issue:
        steps.append("DOMINANT_AXIS:HIGH_SIGNAL")
    elif effective_issue and effective_high:
        steps.append("DOMINANT_AXIS:BOTH")
    else:
        steps.append("DOMINANT_AXIS:NONE")

    return {
        "anchor_alignment_score": min_j_f,
        "anchor_stability_profile": stability,
        "signal_mode": sm,
        "issue_presence": issue_on,
        "issue_axis_effective": effective_issue,
        "high_signal_axis_effective": effective_high,
        "high_signal_opportunity_raw": high_raw,
        "anchor_collapse_gate_fired": collapse_fired,
        "anchor_collapse_threshold": collapse_thresh,
        "anchor_collapse_max_variance": max_var,
        "anchor_collapse_reason": collapse_reason,
        "guest_trigger_source_raw": raw_src,
        "guest_trigger_source": eff_src,
        "guest_generation_effective": effective,
        "decision_primary_cause": primary,
        "guest_generation_confidence": confidence,
        "high_signal_arbitration_threshold": thresh_high,
        "arbitration_notes": notes,
        "decision_steps": steps,
    }


def should_generate_guests(r3: Dict[str, Any]) -> bool:
    """True when an axis survives symmetric collapse + HIGH_SIGNAL anchor arbitration."""
    return build_guest_decision_trace(r3)["guest_generation_effective"]
