"""User-facing library benchmark copy — no fake percentile claims."""

from __future__ import annotations

from backend.services.library_benchmarks import (
    LibraryBenchmarks,
    benchmark_questions,
    library_comparison_bullets,
)


def test_benchmark_questions_never_shows_percent_of_cohort():
    lib = LibraryBenchmarks(
        n_measured=45,
        hook_seconds=[10.0] * 45,
        intro_seconds=[20.0] * 45,
        question_counts=[12] * 44 + [3],
        speaking_turns=[8] * 45,
        guest_ratios=[0.5] * 45,
        topic_shifts=[1] * 45,
    )
    label = benchmark_questions(3, lib)
    assert label
    assert "% of measured" not in label.lower()

    bullets = library_comparison_bullets(
        hook=6.0,
        intro=6.0,
        questions=3,
        turns=8,
        ratio=0.5,
        lib=lib,
        narrative_led=True,
    )
    joined = " ".join(bullets).lower()
    assert "% of measured" not in joined
    assert len(bullets) <= 2
