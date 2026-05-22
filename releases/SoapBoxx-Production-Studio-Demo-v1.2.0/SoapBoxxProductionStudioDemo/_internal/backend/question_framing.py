"""
Host-ready question framing for SoapBoxx.

Two intents:
- **live_capture** — during/after recording: what should the host ask next, grounded in transcript
- **scoop_prep** — before the show: prep questions for a named guest (used in guest_research prompts)

Styles (SOAPBOXX_QUESTION_STYLE): curious | direct | warm
"""

from __future__ import annotations

import os
import re
from typing import List, Literal, Optional, Sequence

QuestionStyle = Literal["curious", "direct", "warm"]
QuestionIntent = Literal["live_capture", "scoop_prep"]

_STYLE_HINTS = {
    "curious": "Curious and exploratory; invite stories and specifics.",
    "direct": "Direct and concise; get to the point without fluff.",
    "warm": "Warm and conversational; approachable tone, still substantive.",
}

# Shared rules appended to Scoop guest-research JSON prompts
SCOOP_QUESTION_RULES = """
QUESTION RULES (for the "questions" array):
- Each item is ONE complete spoken question ending with ?
- 8–22 words; open-ended; avoid yes/no unless clarifying
- Specific to this guest and context; no generic filler like "Tell me about your journey"
- No duplicate or near-duplicate questions
- Exactly 5 questions unless the guest context is extremely thin (then 3 minimum)
"""

_LIVE_SYSTEM = (
    "You help podcast hosts phrase their next questions. "
    "Output only host-ready questions, one per line."
)

_LIVE_USER_TEMPLATE = """From the transcript excerpt below, write {max_questions} questions the HOST should ask next.

Rules:
- One question per line, each ending with ?
- Open-ended; avoid yes/no unless clarifying
- 8–22 words each
- Grounded ONLY in what was said; do not invent names, dates, or facts not in the text
- Do not quote long transcript fragments as the question
- No numbering, bullets, labels, or commentary

Tone: {style_hint}

TRANSCRIPT:
{transcript}
"""


def question_style_from_env() -> QuestionStyle:
    raw = (os.getenv("SOAPBOXX_QUESTION_STYLE") or "curious").strip().lower()
    if raw in ("curious", "direct", "warm"):
        return raw  # type: ignore[return-value]
    return "curious"


def build_live_capture_prompt(
    transcript: str,
    *,
    style: Optional[QuestionStyle] = None,
    max_questions: int = 5,
) -> tuple[str, str]:
    """Return (system, user) messages for live question framing."""
    st = style or question_style_from_env()
    cap = max(1, min(8, int(max_questions)))
    user = _LIVE_USER_TEMPLATE.format(
        max_questions=cap,
        style_hint=_STYLE_HINTS.get(st, _STYLE_HINTS["curious"]),
        transcript=(transcript or "").strip(),
    )
    return _LIVE_SYSTEM, user


def normalize_question_line(line: str) -> Optional[str]:
    """Turn one raw LLM/heuristic line into a host-ready question or None if junk."""
    q = (line or "").strip()
    if not q:
        return None
    # Strip list markers: "1.", "-", "*", "•"
    q = re.sub(r"^[\s\-\*\•\d]+[\.\)\]]\s*", "", q).strip()
    q = q.strip('"\'')
    if not q:
        return None
    # Reject obvious non-questions
    lower = q.lower()
    if lower.startswith(("transcript:", "note:", "here are", "questions:")):
        return None
    if len(q) < 12:
        return None
    if len(q) > 280:
        q = q[:277].rstrip() + "..."
    if not q.endswith("?"):
        q = q.rstrip(".!") + "?"
    words = q.split()
    if len(words) < 4 or len(words) > 28:
        return None
    return q


def parse_question_lines(
    raw: str,
    *,
    known: Optional[Sequence[str]] = None,
    max_items: int = 12,
) -> List[str]:
    """Parse LLM/heuristic output into deduped host-ready questions."""
    known_lower = {k.strip().lower() for k in (known or []) if k}
    out: List[str] = []
    seen: set[str] = set()

    for line in (raw or "").splitlines():
        q = normalize_question_line(line)
        if not q:
            continue
        key = q.lower()
        if key in seen or key in known_lower:
            continue
        # Near-dup: same first 40 chars
        prefix = key[:40]
        if any(existing.startswith(prefix) or prefix.startswith(existing[:40]) for existing in seen):
            continue
        seen.add(key)
        out.append(q)
        if len(out) >= max_items:
            break
    return out


def format_questions_for_display(questions: Sequence[str]) -> str:
    return "\n".join(questions)
