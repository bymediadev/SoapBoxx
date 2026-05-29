"""How this episode differs from other measured episodes on the same show."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures
from backend.services.library_benchmarks import LibraryBenchmarks

MIN_SHOW_EPISODES = 2


def load_show_benchmarks(
    db: Session, podcast_id: int, *, exclude_episode_id: int
) -> LibraryBenchmarks:
    rows = (
        db.execute(
            select(EpisodeFeatures)
            .join(Episode, Episode.id == EpisodeFeatures.episode_id)
            .where(
                Episode.podcast_id == podcast_id,
                EpisodeFeatures.episode_id != exclude_episode_id,
            )
        )
        .scalars()
        .all()
    )
    return LibraryBenchmarks(
        n_measured=len(rows),
        hook_seconds=[float(r.hook_length_seconds or 0) for r in rows],
        intro_seconds=[float(r.intro_length_seconds or 0) for r in rows],
        question_counts=[int(r.question_count or 0) for r in rows],
        speaking_turns=[int(r.speaking_turns or 0) for r in rows],
        guest_ratios=[float(r.host_guest_ratio or 0.5) for r in rows],
        topic_shifts=[int(r.topic_shift_count or 0) for r in rows],
    )


def structural_variance_bullets(
    features: EpisodeFeatures,
    show: LibraryBenchmarks,
    *,
    podcast_name: Optional[str] = None,
) -> List[str]:
    """
    Observable differences vs the same show's measured catalog (not audience outcomes).
    """
    label = podcast_name or "this show"
    if show.n_measured < MIN_SHOW_EPISODES:
        return [
            f"Compared with {label}: measure more episodes from this feed to see "
            "how this one sits against your catalog."
        ]

    n = show.n_measured
    ctx = f"among {n} other measured episode{'s' if n != 1 else ''} from {label}"
    hook = float(features.hook_length_seconds or 0)
    questions = int(features.question_count or 0)
    turns = int(features.speaking_turns or 0)
    topic = int(features.topic_shift_count or 0)
    ratio = float(features.host_guest_ratio or 0.5)

    bullets: List[str] = []

    if show.hook_seconds:
        if hook <= min(show.hook_seconds) + 0.5:
            bullets.append(f"Shortest opening hook {ctx}.")
        elif hook >= max(show.hook_seconds) - 0.5:
            bullets.append(f"Longest opening hook {ctx}.")

    avg_q = show.avg_questions
    if avg_q > 0:
        if questions >= avg_q * 1.35:
            bullets.append(
                f"More question-led than your typical measured episode from {label}."
            )
        elif questions <= avg_q * 0.65:
            bullets.append(
                f"More narrative-led (fewer questions) than your typical measured "
                f"episode from {label}."
            )

    avg_t = show.avg_turns
    if avg_t > 0:
        if turns <= avg_t * 0.65:
            bullets.append(
                f"Longer uninterrupted segments (fewer speaking turns) than usual {ctx}."
            )
        elif turns >= avg_t * 1.35:
            bullets.append(f"More frequent handoffs than usual {ctx}.")

    if show.topic_shifts is not None and topic <= min(show.topic_shifts):
        bullets.append(f"Most focused single-topic measurement {ctx} (fewest pivot markers).")

    if show.guest_ratios:
        if 0.42 <= ratio <= 0.58 and (
            ratio < min(show.guest_ratios) + 0.05 or ratio > max(show.guest_ratios) - 0.05
        ):
            bullets.append(f"Unusually even guest/host balance {ctx}.")

    if not bullets:
        bullets.append(
            f"Structure sits near the middle of your measured catalog from {label}."
        )
    return bullets[:5]
