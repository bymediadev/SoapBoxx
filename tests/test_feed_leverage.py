"""Feed-anchored leverage points — non-ranking bands, observed catalog membership."""

from __future__ import annotations

from backend.models import EpisodeFeatures
from backend.services.feed_leverage_service import (
    build_feed_leverage_points,
    build_structural_identity,
)
from backend.services.library_benchmarks import LibraryBenchmarks

_FORBIDDEN_ORDINAL = (
    "upper band",
    "lower band",
    "mid band",
    "highest",
    "lowest",
    "align with",
    "aligns with",
    "if you",
    "will ",
    "better",
    "worse",
)


def _planet_money_row(episode_id: int, **kwargs) -> EpisodeFeatures:
    defaults = dict(
        hook_length_seconds=40.0,
        intro_length_seconds=20.0,
        question_count=12,
        speaking_turns=18,
        host_guest_ratio=0.52,
        topic_shift_count=1,
    )
    defaults.update(kwargs)
    return EpisodeFeatures(episode_id=episode_id, **defaults)


def test_leverage_uses_named_bands_not_ordinal_language():
    episode = _planet_money_row(
        99,
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
        topic_shift_count=0,
    )
    show_rows = [
        _planet_money_row(1, question_count=4, speaking_turns=9, intro_length_seconds=6.0),
        _planet_money_row(2, question_count=5, speaking_turns=10, intro_length_seconds=8.0),
        _planet_money_row(3, question_count=14, speaking_turns=20),
    ]
    show = LibraryBenchmarks(
        n_measured=3,
        hook_seconds=[20.0, 40.0, 50.0],
        intro_seconds=[6.0, 8.0, 30.0],
        question_counts=[4, 5, 14],
        speaking_turns=[9, 10, 20],
        guest_ratios=[0.5, 0.52, 0.55],
        topic_shifts=[0, 1, 2],
    )
    points = build_feed_leverage_points(
        episode, show, show_rows, feed_name="Planet Money"
    )
    assert len(points) <= 2
    blob = " ".join(points).lower()
    for word in _FORBIDDEN_ORDINAL:
        assert word not in blob
    assert "planet money" in blob
    assert "band" in blob
    assert "have been observed in" in blob


def test_leverage_observes_catalog_membership_not_alignment():
    episode = _planet_money_row(
        99,
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
        topic_shift_count=0,
    )
    show_rows = [
        _planet_money_row(1, question_count=4, speaking_turns=9, intro_length_seconds=6.0),
        _planet_money_row(2, question_count=5, speaking_turns=10, intro_length_seconds=8.0),
    ]
    show = LibraryBenchmarks(
        n_measured=2,
        hook_seconds=[20.0, 40.0],
        intro_seconds=[6.0, 8.0],
        question_counts=[4, 5],
        speaking_turns=[9, 10],
        guest_ratios=[0.5, 0.52],
        topic_shifts=[0, 1],
    )
    points = build_feed_leverage_points(
        episode, show, show_rows, feed_name="Planet Money"
    )
    assert points
    assert any("have been observed in" in p for p in points)
    assert not any("align with" in p.lower() for p in points)


def test_structural_identity_max_two_lines():
    episode = _planet_money_row(
        1,
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
    )
    playbook = {
        "form": "Narrative documentary (structural pattern)",
        "tagline": "Reporter walk-through with sparse Q&A.",
        "feels_like": "Like joining a reporter mid-walkthrough.",
    }
    lines = build_structural_identity(episode, "C", playbook=playbook)
    assert len(lines) <= 2
    assert "narrative documentary" in lines[0].lower()
