"""Rule-based A/B/C tier from metrics vs category benchmarks (not ML)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

MetricDict = Dict[str, Any]
BenchmarkDict = Dict[str, Dict[str, float]]


def _cmp_lower_better(value: float, bench: Dict[str, float]) -> Tuple[int, str]:
    """Score -1 bad, 0 neutral, +1 good for metrics where lower is better."""
    avg = bench.get("avg") or 0
    p90 = bench.get("p90") or avg
    if avg <= 0 and value <= 0:
        return 0, ""
    if value <= avg:
        return 1, f"At or below category avg ({value:.0f} vs avg {avg:.0f})"
    if value <= p90:
        return 0, f"Above avg but within p90 ({value:.0f} vs avg {avg:.0f})"
    return -1, f"Slower/weaker than category p90 ({value:.0f} vs p90 {p90:.0f})"


def _cmp_higher_better(value: float, bench: Dict[str, float]) -> Tuple[int, str]:
    avg = bench.get("avg") or 0
    p10 = bench.get("p10") or avg
    if value >= avg and avg > 0:
        return 1, f"At or above category avg ({value:.0f} vs avg {avg:.0f})"
    if value >= p10:
        return 0, f"Below avg but above p10 ({value:.0f} vs avg {avg:.0f})"
    return -1, f"Below category p10 ({value:.0f} vs p10 {p10:.0f})"


def predict_tier(
    metrics: MetricDict,
    benchmarks: BenchmarkDict,
) -> Dict[str, Any]:
    """
    Return ``{tier, confidence, reasoning}`` with tier in A/B/C.
    """
    scores: List[int] = []
    reasons: List[str] = []

    hook = float(metrics.get("hook_time_seconds") or 0)
    b_hook = benchmarks.get("hook_time_seconds") or {}
    s, r = _cmp_lower_better(hook, b_hook)
    scores.append(s * 2)  # hook weighted
    if r:
        reasons.append(f"Hook time: {r}")

    follow = int(metrics.get("followup_question_count") or 0)
    b_follow = benchmarks.get("followup_question_count") or {}
    s, r = _cmp_higher_better(float(follow), b_follow)
    scores.append(s * 2)
    if r:
        reasons.append(f"Follow-ups: {r}")

    guest = float(metrics.get("guest_talk_percentage") or 0)
    host = float(metrics.get("host_talk_percentage") or 0)
    balance = abs(guest - host)
    if balance <= 15:
        scores.append(1)
        reasons.append("Talk balance: guest/host within 15 pts (good interview balance)")
    elif balance <= 30:
        scores.append(0)
        reasons.append("Talk balance: moderate skew between guest and host")
    else:
        scores.append(-1)
        reasons.append("Talk balance: heavy host or guest dominance")

    questions = int(metrics.get("question_count") or 0)
    b_q = benchmarks.get("question_count") or {}
    s, r = _cmp_higher_better(float(questions), b_q)
    scores.append(s)
    if r:
        reasons.append(f"Questions: {r}")

    if metrics.get("cta_present"):
        scores.append(1)
        reasons.append("CTA present")
    else:
        scores.append(0)
        reasons.append("No clear CTA in transcript")

    total = sum(scores)
    max_possible = 8
    normalized = (total + max_possible) / (2 * max_possible)

    if total >= 4:
        tier = "A"
    elif total >= 1:
        tier = "B"
    else:
        tier = "C"

    confidence = round(min(0.95, max(0.35, 0.45 + 0.5 * abs(normalized - 0.5))), 2)

    if not reasons:
        reasons.append("Insufficient benchmark history; tier from heuristics only")

    return {
        "tier": tier,
        "confidence": confidence,
        "reasoning": reasons[:6],
    }
