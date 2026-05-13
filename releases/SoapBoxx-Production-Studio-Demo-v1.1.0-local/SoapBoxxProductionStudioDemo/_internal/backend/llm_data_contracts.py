# backend/llm_data_contracts.py
"""
Lightweight **semantic** checks for LLM ``data`` payloads (Stage 4 — not transport).

Transport (envelope strict vs legacy) lives in ``episode_intelligence`` / ``soapboxx_v3_workflow``.
These helpers validate *meaning* of structured fields when enabled via env flags.
"""

from __future__ import annotations

from typing import Any, FrozenSet, Set, Tuple

# Subset of workflow_report keys LLM enrichment is allowed to fill.
WORKFLOW_LLM_KNOWN_KEYS: FrozenSet[str] = frozenset(
    (
        "highlights",
        "evidence_map",
        "follow_up_questions",
        "guests",
        "guest_recommendations",
        "segments",
        "analytics",
    )
)

# v2 network brief JSON (episode_intelligence.generate_episode_brief).
REQUIRED_BRIEF_V2_TOP_LEVEL: FrozenSet[str] = frozenset(
    (
        "episode_snapshot",
        "narrative",
        "claims",
        "evidence_gaps",
        "production_moves",
        "guests",
        "action_plan_7d",
    )
)

_EPISODE_SNAPSHOT_STRING_KEYS: Tuple[str, ...] = (
    "title",
    "creator",
    "genre",
    "primary_topic",
    "why_it_matters",
)


def validate_episode_snapshot(snap: Any) -> None:
    """
    Require a dict with non-empty string fields for core snapshot keys.

    Raises ``ValueError`` if the model drifted shape or returned placeholder-empty strings.
    """
    if not isinstance(snap, dict):
        raise ValueError("episode_snapshot must be an object")
    for key in _EPISODE_SNAPSHOT_STRING_KEYS:
        if key not in snap:
            raise ValueError(f"episode_snapshot missing key: {key!r}")
        v = snap.get(key)
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"episode_snapshot.{key} must be a non-empty string")


def validate_brief_v2_semantics(data: Any) -> None:
    """
    Minimal v2 brief contract: required top-level keys + :func:`validate_episode_snapshot`.

    Does not deep-validate every claim object — that stays in ``_normalize_brief`` / quality gates.
    """
    if not isinstance(data, dict):
        raise ValueError("brief root must be an object")
    missing = REQUIRED_BRIEF_V2_TOP_LEVEL - data.keys()
    if missing:
        raise ValueError(f"brief missing required keys: {sorted(missing)!r}")
    validate_episode_snapshot(data.get("episode_snapshot"))


def validate_workflow_data_has_known_keys(data: Any, *, expected: Set[str]) -> None:
    """
    Ensure ``data`` mentions at least one key from the workflow JSON surface area.

    Optional guard against random dicts that parse but are not workflow-shaped.
    """
    if not isinstance(data, dict):
        raise ValueError("workflow structured data must be an object")
    overlap = expected & data.keys()
    if not overlap:
        raise ValueError(
            f"workflow data has no recognized keys (expected at least one of: {sorted(expected)!r})"
        )
