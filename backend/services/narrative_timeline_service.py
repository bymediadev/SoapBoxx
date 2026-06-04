"""Layer A — per-episode narrative engine map (timeline, not trends).

Local tension state inside one episode: what is open, when, for how long.
No cross-episode averaging here — see narrative_timeline_deviation for Layer C.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from backend.features.rule_based import _SPEAKER_LINE, _words

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

    def to_dict(self) -> dict:
        return {
            "timeline": [e.to_dict() for e in self.timeline],
            "open_loops": [o.to_dict() for o in self.open_loops],
            "engine_notes": list(self.engine_notes),
        }


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

    return NarrativeEngineMap(
        timeline=events[:20],
        open_loops=loops[:8],
        engine_notes=notes[:6],
    )
