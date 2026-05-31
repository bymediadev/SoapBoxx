"""Producer notes — editing pressure points (rule-based)."""

from __future__ import annotations

from backend.services.producer_notes_service import build_producer_notes

NARRATIVE_SAMPLE = """
Host: Welcome to Planet Money. Today we're in a factory town.
Host: Here's why this matters. The factory opened in 1987.
Host: But then the jobs started leaving. What happened next was a slow collapse.
Host: Years later the town had to reinvent itself. Meanwhile across town another plant closed.
Host: So to recap — we're talking about one company that carried the whole region.
Host: The problem was simple. No diversification. That's when the mayor stepped in.
Host: Remember, this is a story about dependency. Let me explain the scale.
Host: """ + ("They built widgets and shipped them worldwide. " * 40) + """
Host: Now the town is trying again. Here's why that might work.
""".strip()


def test_producer_notes_longest_segment():
    notes = build_producer_notes(NARRATIVE_SAMPLE, intro_seconds=6.0, topic_shift_count=0)
    assert notes.metrics
    longest = next(m for m in notes.metrics if m.metric == "Longest uninterrupted segment")
    assert "m" in longest.value or "s" in longest.value
    assert notes.bullets
    assert any("longest" in b.lower() for b in notes.bullets)


def test_rehooks_detected():
    notes = build_producer_notes(NARRATIVE_SAMPLE)
    rehooks = next(m for m in notes.metrics if m.metric == "Re-hooks")
    assert int(rehooks.value) >= 3


def test_edit_flags_non_judgmental():
    notes = build_producer_notes(NARRATIVE_SAMPLE)
    blob = " ".join(notes.edit_flags + notes.bullets).lower()
    assert "bad" not in blob
    assert "good" not in blob
    assert "score" not in blob
    if notes.edit_flags:
        assert any("potential" in f.lower() for f in notes.edit_flags)


def test_orientation_resets():
    notes = build_producer_notes(NARRATIVE_SAMPLE)
    orient = next(m for m in notes.metrics if m.metric == "Orientation resets")
    assert int(orient.value) >= 2
