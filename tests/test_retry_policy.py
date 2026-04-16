"""Retry budget and ``retry_blocked`` orchestration helpers."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from retry_policy import RetryBudget, RetryBudgetTracker, compute_retry_blocked  # noqa: E402


def test_retry_blocked_true_when_no_retry_requested():
    d = {
        "quality_should_retry": False,
        "transport_should_retry": False,
        "tier": "accept_strong",
    }
    assert compute_retry_blocked(d, budget=None) is True


def test_retry_blocked_false_when_retry_wanted_and_no_budget_tracker():
    d = {
        "quality_should_retry": True,
        "transport_should_retry": False,
        "tier": "retry_extraction",
    }
    assert compute_retry_blocked(d, budget=None) is False


def test_budget_blocks_extraction_retry():
    d = {
        "quality_should_retry": True,
        "transport_should_retry": False,
        "tier": "retry_extraction",
    }
    tr = RetryBudgetTracker(budget=RetryBudget(extraction=0, grounding=1, transport=3))
    assert compute_retry_blocked(d, budget=tr) is True


def test_tracker_decrement():
    tr = RetryBudgetTracker(budget=RetryBudget(extraction=1, grounding=1, transport=1))
    assert tr.can_retry("extraction")
    assert tr.decrement("extraction")
    assert not tr.can_retry("extraction")
