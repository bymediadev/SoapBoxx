# backend/episode_intelligence.py
"""
Network-facing episode brief: structured JSON + tight markdown (compact **v2** layout).
Designed for podcasters and networks — actionable, not recap filler.

**Primary product workflow is v3** (coach Episode Report + workflow JSON). See
``episode_report_v3.generate_episode_report_v3`` and ``docs/network_episode_brief_v3.md``.
This module still generates the **v2 brief JSON** used as the base layer inside v3 and for
legacy one-page ``markdown`` export.

**LLM inference (Ollama only):** set ``SOAPBOXX_OLLAMA_MODEL`` (and optional ``OLLAMA_HOST``)
so ``generate_episode_brief`` calls a local Ollama server.

**Structured API mode (default, recommended):** ``SOAPBOXX_BRIEF_STRICT_CONTRACT`` defaults to **on**
(omit the variable or set ``1``) so the brief uses ``strict_episode_contract`` — one JSON-only
generation pass plus at most one **repair** pass (no ``text``/``data`` envelope, no prose). Input
is capped by ``SOAPBOXX_BRIEF_CONTRACT_MAX_CHARS`` (default 48000 for long captioned episodes). Output is mapped into the legacy
v2 brief for v3. Set to ``0`` to opt into legacy mode.

**Spine-first + critic + refiner (optional):** set ``SOAPBOXX_BRIEF_SPINE_FIRST=1`` while strict contract stays on
to run ``spine_first_brief`` (spine → critic → optional refiner) and map into the same v2 brief,
with ``argument_spine`` / ``argument_critic`` / ``argument_refined`` preserved. The refiner sees **only**
pass 1 + pass 2 JSON (no transcript). Disable passes with ``SOAPBOXX_BRIEF_SPINE_CRITIC=0`` or
``SOAPBOXX_BRIEF_SPINE_REFINE=0``. Refiner output is **advisory** until the promotion gate passes; claim
``text`` stays pass-1 grounded with optional ``refined_text`` when drift checks pass. ``episode_snapshot``
gains ``argument_topic`` (intelligence line) vs ``primary_topic`` (identity / UI alignment).

**Legacy envelope mode** (``SOAPBOXX_BRIEF_STRICT_CONTRACT=0`` or ``legacy``): responses use
``{"text": str, "data": object}`` (see ``LLM_ENVELOPE_SYSTEM_SUFFIX`` and
``coerce_ollama_message_to_envelope``). Parsing from ``text`` is **off** unless
``SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1``. ``SOAPBOXX_LLM_STRICT_USEFULNESS=1`` to
reject very short ``text`` when ``data`` is empty; ``SOAPBOXX_LLM_MIN_TEXT_CHARS`` (default 10) with
strict mode. Set ``SOAPBOXX_LLM_VALIDATE_BRIEF_SCHEMA=1`` to run lightweight v2 brief semantics checks
(see ``llm_data_contracts.validate_brief_v2_semantics``). For long transcripts, set
``SOAPBOXX_BRIEF_MAX_CHARS`` to match your model context (single full transcript pass before
chunked fallback). Optional ``SOAPBOXX_OLLAMA_NUM_CTX`` / ``OLLAMA_NUM_CTX`` and ``SOAPBOXX_OLLAMA_TOP_P``
are forwarded to Ollama ``options``. Brief synthesis can retry after envelope coercion failures
(``SOAPBOXX_BRIEF_ENVELOPE_RETRIES``; unset defaults to **3** extra attempts after the first).
"""

from __future__ import annotations

from collections import deque
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

    Default **off** (API-style: structure must live in ``data``). Set
    ``SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1`` / ``true`` / ``yes`` / ``on`` to allow legacy ``text`` JSON.
    """
    raw = os.getenv("SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


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
    # Local models often emit camelCase (``episodeSnapshot``); normalize before key checks.
    dk = _canon_brief_top_level_keys(dict(d))
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
    if markers & dk.keys():
        return True
    # Some models use ``snapshot`` instead of ``episode_snapshot`` (lifted elsewhere too).
    if isinstance(dk.get("snapshot"), dict):
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


def _string_may_embed_json_object(val: Any) -> bool:
    if not isinstance(val, str):
        return False
    s = val.strip()
    if not s:
        return False
    return s.startswith("{") or ("{" in s) or ("```" in s)


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
        "json",
        "JSON",
        "model_response",
        "llm_response",
        "assistant_message",
        "analysis",
        "parsed",
        "completion",
        "llm_output",
    ):
        inner = parsed.get(wrap)
        if isinstance(inner, list) and len(inner) == 1 and isinstance(inner[0], dict):
            inner = inner[0]
        if _string_may_embed_json_object(inner):
            jd = _maybe_parse_json_object_string(inner)
            if not isinstance(jd, dict):
                try:
                    jd = _parse_json_loose(inner)
                except (json.JSONDecodeError, TypeError, ValueError):
                    jd = None
            inner = jd
        if not isinstance(inner, dict):
            continue
        inner_c = _canon_brief_top_level_keys(dict(inner))
        if _dict_looks_like_structured_task_payload(inner_c):
            return inner_c
        # Nested envelope: {"response": {"data": {v2 brief}}}
        nested = inner_c.get("data")
        if isinstance(nested, dict) and (
            _dict_looks_like_structured_task_payload(nested)
            or isinstance(nested.get("episode_snapshot"), dict)
        ):
            return nested
        # Another common pattern: wrapper holds only stringified JSON in "content"
        if wrap == "content" and not _dict_looks_like_structured_task_payload(inner_c):
            c = inner_c.get("content") or inner_c.get("text")
            if _string_may_embed_json_object(c):
                jd = _maybe_parse_json_object_string(c)
                if not isinstance(jd, dict):
                    try:
                        jd = _parse_json_loose(c)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        jd = None
                if isinstance(jd, dict):
                    jd2 = _canon_brief_top_level_keys(dict(jd))
                    if _dict_looks_like_structured_task_payload(jd2):
                        return jd2
    if len(parsed) == 1:
        only = next(iter(parsed.values()))
        if _string_may_embed_json_object(only):
            jd = _maybe_parse_json_object_string(only)
            if not isinstance(jd, dict):
                try:
                    jd = _parse_json_loose(only)
                except (json.JSONDecodeError, TypeError, ValueError):
                    jd = None
            only = jd
        if isinstance(only, dict):
            only_c = _canon_brief_top_level_keys(dict(only))
            if _dict_looks_like_structured_task_payload(only_c):
                return only_c
            nd = only_c.get("data")
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


def _extract_text_like_field(parsed: Dict[str, Any]) -> str:
    """Best-effort text fallback for malformed envelopes missing top-level ``text``."""
    for k in ("content", "message", "response", "output", "result", "answer", "assistant"):
        v = parsed.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            inner = v.get("content")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


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
- "data": always a JSON object (never null, never an array — put the brief object directly here).
Put the task-specific structured payload inside "data" (see the task schema below).
Prefer snake_case keys inside "data" (episode_snapshot, claims, …). The server accepts common camelCase
aliases, but snake_case reduces parse failures on small local models.
No markdown. No code fences. No top-level keys other than "text" and "data".
""".strip()

_BRIEF_ENVELOPE_RETRY_USER_MAX = 96_000

_BRIEF_ENVELOPE_RETRY_HINT = """
---
CRITICAL (retry): Your previous reply was not valid JSON or did not match the envelope.
Reply with ONE JSON object with exactly two top-level keys: "text" and "data" only.
"text" is a short string (or ""). "data" must contain the full episode brief object.
No markdown, no code fences, no extra keys at root.
""".strip()

_BRIEF_ENVELOPE_RETRY_HINT_STRICT = """
---
RETRY (strict shape): Inside "data" use snake_case keys only: episode_snapshot, narrative, claims,
evidence_gaps, production_moves, guests, action_plan_7d. Do not put the brief at the JSON root;
the root must be exactly {"text":"...","data":{...}}.
""".strip()


BRIEF_JSON_SCHEMA_HINT = """
Follow the workflow: stakes -> claims -> counter-angle -> evidence gaps -> production moves -> guests -> 7-day actions.
Do not write episode recap filler. No generic praise.

The episode brief object below is the REQUIRED shape of the "data" field (not the root — the root is {"text": "...", "data": { ... }}).
Use **snake_case** keys exactly as shown (e.g. ``episode_snapshot``, not ``episodeSnapshot``). Do not nest the whole brief under an extra ``brief`` / ``output`` wrapper.

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
_RE_REPEATED_COUNT_STUTTER = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+out\s+of\s+\w+\b(?:\s*,?\s*\1\s+out\s+of\s+\w+\b){1,}",
    re.IGNORECASE,
)
_RE_LEADING_FRAGMENT = re.compile(
    r"^(?:[\s,;:\"'”“]+|(?:and|but|so|or)\s+|,\s*the\s+second\s+thing\s+is,?\s*,?\s*)+",
    re.I,
)


def _clean_claim_text(s: str) -> str:
    """Normalize model output: strip boilerplate, collapse repeats, trim."""
    s = (s or "").strip()
    if not s:
        return s
    try:
        from .transcript_structure_extract import strip_youtube_caption_metadata
    except ImportError:  # pragma: no cover
        from transcript_structure_extract import strip_youtube_caption_metadata  # type: ignore

    s = strip_youtube_caption_metadata(s)
    if not s:
        return s
    s = _RE_SPEAKER_LEAD.sub("", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\bcuzut\b", "cuz it", s, flags=re.I)
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
    if _RE_REPEATED_COUNT_STUTTER.search(low):
        return True
    # Common ASR confetti pasted as a "claim" (pop-culture / interview pods)
    asr_confetti = (
        "if you guys have heard",
        "didn't think about it much",
        "that day but yeah",
        "on our hands and knees",
        "playmate of the year is going to be here",
        "that's like any kids like what",
    )
    if any(f in low for f in asr_confetti) and len(t.split()) < 22:
        return True
    # Podcast cold open / warm-up — not defensible "claims" (common on long YouTube caps)
    warm = (
        "hey everybody, welcome to the podcast",
        "welcome to the podcast",
        "thanks for doing this",
        "first of all, thanks for doing this",
        "first of all, thanks for",
        "i appreciate you coming out",
        "i appreciate you coming",
        "some of the things that i wanna talk about with you",
        "how to navigate the stressful times",
    )
    low1 = re.sub(r"\s+", " ", low)
    for w in warm:
        if w in low1:
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
    if any(b in low for b in bad):
        return True
    if _is_asr_artifact_line(s):
        return True
    if _is_dangling_pronoun_line(s):
        return True
    if _is_production_chatter_line(s):
        return True
    return False


# Leading filler / hedges that should be trimmed from transcript anchors before display.
# Never used to reject a line — only to clean the visible text while keeping the claim intact.
_ANCHOR_LEADING_FILLER_TOKENS: Tuple[str, ...] = (
    "yeah", "yep", "yup", "nah", "no",
    "well", "so", "and", "but", "or",
    "like", "so like", "you know", "i mean", "i guess",
    "um", "uh", "hmm", "okay", "ok", "right",
    "actually", "honestly", "basically", "literally",
    "look", "listen", "see",
    "then", "now",
)

_RE_ANCHOR_FILLER_PREFIX = re.compile(
    r"^\s*(?:"
    + r"|".join(re.escape(t) for t in sorted(_ANCHOR_LEADING_FILLER_TOKENS, key=len, reverse=True))
    + r")\s*[,\.\-—–:]*\s+",
    re.IGNORECASE,
)

# Stutter-shaped doublings that almost never occur in grammatical English but are common in ASR:
#   - the same function word repeated consecutively ("the the", "and and")
#   - a determiner immediately followed by a possessive / another determiner
#     ("the their", "a the", "an a") — classic substitution splices
_RE_DOUBLED_FUNCTION_WORDS = re.compile(
    r"\b("
    r"the\s+the|a\s+a|an\s+an|and\s+and|of\s+of|to\s+to|is\s+is|was\s+was"
    r"|that\s+that|this\s+this|in\s+in|on\s+on|for\s+for"
    r"|the\s+(?:their|his|her|its|our|your|my)"
    r"|a\s+the|an\s+a|a\s+an"
    r")\b",
    re.IGNORECASE,
)

# Three-or-more repeated commas (",  ,  ,") or comma + single filler + comma patterns.
_RE_REPEATED_COMMA_SPLICE = re.compile(r",\s*,")


def _is_asr_artifact_line(text: str) -> bool:
    """
    True when a line is visibly corrupted by ASR — doubled articles, empty commas between tokens,
    or other signatures that show the text should not be surfaced verbatim as a highlight.

    Examples that match:
      - "The Rockefeller, , the their foundation…"  (doubled comma + "the their")
      - "It's just, , you know, a thing."            (empty comma slot)
    Does not reject legitimate appositives like "Rockefeller, the foundation,".
    """
    t = (text or "").strip()
    if not t:
        return False
    if _RE_REPEATED_COMMA_SPLICE.search(t):
        return True
    if _RE_DOUBLED_FUNCTION_WORDS.search(t):
        return True
    # Comma followed immediately by another comma with only whitespace between them, already covered.
    # Token-level sanity: three consecutive words that are all stop-word-class is almost always a splice.
    tokens = re.findall(r"[A-Za-z']+", t.lower())
    if len(tokens) >= 3:
        tiny_pron = {"the", "a", "an", "of", "to", "and", "for", "is", "was", "that", "this"}
        run = 0
        for tok in tokens:
            if tok in tiny_pron:
                run += 1
                if run >= 3:
                    return True
            else:
                run = 0
    return False


# Lines that reference a person/thing solely by pronoun with no antecedent and no noun of interest.
# These have no value as standalone highlights ("You don't see him around as much anymore.").
_RE_LEADING_PRONOUN_ONLY = re.compile(
    r"^\s*(?:you|we|they|i|he|she|it|that|this|these|those)\s+"
    r"(?:do(?:n['’]t)?|did(?:n['’]t)?|does(?:n['’]t)?|"
    r"can(?:'t|not)?|could(?:n['’]t)?|should(?:n['’]t)?|would(?:n['’]t)?|"
    r"won['’]t|will(?:n['’]t)?|ain['’]t|is|are|was|were|have|had|has)\b",
    re.IGNORECASE,
)


def _is_dangling_pronoun_line(text: str) -> bool:
    """
    True when a line opens with a pronoun reference (him/her/them/it/that) and contains no proper
    noun or topic anchor — useless as a standalone highlight because the antecedent is missing.

    Example: "You don't see him around as much anymore."
    Passes (not flagged): "You don't see the Rockefellers around as much anymore." (has proper noun).
    """
    t = (text or "").strip()
    if not t or len(t.split()) > 20:
        return False
    if not _RE_LEADING_PRONOUN_ONLY.match(t):
        return False
    # If the line contains a proper noun (capitalised non-sentence-start word) we keep it.
    words = t.split()
    for w in words[1:]:
        if w and w[0].isupper() and w.strip(",.;:\"'") not in ("I", "I'm", "I've", "I'd", "I'll"):
            return False
    # All lowercase or sentence-initial only → no antecedent → dangling.
    return True


# Production / hosting chatter (equipment, cameras, editing) that should never surface as a
# highlight in a substantive episode about another topic.
_PRODUCTION_CHATTER_MARKERS: Tuple[str, ...] = (
    "back engineering",
    "podcast equipment",
    "equipment on a podcast",
    "about 10 to 15 shows",
    "about 10-15 shows",
    "running a show",
    "our setup",
    "this microphone",
    "our cameras",
    "the mics",
    "in the studio",
    "our producer",
    "our editor",
    "cutting tape",
    "splicing audio",
)


def _is_production_chatter_line(text: str) -> bool:
    """Reject obvious backstage / production chatter that is off-thesis for almost every episode."""
    low = (text or "").lower()
    if not low:
        return False
    return any(m in low for m in _PRODUCTION_CHATTER_MARKERS)


def _trim_anchor_display_text(text: str, *, max_chars: int = 240) -> str:
    """
    Clean up a verbatim transcript anchor for display:

    - Trim leading conversational filler (``Yeah``, ``Like``, ``And``, ``So``, ``Well``, …).
    - If the text clearly starts mid-sentence (starts with a lowercase word that is not a pronoun),
      attempt to jump forward to the next capitalised word or sentence terminator.
    - Cap the displayed length at ``max_chars`` and ellipsize on a word boundary.

    This NEVER invents text; it only shortens / skips leading junk.
    """
    s = (text or "").strip()
    if not s:
        return s
    # Strip leading filler (possibly multiple hedges in a row).
    for _ in range(3):
        m = _RE_ANCHOR_FILLER_PREFIX.match(s)
        if not m:
            break
        s = s[m.end():].lstrip()
    # Leading non-letter noise (e.g. ", , I had saved up…").
    s = re.sub(r"^[\s,;:\-—–\.\?!]+", "", s)
    if not s:
        return s
    # If still mid-sentence lowercase junk, try snapping forward to the first capitalised word.
    if s[:1].islower():
        m = re.search(r"(?<=[\.\?!]\s)[A-Z]", s)
        if m:
            s = s[m.start():].strip()
    # Cap length, but cut on a word boundary and ellipsize.
    if len(s) > max_chars:
        cut = s[:max_chars].rsplit(" ", 1)[0].rstrip(",;:\"'")
        s = cut + "…"
    # Capitalise the first character if it's a letter.
    if s and s[:1].isalpha() and s[:1].islower():
        s = s[:1].upper() + s[1:]
    return s


def _heuristic_primary_topic(
    snap: Dict[str, Any], claims: List[Dict[str, Any]]
) -> str:
    """
    Pick a short topic line when the LLM ``primary_topic`` is missing, meta, or conflicts with the title.

    Preference order:
      1. First clean ``narrative`` bullet on ``snap`` (the thesis-shaped bullets the brief already produced).
      2. First clean claim ``text``.
      3. Title (last resort — titles are usually clickbait, not theses).
    """
    narrative = snap.get("narrative")
    if isinstance(narrative, list):
        for b in narrative:
            t = str(b or "").strip()
            if (
                len(t) >= 24
                and not _is_meta_topic_line(t)
                and not _is_narrative_meta_noise(t)
            ):
                return (t[:180] + "…") if len(t) > 180 else t
    if claims:
        for c in claims:
            if not isinstance(c, dict):
                continue
            t = _clean_claim_text(str(c.get("text") or ""))
            if (
                len(t) >= 24
                and not _is_meta_topic_line(t)
                and not _is_narrative_meta_noise(t)
            ):
                return (t[:180] + "…") if len(t) > 180 else t
    title = str(snap.get("title") or "").strip()
    if title and len(title) > 6 and not _is_meta_topic_line(title):
        return title[:200]
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


def _title_signals_education_or_institutions_history(title: str) -> bool:
    """Title cues for schooling, foundations, or institutional history (not crime-beat news)."""
    low = (title or "").lower()
    return any(
        k in low
        for k in (
            "rockefeller",
            "carnegie",
            "foundation",
            "school",
            "education",
            "curriculum",
            "brainwash",
            "psyop",
            "pedagogy",
            "standardized",
            "common core",
            "department of education",
        )
    )


_CRIME_NEWS_PRIMARY_TOPIC_MARKERS: Tuple[str, ...] = (
    "criminal enterprise",
    "law enforcement",
    "police accountability",
    "ottawa police",
    "national security",
    "prosecutor",
    "classified",
)


def _primary_topic_is_crime_news_template(pt: str) -> bool:
    pl = (pt or "").lower().strip()
    return any(k in pl for k in _CRIME_NEWS_PRIMARY_TOPIC_MARKERS)


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
        if _primary_topic_is_crime_news_template(pt):
            return True
    if _title_signals_education_or_institutions_history(title):
        if _primary_topic_is_crime_news_template(pt):
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


def override_primary_topic_with_storyline(
    snap: Dict[str, Any],
    storylines: Optional[List[Any]] = None,
    narrative: Optional[List[Any]] = None,
) -> None:
    """
    Post-analytics override: if ``primary_topic`` is still in a crime-template or clickbait-title
    form but we now have a clear analytics storyline (or narrative bullet) from v3, prefer that.

    This is a second pass — it runs AFTER ``_sanitize_episode_snapshot`` when analytics have been
    assembled. It only fires when:
      - ``_primary_topic_conflicts_title(snap)`` is True, OR
      - the current ``primary_topic`` equals the clickbait title verbatim.
    """
    if not isinstance(snap, dict):
        return
    title = str(snap.get("title") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    needs_override = False
    if _primary_topic_conflicts_title(snap):
        needs_override = True
    elif pt and title and pt == title:
        needs_override = True
    if not needs_override:
        return

    def _first_clean(xs: Optional[List[Any]]) -> str:
        for x in xs or []:
            t = _clean_storyline_for_primary_topic(str(x or ""))
            if (
                len(t) >= 24
                and not _is_meta_topic_line(t)
                and not _is_narrative_meta_noise(t)
            ):
                return (t[:180] + "…") if len(t) > 180 else t
        return ""

    best = _first_clean(storylines) or _first_clean(narrative)
    if best:
        snap["primary_topic"] = best


# Prefix patterns emitted by analytics storylines that are clean enough as a paragraph but read
# poorly as a one-line ``primary_topic`` or ``Core thesis``: "The core theme of this episode is …",
# "This episode is about …", "Main topic: …". We trim the prefix so the header reads like a topic
# label, not an analyst sentence stem.
_RE_STORYLINE_PREFIX = re.compile(
    r"(?i)^\s*(?:"
    r"the\s+core\s+theme\s+of\s+this\s+episode\s+is"
    r"|the\s+primary\s+storyline\s+(?:of\s+this\s+episode\s+)?is"
    r"|this\s+episode\s+is\s+(?:primarily\s+)?about"
    r"|main\s+topic\s*:"
    r"|primary\s+topic\s*:"
    r"|core\s+narrative\s*:"
    r"|storyline\s*:"
    r")\s*[:\-—]*\s*"
)


def _clean_storyline_for_primary_topic(raw: str) -> str:
    """Normalize an analytics storyline so it reads cleanly as a ``primary_topic`` label.

    - Strips analyst stems ("The core theme of this episode is …", "This episode is about …").
    - Collapses semicolon-separated keyword lists to the first one or two items so the header
      doesn't read like a tag cloud.
    - Capitalizes the first letter so the label is presentable inline.

    Non-destructive on already-clean strings (e.g. a single-sentence storyline is returned as-is).
    """
    t = (raw or "").strip()
    if not t:
        return ""
    t = _RE_STORYLINE_PREFIX.sub("", t).strip(" \t\r\n-—:")
    # Semicolon-joined keyword lists (e.g. "X; Y; Z; W") read as a tag cloud — keep first 2 items
    # so the label is concrete but still a phrase, not a full list.
    if ";" in t and t.count(";") >= 2:
        parts = [p.strip(" ,.;") for p in t.split(";") if p.strip(" ,.;")]
        if parts:
            t = "; ".join(parts[:2])
    t = t.rstrip(" .;,:")
    if t and t[0].islower():
        t = t[0].upper() + t[1:]
    return t


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


def _json_root_to_dict(parsed: Any) -> Dict[str, Any]:
    """Local models sometimes wrap the envelope in a single-element JSON array."""
    if isinstance(parsed, list):
        if len(parsed) == 1 and isinstance(parsed[0], dict):
            return dict(parsed[0])
        raise ValueError(
            "Invalid LLM contract: JSON root must be a single object "
            "(got a JSON array; use one root object only)"
        )
    if not isinstance(parsed, dict):
        raise ValueError("Invalid LLM contract: JSON root must be an object")
    return dict(parsed)


def _drop_null_data_key(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """``\"data\": null`` breaks downstream checks; treat as absent."""
    if "data" in parsed and parsed.get("data") is None:
        out = dict(parsed)
        del out["data"]
        return out
    return parsed


def _brief_payload_plausibly_coercible(d: Any) -> bool:
    """True if ``d`` looks like a v2 episode brief body (avoid grabbing unrelated nested JSON)."""
    if not isinstance(d, dict) or not d:
        return False
    dk = _canon_brief_top_level_keys(dict(d))
    es = dk.get("episode_snapshot")
    if isinstance(es, dict) and es:
        return True
    if _v2_brief_payload_without_snapshot(dk):
        return True
    cl = dk.get("claims")
    if isinstance(cl, list) and cl:
        for x in cl:
            if isinstance(x, dict) and str(x.get("text") or "").strip():
                return True
    return False


def _squash_data_array_to_object(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce ``data: [ { brief } ]`` (common JSON-schema slip) into ``data: { brief }``."""
    d = parsed.get("data")
    if not isinstance(d, list) or not d:
        return parsed
    picked: Optional[Dict[str, Any]] = None
    for item in d:
        if not isinstance(item, dict):
            continue
        ic = _canon_brief_top_level_keys(dict(item))
        if _brief_payload_plausibly_coercible(ic):
            picked = ic
            break
    if picked is None and len(d) == 1 and isinstance(d[0], dict):
        picked = _canon_brief_top_level_keys(dict(d[0]))
    if picked is None:
        return parsed
    out = dict(parsed)
    out["data"] = picked
    return out


def _find_plausible_brief_nested(root: Any, *, max_depth: int = 12, max_nodes: int = 400) -> Optional[Dict[str, Any]]:
    """
    Breadth-first search for the shallowest dict that looks like a v2 brief.

    Llama-class models sometimes wrap the contract in ``analysis`` / ``result`` trees or return
    the brief only inside a partially structured object.
    """
    q = deque([(root, 0)])
    seen: set[int] = set()
    nodes = 0
    while q and nodes < max_nodes:
        obj, depth = q.popleft()
        nodes += 1
        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)
        if depth > max_depth:
            continue
        if isinstance(obj, dict):
            dc = _canon_brief_top_level_keys(dict(obj))
            if _brief_payload_plausibly_coercible(dc):
                return dc
            for v in obj.values():
                q.append((v, depth + 1))
        elif isinstance(obj, list):
            for v in obj[:32]:
                q.append((v, depth + 1))
    return None


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

    parsed = _json_root_to_dict(parsed)
    parsed = _drop_null_data_key(parsed)
    parsed = _normalize_envelope_key_aliases(parsed)
    parsed = _lift_snapshot_to_episode_snapshot(parsed)
    parsed = _peel_single_key_structured_shell(parsed)
    parsed = _squash_data_array_to_object(parsed)

    if "text" not in parsed:
        # Stringified JSON in ``data`` (models sometimes double-encode).
        raw_d = parsed.get("data")
        if isinstance(raw_d, str):
            jd = _maybe_parse_json_object_string(raw_d)
            if not isinstance(jd, dict) and raw_d.strip():
                try:
                    jd = _parse_json_loose(raw_d)
                except (json.JSONDecodeError, TypeError, ValueError):
                    jd = None
            if isinstance(jd, dict):
                parsed = {**parsed, "data": jd}
        # ``data`` may still be a list of brief-shaped dicts after partial squash failures.
        if isinstance(parsed.get("data"), list):
            parsed = _squash_data_array_to_object(parsed)
        # Legacy: model returned the task JSON at the root (no envelope).
        if _brief_payload_plausibly_coercible(parsed):
            payload = _canon_brief_top_level_keys(dict(parsed))
            out = {"text": "", "data": payload}
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
        lifted = _try_lift_stringified_brief_single_key(parsed)
        if lifted is not None:
            out = {"text": "", "data": lifted}
            _validate_envelope_usefulness(out["text"], out["data"])
            return out
        nested_brief = _find_plausible_brief_nested(parsed)
        if nested_brief is not None:
            out = {"text": "", "data": nested_brief}
            _validate_envelope_usefulness(out["text"], out["data"])
            return out
        text_fallback = _extract_text_like_field(parsed)
        if text_fallback:
            out = {"text": text_fallback, "data": {}}
            _validate_envelope_usefulness(out["text"], out["data"])
            return out
        # Empty object {} — Ollama JSON mode can emit this on weak models; do not pack into data
        # (empty text+data fails usefulness). Make failure explicit so brief retries can run.
        if isinstance(parsed, dict) and not parsed:
            raise ValueError(
                'Invalid LLM contract: Ollama returned an empty JSON object (no "text" / "data" keys). '
                "Prefer SOAPBOXX_BRIEF_STRICT_CONTRACT=1, SOAPBOXX_BRIEF_ENVELOPE_RETRIES=2, or a larger model."
            )
        if isinstance(parsed, dict) and parsed:
            # Last-resort preserve: keep unknown structured payload for downstream brief-shape coercion.
            out = {"text": "", "data": dict(parsed)}
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
    if isinstance(pm, dict) and bool(pm):
        return True
    guests = data.get("guests")
    if isinstance(guests, list) and len(guests) > 0:
        return True
    eg = data.get("evidence_gaps")
    if isinstance(eg, dict) and any(bool(eg.get(k)) for k in ("supported", "weak_or_unsupported", "proof_needed")):
        return True
    ap = data.get("action_plan_7d")
    return isinstance(ap, list) and len(ap) > 0


_SNAPSHOT_FIELD_KEYS = frozenset(
    {"title", "creator", "genre", "primary_topic", "why_it_matters", "reader"}
)

_BRIEF_TOP_LEVEL_ALIASES: Dict[str, str] = {
    "episodeSnapshot": "episode_snapshot",
    "EpisodeSnapshot": "episode_snapshot",
    "Narrative": "narrative",
    "Claims": "claims",
    "EvidenceGaps": "evidence_gaps",
    "Evidence_Gaps": "evidence_gaps",
    "ProductionMoves": "production_moves",
    "Guests": "guests",
    "ActionPlan7d": "action_plan_7d",
}


def _canon_brief_top_level_keys(data_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Rename common camelCase / PascalCase keys so v2 detection and normalization match."""
    out = dict(data_obj)
    for bad, good in _BRIEF_TOP_LEVEL_ALIASES.items():
        if bad not in out:
            continue
        if good not in out:
            out[good] = out.pop(bad)
        else:
            out.pop(bad, None)
    return out


def _try_lift_stringified_brief_single_key(parsed: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Some local models return one wrapper key whose value is a *string* of JSON (escaped object).
    Example: ``{"result": "{\\"episodeSnapshot\\":{...}}" }``.
    """
    if len(parsed) != 1:
        return None
    k, v = next(iter(parsed.items()))
    if k in ("text", "data"):
        return None
    if not _string_may_embed_json_object(v):
        return None
    jd = _maybe_parse_json_object_string(v)
    if not isinstance(jd, dict):
        try:
            jd = _parse_json_loose(v)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
    if not isinstance(jd, dict):
        return None
    jd2 = _canon_brief_top_level_keys(dict(jd))
    if _dict_looks_like_structured_task_payload(jd2):
        return jd2
    return None


def _unwrap_episode_snapshot_if_singleton_list(data_obj: Dict[str, Any]) -> Dict[str, Any]:
    es = data_obj.get("episode_snapshot")
    if isinstance(es, list) and len(es) == 1 and isinstance(es[0], dict):
        out = dict(data_obj)
        out["episode_snapshot"] = es[0]
        return out
    return data_obj


def _lift_wrapped_v2_brief_object(data_obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    If the model wrapped the whole brief under one key (``brief``, ``output``, …), lift it.
    """
    if not isinstance(data_obj, dict):
        return data_obj
    if isinstance(data_obj.get("episode_snapshot"), dict):
        return data_obj
    if _v2_brief_payload_without_snapshot(data_obj):
        return data_obj
    for wk in (
        "brief",
        "episode_brief",
        "network_brief",
        "output",
        "result",
        "payload",
        "report",
        "content",
        "json",
    ):
        inner = data_obj.get(wk)
        if not isinstance(inner, dict):
            continue
        inner = _canon_brief_top_level_keys(dict(inner))
        if isinstance(inner.get("episode_snapshot"), dict) or _v2_brief_payload_without_snapshot(inner):
            return inner
    if len(data_obj) == 1:
        only = next(iter(data_obj.values()))
        if isinstance(only, dict):
            only = _canon_brief_top_level_keys(dict(only))
            if isinstance(only.get("episode_snapshot"), dict) or _v2_brief_payload_without_snapshot(only):
                return only
    return data_obj


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
    if not isinstance(data_obj, dict):
        return {}
    out = dict(data_obj)
    if out.get("episode_snapshot") is None and "episode_snapshot" in out:
        del out["episode_snapshot"]
    out = _canon_brief_top_level_keys(out)
    out = _unwrap_nested_brief_envelope(out)
    out = _canon_brief_top_level_keys(out)
    out = _lift_wrapped_v2_brief_object(out)
    out = _unwrap_episode_snapshot_if_singleton_list(out)
    out = _canon_brief_top_level_keys(out)

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


def _brief_from_plain_text_summary(text: str) -> Dict[str, Any]:
    """Fallback when envelope text is non-JSON but still carries a usable one-line summary."""
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    if not s:
        return {}
    # Keep this conservative: provide narrative only and let metadata-driven normalization fill snapshot.
    return {"narrative": [s[:280]]}


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

    nested = _find_plausible_brief_nested(data_obj)
    if isinstance(nested, dict):
        nested = _coerce_brief_data_shape(nested)
        if isinstance(nested.get("episode_snapshot"), dict) or _v2_brief_payload_without_snapshot(nested):
            _LOG.warning('LLM brief: recovered nested v2 brief payload from envelope "data".')
            return nested

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
                    "Set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1 to allow recovering the brief from envelope \"text\"."
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
        fallback = _brief_from_plain_text_summary(t)
        if fallback:
            _LOG.warning(
                'LLM brief: envelope "text" was plain summary (non-JSON); using narrative-only fallback.'
            )
            return fallback
        raise ValueError(
            'Brief must be returned in envelope "data" with episode_snapshot, '
            'or v2-shaped JSON in "text". When "text" is a plain summary (not JSON), '
            'the full brief must appear inside "data". '
            "Set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0 to forbid parsing from \"text\"."
        )
    raise ValueError(
        'Brief must be returned in envelope "data" with episode_snapshot (or v2 fields without it), '
        'and/or valid v2 JSON in "text". '
        "Parsing from \"text\" is off unless SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1."
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
        'Claims chunk must set "data.claims", or set SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1 '
        'to allow parsing from "text".'
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


def _brief_envelope_retries_max() -> int:
    """Extra Ollama attempts after ``coerce_ollama_message_to_envelope`` fails (brief paths only)."""
    raw = os.getenv("SOAPBOXX_BRIEF_ENVELOPE_RETRIES", "").strip()
    if raw.isdigit():
        return max(0, min(int(raw), 6))
    # Default 2 extra => 3 tries (small local models often miss the envelope on first call).
    return 2


def _log_envelope_coerce_preview(content: Any, err: Exception) -> None:
    if not (
        llm_env_truthy("SOAPBOXX_OLLAMA_DEBUG")
        or llm_env_truthy("SOAPBOXX_BRIEF_ENVELOPE_DEBUG")
    ):
        return
    try:
        s = content if isinstance(content, (str, bytes)) else repr(content)
    except Exception:  # pragma: no cover - defensive
        s = "<unprintable>"
    if isinstance(s, bytes):
        s = s.decode("utf-8", errors="replace")
    if len(s) > 1400:
        s = s[:1400] + "…"
    _LOG.warning("envelope coerce debug (%s): %s", err, s)


def _ollama_chat_invoke(
    system: str,
    user: str,
    *,
    max_tokens: int = 4_096,
    temperature: float = 0.25,
    stage: str = "episode_intelligence.brief",
    append_brief_envelope_suffix: bool = True,
) -> Any:
    """HTTP POST to Ollama /api/chat; returns raw assistant ``message.content`` (no envelope coercion)."""
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
    _seed = os.getenv("SOAPBOXX_OLLAMA_SEED", "").strip()
    if _seed:
        try:
            o_opts["seed"] = int(_seed)
        except ValueError:
            pass
    if append_brief_envelope_suffix:
        system_full = (system.rstrip() + "\n\n" + LLM_ENVELOPE_SYSTEM_SUFFIX)
    else:
        system_full = system.rstrip()
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
    return (data.get("message") or {}).get("content")


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
    raw = _ollama_chat_invoke(
        system, user, max_tokens=max_tokens, temperature=temperature, stage=stage
    )
    return coerce_ollama_message_to_envelope(raw)


def _brief_llm_envelope(
    system: str,
    user: str,
    *,
    max_tokens: int = 4_096,
    temperature: float = 0.25,
    stage: str = "episode_intelligence.brief",
) -> Dict[str, Any]:
    """Like ``_ollama_chat`` but retries when envelope coercion fails (brief synthesis only)."""
    extra = _brief_envelope_retries_max()
    attempts = 1 + extra
    sys_cur = system
    user_cur = user
    last_err: Optional[ValueError] = None
    for idx in range(attempts):
        raw = _ollama_chat_invoke(
            sys_cur, user_cur, max_tokens=max_tokens, temperature=temperature, stage=stage
        )
        try:
            return coerce_ollama_message_to_envelope(raw)
        except ValueError as e:
            last_err = e
            _log_envelope_coerce_preview(raw, e)
            if idx + 1 >= attempts:
                break
            _LOG.warning(
                "episode brief envelope coerce failed (attempt %d/%d): %s — retrying",
                idx + 1,
                attempts,
                e,
            )
            sys_cur = system.rstrip() + "\n\n" + _BRIEF_ENVELOPE_RETRY_HINT
            if idx >= 1:
                sys_cur = sys_cur.rstrip() + "\n\n" + _BRIEF_ENVELOPE_RETRY_HINT_STRICT
            if len(user_cur) > _BRIEF_ENVELOPE_RETRY_USER_MAX:
                user_cur = (
                    user_cur[:_BRIEF_ENVELOPE_RETRY_USER_MAX]
                    + "\n\n[MESSAGE TRUNCATED FOR RETRY; focus on metadata + valid JSON envelope]\n"
                )
    assert last_err is not None
    raise last_err


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
    correction_feedback: str = "",
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
    if correction_feedback.strip():
        user += (
            "\n\nVALIDATION FEEDBACK (fix all items exactly):\n"
            + correction_feedback.strip()
            + "\n\nOutput must strictly match schema with no extra commentary."
        )
    env = _brief_llm_envelope(
        sys, user, max_tokens=4_096, temperature=0.25
    )
    return _brief_from_llm_envelope(env)


def _strict_contract_input_cap_chars() -> int:
    """Default 8k chars for highest strict-contract reliability on local 8B models."""
    raw = os.getenv("SOAPBOXX_BRIEF_CONTRACT_MAX_CHARS", "").strip()
    if raw.isdigit():
        return max(2_000, min(int(raw), 120_000))
    return 8_000


def _strict_contract_brief_enabled() -> bool:
    """
    Default **on**: one JSON contract pass (+ optional repair) avoids fragile ``text``/``data`` envelopes.

    Set ``SOAPBOXX_BRIEF_STRICT_CONTRACT=0`` (or ``legacy``) to use the legacy envelope + schema hint path.
    """
    raw = os.getenv("SOAPBOXX_BRIEF_STRICT_CONTRACT", "1").strip().lower()
    if raw in ("0", "false", "no", "off", "legacy", "envelope"):
        return False
    return True


def _spine_first_brief_enabled() -> bool:
    """Two-pass spine + optional critic; only applies when strict contract mode is on."""
    raw = os.getenv("SOAPBOXX_BRIEF_SPINE_FIRST", "0").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _spine_critic_llm_enabled() -> bool:
    raw = os.getenv("SOAPBOXX_BRIEF_SPINE_CRITIC", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _spine_refiner_llm_enabled() -> bool:
    raw = os.getenv("SOAPBOXX_BRIEF_SPINE_REFINE", "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _parse_strict_model_json(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    s = _strip_json_fence(str(raw or "").strip())
    if not s:
        raise ValueError("strict contract: empty model output")
    try:
        parsed: Any = json.loads(s)
    except json.JSONDecodeError:
        parsed = _parse_json_loose(s)
    if not isinstance(parsed, dict):
        raise ValueError("strict contract: model output is not a JSON object")
    return parsed


def _generate_brief_via_strict_contract(
    client: Any,
    use_new_api: bool,
    transcript: str,
    metadata: Dict[str, str],
    correction_feedback: str = "",
) -> Dict[str, Any]:
    """
    One strict-contract generation pass. Retry orchestration lives in ``generate_episode_brief``.
    """
    try:
        from .strict_episode_contract import (
            enforce_strict_contract_envelope,
            STRICT_CONTRACT_SYSTEM_PROMPT,
            build_strict_contract_repair_system,
            build_strict_contract_repair_user,
            build_strict_contract_user_block,
            map_strict_contract_to_v2_brief,
            validate_strict_episode_contract,
        )
    except ImportError:
        from strict_episode_contract import (  # type: ignore
            enforce_strict_contract_envelope,
            STRICT_CONTRACT_SYSTEM_PROMPT,
            build_strict_contract_repair_system,
            build_strict_contract_repair_user,
            build_strict_contract_user_block,
            map_strict_contract_to_v2_brief,
            validate_strict_episode_contract,
        )
    _ = (client, use_new_api)
    usr = build_strict_contract_user_block(transcript, metadata)
    if correction_feedback.strip():
        usr = (
            usr
            + "\n\nVALIDATION FEEDBACK (fix all items exactly):\n"
            + correction_feedback.strip()
            + "\n\nOutput must strictly match schema with no extra commentary."
        )
    raw = _ollama_chat_invoke(
        STRICT_CONTRACT_SYSTEM_PROMPT,
        usr,
        max_tokens=4_096,
        temperature=0.0,
        stage="episode_intelligence.strict_contract",
        append_brief_envelope_suffix=False,
    )
    parsed = _parse_strict_model_json(raw)
    parsed = enforce_strict_contract_envelope(parsed)
    ok, err = validate_strict_episode_contract(parsed)
    if not ok:
        # Keep repair builders imported for compatibility, but fail fast here.
        _ = (build_strict_contract_repair_system, build_strict_contract_repair_user)
        raise ValueError(f"strict episode contract invalid: {err}")
    return map_strict_contract_to_v2_brief(parsed, metadata)


def _generate_brief_via_spine_first(
    client: Any,
    use_new_api: bool,
    transcript: str,
    metadata: Dict[str, str],
    correction_feedback: str = "",
) -> Dict[str, Any]:
    """
    Pass 1: spine-first JSON (thesis + rewritten claims + evidence).
    Pass 2: hostile critic JSON (optional).
    Pass 3: refiner JSON from pass 1 + pass 2 only — overlays shippable thesis/claims on the v2 brief.
    """
    try:
        from .spine_first_brief import (
            CRITIC_SYSTEM_PROMPT,
            REFINER_SYSTEM_PROMPT,
            SPINE_FIRST_SYSTEM_PROMPT,
            build_critic_user_payload,
            build_refiner_user_payload,
            build_spine_first_user_block,
            map_spine_critic_refined_to_v2_brief,
            map_spine_critic_to_v2_brief,
            validate_refiner_pass3,
            validate_spine_pass1,
        )
        from .strict_episode_contract import enforce_strict_contract_envelope
    except ImportError:  # pragma: no cover
        from spine_first_brief import (  # type: ignore
            CRITIC_SYSTEM_PROMPT,
            REFINER_SYSTEM_PROMPT,
            SPINE_FIRST_SYSTEM_PROMPT,
            build_critic_user_payload,
            build_refiner_user_payload,
            build_spine_first_user_block,
            map_spine_critic_refined_to_v2_brief,
            map_spine_critic_to_v2_brief,
            validate_refiner_pass3,
            validate_spine_pass1,
        )
        from strict_episode_contract import enforce_strict_contract_envelope  # type: ignore

    _ = (client, use_new_api)
    usr = build_spine_first_user_block(
        transcript, metadata, correction_feedback=correction_feedback
    )
    raw1 = _ollama_chat_invoke(
        SPINE_FIRST_SYSTEM_PROMPT,
        usr,
        max_tokens=4_096,
        temperature=0.15,
        stage="episode_intelligence.spine_first",
        append_brief_envelope_suffix=False,
    )
    p1 = enforce_strict_contract_envelope(_parse_strict_model_json(raw1))
    ok, err = validate_spine_pass1(p1)
    if not ok:
        raise ValueError(f"spine pass 1 invalid: {err}")

    p2: Optional[Dict[str, Any]] = None
    if _spine_critic_llm_enabled():
        try:
            raw2 = _ollama_chat_invoke(
                CRITIC_SYSTEM_PROMPT,
                build_critic_user_payload(p1),
                max_tokens=4_096,
                temperature=0.1,
                stage="episode_intelligence.spine_critic",
                append_brief_envelope_suffix=False,
            )
            p2 = enforce_strict_contract_envelope(_parse_strict_model_json(raw2))
        except Exception as exc:  # noqa: BLE001 — critic is best-effort
            _LOG.warning("spine critic pass failed or unparsable: %s", exc)
            p2 = {"data": {}, "metadata": {"error": "critic_failed", "detail": str(exc)[:500]}}

    if not _spine_refiner_llm_enabled():
        return map_spine_critic_to_v2_brief(p1, p2, metadata)

    try:
        raw3 = _ollama_chat_invoke(
            REFINER_SYSTEM_PROMPT,
            build_refiner_user_payload(p1, p2),
            max_tokens=4_096,
            temperature=0.12,
            stage="episode_intelligence.spine_refine",
            append_brief_envelope_suffix=False,
        )
        p3 = enforce_strict_contract_envelope(_parse_strict_model_json(raw3))
        ok3, err3 = validate_refiner_pass3(p3)
        if not ok3:
            _LOG.warning("spine refiner pass invalid: %s — using spine+critic merge only", err3)
            return map_spine_critic_to_v2_brief(p1, p2, metadata)
        return map_spine_critic_refined_to_v2_brief(p1, p2, p3, metadata)
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("spine refiner pass failed: %s — using spine+critic merge only", exc)
        return map_spine_critic_to_v2_brief(p1, p2, metadata)


def _single_pass_brief(
    client: Any,
    use_new_api: bool,
    transcript: str,
    metadata: Dict[str, str],
    correction_feedback: str = "",
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
    if correction_feedback.strip():
        user += (
            "\n\nVALIDATION FEEDBACK (fix all items exactly):\n"
            + correction_feedback.strip()
            + "\n\nOutput must strictly match schema with no extra commentary."
        )
    env = _brief_llm_envelope(
        sys, user, max_tokens=4_096, temperature=0.25
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
        "argument_topic": "",
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


_BRIEF_SCHEMA_MAX_RETRIES = 2


def _brief_schema_failures(brief: Dict[str, Any]) -> List[str]:
    """Strict v2 brief validator: missing keys/types/critical empties are hard failures."""
    failures: List[str] = []
    if not isinstance(brief, dict):
        return ['brief root must be object']

    required_top = (
        "episode_snapshot",
        "narrative",
        "claims",
        "evidence_gaps",
        "production_moves",
        "guests",
        "action_plan_7d",
    )
    for k in required_top:
        if k not in brief:
            failures.append(f'missing top-level field "{k}"')

    snap = brief.get("episode_snapshot")
    if not isinstance(snap, dict):
        failures.append('field "episode_snapshot" must be object')
    else:
        for k, min_len in (
            ("title", 6),
            ("creator", 2),
            ("genre", 3),
            ("primary_topic", 12),
            ("why_it_matters", 20),
        ):
            v = snap.get(k)
            if not isinstance(v, str):
                failures.append(f'episode_snapshot.{k} must be string')
            elif len(v.strip()) < min_len:
                failures.append(f'episode_snapshot.{k} too short (min {min_len} chars)')

    narrative = brief.get("narrative")
    if not isinstance(narrative, list):
        failures.append('field "narrative" must be array')
    else:
        if len(narrative) < 1:
            failures.append("narrative must contain at least 1 bullet")
        for i, row in enumerate(narrative[:5]):
            if not isinstance(row, str) or len(row.strip()) < 18:
                failures.append(f"narrative[{i}] must be non-empty string (min 18 chars)")

    claims = brief.get("claims")
    claim_ids: set[str] = set()
    if not isinstance(claims, list):
        failures.append('field "claims" must be array')
    else:
        if len(claims) < 1:
            failures.append("claims must contain at least 1 item")
        for i, c in enumerate(claims[:8]):
            if not isinstance(c, dict):
                failures.append(f"claims[{i}] must be object")
                continue
            for k in ("id", "text", "claim_type", "confidence", "why_it_matters", "counter_angle", "next_action"):
                if k not in c:
                    failures.append(f"claims[{i}].{k} is required")
            cid = c.get("id")
            if not isinstance(cid, str) or not _RE_CLAIM_ID.match(cid):
                failures.append(f"claims[{i}].id must match cN")
            else:
                claim_ids.add(cid.lower())
            txt = c.get("text")
            if not isinstance(txt, str) or len(txt.strip()) < 18:
                failures.append(f"claims[{i}].text too short (min 18 chars)")
            ctm = c.get("why_it_matters")
            if not isinstance(ctm, str) or len(ctm.strip()) < 12:
                failures.append(f"claims[{i}].why_it_matters too short (min 12 chars)")
            na = c.get("next_action")
            if not isinstance(na, str) or len(na.strip()) < 4:
                failures.append(f"claims[{i}].next_action too short (min 4 chars)")

    eg = brief.get("evidence_gaps")
    if not isinstance(eg, dict):
        failures.append('field "evidence_gaps" must be object')
    else:
        for k in ("supported", "weak_or_unsupported", "proof_needed"):
            v = eg.get(k)
            if not isinstance(v, list):
                failures.append(f"evidence_gaps.{k} must be array")

    pm = brief.get("production_moves")
    if not isinstance(pm, dict):
        failures.append('field "production_moves" must be object')
    else:
        seg = pm.get("segment_to_run")
        if not isinstance(seg, dict):
            failures.append("production_moves.segment_to_run must be object")
        else:
            nm = seg.get("name")
            gl = seg.get("goal")
            if not isinstance(nm, str) or len(nm.strip()) < 1:
                failures.append("production_moves.segment_to_run.name too short (min 1 char)")
            if not isinstance(gl, str) or len(gl.strip()) < 1:
                failures.append("production_moves.segment_to_run.goal too short (min 1 char)")
        hq = pm.get("host_questions")
        if not isinstance(hq, list):
            failures.append("production_moves.host_questions must be array")
        elif len(hq) < 1:
            failures.append("production_moves.host_questions requires at least 1 item")
        clips = pm.get("clip_candidates")
        if not isinstance(clips, list):
            failures.append("production_moves.clip_candidates must be array")
        elif len(clips) < 1:
            failures.append("production_moves.clip_candidates requires at least 1 item")
        rn = pm.get("risk_note")
        if not isinstance(rn, str):
            failures.append("production_moves.risk_note must be string")

    guests = brief.get("guests")
    if not isinstance(guests, list):
        failures.append('field "guests" must be array')
    else:
        for i, g in enumerate(guests[:5]):
            if not isinstance(g, dict):
                failures.append(f"guests[{i}] must be object")
                continue
            for k, min_len in (("name", 3), ("title", 3), ("angle", 12)):
                v = g.get(k)
                if not isinstance(v, str) or len(v.strip()) < min_len:
                    failures.append(f"guests[{i}].{k} too short (min {min_len} chars)")
            m = g.get("maps_to_claim_id")
            if not isinstance(m, str) or not _RE_CLAIM_ID.match(m):
                failures.append(f"guests[{i}].maps_to_claim_id must match cN")
            elif claim_ids and m.lower() not in claim_ids:
                failures.append(f"guests[{i}].maps_to_claim_id must reference an existing claim id")

    plan = brief.get("action_plan_7d")
    if not isinstance(plan, list):
        failures.append('field "action_plan_7d" must be array')
    else:
        if len(plan) < 3:
            failures.append("action_plan_7d must contain at least 3 items")
        for i, row in enumerate(plan[:7]):
            if not isinstance(row, dict):
                failures.append(f"action_plan_7d[{i}] must be object")
                continue
            day = row.get("day")
            task = row.get("task")
            if not isinstance(day, str) or len(day.strip()) < 2:
                failures.append(f"action_plan_7d[{i}].day too short")
            if not isinstance(task, str) or len(task.strip()) < 8:
                failures.append(f"action_plan_7d[{i}].task too short (min 8 chars)")
    return failures


def _build_schema_retry_feedback(failures: List[str]) -> str:
    lines = [f"- {f}" for f in failures[:20]]
    return (
        "Schema validation failed. Fix every item below exactly:\n"
        + "\n".join(lines)
        + "\n\nSchema reminder: include all required keys and correct types; no null critical fields; "
        "minimum section lengths must be satisfied; output JSON only."
    )


_TOPIC_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "with",
        "from",
        "that",
        "this",
        "your",
        "about",
        "what",
        "when",
        "where",
        "worse",
        "than",
        "think",
        "podcast",
        "episode",
        "show",
        "interview",
        "host",
    }
)


def _title_signal_terms(title: str) -> List[str]:
    toks = re.findall(r"[A-Za-z0-9']+", str(title or "").lower())
    out: List[str] = []
    for t in toks:
        if len(t) < 4 or t in _TOPIC_STOPWORDS or t.isdigit():
            continue
        if t not in out:
            out.append(t)
        if len(out) >= 10:
            break
    return out


def _split_transcript_sentences(transcript: str) -> List[str]:
    s = str(transcript or "").replace("\r\n", "\n").replace("\r", "\n")
    chunks = re.split(r"(?<=[.!?])\s+|\n+", s)
    out: List[str] = []
    for c in chunks:
        t = " ".join(c.split()).strip()
        if t:
            out.append(t)
    return out


def _word_uniqueness_ratio(s: str) -> float:
    toks = re.findall(r"[A-Za-z']+", str(s or "").lower())
    if not toks:
        return 0.0
    return len(set(toks)) / max(1, len(toks))


def _score_claim_candidate(line: str, topic_terms: List[str]) -> int:
    t = _clean_claim_text(line)
    if not t:
        return -999
    if _is_garbage_claim_text(t) or _is_meta_topic_line(t):
        return -999
    if _is_asr_artifact_line(t) or _is_dangling_pronoun_line(t) or _is_production_chatter_line(t):
        return -999
    words = re.findall(r"[A-Za-z']+", t)
    if len(words) < 8 or len(words) > 42:
        return -999
    if _word_uniqueness_ratio(t) < 0.52:
        return -999

    low = t.lower()
    score = 0
    overlap = sum(1 for k in topic_terms if k in low)
    score += min(6, overlap * 2)
    if re.search(r"\b(because|therefore|so that|leads to|drift|centraliz|evidence|history)\b", low):
        score += 2
    if re.search(r"\b(\d+|percent|policy|school|education|media|power|institution)\b", low):
        score += 1
    if low.startswith(("yeah", "okay", "look", "so ", "right", "i mean")):
        score -= 2
    return score


def _extract_transcript_grounded_claims(
    transcript: str,
    metadata: Dict[str, str],
    *,
    max_claims: int = 5,
) -> List[Dict[str, Any]]:
    topic_terms = _title_signal_terms(metadata.get("title") or "")
    cands: List[Tuple[int, int, str]] = []
    seen: set[str] = set()
    for idx, raw in enumerate(_split_transcript_sentences(transcript)):
        cleaned = _clean_claim_text(raw)
        fp = _claim_fingerprint(cleaned)
        if not fp or fp in seen:
            continue
        score = _score_claim_candidate(cleaned, topic_terms)
        if score < 1:
            continue
        seen.add(fp)
        cands.append((score, idx, cleaned))
    cands.sort(key=lambda x: (-x[0], x[1]))
    out: List[Dict[str, Any]] = []
    for n, (_, _, txt) in enumerate(cands[:max_claims], start=1):
        low = txt.lower()
        claim_type = "interpretation"
        next_action = "challenge"
        if re.search(r"\b(\d+|percent|data|study|records?|documents?)\b", low):
            claim_type = "fact"
            next_action = "verify"
        out.append(
            {
                "id": f"c{n}",
                "text": txt,
                "claim_type": claim_type,
                "confidence": "medium",
                "why_it_matters": _ref_line_for_claim(txt, max_len=120),
                "counter_angle": "",
                "next_action": next_action,
            }
        )
    return out


def _enrich_brief_with_transcript_grounding(
    brief: Dict[str, Any],
    transcript: str,
    metadata: Dict[str, str],
) -> bool:
    """When LLM output is weak, fill claims/narrative from transcript evidence deterministically."""
    if not isinstance(brief, dict):
        return False
    claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]
    claims = _dedupe_renumber_claims(claims)
    if len(claims) >= 2:
        return False

    inferred = _extract_transcript_grounded_claims(transcript, metadata, max_claims=5)
    if not inferred:
        return False

    brief["claims"] = inferred
    narr = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    if not narr:
        brief["narrative"] = [_ref_line_for_claim(c["text"], max_len=140) for c in inferred[:3]]

    snap = brief.get("episode_snapshot")
    if not isinstance(snap, dict):
        snap = {}
    snap.setdefault("title", metadata.get("title") or "")
    snap.setdefault("creator", metadata.get("creator") or "")
    snap.setdefault("genre", metadata.get("genre") or "")
    if _is_meta_topic_line(str(snap.get("primary_topic") or "")):
        snap["primary_topic"] = ""
    _sanitize_episode_snapshot(snap, inferred)
    if not str(snap.get("why_it_matters") or "").strip():
        snap["why_it_matters"] = _ref_line_for_claim(inferred[0]["text"], max_len=140)
    brief["episode_snapshot"] = snap
    return True


def _refine_genre_from_title(title: str, current_genre: str) -> str:
    """
    YouTube / RSS metadata very often categorises long-form interview podcasts as "Entertainment"
    even when the episode is clearly about a specific domain. When the current genre is the
    generic "Entertainment" fallback, prefer a domain label inferred from the title keywords.

    Never overrides a meaningful existing genre (e.g. "Education", "Business", "Politics").
    """
    cg = (current_genre or "").strip()
    low_cg = cg.lower()
    is_generic = low_cg in ("", "entertainment", "people & blogs", "people and blogs", "general")
    if not is_generic:
        return cg
    title_l = (title or "").lower()
    if not title_l:
        return cg
    if _title_signals_education_or_institutions_history(title_l):
        return "Education / Society"
    if _title_signals_gambling_or_prediction_markets(title_l):
        return "Business / Markets"
    political_markers = (
        "election", "senator", "congress", "president", "supreme court",
        "politic", "policy", "government", "foreign policy", "geopolit",
    )
    if any(k in title_l for k in political_markers):
        return "Politics / Policy"
    history_markers = ("history", "historian", "archive", "declassified", "cold war", "world war")
    if any(k in title_l for k in history_markers):
        return "History"
    return cg


def _normalize_brief(data: Dict[str, Any], metadata: Dict[str, str]) -> Dict[str, Any]:
    snap = data.get("episode_snapshot") or {}
    snap.setdefault("title", metadata.get("title") or "")
    snap.setdefault("creator", metadata.get("creator") or "")
    snap.setdefault("genre", metadata.get("genre") or "")
    snap.setdefault("argument_topic", str(snap.get("primary_topic") or "").strip())
    # Refine a generic "Entertainment" label when the title clearly signals a specific domain.
    snap["genre"] = _refine_genre_from_title(
        str(snap.get("title") or ""), str(snap.get("genre") or "")
    )
    data["episode_snapshot"] = snap
    raw_claims = [c for c in (data.get("claims") or []) if isinstance(c, dict)]
    claims = _dedupe_renumber_claims(raw_claims)
    for c in claims:
        if "counter_angle" not in c:
            c["counter_angle"] = ""
        c["text"] = _clean_claim_text(str(c.get("text") or ""))
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
            "SOAPBOXX_OFFLINE is set; LLM brief generation was skipped (no episode JSON brief; v3 report will be a shell)."
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
            "Install Ollama, pull a model, and set SOAPBOXX_OLLAMA_MODEL for strict episode brief extraction (v3 report)."
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
        strict_mode = _strict_contract_brief_enabled()
        t_for_generation = t
        merged_claims: Optional[List[Dict[str, Any]]] = None
        if strict_mode:
            cap = _strict_contract_input_cap_chars()
            if len(t_for_generation) > cap:
                t_for_generation = (
                    t_for_generation[:cap]
                    + "\n\n[TRANSCRIPT TRUNCATED — strict contract mode; raise SOAPBOXX_BRIEF_CONTRACT_MAX_CHARS if needed]\n"
                )
                warnings.append(
                    f"Strict contract mode: transcript capped to {cap} chars "
                    f"(full length {len(t)}; set SOAPBOXX_BRIEF_CONTRACT_MAX_CHARS to adjust)."
                )
        elif len(t) > single_pass_limit:
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
            merged_claims = _merge_claim_chunks(claim_lists)

        correction_feedback = ""
        data: Dict[str, Any] = {}
        for attempt in range(_BRIEF_SCHEMA_MAX_RETRIES + 1):
            attempt_num = attempt + 1
            try:
                if strict_mode:
                    if _spine_first_brief_enabled():
                        data = _generate_brief_via_spine_first(
                            client,
                            use_new_api,
                            t_for_generation,
                            meta,
                            correction_feedback=correction_feedback,
                        )
                    else:
                        data = _generate_brief_via_strict_contract(
                            client,
                            use_new_api,
                            t_for_generation,
                            meta,
                            correction_feedback=correction_feedback,
                        )
                elif merged_claims is None:
                    data = _single_pass_brief(
                        client,
                        use_new_api,
                        t,
                        meta,
                        correction_feedback=correction_feedback,
                    )
                else:
                    data = _synthesize_full_brief(
                        client,
                        use_new_api,
                        t,
                        merged_claims,
                        meta,
                        correction_feedback=correction_feedback,
                    )
            except Exception as gen_err:
                gen_reason = str(gen_err)
                print(
                    f"[episode_intelligence] Brief generation attempt {attempt_num}/"
                    f"{_BRIEF_SCHEMA_MAX_RETRIES + 1} failed: {gen_reason}",
                    flush=True,
                )
                _LOG.error(
                    "brief generation attempt %d/%d failed: %s",
                    attempt_num,
                    _BRIEF_SCHEMA_MAX_RETRIES + 1,
                    gen_reason,
                )
                if attempt >= _BRIEF_SCHEMA_MAX_RETRIES:
                    raise ValueError(
                        "Brief generation failed after retries: " + gen_reason
                    ) from gen_err
                correction_feedback = _build_schema_retry_feedback(
                    [f"generation error: {gen_reason}"]
                )
                print(
                    f"[episode_intelligence] Retrying brief generation with correction feedback "
                    f"(retry {attempt_num}/{_BRIEF_SCHEMA_MAX_RETRIES}).",
                    flush=True,
                )
                continue

            schema_failures = _brief_schema_failures(data)
            if not schema_failures:
                if attempt > 0:
                    print(
                        f"[episode_intelligence] Brief schema validation passed on retry {attempt_num}.",
                        flush=True,
                    )
                break

            failure_msg = "; ".join(schema_failures[:8])
            print(
                f"[episode_intelligence] Brief schema validation failed (attempt {attempt_num}/"
                f"{_BRIEF_SCHEMA_MAX_RETRIES + 1}): {failure_msg}",
                flush=True,
            )
            _LOG.error(
                "brief schema validation failed attempt %d/%d: %s",
                attempt_num,
                _BRIEF_SCHEMA_MAX_RETRIES + 1,
                failure_msg,
            )
            if attempt >= _BRIEF_SCHEMA_MAX_RETRIES:
                raise ValueError(
                    "Brief schema validation failed after retries: " + "; ".join(schema_failures)
                )
            correction_feedback = _build_schema_retry_feedback(schema_failures)
            print(
                f"[episode_intelligence] Retrying brief generation with schema feedback "
                f"(retry {attempt_num}/{_BRIEF_SCHEMA_MAX_RETRIES}).",
                flush=True,
            )
        print("[episode_intelligence] Brief generation completed.")
        data = _normalize_brief(data, meta)
        asp = data.get("argument_spine")
        if isinstance(asp, dict):
            smd = asp.get("metadata")
            if isinstance(smd, dict):
                for w in smd.get("warnings") or []:
                    if isinstance(w, str) and w.strip():
                        warnings.append(f"Spine pass: {w.strip()}")
                if str(smd.get("error") or "").strip():
                    warnings.append(f"Spine metadata: {str(smd.get('error')).strip()}")
        ac = data.get("argument_critic")
        if isinstance(ac, dict):
            cmd = ac.get("metadata")
            if isinstance(cmd, dict):
                conf = str(cmd.get("confidence") or "").strip().lower()
                if conf == "low":
                    warnings.append("Spine critic reported low confidence.")
                if str(cmd.get("error") or "").strip():
                    warnings.append(f"Spine critic: {str(cmd.get('error')).strip()}")
        ar = data.get("argument_refined")
        if isinstance(ar, dict):
            rmd = ar.get("metadata")
            if isinstance(rmd, dict):
                for w in rmd.get("warnings") or []:
                    if isinstance(w, str) and w.strip():
                        warnings.append(f"Spine refiner: {w.strip()}")
                if str(rmd.get("error") or "").strip():
                    warnings.append(f"Spine refiner: {str(rmd.get('error')).strip()}")
        post_norm_failures = _brief_schema_failures(data)
        if post_norm_failures:
            raise ValueError(
                "Normalized brief failed schema validation: " + "; ".join(post_norm_failures)
            )
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
        _LOG.error("brief generation hard-failed after schema retries: %s", e)
        warnings.append(f"Brief generation hard failure after schema retries: {e}")
        nb = _normalize_brief(_minimal_brief(meta), meta)
        return {
            "brief": nb,
            "markdown": render_markdown(nb, meta.get("generated_at")),
            "warnings": warnings,
            "model": "brief-unavailable",
            "workflow_version": REPORT_WORKFLOW_VERSION,
        }
