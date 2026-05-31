"""Transition marker labeling in coaching reports."""

from backend.models import EpisodeFeatures
from backend.services.coaching_report_service import build_coaching_report
from backend.services.library_benchmarks import LibraryBenchmarks


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


def test_zero_markers_use_precise_framing():
    f = EpisodeFeatures(
        episode_id=1,
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
        topic_shift_count=0,
    )
    report = build_coaching_report(_FakeSession(), f, library=_library())
    row = next(r for r in report.conversation_dynamics if r.metric == "Transition markers")
    assert row.value == "None detected"
    assert row.benchmark and "inferred" in row.benchmark.lower()
    assert report.topic_shift_note and "transition markers" in report.topic_shift_note.lower()
