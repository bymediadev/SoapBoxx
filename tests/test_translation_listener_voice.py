"""Listener-lens translation templates (Amanda-derived copy rules)."""

from __future__ import annotations

import pytest

from backend.services.translation_service import (
    _FORBIDDEN,
    _template_from_features,
)
from backend.models import EpisodeFeatures

FORBIDDEN = ("good", "bad", "score", "rank", "best", "weak", "engaging")


def _features(**kwargs) -> EpisodeFeatures:
    row = EpisodeFeatures(episode_id=1)
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def test_long_opening_uses_template_a():
    f = _features(
        hook_length_seconds=95.0,
        intro_length_seconds=130.0,
        question_count=5,
        topic_shift_count=0,
        cta_present=False,
    )
    tid, text = _template_from_features(f)
    assert tid == "A"
    assert "listener" in text.lower()
    assert "opening" in text.lower() or "intro" in text.lower()


def test_question_led_uses_template_b():
    f = _features(
        hook_length_seconds=20.0,
        intro_length_seconds=25.0,
        question_count=15,
        topic_shift_count=1,
        cta_present=True,
    )
    tid, text = _template_from_features(f)
    assert tid == "B"
    assert "question" in text.lower()


def test_narrative_uses_template_c():
    f = _features(
        hook_length_seconds=15.0,
        intro_length_seconds=20.0,
        question_count=3,
        topic_shift_count=0,
        cta_present=False,
    )
    tid, text = _template_from_features(f)
    assert tid == "C"
    assert "narrative" in text.lower() or "storytelling" in text.lower()


def test_no_forbidden_language():
    cases = [
        _features(hook_length_seconds=100, intro_length_seconds=140, question_count=2),
        _features(hook_length_seconds=10, intro_length_seconds=15, question_count=20),
        _features(hook_length_seconds=10, intro_length_seconds=15, question_count=2),
    ]
    for f in cases:
        _, text = _template_from_features(f)
        lower = text.lower()
        assert not _FORBIDDEN.search(text)
        assert not any(w in lower for w in FORBIDDEN)
        assert "predict audience" in lower or "do not predict" in lower
