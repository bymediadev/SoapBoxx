"""Rule-based coaching report: benchmarks, listener experience, library comparisons."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.models import Episode, EpisodeFeatures, TranscriptSegment
from backend.services.show_variance_service import (
    load_show_benchmarks,
    load_show_feature_rows,
    structural_variance_bullets,
)
from backend.services.feed_leverage_service import (
    build_feed_leverage_points,
    build_structural_identity,
)
from backend.services.measurement_versions import stamp_for_row, stamp_dict, cohort_note
from backend.services.narrative_timeline_service import build_narrative_engine_map
from backend.services.producer_view_service import build_producer_view
from backend.services.audio_motion_service import load_audio_motion
from backend.services.producer_notes_service import build_producer_notes
from backend.services.template_classification import (
    effective_form_label,
    has_speaker_diarization,
    is_rhetorical_question_heavy,
    template_id_from_features,
    transcript_limitation_notes,
)
from backend.services.template_c_playbook import (
    build_template_c_playbook,
    template_c_listener_experience,
)
from backend.services.library_benchmarks import (
    LibraryBenchmarks,
    benchmark_guest_ratio,
    benchmark_hook,
    benchmark_intro,
    benchmark_questions,
    benchmark_turns,
    library_from_rows,
    load_library_benchmarks,
)

_FORBIDDEN = re.compile(
    r"\b("
    r"score|rank|rating|rated|should improve|you must|"
    r"fix this|audience will|listeners will|"
    r"will become|will result|if you increase|if you change|if you turn|"
    r"align with|aligns with|upper band|lower band|mid band|"
    r"good episode|bad episode|best episode|worst episode|"
    r"weak (?:episode|hook|opening)|strong (?:episode|hook|opening)|"
    r"highly engaging|low engagement"
    r")\b",
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
    structural_identity: List[str] = field(default_factory=list)
    leverage_points: List[str] = field(default_factory=list)
    episode_structure: List[MetricRow] = field(default_factory=list)
    conversation_dynamics: List[MetricRow] = field(default_factory=list)
    listener_experience: List[str] = field(default_factory=list)
    compared_with_library: List[str] = field(default_factory=list)
    editorial_tradeoffs: List[str] = field(default_factory=list)
    structural_variance: List[str] = field(default_factory=list)
    template_playbook: Optional[dict] = None
    what_this_means: List[str] = field(default_factory=list)
    similar_to: Optional[str] = None
    topic_shift_note: Optional[str] = None
    measurement_stamp: dict = field(default_factory=dict)
    measurement_cohort_note: Optional[str] = None
    transcript_limitations: List[str] = field(default_factory=list)
    narrative_engine: Optional[dict] = None
    producer_notes: Optional[dict] = None
    producer_view: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "structural_identity": list(self.structural_identity),
            "leverage_points": list(self.leverage_points),
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
            "template_playbook": self.template_playbook,
            "what_this_means": list(self.what_this_means),
            "similar_to": self.similar_to,
            "topic_shift_note": self.topic_shift_note,
            "measurement_stamp": dict(self.measurement_stamp),
            "measurement_cohort_note": self.measurement_cohort_note,
            "transcript_limitations": list(self.transcript_limitations),
            "narrative_engine": self.narrative_engine,
            "producer_notes": self.producer_notes,
            "producer_view": self.producer_view,
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
    return template_id_from_features(f)


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


def _listener_questions(count: int, *, rhetorical_heavy: bool = False) -> str:
    if rhetorical_heavy:
        return (
            "Many question marks appear in the transcript — without speaker labels "
            "these read as rhetorical narration (diary/explainer pacing), not "
            "interviewer-led pivots."
        )
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
            "The episode holds one dominant narrative thread with few detected "
            "transition markers — produced storytelling rather than frequent scene breaks "
            "(sub-threads may still sit inside the arc)."
        )
    return (
        "Few pivot phrases or scene breaks were detected — "
        "either one dominant narrative thread or transitions that do not surface in the text."
    )


def _listener_balance(ratio: float, *, has_diarization: bool) -> Optional[str]:
    if not has_diarization:
        return None
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


def _transition_markers_value(count: int) -> str:
    if count == 0:
        return "None detected"
    return str(count)


def _transition_markers_note(count: int) -> Optional[str]:
    if count == 0:
        return (
            "No explicit transition markers in transcript — narrative continuity "
            "likely inferred rather than segmented (measures phrasing in text, not full story beats)."
        )
    return f"{count} explicit transition marker(s) detected in transcript text."


def _topic_shift_detection_note(count: int) -> Optional[str]:
    if count > 0:
        return None
    return (
        "Transition markers: none detected in the transcript. This counts explicit pivot "
        "phrases and breaks in text — not every sub-thread or scene change in the edit. "
        "Worth spot-checking against the audio."
    )


def _pattern_synthesis(template_id: str, f: EpisodeFeatures) -> str:
    if is_rhetorical_question_heavy(f):
        return (
            "Pattern: diary / explainer narration — question marks pace the story "
            "but the transcript reads as one voice without labeled interview handoffs."
        )
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
    if is_rhetorical_question_heavy(f):
        return [
            "Trade-off: rhetorical questions pace the diary — momentum from narration, "
            "not interview discovery.",
            "Trade-off: one voice in the transcript — clarity depends on re-hooks and "
            "orientation, not speaker handoffs.",
        ][:2]
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
                "Trade-off: the episode enters the story quickly and holds one dominant "
                "narrative thread — clarity stays high, with few detected pivots for "
                "side-path exploration."
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
    elif questions >= 12 and turns >= 4:
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
    if is_rhetorical_question_heavy(f):
        return (
            "Within your measured library, this episode has been observed in "
            "diary/explainer narration patterns (rhetorical question pacing) "
            "rather than labeled interview structure."
        )
    if template_id == "C":
        return (
            "Within your measured library, this episode has been observed in "
            "narrative-led story-first patterns (explanation blocks, sparse Q&A) "
            "rather than interview-heavy formats."
        )
    if template_id == "B":
        return (
            "Within your measured library, this episode has been observed in "
            "question-led interview patterns rather than sparse narrative structure."
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
    anchor_stamp = stamp_for_row(features)
    lib_excluded = 0
    show_excluded = 0

    if library is not None:
        lib = library
    elif hasattr(db, "execute"):
        lib, lib_excluded = load_library_benchmarks(db, anchor=features)
    else:
        lib = LibraryBenchmarks(
            n_measured=0,
            hook_seconds=[],
            intro_seconds=[],
            question_counts=[],
            speaking_turns=[],
            guest_ratios=[],
            topic_shifts=[],
        )

    hook = float(features.hook_length_seconds or 0)
    intro = float(features.intro_length_seconds or 0)
    questions = int(features.question_count or 0)
    turns = int(features.speaking_turns or 0)
    ratio = float(features.host_guest_ratio or 0.5)
    topic_shifts = int(features.topic_shift_count or 0)
    cta = bool(features.cta_present)

    template_id = _template_id(features)
    rhetorical = is_rhetorical_question_heavy(features)
    diarized = has_speaker_diarization(features)
    limits = transcript_limitation_notes(features)
    narrative_led = template_id == "C" or rhetorical
    playbook = None
    if template_id == "C" and not rhetorical:
        playbook = build_template_c_playbook(
            features, library_measured=lib.n_measured
        ).to_dict()

    structure = [
        MetricRow("Hook", _fmt_seconds(hook), benchmark_hook(hook, lib), None),
        MetricRow("Intro", _fmt_seconds(intro), benchmark_intro(intro, lib), None),
        MetricRow("CTA", "Present" if cta else "Not detected", None, None),
    ]

    dynamics = [
        MetricRow(
            "Questions",
            str(questions),
            benchmark_questions(questions, lib, rhetorical_heavy=rhetorical),
            "Rhetorical ? in narration" if rhetorical else None,
        ),
        MetricRow(
            "Speaking turns",
            str(turns) if diarized else "Not detected",
            benchmark_turns(turns, lib) if diarized else "No labeled speaker lines",
            None,
        ),
        MetricRow(
            "Guest talk ratio",
            _fmt_ratio(ratio) if diarized else "Not available",
            benchmark_guest_ratio(ratio, lib, turns=turns),
            None,
        ),
        MetricRow(
            "Transition markers",
            _transition_markers_value(topic_shifts),
            _transition_markers_note(topic_shifts),
            None,
        ),
    ]

    if template_id == "C" and not rhetorical:
        listener = template_c_listener_experience(features)
        if cta:
            listener.append(
                "A subscribe or follow-style call appears near the end — "
                "standard for produced public-media episodes."
            )
    else:
        listener = [
            _listener_opening(hook, intro),
            _listener_questions(questions, rhetorical_heavy=rhetorical),
            _listener_turns(turns),
            _listener_topic_arc(topic_shifts, template_id),
        ]
        balance = _listener_balance(ratio, has_diarization=diarized)
        if balance:
            listener.append(balance)
        cta_line = _listener_cta(cta)
        if cta_line:
            listener.append(cta_line)

    editorial = (
        playbook["trade_offs"]
        if playbook
        else _editorial_tradeoffs(features, template_id)
    )
    pattern_lines = (
        [playbook["tagline"], playbook["feels_like"]]
        if playbook
        else [_pattern_synthesis(template_id, features)]
    )
    similar = (
        playbook["similar_form"]
        if playbook
        else _similar_to(features, lib, template_id)
    )

    # Library percentile bullets are internal-only; Layer 4 uses band language via producer view.
    compared: List[str] = []

    podcast_name = None
    variance: List[str] = []
    leverage: List[str] = []
    identity: List[str] = []
    show_rows: List[EpisodeFeatures] = []
    show_lib = LibraryBenchmarks(
        n_measured=0,
        hook_seconds=[],
        intro_seconds=[],
        question_counts=[],
        speaking_turns=[],
        guest_ratios=[],
        topic_shifts=[],
    )
    if hasattr(db, "execute"):
        episode = db.execute(
            select(Episode)
            .where(Episode.id == features.episode_id)
            .options(joinedload(Episode.podcast))
        ).scalar_one_or_none()
        if episode:
            podcast_name = episode.podcast.name if episode.podcast else None
            show_rows, show_excluded = load_show_feature_rows(
                db,
                int(episode.podcast_id),
                exclude_episode_id=int(features.episode_id),
                anchor=features,
            )
            show_lib = library_from_rows(show_rows)
            variance = structural_variance_bullets(
                features,
                show_lib,
                podcast_name=podcast_name,
                rhetorical_heavy=rhetorical,
                has_diarization=diarized,
            )
            leverage = build_feed_leverage_points(
                features,
                show_lib,
                show_rows,
                feed_name=podcast_name,
            )

    if rhetorical:
        identity = [
            effective_form_label(template_id, features),
            (
                "Rhetorical question pacing in one voice — diary or explainer shape, "
                "not labeled interview handoffs."
            ),
        ]
    else:
        identity = build_structural_identity(
            features, template_id, playbook=playbook
        )

    cohort_excluded = lib_excluded + show_excluded

    producer = None
    narrative_engine = None
    if hasattr(db, "get"):
        episode_row = db.get(Episode, features.episode_id)
        if episode_row and (episode_row.full_transcript or "").strip():
            seg_rows = (
                db.query(TranscriptSegment)
                .filter(TranscriptSegment.episode_id == features.episode_id)
                .order_by(TranscriptSegment.start_time)
                .all()
            )
            segments = [
                {"start": r.start_time, "end": r.end_time, "text": r.text}
                for r in seg_rows
            ]
            narrative_engine = build_narrative_engine_map(
                episode_row.full_transcript,
                segments or None,
            ).to_dict()
            producer = build_producer_notes(
                episode_row.full_transcript,
                segments or None,
                intro_seconds=float(features.intro_length_seconds or 0),
                topic_shift_count=int(features.topic_shift_count or 0),
            ).to_dict()

    audio_motion = None
    if hasattr(db, "get"):
        audio_motion = load_audio_motion(db, int(features.episode_id))

    producer_view = build_producer_view(
        structural_identity=identity,
        leverage_points=leverage,
        narrative_engine=narrative_engine,
        producer_notes=producer,
        audio_motion=audio_motion,
        transcript_limitations=limits,
    )

    report = CoachingReport(
        structural_identity=identity,
        leverage_points=leverage,
        episode_structure=structure,
        conversation_dynamics=dynamics,
        listener_experience=listener,
        compared_with_library=compared,
        editorial_tradeoffs=editorial,
        structural_variance=variance,
        template_playbook=playbook,
        what_this_means=pattern_lines,
        similar_to=similar,
        topic_shift_note=_topic_shift_detection_note(topic_shifts),
        measurement_stamp=stamp_dict(anchor_stamp),
        measurement_cohort_note=cohort_note(cohort_excluded),
        transcript_limitations=limits,
        narrative_engine=narrative_engine,
        producer_notes=producer,
        producer_view=producer_view,
    )
    _assert_no_forbidden(report)
    return report


def synthesis_insight_text(report: CoachingReport) -> str:
    """Short lead paragraph for API ``insight_text`` field."""
    if report.template_playbook:
        lead = [
            report.template_playbook.get("tagline", ""),
            report.template_playbook.get("feels_like", ""),
        ]
        body = " ".join(x for x in lead if x)
    else:
        body = " ".join(report.listener_experience[:2]) if report.listener_experience else ""
    if not body:
        body = "Structure measured for this episode."
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
    chunks.extend(report.structural_identity)
    chunks.extend(report.leverage_points)
    if report.template_playbook:
        for key in ("tagline", "feels_like", "similar_form"):
            val = report.template_playbook.get(key)
            if val:
                chunks.append(val)
        for key in ("review_these", "how_its_built", "trade_offs", "leverage_points"):
            chunks.extend(report.template_playbook.get(key) or [])
    chunks.extend(report.what_this_means)
    if report.similar_to:
        chunks.append(report.similar_to)
    if report.topic_shift_note:
        chunks.append(report.topic_shift_note)
    if report.measurement_cohort_note:
        chunks.append(report.measurement_cohort_note)
    if report.narrative_engine:
        chunks.extend(report.narrative_engine.get("engine_notes") or [])
        # Timeline labels only — detail/snippet are transcript evidence, not coaching copy.
        for ev in report.narrative_engine.get("timeline") or []:
            label = ev.get("label")
            if label:
                chunks.append(label)
    if report.producer_notes:
        chunks.extend(report.producer_notes.get("bullets") or [])
        chunks.extend(report.producer_notes.get("edit_flags") or [])
        for row in report.producer_notes.get("metrics") or []:
            for part in (row.get("note"),):
                if part:
                    chunks.append(part)
    for text in chunks:
        if _FORBIDDEN.search(text):
            raise RuntimeError(f"Coaching copy violated forbidden language: {text[:80]}")
