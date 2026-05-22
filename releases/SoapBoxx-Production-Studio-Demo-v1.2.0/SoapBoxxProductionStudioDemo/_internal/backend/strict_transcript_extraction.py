# backend/strict_transcript_extraction.py
"""
3-stage **strict transcript extraction** pipeline (extraction → validation → render).

- **Stage 1:** LLM prompt returns JSON only (caller supplies the model call).
- **Stage 2:** Validate → **mechanical-only** auto-repair → re-validate → LLM retry if still bad.
- **Stage 3:** Template-only markdown from validated JSON (no paraphrase).

Auto-repair only fixes duplicates, substring overlaps, non-verbatim ``key_quotes`` removal,
optional whitespace on quote strings, and segment quote rows aligned to surviving ``key_quotes``.
It does **not** fix schema breakage, paraphrase, or bad segmentation (those require retry).

Designed to stay separate from coach/v3 narrative synthesis so boundaries do not blur.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import jsonschema
    from jsonschema import Draft202012Validator

    _HAS_JSONSCHEMA = True
except ImportError:  # pragma: no cover - optional until deps installed
    _HAS_JSONSCHEMA = False
    Draft202012Validator = None  # type: ignore[misc,assignment]


STRICT_EXTRACTION_PROMPT_TEMPLATE = """You are a data extraction engine.

Your task is to extract structured information from a podcast transcript and return ONLY valid JSON that strictly follows the provided schema.

You are NOT allowed to summarize, paraphrase, interpret, or infer meaning.

---

## OUTPUT REQUIREMENTS

- Return ONLY valid JSON
- No markdown, no explanations, no extra text
- Every field in the schema must be present
- If data is missing, return "" or []
- Do not invent information

---

## STRICT RULES

1. VERBATIM TEXT ONLY
- All text must be exact substrings from the transcript
- No rewriting

2. NO DUPLICATION
- No repeated quotes or segments

3. SEGMENTATION
- One continuous topic per segment

4. SPEAKER BLOCKS
- One speaker, uninterrupted

5. QUOTES
- Exact text only
- No merging
- Must be meaningful standalone

6. QUOTE SELECTION CONSISTENCY
- Prefer full sentences
- No partial fragments
- No overlapping quotes
- If similar quotes exist → choose ONE
- If multiple valid options → choose earliest occurrence

7. TIMESTAMPS
- Use if available, else ""

8. ENTITIES
- Only explicitly mentioned

---

## SCHEMA

{
  "episode": {
    "title": "",
    "guest_name": "",
    "host_name": "",
    "date": "",
    "duration": ""
  },
  "segments": [
    {
      "id": "",
      "topic": "",
      "start_time": "",
      "end_time": "",
      "speaker_blocks": [
        {
          "speaker": "",
          "text": "",
          "quotes": [
            {
              "text": "",
              "timestamp": ""
            }
          ]
        }
      ]
    }
  ],
  "key_quotes": [
    {
      "text": "",
      "speaker": "",
      "timestamp": "",
      "topic": ""
    }
  ],
  "entities": {
    "people": [],
    "companies": [],
    "topics": []
  }
}

---

## INPUT

{{TRANSCRIPT}}
"""


EXTRACTION_RETRY_SUFFIX_TEMPLATE = """Your previous output failed validation.

ERROR: {{ERROR}}

Fix the issue and return corrected JSON only.
"""


STRICT_RENDER_PROMPT_TEMPLATE = """Fill the report template using ONLY the provided JSON.

Rules:
- Do NOT paraphrase
- Do NOT add information
- Do NOT infer
- Copy text exactly
- If data is missing, leave blank

## JSON
{{JSON}}
"""


def build_extraction_prompt(transcript: str) -> str:
    return STRICT_EXTRACTION_PROMPT_TEMPLATE.replace("{{TRANSCRIPT}}", transcript or "")


def build_retry_suffix(error_message: str) -> str:
    return EXTRACTION_RETRY_SUFFIX_TEMPLATE.replace("{{ERROR}}", (error_message or "").strip()[:2000])


def build_render_prompt(validated_json: Dict[str, Any]) -> str:
    blob = json.dumps(validated_json, ensure_ascii=False, indent=2)
    return STRICT_RENDER_PROMPT_TEMPLATE.replace("{{JSON}}", blob)


def normalize_whitespace(text: str) -> str:
    return " ".join((text or "").lower().split())


# Alias for drop-in parity with standalone snippets / tests.
normalize = normalize_whitespace


EXTRACTION_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["episode", "segments", "key_quotes", "entities"],
    "additionalProperties": False,
    "properties": {
        "episode": {
            "type": "object",
            "required": ["title", "guest_name", "host_name", "date", "duration"],
            "additionalProperties": False,
            "properties": {
                "title": {"type": "string"},
                "guest_name": {"type": "string"},
                "host_name": {"type": "string"},
                "date": {"type": "string"},
                "duration": {"type": "string"},
            },
        },
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "topic", "start_time", "end_time", "speaker_blocks"],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "topic": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "speaker_blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["speaker", "text", "quotes"],
                            "additionalProperties": False,
                            "properties": {
                                "speaker": {"type": "string"},
                                "text": {"type": "string"},
                                "quotes": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "required": ["text", "timestamp"],
                                        "additionalProperties": False,
                                        "properties": {
                                            "text": {"type": "string"},
                                            "timestamp": {"type": "string"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "key_quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text", "speaker", "timestamp", "topic"],
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string"},
                    "speaker": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "topic": {"type": "string"},
                },
            },
        },
        "entities": {
            "type": "object",
            "required": ["people", "companies", "topics"],
            "additionalProperties": False,
            "properties": {
                "people": {"type": "array", "items": {"type": "string"}},
                "companies": {"type": "array", "items": {"type": "string"}},
                "topics": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


def _schema_validate(data: Any) -> Optional[str]:
    if _HAS_JSONSCHEMA and Draft202012Validator is not None:
        try:
            Draft202012Validator(EXTRACTION_JSON_SCHEMA).validate(data)
        except jsonschema.ValidationError as e:  # type: ignore[attr-defined]
            return f"Schema error: {e.message}"
        return None
    if not isinstance(data, dict):
        return "Schema error: root must be an object"
    for k in ("episode", "segments", "key_quotes", "entities"):
        if k not in data:
            return f"Schema error: missing {k}"
    return None


def _verbatim_in_transcript(quote_text: str, transcript: str) -> bool:
    qt = (quote_text or "").strip()
    if not qt:
        return True
    t = transcript or ""
    if qt in t:
        return True
    return normalize_whitespace(qt) in normalize_whitespace(t)


def _iter_nested_quotes(data: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for seg in data.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        for blk in seg.get("speaker_blocks") or []:
            if not isinstance(blk, dict):
                continue
            for q in blk.get("quotes") or []:
                if isinstance(q, dict) and str(q.get("text") or "").strip():
                    out.append(str(q["text"]).strip())
    return out


def validate_strict_extraction(
    data: Dict[str, Any],
    transcript: str,
    *,
    check_nested_quotes: bool = True,
) -> Tuple[bool, Union[str, Dict[str, Any]]]:
    """
    Return ``(True, data)`` when valid; ``(False, error_string)`` otherwise.
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON root"

    err = _schema_validate(data)
    if err:
        return False, err

    seen: set = set()
    quotes_norm: List[str] = []

    for q in data.get("key_quotes") or []:
        if not isinstance(q, dict):
            return False, "key_quotes items must be objects"
        text = str(q.get("text") or "").strip()
        if not text:
            continue
        if not _verbatim_in_transcript(text, transcript):
            return False, f"Quote not in transcript: {text[:120]}"
        n = normalize_whitespace(text)
        if n in seen:
            return False, f"Duplicate quote: {text[:120]}"
        seen.add(n)
        quotes_norm.append(n)

    for i in range(len(quotes_norm)):
        for j in range(i + 1, len(quotes_norm)):
            a, b = quotes_norm[i], quotes_norm[j]
            if a in b or b in a:
                return False, "Overlapping key_quotes detected"

    if check_nested_quotes:
        for t in _iter_nested_quotes(data):
            if t and not _verbatim_in_transcript(t, transcript):
                return False, f"Nested quote not in transcript: {t[:120]}"

    return True, data


def _strip_quote_text_fields_mechanical(data: Dict[str, Any]) -> Dict[str, Any]:
    """``.strip()`` on quote ``text`` fields only (whitespace formatting)."""
    kq = data.get("key_quotes")
    if isinstance(kq, list):
        for q in kq:
            if isinstance(q, dict) and "text" in q and isinstance(q["text"], str):
                q["text"] = q["text"].strip()
    for seg in data.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        for blk in seg.get("speaker_blocks") or []:
            if not isinstance(blk, dict):
                continue
            for q in blk.get("quotes") or []:
                if isinstance(q, dict) and "text" in q and isinstance(q["text"], str):
                    q["text"] = q["text"].strip()
    return data


def dedupe_key_quotes(data: Dict[str, Any]) -> Dict[str, Any]:
    """First occurrence wins; normalized text as dedupe key."""
    kq = data.get("key_quotes")
    if not isinstance(kq, list):
        return data
    seen: set = set()
    new_quotes: List[Dict[str, Any]] = []
    for q in kq:
        if not isinstance(q, dict):
            continue
        n = normalize_whitespace(str(q.get("text") or ""))
        if not n:
            continue
        if n in seen:
            continue
        seen.add(n)
        new_quotes.append(q)
    data["key_quotes"] = new_quotes
    return data


def remove_overlapping_key_quotes(data: Dict[str, Any]) -> Dict[str, Any]:
    """If one normalized quote is strictly contained in another, drop the shorter."""
    quotes = data.get("key_quotes")
    if not isinstance(quotes, list):
        return data
    cleaned: List[Dict[str, Any]] = []
    for i, q1 in enumerate(quotes):
        if not isinstance(q1, dict):
            continue
        t1 = normalize_whitespace(str(q1.get("text") or ""))
        if not t1:
            continue
        keep = True
        for j, q2 in enumerate(quotes):
            if i == j or not isinstance(q2, dict):
                continue
            t2 = normalize_whitespace(str(q2.get("text") or ""))
            if not t2:
                continue
            if t1 in t2 and len(t1) < len(t2):
                keep = False
                break
        if keep:
            cleaned.append(q1)
    data["key_quotes"] = cleaned
    return data


def remove_invalid_key_quotes(data: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    """Drop ``key_quotes`` whose text is not a verbatim substring (same bar as validation)."""
    kq = data.get("key_quotes")
    if not isinstance(kq, list):
        return data
    valid: List[Dict[str, Any]] = []
    for q in kq:
        if not isinstance(q, dict):
            continue
        text = str(q.get("text") or "").strip()
        if not text:
            continue
        if _verbatim_in_transcript(text, transcript):
            valid.append(q)
    data["key_quotes"] = valid
    return data


def sync_segment_quotes_to_key_quotes(data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only nested ``quotes`` whose normalized text appears in ``key_quotes``."""
    kq = data.get("key_quotes")
    if not isinstance(kq, list):
        return data
    valid_texts = {normalize_whitespace(str(q.get("text") or "")) for q in kq if isinstance(q, dict)}
    valid_texts.discard("")

    for seg in data.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        for blk in seg.get("speaker_blocks") or []:
            if not isinstance(blk, dict):
                continue
            raw_quotes = blk.get("quotes")
            if not isinstance(raw_quotes, list):
                continue
            filtered: List[Dict[str, Any]] = []
            for q in raw_quotes:
                if not isinstance(q, dict):
                    continue
                n = normalize_whitespace(str(q.get("text") or ""))
                if n and n in valid_texts:
                    filtered.append(q)
            blk["quotes"] = filtered
    return data


def auto_repair(data: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    """
    Mechanical-only fixes: dedupe, overlap (shorter dropped), invalid key quotes removed,
    segment nested quotes aligned to surviving key quotes, quote ``text`` stripped.
    Does not invent or rewrite meaning.
    """
    repaired = deepcopy(data)
    _strip_quote_text_fields_mechanical(repaired)
    dedupe_key_quotes(repaired)
    remove_overlapping_key_quotes(repaired)
    remove_invalid_key_quotes(repaired, transcript)
    sync_segment_quotes_to_key_quotes(repaired)
    return repaired


def repair_score(original: Dict[str, Any], repaired: Dict[str, Any]) -> float:
    """
    Ratio of surviving ``key_quotes`` count to original list length.
    Returns ``1.0`` when there were no key quotes to begin with (nothing to lose).
    """
    oq = original.get("key_quotes") if isinstance(original.get("key_quotes"), list) else []
    rq = repaired.get("key_quotes") if isinstance(repaired.get("key_quotes"), list) else []
    no = len(oq)
    if no == 0:
        return 1.0
    return len(rq) / no


def repair_key_quotes(data: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    """Backward-compatible name for :func:`auto_repair`."""
    return auto_repair(data, transcript)


def run_strict_extraction_pipeline(
    transcript: str,
    llm_call: Callable[[str], str],
    *,
    max_retries: int = 3,
    enable_auto_repair: bool = True,
    repair_score_min: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Flow: parse JSON → **validate** → on failure, :func:`auto_repair` → **re-validate** →
    optional ``repair_score_min`` gate → else LLM retry with last error.

    ``llm_call`` receives the **full** prompt (base or base+retry) and must return raw model text (JSON).

    ``repair_score_min`` (e.g. ``0.5``): if set, reject a repair that drops too many
    ``key_quotes`` vs the raw model list (forces retry instead of silent over-stripping).

    ``enable_auto_repair``: set False to skip the mechanical repair path (LLM retries only).
    """
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    base_prompt = build_extraction_prompt(transcript)
    last_error = ""

    for attempt in range(max_retries):
        prompt = base_prompt if attempt == 0 else (base_prompt + "\n\n" + build_retry_suffix(last_error))
        raw = (llm_call(prompt) or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```\s*$", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON: {e}"
            continue

        if not isinstance(data, dict):
            last_error = "JSON root must be an object"
            continue

        ok, res = validate_strict_extraction(data, transcript)
        if ok:
            return res  # type: ignore[return-value]

        last_error = str(res)

        if enable_auto_repair:
            snapshot_before_repair = deepcopy(data)
            repaired = auto_repair(data, transcript)
            ok2, res2 = validate_strict_extraction(repaired, transcript)
            if ok2:
                score = repair_score(snapshot_before_repair, repaired)
                if repair_score_min is not None and score < repair_score_min:
                    last_error = (
                        f"{last_error} | Auto-repair re-validated but repair_score={score:.2f} "
                        f"< repair_score_min={repair_score_min} (rejecting silent over-stripping)"
                    )
                else:
                    return res2  # type: ignore[return-value]
            else:
                last_error = f"{last_error} | After auto-repair: {res2}"

    raise ValueError(f"Strict extraction failed after {max_retries} attempt(s): {last_error}")


def render_strict_json_to_markdown(data: Dict[str, Any]) -> str:
    """Stage-3 **code** renderer: map JSON → markdown with no interpretation."""
    lines: List[str] = ["# Extracted episode (strict pipeline)", ""]
    ep = data.get("episode") if isinstance(data.get("episode"), dict) else {}
    lines.append("## Episode")
    for k in ("title", "guest_name", "host_name", "date", "duration"):
        lines.append(f"- **{k}:** {str(ep.get(k) or '').strip()}")
    lines.append("")
    lines.append("## Key quotes")
    for q in data.get("key_quotes") or []:
        if not isinstance(q, dict):
            continue
        t = str(q.get("text") or "").strip()
        if not t:
            continue
        sp = str(q.get("speaker") or "").strip()
        ts = str(q.get("timestamp") or "").strip()
        top = str(q.get("topic") or "").strip()
        meta_bits: List[str] = []
        if sp:
            meta_bits.append(f"speaker: {sp}")
        if ts:
            meta_bits.append(f"time: {ts}")
        if top:
            meta_bits.append(f"topic: {top}")
        meta = " | ".join(meta_bits)
        lines.append(f"- {t}" + (f" — _{meta}_" if meta else ""))
    lines.append("")
    lines.append("## Segments")
    for seg in data.get("segments") or []:
        if not isinstance(seg, dict):
            continue
        sid = str(seg.get("id") or "").strip()
        topic = str(seg.get("topic") or "").strip()
        lines.append(f"### {sid or '(segment)'} — {topic}".rstrip(" — "))
        for blk in seg.get("speaker_blocks") or []:
            if not isinstance(blk, dict):
                continue
            sp = str(blk.get("speaker") or "").strip()
            tx = str(blk.get("text") or "").strip()
            if sp or tx:
                lines.append(f"- **{sp or 'speaker'}:** {tx}")
            for q in blk.get("quotes") or []:
                if isinstance(q, dict) and str(q.get("text") or "").strip():
                    lines.append(f"  - Quote: {str(q.get('text')).strip()}")
        lines.append("")
    ent = data.get("entities") if isinstance(data.get("entities"), dict) else {}
    lines.append("## Entities")
    for k in ("people", "companies", "topics"):
        vals = ent.get(k) or []
        if isinstance(vals, list) and vals:
            lines.append(f"- **{k}:** {', '.join(str(x) for x in vals)}")
    return "\n".join(lines).strip() + "\n"


__all__ = [
    "STRICT_EXTRACTION_PROMPT_TEMPLATE",
    "build_extraction_prompt",
    "build_retry_suffix",
    "build_render_prompt",
    "validate_strict_extraction",
    "normalize",
    "normalize_whitespace",
    "dedupe_key_quotes",
    "remove_overlapping_key_quotes",
    "remove_invalid_key_quotes",
    "sync_segment_quotes_to_key_quotes",
    "auto_repair",
    "repair_score",
    "repair_key_quotes",
    "run_strict_extraction_pipeline",
    "render_strict_json_to_markdown",
    "EXTRACTION_JSON_SCHEMA",
]
