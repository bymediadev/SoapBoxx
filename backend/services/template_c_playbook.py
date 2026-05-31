"""Template C — narrative documentary / story-first episodes (V1 rule-based playbook)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from backend.models import EpisodeFeatures

_FORBIDDEN = re.compile(
    r"\b("
    r"score|rank|rating|rated|should improve|you must|"
    r"fix this|audience will|listeners will|"
    r"good episode|bad episode|best episode|worst episode|"
    r"highly engaging|low engagement"
    r")\b",
    re.I,
)

FORM_NAME = "Narrative documentary (structural pattern)"
TEMPLATE_ID = "C"


@dataclass
class TemplateCPlaybook:
    template_id: str
    form: str
    tagline: str
    feels_like: str
    review_these: List[str]
    how_its_built: List[str]
    trade_offs: List[str]
    leverage_points: List[str]
    similar_form: str

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "form": self.form,
            "tagline": self.tagline,
            "feels_like": self.feels_like,
            "review_these": list(self.review_these),
            "how_its_built": list(self.how_its_built),
            "trade_offs": list(self.trade_offs),
            "leverage_points": list(self.leverage_points),
            "similar_form": self.similar_form,
        }


def _fmt_seconds(seconds: float) -> str:
    s = max(0.0, float(seconds or 0))
    if s < 60:
        return f"{s:.0f} seconds"
    minutes = int(s // 60)
    rem = int(round(s % 60))
    if rem:
        return f"{minutes}:{rem:02d}"
    return f"{minutes} min"


def build_template_c_playbook(
    f: EpisodeFeatures,
    *,
    library_measured: int = 0,
) -> TemplateCPlaybook:
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)
    topic = int(f.topic_shift_count or 0)
    cta = bool(f.cta_present)

    tagline = (
        "One dominant narrative thread, sparse Q&A, long explanation blocks — built "
        "for listeners who stay for the through-line, not rapid back-and-forth."
    )

    feels_like = (
        "Think a produced field story (Planet Money, Radiolab act, documentary "
        "reporter walk-through) — not a founder interview or roundtable."
    )

    how_built: List[str] = []

    if hook < 45 and intro < 60:
        how_built.append(
            f"The story opens in about {_fmt_seconds(hook)} with guest or topic in "
            f"around {_fmt_seconds(intro)} — listeners are in the premise quickly, "
            "typical for narrative explainers that skip long runway."
        )
    elif hook >= 90 or intro >= 120:
        how_built.append(
            "The opening carries extra runway before the core thread — common when "
            "the show front-loads context before the reporter enters the story."
        )
    else:
        how_built.append(
            "The opening gives moderate setup before the main thread — between "
            "cold-open explainers and long-form scene-setting."
        )

    if questions <= 5:
        how_built.append(
            f"Only {questions} questions in the transcript — the host narrates and "
            "explains more than they excavate. Information moves in blocks, not ping-pong Q&A."
        )
    else:
        how_built.append(
            f"{questions} questions appear — more than a pure explainer, but still "
            "below typical interview density."
        )

    if turns <= 12:
        how_built.append(
            f"{turns} speaking turns — each handoff covers a long stretch. "
            "That's documentary pacing: fewer cuts, longer uninterrupted segments."
        )
    else:
        how_built.append(
            f"{turns} speaking turns — more handoffs than a pure monologue edit, "
            "but still explanation-heavy for this form."
        )

    if topic <= 1:
        how_built.append(
            "No explicit transition markers in the transcript — one dominant narrative "
            "thread on the text; sub-beats or scene changes may still exist in the edit."
        )

    if cta:
        how_built.append(
            "A subscribe/follow-style CTA appears near the end — standard for "
            "produced public-media episodes."
        )

    review: List[str] = []

    if hook < 45:
        review.append(
            "On replay: mark the first line where a new listener would know what "
            "this episode is about — you entered fast; confirm that line is clear without show context."
        )
    else:
        review.append(
            "On replay: note when the premise lands — narrative drops often happen "
            "before the listener understands the stakes of the story."
        )

    if questions <= 5:
        review.append(
            "Scan each question — are they moving the story forward, or only bridging "
            "between explanation blocks? In this form, questions often work as signposts, not probes."
        )

    if turns <= 12:
        review.append(
            "Pick one long segment and listen for mid-block re-hooks (mini questions, "
            "scene resets, 'here's why that matters') — documentary cuts need them when handoffs are rare."
        )

    if topic <= 1:
        review.append(
            "If the story covers several sub-topics, listen for places a stranger might "
            "think the thread changed — pivot language may not show up in the transcript."
        )

    review.append(
        "Compare this cut to an interview-heavy episode from the same show — "
        "where does this one breathe longer, and where does it stay on one rail?"
    )

    trade_offs: List[str] = []

    if hook < 50 and intro < 60 and topic <= 1:
        trade_offs.append(
            "Quick entry + dominant thread: clarity stays high; side-path exploration "
            "stays minimal."
        )

    if questions <= 6 and turns <= 12:
        trade_offs.append(
            "Long explanation blocks over frequent exchange — narrative continuity "
            "over conversational variety."
        )

    if not trade_offs:
        trade_offs.append(
            "Story-first structure trades rapid pivots for a dominant through-line."
        )

    leverage: List[str] = []

    if library_measured >= 3:
        similar = (
            "In your measured library, this shape has been observed among narrative "
            "documentary episodes (sparse Q&A, long segments) rather than "
            "interview-heavy formats."
        )
    else:
        similar = (
            "This shape has been observed in the narrative documentary band — measure "
            "more episodes to compare against your own catalog."
        )

    playbook = TemplateCPlaybook(
        template_id=TEMPLATE_ID,
        form=FORM_NAME,
        tagline=tagline,
        feels_like=feels_like,
        review_these=review[:4],
        how_its_built=how_built[:5],
        trade_offs=trade_offs[:3],
        leverage_points=leverage,
        similar_form=similar,
    )
    _assert_no_forbidden(playbook)
    return playbook


def template_c_listener_experience(f: EpisodeFeatures) -> List[str]:
    """Listener-experience lines tailored to narrative documentary form."""
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)
    topic = int(f.topic_shift_count or 0)

    lines: List[str] = []

    if hook < 45 and intro < 60:
        lines.append(
            "You drop into the story quickly — like joining a reporter mid-walkthrough, "
            "not sitting through a long intro montage."
        )
    else:
        lines.append(
            "The opening takes its time before the main thread — listeners get context "
            "before the reporter fully enters the story."
        )

    if questions <= 5:
        lines.append(
            "Questions are rare — you hear a guided explanation more than a back-and-forth "
            "interview. The host carries the narrative."
        )

    if turns <= 12:
        lines.append(
            "Voices change infrequently — each stretch runs long, like a documentary "
            "segment rather than a conversation clip show."
        )

    if topic <= 1:
        lines.append(
            "The transcript reads as one dominant narrative thread — few explicit "
            "transition markers, even if sub-stories or scene changes exist in the edit."
        )

    lines.append(
        "If you've listened to Planet Money or similar explainers, this is that shape: "
        "a dominant thread, reporter voice, sparse Q&A."
    )

    return lines[:5]


def _assert_no_forbidden(playbook: TemplateCPlaybook) -> None:
    chunks = (
        [playbook.tagline, playbook.feels_like, playbook.similar_form]
        + playbook.review_these
        + playbook.how_its_built
        + playbook.trade_offs
        + playbook.leverage_points
    )
    for text in chunks:
        if _FORBIDDEN.search(text):
            raise RuntimeError(f"Template C copy violated forbidden language: {text[:80]}")
