"""Rule-based coaching report: metrics + library benchmarks + what-this-means bullets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models import EpisodeFeatures
from backend.services.library_benchmarks import (
    LibraryBenchmarks,
    benchmark_guest_ratio,
    benchmark_hook,
    benchmark_intro,
    benchmark_questions,
    benchmark_turns,
    load_library_benchmarks,
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
class MetricRow:
    metric: str
    value: str
    benchmark: Optional[str] = None
    coaching: Optional[str] = None


@dataclass
class CoachingReport:
    episode_structure: List[MetricRow] = field(default_factory=list)
    conversation_dynamics: List[MetricRow] = field(default_factory=list)
    what_this_means: List[str] = field(default_factory=list)
    similar_to: Optional[str] = None
    topic_shift_note: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "episode_structure": [
                {
                    "metric": r.metric,
                    "value": r.value,
                    "benchmark": r.benchmark,
                    "coaching": r.coaching,
                }
                for r in self.episode_structure
            ],
            "conversation_dynamics": [
                {
                    "metric": r.metric,
                    "value": r.value,
                    "benchmark": r.benchmark,
                    "coaching": r.coaching,
                }
                for r in self.conversation_dynamics
            ],
            "what_this_means": list(self.what_this_means),
            "similar_to": self.similar_to,
            "topic_shift_note": self.topic_shift_note,
        }


def _fmt_seconds(seconds: float) -> str:
    s = max(0.0, float(seconds or 0))
    if s < 60:
        return f"{s:.0f}s"
    minutes = int(s // 60)
    rem = int(round(s % 60))
    if rem:
        return f"{minutes}:{rem:02d}"
    return f"{minutes}m"


def _fmt_ratio(ratio: float) -> str:
    return f"{round(float(ratio or 0.5) * 100)}%"


def _coach_hook(seconds: float) -> str:
    if seconds >= 90:
        return (
            "The opening beat is extended before the conversation turns — "
            "listeners may wait longer to hear where the episode is going."
        )
    if seconds >= 45:
        return (
            "The opening runs mid-length before a pivot — "
            "not abrupt, not a long runway."
        )
    return (
        "The opening turns quickly — "
        "listeners hear direction early in the episode."
    )


def _coach_intro(seconds: float) -> str:
    if seconds >= 120:
        return (
            "The intro block is long before guest voice or a clear topic shift — "
            "a listener may still be waiting for the core story."
        )
    if seconds >= 60:
        return "Guest voice or a topic shift appears after a moderate intro block."
    return "The story or guest enters early — little runway before the main thread."


def _coach_questions(count: int) -> str:
    if count >= 18:
        return (
            f"{count} questions drive the episode — "
            "information advances through frequent interviewer-led cycles."
        )
    if count >= 8:
        return (
            f"{count} questions mix guided interview pacing "
            "with longer explanation blocks."
        )
    if count > 0:
        return (
            f"Only {count} questions across the conversation — "
            "most runtime is extended explanation rather than interviewer exploration."
        )
    return (
        "No question marks detected — "
        "the episode reads as continuous narration rather than explicit Q&A."
    )


def _coach_turns(count: int) -> str:
    if count >= 26:
        return (
            f"{count} speaking turns — "
            "rapid back-and-forth pacing with frequent handoffs."
        )
    if count >= 11:
        return (
            f"{count} speaking turns — "
            "a mix of exchange and longer explanation segments."
        )
    if count > 0:
        return (
            f"Only {count} speaking turns — "
            "segments run long, closer to storytelling or lecture pacing than ping-pong interview."
        )
    return "Speaking turns were not detected from labeled lines in the transcript."


def _coach_guest_ratio(ratio: float) -> str:
    if 0.42 <= ratio <= 0.58:
        return "Speaking time is relatively balanced — neither voice clearly dominates."
    if ratio < 0.42:
        return "Host-led airtime — the host carries more of the spoken runtime."
    return "Guest-led airtime — the guest carries more of the spoken runtime."


def _topic_shift_note(count: int) -> str:
    if count >= 2:
        return (
            f"{count} topic-shift markers appear — "
            "several distinct beats in how the conversation moves."
        )
    if count == 1:
        return "One topic-shift marker appears — a single noticeable pivot in the thread."
    return (
        "Zero topic-shift markers in the transcript. "
        "Either the episode stays on one continuous arc, or pivot language may not appear "
        "in the text (worth listening to confirm)."
    )


def _archetype_bullet(template_id: str, f: EpisodeFeatures) -> str:
    hook = float(f.hook_length_seconds or 0)
    questions = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)
    topic_shifts = int(f.topic_shift_count or 0)

    if template_id == "A":
        return (
            "The episode spends substantial runtime in the opening before the core thread — "
            "review that block as a listener would: when does the story actually start?"
        )
    if template_id == "B":
        return (
            "The episode is question-led — "
            "depth and rhythm depend on how follow-ups and clarifiers are used between questions."
        )
    return (
        "The episode runs as a story-first arc with fewer explicit questions "
        f"({questions} questions, {turns} turns, {topic_shifts} topic-shift markers) — "
        "listeners stay for the through-line rather than rapid conversational pivots."
    )


def _similar_to(f: EpisodeFeatures, lib: LibraryBenchmarks) -> str:
    if lib.n_measured < 3:
        return (
            "Similar-to comparisons appear after more episodes are measured in your library."
        )
    qs = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)
    avg_q = lib.avg_questions
    avg_t = lib.avg_turns

    if avg_q > 0 and qs <= avg_q * 0.65 and (avg_t <= 0 or turns <= avg_t * 0.75):
        return (
            "Within your library, this episode reads closer to narrative or story-first structure "
            "(fewer questions, longer segments) than interview-heavy episodes."
        )
    if avg_q > 0 and qs >= avg_q * 1.35:
        return (
            "Within your library, this episode reads closer to question-led interview pacing "
            "than narrative-led episodes."
        )
    return (
        "Within your library, this episode sits in a mixed structural band — "
        "not strongly narrative-only or interview-heavy."
    )


def _template_id(f: EpisodeFeatures) -> str:
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    if intro >= 120 or hook >= 90:
        return "A"
    if questions >= 12:
        return "B"
    return "C"


def build_coaching_report(
    db: Session,
    features: EpisodeFeatures,
    *,
    library: Optional[LibraryBenchmarks] = None,
) -> CoachingReport:
    lib = library or load_library_benchmarks(db)
    hook = float(features.hook_length_seconds or 0)
    intro = float(features.intro_length_seconds or 0)
    questions = int(features.question_count or 0)
    turns = int(features.speaking_turns or 0)
    ratio = float(features.host_guest_ratio or 0.5)
    topic_shifts = int(features.topic_shift_count or 0)
    cta = features.cta_present

    template_id = _template_id(features)

    structure = [
        MetricRow(
            "Hook",
            _fmt_seconds(hook),
            benchmark_hook(hook, lib),
            _coach_hook(hook),
        ),
        MetricRow(
            "Intro",
            _fmt_seconds(intro),
            benchmark_intro(intro, lib),
            _coach_intro(intro),
        ),
        MetricRow(
            "CTA",
            "Present" if cta else "Not detected",
            None,
            "A call-to-action phrase appears near the end."
            if cta
            else "No standard CTA phrase detected in the transcript.",
        ),
    ]

    dynamics = [
        MetricRow(
            "Questions",
            str(questions),
            benchmark_questions(questions, lib),
            _coach_questions(questions),
        ),
        MetricRow(
            "Speaking turns",
            str(turns),
            benchmark_turns(turns, lib),
            _coach_turns(turns),
        ),
        MetricRow(
            "Guest talk ratio",
            _fmt_ratio(ratio),
            benchmark_guest_ratio(ratio, lib),
            _coach_guest_ratio(ratio),
        ),
        MetricRow(
            "Topic shifts",
            str(topic_shifts),
            None,
            _topic_shift_note(topic_shifts).split(". ")[0] + "."
            if topic_shifts > 0
            else None,
        ),
    ]

    bullets: List[str] = []
    seen: set[str] = set()
    for row in structure + dynamics:
        if row.coaching and row.coaching not in seen:
            bullets.append(row.coaching)
            seen.add(row.coaching)
    bullets.append(_archetype_bullet(template_id, features))

    report = CoachingReport(
        episode_structure=structure,
        conversation_dynamics=dynamics,
        what_this_means=bullets,
        similar_to=_similar_to(features, lib),
        topic_shift_note=_topic_shift_note(topic_shifts) if topic_shifts == 0 else None,
    )
    _assert_no_forbidden(report)
    return report


def synthesis_insight_text(report: CoachingReport) -> str:
    """Short lead paragraph for API ``insight_text`` field."""
    lead = report.what_this_means[:2]
    body = " ".join(lead) if lead else "Structure measured for this episode."
    return f"{body} {_DISCLAIMER}"


def coaching_report_for_episode(
    db: Session, features: Optional[EpisodeFeatures]
) -> Optional[dict]:
    if not features:
        return None
    return build_coaching_report(db, features).to_dict()


def _assert_no_forbidden(report: CoachingReport) -> None:
    chunks: List[str] = []
    for row in report.episode_structure + report.conversation_dynamics:
        for part in (row.benchmark, row.coaching):
            if part:
                chunks.append(part)
    chunks.extend(report.what_this_means)
    if report.similar_to:
        chunks.append(report.similar_to)
    if report.topic_shift_note:
        chunks.append(report.topic_shift_note)
    for text in chunks:
        if _FORBIDDEN.search(text):
            raise RuntimeError(f"Coaching copy violated forbidden language: {text[:80]}")
