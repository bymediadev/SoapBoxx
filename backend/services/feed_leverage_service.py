"""Feed-anchored leverage points: structural bands on a feed (no ranking, no causality).

Aggregation logic version: see backend.services.measurement_versions.AGGREGATION_VERSION
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Callable, List, Optional, Sequence

from backend.models import EpisodeFeatures
from backend.services.library_benchmarks import LibraryBenchmarks
from backend.services.measurement_versions import AGGREGATION_VERSION as _AGGREGATION_VERSION  # noqa: F401 — bump with band logic

_FORBIDDEN = re.compile(
    r"\b(align with|aligns with|upper band|lower band|mid band|highest|lowest|"
    r"top \d|bottom \d|better|worse|stronger|weaker|if you|will result|will become|"
    r"improve|improves|should)\b",
    re.I,
)

# Named structural partitions — geometry, not ordinal tiers.
STRUCTURAL_BAND = {
    "A": "extended-opening band",
    "B": "interview-led band",
    "C": "narrative documentary band",
}

STRUCTURAL_PATTERN = {
    "A": "extended-opening",
    "B": "interview-led",
    "C": "narrative documentary",
}

HYBRID_BAND = "hybrid explanation band"
HYBRID_PATTERN = "hybrid explanation"

_KNOB_LABELS = {
    "questions": "Question density",
    "turns": "Speaking-turn density",
    "hook": "Opening length",
}


from backend.services.template_classification import template_id_from_features


def build_structural_identity(
    features: EpisodeFeatures,
    template_id: str,
    *,
    playbook: Optional[dict] = None,
) -> List[str]:
    """One or two lines: what kind of episode this is (decision lens, not analysis)."""
    if playbook:
        lines: List[str] = []
        form = (playbook.get("form") or "").strip()
        tagline = (playbook.get("tagline") or "").strip()
        feels = (playbook.get("feels_like") or "").strip()
        if form:
            lines.append(form)
        if tagline:
            lines.append(tagline)
        elif feels:
            lines.append(feels)
        return lines[:2]

    pattern = STRUCTURAL_PATTERN.get(template_id, "measured episode")
    hook = float(features.hook_length_seconds or 0)
    intro = float(features.intro_length_seconds or 0)
    questions = int(features.question_count or 0)

    if template_id == "A":
        detail = (
            "Extended opening before the core thread — context front-loads before "
            "the story fully opens."
        )
    elif template_id == "B":
        detail = (
            "Question-led interview — rhythm comes from interviewer pivots and "
            "follow-ups rather than long explanation blocks."
        )
    elif hook < 45 and intro < 60 and questions <= 6:
        detail = (
            "Narrative-led produced story — sparse Q&A, longer segments, one "
            "dominant narrative thread."
        )
    else:
        detail = (
            "Narrative-led structure — explanation and narration carry more runtime "
            "than explicit Q&A."
        )
    return [f"{pattern} structure".capitalize(), detail][:2]


def _knob_value(episode: EpisodeFeatures, knob: str) -> float:
    if knob == "questions":
        return float(int(episode.question_count or 0))
    if knob == "turns":
        return float(int(episode.speaking_turns or 0))
    return float(episode.hook_length_seconds or 0)


def _metric_neighbors(
    show_rows: Sequence[EpisodeFeatures],
    episode: EpisodeFeatures,
    knob: str,
) -> List[EpisodeFeatures]:
    """Feed episodes nearest to this episode on one knob axis (structural neighborhood)."""
    current = _knob_value(episode, knob)
    pool = list(show_rows) + [episode]
    pool.sort(key=lambda r: (abs(_knob_value(r, knob) - current), r.episode_id or 0))
    return pool[: max(2, min(4, len(pool)))]


def _band_from_neighbors(neighbors: Sequence[EpisodeFeatures]) -> tuple[str, str]:
    """
    Name a non-ordinal structural band from observed neighbor templates.
    Returns (band_label, pattern_label_for_catalog_phrase).
    """
    if not neighbors:
        return HYBRID_BAND, HYBRID_PATTERN

    templates = [template_id_from_features(r) for r in neighbors]
    counts = Counter(templates)
    dominant_id, dominant_n = counts.most_common(1)[0]
    if dominant_n < 2 or len(counts) > 1 and counts.most_common(2)[1][1] == dominant_n:
        return HYBRID_BAND, HYBRID_PATTERN
    return (
        STRUCTURAL_BAND.get(dominant_id, HYBRID_BAND),
        STRUCTURAL_PATTERN.get(dominant_id, HYBRID_PATTERN),
    )


def _catalog_observation(pattern: str, feed_name: str, *, enough: bool) -> str:
    label = feed_name or "this feed"
    if not enough:
        return (
            f"measure more episodes on {label} to map this knob into "
            f"observed structural bands"
        )
    return (
        f"episodes in this band in your feed have been observed in {pattern} "
        f"patterns within your measured catalog"
    )


def _leverage_line(
    knob: str,
    *,
    show_rows: Sequence[EpisodeFeatures],
    episode: EpisodeFeatures,
    feed_name: str,
) -> str:
    label = _KNOB_LABELS[knob]
    name = feed_name or "this feed"

    if not show_rows:
        return (
            f"{label} · structural band not yet mapped on {name} · "
            f"no other measured episodes on this feed yet"
        )

    neighbors = _metric_neighbors(show_rows, episode, knob)
    band, pattern = _band_from_neighbors(neighbors)
    enough = len(neighbors) >= 2 and len(show_rows) >= 2
    observation = _catalog_observation(pattern, name, enough=enough)

    return f"{label} · {band} on {name} · {observation}"


def _deviation(current: float, values: Sequence[float]) -> float:
    if not values:
        return 0.0
    avg = sum(values) / len(values)
    if avg == 0:
        return abs(current)
    return abs(current - avg) / max(avg, 1.0)


def _assert_leverage_copy(lines: Sequence[str]) -> None:
    for text in lines:
        if _FORBIDDEN.search(text):
            raise RuntimeError(f"Leverage copy violated safe-intelligence contract: {text[:80]}")


def build_feed_leverage_points(
    episode: EpisodeFeatures,
    show: LibraryBenchmarks,
    show_rows: Sequence[EpisodeFeatures],
    *,
    feed_name: Optional[str] = None,
) -> List[str]:
    """
    At most two feed-anchored knobs placed in named structural bands.
    Descriptive partitions only — no ordinal bands, no causality, no outcomes.
    """
    name = feed_name or "this feed"
    candidates: List[tuple[float, str, Callable[[], str]]] = []

    q = int(episode.question_count or 0)
    q_vals = [float(x) for x in show.question_counts]
    candidates.append(
        (
            _deviation(float(q), q_vals) if q_vals else 1.0,
            "questions",
            lambda: _leverage_line(
                "questions",
                show_rows=show_rows,
                episode=episode,
                feed_name=name,
            ),
        )
    )

    t = int(episode.speaking_turns or 0)
    t_vals = [float(x) for x in show.speaking_turns]
    candidates.append(
        (
            _deviation(float(t), t_vals) if t_vals else 0.5,
            "turns",
            lambda: _leverage_line(
                "turns",
                show_rows=show_rows,
                episode=episode,
                feed_name=name,
            ),
        )
    )

    h = float(episode.hook_length_seconds or 0)
    h_vals = [float(x) for x in show.hook_seconds]
    candidates.append(
        (
            _deviation(h, h_vals) if h_vals else 0.3,
            "hook",
            lambda: _leverage_line(
                "hook",
                show_rows=show_rows,
                episode=episode,
                feed_name=name,
            ),
        )
    )

    candidates.sort(key=lambda x: x[0], reverse=True)
    lines: List[str] = []
    seen_knobs: set[str] = set()
    for _, knob, builder in candidates:
        if knob in seen_knobs:
            continue
        seen_knobs.add(knob)
        lines.append(builder())
        if len(lines) >= 2:
            break

    _assert_leverage_copy(lines)
    return lines[:2]
