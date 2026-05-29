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
# Narrative / produced-show transitions (Planet Money, documentary beats)
_DISCOURSE_PIVOT = re.compile(
    r"\b(but first|but now|years later|meanwhile|back in \d{4}|today on the show|"
    r"we(?:'re| are) (?:going to|here in)|let'?s (?:start|go to)|first stop|"
    r"second(?:ly)?|that said|on the other hand|in the (?:\d{4}s|meantime)|"
    r"when we come back|after the break|part (?:one|two|three))\b",
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
# Structural metrics describe the opening of an episode, so they are bounded.
# Without these caps a structureless transcript made the "hook"/"intro" equal to
# the entire runtime.
_HOOK_CAP_SECONDS = 120.0


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
                    return round(min(float(seg.get("start") or 0), _HOOK_CAP_SECONDS), 1)
                except (TypeError, ValueError):
                    break
        # No explicit topic shift: the hook is the opening beat (first segment),
        # not the whole episode.
        try:
            return round(min(float(segments[0].get("end") or 0), _HOOK_CAP_SECONDS), 1)
        except (TypeError, ValueError):
            pass

    words_before_shift = 0
    for para in re.split(r"\n\s*\n", (text or "").strip()):
        if _TOPIC_SHIFT_MARKERS.search(para):
            break
        words_before_shift += _words(para)
    if words_before_shift == 0:
        words_before_shift = min(150, _words(text) // 10)
    return round(min(_estimate_seconds_from_words(words_before_shift), _HOOK_CAP_SECONDS), 1)


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
    """Count structural pivot signals (explicit phrases, discourse beats, paragraph breaks)."""
    t = (text or "").strip()
    if not t:
        return 0
    phrase_hits = len(_TOPIC_SHIFT_MARKERS.findall(t))
    discourse_hits = len(_DISCOURSE_PIVOT.findall(t))
    paras = len([p for p in re.split(r"\n\s*\n", t) if len(p.split()) > 30])
    sent_pivots = sum(
        1
        for s in _sentences(t)
        if _TOPIC_SHIFT_MARKERS.search(s) or _DISCOURSE_PIVOT.search(s)
    )
    from_paras = max(0, paras - 1)
    from_sents = max(0, min(sent_pivots - 1, 6))
    return min(12, max(phrase_hits, discourse_hits, from_paras, from_sents))


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
