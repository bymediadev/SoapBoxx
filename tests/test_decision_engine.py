"""Sanity tests for deterministic product decision tiers."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from decision_engine import (  # noqa: E402
    DecisionConfig,
    DecisionTier,
    ProductLimitedReason,
    decision_effective_should_retry,
    decision_result_to_dict,
    decision_should_retry_any,
    evaluate_decision,
    retry_routing_hint,
    validate_limited_reason_consistency,
)


def test_degraded_preserves_score_tier_with_transport_overlay():
    """Option B: high scores stay HIGHLIGHT; degraded adds flag + message, not system_limited tier."""
    d = evaluate_decision(0.9, 0.9, 0.8, export_status="degraded")
    assert d.tier == DecisionTier.HIGHLIGHT
    assert d.transport_degraded is True
    assert d.quality_should_retry is False
    assert d.transport_should_retry is True
    assert decision_effective_should_retry(d) is True
    assert decision_should_retry_any(d) == decision_effective_should_retry(d)
    assert "Pipeline/transport degraded" in d.message


def test_degraded_overlays_on_weak_scores_too():
    d = evaluate_decision(0.2, 0.0, 0.0, export_status="degraded")
    assert d.tier == DecisionTier.REJECT_INPUT
    assert d.transport_degraded is True
    assert d.quality_should_retry is False
    assert d.transport_should_retry is True


def test_degraded_plus_quality_retry_both_flags():
    d = evaluate_decision(0.5, 0.2, 0.6, export_status="degraded")
    assert d.tier == DecisionTier.RETRY_EXTRACTION
    assert d.quality_should_retry is True
    assert d.transport_should_retry is True
    assert retry_routing_hint(d) == "quality_first"


def test_serialized_decision_retry_fields_and_legacy_alias():
    d = evaluate_decision(0.9, 0.9, 0.8, export_status="degraded")
    payload = decision_result_to_dict(d, export_status="degraded")
    assert payload["should_retry_any"] is True
    assert payload["should_retry"] == payload["should_retry_any"]
    assert payload["trace"]["retry_routing_hint"] == "transport_only"
    assert payload.get("system_version")


def test_validate_limited_reason_consistency_priority_input_over_system():
    d = {
        "tier": "reject_input",
        "limited_reason": "input",
        "transport_degraded": True,
        "trace": {"transport_degraded": True},
    }
    assert validate_limited_reason_consistency(limited_reason="system", decision=d) == "input"


def test_sanity_long_but_useless_is_reject_input():
    d = evaluate_decision(0.2, 0.0, 0.0, export_status="ok")
    assert d.tier == DecisionTier.REJECT_INPUT
    assert d.product_limited_reason == ProductLimitedReason.INPUT
    assert d.transport_degraded is False


def test_sanity_extraction_failure_retries():
    d = evaluate_decision(0.5, 0.2, 0.6, export_status="ok")
    assert d.tier == DecisionTier.RETRY_EXTRACTION
    assert d.quality_should_retry is True
    assert d.transport_should_retry is False


def test_sanity_grounding_hard_floor():
    d = evaluate_decision(0.6, 0.6, 0.2, export_status="ok")
    assert d.tier == DecisionTier.RETRY_GROUNDING


def test_sanity_weak_grounding_soft_band():
    d = evaluate_decision(0.6, 0.6, 0.45, export_status="ok")
    assert d.tier == DecisionTier.LOW_CONFIDENCE


def test_sanity_accept_moderate():
    d = evaluate_decision(0.6, 0.6, 0.55, export_status="ok")
    assert d.tier == DecisionTier.ACCEPT_MODERATE


def test_sanity_accept_strong():
    d = evaluate_decision(0.75, 0.7, 0.7, export_status="ok")
    assert d.tier == DecisionTier.ACCEPT_STRONG


def test_sanity_highlight():
    d = evaluate_decision(0.9, 0.9, 0.8, export_status="ok")
    assert d.tier == DecisionTier.HIGHLIGHT
    assert d.highlight is True


def test_explicit_config_overrides_defaults():
    cfg = DecisionConfig(input_threshold=0.5, extraction_min=0.9)
    d = evaluate_decision(0.4, 0.95, 0.95, export_status="ok", config=cfg)
    assert d.tier == DecisionTier.REJECT_INPUT
