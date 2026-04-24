# report_control_workflow/runtime/decisions.py
"""Ship / revise decisions from score + errors."""

from __future__ import annotations

from typing import Sequence

from report_control_workflow.constants import DEFAULT_SHIP_SCORE_OK, DEFAULT_SHIP_SCORE_STRONG


def decide_report_action(score: float) -> str:
    if score >= DEFAULT_SHIP_SCORE_STRONG:
        return "publish"
    if score >= DEFAULT_SHIP_SCORE_OK:
        return "light_edit"
    if score >= 0.5:
        return "needs_revision"
    return "reprocess"


def decide_report_action_v2(score: float, errors: Sequence[str]) -> str:
    if score >= 0.85 and not errors:
        return "publish"
    if score >= 0.75:
        return "publish_with_minor_edits"
    if score >= 0.6:
        return "revise_claims"
    return "reprocess_transcript"
