"""
Rolling / batch **telemetry** over ``_guest_decision_trace`` — not runtime logic.

Use this to answer: “is the guest-decision system drifting over the last N episodes?”
Feed a list of traces (or v3 reports); get a compact ``system_bias_profile`` for dashboards.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence


def trace_from_v3_report(report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return ``_guest_decision_trace`` if present and dict-shaped."""
    t = report.get("_guest_decision_trace")
    return t if isinstance(t, dict) else None


def _normalize_trace_item(item: Any) -> Optional[Dict[str, Any]]:
    if isinstance(item, dict):
        if "decision_primary_cause" in item or "guest_generation_effective" in item:
            return item
        return trace_from_v3_report(item)
    return None


def aggregate_guest_decision_traces(
    items: Sequence[Any],
    *,
    window_label: str = "rolling",
) -> Dict[str, Any]:
    """
    Aggregate a sequence of traces or v3 report dicts into a **system_bias_profile**.

    Skips entries that do not contain a usable trace unless the whole window is empty
    (then returns zeros with episode_count 0).
    """
    traces: List[Dict[str, Any]] = []
    for raw in items:
        t = _normalize_trace_item(raw)
        if t is not None:
            traces.append(t)

    n = len(traces)
    if n == 0:
        return {
            "window_label": window_label,
            "episode_count": 0,
            "system_bias_profile": _empty_bias_profile(),
        }

    causes: Dict[str, int] = {}
    conf_vals: List[float] = []
    var_vals: List[float] = []
    mean_j_vals: List[float] = []
    guests_on = 0
    collapse_ct = 0
    issue_eff = 0
    high_eff = 0

    for tr in traces:
        pc = str(tr.get("decision_primary_cause") or "UNKNOWN")
        causes[pc] = causes.get(pc, 0) + 1

        if tr.get("guest_generation_effective"):
            guests_on += 1
        if tr.get("anchor_collapse_gate_fired"):
            collapse_ct += 1
        if tr.get("issue_axis_effective"):
            issue_eff += 1
        if tr.get("high_signal_axis_effective"):
            high_eff += 1

        gc = tr.get("guest_generation_confidence")
        if isinstance(gc, (int, float)):
            conf_vals.append(float(gc))

        sp = tr.get("anchor_stability_profile")
        if isinstance(sp, dict):
            vj = sp.get("variance_jaccard")
            if isinstance(vj, (int, float)):
                var_vals.append(float(vj))
            mj = sp.get("mean_jaccard")
            if isinstance(mj, (int, float)):
                mean_j_vals.append(float(mj))

    def _mean(xs: List[float]) -> Optional[float]:
        if not xs:
            return None
        return round(sum(xs) / len(xs), 4)

    def _pct(num: int) -> float:
        return round(100.0 * float(num) / float(n), 2)

    cause_pct = {k: round(100.0 * v / n, 2) for k, v in sorted(causes.items())}

    # Explicit “who drove the label” slices (primary_cause is single attribution).
    h_dom = causes.get("HIGH_SIGNAL_DOMINANT", 0)
    i_dom = causes.get("ISSUE_AXIS_DOMINANT", 0)
    multi = causes.get("MULTI_AXIS_CONVERGENCE", 0)

    profile: Dict[str, Any] = {
        "fraction_guest_generation_on": round(guests_on / n, 4),
        "pct_guest_generation_on": _pct(guests_on),
        "pct_driven_high_signal_primary": _pct(h_dom),
        "pct_driven_issue_primary": _pct(i_dom),
        "pct_driven_multi_axis_primary": _pct(multi),
        "fraction_primary_cause": {k: round(v / n, 4) for k, v in sorted(causes.items())},
        "pct_primary_cause": cause_pct,
        "pct_issue_axis_effective": _pct(issue_eff),
        "pct_high_signal_axis_effective": _pct(high_eff),
        "pct_collapse_suppressions": _pct(collapse_ct),
        "count_collapse_suppressions": collapse_ct,
        "mean_guest_generation_confidence": _mean(conf_vals),
        "mean_anchor_variance_jaccard": _mean(var_vals),
        "mean_anchor_mean_jaccard": _mean(mean_j_vals),
    }

    return {
        "window_label": window_label,
        "episode_count": n,
        "system_bias_profile": profile,
    }


def _empty_bias_profile() -> Dict[str, Any]:
    return {
        "fraction_guest_generation_on": 0.0,
        "pct_guest_generation_on": 0.0,
        "pct_driven_high_signal_primary": 0.0,
        "pct_driven_issue_primary": 0.0,
        "pct_driven_multi_axis_primary": 0.0,
        "fraction_primary_cause": {},
        "pct_primary_cause": {},
        "pct_issue_axis_effective": 0.0,
        "pct_high_signal_axis_effective": 0.0,
        "pct_collapse_suppressions": 0.0,
        "count_collapse_suppressions": 0,
        "mean_guest_generation_confidence": None,
        "mean_anchor_variance_jaccard": None,
        "mean_anchor_mean_jaccard": None,
    }
