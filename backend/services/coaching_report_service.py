"""Rule-based coaching report: benchmarks, listener experience, library comparisons."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models import Episode, EpisodeFeatures
from backend.services.show_variance_service import (
    load_show_benchmarks,
    structural_variance_bullets,
)
from backend.services.library_benchmarks import (
    LibraryBenchmarks,
    benchmark_guest_ratio,
    benchmark_hook,
    benchmark_intro,
    benchmark_questions,
    benchmark_turns,
    library_comparison_bullets,
    load_library_benchmarks,
)

_FORBIDDEN = re.compile(
    r"\b(good|bad|best|worst|score|rank|rating|rated|should improve|you must|"
    r"weak|strong|engaging|engagement|improve|fix this|audience will|listeners will)\b",
    re.I,
)

_DISCLAIMER = (
    "We show how the episode is built — not a quality verdict. "
    "Structure signals only; they do not predict audience response."
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
    listener_experience: List[str] = field(default_factory=list)
    compared_with_library: List[str] = field(default_factory=list)
    editorial_tradeoffs: List[str] = field(default_factory=list)
    structural_variance: List[str] = field(default_factory=list)
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
            "listener_experience": list(self.listener_experience),
            "compared_with_library": list(self.compared_with_library),
            "editorial_tradeoffs": list(self.editorial_tradeoffs),
            "structural_variance": list(self.structural_variance),
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


def _template_id(f: EpisodeFeatures) -> str:
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    if intro >= 120 or hook >= 90:
        return "A"
    if questions >= 12:
        return "B"
    return "C"


def _listener_opening(hook: float, intro: float) -> str:
    if hook >= 90 or intro >= 120:
        return (
            "Listeners spend a long stretch in setup before the core thread lands — "
            "the experience is front-loaded with context before the story fully opens."
        )
    if hook < 45 and intro < 60:
        return (
            "Listeners reach the main thread quickly — the episode does not linger "
            "in runway before the story or guest voice takes over."
        )
    return (
        "The opening moves at a moderate pace — enough runway to orient, "
        "then a turn into the main narrative."
    )


def _listener_questions(count: int) -> str:
    if count >= 18:
        return (
            "Questions arrive often — the listener experiences frequent "
            "interviewer-led pivots rather than long uninterrupted explanation."
        )
    if count >= 8:
        return (
            "Questions appear regularly, alternating guided interview beats "
            "with longer explanatory passages."
        )
    if count > 0:
        return (
            "Questions are used sparingly — most information is delivered "
            "through explanation and narration rather than interviewer exploration."
        )
    return (
        "The transcript carries little explicit Q&A — the listener experience "
        "reads as continuous narration."
    )


def _listener_turns(count: int) -> str:
    if count >= 26:
        return (
            "Voices trade often — the listener hears rapid handoffs and "
            "short bursts rather than long monologue blocks."
        )
    if count >= 11:
        return (
            "Turn-taking is moderate — stretches of explanation alternate "
            "with exchange, without feeling like a single uninterrupted lecture."
        )
    if count > 0:
        return (
            "The episode relies on extended storytelling segments rather than rapid "
            "host–guest exchanges — information arrives in larger narrative blocks, "
            "closer to documentary pacing than ping-pong interview."
        )
    return (
        "Speaker handoffs were not detected from labeled lines — pacing may read "
        "as one continuous voice in the transcript."
    )


def _listener_topic_arc(topic_shifts: int, template_id: str) -> str:
    if topic_shifts >= 3:
        return (
            "The listener hears several structural pivots — distinct beats "
            "as the conversation moves between threads."
        )
    if topic_shifts >= 1:
        return (
            "At least one clear pivot appears in the transcript — "
            "the thread shifts once or twice rather than staying on a single rail."
        )
    if template_id == "C":
        return (
            "The episode stays focused on a single narrative thread with few "
            "detected structural pivots — produced storytelling rather than "
            "frequent scene changes (sub-stories may still sit inside one arc)."
        )
    return (
        "Few pivot phrases or scene breaks were detected — "
        "either one continuous thread or transitions that do not surface in the text."
    )


def _listener_balance(ratio: float) -> str:
    if 0.42 <= ratio <= 0.58:
        return (
            "Neither voice clearly dominates airtime — "
            "the listener hears a relatively even conversation."
        )
    if ratio < 0.42:
        return "The host carries more of the spoken runtime — guest voice is supporting."
    return "The guest carries more of the spoken runtime — host voice frames more than leads."


def _listener_cta(present: bool) -> Optional[str]:
    if present:
        return (
            "A subscribe or follow-style call appears near the end — "
            "listeners get an explicit next-step cue."
        )
    return None


def _topic_shift_detection_note(count: int) -> Optional[str]:
    if count > 0:
        return None
    return (
        "Topic shifts: 0 in measurement. Pivot detection uses explicit transition phrases "
        "and paragraph breaks in the transcript — dense narrative without those cues "
        "can read as one arc even when the story covers several sub-topics. "
        "Worth spot-checking against the audio."
    )


def _pattern_synthesis(template_id: str, f: EpisodeFeatures) -> str:
    if template_id == "A":
        return (
            "Pattern: extended opening before the core thread — "
            "common in shows that front-load context; review when the listener "
            "would feel the story has actually started."
        )
    if template_id == "B":
        return (
            "Pattern: question-led interview — "
            "rhythm and depth come from how the host uses questions and follow-ups, "
            "not from long uninterrupted monologue blocks."
        )
    return (
        "Pattern: narrative-led produced story — "
        "sparse questions, longer segments, and a single through-line "
        "rather than rapid conversational pivots."
    )


def _editorial_tradeoffs(f: EpisodeFeatures, template_id: str) -> List[str]:
    """Structural trade-offs (not quality judgments)."""
    hook = float(f.hook_length_seconds or 0)
    intro = float(f.intro_length_seconds or 0)
    questions = int(f.question_count or 0)
    turns = int(f.speaking_turns or 0)
    topic = int(f.topic_shift_count or 0)
    ratio = float(f.host_guest_ratio or 0.5)
    notes: List[str] = []

    if hook < 50 and intro < 60:
        if topic <= 1:
            notes.append(
                "Trade-off: the episode enters the story quickly and holds one arc — "
                "clarity stays high, with few detected pivots for side-path exploration."
            )
        else:
            notes.append(
                "Trade-off: a quick entry with several pivot markers — "
                "pace moves between threads rather than one uninterrupted runway."
            )
    elif hook >= 90 or intro >= 120:
        notes.append(
            "Trade-off: extended opening runway — listeners get context before the "
            "core thread, at the cost of later story time."
        )

    if questions <= 6 and turns <= 12:
        notes.append(
            "Trade-off: information rides on long explanation blocks rather than "
            "rapid conversational exchanges — narrative continuity over frequent handoffs."
        )
    elif questions >= 12:
        notes.append(
            "Trade-off: frequent questions drive pacing — depth comes from follow-ups, "
            "not from long uninterrupted monologue."
        )

    if 0.42 <= ratio <= 0.58 and questions <= 8:
        notes.append(
            "Trade-off: even speaker balance, though most runtime is still delivered "
            "in extended segments rather than rapid handoffs."
        )

    if template_id == "C" and not notes:
        notes.append(
            "Trade-off: story-first structure prioritizes through-line over "
            "conversational surprise."
        )

    return notes[:3]


def _similar_to(f: EpisodeFeatures, lib: LibraryBenchmarks, template_id: str) -> str:
    if lib.n_measured < 3:
        return (
            "Library comparison unlocks after more episodes are measured."
        )
    if template_id == "C":
        return (
            "Within your measured library, this episode aligns with narrative-led "
            "story-first structure (explanation blocks, sparse Q&A) rather than "
            "interview-heavy formats."
        )
    if template_id == "B":
        return (
            "Within your measured library, this episode aligns with question-led "
            "interview pacing rather than sparse narrative structure."
        )
    return (
        "Within your measured library, this episode is distinguished by opening "
        "length more than question density."
    )


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
    cta = bool(features.cta_present)

    template_id = _template_id(features)
    narrative_led = template_id == "C"

    structure = [
        MetricRow("Hook", _fmt_seconds(hook), benchmark_hook(hook, lib), None),
        MetricRow("Intro", _fmt_seconds(intro), benchmark_intro(intro, lib), None),
        MetricRow("CTA", "Present" if cta else "Not detected", None, None),
    ]

    dynamics = [
        MetricRow(
            "Questions",
            str(questions),
            benchmark_questions(questions, lib),
            None,
        ),
        MetricRow(
            "Speaking turns",
            str(turns),
            benchmark_turns(turns, lib),
            None,
        ),
        MetricRow(
            "Guest talk ratio",
            _fmt_ratio(ratio),
            benchmark_guest_ratio(ratio, lib),
            None,
        ),
        MetricRow("Topic shifts", str(topic_shifts), None, None),
    ]

    listener: List[str] = [
        _listener_opening(hook, intro),
        _listener_questions(questions),
        _listener_turns(turns),
        _listener_topic_arc(topic_shifts, template_id),
        _listener_balance(ratio),
    ]
    cta_line = _listener_cta(cta)
    if cta_line:
        listener.append(cta_line)

    compared = library_comparison_bullets(
        hook=hook,
        intro=intro,
        questions=questions,
        turns=turns,
        ratio=ratio,
        lib=lib,
        narrative_led=narrative_led,
    )

    podcast_name = None
    variance: List[str] = []
    if hasattr(db, "execute"):
        episode = db.execute(
            select(Episode)
            .where(Episode.id == features.episode_id)
            .options(joinedload(Episode.podcast))
        ).scalar_one_or_none()
        if episode:
            podcast_name = episode.podcast.name if episode.podcast else None
            show_lib = load_show_benchmarks(
                db, int(episode.podcast_id), exclude_episode_id=int(features.episode_id)
            )
            variance = structural_variance_bullets(
                features, show_lib, podcast_name=podcast_name
            )

    report = CoachingReport(
        episode_structure=structure,
        conversation_dynamics=dynamics,
        listener_experience=listener,
        compared_with_library=compared,
        editorial_tradeoffs=_editorial_tradeoffs(features, template_id),
        structural_variance=variance,
        what_this_means=[_pattern_synthesis(template_id, features)],
        similar_to=_similar_to(features, lib, template_id),
        topic_shift_note=_topic_shift_detection_note(topic_shifts),
    )
    _assert_no_forbidden(report)
    return report


def synthesis_insight_text(report: CoachingReport) -> str:
    """Short lead paragraph for API ``insight_text`` field."""
    lead = report.listener_experience[:2]
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
    chunks.extend(report.listener_experience)
    chunks.extend(report.compared_with_library)
    chunks.extend(report.editorial_tradeoffs)
    chunks.extend(report.structural_variance)
    chunks.extend(report.what_this_means)
    if report.similar_to:
        chunks.append(report.similar_to)
    if report.topic_shift_note:
        chunks.append(report.topic_shift_note)
    for text in chunks:
        if _FORBIDDEN.search(text):
            raise RuntimeError(f"Coaching copy violated forbidden language: {text[:80]}")
