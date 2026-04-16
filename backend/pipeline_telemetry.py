"""
Pipeline-wide telemetry + **window comparison** (no runtime logic).

Extends guest-decision aggregates with claim-quality and SGV rewrite stats, then compares
two windows for drift early-warning.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

try:
    from .guest_decision_telemetry import aggregate_guest_decision_traces
except ImportError:
    from guest_decision_telemetry import aggregate_guest_decision_traces  # type: ignore


def _mean(xs: List[float]) -> Optional[float]:
    if not xs:
        return None
    return round(sum(xs) / len(xs), 4)


def aggregate_pipeline_telemetry(
    reports: Sequence[Dict[str, Any]],
    *,
    window_label: str = "rolling",
) -> Dict[str, Any]:
    """
    ``aggregate_guest_decision_traces`` plus:

    - ``mean_claim_quality_score``
    - ``mean_sgv_rewrite_count``
    - ``fraction_sgv_rewritten`` (``_sgv_status == REWRITTEN``)
    """
    base = aggregate_guest_decision_traces(reports, window_label=window_label)
    n = len(reports)
    cq_scores: List[float] = []
    sgv_rw: List[float] = []
    sgv_rewritten = 0
    sgv_any = 0

    for r in reports:
        if not isinstance(r, dict):
            continue
        cq = r.get("_claim_quality")
        if isinstance(cq, dict) and not cq.get("skipped"):
            s = cq.get("score")
            if isinstance(s, (int, float)):
                cq_scores.append(float(s))
        st = r.get("_sgv_status")
        if st is not None:
            sgv_any += 1
        if isinstance(r.get("_sgv_rewrite_count"), int):
            sgv_rw.append(float(r["_sgv_rewrite_count"]))
        if str(st or "") == "REWRITTEN":
            sgv_rewritten += 1

    denom = max(n, 1)
    pp: Dict[str, Any] = {
        "mean_claim_quality_score": _mean(cq_scores),
        "mean_sgv_rewrite_count": _mean(sgv_rw),
        "fraction_sgv_status_rewritten": round(sgv_rewritten / float(denom), 4),
        "episode_count_input": n,
        "episodes_with_sgv_status": sgv_any,
    }
    base["pipeline_profile"] = pp
    return base


def compare_telemetry_windows(
    recent: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    abs_delta_claim_quality: float = 0.12,
    abs_delta_sgv_rewrite: float = 1.25,
    abs_delta_high_signal_pct: float = 15.0,
    abs_delta_collapse_pct: float = 12.0,
) -> Dict[str, Any]:
    """
    Compare two outputs from ``aggregate_pipeline_telemetry`` (or compatible shapes).

    Sets ``DRIFT_DETECTED`` true if any |Δ| exceeds the corresponding threshold.
    """
    rp = recent.get("pipeline_profile") if isinstance(recent.get("pipeline_profile"), dict) else {}
    bp = baseline.get("pipeline_profile") if isinstance(baseline.get("pipeline_profile"), dict) else {}
    rs = recent.get("system_bias_profile") if isinstance(recent.get("system_bias_profile"), dict) else {}
    bs = baseline.get("system_bias_profile") if isinstance(baseline.get("system_bias_profile"), dict) else {}

    def gf(d: Dict[str, Any], k: str) -> Optional[float]:
        v = d.get(k)
        return float(v) if isinstance(v, (int, float)) else None

    d_cq = None
    a = gf(rp, "mean_claim_quality_score")
    b = gf(bp, "mean_claim_quality_score")
    if a is not None and b is not None:
        d_cq = round(a - b, 4)

    d_sgv = None
    a = gf(rp, "mean_sgv_rewrite_count")
    b = gf(bp, "mean_sgv_rewrite_count")
    if a is not None and b is not None:
        d_sgv = round(a - b, 4)

    d_hs = None
    a = gf(rs, "pct_driven_high_signal_primary")
    b = gf(bs, "pct_driven_high_signal_primary")
    if a is not None and b is not None:
        d_hs = round(a - b, 2)

    d_co = None
    a = gf(rs, "pct_collapse_suppressions")
    b = gf(bs, "pct_collapse_suppressions")
    if a is not None and b is not None:
        d_co = round(a - b, 2)

    flags = []
    if d_cq is not None and abs(d_cq) > abs_delta_claim_quality:
        flags.append("claim_quality")
    if d_sgv is not None and abs(d_sgv) > abs_delta_sgv_rewrite:
        flags.append("sgv_rewrite_rate")
    if d_hs is not None and abs(d_hs) > abs_delta_high_signal_pct:
        flags.append("high_signal_dominance")
    if d_co is not None and abs(d_co) > abs_delta_collapse_pct:
        flags.append("collapse_suppression")

    return {
        "delta_mean_claim_quality": d_cq,
        "delta_mean_sgv_rewrite_count": d_sgv,
        "delta_pct_high_signal_primary": d_hs,
        "delta_pct_collapse_suppressions": d_co,
        "drift_axes": flags,
        "DRIFT_DETECTED": len(flags) > 0,
        "recent_window": recent.get("window_label"),
        "baseline_window": baseline.get("window_label"),
    }
