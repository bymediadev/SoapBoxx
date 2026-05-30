"""Listener-lens / coaching translation templates."""

from __future__ import annotations

import pytest

from backend.models import EpisodeFeatures
from backend.services.coaching_report_service import build_coaching_report, synthesis_insight_text
from backend.services.library_benchmarks import LibraryBenchmarks
from backend.services.translation_service import run_translation

FORBIDDEN = ("good", "bad", "score", "rank", "best", "weak", "engaging")


def _features(**kwargs) -> EpisodeFeatures:
    row = EpisodeFeatures(episode_id=1)
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def _library() -> LibraryBenchmarks:
    return LibraryBenchmarks(
        n_measured=4,
        hook_seconds=[30.0, 50.0, 70.0, 90.0],
        intro_seconds=[10.0, 30.0, 60.0, 120.0],
        question_counts=[3, 8, 14, 20],
        speaking_turns=[5, 10, 15, 20],
        guest_ratios=[0.45, 0.5, 0.52, 0.55],
        topic_shifts=[0, 1, 1, 2],
    )


class _FakeSession:
    pass


def _template_id(f: EpisodeFeatures) -> str:
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    if intro >= 120 or hook >= 90:
        return "A"
    if questions >= 12:
        return "B"
    return "C"


def test_long_opening_uses_template_a():
    f = _features(
        hook_length_seconds=95.0,
        intro_length_seconds=130.0,
        question_count=5,
        topic_shift_count=0,
        cta_present=False,
    )
    assert _template_id(f) == "A"
    report = build_coaching_report(_FakeSession(), f, library=_library())
    blob = " ".join(report.listener_experience).lower()
    assert "opening" in blob or "setup" in blob or "intro" in blob


def test_question_led_uses_template_b():
    f = _features(
        hook_length_seconds=20.0,
        intro_length_seconds=25.0,
        question_count=15,
        topic_shift_count=1,
        cta_present=True,
    )
    assert _template_id(f) == "B"
    report = build_coaching_report(_FakeSession(), f, library=_library())
    blob = " ".join(report.listener_experience).lower()
    assert "question" in blob


def test_narrative_uses_template_c():
    f = _features(
        hook_length_seconds=15.0,
        intro_length_seconds=20.0,
        question_count=3,
        topic_shift_count=0,
        cta_present=False,
    )
    assert _template_id(f) == "C"
    report = build_coaching_report(_FakeSession(), f, library=_library())
    assert report.template_playbook is not None
    assert report.template_playbook["form"] == "Narrative documentary"
    assert report.template_playbook["review_these"]
    blob = " ".join(
        report.listener_experience
        + report.template_playbook["how_its_built"]
        + report.template_playbook["review_these"]
    ).lower()
    assert "story" in blob or "documentary" in blob or "planet money" in blob


def test_no_forbidden_language():
    cases = [
        _features(hook_length_seconds=100, intro_length_seconds=140, question_count=2),
        _features(hook_length_seconds=10, intro_length_seconds=15, question_count=20),
        _features(hook_length_seconds=10, intro_length_seconds=15, question_count=2),
    ]
    lib = _library()
    for f in cases:
        report = build_coaching_report(_FakeSession(), f, library=lib)
        lower = synthesis_insight_text(report).lower()
        assert not any(w in lower for w in FORBIDDEN)
        assert "predict audience" in lower or "do not predict" in lower
