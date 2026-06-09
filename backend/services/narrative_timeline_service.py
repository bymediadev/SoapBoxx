"""Layer A — per-episode narrative engine map (timeline, not trends).

Semantic narrative understanding via Gemini when configured; rule-based fallback
for timing cues when the API is unavailable.
"""

from __future__ import annotations

import re
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

_NARRATIVE_SEMANTIC_PROMPT = """You are a podcast narrative editor analyzing one episode transcript.

Your job is editorial comprehension — not transcript annotation and not coaching advice.

Reason at the CONCEPT level, not the sentence level:
- Merge paraphrases and related questions into one explanatory thread.
- Recognize implied answers, indirect explanations, narrative callbacks, and thematic resolutions.
- Do NOT create separate loops for surface questions that express the same underlying curiosity.

Example (one thread, not four):
Surface lines: "Why do Americans take less vacation?", "What is wrong with us?",
"Why don't we use our vacation days?", "Why are Europeans different?"
Merged thread: "Why American work culture produces less vacation usage than other wealthy countries."

At the opening, infer the narrative promise even when it is never stated directly:
- What curiosity is being created?
- What question is the audience invited to follow?
- What answer is implicitly promised?

Satisfaction scoring:
- Do NOT ask "Was every question answered?"
- Ask "Would a reasonable listener feel the central curiosity was satisfied by the end?"
- Verdict must be one of: fully_satisfied, mostly_satisfied, partially_satisfied, unsatisfied
- Include confidence 0.0-1.0 and a short rationale.

Copy rules:
- Neutral editorial tone only.
- Never use coaching verdict language (no "good/bad episode", "you should", "score", "rank").
- Use "appears", "suggests", "may" when uncertain.

Return JSON only with this shape:
{
  "central_topic": "one sentence",
  "listener_curiosity": "one sentence — the curiosity driving the episode",
  "narrative_promise": {
    "curiosity_created": "",
    "question_invited": "",
    "answer_promised": ""
  },
  "explanatory_threads": [
    {
      "thread_label": "concept-level thread label",
      "status": "resolved|partial|open",
      "evidence_summary": "how the episode addresses this thread semantically",
      "surfaced_phrases": ["distinct transcript phrases merged into this thread"],
      "approx_open_seconds": 0,
      "approx_close_seconds": null
    }
  ],
  "satisfaction": {
    "verdict": "fully_satisfied|mostly_satisfied|partially_satisfied|unsatisfied",
    "confidence": 0.0,
    "rationale": ""
  },
  "editorial_summary": {
    "story_being_told": "",
    "curiosity_driver": "",
    "explanations_that_landed": ["..."],
    "questions_still_open": ["..."],
    "listener_payoff_assessment": ""
  },
  "timeline_beats": [
    {
      "time_seconds": 0,
      "event_type": "promise_established|thread_opened|explanation|partial_resolution|resolution|callback",
      "label": "short producer-facing beat label",
      "detail": "what this beat means editorially"
    }
  ]
}
""".strip()

_MAX_TRANSCRIPT_CHARS = 120_000


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
class NarrativeEngineMap:
    timeline: List[TimelineEvent] = field(default_factory=list)
    open_loops: List[OpenLoopState] = field(default_factory=list)
    engine_notes: List[str] = field(default_factory=list)
    central_topic: Optional[str] = None
    listener_curiosity: Optional[str] = None
    narrative_promise: Optional[Dict[str, str]] = None
    explanatory_threads: List[Dict[str, Any]] = field(default_factory=list)
    satisfaction: Optional[Dict[str, Any]] = None
    editorial_summary: Optional[Dict[str, Any]] = None
    analysis_mode: str = "rule_based"

    def to_dict(self) -> dict:
        out = {
            "timeline": [e.to_dict() for e in self.timeline],
            "open_loops": [o.to_dict() for o in self.open_loops],
            "engine_notes": list(self.engine_notes),
            "analysis_mode": self.analysis_mode,
        }
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


def _thread_status_to_loop(status: str) -> str:
    s = (status or "").strip().lower()
    if s in ("resolved", "closed"):
        return "closed"
    if s in ("partial", "partially_resolved"):
        return "partial"
    return "open"


def _satisfaction_label(verdict: str) -> str:
    labels = {
        "fully_satisfied": "Fully satisfied",
        "mostly_satisfied": "Mostly satisfied",
        "partially_satisfied": "Partially satisfied",
        "unsatisfied": "Unsatisfied",
    }
    return labels.get((verdict or "").strip().lower(), verdict or "Unknown")


def _build_semantic_narrative_map(
    transcript: str,
    moments: Sequence[tuple[float, str]],
) -> Optional[NarrativeEngineMap]:
    user_prompt = (
        "Analyze this podcast episode transcript for narrative promise, explanatory "
        "threads, and listener satisfaction.\n\n"
        f"{_format_transcript_for_llm(moments)}"
    )
    raw = run_gemini_json(
        system_prompt=_NARRATIVE_SEMANTIC_PROMPT,
        user_prompt=user_prompt,
    )
    if not raw:
        return None

    threads_raw = raw.get("explanatory_threads") or []
    if not isinstance(threads_raw, list):
        threads_raw = []

    threads: List[Dict[str, Any]] = []
    loops: List[OpenLoopState] = []
    for item in threads_raw[:6]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("thread_label") or "").strip()
        if not label:
            continue
        status = str(item.get("status") or "open").strip().lower()
        opened = _safe_float(item.get("approx_open_seconds"), 0.0)
        closed_raw = item.get("approx_close_seconds")
        closed = _safe_float(closed_raw) if closed_raw is not None else None
        loop_status = _thread_status_to_loop(status)
        threads.append(
            {
                "thread_label": label,
                "status": status,
                "evidence_summary": str(item.get("evidence_summary") or "").strip(),
                "surfaced_phrases": [
                    str(p).strip()
                    for p in (item.get("surfaced_phrases") or [])
                    if str(p).strip()
                ][:6],
            }
        )
        loops.append(
            OpenLoopState(
                opened_at=opened,
                closed_at=closed if loop_status == "closed" else None,
                snippet=label,
                status=loop_status,
            )
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

    promise_raw = raw.get("narrative_promise") or {}
    narrative_promise = (
        {
            "curiosity_created": str(promise_raw.get("curiosity_created") or "").strip(),
            "question_invited": str(promise_raw.get("question_invited") or "").strip(),
            "answer_promised": str(promise_raw.get("answer_promised") or "").strip(),
        }
        if isinstance(promise_raw, dict)
        else None
    )

    satisfaction_raw = raw.get("satisfaction") or {}
    satisfaction = None
    if isinstance(satisfaction_raw, dict) and satisfaction_raw.get("verdict"):
        conf = satisfaction_raw.get("confidence")
        try:
            confidence = round(float(conf), 2) if conf is not None else None
        except (TypeError, ValueError):
            confidence = None
        satisfaction = {
            "verdict": str(satisfaction_raw.get("verdict") or "").strip().lower(),
            "confidence": confidence,
            "rationale": str(satisfaction_raw.get("rationale") or "").strip(),
        }

    editorial_raw = raw.get("editorial_summary") or {}
    editorial_summary = None
    if isinstance(editorial_raw, dict):
        editorial_summary = {
            "story_being_told": str(editorial_raw.get("story_being_told") or "").strip(),
            "curiosity_driver": str(editorial_raw.get("curiosity_driver") or "").strip(),
            "explanations_that_landed": [
                str(x).strip()
                for x in (editorial_raw.get("explanations_that_landed") or [])
                if str(x).strip()
            ][:6],
            "questions_still_open": [
                str(x).strip()
                for x in (editorial_raw.get("questions_still_open") or [])
                if str(x).strip()
            ][:6],
            "listener_payoff_assessment": str(
                editorial_raw.get("listener_payoff_assessment") or ""
            ).strip(),
        }

    notes: List[str] = []
    central = str(raw.get("central_topic") or "").strip()
    curiosity = str(raw.get("listener_curiosity") or "").strip()
    if central:
        notes.append(f"Central topic: {central}")
    if curiosity:
        notes.append(f"Listener curiosity: {curiosity}")
    if narrative_promise and narrative_promise.get("answer_promised"):
        notes.append(
            f"Implied narrative promise: {narrative_promise['answer_promised']}"
        )
    if satisfaction:
        conf = satisfaction.get("confidence")
        conf_txt = f" (confidence {conf})" if conf is not None else ""
        notes.append(
            f"Curiosity payoff — {_satisfaction_label(satisfaction['verdict'])}{conf_txt}: "
            f"{satisfaction.get('rationale', '')}"
        )
    if editorial_summary:
        landed = editorial_summary.get("explanations_that_landed") or []
        if landed:
            notes.append(f"Explanations that landed: {landed[0]}")
        open_q = editorial_summary.get("questions_still_open") or []
        if open_q:
            notes.append(f"Questions still open: {open_q[0]}")

    if not threads and not events:
        return None

    return NarrativeEngineMap(
        timeline=events,
        open_loops=loops,
        engine_notes=notes[:8],
        central_topic=central or None,
        listener_curiosity=curiosity or None,
        narrative_promise=narrative_promise,
        explanatory_threads=threads,
        satisfaction=satisfaction,
        editorial_summary=editorial_summary,
        analysis_mode="semantic",
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


def _build_rule_based_narrative_map(
    text: str,
    moments: Sequence[tuple[float, str]],
) -> NarrativeEngineMap:
    total_runtime = moments[-1][0] if moments else 0.0
    events: List[TimelineEvent] = []
    loops: List[OpenLoopState] = []
    primary_idx: Optional[int] = None

    for i, (t, line) in enumerate(moments):
        questions = _extract_questions(line)
        for q in questions:
            is_primary = primary_idx is None and (
                t <= max(60.0, total_runtime * 0.25) or len(loops) == 0
            )
            if is_primary:
                primary_idx = len(loops)
                events.append(
                    TimelineEvent(
                        t,
                        "primary_question",
                        "Possible primary question (transcript)",
                        q[:100],
                    )
                )
            else:
                events.append(
                    TimelineEvent(
                        t,
                        "sub_question",
                        "Possible follow-up question (transcript)",
                        q[:100],
                    )
                )
            loops.append(
                OpenLoopState(opened_at=t, closed_at=None, snippet=q, status="open")
            )

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
            for loop in reversed(loops):
                if loop.status == "open" and loop.opened_at <= t:
                    loop.status = "partial"
                    break

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
                for loop in reversed(loops):
                    if loop.status in ("open", "partial") and loop.opened_at <= t:
                        loop.closed_at = t
                        loop.status = "closed"
                        break

    events.sort(key=lambda e: e.time_seconds)

    notes: List[str] = []
    if loops:
        primary = loops[primary_idx or 0]
        if primary.closed_at:
            notes.append(
                f"Possible primary thread at {_fmt_time(primary.opened_at)} — "
                f"closure language detected near {_fmt_time(primary.closed_at)}"
            )
        else:
            notes.append(
                f"Possible primary thread at {_fmt_time(primary.opened_at)} — "
                "appears unresolved at episode end (no clear closure in transcript)"
            )
        if primary.closed_at and total_runtime > 0:
            pct = round(100 * primary.closed_at / total_runtime)
            notes.append(
                f"Main thread closure at {_fmt_time(primary.closed_at)} "
                f"({pct}% through runtime)"
            )
        elif not primary.closed_at:
            notes.append(
                f"Main-thread payoff may still be open near {_fmt_time(total_runtime)} — "
                "based on transcript cues only"
            )

    open_at_end = [l for l in loops if l.status in ("open", "partial")]
    if len(open_at_end) > 1:
        notes.append(
            f"{len(open_at_end)} thread(s) appear unresolved at episode end — "
            "stacked open loops in transcript"
        )

    false_events = [e for e in events if e.event_type == "false_resolution"]
    if false_events:
        notes.append(
            f"{len(false_events)} moment(s) where closure language is followed by new questions — "
            "worth checking for accidental early resolution"
        )

    partial_events = [e for e in events if e.event_type == "partial_resolution"]
    if partial_events and not false_events:
        notes.append(
            f"Partial resolution at {_fmt_time(partial_events[0].time_seconds)} — "
            "narrative engine may still be active"
        )

    notes.append(
        "Rule-based fallback — configure GEMINI_API_KEY for semantic narrative analysis."
    )

    return NarrativeEngineMap(
        timeline=events[:20],
        open_loops=loops[:8],
        engine_notes=notes[:6],
        analysis_mode="rule_based",
    )


def build_narrative_engine_map(
    transcript: str,
    segments: Optional[Sequence[Dict[str, Any]]] = None,
) -> NarrativeEngineMap:
    text = (transcript or "").strip()
    if len(text) < 40:
        return NarrativeEngineMap(
            engine_notes=["Transcript too short for narrative engine map."]
        )

    moments = _iter_moments(text, segments)
    if not moments:
        return NarrativeEngineMap(engine_notes=["No timed moments detected in transcript."])

    if narrative_semantic_enabled():
        semantic = _build_semantic_narrative_map(text, moments)
        if semantic:
            return semantic

    return _build_rule_based_narrative_map(text, moments)
