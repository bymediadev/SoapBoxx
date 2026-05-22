"""
Post-parse **grounding** checks for v2 episode briefs (complements shape checks in ``episode_intelligence._brief_schema_failures``).

Goal: reject "JSON that validates but is not about this tape" early so retries get corrective feedback.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Sequence, Set

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.I)

_STOP = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "your",
        "what",
        "when",
        "where",
        "which",
        "their",
        "there",
        "these",
        "those",
        "about",
        "after",
        "before",
        "because",
        "would",
        "could",
        "should",
        "episode",
        "podcast",
        "really",
        "thing",
        "things",
        "something",
        "nothing",
        "everyone",
        "someone",
    }
)


def _significant_tokens(text: str, *, min_len: int = 4) -> Set[str]:
    out: Set[str] = set()
    for m in _TOKEN_RE.finditer(text or ""):
        w = m.group(0).lower()
        if len(w) >= min_len and w not in _STOP:
            out.add(w)
    return out


def _transcript_sentence_chunks(transcript: str, *, max_sentences: int = 400) -> List[str]:
    """Lightweight sentence-ish units (aligned with 'tape language' checks, not ASR segmentation)."""
    raw = (transcript or "").replace("\r\n", "\n")
    parts: List[str] = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
        if not chunks:
            chunks = [line]
        parts.extend(chunks)
        if len(parts) >= max_sentences:
            break
    return parts[:max_sentences]


def max_token_recall_vs_transcript(text: str, transcript: str) -> float:
    """
    Max over transcript sentences of |claim_tokens ∩ sentence_tokens| / |claim_tokens|.
    Returns 0 when claim has no significant tokens.
    """
    ctoks = _significant_tokens(text)
    if not ctoks:
        return 0.0
    best = 0.0
    for sent in _transcript_sentence_chunks(transcript):
        stoks = _significant_tokens(sent)
        if not stoks:
            continue
        hit = len(ctoks & stoks) / float(len(ctoks))
        if hit > best:
            best = hit
    return best


def _env_float(key: str, default: float) -> float:
    raw = (os.getenv(key) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int) -> int:
    raw = (os.getenv(key) or "").strip()
    if not raw or not raw.isdigit():
        return default
    return max(0, int(raw))


def brief_transcript_parse_guardrail_failures(
    brief: Dict[str, Any],
    transcript: str,
) -> List[str]:
    """
    Return human-readable failures when brief prose is not plausibly grounded in ``transcript``.

    Skipped when transcript is very short (caller still has structural schema checks).
    Controlled by ``SOAPBOXX_BRIEF_TRANSCRIPT_GUARDRAILS`` (default on).
    """
    raw = os.getenv("SOAPBOXX_BRIEF_TRANSCRIPT_GUARDRAILS", "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return []

    t = (transcript or "").strip()
    min_words = _env_int("SOAPBOXX_BRIEF_GUARD_MIN_WORDS", 120)
    if len(t.split()) < min_words:
        return []

    min_anchor = _env_float("SOAPBOXX_BRIEF_MIN_TRANSCRIPT_ANCHOR", 0.06)
    failures: List[str] = []

    claims = brief.get("claims") if isinstance(brief.get("claims"), list) else []
    for i, c in enumerate(claims[:12]):
        if not isinstance(c, dict):
            continue
        txt = str(c.get("text") or "").strip()
        if len(txt) < 18:
            continue
        score = max_token_recall_vs_transcript(txt, t)
        if score < min_anchor:
            failures.append(
                f"claims[{i}].text is not visibly grounded in the transcript "
                f"(token-recall vs best sentence={score:.2f}; need >= {min_anchor:.2f}). "
                f"Rewrite using phrases the host or guest actually says."
            )

    narrative = brief.get("narrative") if isinstance(brief.get("narrative"), list) else []
    for i, row in enumerate(narrative[:3]):
        if not isinstance(row, str) or len(row.strip()) < 18:
            continue
        score = max_token_recall_vs_transcript(row, t)
        if score < min_anchor * 0.85:
            failures.append(
                f"narrative[{i}] reads off-tape (token-recall={score:.2f}; need >= {min_anchor * 0.85:.2f}). "
                "Pull narrative beats from transcript wording, not generic packaging."
            )

    snap = brief.get("episode_snapshot")
    if isinstance(snap, dict):
        pt = str(snap.get("primary_topic") or "").strip()
        if len(pt) >= 12 and "http" in pt.lower():
            failures.append(
                "episode_snapshot.primary_topic must not be a URL — summarize the tape in plain language."
            )
        elif len(pt) >= 12 and len(_significant_tokens(pt)) >= 2:
            score = max_token_recall_vs_transcript(pt, t)
            if score < min_anchor * 0.5:
                failures.append(
                    "episode_snapshot.primary_topic does not overlap the transcript enough — "
                    "derive it from recurring nouns/themes in the tape (not packaging alone)."
                )

    return failures


def workflow_json_minimal_shape_failures(data: Any, *, required_keys: Sequence[str]) -> List[str]:
    """Optional extra guard for workflow LLM payloads: require at least N of ``required_keys``."""
    if not isinstance(data, dict):
        return ["workflow JSON root must be an object"]
    present = [k for k in required_keys if k in data and data.get(k) not in (None, "", [], {})]
    min_keys = _env_int("SOAPBOXX_WORKFLOW_JSON_MIN_KEYS", 1)
    if len(present) < min_keys:
        return [
            f"workflow JSON must populate at least {min_keys} of {list(required_keys)!r}; "
            f"found only: {present!r}"
        ]
    return []
