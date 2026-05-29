"""Translation layer — structural meaning only (Day 7)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeFeatures, EpisodeTranslation
from backend.services.pipeline_status import (
    STATUS_READY,
    record_event,
    set_episode_status,
)

_FORBIDDEN = re.compile(
    r"\b(good|bad|best|worst|score|rank|rating|rated|should improve|you must|"
    r"weak|strong|engaging|improve|fix this)\b",
    re.I,
)

_DISCLAIMER = (
    "These are structure signals — how a listener might experience the opening "
    "and pacing. They do not predict audience response."
)


@dataclass
class TranslationResult:
    episode_id: int
    template_id: str
    insight_text: str


def _fmt_seconds(seconds: float) -> str:
    s = max(0.0, float(seconds or 0))
    if s < 60:
        return f"{s:.0f} seconds"
    minutes = int(s // 60)
    rem = int(round(s % 60))
    if rem:
        return f"{minutes}:{rem:02d}"
    return f"{minutes} min"


def _opening_listener_note(hook: float, intro: float) -> str:
    """Listener-lens copy for the opening (hook + intro)."""
    parts: list[str] = []

    if hook >= 90:
        parts.append(
            f"The opening beat runs about {_fmt_seconds(hook)} before the conversation turns — "
            "listeners may wait a while to hear where the episode is going."
        )
    elif hook >= 45:
        parts.append(
            f"The opening beat is about {_fmt_seconds(hook)} before a topic shift."
        )
    else:
        parts.append(f"The opening beat is about {_fmt_seconds(hook)}.")

    if intro >= 120:
        parts.append(
            f"The intro block is about {_fmt_seconds(intro)} before guest voice or a clear topic shift — "
            "a listener may still be waiting for the core story."
        )
    elif intro >= 60:
        parts.append(
            f"Guest voice or a topic shift appears around {_fmt_seconds(intro)}."
        )
    else:
        parts.append(
            f"The story or guest enters around {_fmt_seconds(intro)} into the episode."
        )

    return " ".join(parts)


def _conversation_shape_note(
    questions: int,
    topic_shifts: int,
    *,
    cta_present: bool,
) -> str:
    parts: list[str] = []

    if questions >= 18:
        parts.append(
            f"There are {questions} questions in the transcript — "
            "the host guides through frequent question-and-answer cycles."
        )
    elif questions >= 8:
        parts.append(
            f"There are {questions} questions — a mix of guided interview pacing "
            "and longer explanation blocks."
        )
    elif questions > 0:
        parts.append(
            f"There are {questions} questions — lower question density, "
            "with more extended explanation or storytelling segments."
        )
    else:
        parts.append(
            "No question marks detected — the episode reads as continuous narration "
            "rather than explicit interview Q&A."
        )

    if topic_shifts >= 2:
        parts.append(
            f"About {topic_shifts} topic-shift markers appear — "
            "several distinct beats in the conversation."
        )
    elif topic_shifts == 1:
        parts.append("One topic-shift marker appears in the transcript.")

    if cta_present:
        parts.append("A call-to-action phrase appears near the end.")

    return " ".join(parts)


def _template_from_features(f: EpisodeFeatures) -> tuple[str, str]:
    """
    Rule-based insight copy in producer/listener language (template A/B/C).

    A — extended opening (zone-out risk in the first minutes)
    B — question-driven interview pacing
    C — narrative / lower question density
    """
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    topic_shifts = int(f.topic_shift_count or 0)
    cta_present = bool(f.cta_present)

    opening = _opening_listener_note(hook, intro)
    shape = _conversation_shape_note(
        questions, topic_shifts, cta_present=cta_present
    )

    if intro >= 120 or hook >= 90:
        template_id = "A"
        pattern = (
            "The opening block is extended relative to typical interview pacing — "
            "review this section as a listener would: when does the story start?"
        )
    elif questions >= 12:
        template_id = "B"
        pattern = (
            "The episode follows a question-led interview pattern — "
            "follow-ups and depth come from how the host uses those questions."
        )
    else:
        template_id = "C"
        pattern = (
            "The episode is narrative-led with fewer explicit questions — "
            "listeners stay for the through-line of the story rather than rapid Q&A."
        )

    text = f"{opening} {pattern} {shape} {_DISCLAIMER}"
    return template_id, text


def run_translation(db: Session, episode_id: int) -> TranslationResult:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    features = db.get(EpisodeFeatures, episode_id)
    if not features:
        raise ValueError("Episode has no features; run feature extraction first")

    template_id, text = _template_from_features(features)
    if _FORBIDDEN.search(text):
        raise RuntimeError("Translation template violated forbidden language")

    row = db.get(EpisodeTranslation, episode_id)
    if not row:
        row = EpisodeTranslation(episode_id=episode_id)
        db.add(row)
    row.template_id = template_id
    row.insight_text = text
    set_episode_status(db, episode, STATUS_READY, commit=False)
    record_event(
        db,
        "pipeline.ready",
        f"Insight ready: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        meta={"template_id": template_id},
        commit=False,
    )
    db.commit()
    return TranslationResult(
        episode_id=episode_id,
        template_id=template_id,
        insight_text=text,
    )
