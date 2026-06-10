"""Layer A — per-episode narrative engine map (timeline, not trends).

Narrative Engine v2: producer-level reasoning via Gemini semantic pass.
Rule-based fallback supplies timing cues only — no per-question open loops.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from backend.features.rule_based import _SPEAKER_LINE, _words
from backend.llm_service import (
    narrative_semantic_enabled,
    run_gemini_json,
)

_RESOLUTION = re.compile(
    r"\b("
    r"that'?s why|so in the end|the answer is|which explains|"
    r"and that'?s (?:the|our) story|mystery solved|turns out that|"
    r"so that'?s|which is why|in other words,? that means"
    r")\b",
    re.I,
)

_PARTIAL_RESOLUTION = re.compile(
    r"\b("
    r"partly|sort of|not quite|but not entirely|to some extent|"
    r"partially|at least partly|in part"
    r")\b",
    re.I,
)

_DEPENDENCY_ADD = re.compile(
    r"\b("
    r"but there'?s|which raises|that leads to|another question|"
    r"except|however,? there|but here'?s|the twist|complication"
    r")\b",
    re.I,
)

_QUESTION = re.compile(r"[^.!?]*\?", re.M)

_NARRATIVE_V2_PROMPT = """You are a podcast narrative editor producing a producer-level narrative summary.

Analyze MEANING, not wording. Your job is editorial intelligence — not transcript statistics.

CRITICAL — eliminate loop inflation:
- Do NOT treat every question as a separate narrative unit.
- Cluster paraphrases, restatements, rhetorical questions, and follow-up wording BEFORE analysis.
- Surface questions like "What is wrong with us?", "Why don't we use vacation?", and
  "Why don't Americans prioritize vacations?" are ONE curiosity — not three loops.

Infer one primary narrative question the episode is fundamentally trying to explain.

Supporting threads are major EXPLANATORY PATHS (historical, economic, cultural, psychological,
policy, institutional) — NOT individual transcript questions. Group related moments under
the same thread. Maximum 7 supporting threads.

Narrative promise:
- Infer what answer the episode implicitly promises, even if never stated directly.

Narrative payoff:
- Do NOT ask "Was every question answered?"
- Ask "Would a reasonable listener feel the central curiosity was satisfied?"
- Status: fully_delivered | mostly_delivered | partially_delivered | not_delivered
- Confidence: high | medium | low (and confidence_score 0.0-1.0)
- Recognize implied answers, indirect explanations, callbacks, and thematic resolutions.

Remaining open questions: only meaningful unresolved issues (max 4). Omit rhetorical restatements.

Copy rules:
- Neutral editorial tone. No coaching verdict language (no "good/bad episode", "you should", "rank").
- Use "appears", "suggests", "may" when uncertain.

Return JSON only:
{
  "story_being_told": "what story this episode is telling",
  "primary_question": "single central narrative question",
  "curiosity_driver": "what curiosity drives the episode",
  "narrative_promise": "one sentence — what payoff is promised to the listener",
  "payoff": {
    "status": "fully_delivered|mostly_delivered|partially_delivered|not_delivered",
    "confidence": "high|medium|low",
    "confidence_score": 0.0,
    "rationale": ""
  },
  "supporting_threads": [
    {
      "thread_label": "e.g. Historical roots of work culture",
      "status": "delivered|partially_delivered|open",
      "evidence_summary": "how this explanatory path is addressed semantically"
    }
  ],
  "conclusions_reached": ["major conclusions the episode reaches"],
  "remaining_open_questions": ["only meaningful unresolved issues"],
  "timeline_beats": [
    {
      "time_seconds": 0,
      "event_type": "promise_established|explanation|partial_payoff|payoff|callback",
      "label": "producer-facing beat",
      "detail": "editorial meaning of this beat"
    }
  ]
}
""".strip()

_MAX_TRANSCRIPT_CHARS = 120_000

# Per-process cache: the same transcript is requested by /translation,
# /report/producer, and /report/actions on a single episode open — one
# Gemini call should serve all of them.
_SEMANTIC_CACHE: Dict[str, tuple[float, "NarrativeEngineMap"]] = {}
_SEMANTIC_CACHE_TTL_SECONDS = 24 * 3600.0
_SEMANTIC_FAILURE_TTL_SECONDS = 600.0
_SEMANTIC_CACHE_MAX = 64
_SEMANTIC_FAILED_AT: Dict[str, float] = {}


def clear_narrative_cache() -> None:
    _SEMANTIC_CACHE.clear()
    _SEMANTIC_FAILED_AT.clear()


def _transcript_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()


@dataclass
class TimelineEvent:
    time_seconds: float
    event_type: str
    label: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "time_seconds": round(self.time_seconds, 1),
            "time_label": _fmt_time(self.time_seconds),
            "event_type": self.event_type,
            "label": self.label,
            "detail": self.detail,
        }


@dataclass
class OpenLoopState:
    opened_at: float
    closed_at: Optional[float]
    snippet: str
    status: str  # open | partial | closed

    def to_dict(self) -> dict:
        lifespan = (
            (self.closed_at or self.opened_at) - self.opened_at
            if self.closed_at
            else None
        )
        return {
            "opened_at": round(self.opened_at, 1),
            "opened_label": _fmt_time(self.opened_at),
            "closed_at": round(self.closed_at, 1) if self.closed_at else None,
            "closed_label": _fmt_time(self.closed_at) if self.closed_at else None,
            "lifespan_seconds": round(lifespan, 1) if lifespan and self.closed_at else None,
            "lifespan_label": _fmt_time(lifespan)
            if lifespan and self.closed_at
            else "appears open (no closure detected in transcript)",
            "snippet": self.snippet[:120],
            "status": self.status,
        }


@dataclass
class NarrativeSummary:
    primary_question: str = ""
    story_being_told: str = ""
    curiosity_driver: str = ""
    narrative_promise: str = ""
    payoff_status: str = ""
    payoff_label: str = ""
    confidence: str = ""
    confidence_score: Optional[float] = None
    payoff_rationale: str = ""
    supporting_threads: List[Dict[str, Any]] = field(default_factory=list)
    conclusions_reached: List[str] = field(default_factory=list)
    remaining_open_questions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "primary_question": self.primary_question,
            "story_being_told": self.story_being_told,
            "curiosity_driver": self.curiosity_driver,
            "narrative_promise": self.narrative_promise,
            "payoff_status": self.payoff_status,
            "payoff_label": self.payoff_label,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "payoff_rationale": self.payoff_rationale,
            "supporting_threads": list(self.supporting_threads),
            "conclusions_reached": list(self.conclusions_reached),
            "remaining_open_questions": list(self.remaining_open_questions),
        }


@dataclass
class NarrativeEngineMap:
    timeline: List[TimelineEvent] = field(default_factory=list)
    open_loops: List[OpenLoopState] = field(default_factory=list)
    engine_notes: List[str] = field(default_factory=list)
    narrative_summary: Optional[NarrativeSummary] = None
    central_topic: Optional[str] = None
    listener_curiosity: Optional[str] = None
    narrative_promise: Optional[Dict[str, str]] = None
    explanatory_threads: List[Dict[str, Any]] = field(default_factory=list)
    satisfaction: Optional[Dict[str, Any]] = None
    editorial_summary: Optional[Dict[str, Any]] = None
    analysis_mode: str = "rule_based"
    engine_version: str = "v2"

    def to_dict(self) -> dict:
        out: Dict[str, Any] = {
            "timeline": [e.to_dict() for e in self.timeline],
            "open_loops": [o.to_dict() for o in self.open_loops],
            "engine_notes": list(self.engine_notes),
            "analysis_mode": self.analysis_mode,
            "engine_version": self.engine_version,
        }
        if self.narrative_summary:
            out["narrative_summary"] = self.narrative_summary.to_dict()
        if self.central_topic:
            out["central_topic"] = self.central_topic
        if self.listener_curiosity:
            out["listener_curiosity"] = self.listener_curiosity
        if self.narrative_promise:
            out["narrative_promise"] = dict(self.narrative_promise)
        if self.explanatory_threads:
            out["explanatory_threads"] = list(self.explanatory_threads)
        if self.satisfaction:
            out["satisfaction"] = dict(self.satisfaction)
        if self.editorial_summary:
            out["editorial_summary"] = dict(self.editorial_summary)
        return out


def _fmt_time(seconds: float) -> str:
    s = max(0.0, float(seconds or 0))
    m = int(s // 60)
    rem = int(round(s % 60))
    return f"{m}:{rem:02d}"


def _clean_line(text: str) -> str:
    return _SPEAKER_LINE.sub("", (text or "").strip()).strip()


def _iter_moments(
    transcript: str,
    segments: Optional[Sequence[Dict[str, Any]]],
) -> List[tuple[float, str]]:
    """(timestamp_seconds, line_text) in order."""
    moments: List[tuple[float, str]] = []
    if segments:
        for seg in segments:
            text = _clean_line(str(seg.get("text") or ""))
            if not text:
                continue
            try:
                t = float(seg.get("start") or 0)
            except (TypeError, ValueError):
                t = 0.0
            moments.append((t, text))
        return moments

    t = 0.0
    for ln in (transcript or "").splitlines():
        s = _clean_line(ln)
        if not s:
            continue
        moments.append((t, s))
        t += _words(ln) / 2.5
    return moments


def _format_transcript_for_llm(moments: Sequence[tuple[float, str]]) -> str:
    lines = [f"[{_fmt_time(t)}] {text}" for t, text in moments]
    body = "\n".join(lines)
    if len(body) <= _MAX_TRANSCRIPT_CHARS:
        return body
    return (
        body[:_MAX_TRANSCRIPT_CHARS]
        + "\n\n[Transcript truncated for analysis — opening and early beats preserved.]"
    )


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _payoff_label(status: str) -> str:
    labels = {
        "fully_delivered": "Fully Delivered",
        "mostly_delivered": "Mostly Delivered",
        "partially_delivered": "Partially Delivered",
        "not_delivered": "Not Delivered",
        "fully_satisfied": "Fully Delivered",
        "mostly_satisfied": "Mostly Delivered",
        "partially_satisfied": "Partially Delivered",
        "unsatisfied": "Not Delivered",
    }
    return labels.get((status or "").strip().lower(), status or "Unknown")


def _thread_delivery_label(status: str) -> str:
    labels = {
        "delivered": "Delivered",
        "partially_delivered": "Partially Delivered",
        "open": "Open",
        "resolved": "Delivered",
        "partial": "Partially Delivered",
    }
    return labels.get((status or "").strip().lower(), status or "Open")


def _normalize_confidence(raw: Any, score: Optional[float]) -> str:
    text = str(raw or "").strip().lower()
    if text in ("high", "medium", "low"):
        return text.capitalize()
    if score is not None:
        if score >= 0.75:
            return "High"
        if score >= 0.5:
            return "Medium"
        return "Low"
    return ""


def _parse_supporting_threads(raw_threads: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw_threads, list):
        return []
    threads: List[Dict[str, Any]] = []
    for item in raw_threads[:7]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("thread_label") or "").strip()
        if not label:
            continue
        status = str(item.get("status") or "open").strip().lower()
        threads.append(
            {
                "thread_label": label,
                "status": status,
                "status_label": _thread_delivery_label(status),
                "evidence_summary": str(item.get("evidence_summary") or "").strip(),
            }
        )
    return threads


def _build_producer_notes(summary: NarrativeSummary) -> List[str]:
    notes: List[str] = []
    if summary.primary_question:
        notes.append(f"Primary question: {summary.primary_question}")
    if summary.narrative_promise:
        notes.append(f"Narrative promise: {summary.narrative_promise}")
    if summary.payoff_label:
        conf = summary.confidence or ""
        conf_txt = f" ({conf} confidence)" if conf else ""
        notes.append(f"Payoff — {summary.payoff_label}{conf_txt}")
        if summary.payoff_rationale:
            notes.append(summary.payoff_rationale)
    if summary.conclusions_reached:
        notes.append(f"Conclusion: {summary.conclusions_reached[0]}")
    if summary.remaining_open_questions:
        notes.append(
            f"Remaining open: {summary.remaining_open_questions[0]}"
        )
    return notes[:6]


def _legacy_fields_from_summary(summary: NarrativeSummary) -> Dict[str, Any]:
    """Backward-compatible aliases for API consumers on older shapes."""
    verdict_map = {
        "fully_delivered": "fully_satisfied",
        "mostly_delivered": "mostly_satisfied",
        "partially_delivered": "partially_satisfied",
        "not_delivered": "unsatisfied",
    }
    return {
        "central_topic": summary.story_being_told or None,
        "listener_curiosity": summary.curiosity_driver or summary.primary_question or None,
        "narrative_promise": {
            "curiosity_created": summary.curiosity_driver,
            "question_invited": summary.primary_question,
            "answer_promised": summary.narrative_promise,
        }
        if summary.narrative_promise or summary.primary_question
        else None,
        "explanatory_threads": [
            {
                "thread_label": t["thread_label"],
                "status": t["status"],
                "evidence_summary": t.get("evidence_summary", ""),
                "surfaced_phrases": [],
            }
            for t in summary.supporting_threads
        ],
        "satisfaction": {
            "verdict": verdict_map.get(summary.payoff_status, summary.payoff_status),
            "confidence": summary.confidence_score,
            "rationale": summary.payoff_rationale,
        }
        if summary.payoff_status
        else None,
        "editorial_summary": {
            "story_being_told": summary.story_being_told,
            "curiosity_driver": summary.curiosity_driver,
            "explanations_that_landed": summary.conclusions_reached[:6],
            "questions_still_open": summary.remaining_open_questions[:4],
            "listener_payoff_assessment": summary.payoff_rationale,
        },
    }


def _build_semantic_narrative_map(
    transcript: str,
    moments: Sequence[tuple[float, str]],
) -> Optional[NarrativeEngineMap]:
    user_prompt = (
        "Produce a producer-level narrative summary for this podcast episode. "
        "Cluster semantically equivalent questions before identifying threads.\n\n"
        f"{_format_transcript_for_llm(moments)}"
    )
    raw = run_gemini_json(
        system_prompt=_NARRATIVE_V2_PROMPT,
        user_prompt=user_prompt,
    )
    if not raw:
        return None

    primary = str(raw.get("primary_question") or "").strip()
    if not primary:
        return None

    payoff_raw = raw.get("payoff") or {}
    payoff_status = ""
    payoff_rationale = ""
    confidence = ""
    confidence_score = None
    if isinstance(payoff_raw, dict):
        payoff_status = str(payoff_raw.get("status") or "").strip().lower()
        payoff_rationale = str(payoff_raw.get("rationale") or "").strip()
        confidence = _normalize_confidence(
            payoff_raw.get("confidence"),
            None,
        )
        try:
            score_raw = payoff_raw.get("confidence_score")
            confidence_score = round(float(score_raw), 2) if score_raw is not None else None
        except (TypeError, ValueError):
            confidence_score = None
        if not confidence:
            confidence = _normalize_confidence("", confidence_score)

    supporting = _parse_supporting_threads(raw.get("supporting_threads"))
    conclusions = [
        str(x).strip()
        for x in (raw.get("conclusions_reached") or [])
        if str(x).strip()
    ][:6]
    remaining = [
        str(x).strip()
        for x in (raw.get("remaining_open_questions") or [])
        if str(x).strip()
    ][:4]

    summary = NarrativeSummary(
        primary_question=primary,
        story_being_told=str(raw.get("story_being_told") or "").strip(),
        curiosity_driver=str(raw.get("curiosity_driver") or "").strip(),
        narrative_promise=str(raw.get("narrative_promise") or "").strip(),
        payoff_status=payoff_status,
        payoff_label=_payoff_label(payoff_status),
        confidence=confidence,
        confidence_score=confidence_score,
        payoff_rationale=payoff_rationale,
        supporting_threads=supporting,
        conclusions_reached=conclusions,
        remaining_open_questions=remaining,
    )

    events: List[TimelineEvent] = []
    for beat in (raw.get("timeline_beats") or [])[:20]:
        if not isinstance(beat, dict):
            continue
        label = str(beat.get("label") or "").strip()
        if not label:
            continue
        events.append(
            TimelineEvent(
                time_seconds=_safe_float(beat.get("time_seconds"), 0.0),
                event_type=str(beat.get("event_type") or "beat").strip(),
                label=label,
                detail=str(beat.get("detail") or "").strip()[:200],
            )
        )
    events.sort(key=lambda e: e.time_seconds)

    legacy = _legacy_fields_from_summary(summary)
    return NarrativeEngineMap(
        timeline=events,
        open_loops=[],
        engine_notes=_build_producer_notes(summary),
        narrative_summary=summary,
        central_topic=legacy["central_topic"],
        listener_curiosity=legacy["listener_curiosity"],
        narrative_promise=legacy["narrative_promise"],
        explanatory_threads=legacy["explanatory_threads"],
        satisfaction=legacy["satisfaction"],
        editorial_summary=legacy["editorial_summary"],
        analysis_mode="semantic",
        engine_version="v2",
    )


def _extract_questions(text: str) -> List[str]:
    return [q.strip() for q in _QUESTION.findall(text or "") if len(q.strip()) > 8]


def _detect_false_resolution(
    moments: Sequence[tuple[float, str]], idx: int
) -> bool:
    """Closure phrasing followed by a new question within ~90s."""
    t0, line = moments[idx]
    if not _RESOLUTION.search(line):
        return False
    for t, nxt in moments[idx + 1 : idx + 8]:
        if t - t0 > 90:
            break
        if "?" in nxt:
            return True
    return False


def _first_early_question(
    moments: Sequence[tuple[float, str]], total_runtime: float
) -> Optional[tuple[float, str]]:
    """Best-effort primary question — one surface cue only, not a loop inventory."""
    for t, line in moments:
        questions = _extract_questions(line)
        if not questions:
            continue
        if t <= max(90.0, total_runtime * 0.3):
            return t, questions[0]
    for t, line in moments:
        questions = _extract_questions(line)
        if questions:
            return t, questions[0]
    return None


def _build_rule_based_narrative_map(
    text: str,
    moments: Sequence[tuple[float, str]],
) -> NarrativeEngineMap:
    total_runtime = moments[-1][0] if moments else 0.0
    events: List[TimelineEvent] = []
    primary_open: Optional[float] = None
    primary_close: Optional[float] = None
    early = _first_early_question(moments, total_runtime)

    if early:
        t, q = early
        primary_open = t
        events.append(
            TimelineEvent(
                t,
                "primary_question",
                "Possible primary question (transcript cue only)",
                q[:100],
            )
        )

    for i, (t, line) in enumerate(moments):
        if _DEPENDENCY_ADD.search(line):
            events.append(
                TimelineEvent(
                    t,
                    "dependency",
                    "New dependency on main thread",
                    line[:100],
                )
            )

        if _PARTIAL_RESOLUTION.search(line):
            events.append(
                TimelineEvent(
                    t,
                    "partial_resolution",
                    "Partial resolution — engine still active",
                    line[:100],
                )
            )
        if _RESOLUTION.search(line):
            false_close = _detect_false_resolution(moments, i)
            if false_close:
                events.append(
                    TimelineEvent(
                        t,
                        "false_resolution",
                        "Possible early resolution — question returns",
                        line[:100],
                    )
                )
            else:
                events.append(
                    TimelineEvent(
                        t,
                        "resolution",
                        "Major payoff / closure signal",
                        line[:100],
                    )
                )
                if primary_open is not None and primary_close is None:
                    primary_close = t

    events.sort(key=lambda e: e.time_seconds)

    notes: List[str] = []
    summary: Optional[NarrativeSummary] = None
    if early:
        _, q = early
        payoff_status = "partially_delivered" if primary_close else "not_delivered"
        summary = NarrativeSummary(
            primary_question=q[:200],
            narrative_promise="Unclear without semantic analysis — transcript cue only.",
            payoff_status=payoff_status,
            payoff_label=_payoff_label(payoff_status),
            confidence="Low",
            payoff_rationale=(
                f"Closure language detected near {_fmt_time(primary_close)}"
                if primary_close
                else "No clear closure detected — semantic pass recommended."
            ),
        )
        notes.append(f"Primary question (surface cue): {q[:120]}")
        if primary_close:
            notes.append(
                f"Possible payoff near {_fmt_time(primary_close)} — explicit transcript cue only"
            )
        else:
            notes.append(
                "Payoff unclear from transcript cues — semantic narrative pass recommended."
            )

    notes.append(
        "Rule-based timing cues only — enable GEMINI_API_KEY + gemini-2.5-flash "
        "for producer-level narrative summary (v2)."
    )

    return NarrativeEngineMap(
        timeline=events[:20],
        open_loops=[],
        engine_notes=notes[:6],
        narrative_summary=summary,
        analysis_mode="rule_based",
        engine_version="v2",
    )


def build_narrative_engine_map(
    transcript: str,
    segments: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    allow_semantic: bool = True,
) -> NarrativeEngineMap:
    text = (transcript or "").strip()
    if len(text) < 40:
        return NarrativeEngineMap(
            engine_notes=["Transcript too short for narrative engine map."]
        )

    moments = _iter_moments(text, segments)
    if not moments:
        return NarrativeEngineMap(engine_notes=["No timed moments detected in transcript."])

    if allow_semantic and narrative_semantic_enabled():
        key = _transcript_key(text)
        now = time.time()

        cached = _SEMANTIC_CACHE.get(key)
        if cached and now - cached[0] < _SEMANTIC_CACHE_TTL_SECONDS:
            return cached[1]

        failed_at = _SEMANTIC_FAILED_AT.get(key)
        if not (failed_at and now - failed_at < _SEMANTIC_FAILURE_TTL_SECONDS):
            semantic = _build_semantic_narrative_map(text, moments)
            if semantic:
                if len(_SEMANTIC_CACHE) >= _SEMANTIC_CACHE_MAX:
                    oldest = min(_SEMANTIC_CACHE, key=lambda k: _SEMANTIC_CACHE[k][0])
                    _SEMANTIC_CACHE.pop(oldest, None)
                _SEMANTIC_CACHE[key] = (now, semantic)
                _SEMANTIC_FAILED_AT.pop(key, None)
                return semantic
            _SEMANTIC_FAILED_AT[key] = now

    return _build_rule_based_narrative_map(text, moments)
