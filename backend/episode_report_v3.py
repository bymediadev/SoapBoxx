# backend/episode_report_v3.py
"""
**Primary** SoapBoxx episode workflow (v3): coach-style Episode Report (10 sections), signal mode
(HIGH_SIGNAL / LOW_SIGNAL), structured evidence, engagement triads, guests, segments,
actionable analytics, reference validation, semantic deduplication, and ``dual_lens`` (parallel
narrative/analytical assembly + weights — see ``lens_engine_prompts.assemble_dual_lens_package``).

Builds on normalized **v2** brief JSON from episode_intelligence.generate_episode_brief.
The coach always surfaces a single-sentence thesis line (argument-shaped); low-signal runs pair it with an honest-read note.

**Structured intelligence source of truth:** when enabled (default; ``SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=1`` or
``atomic_ground_truth=True`` on :func:`build_v3_report`), claims and graph-derived guests come **only** from
``atomic_pipeline.run_atomic_pipeline`` — v3 does not re-extract claims, re-cluster topics, or synthesize guests
from narrative heuristics. Narrative/coach/dual_lens remain presentation layers on top of the same transcript
and brief context. Set ``SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=0`` to restore brief-only claim rows (legacy/tests).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

# Reuse claim cleanup from v2 pipeline
try:
    from .episode_intelligence import (  # type: ignore
        _clean_claim_text,
        _is_meta_topic_line,
        _is_narrative_meta_noise,
        _sanitize_episode_snapshot,
        _utc_now_iso,
        generate_episode_brief,
        render_markdown,
    )
except ImportError:
    from episode_intelligence import (  # type: ignore
        _clean_claim_text,
        _is_meta_topic_line,
        _is_narrative_meta_noise,
        _sanitize_episode_snapshot,
        _utc_now_iso,
        generate_episode_brief,
        render_markdown,
    )

try:
    from .lens_engine_prompts import assemble_dual_lens_package  # type: ignore
except ImportError:
    from lens_engine_prompts import assemble_dual_lens_package  # type: ignore

try:
    from .episode_quality_gates import evaluate_v3_quality_gates  # type: ignore
except ImportError:
    from episode_quality_gates import evaluate_v3_quality_gates  # type: ignore

try:
    from .episode_quality_gates import build_identity_anchor, jaccard_tokens  # type: ignore
except ImportError:
    from episode_quality_gates import build_identity_anchor, jaccard_tokens  # type: ignore

try:
    from .guest_generation_decision import build_guest_decision_trace  # type: ignore
except ImportError:
    from guest_generation_decision import build_guest_decision_trace  # type: ignore

try:
    from .semantic_grounding_validator import apply_semantic_grounding_validator  # type: ignore
except ImportError:
    from semantic_grounding_validator import apply_semantic_grounding_validator  # type: ignore

try:
    from .claim_quality_gate import apply_claim_quality_gate  # type: ignore
except ImportError:
    from claim_quality_gate import apply_claim_quality_gate  # type: ignore

try:
    from .system_health import apply_system_health_label  # type: ignore
except ImportError:
    from system_health import apply_system_health_label  # type: ignore

try:
    from .report_invariants import validate_v3_invariants  # type: ignore
except ImportError:
    from report_invariants import validate_v3_invariants  # type: ignore

try:
    from .atomic_pipeline import envelope_to_json, run_atomic_pipeline
except ImportError:
    try:
        from atomic_pipeline import envelope_to_json, run_atomic_pipeline  # type: ignore
    except ImportError:  # pragma: no cover
        envelope_to_json = None  # type: ignore[assignment]
        run_atomic_pipeline = None  # type: ignore[assignment]

REPORT_V3_VERSION = "3"
SEMANTIC_DUP_THRESHOLD = 0.8
MIN_EVIDENCE_CONFIDENCE = 0.2


def _transcript_normalize_enabled() -> bool:
    """
    Default **on** (dedupe lines, collapse blank runs) for real-episode transcripts.
    Set ``SOAPBOXX_TRANSCRIPT_NORMALIZE=0`` (or ``false`` / ``no`` / ``off``) to disable.
    """
    v = os.getenv("SOAPBOXX_TRANSCRIPT_NORMALIZE", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return True


def normalize_transcript_for_v3(text: str) -> str:
    """
    Deterministic transcript cleanup before v2 brief / v3 report (no LLM).

    - Normalizes ``\\r\\n`` / ``\\r`` to ``\\n``.
    - Trims trailing whitespace per line.
    - Collapses runs of **3+** blank lines to **2** blank lines.
    - Drops **consecutive duplicate** non-blank lines (exact match after ``rstrip``).
      A blank line between two identical lines breaks deduplication so repeated
      paragraphs separated by whitespace are kept.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: List[str] = []
    prev_content: Optional[str] = None
    blank_run_out = 0
    for line in lines:
        s = line.rstrip()
        if not s:
            if blank_run_out < 2:
                out.append("")
                blank_run_out += 1
            prev_content = None
            continue
        blank_run_out = 0
        if prev_content is not None and s == prev_content:
            continue
        prev_content = s
        out.append(s)
    return "\n".join(out).strip()


def transcript_for_v3_pipeline(text: str) -> str:
    """Return ``normalize_transcript_for_v3`` unless normalization is disabled (see ``_transcript_normalize_enabled``)."""
    if not _transcript_normalize_enabled():
        return text or ""
    return normalize_transcript_for_v3(text or "")


def _workflow_body_guest_rows(workflow: Dict[str, Any]) -> List[Any]:
    """Delegate to :func:`soapboxx_v3_workflow.workflow_guest_rows` (alias drift self-heal)."""
    try:
        from .soapboxx_v3_workflow import workflow_guest_rows
    except ImportError:
        from soapboxx_v3_workflow import workflow_guest_rows  # type: ignore
    return workflow_guest_rows(workflow)


INSIGHT_TRANSFORM_RULES = """
You are NOT allowed to output raw transcript fragments.

For every extracted quote:
1. Rewrite it into a complete, clear sentence
2. Extract the underlying idea (not the wording)
3. Convert it into a generalized insight

Bad Output:
- "those are all ways that you can start to think about..."

Good Output:
- "Identifying environmental temptations is the first step in designing better habits."

If the sentence is incomplete or low-signal -> DISCARD IT.
""".strip()

NARRATIVE_RECONSTRUCTION = """
If no clear narrative is detected, you MUST infer one using:

1. Repeated keywords/themes
2. Speaker intent (advice, story, explanation)
3. Outcome the speaker is pushing toward

Output format:
- Core Thesis (1 sentence)
- Supporting Mechanism (how it works)
- Practical Translation (what it means in real life)

You are NOT allowed to return "no narrative".
""".strip()

EVIDENCE_MAPPING_RULES = """
Each claim must include:

1. Claim (rewritten insight)
2. Function:
   - supports_argument
   - example
   - anecdote
   - mechanism
3. Usage:
   - how a creator can use this in content

Bad:
- random sentence + timestamp

Good:
- "Preparation reduces failure rate" | function: mechanism | usage: teaching segment
""".strip()

STRATEGY_RULES = """
For every insight, generate:

1. Application (real-world action)
2. Content Angle (how to turn into a segment)

Do not leave insights abstract.
""".strip()

QUESTION_RULES = """
Generate questions using these lenses:

1. Failure Case:
   - When does this NOT work?

2. Constraint:
   - What real-world condition breaks this?

3. Contrarian:
   - What would an expert disagree with?

4. Application:
   - What should someone do differently tomorrow?

Avoid generic questions.
""".strip()

GUEST_RULES = """
You must recommend 3-5 guests based on:

1. Validating the idea
2. Challenging the idea
3. Applying the idea in real-world scenarios

Each guest must include:
- Type
- Reason
- Content angle
""".strip()

TAKEAWAY_RULES = """
Generate ONE clear takeaway:

- Max 15 words
- Must be repeatable
- Must sound like something a host would say on-air

Bad:
- vague summary

Good:
- "You don't rise to goals - you fall to systems."
""".strip()

_FILLER_PREFIX = re.compile(
    r"^(The speaker|Host|Guest)\s+(argues|says|claims|notes|states|criticizes)\s+that\s+",
    re.I,
)
_REF_ID = re.compile(r"\bc(\d+)\b", re.I)


def _tokens(s: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", (s or "").lower())


def text_similarity(a: str, b: str) -> float:
    """
    Similarity in [0, 1], calibrated for duplicate detection.
    Blend of Jaccard (word sets) and normalized sequence ratio.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return SequenceMatcher(None, a, b).ratio()
    inter = len(ta & tb)
    union = len(ta | tb)
    jacc = inter / union if union else 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    return float(0.55 * jacc + 0.45 * seq)


def remove_semantic_duplicates(
    items: Sequence[str],
    *,
    threshold: float = SEMANTIC_DUP_THRESHOLD,
    key: Optional[Callable[[str], str]] = None,
) -> List[str]:
    """
    Drop items semantically similar to an earlier kept item (similarity > threshold).
    Keeps the first occurrence (caller should sort by strength if needed).
    Uses text similarity only (embedding dedup was removed in the Ollama-only stack).
    """
    raw = [str(x).strip() for x in items if str(x).strip()]
    if not raw:
        return []
    getter = key or (lambda s: s)
    kept: List[str] = []
    for item in raw:
        k = getter(item)
        if any(text_similarity(k, getter(o)) > threshold for o in kept):
            continue
        kept.append(item)
        if len(kept) >= 20:
            break
    return kept


def _limit_words(text: str, max_words: int = 20) -> str:
    words = (text or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(",;:")


def _is_garbled_insight_line(text: str) -> bool:
    """Broken grammar / word-salad from sloppy model output — never show as a highlight."""
    s = (text or "").strip()
    if len(s.split()) < 8:
        return True
    low = s.lower()
    if re.search(r"\bquite\s+while\b", low):
        return True
    if re.search(r"\bcannot\s+quite\s+\w+\s+while\b", low):
        return True
    if "cannot quite" in low and "while" in low and len(s.split()) < 16:
        return True
    return False


def is_low_signal_insight_line(text: str) -> bool:
    """
    Heuristic filter for transcript junk that should never surface as a "highlight":
    lyrics, outros, repeated interjections, scheduling banter, caption metadata.
    """
    s = (text or "").strip()
    if not s:
        return True
    if _is_meta_topic_line(s) or _is_narrative_meta_noise(s):
        return True
    low = s.lower()
    # Caption / platform boilerplate
    if any(
        x in low
        for x in (
            "kind: captions",
            "language: en",
            "subscribe",
            "like and subscribe",
            "hit the bell",
        )
    ):
        return True
    # Repeated filler / interjections (lyrics, reactions)
    if re.search(r"\b(?:oh\s*,?\s*){3,}", low):
        return True
    if re.search(r"\b(?:okay\s*,?\s*){3,}", low):
        return True
    # Outro / scheduling / music-break chatter
    if any(
        x in low
        for x in (
            "forward to talking",
            "talk to you in about",
            "see you in a few",
            "we'll be right back",
            "whole world to me",
            "making love",
        )
    ):
        return True
    # Short lyric-y fragments without argumentative content
    if "whole world" in low and len(s.split()) < 12:
        return True
    # Nonsense or ultra-vague "wellness" fragments often picked from noisy transcripts
    if "sometimes you always" in low:
        return True
    words = s.split()
    if len(words) < 6 and any(x in low for x in ("oh", "yeah", "baby", "love")):
        return True
    # Radio / meditation intros — atmospheric, not argumentative (common in sleep/spiritual pods)
    atmospheric = (
        "tonight we are",
        "tonight we're",
        "we are going to sit",
        "sit with a man",
        "the kind that waits",
        "spaces between tasks",
        "silence after",
        "after the lights go out",
        "let your breath",
        "particular quiet",
        "more like a question",
        "circling in the back of your mind",
        "understood suffering better than",
        "in the particular quiet",
    )
    if any(x in low for x in atmospheric):
        return True
    if low.startswith("let your ") and any(
        x in low for x in ("breath", "rhythm", "body", "mind", "shoulders")
    ):
        return True
    if _is_garbled_insight_line(s):
        return True
    return False


def _trim_insight_line(text: str, max_words: int = 26) -> str:
    """
    Prefer a complete sentence under max_words; avoid chopping mid-clause when possible.
    """
    t = (text or "").strip()
    if not t:
        return t
    words = t.split()
    if len(words) <= max_words:
        return t
    chunk = " ".join(words[:max_words])
    for sep in (". ", "? ", "! ", "; "):
        idx = chunk.rfind(sep)
        if idx >= 48:
            return chunk[: idx + 1].strip()
    cut = chunk.rsplit(" ", 1)[0]
    return cut.rstrip(",;:\"'") + "…"


def clean_key_highlights(raw_highlights: Union[str, Sequence[str]]) -> List[str]:
    """
    Input: messy transcript-derived highlights (strings or list of strings).
    Output: 3–5 sharp standalone insights (claim-style, ≤20 words, deduped).
    """
    if isinstance(raw_highlights, str):
        lines = [ln.strip() for ln in raw_highlights.splitlines() if ln.strip()]
    else:
        lines = [str(x).strip() for x in raw_highlights if str(x).strip()]
    cleaned: List[str] = []
    for ln in lines:
        s = _FILLER_PREFIX.sub("", _clean_claim_text(ln))
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) < 12:
            continue
        if _is_meta_topic_line(s) or _is_narrative_meta_noise(s):
            continue
        if is_low_signal_insight_line(s):
            continue
        s = _trim_insight_line(s, max_words=26)
        if s and not is_low_signal_insight_line(s) and s not in cleaned:
            cleaned.append(s)
    deduped = remove_semantic_duplicates(cleaned, threshold=SEMANTIC_DUP_THRESHOLD)
    out = [x for x in deduped if not is_low_signal_insight_line(x)][:5]
    return out


def generate_engagement_questions(claim: Dict[str, Any]) -> Dict[str, str]:
    """
    Tension-focused triad per claim: counterpunch, validation, application.
    """
    ct = _clean_claim_text(str(claim.get("text") or ""))[:120]
    short = ct[:80] + ("…" if len(ct) > 80 else "")
    return {
        "counterpunch": f'What would someone who disagrees say about this: "{short}"?',
        "validation": f'Is there real evidence behind this, or is it rhetoric? Push on: "{short}"',
        "application": f"What does this mean in real life for listeners—what should they do differently?",
    }


def map_guest_to_claim(guest: Dict[str, Any], claim: Dict[str, Any]) -> Dict[str, str]:
    """Every guest tied to one specific claim; no generic blurbs."""
    tgt = _clean_claim_text(str(claim.get("text") or ""))
    name = str(guest.get("name") or "Guest").strip()
    role = str(guest.get("title") or guest.get("role") or "Expert").strip()
    why = str(guest.get("angle") or guest.get("why_this_episode") or "").strip()
    if not why:
        why = f"Pressure-tests the claim: {tgt[:100]}{'…' if len(tgt) > 100 else ''}"
    return {
        "guest": name,
        "role": role,
        "why_this_episode": why,
        "target_claim": tgt,
    }


_RE_TS = re.compile(r"(?:^|\s)(?:(\d+):(\d+)(?::(\d+))?\.(\d+)|(\d+\.?\d*))\s*s\b", re.I)
# Full line prefix like [00:02:00] (hours may be 0; podcast lines use HH:MM:SS)
_RE_BRACKET_HMS = re.compile(r"^\s*\[\s*(\d{1,2}):(\d{2}):(\d{2})\s*\]\s*")
_RE_LEADING_TS = re.compile(r"^\s*\[?\s*(\d+\.?\d*)\s*s?\s*\]?\s*", re.I)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with", "is",
    "are", "was", "were", "be", "being", "been", "it", "this", "that", "as", "at", "by",
    "from", "you", "your", "we", "they", "their", "our", "i", "he", "she", "them", "his",
    "her", "not", "do", "does", "did", "can", "could", "should", "would",
}

# Words so common in tech/business transcripts they should not carry evidence match alone.
_GENERIC_EVIDENCE_WORDS = frozenset(
    {
        "ai",
        "artificial",
        "intelligence",
        "business",
        "businesses",
        "small",
        "companies",
        "company",
        "leaders",
        "leader",
        "tech",
        "technology",
        "podcast",
        "episode",
        "today",
        "host",
        "guest",
        "really",
        "just",
        "even",
        "here",
        "think",
        "things",
        "many",
        "some",
        "people",
        "listen",
        "listeners",
        "talk",
        "into",
        "world",
        "like",
        "make",
        "get",
        "going",
        "know",
        "isnt",
        "isn't",
        "dont",
        "don't",
        "big",
        "giant",
        "giants",
        "future",
        "next",
        "time",
        "way",
        "ways",
        "work",
        "works",
        "said",
        "says",
    }
)


def _token_hits_sentence(word: str, sentence_lower: str) -> bool:
    """Plural/stem-friendly membership for overlap scoring."""
    if not word or not sentence_lower:
        return False
    if word in sentence_lower:
        return True
    if len(word) > 4 and word.endswith("s") and word[:-1] in sentence_lower:
        return True
    if len(word) > 3 and not word.endswith("s") and (word + "s") in sentence_lower:
        return True
    return False


def _distinctive_claim_tokens(claim_text: str) -> List[str]:
    """Non-stopword, non-generic tokens we expect to see in supporting evidence."""
    out: List[str] = []
    for w in _tokens(claim_text):
        if len(w) < 3 or w in _STOPWORDS or w in _GENERIC_EVIDENCE_WORDS:
            continue
        out.append(w)
    return out


def _distinctive_coverage(claim_text: str, sentence_text: str) -> float:
    """Fraction of distinctive claim words present in the sentence (0..1)."""
    dist = _distinctive_claim_tokens(claim_text)
    if not dist:
        return 0.0
    low = (sentence_text or "").lower()
    hits = sum(1 for w in dist if _token_hits_sentence(w, low))
    return hits / float(len(dist))


def _soft_evidence_concept_bonus(claim_text: str, sentence_lower: str) -> float:
    """
    Small boosts when paraphrases align (concerned/worried, cost/money, complexity/learning curve).
    """
    bonus = 0.0
    ct = set(_tokens(claim_text))
    if "concerned" in ct and any(
        x in sentence_lower for x in ("worried", "worry", "worries", "worrying")
    ):
        bonus += 0.14
    if ("costs" in ct or "cost" in ct) and any(
        x in sentence_lower for x in ("cost", "costs", "expensive", "price", "pricing")
    ):
        bonus += 0.12
    if "complexity" in ct and (
        "learning curve" in sentence_lower
        or ("curve" in sentence_lower and "learn" in sentence_lower)
    ):
        bonus += 0.12
    return min(0.22, bonus)


@dataclass
class EvidenceClaim:
    id: str
    timestamp: Optional[float]
    claim: str
    function: str
    usage: str


@dataclass
class SentenceUnit:
    idx: int
    text: str
    timestamp: Optional[float]


def _parse_timestamp_line(line: str) -> Tuple[Optional[float], str]:
    """
    Strip common transcript prefixes and return (seconds, rest of line).
    Prefer [HH:MM:SS] so we do not leave ':02:00]' junk in evidence text.
    """
    s = line or ""
    m = _RE_BRACKET_HMS.match(s)
    if m:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
        total = float(h * 3600 + mi * 60 + sec)
        return total, s[m.end() :].strip()
    m = _RE_LEADING_TS.match(s)
    if not m:
        return None, s
    try:
        return float(m.group(1)), s[m.end() :].strip()
    except ValueError:
        return None, s


def _trim_snippet_with_focus(text: str, claim_words: Sequence[str], max_len: int) -> str:
    s = (text or "").strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    low = s.lower()
    hit_idx = -1
    for w in claim_words:
        idx = low.find(w)
        if idx >= 0:
            hit_idx = idx if hit_idx < 0 else min(hit_idx, idx)
    if hit_idx < 0:
        return s[: max_len - 3].rsplit(" ", 1)[0] + "..."
    start = max(0, hit_idx - 28)
    end = min(len(s), start + max_len - 3)
    chunk = s[start:end].strip()
    if start > 0:
        chunk = "..." + chunk
    if end < len(s):
        chunk = chunk.rsplit(" ", 1)[0] + "..."
    return chunk


def _split_into_sentence_units(transcript: str) -> List[SentenceUnit]:
    """Sentence-level index for claim evidence assignment."""
    out: List[SentenceUnit] = []
    idx = 0
    for line in (transcript or "").splitlines():
        ts, rest = _parse_timestamp_line(line)
        line_text = (rest or "").strip()
        if not line_text:
            continue
        chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line_text) if s.strip()]
        if not chunks:
            chunks = [line_text]
        for s in chunks:
            out.append(SentenceUnit(idx=idx, text=s, timestamp=ts))
            idx += 1
    return out


def _remove_fillers(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(
        r"^(?:well|so|and so|you know|i mean|like)\b[\s,.-]*",
        "",
        s,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", s).strip()


def _truncate_words(text: str, max_words: int = 25) -> str:
    """
    Trim to max_words without trailing ellipsis (workflow JSON validation rejects '...').
    Prefer ending at a sentence boundary inside the kept span.
    """
    words = (text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    chunk = " ".join(words[:max_words])
    for sep in (". ", "? ", "! ", "; "):
        idx = chunk.rfind(sep)
        if idx >= 28:
            return chunk[: idx + 1].strip()
    tail = " ".join(words[: max(1, max_words - 1)])
    return tail.rstrip(",;:\"'") + "."


def _strip_orphan_timestamp_junk(text: str) -> str:
    """Remove leftover ':MM:SS]' fragments when timestamp parsing was wrong."""
    s = (text or "").strip()
    s = re.sub(r"^[\s:]*\d{1,2}:\d{2}(?::\d{2})?\s*\]\s*", "", s)
    return s


def _clean_evidence_snippet(text: str, max_words: int = 25) -> str:
    return _truncate_words(_remove_fillers(_strip_orphan_timestamp_junk(text)), max_words=max_words)


def _keyword_overlap(claim_text: str, sentence_text: str) -> float:
    c = {w for w in _tokens(claim_text) if w not in _STOPWORDS and len(w) > 2}
    s = {w for w in _tokens(sentence_text) if w not in _STOPWORDS and len(w) > 2}
    if not c or not s:
        return 0.0
    return len(c & s) / len(c)


def _score_sentence_for_claim(claim_text: str, sentence_text: str) -> float:
    """
    Blend semantic + keyword overlap + *distinctive* word coverage.
    Generic AI/business words alone must not outrank a sentence that shares the claim's specific terms.
    """
    sem = text_similarity(claim_text, sentence_text)
    key = _keyword_overlap(claim_text, sentence_text)
    dcov = _distinctive_coverage(claim_text, sentence_text)
    dist = _distinctive_claim_tokens(claim_text)
    low = (sentence_text or "").lower()
    base = (0.32 * sem) + (0.28 * key) + (0.40 * dcov)
    base += _soft_evidence_concept_bonus(claim_text, low)
    base = min(1.0, base)
    if len(dist) >= 3 and dcov < 0.34:
        base *= 0.38
    elif len(dist) >= 2 and dcov < 0.26:
        base *= 0.48
    return float(max(0.0, min(base, 1.0)))


def _deduplicate_claims_for_evidence(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not txt:
            continue
        if any(text_similarity(txt, _clean_claim_text(str(o.get("text") or ""))) > 0.9 for o in out):
            continue
        out.append(c)
    return out


def _assign_unique_sentence_evidence(
    claims: List[Dict[str, Any]],
    sentence_units: List[SentenceUnit],
    *,
    near_dup_threshold: float = 0.85,
) -> Dict[str, Dict[str, Any]]:
    """
    Assign 1 distinct sentence per claim, avoiding reused/near-duplicate snippets.
    Pairs (claim, sentence) are sorted by score globally so a sentence goes to the claim
    that matches it best — not to whichever long claim is processed first.
    """
    used_idx: Set[int] = set()
    selected_snippets: List[str] = []
    assigned: Dict[str, Dict[str, Any]] = {}
    claim_done: Set[str] = set()

    pairs: List[Tuple[float, str, SentenceUnit]] = []
    for c in claims:
        cid = str(c.get("id") or "")
        claim_txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid or not claim_txt:
            continue
        for su in sentence_units:
            score = _score_sentence_for_claim(claim_txt, su.text)
            if score <= 0.10:
                continue
            pairs.append((score, cid, su))
    pairs.sort(key=lambda x: (-x[0], x[1], x[2].idx))

    for score, cid, su in pairs:
        if cid in claim_done:
            continue
        if su.idx in used_idx:
            continue
        snip = _clean_evidence_snippet(su.text, max_words=25)
        if not snip:
            continue
        if any(text_similarity(snip, prev) > near_dup_threshold for prev in selected_snippets):
            continue
        used_idx.add(su.idx)
        selected_snippets.append(snip)
        assigned[cid] = {
            "timestamp": su.timestamp,
            "evidence": snip,
            "confidence": round(max(0.0, min(score, 1.0)), 3),
            "source_type": "direct_statement",
        }
        claim_done.add(cid)
    return assigned


def _fallback_evidence_for_claim(
    claim_text: str,
    sentence_units: Sequence[SentenceUnit],
    used_snippets: Sequence[str],
) -> Tuple[Optional[float], str, float, str]:
    """
    Fallback policy when confidence is below gate:
    - Prefer highest keyword-overlap sentence not near-duplicate of used evidence.
    - If no good match, fallback to snippet matcher.
    """
    best: Optional[Tuple[float, SentenceUnit]] = None
    for su in sentence_units:
        snip = _clean_evidence_snippet(su.text, max_words=25)
        if not snip:
            continue
        if any(text_similarity(snip, prev) > 0.86 for prev in used_snippets):
            continue
        key = _keyword_overlap(claim_text, su.text)
        sem = text_similarity(claim_text, su.text)
        dcov = _distinctive_coverage(claim_text, su.text)
        low = su.text.lower()
        score = (0.22 * sem) + (0.28 * key) + (0.50 * dcov) + _soft_evidence_concept_bonus(
            claim_text, low
        )
        if best is None or score > best[0]:
            best = (score, su)
    if best and best[0] >= 0.18:
        score, su = best
        return (
            su.timestamp,
            _clean_evidence_snippet(su.text, max_words=25),
            max(MIN_EVIDENCE_CONFIDENCE, float(score)),
            "low_confidence_fallback",
        )
    return None, "", 0.0, "low_confidence_fallback"


def _find_evidence_snippet(transcript: str, claim_text: str, max_len: int = 180) -> Tuple[Optional[float], str]:
    """Best-effort quote + optional timestamp from plain or lightly timestamped transcript."""
    if not transcript or not claim_text:
        return None, ""
    t = transcript.strip()
    claim_words = [w for w in _tokens(claim_text) if len(w) > 2][:8]
    if not claim_words:
        return None, ""
    best_ts: Optional[float] = None
    best_snip = ""
    best_score = 0
    for line in t.splitlines():
        ts, rest = _parse_timestamp_line(line)
        low = rest.lower()
        score = sum(1 for w in claim_words if w in low)
        if score > best_score and rest.strip():
            best_score = score
            best_ts = ts
            snip = _trim_snippet_with_focus(rest, claim_words, max_len)
            best_snip = snip
    if not best_snip:
        # fallback: first sentence containing a claim keyword
        for sent in re.split(r"(?<=[.!?])\s+", t):
            low = sent.lower()
            if sum(1 for w in claim_words if w in low) >= 2:
                s = sent.strip()
                s = _trim_snippet_with_focus(s, claim_words, max_len)
                return None, s
    return best_ts, best_snip


def _find_evidence_snippet_unique(
    transcript: str,
    claim_text: str,
    used_snippets: Sequence[str],
    max_len: int = 180,
) -> Tuple[Optional[float], str]:
    """Pick a best snippet that is not near-duplicate of already used snippets."""
    ts, snip = _find_evidence_snippet(transcript, claim_text, max_len=max_len)
    if not snip:
        return ts, snip
    if not any(text_similarity(snip, u) > 0.86 for u in used_snippets):
        return ts, snip

    claim_words = [w for w in _tokens(claim_text) if len(w) > 2][:8]
    best_ts: Optional[float] = None
    best_snip = ""
    best_score = -1.0
    candidates: List[Tuple[Optional[float], str]] = []
    for line in (transcript or "").splitlines():
        lts, rest = _parse_timestamp_line(line)
        rest = rest.strip()
        if not rest:
            continue
        candidates.append((lts, rest))
        # Also evaluate sentence-level candidates when a line contains many sentences.
        for sent in re.split(r"(?<=[.!?])\s+", rest):
            ss = sent.strip()
            if ss and ss != rest:
                candidates.append((lts, ss))

    used_token_set = set(_tokens(" ".join(used_snippets)))
    long_claim_words = {w for w in claim_words if len(w) >= 6}
    for lts, rest in candidates:
        overlap = sum(1 for w in claim_words if w in rest.lower())
        if overlap <= 0:
            continue
        novel_overlap = sum(1 for w in claim_words if w in rest.lower() and w not in used_token_set)
        long_word_overlap = sum(1 for w in long_claim_words if w in rest.lower())
        dup_penalty = max((text_similarity(rest, u) for u in used_snippets), default=0.0)
        score = (
            float(overlap)
            + (0.7 * novel_overlap)
            + (0.8 * long_word_overlap)
            - (dup_penalty * 3.0)
        )
        if score > best_score:
            best_score = score
            best_ts = lts
            best_snip = rest
    if best_snip:
        best_snip = _trim_snippet_with_focus(best_snip, claim_words, max_len)
        return best_ts, best_snip
    return ts, snip


def extract_claims(cleaned_transcript: str, claims: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or ""))
        if txt:
            out.append(txt)
    if out:
        return out[:8]
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", cleaned_transcript or "")
        if s.strip()
    ]
    return [s for s in sentences if len(s.split()) >= 7][:8]


def _is_low_signal_fragment(text: str) -> bool:
    t = (text or "").strip()
    if len(t.split()) < 6:
        return True
    if t.endswith(("...", "…")):
        return True
    if t and t[-1] not in ".!?":
        return True
    low = t.lower()
    if _is_meta_topic_line(t) or _is_narrative_meta_noise(t):
        return True
    bad_markers = ("you know", "kind of", "sort of", "those are all ways", "um", "uh")
    if any(b in low for b in bad_markers):
        return True
    # Mid-sentence splices pasted as "insights"
    if re.search(r"\b(if you will|tentacle|bullpen of little)\b", low):
        return True
    if low.endswith((" to.", " by.", " for.", " and.", " the.")) and len(t.split()) < 18:
        return True
    # Truncated mid-clause (ASR splice ending on a function word)
    if re.search(r"\s(at|if|the|we|it|or|and|for|of|who)\s*\.\s*$", low):
        return True
    # "at 2 in the." / "work of." / "who carry."
    if re.search(
        r"\b(in the|work of|who carry|and who|to fight|still present)\s*\.\s*$", low
    ):
        return True
    # Stuttered repetition (ASR / copy glitch)
    if re.search(r"\b(\w{3,})\s+(?:\1\s+){2,}", low):
        return True
    return False


def _asr_truncation_markers(low: str, t: str) -> bool:
    """Shared ASR splice / ellipsis / stutter heuristics for claim and evidence strings."""
    if t.endswith(("...", "…")):
        return True
    if low.endswith((" to.", " by.", " for.", " and.", " the.")) and len(t.split()) < 18:
        return True
    if re.search(r"\s(at|if|the|we|it|or|and|for|of|who)\s*\.\s*$", low):
        return True
    if re.search(
        r"\b(in the|work of|who carry|and who|to fight|still present)\s*\.\s*$", low
    ):
        return True
    if re.search(r"\b(\w{3,})\s+(?:\1\s+){2,}", low):
        return True
    return False


def _is_broken_evidence_claim_line(text: str) -> bool:
    """
    True when a *claim* line is an ASR splice / truncation — not when it is short but complete.
    (Do not use ``_is_low_signal_fragment`` here: that rejects short valid claims.)
    """
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if _is_meta_topic_line(t) or _is_narrative_meta_noise(t):
        return True
    if _asr_truncation_markers(low, t):
        return True
    if t[-1] not in ".!?" and len(t.split()) > 12:
        return True
    # Mid-dialogue splice pasted as a "claim" (quoted speech + tail fragment)
    if t.count('"') >= 2 and len(t.split()) < 22 and t[-1] not in ".!?":
        return True
    if re.search(r'"\s*[A-Za-z].*\.\"\s+[A-Za-z]', t) and len(t.split()) < 24:
        return True
    return False


def _is_broken_evidence_quote_line(text: str) -> bool:
    """
    True when an *evidence* pull-quote looks truncated or stutter-corrupted.
    Slightly more lenient than claim lines (longer quotes allowed before flagging missing terminal punct).
    """
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if _is_meta_topic_line(t) or _is_narrative_meta_noise(t):
        return True
    if _asr_truncation_markers(low, t):
        return True
    if t[-1] not in ".!?" and len(t.split()) > 28:
        return True
    return False


def _generalize_sentence(text: str) -> str:
    s = _clean_claim_text(text).strip()
    if not s:
        return s
    # Strip bracket timestamps before leading \W+ trim — otherwise `[00:00:15]` becomes `00:00:15]`.
    s = re.sub(
        r"^\[[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\]\s*",
        "",
        s,
    )
    s = re.sub(r"^\W+", "", s)
    s = re.sub(r"\s+", " ", s)
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".!?":
        s += "."
    return _trim_insight_line(s, max_words=26)


def transform_into_insights(
    raw_claims: Sequence[str],
    *,
    rules: str = INSIGHT_TRANSFORM_RULES,
) -> List[str]:
    _ = rules
    cleaned: List[str] = []
    for rc in raw_claims:
        g = _generalize_sentence(str(rc))
        if not g or _is_low_signal_fragment(g):
            continue
        cleaned.append(g)
    return remove_semantic_duplicates(cleaned, threshold=SEMANTIC_DUP_THRESHOLD)[:5]


def _top_theme_terms(text: str, top_n: int = 6) -> List[str]:
    counts: Dict[str, int] = {}
    for tok in _tokens(text):
        if tok in _STOPWORDS or len(tok) < 4:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:top_n]]


def build_or_reconstruct_narrative(
    brief: Dict[str, Any],
    cleaned_transcript: str,
    insights: Sequence[str],
    *,
    rules: str = NARRATIVE_RECONSTRUCTION,
    output_mode: str = "full",
) -> Dict[str, Any]:
    _ = rules
    if output_mode == "diagnostic":
        return dict(_diagnostic_narrative_block())

    def _practical_action(seed: str) -> str:
        s = _clean_claim_text(seed)
        if not s:
            return "Run one simple 7-day experiment and track one measurable behavior change."
        phrase = " ".join(_tokens(s)[:6]) or "the main claim"
        return f"Test this week: apply {phrase} in one repeatable routine and measure the result."

    def _looks_meta(line: str) -> bool:
        low = (line or "").lower()
        bad = (
            "lacks a clear focus",
            "may confuse the audience",
            "no clear narrative",
            "insufficient signal",
            "not enough information",
            "mixed thoughts",
            "listeners are encouraged",
            "discussion highlights",
            "conversation suggests",
        )
        return any(b in low for b in bad)

    def _is_actionable(line: str) -> bool:
        low = (line or "").strip().lower()
        prefixes = (
            "test ",
            "run ",
            "choose ",
            "set ",
            "track ",
            "remove ",
            "add ",
            "make ",
            "do ",
            "pick ",
            "apply ",
        )
        return low.startswith(prefixes)

    bullets = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    bullets = [
        b
        for b in bullets
        if not _is_narrative_meta_noise(b) and not _is_meta_topic_line(b)
    ]
    if len(bullets) >= 2:
        thesis = bullets[0]
        mechanism = bullets[1]
        practical = bullets[2] if len(bullets) >= 3 else (
            insights[0] if insights else "Convert the main claim into one behavior listeners can test this week."
        )
        if _looks_meta(practical) or not _is_actionable(practical):
            practical = _practical_action(thesis)
        return {
            "core_thesis": _generalize_sentence(thesis),
            "supporting_mechanism": _generalize_sentence(mechanism),
            "practical_translation": _generalize_sentence(practical),
            "reconstructed": False,
        }
    terms = _top_theme_terms(cleaned_transcript)
    t1 = terms[0] if terms else "behavior"
    t2 = terms[1] if len(terms) > 1 else "results"
    seed = insights[0] if insights else "Clear systems outperform vague intentions."
    return {
        "core_thesis": _generalize_sentence(seed),
        "supporting_mechanism": _generalize_sentence(
            f"Repeated focus on {t1} and {t2} suggests process design drives consistent outcomes."
        ),
        "practical_translation": _generalize_sentence(_practical_action(seed)),
        "reconstructed": True,
    }


def _classify_claim_function(claim: str, evidence: str) -> str:
    low = f"{claim} {evidence}".lower()
    if any(k in low for k in ("because", "therefore", "leads to", "drives", "causes")):
        return "mechanism"
    if any(k in low for k in ("for example", "for instance", "such as")):
        return "example"
    if any(k in low for k in ("i ", "we ", "my ", "our ", "story")):
        return "anecdote"
    return "supports_argument"


def _derive_usage(claim: str, function: str) -> str:
    if function == "mechanism":
        return "Use as a teaching segment that explains cause-and-effect."
    if function == "example":
        return "Use as a concrete illustration before the main takeaway."
    if function == "anecdote":
        return "Use as a story beat to humanize the argument."
    return "Use as a framing claim for the episode thesis."


def build_evidence_mapping(
    claims: List[Dict[str, Any]],
    transcript: str,
) -> List[Dict[str, Any]]:
    """
    Structured evidence rows: id, claim, evidence, timestamp, type.
    Drops clips with no usable evidence string.
    """
    out: List[Dict[str, Any]] = []
    claims = _deduplicate_claims_for_evidence(claims)
    sentence_units = _split_into_sentence_units(transcript)
    if sentence_units:
        assigned = _assign_unique_sentence_evidence(claims, sentence_units)
    else:
        assigned = {}
    for c in claims:
        cid = str(c.get("id") or "")
        claim_txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid or not claim_txt:
            continue
        used_snips = [str(r.get("evidence") or "") for r in out if str(r.get("evidence") or "").strip()]
        row_data = assigned.get(cid)
        if row_data:
            ts = row_data.get("timestamp")
            ev = str(row_data.get("evidence") or "")
            conf = float(row_data.get("confidence") or 0.0)
            source_type = str(row_data.get("source_type") or "direct_statement")
        else:
            ts, ev = _find_evidence_snippet(transcript, claim_txt)
            ev = _clean_evidence_snippet(ev, max_words=25)
            conf = 0.45
            source_type = "fallback_match"
        if source_type == "direct_statement" and conf < MIN_EVIDENCE_CONFIDENCE:
            fts, fev, fconf, fsrc = _fallback_evidence_for_claim(
                claim_txt, sentence_units, used_snips
            )
            if fev:
                ts, ev, conf, source_type = fts, fev, fconf, fsrc
            else:
                ts2, ev2 = _find_evidence_snippet(transcript, claim_txt)
                ev2 = _clean_evidence_snippet(ev2, max_words=25)
                if ev2:
                    ts, ev, conf, source_type = (
                        ts2,
                        ev2,
                        MIN_EVIDENCE_CONFIDENCE,
                        "fallback_match",
                    )
        if not ev or len(ev.strip()) < 12:
            continue
        if _is_broken_evidence_claim_line(claim_txt):
            continue
        if _is_broken_evidence_quote_line(ev):
            continue
        fn = _classify_claim_function(claim_txt, ev)
        usage = _derive_usage(claim_txt, fn)
        row = EvidenceClaim(
            id=cid,
            timestamp=ts,
            claim=claim_txt,
            function=fn,
            usage=usage,
        )
        built = asdict(row)
        built["evidence"] = ev
        built["confidence"] = round(max(0.0, min(conf, 1.0)), 3)
        built["source_type"] = source_type
        ctype = str(c.get("claim_type") or "interpretation").lower()
        if ctype == "fact":
            built["type"] = "factual"
        elif ctype == "belief":
            built["type"] = "opinion_host"
        else:
            built["type"] = "interpretive"
        out.append(built)
    return out


def derive_application(insight: str) -> str:
    return (
        f"Convert this into one weekly test: {insight[:96]}{'…' if len(insight) > 96 else ''}"
    )


def derive_content_angle(insight: str) -> str:
    return (
        f"Use this as a segment hook, then pressure-test it with one counterexample."
    )


def inject_strategy_layer(insights: Sequence[str]) -> List[Dict[str, str]]:
    strategies: List[Dict[str, str]] = []
    for insight in insights:
        strategies.append(
            {
                "insight": insight,
                "application": derive_application(insight),
                "content_angle": derive_content_angle(insight),
            }
        )
    return strategies


def _first_question_token(claim: str) -> str:
    words = _tokens(claim)
    for w in words:
        if w not in _STOPWORDS:
            return w
    return "this claim"


def _claim_focus_phrase(claim: str, *, max_words: int = 18, max_chars: int = 115) -> str:
    """
    Short natural excerpt for embedding in host-style questions.
    Prefer a full clause/sentence when possible; avoid chopping mid-list (uses _trim_insight_line).
    """
    txt = _clean_claim_text(str(claim or "")).strip()
    if not txt:
        return "this claim"
    if len(txt) <= max_chars:
        return txt
    trimmed = _trim_insight_line(txt, max_words=max_words)
    if len(trimmed) <= max_chars:
        return trimmed
    cut = trimmed[: max_chars].rsplit(" ", 1)[0].rstrip(",;:\"'")
    if cut and cut[-1] not in ".!?":
        return cut + "."
    return cut


def generate_questions(claims: Sequence[Dict[str, Any]], mode: str = "tension") -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for c in claims:
        cid = str(c.get("id") or "")
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid or not txt:
            continue
        if mode != "tension":
            out[cid] = generate_engagement_questions(c)
            continue
        token = _first_question_token(txt)
        focus = _claim_focus_phrase(txt)
        failure_case = f"When does '{focus}' fail, even if the intent is right?"
        validation = f"What concrete evidence would confirm or disprove '{focus}' this month?"
        application = f"What one change should a listener make tomorrow based on '{focus}'?"
        contrarian = f"What would a domain expert challenge about '{focus}'?"
        out[cid] = {
            "failure_case": failure_case,
            "constraint": f"What real-world constraint blocks '{focus}' despite effort?",
            "contrarian": contrarian,
            "application": application,
            # Backward-compatible keys consumed by existing markdown/workflow adapters.
            "counterpunch": contrarian,
            "validation": validation,
        }
    return out


def identify_gaps(insights: Sequence[str]) -> List[str]:
    gaps: List[str] = []
    for i in insights:
        low = i.lower()
        if "because" not in low and "therefore" not in low:
            gaps.append("Mechanism is implied but not explicit.")
        if len(i.split()) < 9:
            gaps.append("Claim is concise but may lack concrete execution detail.")
    return remove_semantic_duplicates(gaps, threshold=0.92)[:4]


def recommend_guests(
    narrative: Dict[str, str],
    gaps: Sequence[str],
) -> List[Dict[str, str]]:
    _ = GUEST_RULES
    core = str(narrative.get("core_thesis") or "the core episode thesis")
    rows: List[Dict[str, str]] = [
        {
            "type": "Behavioral Psychologist",
            "reason": f"Validates or challenges the thesis: {core[:80]}{'…' if len(core) > 80 else ''}",
            "angle": "science vs self-help framing",
        },
        {
            "type": "Operator / Founder",
            "reason": "Tests execution under real constraints and tradeoffs.",
            "angle": "what actually works in production",
        },
        {
            "type": "Skeptical Domain Expert",
            "reason": "Challenges assumptions and surfaces failure cases the host may miss.",
            "angle": "contrarian quality control",
        },
    ]
    if gaps:
        rows.append(
            {
                "type": "Implementation Coach",
                "reason": gaps[0],
                "angle": "turn insight into a repeatable weekly action plan",
            }
        )
    return rows[:5]


def compress_to_one_line(text: str, *, style: str = "memorable") -> str:
    _ = style
    words = (text or "").split()
    if not words:
        return "Strong systems beat vague intentions."
    short = " ".join(words[:15])
    return short.rstrip(" ,;:.") + "."


def generate_takeaway(narrative: Dict[str, Any], *, output_mode: str = "full") -> str:
    _ = TAKEAWAY_RULES
    if output_mode == "diagnostic" or narrative.get("diagnostic"):
        return (
            "Diagnostic mode: verify before you package — pick one thread, label fact vs. opinion, "
            "then decide what is safe to clip or repeat."
        )
    seed = str(narrative.get("core_thesis") or "")
    line = compress_to_one_line(seed, style="memorable")
    if len(line.split()) > 15:
        line = " ".join(line.split()[:15]).rstrip(" ,;:.") + "."
    return line


def build_executable_segments(
    claims: List[Dict[str, Any]],
    *,
    max_segments: int = 3,
) -> List[Dict[str, Any]]:
    """2–3 recording-ready segment specs; trigger_clip must be a real claim id."""
    segments: List[Dict[str, Any]] = []
    for i, c in enumerate(claims[:max_segments]):
        cid = str(c.get("id") or "")
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid:
            continue
        title = txt[:72] + ("…" if len(txt) > 72 else "")
        segments.append(
            {
                "segment_title": title or f"Segment {i + 1}",
                "trigger_clip": cid,
                "host_angle": "skeptical",
                "guest_angle": "defensive",
                "goal": str(c.get("why_it_matters") or "Separate perception from evidence."),
            }
        )
    return segments


def detect_signal_mode(brief: Dict[str, Any]) -> str:
    """
    HIGH_SIGNAL: clear thesis line with enough claim substance to argue and verify.
    LOW_SIGNAL: missing thesis, outline-only, or single thin claim — do not force a fake arc.
    """
    claims = [
        c
        for c in (brief.get("claims") or [])
        if isinstance(c, dict) and str(c.get("text") or "").strip()
    ]
    if not claims:
        return "LOW_SIGNAL"

    conf_score = {"low": 0.0, "medium": 0.6, "high": 1.0}
    strengths: List[float] = []
    unique_fps: Set[str] = set()
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not txt:
            continue
        fp = re.sub(r"[^a-z0-9]+", " ", txt.lower()).strip()[:180]
        if fp:
            unique_fps.add(fp)
        length_score = min(len(txt.split()) / 12.0, 1.0)
        conf = conf_score.get(str(c.get("confidence") or "").lower(), 0.3)
        mechanism_bonus = 0.15 if any(k in txt.lower() for k in ("because", "leads", "causes", "fails", "works")) else 0.0
        strengths.append((0.55 * length_score) + (0.35 * conf) + mechanism_bonus)

    avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
    uniqueness_ratio = (len(unique_fps) / len(claims)) if claims else 0.0

    # Slightly lenient vs older 0.68 / 0.65 so borderline substantive two-claim episodes still
    # earn HIGH_SIGNAL when wording is tight but lacks a literal "because".
    if len(claims) >= 2 and avg_strength >= 0.62 and uniqueness_ratio >= 0.55:
        return "HIGH_SIGNAL"
    if len(claims) == 1:
        conf = str(claims[0].get("confidence") or "").lower()
        txt = str(claims[0].get("text") or "").strip()
        if conf == "high" and len(txt) >= 45 and any(k in txt.lower() for k in ("because", "therefore", "fails", "works")):
            return "HIGH_SIGNAL"
        if conf in ("high", "medium") and len(txt) >= 55 and "because" in txt.lower():
            return "HIGH_SIGNAL"
    return "LOW_SIGNAL"


def _brief_flags_insufficient_narrative(brief: Dict[str, Any]) -> bool:
    """True when v2/brief explicitly says the episode has no usable arc (do not invent one)."""
    snap = brief.get("episode_snapshot") or {}
    pt = str(snap.get("primary_topic") or "").lower()
    if "insufficient signal" in pt or "no clear narrative" in pt:
        return True
    for line in brief.get("narrative") or []:
        low = str(line).lower()
        if "insufficient signal" in low or "no clear narrative" in low:
            return True
    return False


def classify_output_mode(
    brief: Dict[str, Any],
    *,
    signal_mode: str,
    clean_insights: Sequence[str],
    report_readiness: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """
    full — enough signal to justify prescriptive packaging (clips, spin-off, habit actions).
    diagnostic — withhold fake coherence; surface review + verification guidance instead.

    Primary gate: insufficient-narrative metadata, LOW_SIGNAL classifier, or fewer than two
    reliable highlights. Readiness ``band`` can be ``weak`` solely because the transcript is
    under ~500 words while claims are still strong — that case does not automatically force
    diagnostic mode.
    """
    if _brief_flags_insufficient_narrative(brief):
        return "diagnostic", [
            "Brief or metadata reports insufficient narrative / weak arc — prescriptive packaging withheld.",
        ]
    good = [
        x
        for x in clean_insights
        if str(x).strip() and not is_low_signal_insight_line(str(x))
    ]
    if len(good) < 2:
        return "diagnostic", [
            "Fewer than two reliable highlight lines after quality filtering — prescriptive packaging withheld.",
        ]
    if signal_mode == "LOW_SIGNAL":
        return "diagnostic", [
            "Episode classified LOW_SIGNAL (thin thesis or weak claims) — prescriptive packaging withheld.",
        ]
    band = str((report_readiness or {}).get("band") or "").strip().lower()
    metrics = (report_readiness or {}).get("metrics") if isinstance(report_readiness, dict) else {}
    claim_ct = int((metrics or {}).get("claim_count") or 0)
    # ``minimal`` often means very short transcript *or* no claims — but a dense short clip can
    # still be HIGH_SIGNAL with solid claims; allow full mode in that case.
    if band == "minimal" and not (
        signal_mode == "HIGH_SIGNAL" and len(good) >= 2 and claim_ct >= 1
    ):
        return "diagnostic", [
            "Readiness band is minimal (very short transcript or missing claims) — prescriptive packaging withheld.",
        ]
    if band == "weak" and signal_mode == "HIGH_SIGNAL":
        return "full", []
    if band == "weak":
        return "diagnostic", [
            "Readiness band is weak — verify structure before treating clips or spin-offs as ready.",
        ]
    return "full", []


def _diagnostic_narrative_block() -> Dict[str, Any]:
    """Honest reconstruction when we must not invent a central 'thesis' for growth packaging."""
    return {
        "core_thesis": (
            "No dominant thesis line — the episode splits across competing threads rather than one "
            "defensible arc."
        ),
        "supporting_mechanism": (
            "Listeners will hear policy, personal commentary, and rhetorical claims in parallel; "
            "that fragmentation makes clip and takeaway packaging unreliable until edited."
        ),
        "practical_translation": (
            "Before you optimize for clips: separate factual reporting from opinion, flag what still "
            "needs verification, then choose one thread worth defending in public."
        ),
        "reconstructed": True,
        "diagnostic": True,
    }


def _evidence_timestamp_hint(evidence_mapping: List[Dict[str, Any]], limit: int = 5) -> str:
    """Suggest manual review windows from anchored evidence rows."""
    ts_vals: List[str] = []
    for row in evidence_mapping or []:
        if not isinstance(row, dict):
            continue
        ts = row.get("timestamp")
        if ts is None:
            continue
        try:
            ts_vals.append(f"{float(ts):.0f}s")
        except (TypeError, ValueError):
            continue
        if len(ts_vals) >= limit:
            break
    if not ts_vals:
        return (
            "No timestamped evidence rows — skim the transcript for moments that pair one clear claim "
            "with one concrete detail."
        )
    joined = ", ".join(ts_vals[:limit])
    return f"Manual review: prioritize segments around these anchor times — {joined}."


def compute_report_readiness(
    transcript: str,
    *,
    signal_mode: str,
    claim_count: int,
    evidence_row_count: int,
) -> Dict[str, Any]:
    """
    Honest expectations banner: transcript depth, signal mode, and what to do next.
    Shown in coach markdown and unified export so weak inputs read as tool limits, not bad prose.
    """
    words = len((transcript or "").split())
    notes: List[str] = []
    actions: List[str] = []

    if words < 150:
        notes.append("Transcript is very short — claims and evidence will be thin.")
        actions.append("Upload a longer transcript or full episode text for stronger structure.")
    elif words < 500:
        notes.append("Transcript is on the short side — borderline signal for automated claims.")
        actions.append("Aim for ~600+ words of continuous speech when possible.")

    if claim_count == 0:
        notes.append("No claims were extracted from the episode brief.")
        actions.append("Re-run with a richer brief pass or enable Ollama (SOAPBOXX_OLLAMA_MODEL).")

    if signal_mode == "LOW_SIGNAL":
        notes.append("Brief is classified as LOW_SIGNAL (thin thesis or weak / few claims).")
        actions.append("Tighten one thesis line and add timestamped examples in the source.")

    if evidence_row_count < 2 and claim_count >= 2:
        notes.append("Few evidence rows matched the transcript — verification will feel thin.")
        actions.append("Include bracketed times [MM:SS] or clear quotes so evidence can anchor.")

    if not notes:
        notes.append("Enough text and structure for a useful coach report.")

    if words < 150 or claim_count == 0:
        band = "minimal"
    elif signal_mode == "LOW_SIGNAL" or words < 500:
        band = "weak"
    elif signal_mode == "HIGH_SIGNAL" and evidence_row_count >= 2:
        band = "strong"
    else:
        band = "moderate"

    return {
        "band": band,
        "notes": notes[:8],
        "suggested_actions": actions[:4],
        "metrics": {
            "transcript_word_count": words,
            "claim_count": claim_count,
            "evidence_row_count": evidence_row_count,
            "signal_mode": signal_mode,
        },
    }


def merge_workflow_followups_into_engagement(
    report_v3: Dict[str, Any],
    workflow_report: Dict[str, Any],
) -> None:
    """
    When workflow AI produced follow_up_questions, fold them into ``engagement_questions``
    so coach markdown matches the workflow JSON (counterpunch / validation / application).
    Mutates ``report_v3`` in place.
    """
    fu = workflow_report.get("follow_up_questions") or []
    if not fu:
        return
    by_cid: Dict[str, Dict[str, str]] = {}
    for q in fu:
        if not isinstance(q, dict):
            continue
        cid = str(q.get("claim_id") or "").strip()
        qt = str(q.get("question_type") or "").lower().strip()
        text = str(q.get("question") or "").strip()
        if not cid or not text:
            continue
        tri = by_cid.setdefault(cid, {})
        if qt == "counter":
            tri["counterpunch"] = text
            tri["contrarian"] = text
        elif qt == "validation":
            tri["validation"] = text
        elif qt == "application":
            tri["application"] = text
    if not by_cid:
        return
    eng = dict(report_v3.get("engagement_questions") or {})
    for cid, tri in by_cid.items():
        if len(tri) < 2:
            continue
        prev = eng.get(cid) if isinstance(eng.get(cid), dict) else {}
        eng[cid] = {**prev, **tri}
    report_v3["engagement_questions"] = eng


def build_actionable_analytics(
    brief: Dict[str, Any],
    *,
    signal_mode: str = "LOW_SIGNAL",
) -> Dict[str, List[str]]:
    eg = brief.get("evidence_gaps") or {}
    supported = [str(x) for x in (eg.get("supported") or []) if str(x).strip()]
    weak = [str(x) for x in (eg.get("weak_or_unsupported") or []) if str(x).strip()]
    pm = brief.get("production_moves") or {}
    seg = pm.get("segment_to_run") or {}
    next_moves: List[str] = []
    g = (seg.get("goal") or "").strip()
    if g:
        next_moves.append(g)
    for row in brief.get("action_plan_7d") or []:
        t = str(row.get("task") or "").strip()
        if t and len(next_moves) < 4:
            next_moves.append(t)
    if not supported:
        supported = (
            ["Topic angles that could anchor a thesis once you pick one main line."]
            if signal_mode == "LOW_SIGNAL"
            else ["Claims aligned with stated transcript examples where present."]
        )
    if not weak:
        weak = (
            [
                "No single thesis line yet; competing ideas may split attention.",
                "Hard for listeners to know what to clip or share.",
            ]
            if signal_mode == "LOW_SIGNAL"
            else ["Claims that lack timestamped or third-party verification."]
        )
    if not next_moves:
        next_moves = (
            [
                "Pick one thesis before you hit record; queue other topics for later episodes.",
                "Open with one story or number, not a topic list.",
                "Close with one test: what you'll measure and what would change your mind.",
            ]
            if signal_mode == "LOW_SIGNAL"
            else [
                "Pressure-test the strongest claim with one dedicated segment next episode."
            ]
        )
    return {
        "what_worked": supported[:5],
        "what_failed": weak[:5],
        "next_move": next_moves[:5],
    }


def _coach_follow_up_questions(
    brief: Dict[str, Any],
    engagement: Dict[str, Any],
    *,
    signal_mode: str,
    max_q: int = 6,
) -> List[str]:
    """4–6 sharp, usable questions: brief host questions first, then claim-tied engagement."""
    out: List[str] = []
    pm = brief.get("production_moves") or {}
    for q in pm.get("host_questions") or []:
        s = str(q).strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= max_q:
            return out[:max_q]
    claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]
    for c in claims:
        cid = str(c.get("id") or "")
        tri = engagement.get(cid) or {}
        for key in ("counterpunch", "validation", "application"):
            s = str(tri.get(key) or "").strip()
            if s and s not in out:
                out.append(s)
            if len(out) >= max_q:
                return out[:max_q]
    eg = brief.get("evidence_gaps") or {}
    for x in eg.get("proof_needed") or []:
        s = str(x).strip()
        if s and s not in out:
            out.append(f"What primary source or experiment would settle this: {s}?")
        if len(out) >= max_q:
            break
    if len(out) < 4:
        snap = brief.get("episode_snapshot") or {}
        pt = str(snap.get("primary_topic") or "").strip()
        if signal_mode == "LOW_SIGNAL":
            pool = [
                f"If you had to cut half this episode and keep one idea, what stays - and what becomes its own episode: {pt or 'your strongest thread'}?",
                "What metric would prove the opening worked - and what would you change if it didn't?",
                "What would a skeptical listener say you assumed without saying?",
            ]
        else:
            pool = [
                "What is the strongest fair counterargument to your sharpest claim - and what evidence would you accept?",
                "What should listeners do differently this week based on this episode alone?",
            ]
        for p in pool:
            if p not in out:
                out.append(p)
            if len(out) >= 4:
                break
    return out[:max_q]


def _coach_themes_from_brief(
    brief: Dict[str, Any], clean_insights: List[str], max_themes: int = 4
) -> List[Dict[str, str]]:
    snap = brief.get("episode_snapshot") or {}
    primary = str(snap.get("primary_topic") or "").strip()
    narrative = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    narrative = [n for n in narrative if not _is_narrative_meta_noise(n) and not _is_meta_topic_line(n)]
    seeds: List[str] = []
    if primary:
        seeds.append(primary)
    for n in narrative:
        if n not in seeds:
            seeds.append(n)
    for ins in clean_insights:
        if ins not in seeds:
            seeds.append(ins)
    if not seeds:
        seeds = ["Episode themes (add transcript depth for sharper themes)."]
    out: List[Dict[str, str]] = []
    for i, line in enumerate(seeds[:max_themes]):
        label = f"Theme {i + 1}"
        discussed = line[:240] + ("…" if len(line) > 240 else "")
        out.append(
            {
                "label": label,
                "discussed": discussed,
                "implying": "The show is treating this as actionable for the listener, not background noise.",
                "matters": "Turn this into one decision, one example, and one next step - or it stays noise.",
            }
        )
    return out


def _polish_thesis_one_sentence(raw: str) -> str:
    """
    One sentence, clear stance: strip fluff, take first sentence, enforce ending punctuation.
    """
    s = _clean_claim_text(str(raw or "")).strip()
    if not s:
        return "Name one proposition a skeptical listener should accept after this episode."
    # Drop common filler openers (stance should read direct).
    low = s.lower()
    for prefix in (
        "this episode argues that ",
        "the episode argues that ",
        "the through-line: ",
        "in this episode, ",
    ):
        if low.startswith(prefix):
            s = s[len(prefix) :].strip()
            low = s.lower()
            break
    # First sentence only (avoid multi-sentence "thesis" blobs).
    for sep in (". ", "! ", "? "):
        if sep in s[: min(400, len(s))]:
            cut = s.split(sep, 1)[0] + sep.strip()[0]
            s = cut.strip()
            break
    else:
        if s.endswith("."):
            pass
        elif s and s[-1] not in ".!?":
            s += "."
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 220:
        s = s[:217].rsplit(" ", 1)[0] + "."
    return s


def _finalize_episode_thesis_line(
    snap: Dict[str, Any],
    thesis_quality: Optional[Dict[str, str]],
    signal_mode: str,
    claims: List[Dict[str, Any]],
    clean_insights: List[str],
) -> str:
    """Non-negotiable one-sentence thesis for spine + coach (argument, not vibes)."""
    tq = thesis_quality
    if tq and str(tq.get("suggested_argument") or "").strip():
        return _polish_thesis_one_sentence(str(tq["suggested_argument"]))
    if signal_mode == "HIGH_SIGNAL" and claims:
        raw = str(claims[0].get("text") or "").strip()
        if raw and not _looks_like_quote_fragment_thesis(raw):
            return _polish_thesis_one_sentence(raw)
    return _polish_thesis_one_sentence(_suggested_argument_thesis(snap, clean_insights, claims or []))


def _personalized_coach_intro(creator: str, genre: str, title: str) -> str:
    """Light 'made for you' framing (creator / genre / title)."""
    c = (creator or "").strip()
    g = (genre or "").strip()
    t = (title or "").strip()
    if c and g:
        return f"*For **{c}**'s show - **{g}** format - tailored to this episode:*"
    if c:
        return f"*For **{c}**'s show, tailored to this episode:*"
    if g:
        return f"*Given your **{g}** format:*"
    if t:
        tail = t if len(t) <= 120 else t[:117] + "…"
        return f'*Tailored to "{tail}":*'
    return ""


def _pick_uncomfortable_title(title: str) -> str:
    opts = (
        "Why this episode is weaker than it sounds",
        "Where the argument breaks under pressure",
        "The uncomfortable read",
    )
    key = sum(ord(c) for c in (title or "")[:200]) % len(opts)
    return opts[key]


def _build_uncomfortable_insight(
    snap: Dict[str, Any],
    where_issues: List[str],
    signal_mode: str,
    title: str,
    clean_insights: List[str],
    episode_thesis: str,
) -> Dict[str, str]:
    """Direct, slightly sharp — the hook traditional coaching avoids."""
    tit = _pick_uncomfortable_title(title)
    parts: List[str] = []
    if signal_mode == "LOW_SIGNAL":
        parts.append(
            "The tape has more *topics* than *proof* — listeners may agree in the room and still "
            "repeat nothing specific tomorrow."
        )
    if where_issues:
        w0 = str(where_issues[0]).strip()
        parts.append(f"The pressure point is: {w0}")
    elif clean_insights:
        parts.append(
            "You signal stakes early, but the middle often stays atmospheric — the falsifiable claim "
            "arrives late or not at all."
        )
    else:
        parts.append(
            "Without a named mechanism, the story stays persuasive but not checkable — which caps clips and shares."
        )
    if episode_thesis:
        parts.append(
            f"If your thesis is “{episode_thesis[:160]}{'…' if len(episode_thesis) > 160 else ''}”, "
            "ask what would make you *wrong* on mic — not just what would make you sound fair."
        )
    pt = str(snap.get("primary_topic") or "").strip()
    if pt and not _is_meta_topic_line(pt) and len(title) > 8:
        parts.append(
            f"Someone scanning only the title may expect a harder verdict on “{pt[:80]}” than the conversation actually delivers."
        )
    body = " ".join(parts)
    return {"title": tit, "body": body}


def _build_claim_stakes_compact(
    claims: List[Dict[str, Any]],
    engagement: Dict[str, Any],
    max_rows: int = 5,
) -> List[str]:
    """
    Conclusions-only: one line per claim (what to prove on mic) — hides triad machinery.
    """
    out: List[str] = []
    for c in claims[:max_rows]:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        raw = _clean_claim_text(str(c.get("text") or ""))[:200]
        if not raw:
            continue
        tri = engagement.get(cid) if isinstance(engagement.get(cid), dict) else {}
        counter = str((tri or {}).get("counterpunch") or "").strip()
        validate = str((tri or {}).get("validation") or "").strip()
        app = str((tri or {}).get("application") or "").strip()
        move = app or validate or counter
        if not move:
            move = "Name one source or number that would change your mind."
        line = f"**[{cid}]** {raw} — *On mic:* {move[:180]}{'…' if len(move) > 180 else ''}"
        out.append(line)
    return out


_QUOTE_FRAGMENT_OPENERS = (
    "unfortunately,",
    "we're talking",
    "we are talking",
    "no, i'm",
    "no i'm",
    "at this point,",
    "thanks to things like",
    "i'm not even",
    "i am not even",
)


def _looks_like_quote_fragment_thesis(text: str) -> bool:
    """Cold opens often masquerade as a thesis — long quotes, hedges, or dialogue scraps."""
    t = (text or "").strip()
    if len(t) < 28:
        return False
    low = t.lower()
    if any(low.startswith(p) for p in _QUOTE_FRAGMENT_OPENERS):
        return True
    if len(t.split()) > 44:
        return True
    if t[0] in "\"'“”‘" and len(t) > 80:
        return True
    if t[-1] not in ".!?" and len(t) > 72:
        return True
    return False


def _suggested_argument_thesis(
    snap: Dict[str, Any],
    clean_insights: List[str],
    claims: List[Dict[str, Any]],
) -> str:
    """One-sentence argumentative thesis — not a transcript quote."""
    title = str(snap.get("title") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    if title and len(title) > 12:
        tail = title.split(":")[-1].strip() if ":" in title else title
        tail = tail[:140].strip()
        return (
            f"{tail} is a claim about who gets protected when incentives and rules collide — "
            f"and the episode must pick a side."
        )
    if pt and not _is_meta_topic_line(pt) and len(pt) > 8:
        return (
            f"{pt[:200]}{'…' if len(pt) > 200 else ''} — "
            f"one falsifiable claim, defended on the record."
        )
    if claims:
        g = _generalize_sentence(str(claims[0].get("text") or ""))
        if g and not _looks_like_quote_fragment_thesis(g):
            return g
    if len(clean_insights) > 1 and not _looks_like_quote_fragment_thesis(clean_insights[1]):
        return _generalize_sentence(clean_insights[1])
    return (
        "State one sentence: what single proposition should a skeptical listener accept after this episode?"
    )


def _derive_contrarian_hook(
    snap: Dict[str, Any],
    where_issues: List[str],
    clean_insights: List[str],
    title: str,
) -> str:
    """Non-obvious angle — complements 'organized' coaching."""
    if where_issues:
        w0 = str(where_issues[0]).strip()
        return (
            f"The edit points at: {w0} — the hidden angle is often **who benefits** if listeners stay "
            f"emotional but never name the rule, sponsor, or metric. Say that actor once, on mic."
        )
    if title:
        return (
            f"Listeners may already agree with the *vibe* of “{title[:90]}{'…' if len(title) > 90 else ''}”. "
            f"The gap is usually the **mechanism**: what rule, product design, or incentive makes the harm predictable?"
        )
    if clean_insights:
        return (
            "Steel-man the strongest counter-case you did not fully address — that is usually where "
            "the shareable clip lives."
        )
    return (
        "Name one stakeholder or incentive that wins if the audience feels the problem but cannot describe the system."
    )


def build_coach_report(
    brief: Dict[str, Any],
    transcript: str,
    signal_mode: str,
    *,
    clean_insights: List[str],
    evidence_mapping: List[Dict[str, Any]],
    engagement: Dict[str, Any],
    guests_v3: List[Dict[str, Any]],
    analytics: Dict[str, List[str]],
    claims: List[Dict[str, Any]],
    output_mode: str = "full",
    diagnostic_reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Podcaster-facing coach structure (10 sections). Filled from brief + v3 fields; no transcript paste.
    """
    snap = brief.get("episode_snapshot") or {}
    title = str(snap.get("title") or "")
    narrative = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    competing_topics: List[str] = []
    if narrative:
        competing_topics = narrative[:6]
    elif clean_insights:
        competing_topics = clean_insights[:6]
    else:
        pt = str(snap.get("primary_topic") or "").strip()
        if pt:
            competing_topics = [pt]

    thesis_quality: Optional[Dict[str, str]] = None
    fragment_lead: Optional[str] = None

    if signal_mode == "HIGH_SIGNAL" and claims:
        thesis = str(claims[0].get("text") or "").strip()
        if _looks_like_quote_fragment_thesis(thesis):
            thesis_quality = {
                "issue": "Lead claim reads like a cold-open clip, not a one-sentence argument.",
                "suggested_argument": _suggested_argument_thesis(snap, clean_insights, claims),
                "fix": "Reframe as stakes or mechanism — clips support a thesis; they are rarely the thesis.",
            }
            fragment_lead = thesis
    elif clean_insights and _looks_like_quote_fragment_thesis(clean_insights[0]):
        thesis_quality = {
            "issue": "First highlight reads like a clip, not a thesis.",
            "suggested_argument": _suggested_argument_thesis(snap, clean_insights, claims),
            "fix": "Open with the clip; state a separate one-sentence thesis.",
        }

    episode_thesis = _finalize_episode_thesis_line(
        snap, thesis_quality, signal_mode, claims, clean_insights
    )

    # --- 1. Diagnosis (thesis first; everything else supports it) ---
    diagnosis_lines: List[str] = []
    if output_mode == "diagnostic":
        diagnosis_lines.append(
            "**Report output:** Diagnostic mode — spin-off, clip, and habit-action blocks below are "
            "review-first, not publish-ready packaging."
        )
        if diagnostic_reasons:
            diagnosis_lines.append("**Why diagnostic:** " + " ".join(diagnostic_reasons))

    diagnosis_lines.append(f"**Thesis (one sentence):** {episode_thesis}")

    if signal_mode == "HIGH_SIGNAL" and claims:
        if fragment_lead:
            diagnosis_lines.append(
                "**Thesis check:** Your strongest line reads like transcript, not a publishable claim."
            )
            diagnosis_lines.append(f"**Verbatim lead (act one, not thesis):** {fragment_lead}")
        eg = brief.get("evidence_gaps") or {}
        sup = eg.get("supported") or []
        wk = eg.get("weak_or_unsupported") or []
        if sup:
            diagnosis_lines.append(
                "**Support:** " + "; ".join(str(x) for x in sup[:2] if str(x).strip())
            )
        if wk:
            diagnosis_lines.append(
                "**Gaps:** " + "; ".join(str(x) for x in wk[:2] if str(x).strip())
            )
    else:
        diagnosis_lines.append(
            "**Honest read:** The transcript reads exploratory or thin for one arc — "
            "or SoapBoxx could not extract a claim without inventing it."
        )
        if competing_topics:
            diagnosis_lines.append(
                "**Competing threads:** " + " | ".join(competing_topics[:5])
            )
        if clean_insights and _looks_like_quote_fragment_thesis(clean_insights[0]):
            diagnosis_lines.append(
                "**Note:** First highlight reads like a clip — open with it, but keep the thesis line separate."
            )

    diagnosis_lines.append(
        "**Retention:** One thesis → one repeatable idea for clips and shares."
    )

    themes = _coach_themes_from_brief(brief, clean_insights, max_themes=4)

    what_worked = list(analytics.get("what_worked") or [])[:5]
    pm = brief.get("production_moves") or {}
    clip_cands = pm.get("clip_candidates") or []
    for cl in clip_cands[:2]:
        s = str(cl).strip()
        if s and s not in what_worked:
            what_worked.append(f"Clip angle: {s}")
        if len(what_worked) >= 5:
            break

    where_issues: List[str] = list(analytics.get("what_failed") or [])[:5]
    rule_fix = (
        "One episode = one decision: pick the tradeoff you are defending, then cut everything that does not serve it."
        if signal_mode == "LOW_SIGNAL"
        else "Every segment must point back to the thesis; if it doesn't, it's a different episode."
    )

    contrarian_hook = {
        "title": "The angle listeners might miss",
        "body": _derive_contrarian_hook(snap, where_issues, clean_insights, title),
    }
    uncomfortable_insight = _build_uncomfortable_insight(
        snap, where_issues, signal_mode, title, clean_insights, episode_thesis
    )
    claim_stakes = _build_claim_stakes_compact(claims, engagement)
    personalized_intro = _personalized_coach_intro(
        str(snap.get("creator") or ""),
        str(snap.get("genre") or ""),
        title,
    )

    strongest = (
        clean_insights[0]
        if clean_insights
        else (competing_topics[0] if competing_topics else "Main theme")
    )
    spin_title = f"Deeper on: {strongest[:56]}{'…' if len(strongest) > 56 else ''}"
    spin_structure = (
        "(1) State the single problem. (2) One framework or story. (3) One listener action. (4) What you'll measure."
    )
    clip_ops: List[str] = []
    for cl in clip_cands[:2]:
        clip_ops.append(
            f"**Moment:** {str(cl)[:200]} - **Why:** Concrete promise + payoff; easy to title and share."
        )
    if not clip_ops and clean_insights:
        clip_ops.append(
            "**Moment:** Lead with your clearest promise - **Why:** Sets expectation so the rest of the episode can deliver."
        )
    seg_weak = str((pm.get("segment_to_run") or {}).get("name") or "Thesis line").strip()
    segment_idea = (
        f'Add a tight "{seg_weak}" block that forces one conclusion before you move topics - fixes drift without new gear.'
    )

    questions = _coach_follow_up_questions(
        brief, engagement, signal_mode=signal_mode, max_q=6
    )

    guest_blocks: List[Dict[str, str]] = []
    if signal_mode == "LOW_SIGNAL":
        strategy_intro = (
            "Exploratory guests (broad operators, skeptical peers) - pressure-test priorities, "
            "not credentials alone."
        )
        if not guests_v3:
            guest_blocks.append(
                {
                    "guest_type": "Operator / producer",
                    "adds": "Real tradeoffs from analytics and shipping schedule - turns topics into decisions.",
                }
            )
            guest_blocks.append(
                {
                    "guest_type": "Friendly skeptic host",
                    "adds": "Forces you to pick one thesis by disagreeing with your default.",
                }
            )
        for g in guests_v3[:3]:
            guest_blocks.append(
                {
                    "guest_type": str(g.get("role") or "Guest"),
                    "adds": str(g.get("why_this_episode") or "Sharpens the angle with lived experience."),
                }
            )
    else:
        strategy_intro = (
            "Expert guests (specific authority) - bring verification, edge cases, and citations tied to your thesis."
        )
        for g in guests_v3[:3]:
            guest_blocks.append(
                {
                    "guest_type": str(g.get("role") or "Expert"),
                    "adds": str(g.get("why_this_episode") or "Evidence and counterexamples for the main claim."),
                }
            )
        if not guest_blocks:
            guest_blocks.append(
                {
                    "guest_type": "Domain specialist",
                    "adds": "Stress-tests the strongest claim with data or practice-level detail.",
                }
            )

    segment_upgrade = (
        f'**Single-ladder close (90s):** (1) One-sentence thesis. (2) One example or number. '
        f'(3) One behavior change. Fixes "outline without payoff" in a {signal_mode.lower()} episode.'
    )

    fix_plan_src = list(analytics.get("next_move") or [])[:5]
    _pad = [
        "Say your thesis out loud in the cold open; if you can't, rewrite before you record.",
        "Cut one competing topic and schedule it as a separate episode.",
        "End with one measurable test (metric or behavior) for the next show.",
    ]
    immediate_fix = list(fix_plan_src[:3])
    for p in _pad:
        if len(immediate_fix) >= 3:
            break
        if p not in immediate_fix:
            immediate_fix.append(p)
    immediate_fix = immediate_fix[:3]

    good = (
        "There is raw material and intent - enough to coach."
        if clean_insights or claims
        else "Metadata and topic scope are present; the work is shaping, not summarizing."
    )
    must_change = (
        "Pick one thesis and starve the rest until it lands."
        if signal_mode == "LOW_SIGNAL"
        else "Tighten evidence and conclusion around the lead claim."
    )
    if_fixed = (
        "Retention, clips, and referrals rise when listeners can repeat your idea in one sentence."
    )

    if output_mode == "diagnostic":
        spin_title = "Defer spin-off planning until one thesis thread survives an edit pass."
        spin_structure = (
            "Not assigned — the episode reads as multi-threaded or under-verified for a packaged spin-off brief."
        )
        clip_ops = [
            f"No high-signal auto clip picks. {_evidence_timestamp_hint(evidence_mapping)}",
            "Skip outros, transitions, and lyric fragments; favor one claim plus one checkable detail.",
        ]
        segment_idea = (
            "Next recording: a **validation block** — state the strongest public-facing claim, what would "
            "change your mind, and what primary source you would accept."
        )
        segment_upgrade = (
            "**Diagnostic close (90s):** Name the single sentence you'd defend if quoted; flag what still "
            "needs sourcing before you optimize for distribution."
        )
        immediate_fix = [
            "Tag assertions as reporting vs. inference vs. opinion before clipping.",
            "Write down two primary sources you want before repeating the hottest claim in public.",
            "Isolate segments that mix incompatible frames (news vs. rally vs. personal story).",
        ]
        good = (
            "There is usable tension for an informed audience; the gap is defensibility and arc — "
            "not chemistry or effort."
        )
        must_change = (
            "Stop expanding with growth packaging on a fragmented spine — verify or edit before you clip."
        )
        if_fixed = (
            "Clips and repurposing work once one arc is legible and claims are labeled for the audience you want."
        )
        strategy_intro = (
            "Diagnostic bookings: prioritize verification, sourcing, and steel-manned counterarguments — "
            "not generic motivation angles."
        )
        guest_blocks = [
            {
                "guest_type": "Reporter or records researcher",
                "adds": "Primary documents and timelines — reduces reliance on rhetorical peaks alone.",
            },
            {
                "guest_type": "Friendly skeptic (peer)",
                "adds": "Surfaces the strongest counter-case before you publish or clip.",
            },
        ]

    out_cr: Dict[str, Any] = {
        "signal_mode": signal_mode,
        "output_mode": output_mode,
        "episode_diagnosis": {
            "mode": signal_mode,
            "body": diagnosis_lines,
        },
        "thesis_quality": thesis_quality,
        "episode_thesis": episode_thesis,
        "personalized_intro": personalized_intro,
        "contrarian_hook": contrarian_hook,
        "uncomfortable_insight": uncomfortable_insight,
        "claim_stakes": claim_stakes,
        "themes": themes,
        "what_worked": what_worked[:5],
        "where_it_breaks": {"issues": where_issues, "rule": rule_fix},
        "opportunities": {
            "spinoff_title": spin_title,
            "spinoff_structure": spin_structure,
            "clip_moments": clip_ops,
            "segment_idea": segment_idea,
        },
        "follow_up_questions": questions,
        "guest_strategy": {"intro": strategy_intro, "guests": guest_blocks[:4]},
        "segment_upgrade": segment_upgrade,
        "immediate_fix_plan": immediate_fix,
        "bottom_line": {"good": good, "must_change": must_change, "if_fixed": if_fixed},
        "meta": {
            "title": title,
            "transcript_words": len((transcript or "").split()),
        },
    }
    return out_cr


def validate_references(
    report: Union[Dict[str, Any], str],
    *,
    valid_claim_ids: Optional[Set[str]] = None,
) -> Tuple[bool, List[str]]:
    """
    Ensure every referenced cN exists in valid_claim_ids.
    If valid_claim_ids is None, derive from report['claims'] or report['evidence_mapping'].
    """
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except json.JSONDecodeError:
            report = {"_raw": report}
    valid = valid_claim_ids
    if valid is None:
        valid = set()
        for c in report.get("claims") or []:
            if isinstance(c, dict) and c.get("id"):
                valid.add(str(c["id"]))
        for e in report.get("evidence_mapping") or []:
            if isinstance(e, dict) and e.get("id"):
                valid.add(str(e["id"]))
    blob = json.dumps(report, ensure_ascii=False)
    refs: Set[str] = set()
    for m in _REF_ID.finditer(blob):
        refs.add(f"c{m.group(1)}")
    if not valid:
        if not refs:
            return True, []
        return False, [
            f"Dangling reference {r}: no claims defined in report" for r in sorted(refs)
        ]
    bad = sorted(refs - valid)
    errors = [f"Invalid claim reference {bid}: not in {sorted(valid)}" for bid in bad]
    return len(bad) == 0, errors


# Cross-layer narrative alignment: single compile-time transform (see ``build_v3_report``).
# Jaccard tiers (short-text–aware): soft warning → repair → collapse — not one binary gate.
_CONSISTENCY_SOFT_WARN = 0.10
_CONSISTENCY_REPAIR = 0.07
_CONSISTENCY_COLLAPSE = 0.05


def _jaccard_tier(j: float) -> str:
    if j >= _CONSISTENCY_SOFT_WARN:
        return "ok"
    if j >= _CONSISTENCY_REPAIR:
        return "soft"
    if j >= _CONSISTENCY_COLLAPSE:
        return "repair"
    return "collapse"


def apply_identity_consistency_to_report_v3(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    **Single enforcement point** for v3: run from ``build_v3_report`` only.

    - **Spine:** ``narrative_reconstruction`` fields use tiered Jaccard vs identity anchor.
    - **Coach:** ``episode_thesis`` is **not** blindly copied when both layers are plausibly
      on-identity: it mirrors the narrative spine only when the narrative layer was repaired,
      or when the coach line is severely off-anchor. Otherwise coach wording can diverge from
      reconstruction (interpretive layer preserved).
    - **Observability:** ``_consistency_tier_histogram``, ``_consistency_jaccard_samples``,
      ``_consistency_soft_suggestions`` (pressure for future edits / batch analytics — not silent).

    Sets ``_consistency_drift_notes`` when soft drift is detected; ``_consistency_fix_applied``
    when any replacement runs. Does not change claims, evidence rows, or scores.
    """
    meta = report.get("meta") if isinstance(report.get("meta"), dict) else {}
    snap = report.get("episode_snapshot") if isinstance(report.get("episode_snapshot"), dict) else {}
    anchor = build_identity_anchor(meta, snap)
    if len(anchor) < 8:
        return report

    pt = str(snap.get("primary_topic") or "").strip()
    title = str(snap.get("title") or "").strip()
    fallback_thesis = pt or title or anchor[:280]

    drift_notes: List[str] = []
    soft_suggestions: List[str] = []
    tier_hist: Dict[str, int] = {"ok": 0, "soft": 0, "repair": 0, "collapse": 0}
    jaccard_samples: List[Dict[str, Any]] = []

    def _bump_tier(tier: str) -> None:
        if tier in tier_hist:
            tier_hist[tier] += 1

    fix = False
    narrative_layer_mutated = False
    nr = report.get("narrative_reconstruction")
    if not isinstance(nr, dict):
        nr = {}
        report["narrative_reconstruction"] = nr

    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else None

    def _align_nr_field(key: str) -> None:
        nonlocal fix, narrative_layer_mutated
        val = str(nr.get(key) or "").strip()
        if not val:
            return
        j = jaccard_tokens(val, anchor)
        tier = _jaccard_tier(j)
        _bump_tier(tier)
        jaccard_samples.append({"field": f"narrative_reconstruction.{key}", "jaccard": round(j, 4), "tier": tier})
        if tier == "ok":
            return
        if tier == "soft":
            drift_notes.append(f"{key}: soft_drift_vs_identity (jaccard={j:.3f})")
            soft_suggestions.append(
                f"Tighten {key} toward title/topic identity (jaccard={j:.3f}); "
                f"revisit before the next export if drift persists across episodes."
            )
            return
        if tier in ("repair", "collapse"):
            nr[key] = fallback_thesis
            fix = True
            narrative_layer_mutated = True
            drift_notes.append(f"{key}: realigned_to_identity (tier={tier}, jaccard={j:.3f})")

    # Primary spine first, then supporting fields (same tier rules).
    for key in ("core_thesis", "supporting_mechanism", "practical_translation"):
        _align_nr_field(key)

    insights = [str(x).strip() for x in (report.get("clean_insights") or [])[:5] if str(x).strip()]
    combined = " ".join(
        [
            str(nr.get("core_thesis") or ""),
            " ".join(insights[:3]),
        ]
    ).strip()
    if combined:
        jc = jaccard_tokens(combined, anchor)
        ct = _jaccard_tier(jc)
        _bump_tier(ct)
        jaccard_samples.append(
            {"field": "combined(core_thesis+clean_insights)", "jaccard": round(jc, 4), "tier": ct}
        )
        if jc < _CONSISTENCY_COLLAPSE:
            nr["core_thesis"] = fallback_thesis
            drift_notes.append("combined_insights_gate: collapse_to_identity_anchor")
            fix = True
            narrative_layer_mutated = True

    spine = str(nr.get("core_thesis") or fallback_thesis).strip()

    # Coach thesis: mirror repaired narrative, or fix standalone coach drift — else preserve coach.
    if cr is not None and spine:
        old_et = str(cr.get("episode_thesis") or "").strip()
        j_et = jaccard_tokens(old_et, anchor) if old_et else 1.0
        t_et = _jaccard_tier(j_et)
        if old_et:
            _bump_tier(t_et)
            jaccard_samples.append({"field": "coach_report.episode_thesis", "jaccard": round(j_et, 4), "tier": t_et})
        if narrative_layer_mutated:
            if old_et != spine:
                cr["episode_thesis"] = spine
                fix = True
                drift_notes.append("episode_thesis: mirrored_to_repaired_narrative_spine")
        elif old_et and t_et in ("repair", "collapse"):
            cr["episode_thesis"] = spine
            fix = True
            drift_notes.append("episode_thesis: realigned (off_anchor; narrative layer unchanged)")
        elif old_et and t_et == "soft":
            drift_notes.append(f"episode_thesis: soft_drift_vs_identity (jaccard={j_et:.3f})")
            soft_suggestions.append(
                f"Coach thesis wording drifts from identity (jaccard={j_et:.3f}); "
                f"optional manual contrast vs narrative reconstruction."
            )

    # Clip hooks: only rewrite on severe drift (collapse tier) — thesis vs packaging can differ.
    if cr is not None:
        opp = cr.get("opportunities") if isinstance(cr.get("opportunities"), dict) else {}
        cms_raw = opp.get("clip_moments") or []
        if isinstance(cms_raw, list) and cms_raw:
            new_cms: List[str] = []
            changed_cm = False
            for i, cm in enumerate(cms_raw):
                s = str(cm).strip()
                if not s:
                    continue
                j = jaccard_tokens(s, anchor)
                ct = _jaccard_tier(j)
                _bump_tier(ct)
                jaccard_samples.append(
                    {"field": f"coach_report.opportunities.clip_moments[{i}]", "jaccard": round(j, 4), "tier": ct}
                )
                if ct == "collapse":
                    new_cms.append(f"Anchor clips to the episode thesis: {spine[:120]}")
                    changed_cm = True
                else:
                    new_cms.append(s)
            if changed_cm:
                opp["clip_moments"] = new_cms[:8]
                cr["opportunities"] = opp
                fix = True

    report["_consistency_tier_histogram"] = tier_hist
    report["_consistency_jaccard_samples"] = jaccard_samples
    if soft_suggestions:
        report["_consistency_soft_suggestions"] = soft_suggestions
    if drift_notes:
        report["_consistency_drift_notes"] = drift_notes
    if fix:
        report["_consistency_fix_applied"] = True
    return report


def _distinctive_token_set(text: str) -> Set[str]:
    """Content tokens for cross-layer overlap (not stopwords / generic transcript filler)."""
    return {
        w
        for w in _tokens(text)
        if len(w) > 2 and w not in _STOPWORDS and w not in _GENERIC_EVIDENCE_WORDS
    }


def _union_identity_distinctive_bag(report: Dict[str, Any]) -> Set[str]:
    meta = report.get("meta") if isinstance(report.get("meta"), dict) else {}
    snap = report.get("episode_snapshot") if isinstance(report.get("episode_snapshot"), dict) else {}
    anchor = build_identity_anchor(meta, snap)
    bag = _distinctive_token_set(anchor)
    for c in report.get("claims") or []:
        if isinstance(c, dict):
            bag |= _distinctive_token_set(str(c.get("text") or ""))
    return bag


def _filter_clean_insights_identity_coherence(report: Dict[str, Any]) -> bool:
    """
    Drop clean_insight lines that share no distinctive vocabulary with the identity anchor + claims.
    Conservative: no-op when the bag is too small or every line would be removed.
    """
    ins = report.get("clean_insights")
    if not isinstance(ins, list) or not ins:
        return False
    bag = _union_identity_distinctive_bag(report)
    if len(bag) < 2:
        return False
    new: List[str] = []
    for line in ins:
        s = str(line).strip()
        if not s:
            continue
        if _distinctive_token_set(s) & bag:
            new.append(s)
    if not new or len(new) >= len(ins):
        return False
    report["_clean_insights_coherence_filtered"] = len(ins) - len(new)
    report["clean_insights"] = new
    return True


def _refresh_dual_lens_and_takeaway(
    report: Dict[str, Any],
    brief: Dict[str, Any],
    cleaned: str,
    meta: Dict[str, str],
) -> None:
    """
    Recompute dual_lens + takeaway after identity / claim / SGV passes mutate narrative and coach text.
    Initial assembly happens earlier with pre-pass state; without this, exports can show a stale core story.
    """
    sm = str(report.get("signal_mode") or "")
    report["dual_lens"] = assemble_dual_lens_package(
        brief,
        cleaned,
        meta,
        signal_mode=sm,
        narrative_reconstruction=report.get("narrative_reconstruction") or {},
        coach_report=report.get("coach_report") or {},
        claims=list(report.get("claims") or []),
    )
    report["takeaway"] = generate_takeaway(
        report.get("narrative_reconstruction") or {},
        output_mode=str(report.get("output_mode") or "full"),
    )


def _v3_atomic_ground_truth_resolve(explicit: Optional[bool]) -> bool:
    if explicit is not None:
        return bool(explicit)
    v = os.getenv("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _brief_claim_row_from_atomic(c: Any) -> Dict[str, Any]:
    cat = str(getattr(c, "category", "") or "")
    if cat == "historical_fact":
        claim_type = "fact"
    elif cat == "rhetorical":
        claim_type = "belief"
    else:
        claim_type = "interpretation"
    return {
        "id": c.id,
        "text": _clean_claim_text(str(getattr(c, "raw_statement", "") or "")),
        "claim_type": claim_type,
        "confidence": getattr(c, "confidence", "medium"),
        "evidence_basis": getattr(c, "evidence_basis", "unknown"),
    }


def _v3_guests_from_atomic_recommendations(
    guests: Sequence[Any],
    topic_graph: Any,
    claim_by_id: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Map atomic guest recommendations to v3 guest rows (no narrative-based guest synthesis)."""
    out: List[Dict[str, Any]] = []
    nodes = list(getattr(topic_graph, "nodes", None) or [])
    topic_by_id = {str(getattr(n, "topic_id", "")): n for n in nodes if getattr(n, "topic_id", None)}

    for g in guests:
        tid = str(getattr(g, "target_topic_id", "") or "")
        topic = topic_by_id.get(tid)
        label = ""
        if topic is not None:
            label = str(getattr(topic, "label", "") or "").strip()
        if not label:
            label = "topic cluster"
        target_claim = ""
        if topic is not None:
            for cid in list(getattr(topic, "evidence_claim_ids", None) or []):
                bc = claim_by_id.get(str(cid))
                if bc:
                    target_claim = str(bc.get("text") or "")
                    break
        if not target_claim:
            for bc in claim_by_id.values():
                target_claim = str(bc.get("text") or "")
                if target_claim:
                    break
        reason = getattr(g, "recommendation_reason", None)
        why = ""
        if reason is not None:
            why = str(getattr(reason, "primary_angle", "") or "").strip()
            if not why:
                why = str(getattr(reason, "what_they_would_challenge", "") or "").strip()
        gt = str(getattr(g, "guest_type", "") or "academic")
        title_g = gt.replace("_", " ").title()
        out.append(
            {
                "guest": f"{title_g} — {label[:120]}",
                "role": gt,
                "why_this_episode": why,
                "target_claim": _clean_claim_text(target_claim),
            }
        )
    return out


def build_v3_report(
    brief: Dict[str, Any],
    transcript: str,
    *,
    metadata: Optional[Dict[str, str]] = None,
    atomic_ground_truth: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Assemble full v3 report dict: clean insights, evidence rows, engagement, guests, segments, analytics.

    When atomic ground truth is on (default), structured claims and graph guests come from
    ``run_atomic_pipeline`` only; brief ``claims`` / ``guests`` rows are not used for those fields.
    """
    meta = dict(metadata or {})
    cleaned = (transcript or "").strip()
    use_atomic = _v3_atomic_ground_truth_resolve(atomic_ground_truth)
    atomic_env: Any = None
    atomic_err: Optional[str] = None
    if use_atomic and run_atomic_pipeline is not None:
        try:
            atomic_env = run_atomic_pipeline(cleaned)
        except Exception as e:
            atomic_err = str(e)
            atomic_env = None

    if atomic_env is not None:
        claims = [_brief_claim_row_from_atomic(c) for c in atomic_env.claims]
        brief = {**brief, "claims": claims}
    elif use_atomic:
        claims = []
        brief = {**brief, "claims": claims}
    else:
        claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]
    claim_by_id = {str(c.get("id")): c for c in claims if c.get("id")}

    raw_claims = extract_claims(cleaned, claims)
    transformed_insights = transform_into_insights(raw_claims, rules=INSIGHT_TRANSFORM_RULES)
    if transformed_insights:
        clean_insights = clean_key_highlights(transformed_insights)
    else:
        fallback_narrative = [str(x) for x in (brief.get("narrative") or []) if str(x).strip()]
        claim_texts = [str(c.get("text") or "") for c in claims]
        clean_insights = clean_key_highlights(fallback_narrative + claim_texts)

    evidence_mapping = build_evidence_mapping(claims, cleaned)
    for row in evidence_mapping:
        row.setdefault("function", "supports_argument")
        row.setdefault("usage", "Use as a framing claim for the episode thesis.")
    engagement = generate_questions(claims, mode="tension")
    strategies = inject_strategy_layer(clean_insights)

    guests_v3: List[Dict[str, Any]] = []
    if atomic_env is not None:
        guests_v3 = _v3_guests_from_atomic_recommendations(
            atomic_env.guest_recommendations,
            atomic_env.topic_graph,
            claim_by_id,
        )
    else:
        for g in brief.get("guests") or []:
            if not isinstance(g, dict):
                continue
            mid = str(g.get("maps_to_claim_id") or "").strip()
            claim = claim_by_id.get(mid) or (claims[0] if claims else {})
            if not claim:
                continue
            guests_v3.append(map_guest_to_claim(g, claim))
    gaps = identify_gaps(clean_insights)
    signal_mode = detect_signal_mode(brief)
    report_readiness = compute_report_readiness(
        cleaned,
        signal_mode=signal_mode,
        claim_count=len(claims),
        evidence_row_count=len(evidence_mapping),
    )
    v3_gates = evaluate_v3_quality_gates(brief, cleaned)
    report_readiness["quality_gates"] = v3_gates
    rnotes = report_readiness.get("notes")
    if not isinstance(rnotes, list):
        rnotes = []
        report_readiness["notes"] = rnotes
    for n in v3_gates.get("notes") or []:
        if n not in rnotes:
            rnotes.append(n)
    if atomic_err:
        rnotes.append(f"atomic_pipeline_error: {atomic_err}")

    output_mode, diagnostic_reasons = classify_output_mode(
        brief,
        signal_mode=signal_mode,
        clean_insights=clean_insights,
        report_readiness=report_readiness,
    )
    if v3_gates.get("force_diagnostic") and output_mode != "diagnostic":
        output_mode = "diagnostic"
        diagnostic_reasons = list(diagnostic_reasons or []) + [
            "Automated quality gates flagged title/topic mismatch or weak claim structure — prescriptive packaging withheld.",
        ]
    report_readiness["output_mode"] = output_mode
    report_readiness["diagnostic_reasons"] = diagnostic_reasons

    narrative = build_or_reconstruct_narrative(
        brief,
        cleaned,
        transformed_insights,
        rules=NARRATIVE_RECONSTRUCTION,
        output_mode=output_mode,
    )

    forced_guests = recommend_guests(narrative, gaps=gaps)
    if atomic_env is None and len(guests_v3) < 3:
        for fg in forced_guests:
            guests_v3.append(
                {
                    "guest": fg.get("type"),
                    "role": fg.get("type"),
                    "why_this_episode": fg.get("reason"),
                    "target_claim": narrative.get("core_thesis"),
                    "angle": fg.get("angle"),
                }
            )
            if len(guests_v3) >= 5:
                break

    segments = build_executable_segments(claims, max_segments=3)
    analytics = build_actionable_analytics(brief, signal_mode=signal_mode)
    coach_report = build_coach_report(
        brief,
        cleaned,
        signal_mode,
        clean_insights=clean_insights,
        evidence_mapping=evidence_mapping,
        engagement=engagement,
        guests_v3=guests_v3,
        analytics=analytics,
        claims=claims,
        output_mode=output_mode,
        diagnostic_reasons=diagnostic_reasons,
    )
    narrative = dict(narrative)
    _et = (coach_report or {}).get("episode_thesis")
    if _et and str(_et).strip():
        narrative["core_thesis"] = str(_et).strip()

    dual_lens = assemble_dual_lens_package(
        brief,
        cleaned,
        meta,
        signal_mode=signal_mode,
        narrative_reconstruction=narrative,
        coach_report=coach_report,
        claims=claims,
    )

    snap = dict(brief.get("episode_snapshot") or {})
    _sanitize_episode_snapshot(snap, claims)
    report: Dict[str, Any] = {
        "workflow_version": REPORT_V3_VERSION,
        "signal_mode": signal_mode,
        "dual_lens": dual_lens,
        "coach_report": coach_report,
        "episode_snapshot": snap,
        "narrative_reconstruction": narrative,
        "clean_insights": clean_insights,
        "evidence_mapping": evidence_mapping,
        "strategies": strategies,
        "engagement_questions": engagement,
        "guests": guests_v3,
        "segments": segments,
        "takeaway": generate_takeaway(narrative, output_mode=output_mode),
        "analytics_actionable": analytics,
        "claims": claims,
        "output_mode": output_mode,
        "meta": {
            "title": meta.get("title") or snap.get("title") or "",
            "creator": meta.get("creator") or snap.get("creator") or "",
            "genre": meta.get("genre") or snap.get("genre") or "",
            "generated_at": meta.get("generated_at") or _utc_now_iso(),
            "structured_intelligence_source": (
                "atomic_pipeline" if atomic_env is not None else "episode_brief_v2"
            ),
        },
        "report_readiness": report_readiness,
    }
    if atomic_env is not None and envelope_to_json is not None:
        report["atomic_pipeline"] = envelope_to_json(atomic_env)
    r3 = apply_identity_consistency_to_report_v3(report)
    r3 = apply_claim_quality_gate(r3)
    r3 = apply_semantic_grounding_validator(r3)
    if _filter_clean_insights_identity_coherence(r3):
        r3["strategies"] = inject_strategy_layer(r3.get("clean_insights") or [])
    _refresh_dual_lens_and_takeaway(r3, brief, cleaned, meta)
    r3["_guest_decision_trace"] = build_guest_decision_trace(r3)
    apply_system_health_label(r3)
    r3["_invariant_contract_check"] = validate_v3_invariants(r3)
    return r3


def validate_v3_report_or_raise(report: Dict[str, Any]) -> None:
    valid = {str(c.get("id")) for c in (report.get("claims") or []) if c.get("id")}
    for e in report.get("evidence_mapping") or []:
        if isinstance(e, dict) and e.get("id"):
            valid.add(str(e["id"]))
    ok, errs = validate_references(report, valid_claim_ids=valid)
    if not ok:
        raise ValueError("; ".join(errs))


def build_episode_spine(
    r3: Dict[str, Any],
    workflow_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single structured object: **thesis → claims → guests**. All other sections are supporting detail.
    ``workflow_report`` adds guest rows with ``claim_id`` when enrichment ran.
    """
    wf = workflow_report or {}
    snap = r3.get("episode_snapshot") or {}
    nr = r3.get("narrative_reconstruction") or {}
    cr = r3.get("coach_report") or {}

    thesis = str(cr.get("episode_thesis") or "").strip()
    if not thesis:
        thesis = str(nr.get("core_thesis") or "").strip()
    tq = cr.get("thesis_quality") if isinstance(cr.get("thesis_quality"), dict) else None
    if not thesis and tq and str(tq.get("suggested_argument") or "").strip():
        thesis = str(tq["suggested_argument"]).strip()
    if not thesis or _is_meta_topic_line(thesis):
        thesis = str(snap.get("primary_topic") or "").strip()
    if not thesis:
        ins = r3.get("clean_insights") or []
        if ins and str(ins[0]).strip():
            thesis = _generalize_sentence(str(ins[0]))[:280]
    if not thesis:
        thesis = (
            "State one argumentative thesis this episode should prove — then align every claim and guest to it."
        )

    claims_out: List[Dict[str, str]] = []
    for c in r3.get("claims") or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        txt = _clean_claim_text(str(c.get("text") or ""))[:360]
        if txt:
            claims_out.append({"id": cid, "line": txt})

    if not claims_out:
        for row in (r3.get("evidence_mapping") or [])[:12]:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("id") or "").strip()
            if not cid:
                continue
            cl = _clean_claim_text(str(row.get("claim") or ""))[:360]
            if cl:
                claims_out.append({"id": cid, "line": cl})

    guests_out: List[Dict[str, str]] = []
    gr = _workflow_body_guest_rows(wf)
    for g in gr[:10]:
        if not isinstance(g, dict):
            continue
        guests_out.append(
            {
                "name": str(g.get("name") or "").strip(),
                "title": str(g.get("title") or g.get("role") or "").strip(),
                "claim_id": str(g.get("claim_id") or "").strip(),
                "angle": str(g.get("topic_angle") or g.get("angle") or "").strip(),
            }
        )
    if not guests_out:
        for g in (r3.get("guests") or [])[:6]:
            if not isinstance(g, dict):
                continue
            guests_out.append(
                {
                    "name": str(g.get("guest") or "").strip(),
                    "title": str(g.get("role") or "").strip(),
                    "claim_id": "",
                    "angle": str(g.get("why_this_episode") or "").strip(),
                }
            )

    return {"thesis": thesis, "claims": claims_out, "guests": guests_out}


def format_episode_spine_markdown_lines(spine: Dict[str, Any]) -> List[str]:
    """Markdown block: thesis, then claims, then guests — everything routes through these."""
    lines: List[str] = [
        "## The spine",
        "",
        f"**Thesis (one sentence):** {spine.get('thesis', '')}",
        "",
        "**Claims:**",
    ]
    claims = spine.get("claims") or []
    if claims:
        for c in claims:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "")
            line = str(c.get("line") or "").strip()
            if cid and line:
                lines.append(f"- **[{cid}]** {line}")
    else:
        lines.append(
            "- *(No claims in this run — enable Ollama + brief extraction, or paste claims into the v2 brief.)*"
        )

    lines.extend(["", "**Guests:**"])
    guests = spine.get("guests") or []
    if guests:
        lines.append("| Guest | Role | Serves claim | Why book them |")
        lines.append("| --- | --- | --- | --- |")
        for g in guests:
            if not isinstance(g, dict):
                continue
            nm = str(g.get("name") or "").replace("|", "\\|")
            tl = str(g.get("title") or "").replace("|", "\\|")
            cid = str(g.get("claim_id") or "") or "—"
            ang = str(g.get("angle") or "").replace("|", "\\|")
            lines.append(f"| {nm} | {tl} | {cid} | {ang} |")
    else:
        lines.append(
            "- *(No guests mapped — run workflow AI enrichment, or use the Guest Strategy section below.)*"
        )

    lines.append("")
    lines.append("*Below: detail that should back the thesis, claims, and guest picks.*")
    return lines


def render_episode_report_v3_markdown(
    report: Dict[str, Any],
    *,
    workflow_report: Optional[Dict[str, Any]] = None,
) -> str:
    """SoapBoxx Episode Report — coach layout (10 sections); uses `coach_report` when present."""
    meta = report.get("meta") or {}
    snap = report.get("episode_snapshot") or {}
    title = meta.get("title") or snap.get("title", "")
    creator = meta.get("creator") or snap.get("creator", "")
    genre = meta.get("genre") or snap.get("genre", "")
    gen = meta.get("generated_at") or _utc_now_iso()
    sm = (report.get("signal_mode") or "") or (
        (report.get("coach_report") or {}).get("signal_mode") or "LOW_SIGNAL"
    )
    cr = report.get("coach_report") or {}

    rr = report.get("report_readiness") or {}
    band = str(rr.get("band") or "").strip()
    rnotes = [str(x).strip() for x in (rr.get("notes") or []) if str(x).strip()]
    ract = [str(x).strip() for x in (rr.get("suggested_actions") or []) if str(x).strip()]
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}

    om_coach = str(rr.get("output_mode") or "").strip().lower()
    sig_label = _episode_signal_badge(rr if isinstance(rr, dict) else {}, report)
    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
        _export_header_tagline(),
        "",
        f"**Title:** {title}",
        f"**Show / creator:** {creator or '—'}",
        f"**Genre:** {genre or '—'}",
        f"**Generated:** {gen}",
        f"**Classifier signal:** {sm} · **Readiness:** {sig_label}",
        _signal_badge_caption(sig_label, om_coach),
        "",
        "## 0. Readiness & expectations",
    ]
    if band:
        lines.append(f"**Band:** {band}")
    om = str(rr.get("output_mode") or "").strip().lower()
    if om:
        lines.append(f"**Output mode:** {om}")
    if om == "diagnostic" and rr.get("diagnostic_reasons"):
        lines.append("**Why diagnostic:**")
        for dr in rr.get("diagnostic_reasons") or []:
            lines.append(f"- {dr}")
    if metrics:
        wc = metrics.get("transcript_word_count")
        cc = metrics.get("claim_count")
        er = metrics.get("evidence_row_count")
        lines.append(
            f"*Words: {wc} · Claims: {cc} · Evidence rows: {er} · Signal: {metrics.get('signal_mode', sm)}*"
        )
    if rnotes:
        lines.append("")
        lines.append("**What this means:**")
        for n in rnotes:
            lines.append(f"- {n}")
    if ract:
        lines.append("")
        lines.append("**Suggested next steps:**")
        for a in ract:
            lines.append(f"- {a}")
    spine = build_episode_spine(report, workflow_report)
    lines.extend(["", *format_episode_spine_markdown_lines(spine), "", "## 1. Episode Diagnosis"])

    if cr:
        intro = str(cr.get("personalized_intro") or "").strip()
        if intro:
            lines.append(intro)
        ed = cr.get("episode_diagnosis") or {}
        for para in ed.get("body") or []:
            lines.append(str(para))
        ui = cr.get("uncomfortable_insight") or {}
        if isinstance(ui, dict) and str(ui.get("body") or "").strip():
            utit = str(ui.get("title") or "The uncomfortable read").strip()
            lines.extend(["", f"## 1a. {utit}", str(ui.get("body") or "").strip()])
        ch = cr.get("contrarian_hook") or {}
        if isinstance(ch, dict) and str(ch.get("body") or "").strip():
            lines.extend(
                [
                    "",
                    f"## 1b. {ch.get('title') or 'The angle listeners might miss'}",
                    str(ch.get("body") or "").strip(),
                ]
            )
        stakes = cr.get("claim_stakes") or []
        if isinstance(stakes, list) and stakes:
            lines.extend(["", "## 1c. Claim stakes (on-mic conclusions)"])
            for row in stakes:
                lines.append(f"- {row}")
            lines.append("")
        lines.extend(["", "## 2. Extracted Themes (Clean + Structured)"])
        for th in cr.get("themes") or []:
            if isinstance(th, dict):
                lines.append(f"**{th.get('label', 'Theme')}:**")
                lines.append(f"- What was discussed: {th.get('discussed', '')}")
                lines.append(f"- What the host is implying: {th.get('implying', '')}")
                lines.append(f"- Why it matters: {th.get('matters', '')}")
                lines.append("")
        lines.extend(["## 3. What Worked"])
        for x in cr.get("what_worked") or []:
            lines.append(f"- {x}")
        if not cr.get("what_worked"):
            lines.append("- *(No strengths flagged yet - add transcript depth.)*")
        wb = cr.get("where_it_breaks") or {}
        lines.extend(["", "## 4. Where It Breaks"])
        for x in wb.get("issues") or []:
            lines.append(f"- {x}")
        lines.append(f"- **Rule:** {wb.get('rule', '')}")
        lines.extend(["", "## 5. Actionable Content Opportunities"])
        opp = cr.get("opportunities") or {}
        lines.append("**A. Spin-off episode idea**")
        lines.append(f"- **Title:** {opp.get('spinoff_title', '')}")
        lines.append(f"- **Structure:** {opp.get('spinoff_structure', '')}")
        lines.append("")
        lines.append("**B. Clip opportunity**")
        for cm in opp.get("clip_moments") or []:
            lines.append(f"- {cm}")
        if not opp.get("clip_moments"):
            lines.append("- *(No clip candidates in brief - lead with your clearest promise.)*")
        lines.append("")
        lines.append("**C. Segment idea**")
        lines.append(f"- {opp.get('segment_idea', '')}")
        lines.extend(["", "## 6. Smarter Follow-Up Questions"])
        for q in cr.get("follow_up_questions") or []:
            lines.append(f"- {q}")
        gs = cr.get("guest_strategy") or {}
        lines.extend(["", "## 7. Guest Strategy"])
        lines.append(str(gs.get("intro", "")))
        for g in gs.get("guests") or []:
            if isinstance(g, dict):
                lines.append(
                    f"- **{g.get('guest_type', 'Guest')}** - {g.get('adds', '')}"
                )
        lines.extend(["", "## 8. Segment Upgrade"])
        lines.append(str(cr.get("segment_upgrade", "")))
        lines.extend(["", "## 9. Immediate Fix Plan (CRITICAL)"])
        for i, step in enumerate(cr.get("immediate_fix_plan") or [], start=1):
            lines.append(f"{i}. {step}")
        bl = cr.get("bottom_line") or {}
        lines.extend(["", "## 10. Bottom Line"])
        lines.append(
            f"{bl.get('good', '')} {bl.get('must_change', '')} {bl.get('if_fixed', '')}".strip()
        )
    else:
        lines.append("*Coach report unavailable - run `build_v3_report` with full pipeline.*")

    dl = report.get("dual_lens")
    if isinstance(dl, dict) and dl.get("episode_lens_type"):
        w = dl.get("weights") or {}
        lines.extend(
            [
                "",
                "## 11. Dual lens (parallel read + weights)",
                f"**Episode lens:** {dl.get('episode_lens_type')} "
                f"(heuristic confidence {dl.get('confidence', '—')}) · "
                f"**Weights:** narrative {w.get('narrative')} / analytical {w.get('analytical')}",
            ]
        )
        syn = dl.get("synthesis") if isinstance(dl.get("synthesis"), dict) else {}
        cp = str(syn.get("core_positioning") or "").strip()
        if cp:
            lines.extend(["", "### Core positioning (weighted)", cp])
        cn = syn.get("collision_notes") or []
        if cn:
            lines.extend(["", "### Synthesis (collisions)"])
            for c in cn:
                lines.append(f"- {c}")
        eb = syn.get("execution_bias") if isinstance(syn.get("execution_bias"), dict) else {}
        if eb:
            lines.extend(["", "### Execution bias"])
            lines.append(f"- **Clips:** {eb.get('clips', '')}")
            lines.append(f"- **Actions:** {eb.get('actions', '')}")
        inj = str(dl.get("prompt_injection") or "").strip()
        if inj:
            lines.extend(["", "### Prompt injection (downstream LLM)", "```text", inj, "```"])

    lines.extend(
        [
            "",
            "---",
            "## Appendix - Evidence & engagement (structured)",
        ]
    )
    for row in report.get("evidence_mapping") or []:
        ts = row.get("timestamp")
        ts_s = f"{float(ts):.1f}s" if ts is not None else "n/a"
        lines.append(
            f"- **[{row.get('id')}]** {ts_s} | {row.get('type')} | **Claim:** {row.get('claim')} "
            f"| **Evidence:** {row.get('evidence')}"
        )
    if not report.get("evidence_mapping"):
        lines.append(
            "- *(No evidence rows; low-signal or offline brief - coach sections above still apply.)*"
        )

    lines.extend(
        ["", "**Per-claim pressure tests (detail — optional)**"]
    )
    for cid in sorted(
        (report.get("engagement_questions") or {}).keys(),
        key=lambda x: int(x[1:]) if str(x)[1:].isdigit() else 0,
    ):
        tri = report["engagement_questions"][cid]
        lines.append(f"### [{cid}]")
        lines.append(f"- **Counterpunch:** {tri.get('counterpunch')}")
        lines.append(f"- **Validation:** {tri.get('validation')}")
        lines.append(f"- **Application:** {tri.get('application')}")

    lines.extend(["", "---", f"*SoapBoxx Episode Intelligence - workflow v{REPORT_V3_VERSION}*"])
    return "\n".join(lines)


def _normalized_evidence_claim_key(claim: str) -> str:
    """Stable key for deduping near-duplicate claim lines across evidence rows."""
    return re.sub(r"[^a-z0-9]+", " ", (claim or "").lower()).strip()[:140]


def _dedupe_repeated_sentences(text: str, *, max_words: int = 220) -> str:
    """
    Collapse stuttered ASR/LLM repeats (same sentence back-to-back) and trim length.
    """
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"\s*\[cut\]\s*$", "", t, flags=re.I).strip()
    parts = re.split(r"(?<=[.!?])\s+", t)
    out: List[str] = []
    prev: Optional[str] = None
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if prev is not None and p == prev:
            continue
        out.append(p)
        prev = p
    joined = " ".join(out).strip()
    words = joined.split()
    if len(words) > max_words:
        joined = _truncate_words(joined, max_words=max_words)
    return joined


def _export_header_tagline() -> str:
    """Single line: version + where to read more (compact)."""
    return (
        f"*SoapBoxx Episode Intelligence · v{REPORT_V3_VERSION} · "
        f"Full spec: `docs/network_episode_brief_v3.md` · "
        f"Compact brief: `docs/network_episode_brief_v2.md`*"
    )


def _signal_badge_caption(badge: str, output_mode: str) -> str:
    """One line explaining what the badge means for the reader."""
    om = (output_mode or "").strip().lower()
    b = (badge or "").strip().lower()
    if om == "diagnostic":
        return "*This run is **review-first**: verify claims and arc before clips or growth packaging.*"
    if b == "strong":
        return "*Signal: **strong** — enough structure for thesis, clips, and verification.*"
    if b == "moderate":
        return "*Signal: **moderate** — solid direction; tighten claims and evidence where noted.*"
    return "*Signal: **low** — exploratory or thin extraction; use as an edit checklist, not a finished package.*"


def _episode_signal_badge(report_readiness: Dict[str, Any], r3: Dict[str, Any]) -> str:
    """Human-readable signal label for the export header (strong / moderate / low)."""
    rr = report_readiness or {}
    band = str(rr.get("band") or "").strip().lower()
    sm = str((r3 or {}).get("signal_mode") or "").strip().upper()
    if band == "strong":
        return "strong"
    if band == "moderate":
        return "moderate"
    if band in ("weak", "minimal"):
        return "low"
    if sm == "LOW_SIGNAL":
        return "low"
    if sm == "HIGH_SIGNAL":
        return "moderate"
    return "moderate"


def _format_master_blueprint_v1_section(bundle: Dict[str, Any]) -> List[str]:
    """Markdown block when ``bundle`` includes ``blueprint_v1`` from Master Blueprint v1."""
    bp = bundle.get("blueprint_v1")
    if not isinstance(bp, dict):
        return []
    sr = bp.get("strategist_report") if isinstance(bp.get("strategist_report"), dict) else None
    if sr:
        snap = sr.get("snapshot") if isinstance(sr.get("snapshot"), dict) else {}
        core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
        up = sr.get("upgrade_plan") if isinstance(sr.get("upgrade_plan"), dict) else {}
        sf = up.get("structure_fix") if isinstance(up.get("structure_fix"), dict) else {}
        aud = (
            sr.get("audience_engagement_intelligence")
            if isinstance(sr.get("audience_engagement_intelligence"), dict)
            else {}
        )
        sv = (
            sr.get("strategic_value_for_network")
            if isinstance(sr.get("strategic_value_for_network"), dict)
            else {}
        )
        lines: List[str] = [
            "## Podcast performance & growth intelligence",
            "",
            f"**Positioning:** {str(bp.get('product_positioning') or 'A podcast performance and growth intelligence layer').strip()}",
            "",
        ]
        punchline = str(sr.get("punchline_header") or "").strip()
        if not punchline:
            punchline = "This episode underperforms due to weak positioning and lack of clear takeaway, but can be significantly improved with stronger framing, sharper questions, and more structured delivery."
        lines.append("**Podcast Performance Insight**")
        lines.append(f"> {punchline}")
        lines.append("")
        score = snap.get("overall_score")
        signal = str(snap.get("signal_strength") or "").strip()
        diagnosis = str(snap.get("diagnosis") or "").strip()
        scoring_basis = str(snap.get("scoring_basis") or "").strip()
        if score or signal or diagnosis:
            lines.append("**Snapshot**")
            lines.append(f"- Overall score: {score if score not in (None, '') else '—'} / 10")
            if signal:
                lines.append(f"- Signal strength: {signal}")
            if diagnosis:
                lines.append(f"- Diagnosis: {diagnosis}")
            if scoring_basis:
                lines.append(f"- Scoring basis: {scoring_basis}")
            lines.append("")
        thesis = str(core.get("thesis") or "").strip()
        if thesis:
            lines.append(f"**Thesis:** {thesis}")
            lines.append("")
        key_claims = [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()]
        evidence_anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
        tension_position = core.get("tension_position") if isinstance(core.get("tension_position"), dict) else {}
        if key_claims:
            lines.append("**Key claims**")
            for c in key_claims[:3]:
                lines.append(f"- {c}")
            lines.append("")
        if evidence_anchors:
            lines.append("**Evidence anchors**")
            for row in evidence_anchors[:3]:
                cl = str(row.get("claim") or "").strip()
                an = str(row.get("anchor") or "").strip()
                if cl and an:
                    lines.append(f"- {cl} -> {an}")
            lines.append("")
        implicit_argument = str(tension_position.get("implicit_argument") or "").strip()
        stronger_position = str(tension_position.get("stronger_position") or "").strip()
        if implicit_argument or stronger_position:
            lines.append("**Tension call**")
            if implicit_argument:
                lines.append(f"- {implicit_argument}")
            if stronger_position:
                lines.append(f"- {stronger_position}")
            lines.append("")
        working = [str(x).strip() for x in (sr.get("what_working") or []) if str(x).strip()]
        missing = [str(x).strip() for x in (sr.get("what_missing") or []) if str(x).strip()]
        if working:
            lines.append("**What's working**")
            for w in working[:5]:
                lines.append(f"- {w}")
            lines.append("")
        if missing:
            lines.append("**What's missing / weak**")
            for m in missing[:5]:
                lines.append(f"- {m}")
            lines.append("")
        repo = str(up.get("reposition_episode") or "").strip()
        if repo:
            lines.append(f"**Repositioning:** {repo}")
        if sf:
            lines.append("**Structure fix**")
            for k, label in (
                ("opening_hook", "Opening hook"),
                ("midpoint_tension", "Midpoint tension"),
                ("closing_takeaway", "Closing takeaway"),
            ):
                v = str(sf.get(k) or "").strip()
                if v:
                    lines.append(f"- {label}: {v}")
        clips = [str(x).strip() for x in (up.get("clip_opportunities") or []) if str(x).strip()]
        if clips:
            lines.append("**Clip opportunities**")
            for c in clips[:4]:
                lines.append(f"- {c}")
        if repo or sf or clips:
            lines.append("")
        if aud:
            lines.append("**Audience & engagement intelligence**")
            for k, label in (
                ("listener_takeaway_gap", "Listener takeaway gap"),
                ("behavior_change", "Behavior change"),
                ("weekly_improvement_insight", "Weekly improvement insight"),
            ):
                v = str(aud.get(k) or "").strip()
                if v:
                    lines.append(f"- {label}: {v}")
            lines.append("")
        qs = [str(x).strip() for x in (sr.get("question_upgrade") or []) if str(x).strip()]
        if qs:
            lines.append("**Question upgrade**")
            for q in qs[:3]:
                lines.append(f"- {q}")
            lines.append("")
        guests = [g for g in (sr.get("guest_content_opportunities") or []) if isinstance(g, dict)]
        if guests:
            lines.append("**Guest & content opportunities**")
            for g in guests[:4]:
                who = str(g.get("who_type") or "").strip()
                why = str(g.get("why_they_matter") or "").strip()
                unlock = str(g.get("what_they_unlock") or "").strip()
                if who:
                    tail = " ".join([x for x in (why, unlock) if x]).strip()
                    lines.append(f"- **{who}:** {tail}".rstrip())
            lines.append("")
        if sv:
            lines.append("**Strategic value (network)**")
            wu = str(sv.get("what_improving_unlocks") or "").strip()
            upf = str(sv.get("where_it_underperforms") or "").strip()
            if wu:
                lines.append(f"- What improving unlocks: {wu}")
            if upf:
                lines.append(f"- Where it underperforms: {upf}")
            lines.append("")
        nli = [str(x).strip() for x in (sr.get("network_level_insight") or []) if str(x).strip()]
        if nli:
            lines.append("**Network-level insight**")
            for x in nli[:4]:
                lines.append(f"- {x}")
            lines.append("")
        rollout = str(sr.get("network_rollout_line") or "").strip()
        if rollout:
            lines.append(f"> {rollout}")
            lines.append("")
        one_line_fix = str(sr.get("one_line_fix") or "").strip()
        if not one_line_fix:
            one_line_fix = "If this episode were reframed around a clear argument and structured for tension, it would become significantly more engaging and shareable."
        conviction = str(sr.get("conviction_statement") or "").strip()
        if conviction:
            lines.append(f"**Conviction:** {conviction}")
            lines.append("")
        lines.append(f"**1-Line Fix:** {one_line_fix}")
        return lines
    th = str(bp.get("thesis") or "").strip()
    if not th:
        return []
    lines: List[str] = [
        "## Master blueprint (v1)",
        "",
    ]
    cl = bp.get("classification") or {}
    if isinstance(cl, dict) and (cl.get("type") or str(cl.get("reasoning") or "").strip()):
        ct = str(cl.get("type") or "—")
        cf = cl.get("confidence")
        rs = str(cl.get("reasoning") or "").strip()
        tail = f" — {rs}" if rs else ""
        lines.append(f"**Classification:** {ct} (confidence {cf}){tail}".rstrip())
        lines.append("")
    lines.append(f"**Thesis:** {th}")
    lines.append("")
    syn = bp.get("synthesis") or {}
    if isinstance(syn, dict) and any(str(syn.get(k) or "").strip() for k in syn):
        lines.append("**Synthesis**")
        labels = (
            ("key_insight", "Key insight"),
            ("friction_point", "Friction"),
            ("strength", "Gets right"),
            ("gap", "Gap"),
        )
        for key, lab in labels:
            v = str(syn.get(key) or "").strip()
            if v:
                lines.append(f"- **{lab}:** {v}")
        lines.append("")
    clips = bp.get("clips") or []
    if isinstance(clips, list) and clips:
        lines.append("**Clip candidates**")
        for c in clips[:5]:
            if not isinstance(c, dict):
                continue
            txt = str(c.get("text") or "").strip()
            if not txt:
                continue
            reason = str(c.get("reason") or "").strip()
            lines.append(f"- {txt}" + (f" — *{reason}*" if reason else ""))
        lines.append("")
    acts = bp.get("actions") or []
    if isinstance(acts, list) and acts:
        lines.append("**Suggested actions**")
        for a in acts:
            s = str(a).strip()
            if s:
                lines.append(f"- {s}")
    return lines


def _derive_strategist_report_from_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    abort, rs = strategist_truth_gate_bundle(bundle)
    if abort:
        raise ValueError(
            "strategist derivation blocked (insufficient signal): " + "; ".join(rs)
        )
    bp = bundle.get("blueprint_v1")
    if isinstance(bp, dict) and isinstance(bp.get("strategist_report"), dict):
        return dict(bp.get("strategist_report") or {})
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    snap = dict(r3.get("episode_snapshot") or {})
    claims = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]
    thesis = str(((r3.get("coach_report") or {}).get("episode_thesis") or snap.get("primary_topic") or "").strip())
    if not thesis:
        thesis = "The episode needs one clear argument with explicit tension and a concrete listener takeaway."
    key_claims = [str(c.get("text") or "").strip() for c in claims if str(c.get("text") or "").strip()][:3]
    if not key_claims:
        key_claims = [str(e.get("claim") or "").strip() for e in (wf.get("evidence_map") or []) if isinstance(e, dict) and str(e.get("claim") or "").strip()][:3]
    evidence_anchors: List[Dict[str, str]] = []
    for i, cl in enumerate(key_claims[:3]):
        anchor = ""
        if i < len(wf.get("evidence_map") or []):
            row = (wf.get("evidence_map") or [])[i]
            if isinstance(row, dict):
                anchor = str(row.get("evidence") or "").strip()
        if not anchor and i < len(r3.get("evidence_mapping") or []):
            row2 = (r3.get("evidence_mapping") or [])[i]
            if isinstance(row2, dict):
                anchor = str(row2.get("evidence") or "").strip()
        if not anchor:
            anchor = "In a central scene, the host revisits the same argument without raising the stakes."
        evidence_anchors.append({"claim": cl, "anchor": anchor})
    highlights = [str(h.get("insight") or "").strip() for h in (wf.get("highlights") or []) if isinstance(h, dict) and str(h.get("insight") or "").strip()][:3]
    if len(highlights) < 3:
        highlights.extend([str(x).strip() for x in (r3.get("clean_insights") or []) if str(x).strip() and str(x).strip() not in highlights][: 3 - len(highlights)])
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    word_count = int(metrics.get("transcript_word_count") or 0)
    claim_count = int(metrics.get("claim_count") or len(key_claims or []))
    evidence_row_count = int(metrics.get("evidence_row_count") or len(evidence_anchors or []))
    mode = "evidence" if (word_count >= 120 and claim_count >= 1 and evidence_row_count >= 1) else "interpretive"
    weaknesses: List[str] = []
    bl = (r3.get("coach_report") or {}).get("bottom_line") or {}
    for k in ("must_change", "if_fixed"):
        v = str(bl.get(k) or "").strip()
        if not v:
            continue
        lv = v.lower()
        if any(
            bad in lv
            for bad in (
                "no claims were extracted",
                "low_signal",
                "diagnostic mode",
                "enable ollama",
                "reality check",
            )
        ):
            continue
        weaknesses.append(v)
        if len(weaknesses) >= 3:
            break
    if mode == "interpretive":
        while len(weaknesses) < 3:
            fill = [
                "The episode resets topics before one claim is defended.",
                "No speaker pressure-tests the central claim once it appears.",
                "The close ends without one explicit listener action.",
            ][len(weaknesses)]
            weaknesses.append(fill)
    else:
        while len(weaknesses) < 3:
            fill = [
                "The strongest claim appears, but no one challenges it with a hard counterexample.",
                "Evidence is present, but the argument does not escalate after the midpoint.",
                "The close does not convert the argument into one concrete listener action.",
            ][len(weaknesses)]
            weaknesses.append(fill)
    clips = [str(e.get("claim") or "").strip() for e in (wf.get("evidence_map") or []) if isinstance(e, dict) and str(e.get("claim") or "").strip()][:3]
    if len(clips) < 2:
        clips.extend([str(x).strip() for x in key_claims if str(x).strip() not in clips][: 2 - len(clips)])
    behavior_change = "Apply one explicit listener behavior change tied to the core argument this week."
    recommendations = [
        "Open with one explicit argument in the first 60 seconds.",
        "Force a midpoint counterargument that challenges the core claim.",
        "Close with one concrete listener action and proof of progress.",
    ]
    return {
        "punchline_header": "Strong topic, but the episode keeps shifting claims instead of defending one argument. Reframe around one claim and engagement rises.",
        "core_problem": weaknesses[0],
        "snapshot": {
            # Heuristic defaults when deriving a strategist-shaped view without a real blueprint.
            # Suppressed when strict export emits an insufficient-signal card instead (see
            # ``workflow_export_should_abort_insufficient`` / ``render_insufficient_signal_export_markdown``).
            "overall_score": 6,
            "signal_strength": "Moderate",
            "diagnosis": weaknesses[0],
            "scoring_basis": "8-10 clear thesis + strong clips + actionable takeaway; 5-7 decent story but weak clarity/payoff; 1-4 unclear point and low engagement value",
        },
        "core_breakdown": {
            "thesis": thesis,
            "key_claims": key_claims[:3],
            "evidence_anchors": evidence_anchors[:3],
            "tension_position": {
                "implicit_argument": f"This episode treats this as true: {(key_claims[:1] or [thesis])[0]}",
                "stronger_position": f"But the stronger position is this: {thesis}",
            },
        },
        "what_working": highlights[:3],
        "what_missing": weaknesses[:3],
        "upgrade_plan": {
            "reposition_episode": f"This episode should be about {thesis}",
            "structure_fix": {
                "opening_hook": "State the argument immediately.",
                "midpoint_tension": "Test the argument against the strongest opposing view.",
                "closing_takeaway": "Commit one specific listener action.",
            },
            "clip_opportunities": clips[:3],
            "recommendations": recommendations,
        },
        "audience_engagement_intelligence": {
            "listener_takeaway_gap": "The listener needs one unmistakable point and one action.",
            "behavior_change": behavior_change,
            "weekly_improvement_insight": "Ship each episode around one argument, one tension beat, and one behavior change.",
        },
        "question_upgrade": [
            "What is the strongest counterargument to your main claim?",
            "Which specific proof would validate or falsify your claim?",
            "What should the listener do differently this week?",
        ],
        "guest_content_opportunities": [
            {"who_type": "Domain practitioner", "why_they_matter": "Grounds claims in execution reality.", "what_they_unlock": "Concrete tradeoffs."},
            {"who_type": "Skeptical expert", "why_they_matter": "Introduces productive tension.", "what_they_unlock": "Shareable conflict."},
            {"who_type": "Research analyst", "why_they_matter": "Separates claims from assumptions.", "what_they_unlock": "Defensible evidence."},
        ],
        "strategic_value_for_network": {
            "what_improving_unlocks": "Higher retention, stronger clip yield, and clearer show positioning.",
            "where_it_underperforms": "Argument clarity and tension are not carrying the episode.",
        },
        "network_level_insight": [
            "Weak positioning across shows",
            "Lack of shareable moments",
            "Structural engagement issues",
            "High-upside opportunities",
        ],
        "network_rollout_line": "If we applied this across your network, we would identify which shows are underperforming, which episodes are most shareable, and where audience growth is being lost.",
        "one_line_fix": "If this episode were reframed around a clear argument and structured for tension, it would become significantly more engaging and shareable.",
        "conviction_statement": "This episode is underperforming because it avoids taking a hard position on its core debate.",
        "report_mode": mode,
        "product_positioning": "A podcast performance and growth intelligence layer",
        "title": str(snap.get("title") or ""),
        "creator": str(snap.get("creator") or ""),
        "genre": str(snap.get("genre") or ""),
    }


# --- Strict export: no “full report” shell when grounding is missing (network-grade failure card) ---

_EXPORT_PLACEHOLDER_MARKERS = (
    "primary tension (edit to fit)",
    "verify against the excerpt below",
    "pick one argumentative through-line from the tape",
)


def strict_export_enabled() -> bool:
    """When True (default), strategist markdown is withheld if gates fail (see workflow export helpers)."""
    v = (os.getenv("SOAPBOXX_STRICT_EXPORT") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def evidence_row_is_export_grounded(row: Any) -> bool:
    """True if an evidence_map row looks like real claim+quote, not offline scaffold or placeholders."""
    if not isinstance(row, dict):
        return False
    c = str(row.get("claim") or "").strip()
    ev = str(row.get("evidence") or "").strip()
    if len(c) < 12 or len(ev) < 20:
        return False
    low = c.lower()
    for p in _EXPORT_PLACEHOLDER_MARKERS:
        if p in low:
            return False
    if _is_broken_evidence_claim_line(c) or _is_broken_evidence_quote_line(ev):
        return False
    return True


def evidence_mapping_row_is_export_grounded(row: Any) -> bool:
    """Same bar as workflow ``evidence_map`` rows, for ``report_v3.evidence_mapping`` dicts."""
    return evidence_row_is_export_grounded(row)


def bundle_grounded_evidence_counts(
    bundle: Dict[str, Any],
) -> Tuple[int, int, int]:
    """
    Grounded evidence rows: ``(max(workflow, r3), n_workflow, n_report_v3)``.
    Shared by the truth gate and structural tier (compression under uncertainty).
    """
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    n_wf = sum(1 for e in (wf.get("evidence_map") or []) if evidence_row_is_export_grounded(e))
    n_r3 = sum(
        1
        for e in (r3.get("evidence_mapping") or [])
        if evidence_mapping_row_is_export_grounded(e)
    )
    return (max(n_wf, n_r3), n_wf, n_r3)


def export_compression_enabled() -> bool:
    """When True (default), omit optional packaging sections when signal density is borderline."""
    v = (os.getenv("SOAPBOXX_EXPORT_COMPRESSION") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def export_structural_tier(bundle: Dict[str, Any]) -> str:
    """
    ``full`` — emit full strategist sections (upgrade, guests, network, etc.).

    ``compressed`` — after core spine (through *What's Missing*), omit inflated packaging sections,
    then add :func:`compressed_action_bullets` (max three imperative lines from existing signal only),
    then optional 1-Line Fix. No fake upgrade/guest/network blocks.

    Tier uses ``report_v3.signal_mode``, transcript word count, and grounded evidence counts.
    """
    if not export_compression_enabled():
        return "full"
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    sm = str(r3.get("signal_mode") or "").upper().strip()
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    try:
        wc = int(metrics.get("transcript_word_count") or 0)
    except (TypeError, ValueError):
        wc = 0
    n_ev, _, _ = bundle_grounded_evidence_counts(bundle)

    if sm == "LOW_SIGNAL":
        return "compressed"
    if n_ev <= 2:
        return "compressed"
    if wc > 0 and wc < 400:
        return "compressed"
    if sm == "MEDIUM_SIGNAL" and (wc < 600 or n_ev < 3):
        return "compressed"
    return "full"


def _clip_action_text(s: str, max_chars: int) -> str:
    t = (s or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def _action_texts_too_similar(a: str, b: str, *, threshold: float = 0.78) -> bool:
    """Block two bullets that restate the same move (e.g. thesis vs near-duplicate claim)."""
    x = (a or "").strip().lower()
    y = (b or "").strip().lower()
    if not x or not y:
        return False
    if x in y or y in x:
        return len(min(x, y, key=len)) >= 24
    return SequenceMatcher(None, x, y).ratio() >= threshold


_COMPRESSED_ACTION_FALLBACK = (
    "No actionable steps could be derived from the available signal. "
    "Record a clearer primary claim and at least one supporting example in the next episode."
)


def _action_coarse_intent_bucket(text: str) -> str:
    """
    Bucket rendered bullet text so near-duplicate *actions* (different wording) collapse.
    """
    low = (text or "").lower()
    if any(
        k in low
        for k in (
            "rebuild the open",
            "thesis in one beat",
            "listener gets this thesis",
        )
    ):
        return "thesis_open"
    if any(
        k in low
        for k in (
            "do not ship clip",
            "cut around the tape",
            "trace to this anchor",
            "clearly carries this claim",
        )
    ):
        return "claim_clip"
    if any(k in low for k in ("pressures this tension", "exchange that pressures")):
        return "tension"
    if "fix this before publish" in low:
        return "must_change"
    # Fallback: normalized stem (avoids splitting synonymous bullets poorly)
    stem = re.sub(r"[^a-z0-9]+", " ", low)[:56].strip()
    return stem or "misc"


def _dedupe_action_bullets_by_intent(bullets: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for b in bullets:
        if not (b or "").strip():
            continue
        bucket = _action_coarse_intent_bucket(b)
        if bucket in seen:
            continue
        seen.add(bucket)
        out.append(b.strip())
    return out[:3]


def compressed_action_bullets(bundle: Dict[str, Any], sr: Dict[str, Any]) -> List[str]:
    """
    Up to **three** imperative lines for compressed exports only.

    Uses **only** strings already present in ``sr`` and ``bundle["report_v3"]``. One bullet per
    *source lane* where possible: thesis → primary claim line → ``must_change`` or tension, with
    similarity checks so lanes do not restate the same move. If nothing can be built, returns a
    single honest **fallback** line (still no LLM inference).

    Near-duplicate bullets are dropped using coarse intent buckets (not just string prefixes).
    """
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    thesis = str(core.get("thesis") or "").strip()
    if not thesis:
        thesis = str((r3.get("coach_report") or {}).get("episode_thesis") or "").strip()
    if not thesis:
        thesis = str((r3.get("episode_snapshot") or {}).get("primary_topic") or "").strip()

    kc = [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()][:2]
    tp = sr.get("tension_position") if isinstance(sr.get("tension_position"), dict) else {}
    ia = str(tp.get("implicit_argument") or "").strip()
    sp = str(tp.get("stronger_position") or "").strip()
    tension_line = sp or ia

    anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
    em = [e for e in (r3.get("evidence_mapping") or []) if isinstance(e, dict)]

    claim_line = ""
    if kc:
        claim_line = kc[0]
    elif em:
        claim_line = str(em[0].get("claim") or "").strip()
    elif anchors:
        claim_line = str(anchors[0].get("claim") or "").strip()

    bl = (r3.get("coach_report") or {}).get("bottom_line") if isinstance(r3.get("coach_report"), dict) else {}
    must_change = str(bl.get("must_change") or "").strip() if isinstance(bl, dict) else ""

    ordered: List[str] = []

    if thesis:
        ordered.append(
            f"Rebuild the open so the listener gets this thesis in one beat: {_clip_action_text(thesis, 180)}"
        )

    if claim_line and not _action_texts_too_similar(claim_line, thesis):
        ordered.append(
            f"Do not ship clip packaging until one cut clearly carries this claim: {_clip_action_text(claim_line, 160)}"
        )

    third: Optional[str] = None
    if must_change and not _action_texts_too_similar(must_change, thesis) and not _action_texts_too_similar(
        must_change, claim_line
    ):
        third = f"Fix this before publish: {_clip_action_text(must_change, 200)}"
    elif tension_line and not _action_texts_too_similar(tension_line, thesis) and not _action_texts_too_similar(
        tension_line, claim_line
    ):
        third = f"Keep or add one exchange that pressures this tension: {_clip_action_text(tension_line, 160)}"

    if third:
        ordered.append(third)

    out = _dedupe_action_bullets_by_intent([x for x in ordered if x])
    if not out:
        return [_COMPRESSED_ACTION_FALLBACK]
    return out[:3]


def strategist_truth_gate_bundle(bundle: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Single epistemic gate for strategist markdown **and** :func:`_derive_strategist_report_from_bundle`.

    When :func:`strict_export_enabled`, a full strategist export (scores, packaging, derived shell)
    is allowed only if:

    - ``workflow_report.metadata.v3_reality_check`` did not record a failure (when present).
    - At least **two** grounded evidence rows across workflow + v3 (``max`` of both layers).
    - At least **one** segment across workflow + v3 (``max`` of both layers).

    Using ``max`` avoids dual-reality: if either layer has real structure, we do not invent a
    contradictory shell from the other empty layer.

    **Blueprint:** ``blueprint_v1.strategist_report`` does **not** bypass this gate. The blueprint
    supplies structure only after the same evidence / segment / reality checks pass — otherwise
    a bad model payload cannot be treated as canonical over thin transcript signal.
    """
    if not strict_export_enabled():
        return False, []
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    md = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    reasons: List[str] = []

    rc = md.get("v3_reality_check")
    if isinstance(rc, dict) and rc.get("passed") is False:
        fails = rc.get("failures") or []
        if isinstance(fails, list) and fails:
            reasons.extend(str(x) for x in fails if str(x).strip())
        else:
            reasons.append("v3 reality check did not pass (no failure strings recorded).")

    n_ev, n_wf, n_r3 = bundle_grounded_evidence_counts(bundle)

    n_seg = max(
        len(wf.get("segments") or []),
        len(r3.get("segments") or []),
    )

    if n_ev < 2:
        reasons.append(
            f"grounded evidence rows {n_ev} < 2 (workflow={n_wf}, report_v3={n_r3})"
        )
    if n_seg < 1:
        reasons.append(f"segments {n_seg} < 1 (workflow and report_v3)")

    return (len(reasons) > 0, reasons)


def workflow_export_should_abort_insufficient(
    workflow_report: Dict[str, Any],
    report_v3: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Deprecated: use :func:`strategist_truth_gate_bundle` with
    ``{"workflow_report": ..., "report_v3": ...}`` (metadata lives under ``workflow_report``).
    """
    wf = dict(workflow_report or {})
    md = metadata or {}
    if md:
        wf["metadata"] = md
    return strategist_truth_gate_bundle({"workflow_report": wf, "report_v3": report_v3 or {}})


def _humanize_export_blocker(raw: str) -> str:
    """Turn internal blocker strings into short, user-facing explanations."""
    s = str(raw).strip()
    if not s:
        return s
    low = s.lower()
    if "grounded evidence rows" in low and "< 2" in s:
        return (
            "Not enough on-tape evidence rows to anchor claims and clips "
            "(need at least two grounded quotes)."
        )
    if "segments" in low and "< 1" in s:
        return "No clear segment or chapter structure detected (need at least one segment)."
    if "ollama transport" in low or "transport exhausted" in low:
        return (
            "Local enrichment transport hit limits; some structure may be missing even when "
            "the tape has more in it."
        )
    if "reality check" in low or ("v3 reality" in low and "fail" in low):
        return "Consistency / reality checks did not pass for this run."
    if "output_mode" in low and "diagnostic" in low:
        return "The pipeline ran in diagnostic mode, which is not shippable as a full brief."
    return s


def _resolve_limited_reason_label(
    bundle: Dict[str, Any],
    blockers: List[str],
    wmeta: Dict[str, Any],
    export_status: str,
    transcript_word_count: int,
    readiness_band: str,
) -> str:
    """Prefer finalized ``limited_reason``; otherwise match :func:`evaluation_pipeline.compute_limited_reason`."""
    lr0 = str(wmeta.get("limited_reason") or "").strip().lower()
    if lr0 in ("content", "input", "system"):
        return lr0
    try:
        from evaluation_pipeline import compute_input_quality_score, compute_limited_reason
    except ImportError:
        return "content"

    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    n_ev, _, _ = bundle_grounded_evidence_counts({"workflow_report": wf, "report_v3": r3})
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    cc = int(metrics.get("claim_count") or 0)
    if cc <= 0:
        cl = r3.get("claims")
        if isinstance(cl, list):
            cc = len([x for x in cl if isinstance(x, dict)])
    iqs = compute_input_quality_score(int(transcript_word_count), cc, int(n_ev))

    eb = wmeta.get("export_blockers")
    if not isinstance(eb, list) or not eb:
        eb = list(blockers or [])
    bbs = wmeta.get("export_blockers_by_source")
    if not isinstance(bbs, dict):
        bbs = {}
    snap = {
        "transcript_word_count": int(transcript_word_count),
        "readiness_band": str(readiness_band or "").strip().lower(),
        "claim_count": cc,
        "canonical_evidence_count": int(n_ev),
    }
    out = compute_limited_reason(
        user_export_mode="limited",
        export_status=str(export_status or ""),
        snapshot=snap,
        export_blockers=[str(x) for x in eb if str(x).strip()],
        blockers_by_source=bbs,
        input_quality_score=iqs,
    )
    return str(out or "content")


def render_limited_signal_export_markdown(
    bundle: Dict[str, Any], blockers: List[str]
) -> str:
    """
    **Limited Signal** user-facing export: directional guidance + confidence, not silence.

    Internal diagnostics stay in ``export_blockers``; this layer interprets them as actionable signal.
    """
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    snap = dict(r3.get("episode_snapshot") or {})
    m = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    title = str(snap.get("title") or "").strip() or str(m.get("title") or "").strip() or "—"
    creator = str(snap.get("creator") or "").strip() or str(m.get("creator") or "").strip()
    genre = str(snap.get("genre") or "").strip()
    primary_topic = str(snap.get("primary_topic") or "").strip()
    cr = r3.get("coach_report") if isinstance(r3.get("coach_report"), dict) else {}
    thesis = str(cr.get("episode_thesis") or "").strip()
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    word_count = int(metrics.get("transcript_word_count") or 0)
    readiness_band = str(rr.get("band") or "").strip().lower()
    signal_mode = str(metrics.get("signal_mode") or r3.get("signal_mode") or "").strip()

    raw_blockers = [str(x).strip() for x in (blockers or []) if str(x).strip()]
    bp = bundle.get("blueprint_v1")
    if isinstance(bp, dict) and isinstance(bp.get("strategist_report"), dict) and bp.get("strategist_report"):
        raw_blockers = list(raw_blockers) + [
            "Master Blueprint strategist output was withheld: it does not bypass "
            "transcript/workflow truth checks.",
        ]
    if not raw_blockers:
        raw_blockers = [
            "Minimum evidence and/or segment bars were not met, or checks did not pass.",
        ]

    human = [_humanize_export_blocker(b) for b in raw_blockers]
    # De-dupe while preserving order
    seen: set = set()
    human_unique: List[str] = []
    for h in human:
        if h and h not in seen:
            seen.add(h)
            human_unique.append(h)

    export_status = str(wmeta.get("export_status") or "").strip().lower()
    limited_reason = _resolve_limited_reason_label(
        bundle, raw_blockers, wmeta, export_status, word_count, readiness_band
    )
    verdict_line = {
        "content": "## Episode verdict: **C — Weak episode (limited read)**",
        "input": "## Episode verdict: **C — Unreadable input (low confidence)**",
        "system": "## Episode verdict: **C — System limited (retry recommended)**",
    }.get(limited_reason, "## Episode verdict: **C — Weak episode (limited read)**")

    whats_going_on: List[str] = [
        "This episode did not provide enough **structured signal** for a full breakdown "
        "(low evidence, weak segmentation, and/or transcript quality limits what can be verified).",
        "",
        "**Translation:** the content lacks a clear analyzable spine on the tape, or the transcript "
        "is too weak to extract it reliably.",
    ]
    if export_status == "degraded":
        whats_going_on = [
            "Enrichment or transport hit limits (for example local model timeouts). "
            "You may still have usable audio—what’s missing is **reliably extracted structure**.",
            "",
            "**Translation:** treat this as a partial read until you re-run with stable enrichment "
            "or a cleaner transcript.",
        ]

    pattern_issues = [
        "**No clear structure** — ideas drift instead of building in stages.",
        "**Low specificity** — abstract talk without concrete claims or scenes.",
        "**Weak segmentation** — few “moments” to anchor clips or chapter-style insights.",
    ]
    # Tie pattern list to humanized blockers when obvious
    if any("evidence" in x.lower() for x in human_unique):
        pattern_issues[0] = pattern_issues[0] + " *(reinforced by thin evidence rows.)*"
    if any("segment" in x.lower() for x in human_unique):
        pattern_issues[2] = pattern_issues[2] + " *(reinforced by missing segments.)*"

    fix_next = [
        "**Force a clear episode thesis early** — “This episode is about X; we’ll show it through Y.”",
        "**Break the conversation into segments** — chapters, not one long ramble.",
        "**Add concrete examples** — stories beat philosophy-only blocks for clips and growth.",
    ]

    growth_lines = [
        "Episodes like this (ambient, philosophical, or passive-listening formats) often:",
        "",
        "- perform well for **passive listening / retention**",
        "- perform poorly for **clips and growth** unless you add stakes and scenes",
        "",
        "**Decide:** is this a **growth episode** or a **retention episode**? Right now it reads "
        "as neither optimized.",
    ]
    g_low = genre.lower()
    if any(x in g_low for x in ("sleep", "ambient", "meditation", "asmr")):
        growth_lines = [
            "This genre often optimizes for **calm or sleep**, not for **clip-friendly tension**.",
            "",
            "**Decide:** if growth matters, add one sharp, concrete beat; if not, own the format and "
            "measure retention instead of clip velocity.",
        ]

    why_limited: List[str] = [
        "Deeper scoring and clip picks would be guesswork without grounded evidence and segments.",
        "",
        "*This remains honest: there are **no synthetic scores** or faux-authoritative packaging here.*",
        "",
        "**Why this is limited** (plain language): the run had **insufficient signal** for a "
        "full network-grade strategist export — same bar as before, better coaching.",
    ]
    detail_bits: List[str] = []
    if word_count:
        detail_bits.append(f"Transcript words (when counted): ~{word_count}")
    if signal_mode:
        detail_bits.append(f"Signal mode: {signal_mode}")
    if primary_topic and "insufficient" not in primary_topic.lower():
        detail_bits.append(f"Primary topic (best effort): {primary_topic}")
    elif thesis:
        detail_bits.append(f"Working thesis (best effort): {thesis}")
    if detail_bits:
        why_limited.insert(0, "")
        why_limited.insert(0, " · ".join(detail_bits))

    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
        verdict_line,
        "",
        f"**Show / episode:** {creator + ' · ' if creator else ''}{title}",
        "",
        "### What's going on",
    ]
    lines.extend(whats_going_on)
    lines.extend(
        [
            "",
            "### Likely issues (from pattern + this run)",
            "",
        ]
    )
    for i, p in enumerate(pattern_issues[:3], start=1):
        lines.append(f"{i}. {p}")
    lines.append("")
    lines.append("**From this run specifically:**")
    for h in human_unique[:6]:
        lines.append(f"- {h}")
    lines.extend(
        [
            "",
            "### What to fix next episode",
            "",
        ]
    )
    for f in fix_next:
        lines.append(f"- {f}")
    lines.extend(
        [
            "",
            "### Growth insight",
            "",
        ]
    )
    lines.extend(growth_lines)
    lines.extend(["", "### Why this is limited", ""])
    lines.extend(why_limited)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Technical details for support / QA:* "
        + "; ".join(str(x) for x in raw_blockers[:8])
    )
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_insufficient_signal_export_markdown(
    bundle: Dict[str, Any], blockers: List[str]
) -> str:
    """Backward-compatible name for :func:`render_limited_signal_export_markdown`."""
    return render_limited_signal_export_markdown(bundle, blockers)


def _render_strategist_export_markdown(bundle: Dict[str, Any]) -> str:
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3b = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    if wmeta.get("export_status") in ("insufficient_signal", "degraded"):
        blockers = wmeta.get("export_blockers") or []
        if not isinstance(blockers, list):
            blockers = [str(blockers)]
        return render_insufficient_signal_export_markdown(bundle, [str(x) for x in blockers if str(x).strip()])
    # Authoritative path: if a unified evaluator already finalized export_status, do not run
    # a second independent truth gate here.
    if wmeta.get("export_status") == "ok":
        abort = False
        reasons: List[str] = []
    else:
        abort, reasons = strategist_truth_gate_bundle(bundle)
    if abort:
        return render_insufficient_signal_export_markdown(bundle, reasons)

    sr = _derive_strategist_report_from_bundle(bundle)
    bp = bundle.get("blueprint_v1") if isinstance(bundle.get("blueprint_v1"), dict) else {}
    title = str(sr.get("title") or (((bundle.get("report_v3") or {}).get("episode_snapshot") or {}).get("title") or "")).strip()
    creator = str(sr.get("creator") or (((bundle.get("report_v3") or {}).get("episode_snapshot") or {}).get("creator") or "")).strip()
    genre = str(sr.get("genre") or (((bundle.get("report_v3") or {}).get("episode_snapshot") or {}).get("genre") or "")).strip()
    snap = sr.get("snapshot") if isinstance(sr.get("snapshot"), dict) else {}
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    evidence_anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
    tension_position = core.get("tension_position") if isinstance(core.get("tension_position"), dict) else {}
    up = sr.get("upgrade_plan") if isinstance(sr.get("upgrade_plan"), dict) else {}
    sf = up.get("structure_fix") if isinstance(up.get("structure_fix"), dict) else {}
    sv = sr.get("strategic_value_for_network") if isinstance(sr.get("strategic_value_for_network"), dict) else {}
    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
    ]
    try:
        from .episode_progress import format_progress_markdown_lines
    except ImportError:
        from episode_progress import format_progress_markdown_lines

    lines.extend(format_progress_markdown_lines(bundle))
    lines.extend(
        [
        "## Podcast performance & growth intelligence",
        "",
        f"**Title:** {title or '—'}",
        f"**Show / creator:** {creator or '—'}",
        f"**Genre:** {genre or '—'}",
        f"**Positioning:** {str(bp.get('product_positioning') or sr.get('product_positioning') or 'A podcast performance and growth intelligence layer').strip()}",
        "",
        "## Podcast Performance Insight",
        f"> {str(sr.get('punchline_header') or '').strip() or 'Strong topic, but the episode circles the same point without committing to one argument.'}",
        "",
        "## Snapshot",
        f"- Score: {snap.get('overall_score', '—')} / 10",
        f"- Signal: {str(snap.get('signal_strength') or '—').strip()}",
        f"- Diagnosis: {str(snap.get('diagnosis') or '').strip()}",
        f"- Core problem: {str(sr.get('core_problem') or snap.get('diagnosis') or '').strip()}",
        "",
        "## Core Breakdown",
        f"**Thesis (fixed):** {str(core.get('thesis') or '').strip()}",
        "",
        "**Claims:**",
        ]
    )
    for c in [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()][:3]:
        lines.append(f"- {c}")
    if evidence_anchors:
        lines.extend(["", "## Evidence Anchors"])
        for row in evidence_anchors[:3]:
            cl = str(row.get("claim") or "").strip()
            an = str(row.get("anchor") or "").strip()
            if cl and an:
                lines.append(f"- {cl} -> {an}")
    implicit_argument = str(tension_position.get("implicit_argument") or "").strip()
    stronger_position = str(tension_position.get("stronger_position") or "").strip()
    if implicit_argument or stronger_position:
        lines.extend(["", "## Tension Call"])
        if implicit_argument:
            lines.append(f"- {implicit_argument}")
        if stronger_position:
            lines.append(f"- {stronger_position}")
    lines.extend(["", "## What's Working"])
    for w in [str(x).strip() for x in (sr.get("what_working") or []) if str(x).strip()][:3]:
        lines.append(f"- {w}")
    lines.extend(["", "## What's Missing"])
    for m in [str(x).strip() for x in (sr.get("what_missing") or []) if str(x).strip()][:3]:
        lines.append(f"- {m}")

    tier = export_structural_tier(bundle)
    if tier == "compressed":
        lines.extend(
            [
                "",
                "*Packaging sections omitted (upgrade plan, guest slots, network framing): transcript length or signal density is below the bar for actionable distribution advice. Do not treat omitted blocks as hidden recommendations.*",
            ]
        )
        act = compressed_action_bullets(bundle, sr)
        if act:
            lines.extend(["", "## If You Had to Act Anyway"])
            for b in act:
                lines.append(f"- {b}")
        one_line_fix_c = str(sr.get("one_line_fix") or "").strip()
        if one_line_fix_c:
            lines.extend(["", "## 1-Line Fix", one_line_fix_c])
        return "\n".join(lines).strip() + "\n"

    lines.extend(["", "## Upgrade Plan"])
    repo = str(up.get("reposition_episode") or "").strip()
    if repo:
        lines.append(f"**Reposition:** {repo}")
    lines.append("")
    lines.append("**Structure:**")
    for k, label in (("opening_hook", "Hook"), ("midpoint_tension", "Tension"), ("closing_takeaway", "Takeaway")):
        v = str(sf.get(k) or "").strip()
        if v:
            lines.append(f"- {label}: {v}")
    for r in [str(x).strip() for x in (up.get("recommendations") or []) if str(x).strip()][:3]:
        lines.append(f"- Recommendation: {r}")
    lines.append("")
    lines.append("**Clips:**")
    for c in [str(x).strip() for x in (up.get("clip_opportunities") or []) if str(x).strip()][:3]:
        lines.append(f"- {c}")
    lines.extend(["", "## Questions That Should Have Been Asked"])
    for q in [str(x).strip() for x in (sr.get("question_upgrade") or []) if str(x).strip()][:3]:
        lines.append(f"- {q}")
    lines.extend(["", "## Guest Opportunities"])
    for g in [x for x in (sr.get("guest_content_opportunities") or []) if isinstance(x, dict)][:3]:
        who = str(g.get("who_type") or "").strip()
        why = str(g.get("why_they_matter") or "").strip()
        unlock = str(g.get("what_they_unlock") or "").strip()
        if who:
            lines.append(f"- {who} -> {why} {unlock}".strip())
    lines.extend(["", "## Strategic Value"])
    wu = str(sv.get("what_improving_unlocks") or "").strip()
    upf = str(sv.get("where_it_underperforms") or "").strip()
    if wu:
        lines.append(f"- {wu}")
    if upf:
        lines.append(f"- {upf}")
    lines.extend(["", "## Network Insight"])
    for x in [str(x).strip() for x in (sr.get("network_level_insight") or []) if str(x).strip()][:4]:
        lines.append(f"- {x}")
    rollout = str(sr.get("network_rollout_line") or "").strip()
    if rollout:
        lines.extend(["", f"> {rollout}"])
    one_line_fix = str(sr.get("one_line_fix") or "").strip()
    conviction = str(sr.get("conviction_statement") or "").strip()
    if conviction:
        lines.extend(["", "## Conviction", conviction])
    if one_line_fix:
        lines.extend(["", "## 1-Line Fix", one_line_fix])
    return "\n".join(lines).strip() + "\n"


def render_unified_episode_export_markdown(bundle: Dict[str, Any]) -> str:
    """
    One markdown string for sharing: strategist-first export via :func:`_render_strategist_export_markdown`.

    When ``SOAPBOXX_EXPORT_COMPRESSION`` is on (default), borderline signal yields a **shorter**
    markdown: spine through *What's Missing*, honesty note, :func:`compressed_action_bullets`, then
    optional 1-Line Fix. See :func:`export_structural_tier`.

    When ``bundle`` includes ``blueprint_v1`` (from Master Blueprint v1 via ``FeedbackEngine``), the
    strategist payload is still subject to the truth gate and compression tier.
    """
    # Final export is strategist-only by design; legacy diagnostic/readiness sections are excluded.
    return _render_strategist_export_markdown(bundle)
    r3 = bundle.get("report_v3") or {}
    wf = bundle.get("workflow_report") or {}
    snap = dict(r3.get("episode_snapshot") or {})
    claims = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]
    _sanitize_episode_snapshot(snap, claims)

    title = str(snap.get("title") or "").strip()
    creator = str(snap.get("creator") or "").strip()
    genre = str(snap.get("genre") or "").strip()
    gen = _utc_now_iso()
    m = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    if isinstance(m.get("generated_at"), str):
        gen = m["generated_at"]

    rr_pre = r3.get("report_readiness") or {}
    sig_badge = _episode_signal_badge(rr_pre if isinstance(rr_pre, dict) else {}, r3)
    om_u = str((rr_pre or {}).get("output_mode") or r3.get("output_mode") or "full").strip().lower()

    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
        _export_header_tagline(),
        "",
        f"**Title:** {title}",
        f"**Show / creator:** {creator or '—'}",
        f"**Genre:** {genre or '—'}",
        f"**Generated:** {gen}",
        f"**Report signal:** {sig_badge}",
        _signal_badge_caption(sig_badge, om_u),
        "",
    ]
    pi_u = _personalized_coach_intro(creator, genre, title)
    if pi_u:
        lines.append(pi_u)
        lines.append("")
    pt = str(snap.get("primary_topic") or "").strip()
    cr_u = r3.get("coach_report") or {}
    wt_u = str(cr_u.get("episode_thesis") or "").strip()
    if pt and not _is_meta_topic_line(pt):
        lines.append(f"**Primary topic:** {pt}")
        lines.append("")
    elif wt_u:
        lines.append(f"**Working thesis:** {wt_u}")
        lines.append("")

    rr = rr_pre if isinstance(rr_pre, dict) else {}
    band = str(rr.get("band") or "").strip()
    rnotes = [str(x).strip() for x in (rr.get("notes") or []) if str(x).strip()]
    ract = [str(x).strip() for x in (rr.get("suggested_actions") or []) if str(x).strip()]
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    if band or rnotes or ract:
        lines.append("## Readiness & expectations")
        if band:
            lines.append(f"**Band:** {band}")
        if metrics:
            lines.append(
                f"*Words: {metrics.get('transcript_word_count')} · Claims: {metrics.get('claim_count')} "
                f"· Evidence rows: {metrics.get('evidence_row_count')} · Signal: {metrics.get('signal_mode', '')}*"
            )
        if rnotes:
            for n in rnotes:
                lines.append(f"- {n}")
        if ract:
            lines.append("")
            lines.append("**Next steps:**")
            for a in ract:
                lines.append(f"- {a}")
        lines.append("")

    if om_u == "diagnostic":
        lines.append("## Diagnostic output")
        lines.append(
            "**Review-first mode:** prioritize verification and editing before clips, titles, or growth packaging."
        )
        _rrd = rr_pre if isinstance(rr_pre, dict) else {}
        for dr in (_rrd.get("diagnostic_reasons") or r3.get("diagnostic_reasons") or []):
            lines.append(f"- {dr}")
        lines.append("")

    spine_u = build_episode_spine(r3, wf)
    lines.extend(format_episode_spine_markdown_lines(spine_u))
    lines.append("")

    bp_lines = _format_master_blueprint_v1_section(bundle)
    if bp_lines:
        lines.extend(bp_lines)
        lines.append("")

    # --- 1. Key Highlights
    hl_rows: List[str] = []
    for h in (wf.get("highlights") or [])[:8]:
        if isinstance(h, dict):
            ins = str(h.get("insight") or "").strip()
            if (
                ins
                and not _is_meta_topic_line(ins)
                and not _is_narrative_meta_noise(ins)
                and not is_low_signal_insight_line(ins)
                and not _is_garbled_insight_line(ins)
            ):
                hl_rows.append(ins)
    if not hl_rows:
        for x in (r3.get("clean_insights") or [])[:8]:
            s = str(x).strip()
            if (
                s
                and not _is_meta_topic_line(s)
                and not _is_narrative_meta_noise(s)
                and not is_low_signal_insight_line(s)
                and not _is_garbled_insight_line(s)
            ):
                hl_rows.append(s)
    lines.append("## 1. Key Highlights")
    if hl_rows:
        for h in hl_rows:
            lines.append(f"- {h}")
    else:
        lines.append(
            "- *(No highlights passed quality filters — rerun with a richer transcript or check Ollama / `warnings`.)*"
        )
    lines.append("")

    # --- 2. Key beats & pull quotes (same schema as legacy "evidence_map")
    lines.append("## 2. Key beats & pull quotes")
    em_wf = wf.get("evidence_map") or []
    ev_count = 0
    seen_ev_keys: Set[str] = set()
    if em_wf:
        for e in em_wf[:20]:
            if not isinstance(e, dict):
                continue
            cid = str(e.get("id") or "")
            ts = e.get("timestamp")
            ts_s = f"{float(ts):.1f}s" if ts is not None else "n/a"
            typ = str(e.get("type") or "other")
            cl = str(e.get("claim") or "").strip()
            ev = _dedupe_repeated_sentences(str(e.get("evidence") or "").strip())
            if _is_broken_evidence_claim_line(cl):
                continue
            if _is_broken_evidence_quote_line(ev):
                continue
            ek = _normalized_evidence_claim_key(cl)
            if ek and ek in seen_ev_keys:
                continue
            if ek:
                seen_ev_keys.add(ek)
            label = "Quote" if typ.lower() == "pull_quote" else "Evidence"
            moment = "Moment" if typ.lower() == "pull_quote" else "Claim"
            lines.append(
                f"- **[{cid}]** {ts_s} | {typ} | **{moment}:** {cl} | **{label}:** {ev}"
            )
            ev_count += 1
            if ev_count >= 12:
                break
    else:
        for row in (r3.get("evidence_mapping") or [])[:20]:
            if not isinstance(row, dict):
                continue
            cl = str(row.get("claim") or "").strip()
            if _is_broken_evidence_claim_line(cl):
                continue
            ev_r = _dedupe_repeated_sentences(str(row.get("evidence") or "").strip())
            if _is_broken_evidence_quote_line(ev_r):
                continue
            ek = _normalized_evidence_claim_key(cl)
            if ek and ek in seen_ev_keys:
                continue
            if ek:
                seen_ev_keys.add(ek)
            ts = row.get("timestamp")
            ts_s = f"{float(ts):.1f}s" if ts is not None else "n/a"
            lines.append(
                f"- **[{row.get('id')}]** {ts_s} | {row.get('type')} | "
                f"**Claim:** {row.get('claim')} | **Evidence:** {ev_r}"
            )
            ev_count += 1
            if ev_count >= 12:
                break
    if ev_count == 0:
        lines.append(
            "- *(No evidence rows — see coach report appendix in `markdown_v3`.)*"
        )
    lines.append("")

    # --- 3. Follow-Up Questions
    lines.append("## 3. Follow-Up Questions")
    fu = wf.get("follow_up_questions") or []
    if fu:
        for q in fu[:12]:
            if not isinstance(q, dict):
                continue
            qt = str(q.get("question") or "").strip()
            cid = str(q.get("claim_id") or "")
            if qt:
                lines.append(f"- **[{cid}]** {qt}")
    else:
        eng = r3.get("engagement_questions") or {}
        for cid in sorted(
            eng.keys(),
            key=lambda x: int(x[1:]) if str(x)[1:].isdigit() else 0,
        ):
            tri = eng.get(cid) or {}
            for label, key in (
                ("Counter", "counterpunch"),
                ("Validation", "validation"),
                ("Application", "application"),
            ):
                t = str(tri.get(key) or "").strip()
                if t:
                    lines.append(f"- **[{cid}]** ({label}) {t}")
    lines.append("")

    # --- 4. Guest / Research Recommendations
    lines.append("## 4. Guest / Research Recommendations")
    gr = _workflow_body_guest_rows(wf)
    if gr:
        use_rich = bool(
            gr
            and isinstance(gr[0], dict)
            and gr[0].get("guest_archetype")
            and (gr[0].get("what_it_fixes") or gr[0].get("topic_angle"))
        )
        if use_rich:
            lines.append(
                "**Guest strategy — what to bring on next** *(tied to this episode’s weaknesses, not a name list)*"
            )
            lines.append("")
            first = gr[0] if gr and isinstance(gr[0], dict) else {}
            commit = str(first.get("commitment_line") or "").strip()
            if commit:
                lines.append(commit)
                lines.append("")
            n = 0
            for g in gr[:8]:
                if not isinstance(g, dict):
                    continue
                n += 1
                nm = str(g.get("name") or "Guest archetype").strip()
                why = str(g.get("angle") or "").strip()
                look = str(g.get("topic_angle") or "").strip()
                fix = str(g.get("what_it_fixes") or "").strip()
                seq = str(g.get("sequence_label") or "").strip()
                head = f"### {seq}: {nm}" if seq else f"### {n}. {nm}"
                lines.append(head)
                lines.append("")
                if why:
                    lines.append(f"- **Why:** {why}")
                if look:
                    lines.append(f"- **Look for:** {look}")
                if fix:
                    lines.append(f"- **What it fixes:** {fix}")
                nem = str(g.get("next_episode_move") or "").strip()
                if nem and str(g.get("guest_sequence") or "") == "primary":
                    lines.append(f"- **Next episode move:** {nem}")
                lines.append("")
        else:
            lines.append("| Suggested Guest | Title | Topic / Angle | Claim | Relevance |")
            lines.append("| --- | --- | --- | --- | --- |")
            for g in gr[:8]:
                if not isinstance(g, dict):
                    continue
                lines.append(
                    f"| {g.get('name', '')} | {g.get('title') or g.get('role', '')} | "
                    f"{g.get('topic_angle') or g.get('angle', '')} | {g.get('claim_id', '')} | "
                    f"{g.get('relevance', '')} |"
                )
    else:
        lines.append(
            "- *(See coach report guest strategy in `markdown_v3`, or enable workflow AI enrichment.)*"
        )
    lines.append("")

    # --- 5. Segment Planning
    lines.append("## 5. Segment Planning")
    segs = wf.get("segments") or []
    if segs:
        for s in segs[:5]:
            if not isinstance(s, dict):
                continue
            lines.append(f"- **{s.get('title') or s.get('segment_id')}** — {s.get('goal', '')}")
    else:
        for s in (r3.get("segments") or [])[:5]:
            if isinstance(s, dict):
                lines.append(f"- {s.get('segment_title', '')} — {s.get('goal', '')}")
    lines.append("")

    # --- 6. Analytics / Narrative Tracking
    lines.append("## 6. Analytics / Narrative Tracking")
    an = wf.get("analytics") or {}
    aa = r3.get("analytics_actionable") or {}
    story = list(an.get("storylines") or aa.get("what_worked") or [])[:6]
    topics = list(an.get("topic_signals") or aa.get("what_failed") or [])[:8]
    steps = list(an.get("actionable_steps") or aa.get("next_move") or [])[:6]
    if story:
        lines.append("**Recurring / supporting themes:**")
        for x in story:
            lines.append(f"- {x}")
    if topics:
        lines.append("**Topic signals:** " + ", ".join(str(t) for t in topics))
    if steps:
        lines.append("**Next moves:**")
        for x in steps:
            lines.append(f"- {x}")
    if not story and not topics and not steps:
        lines.append("- *(No analytics block — see `markdown_v3` coach diagnosis.)*")
    lines.append("")

    lines.append("## 7. Episode Comparison Graph (Optional)")
    lines.append("")
    lines.append(
        f"---\n*SoapBoxx Episode Intelligence — unified export — workflow v{REPORT_V3_VERSION}*"
    )
    return "\n".join(lines)


def generate_episode_report_v3(
    transcript: str,
    metadata: Optional[Dict[str, str]] = None,
    *,
    client: Any = None,
    use_new_api: bool = True,
    api_key: Optional[str] = None,
    strict_references: bool = True,
    include_v2_markdown: bool = True,
    atomic_ground_truth: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Full v3 pipeline: base brief (v2 generator) + v3 enrichment + markdown.

    Applies :func:`transcript_for_v3_pipeline` before the brief pass (normalization is **on** by
    default; set ``SOAPBOXX_TRANSCRIPT_NORMALIZE=0`` to disable).

    ``atomic_ground_truth`` is forwarded to :func:`build_v3_report` (see module docstring).
    """
    meta = dict(metadata or {})
    transcript = transcript_for_v3_pipeline(transcript or "")
    base = generate_episode_brief(
        transcript,
        meta,
        client=client,
        use_new_api=use_new_api,
        api_key=api_key,
    )
    brief = base.get("brief") or {}
    report = build_v3_report(
        brief, transcript or "", metadata=meta, atomic_ground_truth=atomic_ground_truth
    )
    warnings = list(base.get("warnings") or [])

    if strict_references:
        validate_v3_report_or_raise(report)

    md_v3 = render_episode_report_v3_markdown(report)
    out: Dict[str, Any] = {
        "report_v3": report,
        "markdown_v3": md_v3,
        "brief": brief,
        "warnings": warnings,
        "model": base.get("model"),
        "workflow_version": REPORT_V3_VERSION,
    }
    if include_v2_markdown:
        out["markdown"] = base.get("markdown") or render_markdown(brief, meta.get("generated_at"))
    out["meta"] = {
        "generated_at": meta.get("generated_at"),
        "title": meta.get("title"),
        "creator": meta.get("creator"),
        "genre": meta.get("genre"),
    }
    out["episode_spine"] = build_episode_spine(report, None)
    try:
        from .episode_progress import (
            attach_export_telemetry_to_metadata,
            persist_episode_progress_after_export,
            prepare_bundle_for_export,
        )
    except ImportError:
        from episode_progress import (  # type: ignore
            attach_export_telemetry_to_metadata,
            persist_episode_progress_after_export,
            prepare_bundle_for_export,
        )

    prepare_bundle_for_export(out)
    attach_export_telemetry_to_metadata(out.get("meta") or {}, out)
    out["markdown_export"] = render_unified_episode_export_markdown(out)
    persist_episode_progress_after_export(out)
    return out


__all__ = [
    "REPORT_V3_VERSION",
    "SEMANTIC_DUP_THRESHOLD",
    "clean_key_highlights",
    "text_similarity",
    "remove_semantic_duplicates",
    "generate_engagement_questions",
    "map_guest_to_claim",
    "build_evidence_mapping",
    "build_executable_segments",
    "detect_signal_mode",
    "build_actionable_analytics",
    "build_coach_report",
    "validate_references",
    "build_v3_report",
    "apply_identity_consistency_to_report_v3",
    "apply_claim_quality_gate",
    "apply_semantic_grounding_validator",
    "apply_system_health_label",
    "validate_v3_invariants",
    "render_episode_report_v3_markdown",
    "render_unified_episode_export_markdown",
    "build_episode_spine",
    "format_episode_spine_markdown_lines",
    "generate_episode_report_v3",
    "validate_v3_report_or_raise",
    "compute_report_readiness",
    "merge_workflow_followups_into_engagement",
    "is_low_signal_insight_line",
    "classify_output_mode",
    "strict_export_enabled",
    "strategist_truth_gate_bundle",
    "render_limited_signal_export_markdown",
    "workflow_export_should_abort_insufficient",
    "bundle_grounded_evidence_counts",
    "export_structural_tier",
    "export_compression_enabled",
    "compressed_action_bullets",
]
