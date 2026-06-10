"""Narrative engine v2 — producer summary, not per-question loops."""

from unittest.mock import patch

import pytest

from backend.services.narrative_timeline_service import (
    build_narrative_engine_map,
    clear_narrative_cache,
)


@pytest.fixture(autouse=True)
def _isolated_narrative_engine():
    """No cross-test cache leakage; no live Gemini calls from ambient env keys."""
    clear_narrative_cache()
    yield
    clear_narrative_cache()

SAMPLE = """
Host: Welcome. Why did this factory town collapse?
Host: Here's the setup. In 1987 the plant opened.
Host: But then jobs started leaving. What happened next?
Host: Partly it was automation — but not entirely.
Host: That's why the mayor tried a new plan.
Host: Except there was another problem. Who pays for the cleanup?
Host: So in the end the town had to choose between two bad options.
Host: And that's the story.
""".strip()

VACATION_TRANSCRIPT = """
Host: Why do Americans take less vacation?
Host: What is wrong with us?
Host: Why don't we use our vacation days?
Host: Why don't Americans prioritize vacations?
Host: A traveler notices Europeans appear to work less and vacation more.
Host: Later we discuss labor history, tax incentives, workplace norms, and the Protestant work ethic.
Host: So that is the pattern — Americans defer time off in ways Europeans often do not.
""".strip()

SEMANTIC_VACATION_RESPONSE = {
    "story_being_told": "A contrast between US and European vacation habits becomes a cultural and institutional explanation.",
    "primary_question": "Why do Americans take less vacation than workers in other wealthy countries?",
    "curiosity_driver": "Why Americans leave vacation days unused",
    "narrative_promise": "This episode will explain why American work culture produces unusually low vacation usage.",
    "payoff": {
        "status": "mostly_delivered",
        "confidence": "high",
        "confidence_score": 0.84,
        "rationale": "Labor history, tax incentives, workplace norms, and Protestant work ethic address the central curiosity without restating every surface question.",
    },
    "supporting_threads": [
        {
            "thread_label": "Historical roots of work culture",
            "status": "delivered",
            "evidence_summary": "Labor history frames how time off became optional.",
        },
        {
            "thread_label": "Protestant work ethic influence",
            "status": "delivered",
            "evidence_summary": "Cultural norms treat vacation as deferrable.",
        },
        {
            "thread_label": "Economic incentives and taxation",
            "status": "delivered",
            "evidence_summary": "Tax and workplace incentives shape usage.",
        },
        {
            "thread_label": "Individual worker psychology",
            "status": "partially_delivered",
            "evidence_summary": "Mentioned but not fully explored.",
        },
    ],
    "conclusions_reached": [
        "American work culture systematically discourages taking full vacation.",
    ],
    "remaining_open_questions": [
        "Whether cultural attitudes can realistically change.",
    ],
    "timeline_beats": [
        {
            "time_seconds": 0,
            "event_type": "promise_established",
            "label": "Vacation culture contrast introduced",
            "detail": "European observation sets up the implied promise.",
        },
        {
            "time_seconds": 180,
            "event_type": "payoff",
            "label": "Institutional explanation lands",
            "detail": "Labor and cultural factors close the central thread.",
        },
    ],
}


@patch("backend.services.narrative_timeline_service.run_gemini_json", return_value=None)
def test_rule_based_does_not_inflate_open_loops(_mock):
    m = build_narrative_engine_map(SAMPLE)
    assert m.open_loops == []
    assert m.engine_version == "v2"


@patch("backend.services.narrative_timeline_service.run_gemini_json", return_value=None)
def test_rule_based_has_single_primary_cue_not_many_loops(_mock):
    m = build_narrative_engine_map(SAMPLE)
    d = m.to_dict()
    assert d.get("narrative_summary")
    assert d["narrative_summary"]["primary_question"]
    assert len(d["open_loops"]) == 0


@patch("backend.services.narrative_timeline_service.run_gemini_json", return_value=None)
def test_engine_notes_are_local_not_trend(_mock):
    m = build_narrative_engine_map(SAMPLE)
    blob = " ".join(m.engine_notes).lower()
    assert "primary question" in blob or "semantic" in blob
    assert "category" not in blob
    assert "usually" not in blob
    assert "average" not in blob


@patch("backend.services.narrative_timeline_service.run_gemini_json", return_value=None)
def test_false_resolution_detected(_mock):
    text = """
Host: Why did it fail?
Host: So in the end it was simple. That's why.
Host: But wait — what about the workers?
""".strip()
    m = build_narrative_engine_map(text)
    assert any(e.event_type == "false_resolution" for e in m.timeline)


@patch("backend.services.narrative_timeline_service.run_gemini_json", return_value=None)
def test_timeline_events_have_time_labels(_mock):
    m = build_narrative_engine_map(SAMPLE)
    d = m.to_dict()
    assert d["timeline"][0]["time_label"]
    assert ":" in d["timeline"][0]["time_label"]


@patch("backend.services.narrative_timeline_service.run_gemini_json")
def test_semantic_result_cached_per_transcript(mock_gemini):
    mock_gemini.return_value = SEMANTIC_VACATION_RESPONSE
    first = build_narrative_engine_map(VACATION_TRANSCRIPT)
    second = build_narrative_engine_map(VACATION_TRANSCRIPT)
    assert mock_gemini.call_count == 1
    assert first is second


@patch("backend.services.narrative_timeline_service.run_gemini_json", return_value=None)
def test_semantic_failure_not_retried_within_ttl(mock_gemini):
    build_narrative_engine_map(VACATION_TRANSCRIPT)
    build_narrative_engine_map(VACATION_TRANSCRIPT)
    assert mock_gemini.call_count == 1


@patch("backend.services.narrative_timeline_service.run_gemini_json")
def test_allow_semantic_false_skips_gemini(mock_gemini):
    m = build_narrative_engine_map(VACATION_TRANSCRIPT, allow_semantic=False)
    mock_gemini.assert_not_called()
    assert m.analysis_mode == "rule_based"


@patch("backend.services.narrative_timeline_service.run_gemini_json")
def test_semantic_v2_merges_surface_questions(mock_gemini):
    mock_gemini.return_value = SEMANTIC_VACATION_RESPONSE
    m = build_narrative_engine_map(VACATION_TRANSCRIPT)
    d = m.to_dict()

    assert m.analysis_mode == "semantic"
    assert m.open_loops == []
    summary = d["narrative_summary"]
    assert "vacation" in summary["primary_question"].lower()
    assert summary["payoff_label"] == "Mostly Delivered"
    assert summary["confidence"] == "High"
    assert len(summary["supporting_threads"]) == 4
    assert len(summary["remaining_open_questions"]) == 1


@patch("backend.services.narrative_timeline_service.run_gemini_json")
def test_semantic_v2_producer_summary_fields(mock_gemini):
    mock_gemini.return_value = SEMANTIC_VACATION_RESPONSE
    d = build_narrative_engine_map(VACATION_TRANSCRIPT).to_dict()

    summary = d["narrative_summary"]
    assert summary["narrative_promise"]
    assert summary["story_being_told"]
    assert summary["supporting_threads"][0]["status_label"] == "Delivered"
    assert any("Primary question" in note for note in d["engine_notes"])
    assert d["engine_version"] == "v2"
