# backend/episode_intelligence.py
"""
Network-facing episode brief: structured JSON + tight markdown (compact **v2** layout).
Designed for podcasters and networks — actionable, not recap filler.

**Primary product workflow is v3** (coach Episode Report + workflow JSON). See
``episode_report_v3.generate_episode_report_v3`` and ``docs/network_episode_brief_v3.md``.
This module still generates the **v2 brief JSON** used as the base layer inside v3 and for
legacy one-page ``markdown`` export.

**LLM inference (Ollama only):** set ``SOAPBOXX_OLLAMA_MODEL`` (and optional ``OLLAMA_HOST``)
so ``generate_episode_brief`` calls a local Ollama server. All brief/claim responses use a strict
JSON envelope ``{"text": str, "data": object}`` (see ``LLM_ENVELOPE_SYSTEM_SUFFIX`` and
``coerce_ollama_message_to_envelope``). By default, if ``data.episode_snapshot`` is missing or invalid,
the parser also tries a v2-shaped JSON object in ``text`` (set ``SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0``
to disable). ``SOAPBOXX_LLM_STRICT_USEFULNESS=1`` to
reject very short ``text`` when ``data`` is empty; ``SOAPBOXX_LLM_MIN_TEXT_CHARS`` (default 10) with
strict mode. Set ``SOAPBOXX_LLM_VALIDATE_BRIEF_SCHEMA=1`` to run lightweight v2 brief semantics checks
(see ``llm_data_contracts.validate_brief_v2_semantics``). For long transcripts, set
``SOAPBOXX_BRIEF_MAX_CHARS`` to match your model context (single full transcript pass before
chunked fallback). Optional ``SOAPBOXX_OLLAMA_NUM_CTX`` / ``OLLAMA_NUM_CTX`` and ``SOAPBOXX_OLLAMA_TOP_P``
are forwarded to Ollama ``options``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from json_repair import loads as _json_repair_loads
except ImportError:  # pragma: no cover - optional until pip install
    _json_repair_loads = None  # type: ignore

try:
    from tenacity import retry, stop_after_attempt, wait_exponential
except ImportError:  # pragma: no cover - local fallback when dependency missing
    def retry(*_args: Any, **_kwargs: Any):  # type: ignore
        def _decorator(fn: Any) -> Any:
            return fn

        return _decorator

    def stop_after_attempt(_n: int) -> Any:  # type: ignore
        return None

    def wait_exponential(**_kwargs: Any) -> Any:  # type: ignore
        return None


_LOG = logging.getLogger(__name__)


def llm_env_truthy(key: str) -> bool:
    """True if ``key`` is set to ``1`` / ``true`` / ``yes`` / ``on`` (shared LLM envelope flags)."""
    return os.getenv(key, "").strip().lower() in ("1", "true", "yes", "on")


def _llm_envelope_text_fallback_enabled() -> bool:
    """Whether to parse v2 brief JSON from envelope ``text`` when ``data`` is incomplete.

    Default **on** (local models often put the brief only in ``text``). Set
    ``SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0`` / ``false`` / ``off`` to require strict ``data``.
    """
    raw = os.getenv("SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def _warn_raw_envelope_violations(raw_str: str) -> None:
    """Log likely prompt-contract drift before ``json.loads`` (fences, prose prefix)."""
    if "```" in raw_str:
        _LOG.warning(
            "LLM envelope: markdown fence in message.content (expected raw JSON only)"
        )
    s = raw_str.strip()
    if s and not s.startswith("{"):
        _LOG.warning(
            "LLM envelope: content does not start with '{' after strip (possible prose prefix)"
        )


def _dict_looks_like_structured_task_payload(d: Any) -> bool:
    """True if ``d`` plausibly holds brief/workflow rows (not arbitrary metadata)."""
    if not isinstance(d, dict) or not d:
        return False
    markers = frozenset(
        {
            "episode_snapshot",
            "highlights",
            "evidence_map",
            "follow_up_questions",
            "claims",
            "narrative",
            "evidence_gaps",
            "production_moves",
            "guests",
            "action_plan_7d",
            "segments",
            "analytics",
            "snapshot",
            "brief",
        }
    )
    if markers & d.keys():
        return True
    # Some models use ``snapshot`` instead of ``episode_snapshot`` (lifted elsewhere too).
    if isinstance(d.get("snapshot"), dict):
        return True
    return False


def _maybe_parse_json_object_string(val: Any) -> Any:
    """Some models put a JSON object inside a string field; parse once if it looks like an object."""
    if not isinstance(val, str):
        return val
    s = val.strip()
    if len(s) < 2 or s[0] != "{":
        return val
    try:
        j = json.loads(s)
    except (json.JSONDecodeError, TypeError, ValueError):
        return val
    return j if isinstance(j, dict) else val


def _unwrap_wrapped_payload(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """If the model nested the payload one level under a common key, return the inner dict."""
    for wrap in (
        "response",
        "output",
        "result",
        "message",
        "brief",
        "payload",
        "answer",
        "content",
        "envelope",
        "body",
        "assistant",
    ):
        inner = parsed.get(wrap)
        if not isinstance(inner, dict):
            continue
        if _dict_looks_like_structured_task_payload(inner):
            return inner
        # Nested envelope: {"response": {"data": {v2 brief}}}
        nested = inner.get("data")
        if isinstance(nested, dict) and (
            _dict_looks_like_structured_task_payload(nested)
            or isinstance(nested.get("episode_snapshot"), dict)
        ):
            return nested
        # Another common pattern: wrapper holds only stringified JSON in "content"
        if wrap == "content" and not _dict_looks_like_structured_task_payload(inner):
            c = inner.get("content") or inner.get("text")
            if isinstance(c, str) and c.strip().startswith("{"):
                jd = _maybe_parse_json_object_string(c)
                if isinstance(jd, dict) and _dict_looks_like_structured_task_payload(jd):
                    return jd
    if len(parsed) == 1:
        only = next(iter(parsed.values()))
        if isinstance(only, dict):
            if _dict_looks_like_structured_task_payload(only):
                return only
            nd = only.get("data")
            if isinstance(nd, dict) and (
                _dict_looks_like_structured_task_payload(nd)
                or isinstance(nd.get("episode_snapshot"), dict)
            ):
                return nd
    return None


def _normalize_envelope_key_aliases(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Map ``Text``/``Data`` and similar to ``text``/``data`` before strict contract checks."""
    out = dict(parsed)
    if "text" not in out:
        for alt in ("Text", "TEXT", "_text"):
            if alt in out:
                tv = out.pop(alt)
                out["text"] = tv if isinstance(tv, str) else ("" if tv is None else str(tv))
                break
    if "data" not in out and "Data" in out:
        out["data"] = out.pop("Data")
    return out


def _lift_snapshot_to_episode_snapshot(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """If only ``snapshot`` is present, mirror to ``episode_snapshot`` for marker detection."""
    out = dict(parsed)
    if "episode_snapshot" not in out and isinstance(out.get("snapshot"), dict):
        out["episode_snapshot"] = out["snapshot"]
    return out


def _peel_single_key_structured_shell(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Unwrap a single-key shell (e.g. result/output) until ``text``, ``data``, or a task-shaped root."""
    cur: Dict[str, Any] = parsed
    for _ in range(6):
        if "text" in cur:
            return cur
        if _dict_looks_like_structured_task_payload(cur) and "text" not in cur:
            return cur
        if len(cur) != 1:
            return cur
        inner = next(iter(cur.values()))
        if not isinstance(inner, dict):
            return cur
        if (
            "text" in inner
            or "data" in inner
            or _dict_looks_like_structured_task_payload(inner)
        ):
            cur = _normalize_envelope_key_aliases(inner)
            cur = _lift_snapshot_to_episode_snapshot(cur)
            continue
        return cur
    return cur


def _validate_envelope_usefulness(text: str, data: Dict[str, Any]) -> None:
    """
    Reject vacuous envelopes: **both** ``text`` (stripped) and ``data`` empty.

    ``text`` is optional UX metadata; ``data`` is the structural payload (may be empty only if
    ``text`` carries content). Optional stricter check when ``SOAPBOXX_LLM_STRICT_USEFULNESS=1``.
    """
    if data is None:
        raise ValueError('Invalid LLM contract: missing "data"')
    if not isinstance(data, dict):
        raise ValueError('Invalid LLM contract: "data" must be a JSON object')
    t = (text or "").strip()
    if not t and len(data) == 0:
        raise ValueError("Empty envelope: text and data are both empty")
    if llm_env_truthy("SOAPBOXX_LLM_STRICT_USEFULNESS"):
        try:
            min_chars = int(os.getenv("SOAPBOXX_LLM_MIN_TEXT_CHARS", "10"))
        except ValueError:
            min_chars = 10
        min_chars = max(0, min_chars)
        if len(t) < min_chars and len(data) == 0:
            raise ValueError(
                "Uninformative LLM output: text shorter than minimum and data is empty "
                f"(min_chars={min_chars}; disable with SOAPBOXX_LLM_STRICT_USEFULNESS=0)"
            )


# Phrases that read as generic AI filler — strip or reject lines containing them.
BANNED_SUBSTRINGS = (
    "delve into",
    "landscape",
    "it's important to note",
    "it's worth noting",
    "robust discussion",
    "unpack",
    "nuanced",
    "tapestry",
    "leverage",
    "synergy",
    "deep dive",
    "at the end of the day",
    "moving forward",
)

# Default single-pass brief size (chars) when ``SOAPBOXX_BRIEF_MAX_CHARS`` is unset.
# One full pass before chunking improves claim/thesis quality on typical podcast transcripts.
# Override with ``SOAPBOXX_BRIEF_MAX_CHARS`` if your model context is smaller.
# ~200k fits long YouTube caption dumps in one pass on common local models (override with SOAPBOXX_BRIEF_MAX_CHARS).
DEFAULT_TRANSCRIPT_SINGLE_PASS_CHARS = 200_000
# Legacy name kept for comments / docs that referenced the old 32k default.
MAX_TRANSCRIPT_SINGLE_PASS = DEFAULT_TRANSCRIPT_SINGLE_PASS_CHARS
CHUNK_SIZE = 6_000
CHUNK_OVERLAP = 400

# If set (digits only), transcripts up to this many characters use one LLM pass with the full text
# (good for local Ollama with large-context models, e.g. llama3.1:8b with SOAPBOXX_BRIEF_MAX_CHARS=200000).
# Example: SOAPBOXX_BRIEF_MAX_CHARS=128000

# Compact network-brief JSON / markdown format version (v2). Primary Episode Report is v3.
REPORT_WORKFLOW_VERSION = "2"
PRIMARY_EPISODE_REPORT_WORKFLOW_VERSION = "3"

# Embedded in every markdown export so producers see the same process the model was told to follow.
WORKFLOW_CHECKLIST_MD = """
## How this brief was built (network brief format v2 — compact)

1. **Stakes** - What the episode argues or proves to the listener (not a recap).
2. **Claims** - 3-5 items only; each tagged `fact` / `interpretation` / `belief`.
3. **Counter-angle** - One line of strongest tension or counter-example (not a takedown).
4. **Evidence** - What would verify or weaken each factual claim.
5. **Moves** - Segment, questions, clips, risk - each tied to a next action.

If a line does not change what someone does next, it does not belong in this brief.
""".strip()


LLM_ENVELOPE_SYSTEM_SUFFIX = """
---
Response contract (mandatory): reply with ONE JSON object and exactly two top-level keys: "text" and "data" only.
- "text": always a string (one-line summary or "").
- "data": always a JSON object. Put the task-specific structured payload inside "data" (see the task schema below).
No markdown. No code fences. No top-level keys other than "text" and "data".
""".strip()


BRIEF_JSON_SCHEMA_HINT = """
Follow the workflow: stakes -> claims -> counter-angle -> evidence gaps -> production moves -> guests -> 7-day actions.
Do not write episode recap filler. No generic praise.

The episode brief object below is the REQUIRED shape of the "data" field (not the root — the root is {"text": "...", "data": { ... }}).

Inside "data", use exactly this shape:
{
  "episode_snapshot": {
    "title": "string",
    "creator": "string",
    "genre": "string",
    "primary_topic": "one short phrase naming the real subject (e.g. habits, behavior change) — never meta-commentary about signal quality, missing data, or whether a narrative was detected",
    "why_it_matters": "max 2 sentences, concrete",
    "reader": "optional: who this brief is for e.g. network dev / indie host"
  },
  "narrative": ["max 3 bullets, tension + stakes"],
  "claims": [
    {
      "id": "c1",
      "text": "one sentence, attributed if clear from transcript",
      "claim_type": "fact|interpretation|belief",
      "confidence": "high|medium|low",
      "why_it_matters": "one line",
      "counter_angle": "one sentence: strongest counter-example or tension (empty string if N/A)",
      "next_action": "verify|challenge|follow_up_segment|none"
    }
  ],
  "evidence_gaps": {
    "supported": ["max 3 short bullets or empty"],
    "weak_or_unsupported": ["max 3 short bullets or empty"],
    "proof_needed": ["what doc/source/timestamp would help, max 3"]
  },
  "production_moves": {
    "segment_to_run": { "name": "string", "goal": "one line" },
    "host_questions": ["exactly 3 sharp questions"],
    "clip_candidates": ["2 moments + why they'd engage, one line each"],
    "risk_note": "legal/reputation/pushback risk in one line, or empty string"
  },
  "guests": [
    {
      "name": "string",
      "title": "string",
      "angle": "what they add",
      "maps_to_claim_id": "c1 or empty"
    }
  ],
  "action_plan_7d": [
    { "day": "Day 1", "task": "one concrete task" },
    { "day": "Day 2", "task": "..." },
    { "day": "Day 3", "task": "..." },
    { "day": "Day 4-7", "task": "one line for the block" }
  ]
}
Rules: No filler adjectives. Every claim must have next_action and counter_angle (use \"\" if not applicable). Max 5 claims.
Inside every JSON string value, escape literal double-quote characters as \\\" (broken quotes make the JSON invalid).

Claim text rules (strict):
- One sentence paraphrase of what the show argues; readable standalone.
- Never paste raw transcript dialogue, filler (\"you know\", \"man\"), or first-person host/guest lines.
- No duplicated sentences or repeated phrases in the same claim.
- maps_to_claim_id on guests must be exactly one of the claim ids you output (c1..c5), or \"\".

Grounding (non-negotiable):
- episode_snapshot.title, creator, and genre come from METADATA and name the real show — primary_topic MUST align with them (same people, show, or clearly stated subtopic of that episode).
- Do NOT label the episode with spiritual, theological, doctrinal, or religious framing unless the title or genre explicitly signals faith content (e.g. church, sermon, theology podcast).
- If the episode is pop culture, news, business, or lifestyle, primary_topic must use that vocabulary — never default to generic \"spiritual principles\" language.
"""


_RE_SPEAKER_LEAD = re.compile(
    r"^The speaker (argues|says|claims|notes|states|criticizes)\s+that\s+",
    re.I,
)
_RE_REPEATED_PHRASE = re.compile(r"(.{18,120}?)(\s*\1){1,}", re.DOTALL)
_RE_LEADING_FRAGMENT = re.compile(
    r"^(?:[\s,;:\"'”“]+|(?:and|but|so|or)\s+|,\s*the\s+second\s+thing\s+is,?\s*,?\s*)+",
    re.I,
)


def _clean_claim_text(s: str) -> str:
    """Normalize model output: strip boilerplate, collapse repeats, trim."""
    s = (s or "").strip()
    if not s:
        return s
    s = _RE_SPEAKER_LEAD.sub("", s)
    s = re.sub(r"\s+", " ", s)
    for _ in range(6):
        s2 = _RE_LEADING_FRAGMENT.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    # Collapse immediate repeated phrase (model stutter)
    prev = None
    for _ in range(4):
        s2 = _RE_REPEATED_PHRASE.sub(r"\1", s)
        if s2 == s:
            break
        prev, s = s, s2
    return s.strip()


def _claim_fingerprint(text: str) -> str:
    t = _clean_claim_text(text).lower()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:200]


def _is_garbage_claim_text(s: str) -> bool:
    """
    Drop mid-transcript snippets the model pasted as 'claims' (chunk/small-model failures).
    """
    t = _clean_claim_text(s)
    if not t:
        return True
    if _is_meta_topic_line(t):
        return True
    low = t.lower()
    if len(t) < 28:
        return True
    # Incomplete / mid-sentence tails (common in chunked extraction)
    if re.search(
        r"\b(by advising them|for years in court|because of black hat|under the guise)\b",
        low,
    ):
        return True
    if re.search(r"\bvictims\s+v\s+\w+", low):
        return True
    if t.rstrip().endswith((" to", " by", " for", " and", " or", " the")):
        return True
    # Starts like a mid-paragraph splice, not a standalone claim
    bad_open = (
        "has a bullpen",
        "has a ",
        "comes back and says",
        "jobs to remove",
        "victims v ",
        "putting food on",
        "are going to do that",
        "are not allowed to happen",
        "like he believes it",
        "hillary likes",
        "epstein files, firm",
    )
    if any(low.startswith(b) for b in bad_open):
        return True
    if low.startswith(("has ", "comes ", "victims ", "jobs ")) and len(t.split()) < 14:
        return True
    # Common ASR confetti pasted as a "claim" (pop-culture / interview pods)
    asr_confetti = (
        "if you guys have heard",
        "didn't think about it much",
        "that day but yeah",
        "on our hands and knees",
        "playmate of the year is going to be here",
    )
    if any(f in low for f in asr_confetti) and len(t.split()) < 22:
        return True
    return False


def _dedupe_renumber_claims(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        raw = str(c.get("text") or "")
        cleaned = _clean_claim_text(raw)
        if not cleaned:
            continue
        if _is_garbage_claim_text(cleaned):
            continue
        fp = _claim_fingerprint(cleaned)
        if not fp or fp in seen:
            continue
        seen.add(fp)
        c2 = dict(c)
        c2["text"] = cleaned
        out.append(c2)
        if len(out) >= 5:
            break
    for i, c in enumerate(out, start=1):
        c["id"] = f"c{i}"
    return out


def _valid_claim_ids(claims: List[Dict[str, Any]]) -> set:
    return {str(c.get("id", "")) for c in claims if c.get("id")}


_RE_CLAIM_ID = re.compile(r"^c\d+$", re.I)


def _sanitize_guest_claim_maps(
    guests: List[Dict[str, Any]], valid_ids: set
) -> None:
    if not valid_ids:
        for g in guests:
            if isinstance(g, dict):
                g["maps_to_claim_id"] = ""
        return
    first = sorted(valid_ids, key=lambda x: int(x[1:]) if x[1:].isdigit() else 0)[0]
    for g in guests:
        if not isinstance(g, dict):
            continue
        mid = str(g.get("maps_to_claim_id") or "").strip()
        if not mid or not _RE_CLAIM_ID.match(mid) or mid not in valid_ids:
            g["maps_to_claim_id"] = first


def _ref_line_for_claim(text: str, max_len: int = 220) -> str:
    """Single-line Ref for follow-ups; no mid-word truncation."""
    t = _clean_claim_text(text)
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1].rsplit(" ", 1)[0]
    if len(cut) < 40:
        cut = t[:max_len].rstrip()
    return cut.rstrip(",;:") + "…"


def _follow_up_question(claim: Dict[str, Any], index: int) -> str:
    """Deterministic question per claim so Refs stay aligned with claim text."""
    na = (claim.get("next_action") or "none").strip().lower()
    ct = (claim.get("claim_type") or "interpretation").strip().lower()
    if na == "verify":
        return "What evidence or primary source would verify or weaken this?"
    if na == "challenge":
        return "What is the strongest fair counterpoint to this?"
    if na == "follow_up_segment":
        return "What follow-up segment would pressure-test this responsibly?"
    if ct == "belief":
        return "What lived experience, evidence, or counterexample would confirm or challenge this belief?"
    if ct == "fact":
        return "How could listeners evaluate this without rumor or hearsay?"
    if ct == "interpretation":
        return "What alternative reading fits the same facts?"
    pool = (
        "What is the strongest fair counterpoint to this?",
        "What evidence would change your mind about this claim?",
        "How could listeners evaluate this without rumor or hearsay?",
    )
    return pool[index % len(pool)]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_meta_topic_line(s: str) -> bool:
    """True if the line describes missing analysis / low signal instead of episode content."""
    low = (s or "").lower().strip()
    if len(low) < 8:
        return False
    bad = (
        "no clear narrative",
        "insufficient signal",
        "unable to determine",
        "cannot determine",
        "unclear narrative",
        "not enough information",
        "brief unavailable",
        "without openai api",
        "provide transcript for full analysis",
        # Tooling / offline brief — never treat as episode thesis or highlights
        "transcript length",
        "run with api key",
        "claim mapping and production",
        "set soapboxx_ollama",
        "start ollama",
    )
    return any(b in low for b in bad)


def _is_narrative_meta_noise(s: str) -> bool:
    """Drop bullets that negate having a story, plus tooling/setup lines from offline fallback."""
    low = (s or "").lower().strip()
    if len(low) < 8:
        return False
    bad = (
        "no clear narrative",
        "insufficient signal",
        "unable to determine",
        "cannot determine",
        "unclear narrative",
        "transcript length",
        "run with api key",
        "claim mapping and production",
        "set soapboxx_ollama",
        "start ollama",
        "brief unavailable",
    )
    return any(b in low for b in bad)


def _heuristic_primary_topic(
    snap: Dict[str, Any], claims: List[Dict[str, Any]]
) -> str:
    title = str(snap.get("title") or "").strip()
    if title and len(title) > 6 and not _is_meta_topic_line(title):
        return title[:200]
    if claims:
        t = _clean_claim_text(str(claims[0].get("text") or ""))
        if len(t) > 24:
            return (t[:140] + "…") if len(t) > 140 else t
    return "Episode themes (from transcript)"


def _title_signals_gambling_or_prediction_markets(title: str) -> bool:
    low = (title or "").lower()
    return any(
        k in low
        for k in (
            "kalshi",
            "prediction market",
            "sportsbook",
            "sports book",
            "gambling",
            "betting",
            "wager",
            "casino",
            "bookmaker",
            "fantasy sport",
            "draftkings",
            "fanduel",
            "parlay",
            "normalize betting",
            "sports betting",
        )
    )


def _primary_topic_conflicts_title(snap: Dict[str, Any]) -> bool:
    """
    Detect stale/wrong LLM primary_topic (e.g. crime beat) when the title is clearly another domain.
    """
    title = str(snap.get("title") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    if not title or len(title) < 8 or not pt:
        return False
    pl = pt.lower()
    if _title_signals_gambling_or_prediction_markets(title):
        crime_news_template = (
            "criminal enterprise",
            "law enforcement",
            "police accountability",
            "ottawa police",
            "national security",
            "prosecutor",
            "classified",
        )
        if any(k in pl for k in crime_news_template):
            return True
    return False


def _sanitize_episode_snapshot(
    snap: Dict[str, Any], claims: List[Dict[str, Any]]
) -> None:
    pt = str(snap.get("primary_topic") or "").strip()
    if _is_meta_topic_line(pt) or len(pt) < 3:
        snap["primary_topic"] = _heuristic_primary_topic(snap, claims)
    elif _primary_topic_conflicts_title(snap):
        snap["primary_topic"] = _heuristic_primary_topic(snap, claims)
    wm = str(snap.get("why_it_matters") or "").strip()
    if _is_meta_topic_line(wm) or "brief unavailable" in wm.lower():
        snap["why_it_matters"] = (
            "Listeners want one concrete behavior or belief they can test this week — "
            "not a recap of topics."
        )


def _filter_narrative_bullets(
    narrative: List[Any], claims: List[Dict[str, Any]]
) -> List[str]:
    out: List[str] = []
    for b in narrative or []:
        s = str(b).strip()
        if not s or _is_narrative_meta_noise(s):
            continue
        out.append(s)
    if len(out) >= 2:
        return out[:3]
    for c in claims:
        if len(out) >= 3:
            break
        t = _clean_claim_text(str(c.get("text") or ""))
        if len(t) < 20 or _is_narrative_meta_noise(t):
            continue
        if t not in out:
            out.append(t)
    return out[:3]


def chunk_transcript(text: str, max_chars: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Tuple[int, str]]:
    """Split text into (chunk_index, chunk_text) with overlap."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [(0, text)]
    chunks: List[Tuple[int, str]] = []
    start = 0
    idx = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end]
        chunks.append((idx, chunk))
        if end >= len(text):
            break
        start = end - overlap
        idx += 1
    return chunks


def coerce_ollama_message_to_envelope(content: Any) -> Dict[str, Any]:
    """
    Normalize Ollama ``message.content`` to ``{"text": str, "data": dict}``.

    Raises ``ValueError`` if the model output cannot be coerced. Supports a
    legacy root object (e.g. brief or workflow JSON without the envelope) by
    wrapping it as ``{"text": "", "data": <root>}``.
    """
    if content is None:
        raise ValueError('Invalid LLM contract: missing message "content"')

    parsed: Any
    if isinstance(content, str):
        s = content.strip()
        if not s:
            raise ValueError("Invalid LLM contract: empty message content")
        _warn_raw_envelope_violations(content)
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            try:
                parsed = _parse_json_loose(s)
            except (json.JSONDecodeError, TypeError, ValueError) as e2:
                raise ValueError("Invalid LLM contract: content is not valid JSON") from e2
    elif isinstance(content, dict):
        parsed = content
    else:
        raise ValueError(
            f'Invalid LLM contract: message content must be str or dict, got {type(content).__name__}'
        )

    if not isinstance(parsed, dict):
        raise ValueError("Invalid LLM contract: JSON root must be an object")

    parsed = _normalize_envelope_key_aliases(parsed)
    parsed = _lift_snapshot_to_episode_snapshot(parsed)
    parsed = _peel_single_key_structured_shell(parsed)

    if "text" not in parsed:
        # Stringified JSON in ``data`` (models sometimes double-encode).
        raw_d = parsed.get("data")
        if isinstance(raw_d, str):
            jd = _maybe_parse_json_object_string(raw_d)
            if isinstance(jd, dict):
                parsed = {**parsed, "data": jd}
        # Legacy: model returned the task JSON at the root (no envelope).
        if _dict_looks_like_structured_task_payload(parsed):
            out = {"text": "", "data": parsed}
            _validate_envelope_usefulness(out["text"], out["data"])
            return out
        # JSON-mode / partial: only ``data`` at top level (authoritative payload; text omitted).
        if isinstance(parsed.get("data"), dict):
            out = {"text": "", "data": parsed["data"]}
            _validate_envelope_usefulness(out["text"], out["data"])
            return out
        # Nested: ``{"response": {...}}`` or a single-key wrapper around the brief.
        inner = _unwrap_wrapped_payload(parsed)
        if inner is not None:
            out = {"text": "", "data": inner}
            _validate_envelope_usefulness(out["text"], out["data"])
            return out
        raise ValueError(
            'Invalid LLM contract: missing "text" and no usable structured payload '
            '(expected object "data", v2 brief keys at root, or one nested wrapper level).'
        )

    text = parsed.get("text")
    if text is None:
        text = ""
    elif not isinstance(text, str):
        text = json.dumps(text, ensure_ascii=False) if isinstance(text, (dict, list)) else str(text)

    data = parsed.get("data")
    if isinstance(data, str):
        data = _maybe_parse_json_object_string(data)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if len(data) == 0:
        hoisted = {k: v for k, v in parsed.items() if k not in ("text", "data")}
        if _dict_looks_like_structured_task_payload(hoisted):
            data = hoisted

    out = {"text": text, "data": data}
    _validate_envelope_usefulness(out["text"], out["data"])
    return out


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _strip_trailing_commas_json(s: str) -> str:
    """Remove JS-style trailing commas before } or ] (common in LLM output)."""
    out = s
    for _ in range(64):
        s2 = re.sub(r",(\s*[}\]])", r"\1", out)
        if s2 == out:
            return out
        out = s2
    return out


def _extract_first_json_object(raw: str) -> str:
    """
    If the model adds prose before/after JSON, take the first top-level `{...}` object.
    Tracks string/escape state so `{`/`}` inside quoted strings do not affect depth.
    """
    s = raw.strip()
    start = s.find("{")
    if start < 0:
        return raw
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : j + 1]
    return s[start:]


def _parse_json_loose(raw: str) -> Dict[str, Any]:
    """
    Parse model JSON: strip fences, isolate first object, tolerate trailing commas.
    Falls back to ``json-repair`` (unescaped quotes in strings, minor syntax glitches).
    """
    s = _strip_json_fence(raw).strip().lstrip("\ufeff")
    if not s:
        raise json.JSONDecodeError("empty", "", 0)
    blob = _extract_first_json_object(s) if "{" in s else s
    blob_tc = _strip_trailing_commas_json(blob)

    last_err: Optional[Exception] = None
    try:
        data = json.loads(blob_tc)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        last_err = e

    if _json_repair_loads is not None:
        try:
            data = _json_repair_loads(blob)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            last_err = e

    if last_err is not None:
        raise last_err
    raise json.JSONDecodeError("could not parse brief JSON", blob, 0)


def _maybe_validate_brief_semantics(brief: Dict[str, Any]) -> None:
    if not llm_env_truthy("SOAPBOXX_LLM_VALIDATE_BRIEF_SCHEMA"):
        return
    try:
        from .llm_data_contracts import validate_brief_v2_semantics
    except ImportError:
        from llm_data_contracts import validate_brief_v2_semantics  # type: ignore
    validate_brief_v2_semantics(brief)


def _v2_brief_payload_without_snapshot(data: Dict[str, Any]) -> bool:
    """True when ``data`` looks like a v2 brief body but ``episode_snapshot`` is missing or not a dict."""
    if not isinstance(data, dict) or isinstance(data.get("episode_snapshot"), dict):
        return False
    claims = data.get("claims")
    if isinstance(claims, list) and len(claims) > 0:
        return True
    narr = data.get("narrative")
    if isinstance(narr, list) and len(narr) > 0:
        return True
    pm = data.get("production_moves")
    return isinstance(pm, dict) and bool(pm)


_SNAPSHOT_FIELD_KEYS = frozenset(
    {"title", "creator", "genre", "primary_topic", "why_it_matters", "reader"}
)


def _unwrap_nested_brief_envelope(data_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Peel accidental double envelopes: ``{"data": {"data": {brief}}}`` or inner LLM envelope
    ``{"text": "", "data": {brief}}`` sitting inside ``data``.
    """
    out = dict(data_obj)
    mid = out.get("data")
    if isinstance(mid, dict):
        inner = mid.get("data")
        if isinstance(inner, dict) and (
            isinstance(inner.get("episode_snapshot"), dict)
            or _v2_brief_payload_without_snapshot(inner)
        ):
            return inner
        # Full second envelope inside data
        if isinstance(inner, dict) and "text" in inner and isinstance(inner.get("data"), dict):
            inner2 = inner["data"]
            if isinstance(inner2.get("episode_snapshot"), dict) or _v2_brief_payload_without_snapshot(
                inner2
            ):
                return inner2
    return out


def _coerce_brief_data_shape(data_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Heal common local-model layout mistakes (aliases, flat snapshot fields, nested data)."""
    out = _unwrap_nested_brief_envelope(data_obj)

    if not isinstance(out.get("episode_snapshot"), dict):
        alt = out.get("snapshot")
        if isinstance(alt, dict):
            out = dict(out)
            out["episode_snapshot"] = alt
            out.pop("snapshot", None)

    # Single top-level "data" key whose value is the whole brief
    if (
        isinstance(out.get("data"), dict)
        and len([k for k in out if k != "data"]) == 0
    ):
        inner_only = out["data"]
        if isinstance(inner_only.get("episode_snapshot"), dict) or _v2_brief_payload_without_snapshot(
            inner_only
        ):
            return dict(inner_only)

    # Snapshot fields placed at root next to claims / narrative (no episode_snapshot object)
    if not isinstance(out.get("episode_snapshot"), dict):
        snap_keys = [k for k in out if k in _SNAPSHOT_FIELD_KEYS]
        if len(snap_keys) >= 2:
            out = dict(out)
            snap = {k: out.pop(k) for k in snap_keys}
            out["episode_snapshot"] = snap

    return out


def _text_likely_contains_json_object(t: str) -> bool:
    """
    The LLM envelope allows ``text`` to be a plain one-line summary (not JSON).
    Only run ``_parse_json_loose`` when ``text`` plausibly embeds an object.
    """
    s = (t or "").strip()
    if not s:
        return False
    if s.startswith("{") or "```" in s:
        return True
    return "{" in s


def _unwrap_parsed_text_to_brief_dict(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """If the model put a full envelope or only ``data`` in ``text``, return the v2 brief dict."""
    if not isinstance(parsed, dict):
        return {}
    inner_data = parsed.get("data")
    if isinstance(inner_data, dict) and (
        isinstance(inner_data.get("episode_snapshot"), dict)
        or _v2_brief_payload_without_snapshot(inner_data)
    ):
        return dict(inner_data)
    if isinstance(parsed.get("episode_snapshot"), dict) or _v2_brief_payload_without_snapshot(parsed):
        return dict(parsed)
    return dict(parsed)


def _maybe_parse_episode_snapshot_string_field(data_obj: Dict[str, Any]) -> None:
    """If ``episode_snapshot`` is a JSON object string, replace with the parsed dict."""
    es = data_obj.get("episode_snapshot")
    if isinstance(es, str) and es.strip():
        try:
            inner = json.loads(es)
            if isinstance(inner, dict):
                data_obj["episode_snapshot"] = inner
        except (json.JSONDecodeError, TypeError, ValueError):
            pass


def _brief_from_llm_envelope(env: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the v2 brief dict: prefer ``data.episode_snapshot``; heal common local-model drift."""
    if "text" not in env:
        raise ValueError('Invalid LLM contract: missing "text"')
    data_obj = env.get("data")
    if not isinstance(data_obj, dict):
        data_obj = {}
    else:
        data_obj = dict(data_obj)

    _maybe_parse_episode_snapshot_string_field(data_obj)
    data_obj = _coerce_brief_data_shape(data_obj)
    _maybe_parse_episode_snapshot_string_field(data_obj)

    if isinstance(data_obj.get("episode_snapshot"), dict):
        _maybe_validate_brief_semantics(data_obj)
        return data_obj

    if _v2_brief_payload_without_snapshot(data_obj):
        _LOG.warning(
            'LLM brief: "data" has v2 fields but no episode_snapshot object; '
            "downstream normalization will fill title/creator/genre from METADATA."
        )
        return data_obj

    t = env.get("text") or ""
    if not isinstance(t, str):
        t = ""
    if _llm_envelope_text_fallback_enabled() and t.strip():
        if _text_likely_contains_json_object(t):
            try:
                parsed_raw = _parse_json_loose(t)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                raise ValueError(
                    'Brief must be returned in envelope "data" with episode_snapshot, '
                    "or valid v2 JSON in \"text\" (parse failed). "
                    "Set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0 only if you require strict data-only mode."
                ) from e
            if isinstance(parsed_raw, dict):
                parsed = _unwrap_parsed_text_to_brief_dict(parsed_raw)
                pes = parsed.get("episode_snapshot")
                if isinstance(pes, str) and pes.strip():
                    try:
                        inner = json.loads(pes)
                        if isinstance(inner, dict):
                            parsed = dict(parsed)
                            parsed["episode_snapshot"] = inner
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                if isinstance(parsed.get("episode_snapshot"), dict):
                    _LOG.warning(
                        'LLM brief: using JSON from envelope "text"; prefer episode_snapshot inside "data".'
                    )
                    _maybe_validate_brief_semantics(parsed)
                    return parsed
                if _v2_brief_payload_without_snapshot(parsed):
                    _LOG.warning(
                        'LLM brief: using partial v2 JSON from envelope "text" (no episode_snapshot); '
                        "METADATA will fill snapshot fields."
                    )
                    return parsed
        raise ValueError(
            'Brief must be returned in envelope "data" with episode_snapshot, '
            'or v2-shaped JSON in "text". When "text" is a plain summary (not JSON), '
            'the full brief must appear inside "data". '
            "Set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0 to forbid parsing from \"text\"."
        )
    raise ValueError(
        'Brief must be returned in envelope "data" with episode_snapshot (or v2 fields without it), '
        'and/or valid v2 JSON in "text". '
        "Parsing from \"text\" is on by default; set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0 to require data-only."
    )


def _claims_from_llm_envelope(env: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Strict: ``data.claims`` only. Legacy: ``data.claims`` if present, else one ``_parse_json_loose(text)`` pass."""
    if "text" not in env:
        raise ValueError('Invalid LLM contract: missing "text"')
    d = env.get("data") or {}
    if not isinstance(d, dict):
        d = {}
    claims = d.get("claims")
    if isinstance(claims, list):
        return [c for c in claims if isinstance(c, dict)]
    allow_text = _llm_envelope_text_fallback_enabled()
    t = env.get("text") or ""
    if not isinstance(t, str):
        t = ""
    if allow_text:
        if not t.strip():
            return []
        _LOG.warning(
            'LLM claims: using JSON from envelope "text"; prefer {"data": {"claims": [...]}}.'
        )
        try:
            jo = _parse_json_loose(t)
            cl = jo.get("claims")
            if isinstance(cl, list):
                return [c for c in cl if isinstance(c, dict)]
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return []
    raise ValueError(
        'Claims chunk must set "data.claims", or allow parsing from "text" '
        "(default: allowed; set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0 for strict data-only)."
    )


def _has_banned_slop(text: str) -> bool:
    low = text.lower()
    return any(b in low for b in BANNED_SUBSTRINGS)


def _scrub_slop(text: str) -> str:
    if not text or not _has_banned_slop(text):
        return text
    lines = text.splitlines()
    kept = [ln for ln in lines if not _has_banned_slop(ln)]
    return "\n".join(kept) if kept else text


def _model_name() -> str:
    """LLM label for exports; runtime uses ``SOAPBOXX_OLLAMA_MODEL`` (Ollama-only)."""
    return os.getenv("SOAPBOXX_OLLAMA_MODEL", "ollama").strip() or "ollama"


def _max_transcript_single_pass_chars() -> int:
    raw = os.getenv("SOAPBOXX_BRIEF_MAX_CHARS", "").strip()
    if raw.isdigit():
        return min(max(int(raw), 1_000), 500_000)
    return DEFAULT_TRANSCRIPT_SINGLE_PASS_CHARS


def _brief_backend_label() -> str:
    o = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    return f"ollama:{o}" if o else _model_name()


def _ollama_chat(
    system: str,
    user: str,
    *,
    max_tokens: int = 4_096,
    temperature: float = 0.25,
    stage: str = "episode_intelligence.brief",
) -> Dict[str, Any]:
    """Local Ollama HTTP API — no OpenAI API key. Requires SOAPBOXX_OLLAMA_MODEL and a running server.

    Returns a strict ``{"text": str, "data": dict}`` envelope (see ``LLM_ENVELOPE_SYSTEM_SUFFIX``).
    """
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError("SOAPBOXX_OLLAMA_MODEL is not set")
    o_opts: Dict[str, Any] = {
        "num_predict": max_tokens,
        "temperature": temperature,
    }
    _ctx = os.getenv("SOAPBOXX_OLLAMA_NUM_CTX", os.getenv("OLLAMA_NUM_CTX", "")).strip()
    if _ctx:
        try:
            o_opts["num_ctx"] = int(_ctx)
        except ValueError:
            pass
    _tp = os.getenv("SOAPBOXX_OLLAMA_TOP_P", "").strip()
    if _tp:
        try:
            o_opts["top_p"] = float(_tp)
        except ValueError:
            pass
    system_full = (system.rstrip() + "\n\n" + LLM_ENVELOPE_SYSTEM_SUFFIX)
    # Ollama JSON mode improves parse success for brief/claim extraction (esp. small local models).
    payload_obj: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_full},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": o_opts,
    }
    try:
        try:
            from .ollama_chat_http import ollama_api_chat
            from .ollama_heartbeat import ollama_blocking_heartbeat
        except ImportError:
            from ollama_chat_http import ollama_api_chat  # type: ignore
            from ollama_heartbeat import ollama_blocking_heartbeat  # type: ignore

        data = ollama_api_chat(
            host,
            payload_obj,
            stage=stage,
            component="episode_intelligence",
            heartbeat_cm=ollama_blocking_heartbeat,
        )
    except Exception as e:
        try:
            from .ollama_chat_http import OllamaTransportError
        except ImportError:
            from ollama_chat_http import OllamaTransportError  # type: ignore
        if isinstance(e, OllamaTransportError):
            raise RuntimeError(str(e)) from e
        raise
    return coerce_ollama_message_to_envelope((data.get("message") or {}).get("content"))


def _openai_chat(
    client: Any,
    use_new_api: bool,
    system: str,
    user: str,
    max_tokens: int = 4_096,
    temperature: float = 0.25,
) -> Dict[str, Any]:
    """Ollama-only: ``SOAPBOXX_OLLAMA_MODEL`` must be set (see ``_ollama_chat``)."""
    if not os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip():
        raise RuntimeError(
            "SOAPBOXX_OLLAMA_MODEL is not set — LLM brief generation requires a local Ollama model."
        )
    return _ollama_chat(
        system, user, max_tokens=max_tokens, temperature=temperature
    )


def _openai_chat_with_retry(
    client: Any,
    use_new_api: bool,
    system: str,
    user: str,
    max_tokens: int = 4_096,
    temperature: float = 0.25,
) -> Dict[str, Any]:
    """Retries are handled in ``ollama_api_chat`` (bounded exponential)."""
    return _openai_chat(
        client,
        use_new_api,
        system,
        user,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def _merge_claim_chunks(claim_lists: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    n = 1
    for lst in claim_lists:
        for c in lst:
            cleaned = _clean_claim_text(str(c.get("text") or ""))
            key = _claim_fingerprint(cleaned)
            if not key or key in seen:
                continue
            seen.add(key)
            c2 = dict(c)
            c2["text"] = cleaned
            c2["id"] = f"c{n}"
            out.append(c2)
            n += 1
            if len(out) >= 5:
                return out[:5]
    return out[:5]


def _extract_claims_chunk(
    client: Any,
    use_new_api: bool,
    chunk: str,
    chunk_idx: int,
    metadata: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    sys = (
        "You extract testable claims from podcast transcript chunks. "
        "Inside the required \"data\" object, output exactly: {\"claims\": [...]}. "
        "Each claim has fields: text, claim_type, confidence, "
        "why_it_matters, counter_angle (one sentence or empty), next_action. "
        "Each text must be ONE short paraphrase sentence (no dialogue, no filler words). "
        "Max 4 claims per chunk. Skip small talk. Use \"text\": \"\" unless you add a one-line note."
    )
    md = dict(metadata or {})
    title = str(md.get("title") or "")[:120]
    genre = str(md.get("genre") or "")[:80]
    user = (
        f"EPISODE_TITLE: {title or '(unknown)'}\nGENRE: {genre or '(unknown)'}\n"
        f"CHUNK {chunk_idx}:\n{chunk}\n\nReturn JSON only."
    )
    env = _openai_chat_with_retry(
        client, use_new_api, sys, user, max_tokens=1_800, temperature=0.2
    )
    try:
        return _claims_from_llm_envelope(env)
    except ValueError as e:
        _LOG.warning("claims chunk envelope: %s", e)
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _synthesize_full_brief(
    client: Any,
    use_new_api: bool,
    transcript_sample: str,
    claims_merged: List[Dict[str, Any]],
    metadata: Dict[str, str],
) -> Dict[str, Any]:
    meta = json.dumps(metadata, ensure_ascii=False)
    claims_json = json.dumps(claims_merged, ensure_ascii=False)
    sys = (
        "You are a senior podcast producer writing a one-page brief for networks. "
        "Be direct. No hype. No recap filler. "
        + BRIEF_JSON_SCHEMA_HINT
    )
    grounding = (
        "GROUNDING: Episode identity is in METADATA (title, creator, genre). primary_topic must align with that identity. "
        "Never use spiritual/theological framing unless the metadata clearly indicates a faith or religion show.\n\n"
    )
    user = (
        grounding
        + f"METADATA (use as defaults; episode_snapshot may refine):\n{meta}\n\n"
        + f"CLAIMS (dedupe and align brief to these; max 5 in output):\n{claims_json}\n\n"
        + "TRANSCRIPT EXCERPT (for voice and nuance; do not invent facts not supported here):\n"
        + f"{transcript_sample[:12000]}\n"
    )
    env = _openai_chat_with_retry(
        client, use_new_api, sys, user, max_tokens=4_096, temperature=0.25
    )
    return _brief_from_llm_envelope(env)


def _single_pass_brief(
    client: Any,
    use_new_api: bool,
    transcript: str,
    metadata: Dict[str, str],
) -> Dict[str, Any]:
    sys = (
        "You are a senior podcast producer writing a one-page brief for networks. "
        "Be direct. No hype. No recap filler. "
        "Separate fact vs interpretation vs belief. "
        + BRIEF_JSON_SCHEMA_HINT
    )
    meta = dict(metadata or {})
    grounding = (
        "GROUNDING: Use metadata title, creator, and genre as the source of truth for what this episode is about. "
        "primary_topic must visibly overlap those fields (names, domain, format). "
        "Do not output religious/spiritual framing unless the show is explicitly faith-oriented.\n\n"
    )
    user = (
        grounding
        + f"METADATA:\n{json.dumps(meta, ensure_ascii=False)}\n\n"
        + f"TRANSCRIPT:\n{transcript}\n"
    )
    env = _openai_chat_with_retry(
        client, use_new_api, sys, user, max_tokens=4_096, temperature=0.25
    )
    return _brief_from_llm_envelope(env)


def _minimal_brief(metadata: Dict[str, str]) -> Dict[str, Any]:
    """
    Empty v2-shaped brief when no LLM output is available — no synthetic narrative or coaching text.
    Warnings on the return value explain why generation did not run.
    """
    snap = {
        "title": metadata.get("title") or "Untitled episode",
        "creator": metadata.get("creator") or "",
        "genre": metadata.get("genre") or "",
        "primary_topic": "",
        "why_it_matters": "",
    }
    return {
        "episode_snapshot": snap,
        "narrative": [],
        "claims": [],
        "evidence_gaps": {
            "supported": [],
            "weak_or_unsupported": [],
            "proof_needed": [],
        },
        "production_moves": {
            "segment_to_run": {"name": "", "goal": ""},
            "host_questions": [],
            "clip_candidates": [],
            "risk_note": "",
        },
        "guests": [],
        "action_plan_7d": [],
    }


def _normalize_brief(data: Dict[str, Any], metadata: Dict[str, str]) -> Dict[str, Any]:
    snap = data.get("episode_snapshot") or {}
    snap.setdefault("title", metadata.get("title") or "")
    snap.setdefault("creator", metadata.get("creator") or "")
    snap.setdefault("genre", metadata.get("genre") or "")
    data["episode_snapshot"] = snap
    raw_claims = [c for c in (data.get("claims") or []) if isinstance(c, dict)]
    claims = _dedupe_renumber_claims(raw_claims)
    for c in claims:
        if "counter_angle" not in c:
            c["counter_angle"] = ""
        ca = _clean_claim_text(str(c.get("counter_angle") or ""))
        c["counter_angle"] = ca
    data["claims"] = claims
    qwarn: List[str] = []
    try:
        from .episode_quality_gates import apply_brief_quality_pass
    except ImportError:
        from episode_quality_gates import apply_brief_quality_pass  # type: ignore

    qwarn = apply_brief_quality_pass(data, metadata)
    data["_quality_warnings"] = qwarn
    claims = data["claims"]
    _sanitize_episode_snapshot(snap, claims)
    data["narrative"] = _filter_narrative_bullets(data.get("narrative") or [], claims)
    try:
        from .episode_quality_gates import clamp_narrative_bullets_to_identity
    except ImportError:
        from episode_quality_gates import clamp_narrative_bullets_to_identity  # type: ignore

    narr_clamped, narr_warn = clamp_narrative_bullets_to_identity(snap, data.get("narrative") or [])
    if narr_warn:
        qw = data.get("_quality_warnings") or []
        if not isinstance(qw, list):
            qw = []
        qw.extend(narr_warn)
        data["_quality_warnings"] = qw
    data["narrative"] = narr_clamped
    valid = _valid_claim_ids(claims)
    guests = [g for g in (data.get("guests") or []) if isinstance(g, dict)]
    if not guests and claims:
        guests = [
            {
                "name": "Behavioral scientist or habit researcher",
                "title": "Academic / practitioner",
                "angle": "Stress-tests how habits form and break using evidence, not just anecdotes.",
                "maps_to_claim_id": claims[0]["id"],
            },
            {
                "name": "Accountability coach",
                "title": "Operator",
                "angle": "Maps episode themes to concrete weekly routines listeners can try.",
                "maps_to_claim_id": claims[min(1, len(claims) - 1)]["id"],
            },
        ]
    _sanitize_guest_claim_maps(guests, valid)
    data["guests"] = guests[:3]
    pm = data.get("production_moves") or {}
    hq = pm.get("host_questions") or []
    if len(hq) > 3:
        pm["host_questions"] = hq[:3]
    data["production_moves"] = pm
    return data


def render_markdown(brief: Dict[str, Any], generated_at: Optional[str] = None) -> str:
    """Turn brief JSON into a one-page style markdown document."""
    gen = generated_at or _utc_now_iso()
    snap = brief.get("episode_snapshot") or {}
    lines: List[str] = []
    lines.append("# SoapBoxx - Network Episode Brief")
    lines.append("")
    lines.append(
        f"**Primary episode workflow:** v{PRIMARY_EPISODE_REPORT_WORKFLOW_VERSION} "
        "(SoapBoxx Episode Report — see `docs/network_episode_brief_v3.md`)."
    )
    lines.append(
        f"**This export:** v{REPORT_WORKFLOW_VERSION} compact brief (one-page markdown). "
        "Optional legacy layout; v3 remains the main programming report."
    )
    lines.append(
        "**Docs:** `docs/network_episode_brief_v3.md` (primary). "
        "Alias: `docs/network_episode_brief_v2.md`."
    )
    lines.append(f"**Title:** {snap.get('title', '')}")
    lines.append(f"**Show / Creator:** {snap.get('creator', '')}")
    lines.append(f"**Genre:** {snap.get('genre', '')}")
    lines.append(f"**Generated:** {gen}")
    reader = snap.get("reader") or ""
    if reader:
        lines.append(f"**Reader:** {reader}")
    lines.append("")
    lines.append(WORKFLOW_CHECKLIST_MD)
    lines.append("")
    lines.append("## Episode snapshot")
    lines.append(f"- **Primary topic:** {snap.get('primary_topic', '')}")
    lines.append(f"- **Why it matters:** {snap.get('why_it_matters', '')}")
    lines.append("")
    lines.append("## Core narrative (max 3)")
    for b in brief.get("narrative") or []:
        lines.append(f"- {_scrub_slop(str(b))}")
    lines.append("")
    lines.append("## Claims to track")
    for c in brief.get("claims") or []:
        cid = c.get("id", "")
        lines.append(
            f"- **{cid}** ({c.get('claim_type', '')}, confidence: {c.get('confidence', '')}) - "
            f"{_scrub_slop(str(c.get('text', '')))}"
        )
        lines.append(f"  - *Why it matters:* {_scrub_slop(str(c.get('why_it_matters', '')))}")
        ca = (c.get("counter_angle") or "").strip()
        if ca:
            lines.append(f"  - *Counter-angle:* {_scrub_slop(ca)}")
        lines.append(f"  - *Next action:* {c.get('next_action', '')}")
    lines.append("")
    lines.append("## Follow-up questions (by claim)")
    lines.append(
        "Each question is tied to the claim text above; **Ref** is the same claim in short form."
    )
    clist = brief.get("claims") or []
    if not clist:
        lines.append("- *(No claims extracted; run with full transcript or API.)*")
    else:
        for i, c in enumerate(clist):
            cid = c.get("id", "")
            q = _follow_up_question(c, i)
            ref = _ref_line_for_claim(str(c.get("text") or ""))
            lines.append(f"- **[{cid}]** {q} **Ref:** {ref}")
    lines.append("")
    eg = brief.get("evidence_gaps") or {}
    lines.append("## Evidence & gaps")
    lines.append("**Stronger support**")
    for x in eg.get("supported") or []:
        lines.append(f"- {_scrub_slop(str(x))}")
    lines.append("")
    lines.append("**Weaker / needs verification**")
    for x in eg.get("weak_or_unsupported") or []:
        lines.append(f"- {_scrub_slop(str(x))}")
    lines.append("")
    lines.append("**Proof that would help**")
    for x in eg.get("proof_needed") or []:
        lines.append(f"- {_scrub_slop(str(x))}")
    lines.append("")
    pm = brief.get("production_moves") or {}
    seg = pm.get("segment_to_run") or {}
    lines.append("## Production moves")
    lines.append(f"- **Segment:** {seg.get('name', '')} - {seg.get('goal', '')}")
    lines.append("- **Host questions**")
    for q in pm.get("host_questions") or []:
        lines.append(f"  - {_scrub_slop(str(q))}")
    lines.append("- **Clip candidates**")
    for cl in pm.get("clip_candidates") or []:
        lines.append(f"  - {_scrub_slop(str(cl))}")
    rn = pm.get("risk_note") or ""
    if rn:
        lines.append(f"- **Risk:** {_scrub_slop(rn)}")
    lines.append("")
    lines.append("## Guest targets (max 3)")
    for g in brief.get("guests") or []:
        mid = g.get("maps_to_claim_id") or "-"
        lines.append(
            f"- **{g.get('name', '')}** ({g.get('title', '')}) - {_scrub_slop(str(g.get('angle', '')))} "
            f"*(maps to claim {mid})*"
        )
    lines.append("")
    lines.append("## 7-day action plan")
    for row in brief.get("action_plan_7d") or []:
        lines.append(f"- **{row.get('day', '')}:** {_scrub_slop(str(row.get('task', '')))}")
    lines.append("")
    lines.append("---")
    lines.append(
        f"*SoapBoxx Episode Intelligence — v{REPORT_WORKFLOW_VERSION} brief export; "
        f"primary workflow v{PRIMARY_EPISODE_REPORT_WORKFLOW_VERSION} — programming and sales.*"
    )
    return "\n".join(lines)


def generate_episode_brief(
    transcript: str,
    metadata: Optional[Dict[str, str]] = None,
    *,
    client: Any = None,
    use_new_api: bool = True,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Produce the **v2-format** network brief dict + one-page markdown (compact layer).

    **Primary** programming output is **v3** (`episode_report_v3.generate_episode_report_v3`),
    which uses this brief JSON internally. This function does not emit v3 markdown.

    Returns:
        {
          "brief": { ... },
          "markdown": "...",
          "warnings": [...],
          "model": str,
          "workflow_version": "2",
        }
    """
    meta = dict(metadata or {})
    if not meta.get("generated_at"):
        meta["generated_at"] = _utc_now_iso()
    warnings: List[str] = []

    t = (transcript or "").strip()
    if not t:
        nb = _normalize_brief(_minimal_brief(meta), meta)
        return {
            "brief": nb,
            "markdown": render_markdown(nb, meta.get("generated_at")),
            "warnings": ["Empty transcript"],
            "model": "brief-unavailable",
            "workflow_version": REPORT_WORKFLOW_VERSION,
        }

    offline = os.getenv("SOAPBOXX_OFFLINE", "").strip().lower() in ("1", "true", "yes")
    use_ollama = bool(os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip())
    if offline:
        warnings.append(
            "SOAPBOXX_OFFLINE is set; LLM brief generation was skipped (no v2 brief JSON)."
        )
        nb = _normalize_brief(_minimal_brief(meta), meta)
        return {
            "brief": nb,
            "markdown": render_markdown(nb, meta.get("generated_at")),
            "warnings": warnings,
            "model": "offline",
            "workflow_version": REPORT_WORKFLOW_VERSION,
        }

    if not use_ollama:
        warnings.append(
            "SOAPBOXX_OLLAMA_MODEL is not set; no LLM brief was produced. "
            "Install Ollama, pull a model, and set SOAPBOXX_OLLAMA_MODEL for v2 brief extraction."
        )
        print("[episode_intelligence] SOAPBOXX_OLLAMA_MODEL not set; returning empty brief shell.")
        nb = _normalize_brief(_minimal_brief(meta), meta)
        return {
            "brief": nb,
            "markdown": render_markdown(nb, meta.get("generated_at")),
            "warnings": warnings,
            "model": "brief-unavailable",
            "workflow_version": REPORT_WORKFLOW_VERSION,
        }

    try:
        print(
            f"[episode_intelligence] Generating brief via Ollama model={os.getenv('SOAPBOXX_OLLAMA_MODEL','') or '(unset)'} "
            f"host={os.getenv('OLLAMA_HOST','http://127.0.0.1:11434')} "
            f"timeout={os.getenv('SOAPBOXX_OLLAMA_HTTP_TIMEOUT','900')}s"
        )
        single_pass_limit = _max_transcript_single_pass_chars()
        if len(t) <= single_pass_limit:
            data = _single_pass_brief(client, use_new_api, t, meta)
        else:
            warnings.append(
                f"Long transcript ({len(t)} chars > {single_pass_limit}): "
                "chunked claim extraction + synthesis. "
                "Raise SOAPBOXX_BRIEF_MAX_CHARS for one full pass if your model context allows."
            )
            claim_lists: List[List[Dict[str, Any]]] = []
            for idx, ch in chunk_transcript(t):
                claim_lists.append(
                    _extract_claims_chunk(client, use_new_api, ch, idx, meta)
                )
            merged = _merge_claim_chunks(claim_lists)
            data = _synthesize_full_brief(client, use_new_api, t, merged, meta)
        print("[episode_intelligence] Brief generation completed.")
        data = _normalize_brief(data, meta)
        warnings.extend(data.pop("_quality_warnings", []) or [])
        md = render_markdown(data, meta.get("generated_at"))
        if _has_banned_slop(md):
            md = _scrub_slop(md)
            warnings.append("Scrubbed generic phrasing from output.")
        return {
            "brief": data,
            "markdown": md,
            "warnings": warnings,
            "model": _brief_backend_label(),
            "workflow_version": REPORT_WORKFLOW_VERSION,
        }
    except Exception as e:
        print(f"[episode_intelligence] Brief generation failed: {e}")
        warnings.append(f"Brief generation failed: {e}")
        nb = _normalize_brief(_minimal_brief(meta), meta)
        return {
            "brief": nb,
            "markdown": render_markdown(nb, meta.get("generated_at")),
            "warnings": warnings,
            "model": "brief-unavailable",
            "workflow_version": REPORT_WORKFLOW_VERSION,
        }
