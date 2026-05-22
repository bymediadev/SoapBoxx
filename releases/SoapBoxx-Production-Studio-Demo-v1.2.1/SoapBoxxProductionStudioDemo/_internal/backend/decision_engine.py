"""
Deterministic product decisions from input-quality component scores.

Sits after :func:`evaluation_pipeline.compute_input_quality_components` and maps metrics
to UI/retry-friendly tiers. No ML — same inputs always yield the same decision.

**Precedence (explicit):** quality tiers are chosen from scores first. ``export_status ==
degraded`` does *not* replace that tier; it sets ``transport_degraded`` and adjusts messaging
(Option B — pipeline issues downgrade trust, not the score-derived label).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from .system_contracts import SYSTEM_VERSION
except ImportError:
    from system_contracts import SYSTEM_VERSION  # type: ignore


class DecisionTier(str, Enum):
    REJECT_INPUT = "reject_input"
    RETRY_EXTRACTION = "retry_extraction"
    RETRY_GROUNDING = "retry_grounding"
    LOW_CONFIDENCE = "low_confidence"
    ACCEPT_MODERATE = "accept_moderate"
    ACCEPT_STRONG = "accept_strong"
    HIGHLIGHT = "highlight"


class ProductLimitedReason(str, Enum):
    """Sub-reason inside ``decision`` (distinct from blame ``metadata.limited_reason``)."""

    INPUT = "input"
    EXTRACTION = "extraction"
    GROUNDING = "grounding"
    NONE = "none"


@dataclass
class DecisionResult:
    tier: DecisionTier
    product_limited_reason: ProductLimitedReason
    message: str
    quality_should_retry: bool = False
    """True when scores imply re-run extraction/grounding (policy layer may still skip)."""
    transport_should_retry: bool = False
    """True when pipeline/transport was degraded — orchestrator may retry enrichment only."""
    should_surface: bool = False
    highlight: bool = False
    transport_degraded: bool = False
    """True when export/transport was degraded — overlay; ``tier`` is still score-derived."""
    trace_path: str = ""
    """Stable id for which branch fired (debugging / analytics)."""


def decision_should_retry_any(d: DecisionResult) -> bool:
    """Explicit name for ``quality_should_retry or transport_should_retry`` (compatibility aggregate)."""
    return bool(d.quality_should_retry or d.transport_should_retry)


def decision_effective_should_retry(d: DecisionResult) -> bool:
    """Alias of :func:`decision_should_retry_any` (older name)."""
    return decision_should_retry_any(d)


def validate_limited_reason_consistency(
    *,
    limited_reason: Optional[str],
    decision: Dict[str, Any],
) -> str:
    """
    Map product signals into **exactly one** failure category for analytics / UI.

    Categories: ``input`` | ``extraction`` | ``grounding`` | ``system``.
    When multiple signals apply, precedence is:
    **input > extraction > grounding > system** (strongest product signal wins).
    """
    priority = {"input": 0, "extraction": 1, "grounding": 2, "system": 3}
    tier = str(decision.get("tier") or "").strip().lower()
    trace = decision.get("trace") if isinstance(decision.get("trace"), dict) else {}
    transport_degraded = bool(decision.get("transport_degraded") or trace.get("transport_degraded"))
    plr = str(decision.get("limited_reason") or "none").strip().lower()

    candidates: List[str] = []

    ml = str(limited_reason or "").strip().lower()
    if ml == "system":
        candidates.append("system")
    elif ml == "input":
        candidates.append("input")
    elif ml == "content":
        candidates.append("extraction")

    if transport_degraded:
        candidates.append("system")

    if plr == "input":
        candidates.append("input")
    elif plr == "extraction":
        candidates.append("extraction")
    elif plr == "grounding":
        candidates.append("grounding")

    if tier == "reject_input":
        candidates.append("input")
    elif tier == "retry_extraction":
        candidates.append("extraction")
    elif tier == "retry_grounding":
        candidates.append("grounding")
    elif tier == "low_confidence":
        candidates.append("grounding")

    if not candidates:
        return "extraction"

    return min(set(candidates), key=lambda c: priority[c])


def retry_routing_hint(d: DecisionResult) -> str:
    """
    Orchestration hint when both layers want a retry: **quality first** (semantic before infra).

    Returns one of: ``quality_first``, ``quality_only``, ``transport_only``, ``none``.
    """
    q = d.quality_should_retry
    t = d.transport_should_retry
    if q and t:
        return "quality_first"
    if q:
        return "quality_only"
    if t:
        return "transport_only"
    return "none"


@dataclass
class DecisionConfig:
    """Thresholds — prefer constructing via :func:`evaluation_pipeline.build_decision_config`."""

    input_threshold: float = 0.3
    extraction_min: float = 0.4
    grounding_soft_min: float = 0.5
    grounding_hard_min: float = 0.3
    moderate_threshold: float = 0.7
    strong_threshold: float = 0.85


def decision_result_to_dict(
    d: DecisionResult,
    *,
    export_status: str,
    metrics_ref: str = "input_quality_components",
) -> Dict[str, Any]:
    """Serialize decision; scores live only under ``metadata[metrics_ref]``, not duplicated here."""
    any_retry = decision_should_retry_any(d)
    out: Dict[str, Any] = {
        "tier": d.tier.value,
        "limited_reason": d.product_limited_reason.value,
        "system_version": SYSTEM_VERSION,
        "message": d.message,
        "quality_should_retry": d.quality_should_retry,
        "transport_should_retry": d.transport_should_retry,
        "should_retry_any": any_retry,
        # Legacy alias — prefer ``should_retry_any`` + split flags for new orchestrators.
        "should_retry": any_retry,
        "should_surface": d.should_surface,
        "highlight": d.highlight,
        "transport_degraded": d.transport_degraded,
        "metrics_ref": metrics_ref,
        "trace": {
            "path_taken": d.trace_path,
            "export_status": str(export_status or "").strip().lower() or "ok",
            "transport_degraded": d.transport_degraded,
            "precedence": "quality_tier_first_then_transport_overlay",
            "retry_routing_hint": retry_routing_hint(d),
        },
    }
    return out


def _evaluate_quality_path(
    iqs: float,
    extraction_success_score: float,
    grounding_density_score: float,
    config: DecisionConfig,
) -> Tuple[DecisionResult, str]:
    """Score-only policy path; no export/transport knowledge."""
    if iqs < config.input_threshold:
        return (
            DecisionResult(
                tier=DecisionTier.REJECT_INPUT,
                product_limited_reason=ProductLimitedReason.INPUT,
                message="Input too weak or insufficient for analysis.",
                quality_should_retry=False,
                should_surface=False,
                trace_path="reject_input_iqs_below_threshold",
            ),
            "reject_input_iqs_below_threshold",
        )

    if extraction_success_score < config.extraction_min:
        return (
            DecisionResult(
                tier=DecisionTier.RETRY_EXTRACTION,
                product_limited_reason=ProductLimitedReason.EXTRACTION,
                message="Failed to extract meaningful structure vs transcript length. Retry extraction.",
                quality_should_retry=True,
                should_surface=False,
                trace_path="retry_extraction_below_min",
            ),
            "retry_extraction_below_min",
        )

    if grounding_density_score < config.grounding_hard_min:
        return (
            DecisionResult(
                tier=DecisionTier.RETRY_GROUNDING,
                product_limited_reason=ProductLimitedReason.GROUNDING,
                message="Claims lack sufficient evidence grounding. Retry grounding.",
                quality_should_retry=True,
                should_surface=False,
                trace_path="retry_grounding_below_hard",
            ),
            "retry_grounding_below_hard",
        )

    if grounding_density_score < config.grounding_soft_min:
        return (
            DecisionResult(
                tier=DecisionTier.LOW_CONFIDENCE,
                product_limited_reason=ProductLimitedReason.GROUNDING,
                message="Insights extracted but weakly grounded.",
                quality_should_retry=False,
                should_surface=True,
                trace_path="low_confidence_grounding_soft_band",
            ),
            "low_confidence_grounding_soft_band",
        )

    if iqs < config.moderate_threshold:
        return (
            DecisionResult(
                tier=DecisionTier.ACCEPT_MODERATE,
                product_limited_reason=ProductLimitedReason.NONE,
                message="Moderate quality insights.",
                should_surface=True,
                trace_path="accept_moderate_iqs_band",
            ),
            "accept_moderate_iqs_band",
        )

    if iqs < config.strong_threshold:
        return (
            DecisionResult(
                tier=DecisionTier.ACCEPT_STRONG,
                product_limited_reason=ProductLimitedReason.NONE,
                message="Strong, reliable insights.",
                should_surface=True,
                trace_path="accept_strong_iqs_band",
            ),
            "accept_strong_iqs_band",
        )

    return (
        DecisionResult(
            tier=DecisionTier.HIGHLIGHT,
            product_limited_reason=ProductLimitedReason.NONE,
            message="High-signal output. Highlight-worthy.",
            should_surface=True,
            highlight=True,
            trace_path="highlight_top_band",
        ),
        "highlight_top_band",
    )


def _apply_transport_overlay(
    base: DecisionResult,
    path_key: str,
) -> DecisionResult:
    """Degraded transport: keep score-derived tier; flag + message; transport retry is separate from quality retry."""
    suffix = " — Pipeline/transport degraded: retry enrichment; treat output as lower confidence."
    return DecisionResult(
        tier=base.tier,
        product_limited_reason=base.product_limited_reason,
        message=(base.message or "").rstrip() + suffix,
        quality_should_retry=base.quality_should_retry,
        transport_should_retry=True,
        should_surface=base.should_surface or True,
        highlight=base.highlight,
        transport_degraded=True,
        trace_path=f"{path_key}+overlay_transport_degraded",
    )


def evaluate_decision(
    iqs: float,
    extraction_success_score: float,
    grounding_density_score: float,
    *,
    export_status: Optional[str] = None,
    config: Optional[DecisionConfig] = None,
) -> DecisionResult:
    """
    Convert metrics → tier. ``export_status == degraded`` overlays transport flags without
    discarding the score-derived ``tier`` (explicit Option B).
    """
    if config is None:
        config = DecisionConfig()

    base, path_key = _evaluate_quality_path(
        iqs, extraction_success_score, grounding_density_score, config
    )

    es = str(export_status or "").strip().lower()
    if es == "degraded":
        return _apply_transport_overlay(base, path_key)

    return base

