"""
Orchestration safety: retry budgets and ``retry_blocked`` (no scoring logic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

Stage = Literal["extraction", "grounding", "transport"]


@dataclass
class RetryBudget:
    extraction: int = 2
    grounding: int = 1
    transport: int = 3


@dataclass
class RetryBudgetTracker:
    """Runtime budget; call :meth:`reset` between top-level runs."""

    budget: RetryBudget = field(default_factory=RetryBudget)
    _remaining: Dict[str, int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._remaining = {
            "extraction": max(0, int(self.budget.extraction)),
            "grounding": max(0, int(self.budget.grounding)),
            "transport": max(0, int(self.budget.transport)),
        }

    def can_retry(self, stage: Stage) -> bool:
        return self._remaining.get(stage, 0) > 0

    def decrement(self, stage: Stage) -> bool:
        if not self.can_retry(stage):
            return False
        self._remaining[stage] = self._remaining.get(stage, 0) - 1
        return True


def compute_retry_blocked(
    decision: Dict[str, Any],
    *,
    budget: Optional[RetryBudgetTracker] = None,
) -> bool:
    """
    When no retry is requested, orchestration is done → ``retry_blocked`` is True.

    When a retry *is* requested and a :class:`RetryBudgetTracker` is supplied, returns
    True if the applicable stage(s) cannot be retried within budget (no-op decision).
    """
    q = bool(decision.get("quality_should_retry"))
    t = bool(decision.get("transport_should_retry"))
    tier = str(decision.get("tier") or "").strip().lower()

    if not q and not t:
        return True

    if budget is None:
        return False

    blocked = False
    if t and not budget.can_retry("transport"):
        blocked = True
    if q:
        if tier == "retry_extraction":
            if not budget.can_retry("extraction"):
                blocked = True
        elif tier in ("retry_grounding", "low_confidence"):
            if not budget.can_retry("grounding"):
                blocked = True
        else:
            if not budget.can_retry("extraction") and not budget.can_retry("grounding"):
                blocked = True
    return blocked
