"""
Rule-based episode features (V1 instrumentation).

Same keys as intelligence_v1 metrics for storage compatibility.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

# Align with schemas/episode_metrics_schema.json + intelligence_v1
METRIC_KEYS = (
    "hook_time_seconds",
    "guest_talk_percentage",
    "host_talk_percentage",
    "question_count",
    "followup_question_count",
    "story_count",
    "interruptions",
    "topic_changes",
    "cta_present",
)

_TOPIC_SHIFT_MARKERS = re.compile(
    r"\b(anyway|moving on|let'?s talk about|speaking of|on another note|"
    r"before we go|next topic|switching gears|pivot)\b",
    re.I,
)
_CTA_MARKERS = re.compile(
    r"\b(subscribe|subscribed|patreon|follow the show|rate and review|"
    r"link in the description|apple podcasts|spotify|youtube channel)\b",
    re.I,
)
_SPEAKER_LINE = re.compile(
    r"^\s*(host|guest|speaker\s*\d+|interviewer|narrator)\s*:\s*",
    re.I,
)


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [p.strip() for p in parts if len(p.strip()) > 2]


def _words(text: str) -> int:
    return len((text or "").split())


def _estimate_seconds_from_words(word_count: int, wps: float = 2.5) -> float:
    return max(0.0, word_count / max(wps, 0.1))


def _speaker_talk_ratios(text: str) -> tuple[float, float, int]:
    """Returns guest_pct, host_pct, speaking_turns from labeled lines."""
    guest_words = 0
    host_words = 0
    turns = 0
    for line in (text or "").splitlines():
        s = line.strip()
        if not s:
            continue
        m = _SPEAKER_LINE.match(s)
        if not m:
            continue
        turns += 1
        body = _SPEAKER_LINE.sub("", s).strip()
        w = _words(body)
        label = m.group(1).lower()
        if label.startswith("guest"):
            guest_words += w
        else:
            host_words += w
    total = guest_words + host_words
    if total < 20:
        return 50.0, 50.0, turns
    return (
        round(100.0 * guest_words / total, 1),
        round(100.0 * host_words / total, 1),
        turns,
    )


def hook_time_seconds(text: str, segments: Optional[Sequence[Dict[str, Any]]] = None) -> float:
    if segments:
        for i, seg in enumerate(segments):
            if i == 0:
                continue
            t = str(seg.get("text") or "")
            if _TOPIC_SHIFT_MARKERS.search(t):
                try:
                    return float(seg.get("start") or 0)
                except (TypeError, ValueError):
                    break
        try:
            return float(segments[-1].get("end") or 0) if segments else 0.0
        except (TypeError, ValueError):
            pass

    words_before_shift = 0
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        if _TOPIC_SHIFT_MARKERS.search(para):
            break
        words_before_shift += _words(para)
    if words_before_shift == 0:
        words_before_shift = min(150, _words(text) // 10)
    return round(_estimate_seconds_from_words(words_before_shift), 1)


def question_count(text: str) -> int:
    return len(re.findall(r"\?", text or ""))


def followup_question_count(text: str) -> int:
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    count = 0
    prev_had_q = False
    for ln in lines:
        has_q = "?" in ln
        if has_q and prev_had_q:
            count += 1
        prev_had_q = has_q
    return count


def topic_changes(text: str) -> int:
    hits = len(_TOPIC_SHIFT_MARKERS.findall(text or ""))
    paras = len([p for p in re.split(r"\n\s*\n", (text or "").strip()) if len(p.split()) > 30])
    return max(hits, max(0, paras - 1))


def cta_present(text: str) -> bool:
    return bool(_CTA_MARKERS.search(text or ""))


def avg_sentence_length(text: str) -> float:
    sents = _sentences(text)
    if not sents:
        return 0.0
    return round(sum(_words(s) for s in sents) / len(sents), 1)


def extract_rule_features(
    transcript: str,
    segments: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Reproducible V1 features. ``story_count`` and ``interruptions`` are 0 in V1
    (require judgment or diarization) — reserved for schema compatibility.
    """
    text = (transcript or "").strip()
    guest_pct, host_pct, turns = _speaker_talk_ratios(text)
    return {
        "hook_time_seconds": hook_time_seconds(text, segments),
        "guest_talk_percentage": guest_pct,
        "host_talk_percentage": host_pct,
        "question_count": question_count(text),
        "followup_question_count": followup_question_count(text),
        "story_count": 0,
        "interruptions": 0,
        "topic_changes": topic_changes(text),
        "cta_present": cta_present(text),
        "feature_source": "rule_based",
        "speaking_turns": turns,
        "avg_sentence_length": avg_sentence_length(text),
    }
