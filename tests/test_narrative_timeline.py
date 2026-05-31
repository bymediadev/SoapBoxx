"""Narrative engine map — within-episode tension timeline."""

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


def test_timeline_has_primary_question():
    m = build_narrative_engine_map(SAMPLE)
    types = [e.event_type for e in m.timeline]
    assert "primary_question" in types
    assert m.open_loops
    assert m.open_loops[0].snippet


def test_engine_notes_are_local_not_trend():
    m = build_narrative_engine_map(SAMPLE)
    blob = " ".join(m.engine_notes).lower()
    assert "primary question" in blob or "main thread" in blob
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
