"""Structural variance vs same-show catalog."""

from __future__ import annotations

from backend.models import EpisodeFeatures
from backend.services.library_benchmarks import LibraryBenchmarks
from backend.services.show_variance_service import structural_variance_bullets


def _show(**kwargs) -> LibraryBenchmarks:
    defaults = dict(
        n_measured=3,
        hook_seconds=[20.0, 40.0, 50.0],
        intro_seconds=[10.0, 20.0, 30.0],
        question_counts=[10, 12, 14],
        speaking_turns=[15, 18, 20],
        guest_ratios=[0.5, 0.52, 0.55],
        topic_shifts=[1, 2, 2],
    )
    defaults.update(kwargs)
    return LibraryBenchmarks(**defaults)


def test_shortest_hook_vs_show():
    f = EpisodeFeatures(
        episode_id=99,
        hook_length_seconds=18.0,
        intro_length_seconds=10.0,
        question_count=3,
        speaking_turns=8,
        host_guest_ratio=0.54,
        topic_shift_count=0,
    )
    bullets = structural_variance_bullets(f, _show(), podcast_name="Planet Money")
    assert any("shortest" in b.lower() for b in bullets)


def test_insufficient_show_episodes():
    f = EpisodeFeatures(episode_id=1, hook_length_seconds=30.0)
    bullets = structural_variance_bullets(
        f, _show(n_measured=1, hook_seconds=[40.0]), podcast_name="Planet Money"
    )
    assert len(bullets) == 1
    assert "measure more" in bullets[0].lower()
