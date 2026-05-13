"""
Deterministic transcript quality scoring for intake decisions.

Goal: estimate whether a transcript is clean enough for high-quality content extraction
without invoking another LLM call.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

_NOISE_LINE_RE = re.compile(
    r"^\s*(?:\[[^\]]+\]|\((?:music|applause|laughter|inaudible|silence)\)|music|applause|laughter)\s*$",
    flags=re.IGNORECASE,
)
_TIMESTAMP_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")


def _lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _tokens(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", text or "")


def _safe_div(a: float, b: float) -> float:
    return a / b if b else 0.0


def assess_transcript_quality(
    text: str,
    *,
    source: str = "unknown",
) -> Dict[str, Any]:
    """
    Return a score + verdict to drive intake source selection.

    Verdicts:
      - pass: good enough for primary extraction
      - degraded: usable but likely noisy; keep with warnings or try better source
      - fail: too weak/noisy for trustworthy extraction
    """
    raw = text or ""
    lines = _lines(raw)
    tokens = _tokens(raw)
    low_lines = [ln.lower() for ln in lines]

    line_count = len(lines)
    word_count = len(tokens)
    unique_line_ratio = _safe_div(len(set(low_lines)), line_count)
    repeated_line_ratio = max(0.0, 1.0 - unique_line_ratio)
    short_line_ratio = _safe_div(sum(1 for ln in lines if len(_tokens(ln)) <= 2), line_count)
    noise_line_ratio = _safe_div(sum(1 for ln in lines if _NOISE_LINE_RE.match(ln)), line_count)
    timestamp_hits = len(_TIMESTAMP_RE.findall(raw))
    replacement_chars = raw.count("\ufffd")
    avg_words_per_line = _safe_div(word_count, line_count)

    score = 1.0
    if word_count < 80:
        score -= 0.35
    elif word_count < 160:
        score -= 0.20
    if line_count < 20:
        score -= 0.10
    if repeated_line_ratio > 0.30:
        score -= min(0.35, repeated_line_ratio * 0.9)
    if short_line_ratio > 0.45:
        score -= min(0.22, short_line_ratio * 0.35)
    if noise_line_ratio > 0.08:
        score -= min(0.18, noise_line_ratio * 0.8)
    if avg_words_per_line < 3.0 and line_count >= 15:
        score -= 0.12
    if timestamp_hits > 12:
        score -= 0.10
    if replacement_chars > 0:
        score -= min(0.10, replacement_chars * 0.02)

    # Captions are more prone to repetition and line fragmentation; tighten slightly.
    if source == "captions" and repeated_line_ratio > 0.22:
        score -= 0.08
    if source == "captions" and short_line_ratio > 0.50:
        score -= 0.06

    score = max(0.0, min(1.0, score))
    if score >= 0.70:
        verdict = "pass"
    elif score >= 0.45:
        verdict = "degraded"
    else:
        verdict = "fail"

    reasons: List[str] = []
    if word_count < 160:
        reasons.append(f"low_word_count:{word_count}")
    if repeated_line_ratio > 0.25:
        reasons.append(f"high_repetition:{repeated_line_ratio:.2f}")
    if short_line_ratio > 0.45:
        reasons.append(f"fragmented_lines:{short_line_ratio:.2f}")
    if noise_line_ratio > 0.08:
        reasons.append(f"noise_lines:{noise_line_ratio:.2f}")
    if timestamp_hits > 12:
        reasons.append(f"timestamp_artifacts:{timestamp_hits}")
    if replacement_chars:
        reasons.append(f"replacement_chars:{replacement_chars}")

    return {
        "source": source,
        "score": round(score, 4),
        "verdict": verdict,
        "reasons": reasons,
        "metrics": {
            "word_count": word_count,
            "line_count": line_count,
            "unique_line_ratio": round(unique_line_ratio, 4),
            "repeated_line_ratio": round(repeated_line_ratio, 4),
            "short_line_ratio": round(short_line_ratio, 4),
            "noise_line_ratio": round(noise_line_ratio, 4),
            "timestamp_hits": timestamp_hits,
            "replacement_chars": replacement_chars,
            "avg_words_per_line": round(avg_words_per_line, 4),
        },
    }


def pick_better_transcript_report(reports: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Choose best candidate by verdict tier then score."""
    ranked: List[Dict[str, Any]] = [r for r in reports if isinstance(r, dict)]
    if not ranked:
        return {}
    tier = {"pass": 2, "degraded": 1, "fail": 0}
    ranked.sort(
        key=lambda r: (
            tier.get(str(r.get("verdict") or ""), -1),
            float(r.get("score") or 0.0),
        ),
        reverse=True,
    )
    return ranked[0]


__all__ = [
    "assess_transcript_quality",
    "pick_better_transcript_report",
]
