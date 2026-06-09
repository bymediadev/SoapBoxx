"""Narrative engine map — semantic threads and within-episode tension timeline."""

from unittest.mock import patch

from backend.services.narrative_timeline_service import build_narrative_engine_map

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
Host: A traveler notices Europeans appear to work less and vacation more.
Host: Later we discuss labor history, tax incentives, workplace norms, and the Protestant work ethic.
Host: So that is the pattern — Americans defer time off in ways Europeans often do not.
""".strip()

SEMANTIC_VACATION_RESPONSE = {
    "central_topic": "American vacation culture compared with European norms",
    "listener_curiosity": "Why Americans take significantly less vacation than peers in other wealthy countries",
    "narrative_promise": {
        "curiosity_created": "Europeans seem to vacation more while working less",
        "question_invited": "Why American work culture produces less vacation usage",
        "answer_promised": "The episode will explain structural and cultural reasons Americans defer time off",
    },
    "explanatory_threads": [
        {
            "thread_label": "Why American work culture produces less vacation usage than other wealthy countries",
            "status": "resolved",
            "evidence_summary": "Labor history, tax incentives, workplace norms, and Protestant work ethic explain the gap without restating every surface question.",
            "surfaced_phrases": [
                "Why do Americans take less vacation?",
                "Why don't we use our vacation days?",
                "Why are Europeans different?",
            ],
            "approx_open_seconds": 0,
            "approx_close_seconds": 240,
        }
    ],
    "satisfaction": {
        "verdict": "mostly_satisfied",
        "confidence": 0.82,
        "rationale": "The central curiosity is addressed through multiple indirect explanations even though no single line states the final answer verbatim.",
    },
    "editorial_summary": {
        "story_being_told": "An opening contrast between US and European vacation habits becomes a cultural and institutional explanation.",
        "curiosity_driver": "Why Americans leave vacation days unused",
        "explanations_that_landed": [
            "Workplace norms and Protestant work ethic frame time off as optional",
        ],
        "questions_still_open": [],
        "listener_payoff_assessment": "A reasonable listener would likely feel the main curiosity was answered.",
    },
    "timeline_beats": [
        {
            "time_seconds": 0,
            "event_type": "promise_established",
            "label": "Vacation culture contrast introduced",
            "detail": "European observation sets up the implied promise.",
        },
        {
            "time_seconds": 180,
            "event_type": "resolution",
            "label": "Institutional explanation lands",
            "detail": "Labor and cultural factors close the central thread.",
        },
    ],
}


def test_timeline_has_primary_question():
    m = build_narrative_engine_map(SAMPLE)
    types = [e.event_type for e in m.timeline]
    assert "primary_question" in types
    assert m.open_loops
    assert m.open_loops[0].snippet


def test_engine_notes_are_local_not_trend():
    m = build_narrative_engine_map(SAMPLE)
    blob = " ".join(m.engine_notes).lower()
    assert (
        "primary question" in blob
        or "primary thread" in blob
        or "main-thread" in blob
        or "main thread" in blob
    )
    assert "category" not in blob
    assert "usually" not in blob
    assert "average" not in blob


def test_false_resolution_detected():
    text = """
Host: Why did it fail?
Host: So in the end it was simple. That's why.
Host: But wait — what about the workers?
""".strip()
    m = build_narrative_engine_map(text)
    assert any(e.event_type == "false_resolution" for e in m.timeline)


def test_timeline_events_have_time_labels():
    m = build_narrative_engine_map(SAMPLE)
    d = m.to_dict()
    assert d["timeline"][0]["time_label"]
    assert ":" in d["timeline"][0]["time_label"]


@patch("backend.services.narrative_timeline_service.run_gemini_json")
def test_semantic_analysis_merges_surface_questions(mock_gemini):
    mock_gemini.return_value = SEMANTIC_VACATION_RESPONSE
    m = build_narrative_engine_map(VACATION_TRANSCRIPT)
    d = m.to_dict()

    assert m.analysis_mode == "semantic"
    assert len(m.open_loops) == 1
    assert len(d.get("explanatory_threads") or []) == 1
    assert "American work culture" in m.open_loops[0].snippet
    assert d["satisfaction"]["verdict"] == "mostly_satisfied"
    assert d["narrative_promise"]["answer_promised"]


@patch("backend.services.narrative_timeline_service.run_gemini_json")
def test_semantic_editorial_fields_in_payload(mock_gemini):
    mock_gemini.return_value = SEMANTIC_VACATION_RESPONSE
    d = build_narrative_engine_map(VACATION_TRANSCRIPT).to_dict()

    assert d["central_topic"]
    assert d["listener_curiosity"]
    assert d["editorial_summary"]["story_being_told"]
    assert any("Curiosity payoff" in note for note in d["engine_notes"])
