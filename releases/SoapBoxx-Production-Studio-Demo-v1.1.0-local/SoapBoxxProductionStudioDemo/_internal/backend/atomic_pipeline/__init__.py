# backend/atomic_pipeline/__init__.py
"""Atomic claim → verification → topic graph → insights → clips → guests → actions."""

from .pipeline import envelope_to_json, extract_atomic_claims, run_atomic_pipeline, verify_claims
from .schemas import (
    AtomicPipelineEnvelope,
    AudienceAction,
    Claim,
    Clip,
    GuestRecommendation,
    Insight,
    TopicGraph,
    Verification,
)

__all__ = [
    "AtomicPipelineEnvelope",
    "AudienceAction",
    "Claim",
    "Clip",
    "GuestRecommendation",
    "Insight",
    "TopicGraph",
    "Verification",
    "envelope_to_json",
    "extract_atomic_claims",
    "run_atomic_pipeline",
    "verify_claims",
]
