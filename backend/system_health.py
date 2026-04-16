"""
Single derived label for production: **what kind of stress** the run is under (not only scores).

``_system_health_label`` is stamped on the v3 report after guest trace / invariants are knowable.
"""

from __future__ import annotations

from typing import Any, Dict


def derive_system_health_label(report: Dict[str, Any]) -> str:
    """
    One of: HEALTHY, SUBSTRATE_NOISY, OVER_RESTRICTED, OVER_GENERATIVE, ANCHOR_FRAGILE, CLAIM_DEGRADED.

    Precedence is fixed: substrate/anchor crises before tuning labels.
    """
    claims = [c for c in (report.get("claims") or []) if isinstance(c, dict) and str(c.get("text") or "").strip()]
    cq = report.get("_claim_quality") if isinstance(report.get("_claim_quality"), dict) else {}
    tr = report.get("_guest_decision_trace") if isinstance(report.get("_guest_decision_trace"), dict) else {}

    score = cq.get("score")
    warning = bool(cq.get("warning"))
    # --- CLAIM_DEGRADED ---
    if not claims:
        return "CLAIM_DEGRADED"
    if isinstance(score, (int, float)) and float(score) < 0.35:
        return "CLAIM_DEGRADED"

    # --- ANCHOR_FRAGILE ---
    if tr.get("anchor_collapse_gate_fired"):
        return "ANCHOR_FRAGILE"
    mj = tr.get("anchor_alignment_score")
    if isinstance(mj, (int, float)) and float(mj) < 0.06:
        return "ANCHOR_FRAGILE"
    cr = tr.get("anchor_collapse_reason")
    if cr == "min_below_threshold_low_variance":
        return "ANCHOR_FRAGILE"

    # --- SUBSTRATE_NOISY (weak but not collapsed) ---
    if warning and isinstance(score, (int, float)) and float(score) >= 0.35:
        return "SUBSTRATE_NOISY"

    # --- OVER_RESTRICTED (SGV hammered the copy) ---
    srw = report.get("_sgv_rewrite_count")
    if isinstance(srw, int) and srw >= 6:
        return "OVER_RESTRICTED"
    if isinstance(srw, int) and srw >= 4 and str(report.get("output_mode") or "") == "diagnostic":
        return "OVER_RESTRICTED"

    # --- OVER_GENERATIVE (enrichment-heavy, little SGV friction) ---
    pc = str(tr.get("decision_primary_cause") or "")
    srw_i = int(srw) if isinstance(srw, int) else 0
    if (
        pc == "HIGH_SIGNAL_DOMINANT"
        and srw_i == 0
        and isinstance(score, (int, float))
        and float(score) > 0.72
        and bool(tr.get("guest_generation_effective"))
    ):
        return "OVER_GENERATIVE"

    return "HEALTHY"


def apply_system_health_label(report: Dict[str, Any]) -> str:
    """Set ``_system_health_label`` and return the label."""
    lab = derive_system_health_label(report)
    report["_system_health_label"] = lab
    return lab
