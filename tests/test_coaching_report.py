"""Coaching report — benchmarks, bullets, forbidden language."""

from __future__ import annotations

import pytest

from backend.models import EpisodeFeatures
from backend.services.coaching_report_service import (
    build_coaching_report,
    synthesis_insight_text,
)
from backend.services.library_benchmarks import LibraryBenchmarks
FORBIDDEN = ("good", "bad", "score", "rank", "best", "weak", "engaging")


def _features(**kwargs) -> EpisodeFeatures:
    row = EpisodeFeatures(episode_id=1)
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def _library(**kwargs) -> LibraryBenchmarks:
    defaults = dict(
        n_measured=5,
        hook_seconds=[20.0, 40.0, 60.0, 80.0, 100.0],
        intro_seconds=[10.0, 30.0, 50.0, 70.0, 90.0],
        question_counts=[3, 5, 10, 15, 20],
        speaking_turns=[4, 8, 12, 16, 20],
        guest_ratios=[0.4, 0.45, 0.5, 0.55, 0.6],
        topic_shifts=[0, 0, 1, 2, 3],
    )
    defaults.update(kwargs)
    return LibraryBenchmarks(**defaults)


class _FakeSession:
    """Minimal stub — benchmarks passed explicitly."""

    pass


def test_narrative_episode_coaching_bullets():
    f = _features(
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
        host_guest_ratio=0.542,
        topic_shift_count=0,
        cta_present=True,
    )
    lib = _library()
    report = build_coaching_report(_FakeSession(), f, library=lib)
    text = " ".join(report.what_this_means).lower()
    assert "only 3 questions" in text or "3 questions" in text
    assert "8 speaking turns" in text or "only 8" in text
    assert report.topic_shift_note
    assert "continuous arc" in report.topic_shift_note.lower() or "zero" in report.topic_shift_note.lower()
    assert report.similar_to
    assert report.episode_structure[0].benchmark


def test_no_forbidden_language_in_report():
    cases = [
        _features(hook_length_seconds=100, intro_length_seconds=140, question_count=2),
        _features(hook_length_seconds=10, intro_length_seconds=15, question_count=20),
        _features(hook_length_seconds=32, intro_length_seconds=6, question_count=3, speaking_turns=8),
    ]
    lib = _library()
    for f in cases:
        report = build_coaching_report(_FakeSession(), f, library=lib)
        blob = synthesis_insight_text(report).lower()
        assert not any(w in blob for w in FORBIDDEN)

