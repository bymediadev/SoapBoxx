"""Forbidden-language guard must not block transcript evidence in reports."""

from __future__ import annotations

from backend.services.coaching_report_service import (
    CoachingReport,
    MetricRow,
    _assert_no_forbidden,
)


def test_transcript_quote_in_timeline_detail_allowed():
    report = CoachingReport(
        structural_identity=["Diary / explainer narration"],
        narrative_engine={
            "engine_notes": ["Open loops tracked from questions in transcript."],
            "timeline": [
                {
                    "label": "Sub-question introduced",
                    "detail": (
                        "products that we didn't help make? Sort of a serious question. "
                        "That's a good, it"
                    ),
                }
            ],
            "open_loops": [
                {
                    "snippet": "That's a good question about the economy",
                    "status": "open",
                }
            ],
        },
        producer_notes={
            "bullets": ["Segment rhythm is steady in the middle third."],
            "metrics": [],
            "edit_flags": [],
        },
    )
    report.episode_structure = [
        MetricRow("Hook", "3s", coaching="Short opening before context.")
    ]
    _assert_no_forbidden(report)


def test_coaching_verdict_language_still_blocked():
    report = CoachingReport(
        structural_identity=["This is a good episode for the feed."],
    )
    try:
        _assert_no_forbidden(report)
        raised = False
    except RuntimeError:
        raised = True
    assert raised
