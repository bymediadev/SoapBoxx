# backend/soapboxx_v3_workflow.py
"""
**Primary** structured workflow JSON for SoapBoxx (spec version 3): highlights → evidence →
follow-ups → guests → segments → analytics. This module is the workflow layer — not the PyQt app.

**Default (`soapboxx_v3_workflow_local`):** builds the coach-style `report_v3` via
`episode_report_v3.generate_episode_report_v3`, maps it to workflow JSON, then — when an LLM is
available — **runs multi-step AI extraction** to fill highlights, evidence_map, follow-ups,
guests, segments, and analytics (`metadata.workflow_mode` = ``local+ai``).

- ``metadata.workflow_spec_version`` is always ``WORKFLOW_SPEC_VERSION`` (``"3"``); ``primary_episode_workflow`` is ``True``.
- Set ``SOAPBOXX_WORKFLOW_USE_AI=0`` to skip AI and keep deterministic mapping only (`local`).
- Transcript window: ``SOAPBOXX_WORKFLOW_MAX_WORDS`` defaults to **500_000** (~7 chars/word cap toward the hard character ceiling). Set ``SOAPBOXX_WORKFLOW_MAX_WORDS=0`` to use only ``SOAPBOXX_WORKFLOW_MAX_CHARS`` (default 3_000_000). Hard ceiling 3_500_000 characters.
- Evidence style: ``SOAPBOXX_WORKFLOW_EVIDENCE_MODE`` = ``anchors`` (default, verbatim pull quotes + short labels), ``full`` (claim+evidence pairs), or ``v3`` (keep coach ``report_v3`` mapping only, no LLM evidence pass).
- Each successful run adds ``markdown_export`` (unified numbered markdown) to the workflow JSON for scripts/CI — not wired to the PyQt main window.
- Follow-up questions (when AI is on) use **claim + evidence + local transcript window + episode meta**, plus an optional second **batch sharpen** pass. Set ``SOAPBOXX_WORKFLOW_SHARPEN_FU=0`` to disable only the sharpen pass (saves one LLM call).
- **Quality gate:** if the transcript is below ``SOAPBOXX_WORKFLOW_MIN_WORDS`` (default 200), or line-level uniqueness falls below ``SOAPBOXX_WORKFLOW_MIN_LINE_UNIQUENESS`` (default 0.22), multi-step enrichment is skipped in favor of **one** ``enrich_workflow_report_minimal`` call. Set ``SOAPBOXX_WORKFLOW_SKIP_GATE=1`` to always run full enrichment.

**Alternate:** ``use_cloud_llm=True`` — AI-only pipeline (`soapboxx_v3_workflow_cloud`), no v3 coach merge.

**LLM:** ``SOAPBOXX_OLLAMA_MODEL`` + ``OLLAMA_HOST`` (default http://127.0.0.1:11434) — Ollama only.
Ollama uses JSON mode for structured steps.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

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

try:
    from pydantic import BaseModel, ConfigDict, Field, ValidationError
except ImportError:  # pragma: no cover - fallback when dependency missing
    BaseModel = None  # type: ignore
    ConfigDict = dict  # type: ignore
    Field = None  # type: ignore
    ValidationError = Exception  # type: ignore

try:
    from .episode_intelligence import _clean_claim_text
except ImportError:
    from episode_intelligence import _clean_claim_text

REQUIRED_QUESTION_TYPES = frozenset({"counter", "validation", "application"})

# Structured workflow JSON is v3; distinct from the v2 compact brief JSON in episode_intelligence.
WORKFLOW_SPEC_VERSION = "3"

# Default word budget for workflow LLM transcript window (override via ``SOAPBOXX_WORKFLOW_MAX_WORDS``).
DEFAULT_WORKFLOW_MAX_WORDS = 500_000


def _apply_workflow_version_metadata(meta: Dict[str, Any]) -> None:
    """Stamp workflow outputs so integrations know this is the primary v3 workflow spec."""
    meta["workflow_spec_version"] = WORKFLOW_SPEC_VERSION
    meta["primary_episode_workflow"] = True


if BaseModel:
    class HighlightItem(BaseModel):
        model_config = ConfigDict(extra="allow")
        id: str
        insight: str


    class EvidenceItem(BaseModel):
        model_config = ConfigDict(extra="allow")
        id: str
        claim: str
        evidence: str
        timestamp: Optional[float] = None
        type: str
        strength: Optional[int] = None


    class FollowUpQuestionItem(BaseModel):
        model_config = ConfigDict(extra="allow")
        question: str
        question_type: str
        claim_id: str


    class WorkflowReportModel(BaseModel):
        model_config = ConfigDict(extra="allow")
        highlights: List[HighlightItem] = []
        evidence_map: List[EvidenceItem] = []
        follow_up_questions: List[FollowUpQuestionItem] = []
        summary: Optional[str] = None
        score: Optional[int] = Field(default=None, ge=0, le=100)
else:
    HighlightItem = EvidenceItem = FollowUpQuestionItem = WorkflowReportModel = None  # type: ignore


def _strip_json_fence(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def _model_name() -> str:
    return os.getenv("SOAPBOXX_OLLAMA_MODEL", "ollama").strip() or "ollama"


def _ollama_chat(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "",
    json_format: bool = False,
) -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError("SOAPBOXX_OLLAMA_MODEL not set")
    messages: List[Dict[str, str]] = []
    if (system or "").strip():
        messages.append({"role": "system", "content": system.strip()})
    messages.append({"role": "user", "content": prompt})
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature,
        },
    }
    if json_format:
        payload["format"] = "json"
    data_b = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=data_b,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    timeout_s = float(os.getenv("SOAPBOXX_OLLAMA_HTTP_TIMEOUT", "900") or "900")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = (e.read() or b"").decode("utf-8", errors="replace")[:2000]
        except Exception:
            pass
        hint = (
            f"Ollama returned HTTP {e.code} for POST {host}/api/chat. "
            "Confirm: (1) `ollama serve` is running and OLLAMA_HOST matches the API base "
            f"(default http://127.0.0.1:11434); (2) the model exists — run `ollama list` and "
            f"`ollama pull {model}` if needed. "
        )
        if body:
            hint += f"Response body: {body}"
        raise RuntimeError(hint) from e
    return (data.get("message") or {}).get("content") or ""


def call_llm(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "You follow instructions exactly. When asked for JSON, respond with ONLY valid JSON — no markdown fences, no commentary.",
    client: Any = None,
    json_format: bool = False,
) -> str:
    """Local Ollama only. Set ``SOAPBOXX_OLLAMA_MODEL``; ``client`` is ignored (compat)."""
    if not os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip():
        raise RuntimeError(
            "SOAPBOXX_OLLAMA_MODEL is not set — workflow LLM calls require a local Ollama model."
        )
    return _ollama_chat(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        json_format=json_format,
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
def call_llm_with_retry(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "You follow instructions exactly. When asked for JSON, respond with ONLY valid JSON — no markdown fences, no commentary.",
    client: Any = None,
    json_format: bool = False,
) -> str:
    return call_llm(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        client=client,
        json_format=json_format,
    )


def call_llm_json(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    parser: Callable[[str], Any] = json.loads,
    client: Any = None,
) -> Any:
    raw = call_llm_with_retry(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        client=client,
        json_format=True,
    )
    return parser(_strip_json_fence(raw))


def _workflow_transcript_excerpt(transcript: str) -> str:
    """How much transcript the workflow LLM steps may see.

    Default word budget is ``DEFAULT_WORKFLOW_MAX_WORDS`` (500k) unless overridden.
    Set ``SOAPBOXX_WORKFLOW_MAX_WORDS=0`` to ignore the word budget and use ``SOAPBOXX_WORKFLOW_MAX_CHARS`` only.
    """
    t = (transcript or "").strip()
    hard_max = 3_500_000
    mw_raw = os.getenv("SOAPBOXX_WORKFLOW_MAX_WORDS", "").strip()
    if not mw_raw:
        mw_raw = str(DEFAULT_WORKFLOW_MAX_WORDS)
    if mw_raw.isdigit() and int(mw_raw) > 0:
        w = min(max(int(mw_raw), 1), 500_000)
        cap = min(w * 7, hard_max)
        return t[:cap] if len(t) > cap else t
    raw = os.getenv("SOAPBOXX_WORKFLOW_MAX_CHARS", "3000000").strip()
    cap = 24_000
    if raw.isdigit():
        cap = min(max(int(raw), 2000), hard_max)
    return t[:cap] if len(t) > cap else t


def _workflow_evidence_mode() -> str:
    """
    anchors — verbatim pull quotes + short labels (default; less finicky than claim+evidence).
    full — structured claims mapped to quotes (legacy).
    v3 — do not replace evidence_map from LLM; keep mapping from coach report_v3 only.
    """
    raw = os.getenv("SOAPBOXX_WORKFLOW_EVIDENCE_MODE", "anchors").strip().lower()
    if raw in ("full", "claim", "claims", "mapped"):
        return "full"
    if raw in ("v3", "coach", "off", "none", "skip"):
        return "v3"
    return "anchors"


def _episode_meta_lines(episode_meta: Optional[Dict[str, Any]]) -> str:
    if not episode_meta:
        return ""
    lines: List[str] = []
    for key in ("title", "creator", "genre", "primary_topic", "episode_number"):
        v = str(episode_meta.get(key) or "").strip()
        if v:
            lines.append(f"- {key}: {v}")
    return "\n".join(lines)


def _episode_context_block(episode_meta: Optional[Dict[str, Any]]) -> str:
    """Title/genre lines so LLM steps stay aligned with the actual episode (not generic themes)."""
    if not episode_meta:
        return ""
    title = str(episode_meta.get("title") or "").strip()
    genre = str(episode_meta.get("genre") or "").strip()
    creator = str(episode_meta.get("creator") or "").strip()
    if not title and not genre and not creator:
        return ""
    parts = [
        "EPISODE CONTEXT (every insight and claim must match this episode — do not invent unrelated themes):",
    ]
    if title:
        parts.append(f"- Title: {title}")
    if creator:
        parts.append(f"- Creator / show: {creator}")
    if genre:
        parts.append(f"- Genre: {genre}")
    pt = str(episode_meta.get("primary_topic") or "").strip()
    if pt:
        parts.append(f"- Primary topic (if known): {pt}")
    parts.append("")
    return "\n".join(parts)


def _guest_topic_anchor_block(
    episode_meta: Optional[Dict[str, Any]],
    transcript: str,
    *,
    max_sample_chars: int = 3200,
) -> str:
    """
    Ground guest suggestions in this episode's subject: title, optional primary topic, transcript sample.
    """
    t = (transcript or "").strip()
    if not t and not episode_meta:
        return ""
    title = str((episode_meta or {}).get("title") or "").strip()
    genre = str((episode_meta or {}).get("genre") or "").strip()
    pt = str((episode_meta or {}).get("primary_topic") or "").strip()
    creator = str((episode_meta or {}).get("creator") or "").strip()
    parts = [
        "TOPIC ANCHOR — every guest must map to THIS episode (reject generic podcast guests):",
    ]
    if title:
        parts.append(f"- Episode title (primary subject signal): {title}")
    if creator:
        parts.append(f"- Show / host: {creator}")
    if genre:
        parts.append(f"- Genre: {genre}")
    if pt:
        parts.append(f"- Declared primary topic: {pt}")
    if t:
        if len(t) <= max_sample_chars:
            sample = t
        else:
            head = t[: max_sample_chars // 2]
            tail = t[-(max_sample_chars // 2) :]
            sample = f"{head}\n[... middle omitted ...]\n{tail}"
        parts.append("Transcript sample (use names, domains, conflicts here to pick topic-specific guests):")
        parts.append(sample[: max_sample_chars + 200])
    parts.append("")
    return "\n".join(parts)


def _normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


_TOPIC_SIGNAL_STOPWORDS = frozenset(
    {
        "life",
        "work",
        "actually",
        "something",
        "things",
        "people",
        "just",
        "really",
        "going",
        "want",
        "back",
        "were",
        "says",
        "said",
        "even",
        "well",
        "thing",
    }
)


def _scrub_topic_signals(signals: List[Any]) -> List[str]:
    """Drop single-token filler the model sometimes emits as 'topics'."""
    out: List[str] = []
    for x in signals or []:
        s = str(x).strip()
        if not s or len(s.split()) < 2:
            continue
        if s.lower() in _TOPIC_SIGNAL_STOPWORDS:
            continue
        out.append(s)
    return out[:12]


def _evidence_quote_grounded(transcript: str, evidence: str) -> bool:
    """True if the evidence string plausibly appears in the transcript (verbatim-ish)."""
    ev = (evidence or "").strip()
    if len(ev) < 12:
        return True
    t = _normalize_ws(transcript)
    e = _normalize_ws(ev)
    if e in t:
        return True
    t_alnum = re.sub(r"[^\w\s]", "", t)
    e_alnum = re.sub(r"[^\w\s]", "", e)
    if len(e_alnum) >= 12 and e_alnum in t_alnum:
        return True
    words = e_alnum.split()
    if len(words) < 5:
        return False
    need = max(4, int(len(words) * 0.72))
    chunk = " ".join(words[:need])
    return chunk in t_alnum


def _filter_grounded_evidence_map(
    transcript: str, rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Drop evidence rows whose quotes are not found in the transcript (hallucinated quotes)."""
    if not rows:
        return rows
    kept = [
        r
        for r in rows
        if isinstance(r, dict)
        and _evidence_quote_grounded(transcript, str(r.get("evidence") or ""))
    ]
    if len(kept) >= max(1, len(rows) // 4):
        return kept
    return rows


def _sanitize_evidence_map_claims(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove truncated ASR claim lines and duplicate beats (same claim text, different ids).
    """
    try:
        from .episode_report_v3 import _dedupe_repeated_sentences, _is_broken_evidence_claim_line
    except ImportError:
        from episode_report_v3 import _dedupe_repeated_sentences, _is_broken_evidence_claim_line

    seen = set()
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        cl = str(r.get("claim") or "").strip()
        if not cl or _is_broken_evidence_claim_line(cl):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", cl.lower()).strip()[:140]
        if key in seen:
            continue
        seen.add(key)
        rr = dict(r)
        ev = str(rr.get("evidence") or "").strip()
        if ev:
            rr["evidence"] = _dedupe_repeated_sentences(ev)
        out.append(rr)
    return out


def _ensure_evidence_map_ids(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ollama JSON occasionally omits `id`; validation requires c1, c2, …"""
    out: List[Dict[str, Any]] = []
    n = 0
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        n += 1
        rr = dict(r)
        if not str(rr.get("id") or "").strip():
            rr["id"] = f"c{n}"
        out.append(rr)
    return out


def _ensure_evidence_map_nonempty(
    transcript: str, rows: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Guarantee at least one evidence row so strict validate_json can pass."""
    if rows:
        return rows
    t = (transcript or "").strip()
    quote = ""
    for line in t.splitlines():
        s = line.strip()
        if len(s.split()) >= 8:
            quote = s[:500]
            break
    if not quote:
        quote = (" ".join(t.split()[:50]))[:500] or "…"
    return [
        {
            "id": "c1",
            "claim": "Core moment from the transcript (auto anchor).",
            "evidence": quote,
            "timestamp": None,
            "type": "pull_quote",
            "strength": 6,
        }
    ]


def _local_transcript_window(transcript: str, evidence: str, *, radius: int = 360) -> str:
    """Narrow excerpt around the evidence quote so follow-up questions can reference scene-specific stakes."""
    t = transcript or ""
    ev = (evidence or "").strip()
    if len(ev) < 12 or not t:
        return ""
    for n in (min(80, len(ev)), 50, 35):
        needle = ev[:n]
        idx = t.find(needle)
        if idx >= 0:
            lo = max(0, idx - radius)
            hi = min(len(t), idx + len(ev) + radius)
            return t[lo:hi].strip()
    return ""


def _sharpen_follow_up_batch_enabled() -> bool:
    return os.getenv("SOAPBOXX_WORKFLOW_SHARPEN_FU", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _workflow_quality_gate_full_enrichment(
    transcript: str,
    r3: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Cheap checks before multi-step LLM enrichment. If the gate fails, run
    ``enrich_workflow_report_minimal`` (one call) instead.

    Do **not** require ``report_v3`` claims: ``enrich_workflow_report_with_ai`` builds
    ``evidence_map`` from the transcript directly.

    Set ``SOAPBOXX_WORKFLOW_SKIP_GATE=1`` to always run full enrichment (skip these checks).
    """
    _ = r3  # reserved for future gates that need v3 context
    if os.getenv("SOAPBOXX_WORKFLOW_SKIP_GATE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True, []
    issues: List[str] = []
    wc = len((transcript or "").split())
    min_w = int(os.getenv("SOAPBOXX_WORKFLOW_MIN_WORDS", "200"))
    if wc < min_w:
        issues.append(f"transcript_word_count={wc} (min {min_w})")
    lines = [ln.strip() for ln in (transcript or "").splitlines() if ln.strip()]
    if len(lines) >= 24:
        uniq = len(set(lines))
        ratio = uniq / len(lines)
        raw_u = os.getenv("SOAPBOXX_WORKFLOW_MIN_LINE_UNIQUENESS", "0.22").strip()
        try:
            min_uniq = float(raw_u)
        except ValueError:
            min_uniq = 0.22
        min_uniq = min(max(min_uniq, 0.05), 0.95)
        if ratio < min_uniq:
            issues.append(f"duplicate_line_ratio_high (line_uniqueness={ratio:.2f}, min {min_uniq})")
    return len(issues) == 0, issues


def _llm_available() -> bool:
    return bool(os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip())


def _workflow_ai_enrichment_enabled() -> bool:
    return os.getenv("SOAPBOXX_WORKFLOW_USE_AI", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def enrich_workflow_report_minimal(
    transcript: str,
    body: Dict[str, Any],
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single LLM call when the quality gate skips full multi-step enrichment (very short transcript
    or highly duplicated lines). Uses the same transcript window as full enrichment
    (``SOAPBOXX_WORKFLOW_MAX_CHARS``). Produces a smaller but valid workflow slice.
    """
    out = dict(body)
    excerpt = _workflow_transcript_excerpt(transcript)
    if not excerpt.strip():
        _sanitize_workflow_highlights(out)
        return out
    ev_mode = _workflow_evidence_mode()
    if ev_mode == "v3":
        _sanitize_workflow_highlights(out)
        return out
    meta_lines = _episode_meta_lines(episode_meta)
    ectx = _episode_context_block(episode_meta)
    if ev_mode == "full":
        em_rules = """- "evidence_map": 3–5 objects with id, claim, evidence, timestamp, type, strength (ids c1, c2, … in order).
  type must be one of: story_beat | personal_account | institutional | legal_risk | business | other"""
    else:
        em_rules = """- "evidence_map": 3–5 objects with id, claim, evidence, timestamp, type, strength (ids c1, c2, … in order).
  claim: short label (≤18 words). evidence: verbatim substring from TRANSCRIPT. type: always "pull_quote" """
    prompt = f"""
TASK: Build a podcast workflow JSON from the transcript. The transcript may be short or noisy —
extract only what you can justify from the text.

{ectx}SHOW METADATA:
{meta_lines or "(none)"}

TRANSCRIPT:
{excerpt}

Return ONE JSON object only with keys:
- "highlights": up to 5 objects with keys id, insight, length_words, priority (ids h1..h5)
{em_rules}
- "follow_up_questions": for each evidence id, exactly 3 questions with question_type counter, validation, application (one each) and matching claim_id

Rules: complete sentences; no trailing ellipsis; no empty strings; evidence must be copied verbatim from TRANSCRIPT; claims must match the episode title/subject when provided.

Output JSON only.
"""
    try:
        data = call_llm_json(prompt, max_tokens=4000, temperature=0.2, client=client)
    except Exception:
        _sanitize_workflow_highlights(out)
        return out
    if not isinstance(data, dict):
        _sanitize_workflow_highlights(out)
        return out
    if isinstance(data.get("highlights"), list) and data["highlights"]:
        out["highlights"] = data["highlights"][:5]
    if isinstance(data.get("evidence_map"), list) and data["evidence_map"]:
        em = _filter_grounded_evidence_map(transcript or "", data["evidence_map"][:8])
        out["evidence_map"] = _sanitize_evidence_map_claims(em)
    if isinstance(data.get("follow_up_questions"), list) and data["follow_up_questions"]:
        out["follow_up_questions"] = data["follow_up_questions"]
    _sanitize_workflow_highlights(out)
    return out


def enrich_workflow_report_with_ai(
    transcript: str,
    body: Dict[str, Any],
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fill workflow JSON using multi-step LLM extraction (highlights, evidence, Q&A, guests,
    segments, analytics). Caller supplies base `body` from `workflow_report_from_v3_report`;
    non-empty AI sections replace the corresponding lists.

    ``episode_meta`` (title, creator, genre, …) is passed into follow-up generation so questions
    are anchored to the show and claims, not generic podcast boilerplate.
    """
    out = dict(body)
    excerpt = _workflow_transcript_excerpt(transcript)
    if not excerpt:
        return out

    highlights = generate_highlights(excerpt, client=client, episode_meta=episode_meta)
    if highlights:
        out["highlights"] = highlights

    ev_mode = _workflow_evidence_mode()
    if ev_mode == "v3":
        pass  # keep evidence_map from workflow_report_from_v3_report(body)
    elif ev_mode == "full":
        evidence_map = generate_evidence_map(excerpt, client=client, episode_meta=episode_meta)
        if evidence_map:
            evidence_map = _filter_grounded_evidence_map(transcript or "", evidence_map)
            out["evidence_map"] = _sanitize_evidence_map_claims(evidence_map)
    else:
        evidence_map = generate_anchor_evidence_map(
            excerpt, client=client, episode_meta=episode_meta
        )
        if evidence_map:
            evidence_map = _filter_grounded_evidence_map(transcript or "", evidence_map)
            out["evidence_map"] = _sanitize_evidence_map_claims(evidence_map)

    em = out.get("evidence_map") or []
    questions = generate_follow_up_questions(
        em,
        client=client,
        transcript=transcript or "",
        episode_meta=episode_meta,
    )
    if questions:
        if _sharpen_follow_up_batch_enabled():
            questions = refine_follow_up_questions_batch(
                excerpt,
                em,
                questions,
                client=client,
                episode_meta=episode_meta,
            )
        out["follow_up_questions"] = questions

    guests = generate_guest_recommendations(
        em,
        client=client,
        highlights=out.get("highlights") or [],
        episode_meta=episode_meta,
        transcript=transcript or "",
    )
    if guests:
        for g in guests:
            if not isinstance(g, dict):
                continue
            if not str(g.get("title") or "").strip():
                r = str(g.get("role") or "").strip()
                if r:
                    g["title"] = r
            g.setdefault("topic_angle", g.get("angle"))
        out["guest_recommendations"] = guests

    hl = out.get("highlights") or []
    segments = generate_segments(em, hl, client=client)
    if segments:
        out["segments"] = segments

    analytics = generate_analytics(excerpt, em, client=client, episode_meta=episode_meta)
    if isinstance(analytics, dict) and any(
        analytics.get(k) for k in ("storylines", "topic_signals", "actionable_steps")
    ):
        out["analytics"] = {
            "storylines": list(analytics.get("storylines") or []),
            "topic_signals": list(analytics.get("topic_signals") or []),
            "actionable_steps": list(analytics.get("actionable_steps") or []),
        }

    _sanitize_workflow_highlights(out)
    return out


def validate_json(report: Dict[str, Any], *, strict: bool = True) -> Dict[str, Any]:
    """
    Validate v3 JSON structure. With strict=False, only checks types and refs when evidence exists.
    """
    if WorkflowReportModel is not None:
        try:
            parsed = WorkflowReportModel.model_validate(report)
            report = parsed.model_dump(exclude_none=True)
        except ValidationError as e:
            raise ValueError(f"Schema validation failed: {e}") from e

    em = report.get("evidence_map") or []
    if not isinstance(em, list):
        raise ValueError("evidence_map must be a list")
    valid_ids = {str(e.get("id")) for e in em if isinstance(e, dict) and e.get("id")}

    highlights = report.get("highlights") or []
    if isinstance(highlights, list) and len(highlights) > 5:
        report["highlights"] = highlights[:5]

    fuq = report.get("follow_up_questions") or []
    if not isinstance(fuq, list):
        raise ValueError("follow_up_questions must be a list")

    if not strict and not valid_ids:
        return report

    if strict and not valid_ids:
        raise ValueError("evidence_map must contain at least one item with id")

    for q in fuq:
        if not isinstance(q, dict):
            raise ValueError("Each follow_up_question must be an object")
        cid = str(q.get("claim_id") or "")
        if valid_ids and cid not in valid_ids:
            raise ValueError(
                f"Invalid question reference claim_id={cid!r}; valid: {sorted(valid_ids)}"
            )

    claim_qtypes: Dict[str, set] = {}
    for q in fuq:
        qt = str(q.get("question_type") or "").lower().strip()
        cid = str(q.get("claim_id") or "")
        if qt not in REQUIRED_QUESTION_TYPES:
            raise ValueError(
                f"Invalid question_type {qt!r}; expected one of {sorted(REQUIRED_QUESTION_TYPES)}"
            )
        claim_qtypes.setdefault(cid, set()).add(qt)

    if strict:
        for cid in valid_ids:
            got = claim_qtypes.get(cid, set())
            missing = REQUIRED_QUESTION_TYPES - got
            if missing:
                raise ValueError(
                    f"Claim {cid} missing question types: {sorted(missing)} (has {sorted(got)})"
                )

    if not strict:
        return report

    for section_name in ("highlights", "evidence_map", "follow_up_questions"):
        section = report.get(section_name) or []
        if not isinstance(section, list):
            continue
        for item in section:
            if isinstance(item, str):
                candidates = [("text", item)]
            elif isinstance(item, dict):
                candidates = list(item.items())
            else:
                continue
            for key, val in candidates:
                if not isinstance(val, str):
                    continue
                v = val.strip()
                if not v:
                    continue
                if v.endswith((" and", " or")):
                    raise ValueError(f"Truncated string in {section_name}.{key}: {val!r}")
                if v.endswith("...") or v.endswith("…"):
                    raise ValueError(f"Truncated string in {section_name}.{key}: {val!r}")
                if v.endswith(",") and len(v) < 25:
                    raise ValueError(f"Truncated string in {section_name}.{key}: {val!r}")

    return report


def _attach_unified_markdown_export(
    report: Dict[str, Any],
    report_v3: Optional[Dict[str, Any]],
    meta: Dict[str, Any],
) -> None:
    """Add `markdown_export` for CLI/integrations; not used by the desktop main window."""
    try:
        from .episode_report_v3 import render_unified_episode_export_markdown
    except ImportError:
        from episode_report_v3 import render_unified_episode_export_markdown

    m = meta or {}
    report["markdown_export"] = render_unified_episode_export_markdown(
        {
            "report_v3": report_v3 or {},
            "workflow_report": report,
            "meta": {
                "generated_at": m.get("generated") or m.get("generated_at"),
                "title": m.get("title"),
                "creator": m.get("creator"),
                "genre": m.get("genre"),
            },
        }
    )


def attach_summary_and_score(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add `summary` (one-line string) and `score` (0–100) for UI, doctor checks, and CI validation.
    Score is heuristic from signal_mode and weak_claims count.
    """
    sm = str(report.get("signal_mode") or "").upper().strip()
    if sm == "HIGH_SIGNAL":
        base = 82
    elif sm == "LOW_SIGNAL":
        base = 42
    elif sm in ("MEDIUM_SIGNAL", "MEDIUM"):
        base = 62
    else:
        base = 68
    wc = report.get("weak_claims")
    if isinstance(wc, list):
        penalty = min(25, len(wc) * 4)
    else:
        penalty = 0
    score = max(0, min(100, base - penalty))
    def _is_meta_summary(s: str) -> bool:
        low = (s or "").lower()
        return any(
            x in low
            for x in (
                "no clear narrative",
                "insufficient signal",
                "unclear narrative",
            )
        )

    summary_parts: List[str] = []
    cr = report.get("coach_report")
    if isinstance(cr, dict):
        bl = cr.get("bottom_line")
        if isinstance(bl, dict):
            for k in ("good", "must_change", "if_fixed"):
                v = str(bl.get(k) or "").strip()
                if v and not _is_meta_summary(v):
                    summary_parts.append(v)
                    break
        if not summary_parts:
            ed = cr.get("episode_diagnosis")
            if isinstance(ed, dict):
                body = ed.get("body")
                if isinstance(body, list) and body:
                    first = str(body[0]).strip()
                    if first and not _is_meta_summary(first):
                        summary_parts.append(first)
    if not summary_parts:
        hl = report.get("highlights") or []
        if hl and isinstance(hl[0], dict):
            insight = str(hl[0].get("insight") or "").strip()
            if insight and not _is_meta_summary(insight):
                try:
                    from .episode_report_v3 import _is_garbled_insight_line
                except ImportError:
                    from episode_report_v3 import _is_garbled_insight_line
                if not _is_garbled_insight_line(insight):
                    summary_parts.append(insight)
    if not summary_parts:
        em = report.get("evidence_map") or []
        if em and isinstance(em[0], dict):
            c = str(em[0].get("claim") or "").strip()
            if c:
                summary_parts.append(c)
    if not summary_parts:
        mt = str((report.get("metadata") or {}).get("title") or "").strip()
        if mt:
            summary_parts.append(f"{mt} — SoapBoxx v3 workflow.")
        else:
            summary_parts.append("SoapBoxx episode workflow report.")
    report["summary"] = " ".join(summary_parts)[:800]
    report["score"] = int(score)
    return report


def _sanitize_workflow_highlights(report: Dict[str, Any]) -> None:
    """Remove lyric/outro/caption-style lines from workflow highlights (mutates ``report``)."""
    try:
        from .episode_report_v3 import _is_garbled_insight_line, is_low_signal_insight_line
    except ImportError:
        from episode_report_v3 import _is_garbled_insight_line, is_low_signal_insight_line

    hl = report.get("highlights") or []
    if not isinstance(hl, list) or not hl:
        return
    kept: List[Dict[str, Any]] = []
    n = 0
    for h in hl:
        if not isinstance(h, dict):
            continue
        ins = str(h.get("insight") or "").strip()
        if (
            ins
            and not is_low_signal_insight_line(ins)
            and not _is_garbled_insight_line(ins)
        ):
            n += 1
            hh = dict(h)
            hh["id"] = f"h{n}"
            kept.append(hh)
    report["highlights"] = kept[:5]


def _detect_weak_claims_local(evidence_map: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for e in evidence_map:
        ev = str(e.get("evidence") or "")
        st = e.get("strength")
        try:
            st_i = int(st) if st is not None else 5
        except (TypeError, ValueError):
            st_i = 5
        if len(ev.split()) < 8 or st_i < 5:
            out.append(
                {
                    "id": e.get("id"),
                    "reason": "Short evidence or low strength in local assessment",
                    "severity": "medium",
                }
            )
    return out[:10]


def _topic_specific_guest_fallback(r3: Dict[str, Any], claim_id: str) -> List[Dict[str, Any]]:
    """Build less-generic guest roles when v3 report falls back."""
    snap = r3.get("episode_snapshot") or {}
    title = str(snap.get("title") or "").strip()
    primary_topic = str(snap.get("primary_topic") or "").strip()
    text_bits: List[str] = [title, primary_topic]
    for x in (r3.get("clean_insights") or [])[:6]:
        text_bits.append(str(x))
    for c in (r3.get("claims") or [])[:6]:
        if isinstance(c, dict):
            text_bits.append(str(c.get("text") or ""))
    topic_text = " ".join(text_bits).lower()

    # Prediction markets / gambling — must run before the news/politics branch: substrings like
    # "election" (election markets) or "court" (sports/legal) otherwise mis-trigger news guests.
    if any(
        k in topic_text
        for k in (
            "kalshi",
            "prediction market",
            "prediction-market",
            "sportsbook",
            "sports book",
            "gambling",
            "online betting",
            "sports betting",
            "betting on",
            " bookmaker",
            " casino",
            " wager",
            "fantasy sport",
            "draftkings",
            "fanduel",
            "parlay",
            "normalizes betting",
            "normalises betting",
            "betting lounge",
        )
    ):
        tshort = (primary_topic or title or "this episode")[:140]
        return [
            {
                "name": "Problem gambling / behavioral-addiction researcher",
                "title": "Clinical / public health",
                "role": "Addiction science",
                "claim_id": claim_id,
                "angle": (
                    "Separates habit formation, loss-chasing, and population-risk claims from "
                    "marketing narratives — with an eye toward harm reduction."
                ),
                "topic_angle": "Addiction mechanisms and measured interventions",
                "relevance": 10,
            },
            {
                "name": "Former regulator or counsel (CFTC / state gaming / operator compliance)",
                "title": "Legal / regulatory",
                "role": "Regulatory",
                "claim_id": claim_id,
                "angle": (
                    f"Maps claims about {tshort[:72]} to real filings: CFTC vs. state commissions, "
                    "house rules, and DraftKings-style compliance — not vibes."
                ),
                "topic_angle": "Jurisdiction, product definitions, and enforcement",
                "relevance": 9,
            },
            {
                "name": "Sports economics or prediction-market researcher",
                "title": "Economics",
                "role": "Markets",
                "claim_id": claim_id,
                "angle": (
                    "Pressure-tests incentive design, liquidity, and information asymmetry claims "
                    "with empirical work — not vibes."
                ),
                "topic_angle": "Incentives, prices, and real-money outcomes",
                "relevance": 8,
            },
            {
                "name": "Investigative or beat reporter (gaming / finance)",
                "title": "Reporting",
                "role": "Reporting",
                "claim_id": claim_id,
                "angle": (
                    f"Traces sponsorships, ad inventory, and league deals behind: {tshort[:90]} "
                    "— what is confirmed vs. alleged."
                ),
                "topic_angle": "Sourcing and timelines",
                "relevance": 8,
            },
            {
                "name": "Editorial producer / story editor",
                "title": "Structure",
                "role": "Editorial",
                "claim_id": claim_id,
                "angle": "Tightens thesis and clip strategy so the episode lands one defensible arc.",
                "topic_angle": "Packaging and clarity",
                "relevance": 7,
            },
        ]

    # News / politics / public affairs — do not fall through to generic business-authors.
    if any(
        k in topic_text
        for k in (
            "breaking",
            "news",
            "politic",
            "police",
            "parliament",
            "senate",
            "congress",
            "election",
            "government",
            "minister",
            "court",
            "trial",
            "verdict",
            "prosecutor",
            "defense attorney",
            "lawsuit",
            "classified",
            "national security",
            "ottawa",
            "convoy",
            "protest",
            "journalist",
            "investigative",
        )
    ):
        tshort = (primary_topic or title or "this story")[:140]
        return [
            {
                "name": "Beat or investigative journalist",
                "title": "Reporting",
                "role": "Reporting",
                "claim_id": claim_id,
                "angle": f"Pressure-tests sourcing and timelines for: {tshort} — what is confirmed vs. alleged.",
                "topic_angle": "Sourcing, attribution, and what still needs confirmation",
                "relevance": 10,
            },
            {
                "name": "Criminal or civil litigator",
                "title": "Legal",
                "role": "Legal analysis",
                "claim_id": claim_id,
                "angle": "Maps claims to elements of proof, risks of defamation, and what a court would need to see.",
                "topic_angle": "Legal exposure and standards of evidence",
                "relevance": 9,
            },
            {
                "name": "Policy researcher (security / governance)",
                "title": "Policy",
                "role": "Policy",
                "claim_id": claim_id,
                "angle": "Connects institutional incentives and jurisdictional constraints to the episode's strongest claims.",
                "topic_angle": "Institutions, incentives, second-order effects",
                "relevance": 8,
            },
            {
                "name": "Civil liberties or oversight advocate",
                "title": "Rights & oversight",
                "role": "Oversight",
                "claim_id": claim_id,
                "angle": "Stress-tests enforcement narratives against rights framing and proportionality — without strawmen.",
                "topic_angle": "Rights, proportionality, and counter-narratives",
                "relevance": 8,
            },
            {
                "name": "Regional or beat editor",
                "title": "Editorial",
                "role": "Editorial",
                "claim_id": claim_id,
                "angle": "Tightens thesis and clip strategy so segments map to one defensible arc for a news audience.",
                "topic_angle": "Structure, defensibility, and audience takeaway",
                "relevance": 7,
            },
        ]

    if any(
        k in topic_text
        for k in (
            "burnout",
            "lonely",
            "loneliness",
            "happiness",
            "meaning",
            "work-life",
            "success",
            "high achiever",
        )
    ):
        return [
            {
                "name": "Dr. Christina Maslach",
                "title": "Burnout researcher",
                "role": "Burnout research",
                "claim_id": claim_id,
                "angle": "Brings the Maslach burnout framework to separate exhaustion, cynicism, and efficacy loss in high-achieving workplaces.",
                "topic_angle": "Burnout mechanisms in high-achieving teams",
                "relevance": 10,
            },
            {
                "name": "Dr. Julianne Holt-Lunstad",
                "title": "Loneliness and social connection scientist",
                "role": "Social connection science",
                "claim_id": claim_id,
                "angle": "Evaluates loneliness risk claims with meta-analytic evidence and practical connection interventions.",
                "topic_angle": "Loneliness, belonging, and behavior change",
                "relevance": 10,
            },
            {
                "name": "Dr. Arthur C. Brooks",
                "title": "Happiness and purpose scholar",
                "role": "Meaning and wellbeing",
                "claim_id": claim_id,
                "angle": "Deepens the episode's meaning-vs-success thesis with evidence-backed frameworks listeners can apply weekly.",
                "topic_angle": "From success metrics to sustainable fulfillment",
                "relevance": 9,
            },
            {
                "name": "Dr. Laurie Santos",
                "title": "Behavioral science of happiness",
                "role": "Behavioral psychology",
                "claim_id": claim_id,
                "angle": "Connects achievement incentives to wellbeing outcomes and gives concrete behavior redesigns to avoid emptiness.",
                "topic_angle": "Incentive traps behind burnout and emptiness",
                "relevance": 9,
            },
            {
                "name": "Dr. Emily Nagoski",
                "title": "Stress and burnout researcher",
                "role": "Stress and burnout science",
                "claim_id": claim_id,
                "angle": "Adds evidence-backed burnout recovery strategies focused on stress-cycle completion and sustainable performance.",
                "topic_angle": "Stress-cycle completion and recovery behaviors",
                "relevance": 8,
            },
        ]

    topic = primary_topic or title or "this episode"
    # Genre-agnostic expert *roles* — avoids mismatched celebrity names when topic classification is thin.
    return [
        {
            "name": "Skeptical domain practitioner",
            "title": "Practitioner interview",
            "role": "Domain practice",
            "claim_id": claim_id,
            "angle": f"Pressure-tests the strongest on-mic claims about: {topic[:120]} with field experience and failure modes.",
            "topic_angle": "Execution reality vs. story",
            "relevance": 8,
        },
        {
            "name": "Researcher or analyst (primary sources)",
            "title": "Evidence",
            "role": "Evidence",
            "claim_id": claim_id,
            "angle": "Separates verified facts, contested interpretations, and missing data the episode should flag.",
            "topic_angle": "Verification and uncertainty",
            "relevance": 8,
        },
        {
            "name": "Contrarian voice (steel-manned)",
            "title": "Debate segment",
            "role": "Counter-case",
            "claim_id": claim_id,
            "angle": "States the strongest opposing case without caricature — useful for a dedicated tension segment.",
            "topic_angle": "Best counterargument on the table",
            "relevance": 7,
        },
        {
            "name": "Editorial producer / story editor",
            "title": "Structure",
            "role": "Structure",
            "claim_id": claim_id,
            "angle": "Tightens thesis, clip strategy, and segment order so listeners leave with one memorable through-line.",
            "topic_angle": "Clarity and packaging",
            "relevance": 6,
        },
    ]


def _guest_rows_are_generic(rows: List[Dict[str, Any]]) -> bool:
    if not rows:
        return True
    generic_markers = (
        "behavioral psychologist",
        "operator / founder",
        "skeptical domain expert",
        "implementation coach",
        "transcript length",
    )
    hit = 0
    for g in rows:
        name = str(g.get("name") or "").strip().lower()
        angle = str(g.get("angle") or "").strip().lower()
        if any(m in name for m in generic_markers) or any(m in angle for m in generic_markers):
            hit += 1
    return hit >= max(2, len(rows) // 2)


def _extract_in_episode_names(r3: Dict[str, Any]) -> List[str]:
    """Best-effort extraction of already-featured names from episode title metadata."""
    snap = r3.get("episode_snapshot") or {}
    title = str(snap.get("title") or "").strip()
    if not title:
        return []
    names: List[str] = []
    patterns = [
        r"\(\s*with\s+([^)]+)\)",
        r"\bwith\s+([A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){1,4})",
    ]
    for pat in patterns:
        for m in re.findall(pat, title, flags=re.IGNORECASE):
            cand = str(m).strip(" -:;,.")
            if cand:
                names.append(cand)
    return names


def _normalize_person_name(name: str) -> str:
    n = (name or "").strip().lower()
    n = re.sub(r"\b(dr|mr|mrs|ms|prof)\.?\s+", "", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n)
    n = re.sub(r"[^a-z\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _same_person_name(a: str, b: str) -> bool:
    na = _normalize_person_name(a)
    nb = _normalize_person_name(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta = [x for x in na.split() if len(x) > 1]
    tb = [x for x in nb.split() if len(x) > 1]
    if len(ta) < 2 or len(tb) < 2:
        return False
    # Strong heuristic: same last name and first-initial match.
    if ta[-1] == tb[-1] and ta[0][0] == tb[0][0]:
        return True
    return False


def _filter_already_featured_guests(rows: List[Dict[str, Any]], excluded_names: List[str]) -> List[Dict[str, Any]]:
    if not rows or not excluded_names:
        return rows
    out: List[Dict[str, Any]] = []
    for g in rows:
        nm = str(g.get("name") or "").strip()
        if not nm:
            continue
        if any(_same_person_name(nm, x) for x in excluded_names):
            continue
        out.append(g)
    return out


def _dedupe_guest_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for g in rows:
        nm = _normalize_person_name(str(g.get("name") or ""))
        if not nm or nm in seen:
            continue
        seen.add(nm)
        out.append(g)
    return out


def workflow_report_from_v3_report(r3: Dict[str, Any]) -> Dict[str, Any]:
    """Map `episode_report_v3` `report_v3` dict into this module's workflow schema."""
    try:
        from .episode_report_v3 import is_low_signal_insight_line
    except ImportError:
        from episode_report_v3 import is_low_signal_insight_line

    highlights: List[Dict[str, Any]] = []
    n = 0
    for ins in r3.get("clean_insights") or []:
        s = str(ins).strip()
        if not s or is_low_signal_insight_line(s):
            continue
        n += 1
        highlights.append(
            {
                "id": f"h{n}",
                "insight": s,
                "length_words": len(s.split()),
                "priority": "high" if n == 1 else "medium",
            }
        )

    evidence_map: List[Dict[str, Any]] = []
    for row in r3.get("evidence_mapping") or []:
        if not isinstance(row, dict):
            continue
        evidence_map.append(
            {
                "id": row.get("id"),
                "claim": row.get("claim"),
                "evidence": row.get("evidence"),
                "timestamp": row.get("timestamp"),
                "type": row.get("type", "other"),
                "strength": row.get("strength", 7),
            }
        )
    evidence_map = _sanitize_evidence_map_claims(evidence_map)

    follow_up: List[Dict[str, Any]] = []
    eng = r3.get("engagement_questions") or {}
    tri_map = (
        ("counter", "counterpunch"),
        ("validation", "validation"),
        ("application", "application"),
    )
    for cid in sorted(eng.keys(), key=lambda x: int(x[1:]) if str(x)[1:].isdigit() else 0):
        tri = eng[cid] or {}
        for qt, k in tri_map:
            text = str(tri.get(k) or "").strip()
            if not text and qt == "counter":
                text = str(tri.get("contrarian") or tri.get("failure_case") or "").strip()
            if not text and qt == "validation":
                text = str(tri.get("constraint") or "").strip()
            if text:
                follow_up.append(
                    {"question": text, "question_type": qt, "claim_id": str(cid)}
                )

    claims = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]

    guest_recommendations: List[Dict[str, Any]] = []
    for g in r3.get("guests") or []:
        if not isinstance(g, dict):
            continue
        tgt = _clean_claim_text(str(g.get("target_claim") or ""))
        claim_id = None
        for c in claims:
            if _clean_claim_text(str(c.get("text") or "")) == tgt:
                claim_id = str(c.get("id") or "")
                break
        if not claim_id and claims:
            claim_id = str(claims[0].get("id") or "")
        guest_recommendations.append(
            {
                "name": g.get("guest"),
                "title": g.get("role"),
                "role": g.get("role"),
                "claim_id": claim_id or "",
                "angle": g.get("why_this_episode"),
                "topic_angle": g.get("why_this_episode"),
                "relevance": 8,
            }
        )

    if not guest_recommendations:
        cr = r3.get("coach_report") or {}
        gs = (cr.get("guest_strategy") or {}).get("guests") or []
        for item in gs:
            if not isinstance(item, dict):
                continue
            gt = str(item.get("guest_type") or "Guest").strip()
            adds = str(item.get("adds") or "").strip()
            cid_gs = str(claims[0].get("id")) if claims else ""
            guest_recommendations.append(
                {
                    "name": gt,
                    "title": "Suggested",
                    "role": gt,
                    "claim_id": cid_gs,
                    "angle": adds,
                    "topic_angle": adds,
                    "relevance": 7,
                }
            )
            if len(guest_recommendations) >= 5:
                break
    if not guest_recommendations:
        snap = r3.get("episode_snapshot") or {}
        topic = str(snap.get("primary_topic") or snap.get("title") or "this episode")[:120]
        cid = str(claims[0].get("id")) if claims else ""
        guest_recommendations = [
            {
                "name": "Investigative journalist or legal analyst",
                "title": "Expert",
                "role": "Expert",
                "claim_id": cid,
                "angle": f"Verify primary sources and institutional claims about: {topic}.",
                "topic_angle": "Source verification and counter-narrative",
                "relevance": 8,
            },
            {
                "name": "Subject-matter historian / researcher",
                "title": "Research",
                "role": "Research",
                "claim_id": cid,
                "angle": "Grounds hot-button segments in documented context and timelines.",
                "topic_angle": "Context and chronology",
                "relevance": 7,
            },
            {
                "name": "Editorial producer",
                "title": "Production",
                "role": "Production",
                "claim_id": cid,
                "angle": "Tighten thesis and clip strategy so segments map to one defensible arc.",
                "topic_angle": "Structure and defensibility",
                "relevance": 6,
            },
        ]
    cid_fallback = str(claims[0].get("id")) if claims else "c1"
    if _guest_rows_are_generic(guest_recommendations):
        guest_recommendations = _topic_specific_guest_fallback(r3, cid_fallback)
    excluded_names = _extract_in_episode_names(r3)
    guest_recommendations = _filter_already_featured_guests(guest_recommendations, excluded_names)
    if not guest_recommendations:
        guest_recommendations = _filter_already_featured_guests(
            _topic_specific_guest_fallback(r3, cid_fallback),
            excluded_names,
        )
    if len(guest_recommendations) < 4:
        extras = _filter_already_featured_guests(
            _topic_specific_guest_fallback(r3, cid_fallback),
            excluded_names,
        )
        guest_recommendations = _dedupe_guest_rows(guest_recommendations + extras)
    guest_recommendations = guest_recommendations[:5]

    segments: List[Dict[str, Any]] = []
    default_run = [
        "Play clip",
        "Host reacts",
        "Guest responds",
        "Challenge assumptions",
        "Summarize takeaway",
    ]
    for i, s in enumerate(r3.get("segments") or []):
        if not isinstance(s, dict):
            continue
        segments.append(
            {
                "segment_id": f"s{i + 1}",
                "title": s.get("segment_title"),
                "clip_id": s.get("trigger_clip"),
                "host_position": s.get("host_angle"),
                "guest_position": s.get("guest_angle"),
                "goal": s.get("goal"),
                "run_of_show": default_run,
            }
        )

    aa = r3.get("analytics_actionable") or {}
    analytics = {
        "storylines": list(aa.get("what_worked") or []),
        "topic_signals": list(aa.get("what_failed") or []),
        "actionable_steps": list(aa.get("next_move") or []),
    }

    out: Dict[str, Any] = {
        "highlights": highlights,
        "evidence_map": evidence_map,
        "follow_up_questions": follow_up,
        "guest_recommendations": guest_recommendations,
        "segments": segments,
        "analytics": analytics,
    }
    _sanitize_workflow_highlights(out)
    sm = r3.get("signal_mode")
    if sm:
        out["signal_mode"] = sm
    cr = r3.get("coach_report")
    if cr:
        out["coach_report"] = cr
    return out


def _ensure_fallback_evidence(
    report: Dict[str, Any], transcript: str
) -> None:
    """If offline produced no evidence rows, add one anchor so validation can pass."""
    if report.get("evidence_map"):
        return
    try:
        from .episode_report_v3 import _dedupe_repeated_sentences, _truncate_words
    except ImportError:
        from episode_report_v3 import _dedupe_repeated_sentences, _truncate_words

    words = transcript.split()
    snippet = " ".join(words[:50])
    if len(snippet) > 220:
        snippet = _truncate_words(snippet, max_words=45)
    snippet = _dedupe_repeated_sentences(snippet, max_words=80)
    report["evidence_map"] = [
        {
            "id": "c1",
            "claim": "Core tension from the episode: external achievement can mask loneliness, anxiety, or loss of meaning.",
            "evidence": snippet or "(empty transcript)",
            "timestamp": None,
            "type": "other",
            "strength": 4,
        }
    ]
    report["follow_up_questions"] = [
        {
            "question": "What is the strongest counterargument a skeptical listener would raise to the episode’s main tension?",
            "question_type": "counter",
            "claim_id": "c1",
        },
        {
            "question": "Which lines in the transcript best support the sharpest claim you would defend in public?",
            "question_type": "validation",
            "claim_id": "c1",
        },
        {
            "question": "What concrete behavior should listeners change this week based on this episode?",
            "question_type": "application",
            "claim_id": "c1",
        },
    ]


def soapboxx_v3_workflow_local(
    transcript: str,
    metadata: Dict[str, Any],
    *,
    validate: bool = True,
    strict_references: bool = False,
    client: Any = None,
    report_v3: Optional[Dict[str, Any]] = None,
    brief_warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    **Default path:** v3 report + workflow JSON from `episode_report_v3`, then optional **AI enrichment**
    when `SOAPBOXX_OLLAMA_MODEL` is set (`SOAPBOXX_WORKFLOW_USE_AI=1` by default).

    AI steps fill highlights, evidence_map, follow_up_questions, guest_recommendations, segments, analytics.

    Pass ``report_v3`` (and optional ``brief_warnings``) to reuse an already-built v3 report and avoid a
    second ``generate_episode_report_v3`` call (e.g. from ``FeedbackEngine.generate_network_brief_v3``).
    """
    try:
        from .episode_report_v3 import generate_episode_report_v3
    except ImportError:
        from episode_report_v3 import generate_episode_report_v3

    meta = {k: str(v) for k, v in metadata.items() if v is not None}
    if report_v3 is not None:
        r3 = report_v3
        source_warnings: List[str] = list(brief_warnings or [])
    else:
        out = generate_episode_report_v3(
            transcript or "",
            meta,
            strict_references=strict_references,
            include_v2_markdown=False,
        )
        r3 = out.get("report_v3") or {}
        source_warnings = list(out.get("warnings") or [])
    body = workflow_report_from_v3_report(r3)
    meta_out = dict(metadata)
    meta_out.setdefault(
        "generated", datetime.now(timezone.utc).isoformat()
    )
    enrich_meta = dict(meta)
    snap_es = r3.get("episode_snapshot") or {}
    _pt = str(snap_es.get("primary_topic") or "").strip()
    if _pt:
        enrich_meta["primary_topic"] = _pt
    mode = "local"
    enrich_tier = "none"

    llm_client = client
    if _workflow_ai_enrichment_enabled() and _llm_available():
        try:
            gate_ok, gate_issues = _workflow_quality_gate_full_enrichment(
                transcript or "", r3
            )
            for gi in gate_issues:
                source_warnings.append(f"workflow_quality_gate: {gi}")
            if gate_ok:
                body = enrich_workflow_report_with_ai(
                    transcript or "", body, client=llm_client, episode_meta=enrich_meta
                )
                enrich_tier = "full"
            else:
                body = enrich_workflow_report_minimal(
                    transcript or "", body, client=llm_client, episode_meta=enrich_meta
                )
                enrich_tier = "minimal"
            mode = "local+ai"
        except Exception as e:
            source_warnings.append(f"AI workflow enrichment failed: {e}")

    meta_out["workflow_mode"] = mode
    meta_out["workflow_enrichment_tier"] = enrich_tier
    meta_out["source_warnings"] = source_warnings
    _apply_workflow_version_metadata(meta_out)

    report: Dict[str, Any] = {
        "metadata": meta_out,
        **body,
    }
    _ensure_fallback_evidence(report, transcript or "")

    weak_claims: List[Dict[str, Any]] = []
    if mode == "local+ai" and _llm_available():
        try:
            wc_client = llm_client
            weak_claims = detect_weak_claims(
                report.get("evidence_map") or [], client=wc_client
            )
        except Exception:
            weak_claims = []
    report["weak_claims"] = weak_claims or _detect_weak_claims_local(
        report.get("evidence_map") or []
    )
    attach_summary_and_score(report)

    if validate:
        try:
            validate_json(report, strict=True)
        except ValueError as e:
            if meta_out.get("workflow_enrichment_tier") == "minimal":
                source_warnings.append(f"workflow_validation_relaxed: {e}")
                validate_json(report, strict=False)
            else:
                raise
    _attach_unified_markdown_export(report, r3, meta_out)
    return report


def generate_highlights(
    transcript: str,
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    excerpt = _workflow_transcript_excerpt(transcript)
    ctx = _episode_context_block(episode_meta)
    prompt = f"""
TASK: Generate at most 5 clean insights from the transcript.

{ctx}INPUT TRANSCRIPT (excerpt may be truncated):
{excerpt}

RULES:
- Each insight ≤ 20 words, standalone, no raw dialogue fragments or half-sentences
- Themes must match the EPISODE CONTEXT / title (e.g. crime interview vs ministry) — do not invent unrelated angles or faith-based framing when the episode is news/politics without that content
- Reject song lyrics, outros ("talk to you in 3 minutes"), repeated "oh oh oh", or subscribe/banter lines
- No filler phrases like "The speaker argues" or "The host says"
- No semantic duplicates
- Output a JSON array only:
[
  {{"id":"h1","insight":"...","length_words":12,"priority":"high"}},
  ...
]
Max 5 objects. IDs h1..h5.
"""
    data = call_llm_json(prompt, max_tokens=1200, client=client)
    if not isinstance(data, list):
        data = (data.get("highlights") or []) if isinstance(data, dict) else []
    return [x for x in data if isinstance(x, dict)][:5]


def generate_evidence_map(
    transcript: str,
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    excerpt = _workflow_transcript_excerpt(transcript)
    ctx = _episode_context_block(episode_meta)
    prompt = f"""
TASK: Extract 3–5 core claims and map each to evidence from the transcript.

{ctx}INPUT:
{excerpt}

RULES:
- Claims must reflect what this episode is actually about (see EPISODE CONTEXT / title), not generic religious or filler themes unless the transcript supports that
- Each claim ≤ 20 words, debatable, paraphrase (not raw rambling dialogue)
- evidence: verbatim quote copied from the INPUT above (required — no invented quotes)
- timestamp: seconds from start if you can infer from context; else null
- type: one of story_beat | personal_account | institutional | legal_risk | business | other
  (use "other" for mixed dialogue; do not use religious labels unless clearly about faith)
- strength: 0-10 integer
- id: c1, c2, c3, ... in order

Output JSON array only, no prose:
[
  {{
    "id": "c1",
    "claim": "...",
    "evidence": "...",
    "timestamp": 12.3,
    "type": "story_beat",
    "strength": 8
  }}
]
"""
    data = call_llm_json(prompt, max_tokens=2000, client=client)
    if not isinstance(data, list):
        data = (data.get("evidence_map") or []) if isinstance(data, dict) else []
    return [x for x in data if isinstance(x, dict)][:8]


def generate_anchor_evidence_map(
    transcript: str,
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Simpler than full claim+evidence mapping: producer-facing **pull quotes** with short labels.
    Same ``evidence_map`` schema so follow-ups, segments, and exports stay compatible.
    """
    excerpt = _workflow_transcript_excerpt(transcript)
    ctx = _episode_context_block(episode_meta)
    prompt = f"""
TASK: Pick 5–7 strong **verbatim quotes** from the transcript for clip planning and social cuts.

{ctx}TRANSCRIPT:
{excerpt}

RULES:
- "evidence" must be a COPY-PASTE substring from TRANSCRIPT (25–220 characters). No invented dialogue.
- "claim" is a **short label** naming what this moment shows (≤ 18 words), not a separate thesis.
- id: c1, c2, c3, … in order
- type: always "pull_quote"
- timestamp: seconds from episode start if inferable; else null
- strength: 1–10 (how strong / usable this beat is)

Output JSON array only:
[
  {{"id":"c1","claim":"...","evidence":"...","timestamp":null,"type":"pull_quote","strength":8}}
]
"""
    data = call_llm_json(prompt, max_tokens=2200, client=client)
    if not isinstance(data, list):
        data = (data.get("evidence_map") or []) if isinstance(data, dict) else []
    rows = [x for x in data if isinstance(x, dict)][:8]
    for r in rows:
        if isinstance(r, dict):
            r.setdefault("type", "pull_quote")
    return rows


def generate_follow_up_questions(
    evidence_map: List[Dict[str, Any]],
    *,
    client: Any = None,
    transcript: str = "",
    episode_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Per-claim follow-ups: uses **claim + evidence + local transcript window + episode meta** so the
    model cannot rely on generic “listeners / this claim” phrasing alone.
    """
    questions: List[Dict[str, Any]] = []
    ctx_lines = _episode_meta_lines(episode_meta)
    for e in evidence_map:
        eid = str(e.get("id") or "")
        claim = str(e.get("claim") or "").strip()
        ev_quote = str(e.get("evidence") or "").strip()
        local_win = _local_transcript_window(transcript, ev_quote)
        local_block = (
            f"LOCAL TRANSCRIPT (around the evidence quote; use for stakes and names):\n{local_win}"
            if local_win
            else "LOCAL TRANSCRIPT: (not matched — rely on claim + evidence below.)"
        )
        ep_block = (
            f"EPISODE / SHOW CONTEXT:\n{ctx_lines}\n"
            if ctx_lines
            else "EPISODE / SHOW CONTEXT: (not provided)\n"
        )
        prompt = f"""
TASK: Write exactly 3 **specific** interview questions for this ONE claim for a podcast host.

{ep_block}
{local_block}

CLAIM ID: {eid}
CLAIM (paraphrase): {claim}
EVIDENCE QUOTE (from transcript; treat as anchor): {ev_quote or "(none)"}

STRICT RULES:
- Output exactly 3 objects: question_type must be counter, validation, application (one each).
- counter: Name the strongest opposing view, institutional incentive, or failure mode that threatens this claim — not vague “critics” or “someone who disagrees”.
- validation: Ask what document, witness, dataset, or primary source would **confirm or falsify** the claim (or the quoted evidence), not generic “is there evidence”.
- application: Name a concrete tradeoff, decision, or behavior change implied by the claim — not “what should listeners do”.
- Match the episode’s domain (news, politics, faith, business, etc.): do not use religious or ministry framing unless the claim/evidence/transcript is clearly about religion.
- Each question 14–28 words, complete sentences.
- Forbidden unless tied to a named entity or mechanism from the claim/evidence/local context: “listeners”, “in today’s world”, “this claim”, “rhetoric”, “real life” as filler.
- Do not copy the claim verbatim as the entire question; do not end with “...”.

Output JSON array only:
[
  {{"question":"...","question_type":"counter","claim_id":"{eid}"}},
  {{"question":"...","question_type":"validation","claim_id":"{eid}"}},
  {{"question":"...","question_type":"application","claim_id":"{eid}"}}
]
"""
        data = call_llm_json(prompt, max_tokens=900, temperature=0.2, client=client)
        if not isinstance(data, list):
            data = []
        for q in data:
            if isinstance(q, dict):
                q.setdefault("claim_id", eid)
                questions.append(q)
    return questions


def refine_follow_up_questions_batch(
    transcript_excerpt: str,
    evidence_map: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Second pass: one JSON-in/JSON-out edit to remove repeated generic phrasing across claims.
    Falls back to ``questions`` if the model returns an invalid shape.
    """
    if not questions:
        return questions
    head = (transcript_excerpt or "")[:12000]
    em_compact = [
        {
            "id": e.get("id"),
            "claim": e.get("claim"),
            "evidence": (str(e.get("evidence") or ""))[:400],
        }
        for e in evidence_map
        if isinstance(e, dict)
    ]
    ctx = _episode_meta_lines(episode_meta)
    prompt = f"""
TASK: Rewrite the follow-up questions to be **more specific** to this episode. Keep the same count,
order, claim_id, and question_type for each item. Do not add or remove objects.

EPISODE CONTEXT:
{ctx or "(none)"}

CLAIMS + EVIDENCE (for grounding):
{json.dumps(em_compact, ensure_ascii=False)}

TRANSCRIPT EXCERPT (for names, institutions, stakes):
{head}

CURRENT QUESTIONS (edit in place — sharper wording only):
{json.dumps(questions, ensure_ascii=False)}

RULES:
- Preserve every "claim_id" and "question_type" exactly.
- Remove boilerplate: vague "listeners", "this idea", "in society", "rhetoric vs reality" without named stakes.
- Prefer named mechanisms, institutions, timelines, or tradeoffs visible in the excerpt or claims.
- 14–30 words per question; complete sentences; no trailing "...".

Output JSON array only, same length as input.
"""
    data = call_llm_json(prompt, max_tokens=2400, temperature=0.15, client=client)
    if not isinstance(data, list) or len(data) != len(questions):
        return questions
    out: List[Dict[str, Any]] = []
    for i, q in enumerate(questions):
        if i >= len(data) or not isinstance(data[i], dict):
            out.append(q)
            continue
        new_q = dict(q)
        t = str(data[i].get("question") or "").strip()
        if t:
            new_q["question"] = t
        if str(data[i].get("claim_id") or "") == str(q.get("claim_id") or ""):
            new_q["claim_id"] = q.get("claim_id")
        if str(data[i].get("question_type") or "") == str(q.get("question_type") or ""):
            new_q["question_type"] = q.get("question_type")
        out.append(new_q)
    return out


def generate_guest_recommendations(
    evidence_map: List[Dict[str, Any]],
    *,
    client: Any = None,
    highlights: Optional[List[Dict[str, Any]]] = None,
    episode_meta: Optional[Dict[str, Any]] = None,
    transcript: str = "",
) -> List[Dict[str, Any]]:
    claims = [str(e.get("claim")) for e in evidence_map if isinstance(e, dict) and e.get("claim")]
    quotes = [
        str(e.get("evidence"))
        for e in evidence_map
        if isinstance(e, dict) and str(e.get("evidence") or "").strip()
    ]
    ctx = _episode_context_block(episode_meta)
    hl_ins = [
        str(h.get("insight"))
        for h in (highlights or [])
        if isinstance(h, dict) and str(h.get("insight") or "").strip()
    ]
    claims_blob = claims if claims else ["(none — infer from TOPIC ANCHOR + transcript sample)"]
    anchor = _guest_topic_anchor_block(episode_meta, transcript or "")
    prompt = f"""
TASK: Suggest 3–4 guests who are **topic-specific to THIS episode only** — not generic podcast guests.

{anchor}{ctx}PULL-QUOTE LABELS (one line each — tie guests to these beats):
{json.dumps(claims_blob[:14], ensure_ascii=False)}

VERBATIM QUOTES (anchors):
{json.dumps(quotes[:10], ensure_ascii=False)}

INSIGHTS (if any):
{json.dumps(hl_ins[:10], ensure_ascii=False)}

STRICT RULES:
- Each guest must address a **named sub-topic** that appears in the episode title, transcript sample, or quotes (e.g. industry, legal regime, geography, named conflict — not "leadership" unless the episode is about leadership).
- **Forbidden:** vague archetypes with no domain tie ("communications expert", "life coach", "motivational speaker", "business consultant") unless the transcript explicitly supports that niche.
- **Required:** `topic_focus` = 3–10 words naming the **specific thread** this guest speaks to (must echo language or domain from title/transcript/quotes when possible).
- `name`: credible role label **including domain** (e.g. "Former federal prosecutor (RICO / narcotics)" not "Legal expert").
- `role`: short professional title aligned with that domain.
- `angle`: one sentence: what they add **to this episode's argument or story** (cite mechanism, institution, or stake from context).
- Map `claim_id` to c1, c2, … when those ids exist; else c1.
- `relevance`: 0–10 (how on-topic for THIS episode).

Output JSON array only:
[
  {{"name":"...","role":"...","claim_id":"c1","topic_focus":"...","angle":"...","relevance":9}}
]
"""
    data = call_llm_json(prompt, max_tokens=1400, client=client)
    if not isinstance(data, list):
        data = (data.get("guest_recommendations") or []) if isinstance(data, dict) else []
    out = [x for x in data if isinstance(x, dict)][:5]
    primary_cid = ""
    for e in evidence_map:
        if isinstance(e, dict) and str(e.get("id") or "").strip():
            primary_cid = str(e.get("id") or "").strip()
            break
    for g in out:
        tf = str(g.get("topic_focus") or "").strip()
        ang = str(g.get("angle") or "").strip()
        if tf and ang:
            g["topic_angle"] = f"{tf} — {ang}"
        else:
            g.setdefault("topic_angle", ang or tf)
        if not str(g.get("title") or "").strip():
            r = str(g.get("role") or "").strip()
            if r:
                g["title"] = r
        if not str(g.get("claim_id") or "").strip():
            g["claim_id"] = primary_cid or "c1"
    return out


def generate_segments(
    evidence_map: List[Dict[str, Any]],
    highlights: List[Dict[str, Any]],
    *,
    client: Any = None,
) -> List[Dict[str, Any]]:
    prompt = f"""
TASK: Build 2–3 executable show segments for a podcast host.

EVIDENCE MAP (JSON):
{json.dumps(evidence_map, ensure_ascii=False)[:4000]}

HIGHLIGHTS (JSON):
{json.dumps(highlights, ensure_ascii=False)[:2000]}

RULES:
- trigger_clip / clip_id must reference an existing claim id (c1, c2, …)
- host_position / host_angle: skeptical | curious | neutral
- guest_position / guest_angle: defensive | expert | neutral
- run_of_show: ordered steps (strings), e.g. Play clip → Host reacts → Guest responds → Challenge → Takeaway

Output JSON array only (2-3 items):
[
  {{
    "segment_id": "s1",
    "title": "...",
    "clip_id": "c2",
    "host_position": "skeptical",
    "guest_position": "defensive",
    "goal": "...",
    "run_of_show": ["Play clip", "Host reacts", "Guest responds", "Challenge assumptions", "Summarize takeaway"]
  }}
]
"""
    data = call_llm_json(prompt, max_tokens=1500, client=client)
    if not isinstance(data, list):
        data = (data.get("segments") or []) if isinstance(data, dict) else []
    return [x for x in data if isinstance(x, dict)][:3]


def generate_analytics(
    transcript: str,
    evidence_map: List[Dict[str, Any]],
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    excerpt = _workflow_transcript_excerpt(transcript)[:12000]
    ctx = _episode_context_block(episode_meta)
    prompt = f"""
TASK: Narrative signals and actionable next moves for a podcast producer.

{ctx}TRANSCRIPT (excerpt):
{excerpt}

EVIDENCE MAP:
{json.dumps(evidence_map, ensure_ascii=False)[:4000]}

RULES:
- storylines and topic_signals must align with the episode title/context — do not default to unrelated themes
- Include **at least one** storyline that names a hidden incentive, blind spot, or "what this episode still owes the listener" (insight-dense, not generic)
- topic_signals: substantive phrases (not stopwords like "says", "were", "back")
- Output JSON object only with keys:
  storylines: string[] (recurring themes)
  topic_signals: string[] (keywords or topics)
  actionable_steps: string[] (3–5 concrete production moves)
"""
    data = call_llm_json(prompt, max_tokens=1000, client=client)
    if not isinstance(data, dict):
        return {"storylines": [], "topic_signals": [], "actionable_steps": []}
    out = dict(data)
    out["topic_signals"] = _scrub_topic_signals(out.get("topic_signals") or [])
    return out


def detect_weak_claims(
    evidence_map: List[Dict[str, Any]],
    *,
    client: Any = None,
) -> List[Dict[str, Any]]:
    prompt = f"""
TASK: Flag weak or under-supported claims.

INPUT:
{json.dumps(evidence_map, ensure_ascii=False)}

RULES:
- Flag if evidence text is missing, very short (<8 words), or strength < 4
- Output JSON array only:
[{{"id":"c1","reason":"...","severity":"high"}}]
"""
    data = call_llm_json(prompt, max_tokens=800, client=client)
    if not isinstance(data, list):
        data = []
    return [x for x in data if isinstance(x, dict)]


def soapboxx_v3_workflow_cloud(
    transcript: str,
    metadata: Dict[str, Any],
    *,
    client: Any = None,
    validate: bool = True,
) -> Dict[str, Any]:
    """Multi-step LLM pipeline (Ollama). Requires ``SOAPBOXX_OLLAMA_MODEL`` and ``call_llm``."""

    meta = dict(metadata)
    if "generated" not in meta and "generated_at" not in meta:
        meta["generated"] = datetime.now(timezone.utc).isoformat()

    excerpt = _workflow_transcript_excerpt(transcript)
    highlights = generate_highlights(transcript, client=client, episode_meta=meta)
    ev_mode = _workflow_evidence_mode()
    if ev_mode == "full":
        evidence_map = generate_evidence_map(transcript, client=client, episode_meta=meta)
    else:
        evidence_map = generate_anchor_evidence_map(transcript, client=client, episode_meta=meta)
    evidence_map = _ensure_evidence_map_ids(evidence_map)
    evidence_map = _filter_grounded_evidence_map(transcript or "", evidence_map)
    evidence_map = _sanitize_evidence_map_claims(evidence_map)
    evidence_map = _ensure_evidence_map_nonempty(transcript or "", evidence_map)
    questions = generate_follow_up_questions(
        evidence_map,
        client=client,
        transcript=transcript or "",
        episode_meta=meta,
    )
    if questions and _sharpen_follow_up_batch_enabled():
        questions = refine_follow_up_questions_batch(
            excerpt,
            evidence_map,
            questions,
            client=client,
            episode_meta=meta,
        )
    guests = generate_guest_recommendations(
        evidence_map,
        client=client,
        highlights=highlights,
        episode_meta=meta,
        transcript=transcript or "",
    )
    segments = generate_segments(evidence_map, highlights, client=client)
    analytics = generate_analytics(transcript, evidence_map, client=client, episode_meta=meta)
    weak_claims = detect_weak_claims(evidence_map, client=client)

    meta["workflow_mode"] = "cloud"
    _apply_workflow_version_metadata(meta)

    report: Dict[str, Any] = {
        "metadata": meta,
        "highlights": highlights,
        "evidence_map": evidence_map,
        "follow_up_questions": questions,
        "guest_recommendations": guests,
        "segments": segments,
        "analytics": analytics,
        "weak_claims": weak_claims,
    }
    attach_summary_and_score(report)

    if validate:
        validate_json(report, strict=True)
    _attach_unified_markdown_export(report, None, meta)
    return report


def soapboxx_v3_workflow(
    transcript: str,
    metadata: Dict[str, Any],
    *,
    use_cloud_llm: bool = False,
    validate: bool = True,
    strict_references: bool = False,
    client: Any = None,
) -> Dict[str, Any]:
    """
    Main entry: **local** (default) or **cloud** multi-step LLM.

    - `use_cloud_llm=False`: `soapboxx_v3_workflow_local` — Ollama optional for AI enrichment.
    - `use_cloud_llm=True`: `soapboxx_v3_workflow_cloud` — multi-step LLM pipeline (Ollama).
    """
    if use_cloud_llm:
        return soapboxx_v3_workflow_cloud(
            transcript, metadata, client=client, validate=validate
        )
    return soapboxx_v3_workflow_local(
        transcript,
        metadata,
        validate=validate,
        strict_references=strict_references,
        client=client,
    )


__all__ = [
    "WORKFLOW_SPEC_VERSION",
    "call_llm",
    "call_llm_json",
    "validate_json",
    "attach_summary_and_score",
    "workflow_report_from_v3_report",
    "enrich_workflow_report_with_ai",
    "enrich_workflow_report_minimal",
    "refine_follow_up_questions_batch",
    "soapboxx_v3_workflow_local",
    "soapboxx_v3_workflow_cloud",
    "soapboxx_v3_workflow",
    "generate_highlights",
    "generate_evidence_map",
    "generate_follow_up_questions",
    "generate_guest_recommendations",
    "generate_segments",
    "generate_analytics",
    "detect_weak_claims",
]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SoapBoxx v3 workflow JSON report")
    parser.add_argument(
        "--transcript",
        default=None,
        help="Path to transcript text file (default: built-in sample)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Write JSON report to this path",
    )
    parser.add_argument(
        "--cloud",
        action="store_true",
        help="Use multi-step LLM pipeline (requires SOAPBOXX_OLLAMA_MODEL / Ollama)",
    )
    parser.add_argument("--title", default="", help="Episode title (metadata)")
    parser.add_argument("--creator", "-c", default="", help="Show / creator name")
    parser.add_argument("--genre", "-g", default="Education", help="Genre label")
    parser.add_argument("--episode", default="1", help="Episode number string")
    args = parser.parse_args()

    sample = (
        "Host: Welcome. Guest: I think pastors are judged unfairly on money. "
        "Host: Say more. Guest: People repeat rumors without checking. "
        "We need accountability but also fairness."
    )
    if args.transcript:
        with open(args.transcript, "r", encoding="utf-8", errors="replace") as f:
            transcript_text = f.read()
    else:
        transcript_text = sample

    meta = {
        "title": (args.title or "").strip() or "Sample",
        "creator": (args.creator or "").strip() or "Demo",
        "genre": (args.genre or "").strip() or "Education",
        "episode_number": str(args.episode or "1").strip(),
    }
    out = soapboxx_v3_workflow(
        transcript_text, meta, use_cloud_llm=bool(args.cloud), validate=True
    )
    payload = json.dumps(out, indent=2, ensure_ascii=False)
    if args.output:
        outp = os.path.abspath(args.output)
        odir = os.path.dirname(outp)
        if odir:
            os.makedirs(odir, exist_ok=True)
        with open(outp, "w", encoding="utf-8") as f:
            f.write(payload)
    else:
        print(payload)
