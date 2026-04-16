"""Tests for lead_audit_render (1-page outreach card, no LLM)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from lead_audit_render import pick_best_anchor_row, render_lead_audit_markdown  # noqa: E402


def test_lead_audit_insufficient_signal_uses_honest_copy():
    bundle = {
        "report_v3": {
            "episode_snapshot": {"title": "Ep X", "creator": "Show Y"},
            "clean_insights": ["Host energy is consistent."],
        },
        "workflow_report": {
            "metadata": {
                "export_status": "insufficient_signal",
                "export_blockers": ["grounded evidence rows 0 < 2 (workflow=0, report_v3=0)"],
            },
            "highlights": [{"insight": "Clear audio"}],
        },
        "meta": {},
    }
    md = render_lead_audit_markdown(bundle)
    assert "# Podcast audit — Show Y · Ep X" in md
    assert "limited-signal" in md.lower() or "directional" in md.lower()
    assert "Primary issue:" in md
    assert "grounded evidence" in md


def test_lead_audit_full_path_with_strict_export_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOAPBOXX_STRICT_EXPORT", "0")
    bundle = {
        "report_v3": {
            "episode_snapshot": {"title": "T", "creator": "C"},
            "claims": [{"text": "Claim one is long enough to count"}],
            "coach_report": {"episode_thesis": "One thesis line for the episode."},
            "clean_insights": ["A", "B", "C"],
            "evidence_mapping": [
                {"evidence": "Quote one is long enough to pass grounded checks here."},
                {"evidence": "Quote two is also long enough to pass grounded checks."},
            ],
        },
        "workflow_report": {
            "metadata": {},
            "segments": [{"id": "s1"}],
            "evidence_map": [
                {
                    "claim": "First claim is substantial text.",
                    "evidence": "Evidence quote one is substantial text here.",
                },
                {
                    "claim": "Second claim is substantial text.",
                    "evidence": "Evidence quote two is substantial text here.",
                },
            ],
            "highlights": [
                {"insight": "Working bullet one"},
                {"insight": "Working bullet two"},
                {"insight": "Working bullet three"},
            ],
        },
        "meta": {},
    }
    md = render_lead_audit_markdown(bundle)
    assert "# Podcast audit — C · T" in md
    assert "on the tape" in md.lower()
    assert "but it isn't developed into" in md.lower()
    assert ", so " in md
    assert "## What's working" in md
    assert "Working bullet one" in md
    assert "## If you fixed one thing first" in md


def test_lead_audit_omits_working_when_no_meaningful_bullets(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOAPBOXX_STRICT_EXPORT", "0")
    bundle = {
        "report_v3": {
            "episode_snapshot": {"title": "T2", "creator": "C2"},
            "claims": [{"text": "Claim one is long enough to count"}],
            "coach_report": {"episode_thesis": "One thesis line for the episode."},
            "clean_insights": [],
            "evidence_mapping": [
                {
                    "claim": "First claim is substantial text for the mapping row.",
                    "evidence": "Quote one is long enough to pass grounded checks here.",
                },
                {
                    "claim": "Second claim is substantial text for the mapping row.",
                    "evidence": "Quote two is also long enough to pass grounded checks here.",
                },
            ],
        },
        "workflow_report": {
            "metadata": {},
            "segments": [{"id": "s1"}],
            "highlights": [],
            "evidence_map": [
                {
                    "claim": "First claim is substantial text.",
                    "evidence": "Evidence quote one is substantial text here.",
                },
                {
                    "claim": "Second claim is substantial text.",
                    "evidence": "Evidence quote two is substantial text here.",
                },
            ],
        },
        "meta": {},
    }
    md = render_lead_audit_markdown(bundle)
    assert "## What's working" not in md
    assert "on the tape" in md.lower()


def test_anchor_prefers_contrast_over_longer_flat_quote():
    bundle = {
        "report_v3": {"evidence_mapping": []},
        "workflow_report": {
            "evidence_map": [
                {
                    "claim": "First substantial claim line for grounded export checks.",
                    "evidence": "A longer flat supporting quote with no pivot words in it here.",
                },
                {
                    "claim": "Second substantial claim line for grounded export checks.",
                    "evidence": "Shorter quote but it turns the corner with contrast right here.",
                },
            ]
        },
        "meta": {},
    }
    picked = pick_best_anchor_row(bundle)
    assert picked is not None
    assert "but it turns" in str(picked.get("evidence") or "")


def test_lead_audit_weak_inserts_warning_line():
    bundle = {
        "report_v3": {
            "episode_snapshot": {"title": "Weak Ep", "creator": "Weak Show"},
        },
        "workflow_report": {
            "metadata": {
                "export_status": "insufficient_signal",
                "export_blockers": ["grounded evidence rows 1 < 2 (workflow=1, report_v3=0)"],
                "structure_state": "WEAK",
                "structure_diagnostics": {
                    "evidence_rows": 1,
                    "segments": 0,
                    "structure_state": "WEAK",
                },
            },
            "evidence_map": [
                {
                    "claim": "A grounded enough claim line for evidence counting.",
                    "evidence": "A grounded enough quote that still leaves segment structure incomplete.",
                }
            ],
            "segments": [],
        },
        "meta": {},
    }
    md = render_lead_audit_markdown(bundle)
    warning = "⚠️ Weak structure: partial signal extracted, selection layer not fully activated."
    assert md.count(warning) == 1
