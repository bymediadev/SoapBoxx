"""How this episode differs from other measured episodes on the same show."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures
from backend.services.library_benchmarks import LibraryBenchmarks, library_from_rows
from backend.services.measurement_versions import filter_comparable_rows, stamp_for_row

MIN_SHOW_EPISODES = 2


def load_show_feature_rows(
    db: Session,
    podcast_id: int,
    *,
    exclude_episode_id: int,
    anchor: Optional[EpisodeFeatures] = None,
) -> tuple[List[EpisodeFeatures], int]:
    rows = list(
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
    stamp = stamp_for_row(anchor)
    kept, excluded = filter_comparable_rows(rows, stamp)
    return kept, excluded


def load_show_benchmarks(
    db: Session,
    podcast_id: int,
    *,
    exclude_episode_id: int,
    anchor: Optional[EpisodeFeatures] = None,
) -> tuple[LibraryBenchmarks, int]:
    rows, excluded = load_show_feature_rows(
        db,
        podcast_id,
        exclude_episode_id=exclude_episode_id,
        anchor=anchor,
    )
    lib = library_from_rows(rows)
    return lib, excluded


def structural_variance_bullets(
    features: EpisodeFeatures,
    show: LibraryBenchmarks,
    *,
    podcast_name: Optional[str] = None,
    rhetorical_heavy: bool = False,
    has_diarization: bool = True,
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
    if avg_q > 0 and not rhetorical_heavy:
        if questions >= avg_q * 1.35:
            bullets.append(
                f"More question-led than your typical measured episode from {label}."
            )
        elif questions <= avg_q * 0.65:
            bullets.append(
                f"More narrative-led (fewer questions) than your typical measured "
                f"episode from {label}."
            )
    elif rhetorical_heavy:
        bullets.append(
            f"More rhetorical question marks in narration than typical interview-led "
            f"episodes from {label} — diary/explainer read."
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
        bullets.append(f"Most focused dominant-thread measurement {ctx} (fewest transition markers in text).")

    if show.guest_ratios and has_diarization:
        if 0.42 <= ratio <= 0.58 and (
            ratio < min(show.guest_ratios) + 0.05 or ratio > max(show.guest_ratios) - 0.05
        ):
            bullets.append(f"Unusually even guest/host balance {ctx}.")

    if not bullets:
        bullets.append(
            f"Structure sits near the middle of your measured catalog from {label}."
        )
    return bullets[:5]
