# report_control_workflow/pipeline/assembly.py
"""Shipped JSON dict (pure assembly from a populated ControlReport)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from report_control_workflow.constants import DEFAULT_CLIP_SELECT_K
from report_control_workflow.core.models import ControlReport
from report_control_workflow.intelligence.clips import select_top_clips
from report_control_workflow.intelligence.contrarian import extract_contrarian_line
from report_control_workflow.intelligence.insight import extract_core_insight


def assemble_report(
    report: ControlReport,
    *,
    clip_select_k: int = DEFAULT_CLIP_SELECT_K,
    derive_clips_from_claims: bool = True,
    relationship_llm_fn: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    d = report.to_minimal_dict()
    if not (d.get("core_insight") or "").strip():
        d["core_insight"] = extract_core_insight(report.claims)
    if not (d.get("contrarian") or "").strip():
        d["contrarian"] = extract_contrarian_line(
            report.claims,
            report.thesis,
            relationship_llm_fn=relationship_llm_fn,
        )
    if derive_clips_from_claims:
        d["clips"] = select_top_clips(report.claims, k=clip_select_k)
    return d
