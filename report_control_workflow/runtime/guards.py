# report_control_workflow/runtime/guards.py
"""Optional final checks (thin wrappers over validation contracts)."""

from __future__ import annotations

from typing import Any, Dict, List

from report_control_workflow.pipeline.validation import validate_output_contract


def final_output_guard(data: Dict[str, Any]) -> List[str]:
    """Return contract issues (empty list if OK)."""
    return validate_output_contract(data)
