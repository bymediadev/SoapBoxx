"""Coaching report — benchmarks, bullets, forbidden language."""

from __future__ import annotations

import pytest

from backend.models import EpisodeFeatures
from backend.services.coaching_report_service import (
    build_coaching_report,
    synthesis_insight_text,
)
from backend.services.library_benchmarks import (
    LibraryBenchmarks,
    benchmark_hook,
    benchmark_turns,
)
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
    listener = " ".join(report.listener_experience).lower()
    assert "sparingly" in listener or "narration" in listener
    assert "documentary" in listener or "storytelling" in listener
    assert "single narrative" in listener or "few" in listener
    assert report.topic_shift_note
    assert "detection" in report.topic_shift_note.lower() or "0" in report.topic_shift_note
    assert report.compared_with_library
    assert report.similar_to
    assert report.episode_structure[0].benchmark


def test_small_library_avoids_hard_percentiles():
    lib = _library(n_measured=4)
    label = benchmark_hook(32.0, lib)
    assert label is not None
    assert "%" not in label
    assert "current library" in label.lower()
    assert "4 measured" in label.lower()


def test_narrative_episode_has_editorial_tradeoffs():
    f = _features(
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
        host_guest_ratio=0.542,
        topic_shift_count=0,
        cta_present=True,
    )
    report = build_coaching_report(_FakeSession(), f, library=_library(n_measured=4))
    assert report.editorial_tradeoffs
    assert any("trade-off" in t.lower() for t in report.editorial_tradeoffs)


def test_turns_benchmark_at_library_high_end_not_more_than_most():
    lib = _library(speaking_turns=[2, 4, 6, 8])
    label = benchmark_turns(8, lib)
    assert label is not None
    assert "more turn-taking than most" not in label.lower()
    assert "high end" in label.lower() or "longer" in label.lower()


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

