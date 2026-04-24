# backend/soapboxx_v3_workflow.py
"""
**Primary** structured workflow JSON for SoapBoxx (spec version 3): highlights → evidence →
follow-ups → guests → segments → analytics. This module is the workflow layer — not the PyQt app.

**Default (`soapboxx_v3_workflow_local`):** builds the coach-style `report_v3` via
`episode_report_v3.generate_episode_report_v3`, maps it to workflow JSON, then — when an LLM is
available — **runs multi-step AI extraction** to fill highlights, evidence_map, follow-ups,
guests, segments, and analytics (`metadata.workflow_mode` = ``local+ai``).

**Structured intelligence contract:** the v3 report’s canonical claims / graph-backed guests come from
`atomic_pipeline.run_atomic_pipeline` when atomic ground truth is enabled (default in
`episode_report_v3.build_v3_report`). The workflow layer formats and enriches; it does not replace
that structured core. Set ``SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=0`` only for legacy or tests.

When the v3 report is atomic-backed, **AI enrichment does not overwrite** ``evidence_map`` or
canonical ``guests`` (legacy alias ``guest_recommendations`` — see ``_atomic_structure_lock_from_report_v3``); follow-ups are filtered to
existing evidence ids or reverted to the v3-derived baseline. ``metadata.atomic_structure_lock_applied``
is set after a successful enrich pass when that lock was active.

- ``metadata.workflow_spec_version`` is always ``WORKFLOW_SPEC_VERSION`` (``"3"``); ``primary_episode_workflow`` is ``True``.
- Set ``SOAPBOXX_WORKFLOW_USE_AI=0`` to skip AI and keep deterministic mapping only (`local`).
- Transcript window: ``SOAPBOXX_WORKFLOW_MAX_WORDS`` defaults to **500_000** (~7 chars/word cap toward the hard character ceiling). Set ``SOAPBOXX_WORKFLOW_MAX_WORDS=0`` to use only ``SOAPBOXX_WORKFLOW_MAX_CHARS`` (default 3_000_000). Hard ceiling 3_500_000 characters.
- Evidence style: ``SOAPBOXX_WORKFLOW_EVIDENCE_MODE`` = ``anchors`` (default, verbatim pull quotes + short labels), ``full`` (claim+evidence pairs), or ``v3`` (keep coach ``report_v3`` mapping only, no LLM evidence pass).
- Each successful run adds ``markdown_export`` (unified numbered markdown) to the workflow JSON for scripts/CI — not wired to the PyQt main window.
- Follow-up questions (when AI is on) use **claim + evidence + local transcript window + episode meta**, plus an optional second **batch sharpen** pass. Set ``SOAPBOXX_WORKFLOW_SHARPEN_FU=0`` to disable only the sharpen pass (saves one LLM call).
- **Quality gate:** if the transcript is below ``SOAPBOXX_WORKFLOW_MIN_WORDS`` (default 200), or line-level uniqueness falls below ``SOAPBOXX_WORKFLOW_MIN_LINE_UNIQUENESS`` (default 0.22), multi-step enrichment is skipped in favor of **one** ``enrich_workflow_report_minimal`` call. Set ``SOAPBOXX_WORKFLOW_SKIP_GATE=1`` to always run full enrichment.
- **Reality check (v3):** after ``report_v3`` is built, ``soapboxx_v3_workflow_local`` runs ``report_reality_checks.validate_reality_golden`` using ``backend/data/v3_reality_expected.json`` by default. Set ``SOAPBOXX_V3_REALITY_RULES`` to a JSON path to override; ``SOAPBOXX_V3_REALITY_CHECK=0`` to skip. Results are stored on ``metadata.v3_reality_check`` (``failures``, ``would_ship`` / ``ship_blockers``, ``degraded_notes``, plus ``report_v3_output_mode``, ``signal_mode``, ``readiness_band``, ``diagnostic_reasons``, ``good_clean_insight_lines``) and echoed into ``metadata.source_warnings``.

**Alternate:** ``use_cloud_llm=True`` — AI-only pipeline (`soapboxx_v3_workflow_cloud`), no v3 coach merge.

**LLM (workflow + editorial pass):** ``call_llm`` uses **Ollama** (``SOAPBOXX_OLLAMA_MODEL`` + ``OLLAMA_HOST``)
or **Groq** (``GROQ_API_KEY`` / ``SOAPBOXX_GROQ_API_KEY``) when ``SOAPBOXX_WORKFLOW_LLM_BACKEND=groq`` —
**default is ``groq`` if a Groq key is set**, else Ollama. (Episode **brief** / strict contract in
``episode_intelligence`` remains **Ollama**.) Responses are normalized to a strict envelope
``{"text": str, "data": object}`` (shared with ``episode_intelligence``). ``call_llm_json`` requires
non-empty ``data`` unless ``SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=1`` to allow parsing JSON from ``text``
(default is ``data``-only). Set ``SOAPBOXX_LLM_VALIDATE_WORKFLOW_DATA=1`` to require at least
one known workflow key on parsed JSON (see ``llm_data_contracts``). Ollama uses JSON mode; Groq uses
``response_format=json_object``. Optional: ``SOAPBOXX_OLLAMA_NUM_CTX`` / ``OLLAMA_NUM_CTX`` (context),
``SOAPBOXX_OLLAMA_TOP_P``; for Groq set ``SOAPBOXX_GROQ_WORKFLOW_MODEL`` (default
``llama-3.1-8b-instant``). **Editorial pass** on unified markdown: ``maybe_editorial_pass_unified_markdown``
— on by default when an LLM is available (disable with ``SOAPBOXX_EDITORIAL_PASS=0``). CLI applies it when
writing JSON; ``generate_network_brief_v3`` applies it to the final ``markdown_export`` and syncs ``workflow_report``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Set, Tuple

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
    from .episode_intelligence import (
        LLM_ENVELOPE_SYSTEM_SUFFIX,
        _clean_claim_text,
        _llm_envelope_text_fallback_enabled,
        coerce_ollama_message_to_envelope,
        llm_env_truthy,
    )
except ImportError:
    from episode_intelligence import (  # type: ignore
        LLM_ENVELOPE_SYSTEM_SUFFIX,
        _clean_claim_text,
        _llm_envelope_text_fallback_enabled,
        coerce_ollama_message_to_envelope,
        llm_env_truthy,
    )

_LOG_WF = logging.getLogger(__name__)

try:
    from .guest_generation_decision import gather_issue_blob_for_guests, should_generate_guests
except ImportError:
    from guest_generation_decision import (  # type: ignore
        gather_issue_blob_for_guests,
        should_generate_guests,
    )

REQUIRED_QUESTION_TYPES = frozenset({"counter", "validation", "application"})

# Structured workflow JSON is v3; distinct from the v2 compact brief JSON in episode_intelligence.
WORKFLOW_SPEC_VERSION = "3"

# Drop LLM “placeholder experts” (job labels with no name) from booking-oriented exports.
_GENERIC_GUEST_NAME_BLOCKLIST = frozenset(
    {
        "historian",
        "skeptical expert",
        "domain expert",
        "domain practitioner",
        "communications expert",
        "life coach",
        "business consultant",
        "motivational speaker",
        "expert",
        "researcher",
        "author",
    }
)
_GENERIC_SINGLE_TOKEN_NAMES = frozenset(
    {
        "historian",
        "skeptic",
        "expert",
        "researcher",
        "journalist",
        "scientist",
        "author",
    }
)


def _align_guest_ids_to_evidence_map(
    evidence_map: List[Dict[str, Any]], guests: List[Dict[str, Any]]
) -> None:
    """
    Map ``c1``/``c2``-style ids from the brief LLM to real evidence row ids (often ``a1``, ``a6``).
    """
    eids: List[str] = []
    for e in evidence_map or []:
        if not isinstance(e, dict):
            continue
        eid = str(e.get("id") or "").strip()
        if eid and eid not in eids:
            eids.append(eid)
    if not eids or not guests:
        return

    def _remap_one(raw: str) -> str:
        s = (raw or "").strip()
        if not s:
            return eids[0]
        if s in eids:
            return s
        low = s.lower()
        if low.startswith("c") and low[1:].isdigit():
            idx = int(low[1:]) - 1
            if 0 <= idx < len(eids):
                return eids[idx]
        return eids[0]

    for g in guests:
        if not isinstance(g, dict):
            continue
        nxt = _remap_one(str(g.get("maps_to_claim_id") or g.get("claim_id") or ""))
        g["maps_to_claim_id"] = nxt
        g["claim_id"] = nxt


def _guest_name_is_plausible_booking(g: Dict[str, Any]) -> bool:
    n = str(g.get("name") or "").strip()
    if len(n) < 3:
        return False
    low = n.lower()
    if low in _GENERIC_GUEST_NAME_BLOCKLIST:
        return False
    if " " not in n and low in _GENERIC_SINGLE_TOKEN_NAMES:
        return False
    return True


def _booking_oriented_guest_rows(rows: List[Any]) -> List[Any]:
    """
    Drop transcript-figure rows (``episode_grounded_person`` / “named in episode verbatim”) from any
    list returned to UIs or markdown — those are **story subjects**, not outreach targets.

    Stale workflow JSON from older builds may still contain those rows; filtering here fixes exports
    without requiring a full re-run.
    """
    if not rows:
        return rows
    out: List[Any] = []
    for g in rows:
        if not isinstance(g, dict):
            out.append(g)
            continue
        src = str(g.get("source") or "").strip()
        if src == "episode_grounded_person":
            continue
        title_l = str(g.get("title") or "").lower()
        if "named in this episode" in title_l and "verbatim" in title_l:
            continue
        out.append(g)
    if out:
        return out
    cid0 = ""
    if rows and isinstance(rows[0], dict):
        cid0 = str((rows[0] or {}).get("claim_id") or "").strip()
    return [
        {
            "name": "Subject-matter historian or investigative journalist",
            "title": "Bookable expert (replaces transcript-name placeholders)",
            "role": "Expert",
            "claim_id": cid0 or "c1",
            "angle": (
                "Prior rows only named people *in* the story — add an outside expert who can "
                "contextualize or fact-check the same themes."
            ),
            "topic_angle": "Outreach-oriented guest angle",
            "relevance": 7,
            "source": "expert_placeholder_after_verbatim_filter",
        }
    ]


def workflow_guest_rows(workflow: Optional[Dict[str, Any]]) -> List[Any]:
    """Return the workflow guest list: prefer ``guests``, then legacy ``guest_recommendations``.

    If both keys hold lists but they are **not** the same object (alias drift), re-bind via
    :func:`set_workflow_guest_rows` using canonical ``guests`` when non-empty, else legacy rows.

    Returned rows omit **verbatim transcript figures** (``episode_grounded_person``) so JSON and
    markdown match “bookable expert” intent.
    """
    if not isinstance(workflow, dict):
        return []
    g = workflow.get("guests")
    gr = workflow.get("guest_recommendations")
    if isinstance(g, list) and isinstance(gr, list) and g is not gr:
        source = g if g else gr
        if g and gr and g != gr:
            _LOG_WF.debug(
                "workflow_guest_rows: guest list value conflict; canonical `guests` overrides legacy `guest_recommendations`"
            )
        elif __debug__:
            _LOG_WF.debug(
                "workflow_guest_rows: healing guests/guest_recommendations alias drift (different list ids)"
            )
        set_workflow_guest_rows(workflow, source)
        return _booking_oriented_guest_rows(workflow["guests"])
    if isinstance(g, list):
        return _booking_oriented_guest_rows(g)
    if isinstance(gr, list):
        return _booking_oriented_guest_rows(gr)
    return []


def set_workflow_guest_rows(workflow: Dict[str, Any], rows: List[Any]) -> None:
    """
    Set canonical ``guests`` and mirror to ``guest_recommendations`` for backward compatibility.

    Copies ``rows`` into a **single** new list so both keys share one reference; use this (or in-place
    mutation on that list) instead of assigning only one key—reassigning one key with ``+`` or slicing
    would break the alias invariant.
    """
    unified: List[Any] = list(rows)
    workflow["guests"] = unified
    workflow["guest_recommendations"] = unified
    if __debug__:
        assert workflow["guests"] is workflow["guest_recommendations"]


def _safe_claim_text(claim: Any) -> str:
    """
    Normalize any claim-shaped value to a plain string for ``.split()`` / ``.replace()`` / matching.
    Handles str, dicts with text/raw_statement/claim (including nested dicts), and other scalars.
    """
    try:
        from .transcript_structure_extract import strip_youtube_caption_metadata as _strip_cap
    except ImportError:  # pragma: no cover
        from transcript_structure_extract import strip_youtube_caption_metadata as _strip_cap  # type: ignore

    def _fin(s: str) -> str:
        return _strip_cap((s or "").strip()).strip()

    if claim is None:
        return ""
    if isinstance(claim, str):
        return _fin(claim)
    if isinstance(claim, dict):
        for key in ("text", "raw_statement", "claim"):
            v = claim.get(key)
            if isinstance(v, str) and v.strip():
                return _fin(v)
            if isinstance(v, dict):
                inner = _safe_claim_text(v)
                if inner.strip():
                    return inner
        return ""
    return _fin(str(claim))


def _workflow_claim_rows_for_subject_fallback(r3: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    When ``report_v3["claims"]`` is empty, still use atomic envelope claims or evidence_mapping
    rows so subject extraction can see the same text the UI labels as claims.
    """
    ap = r3.get("atomic_pipeline")
    if isinstance(ap, dict):
        raw = ap.get("claims") or []
        ac = [c for c in raw if isinstance(c, dict)]
        if ac:
            return ac
    out: List[Dict[str, Any]] = []
    for row in r3.get("evidence_mapping") or []:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        cl = _safe_claim_text({"claim": row.get("claim")})
        if not cl.strip():
            cl = _safe_claim_text(row)
        if cid and cl.strip():
            out.append({"id": cid, "text": cl.strip()})
    return out


# Default word budget for workflow LLM transcript window (override via ``SOAPBOXX_WORKFLOW_MAX_WORDS``).
DEFAULT_WORKFLOW_MAX_WORDS = 500_000


def _apply_workflow_version_metadata(meta: Dict[str, Any]) -> None:
    """Stamp workflow outputs so integrations know this is the primary v3 workflow spec."""
    meta["workflow_spec_version"] = WORKFLOW_SPEC_VERSION
    meta["primary_episode_workflow"] = True


def _derive_structure_state(evidence_rows: int, segments: int) -> str:
    """Compatibility wrapper: delegated to snapshot evaluator helpers."""
    try:
        from .evaluation_pipeline import derive_structure_state
    except ImportError:
        from evaluation_pipeline import derive_structure_state  # type: ignore
    return derive_structure_state(evidence_rows, segments)


def _compute_structure_diagnostics(
    workflow_report: Dict[str, Any], report_v3: Dict[str, Any]
) -> Dict[str, Any]:
    """Compatibility wrapper: delegated to snapshot evaluator helpers."""
    try:
        from .evaluation_pipeline import build_evaluation_snapshot, evaluate_snapshot
    except ImportError:
        from evaluation_pipeline import build_evaluation_snapshot, evaluate_snapshot  # type: ignore
    wf = workflow_report if isinstance(workflow_report, dict) else {}
    r3 = report_v3 if isinstance(report_v3, dict) else {}
    snap = build_evaluation_snapshot(wf, r3, {"strict_export_enabled": True})
    ev = evaluate_snapshot(snap)
    return dict(ev.get("structure_diagnostics") or {})


def _attach_structure_diagnostics(
    meta_out: Dict[str, Any], workflow_report: Dict[str, Any], report_v3: Dict[str, Any]
) -> None:
    """Attach observational structure telemetry to workflow metadata."""
    diag = _compute_structure_diagnostics(workflow_report, report_v3)
    meta_out["structure_state"] = str(diag.get("structure_state") or "FAIL")
    meta_out["structure_diagnostics"] = diag


def _v3_reality_check_enabled() -> bool:
    raw = os.getenv("SOAPBOXX_V3_REALITY_CHECK")
    if raw is None:
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off")


def _run_v3_reality_check_into_meta(
    r3: Dict[str, Any],
    transcript: str,
    meta_out: Dict[str, Any],
    source_warnings: List[str],
) -> None:
    """Load reality rules, validate ``report_v3``, attach ``metadata.v3_reality_check`` + warnings."""
    if not _v3_reality_check_enabled():
        return
    try:
        try:
            from . import report_reality_checks as rrc
        except ImportError:
            import report_reality_checks as rrc  # type: ignore
    except ImportError:
        source_warnings.append("v3_reality: report_reality_checks module not available")
        return

    custom = (os.getenv("SOAPBOXX_V3_REALITY_RULES") or "").strip()
    rules: Dict[str, Any]
    rules_label: str
    if custom:
        if not os.path.isfile(custom):
            source_warnings.append(f"v3_reality: SOAPBOXX_V3_REALITY_RULES file missing: {custom}")
            return
        try:
            rules = rrc.load_reality_rules_from_path(Path(custom).expanduser())
            rules_label = custom
        except Exception as e:
            source_warnings.append(f"v3_reality: failed to load rules from {custom}: {e}")
            return
    else:
        rules = rrc.load_default_reality_rules()
        rules_label = str(rrc.default_reality_rules_path())
        if not rules:
            source_warnings.append(f"v3_reality: default rules file missing: {rules_label}")
            return

    tx = transcript or ""
    fails, degraded_notes = rrc.validate_reality_golden(r3, tx, rules)
    ship_ok, ship_fails = rrc.would_ship_v3(r3, tx)
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    dr = rr.get("diagnostic_reasons")
    if isinstance(dr, list):
        diagnostic_reasons = [str(x).strip() for x in dr if str(x).strip()]
    else:
        diagnostic_reasons = [str(dr).strip()] if dr and str(dr).strip() else []
    good_highlight_ct = 0
    try:
        try:
            from .episode_report_v3 import is_low_signal_insight_line as _low_sig_hl
        except ImportError:
            from episode_report_v3 import is_low_signal_insight_line as _low_sig_hl  # type: ignore
    except ImportError:
        _low_sig_hl = None  # type: ignore[misc, assignment]
    if _low_sig_hl:
        for ln in r3.get("clean_insights") or []:
            s = str(ln).strip()
            if s and not _low_sig_hl(s):
                good_highlight_ct += 1
    meta_out["v3_reality_check"] = {
        "passed": len(fails) == 0,
        "failures": fails,
        "degraded_notes": degraded_notes,
        "would_ship": ship_ok,
        "ship_blockers": ship_fails,
        "rules_source": rules_label,
        # Why ``output_mode`` may be diagnostic — mirrors ``report_v3`` without opening nested JSON.
        "report_v3_output_mode": str(r3.get("output_mode") or ""),
        "signal_mode": str(r3.get("signal_mode") or ""),
        "readiness_band": str(rr.get("band") or ""),
        "diagnostic_reasons": diagnostic_reasons,
        "good_clean_insight_lines": good_highlight_ct,
    }
    # One-line summaries in source_warnings — full detail lives in metadata.v3_reality_check.
    if fails:
        source_warnings.append(
            f"v3_reality: {len(fails)} expectation(s) failed — see metadata.v3_reality_check.failures"
        )
    if degraded_notes:
        for note in degraded_notes:
            source_warnings.append(f"v3_reality (non-blocking): {note}")
    if not ship_ok and ship_fails:
        fail_only = [x for x in ship_fails if str(x).startswith("FAIL:")]
        warn_only = [x for x in ship_fails if not str(x).startswith("FAIL:")]
        if fail_only:
            source_warnings.append(
                f"v3_reality: would-ship bar not met ({len(fail_only)} blocker(s)) — "
                "see metadata.v3_reality_check.ship_blockers"
            )
        for w in warn_only:
            source_warnings.append(f"v3_reality (non-blocking): {w}")


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


def _groq_api_key() -> str:
    return os.getenv("SOAPBOXX_GROQ_API_KEY", "").strip() or os.getenv("GROQ_API_KEY", "").strip()


def _workflow_llm_backend() -> str:
    """
    ``ollama`` | ``groq``. Default: Groq when a Groq key is set (faster/cleaner JSON for workflow
    enrichment), else Ollama. Brief generation stays on Ollama in ``episode_intelligence`` regardless.
    """
    forced = os.getenv("SOAPBOXX_WORKFLOW_LLM_BACKEND", "").strip().lower()
    if forced in ("ollama", "groq"):
        return forced
    if _groq_api_key():
        return "groq"
    return "ollama"


def _groq_chat(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "",
    json_format: bool = False,  # unused; OpenAI client always returns JSON when requested
    stage: str = "workflow.llm",
) -> Dict[str, Any]:
    """Groq OpenAI-compatible API — same envelope contract as Ollama path."""
    _ = json_format
    api_key = _groq_api_key()
    if not api_key:
        raise RuntimeError(
            "SOAPBOXX_WORKFLOW_LLM_BACKEND=groq (or default when GROQ_API_KEY is set) requires "
            "GROQ_API_KEY or SOAPBOXX_GROQ_API_KEY."
        )
    model = os.getenv("SOAPBOXX_GROQ_WORKFLOW_MODEL", "").strip() or "llama-3.1-8b-instant"
    base = os.getenv("SOAPBOXX_GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/")
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover - optional dep
        raise RuntimeError("Install the 'openai' package for Groq workflow LLM support.") from e
    base_sys = (system or "").strip()
    full_sys = (
        (base_sys + "\n\n" + LLM_ENVELOPE_SYSTEM_SUFFIX)
        if base_sys
        else LLM_ENVELOPE_SYSTEM_SUFFIX
    )
    client = OpenAI(api_key=api_key, base_url=f"{base}/")
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": full_sys},
                {"role": "user", "content": prompt},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:
        raise RuntimeError(f"Groq workflow LLM failed ({stage}): {e}") from e
    return coerce_ollama_message_to_envelope(raw)


def _ollama_chat(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "",
    json_format: bool = False,
    stage: str = "workflow.llm",
) -> Dict[str, Any]:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError("SOAPBOXX_OLLAMA_MODEL not set")
    base_sys = (system or "").strip()
    full_sys = (
        (base_sys + "\n\n" + LLM_ENVELOPE_SYSTEM_SUFFIX)
        if base_sys
        else LLM_ENVELOPE_SYSTEM_SUFFIX
    )
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": full_sys},
        {"role": "user", "content": prompt},
    ]
    ollama_opts: Dict[str, Any] = {
        "num_predict": max_tokens,
        "temperature": temperature,
    }
    _ctx = os.getenv("SOAPBOXX_OLLAMA_NUM_CTX", os.getenv("OLLAMA_NUM_CTX", "")).strip()
    if _ctx:
        try:
            ollama_opts["num_ctx"] = int(_ctx)
        except ValueError:
            pass
    _tp = os.getenv("SOAPBOXX_OLLAMA_TOP_P", "").strip()
    if _tp:
        try:
            ollama_opts["top_p"] = float(_tp)
        except ValueError:
            pass
    _seed = os.getenv("SOAPBOXX_OLLAMA_SEED", "").strip()
    if _seed:
        try:
            ollama_opts["seed"] = int(_seed)
        except ValueError:
            pass
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": ollama_opts,
        "format": "json",
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
            payload,
            stage=stage,
            component="soapboxx_workflow",
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


def call_llm(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "You follow instructions exactly. When asked for JSON, respond with ONLY valid JSON — no markdown fences, no commentary.",
    client: Any = None,
    json_format: bool = False,
    stage: str = "workflow.llm",
) -> Dict[str, Any]:
    """
    Workflow / editorial LLM. Backend: ``SOAPBOXX_WORKFLOW_LLM_BACKEND`` = ``ollama`` | ``groq``;
    if unset, **Groq is used when** ``GROQ_API_KEY`` (or ``SOAPBOXX_GROQ_API_KEY``) is set, else Ollama.
    ``client`` is ignored (compat). Episode brief extraction remains Ollama in ``episode_intelligence``.
    """
    _ = client
    if _workflow_llm_backend() == "groq":
        return _groq_chat(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            json_format=json_format,
            stage=stage,
        )
    if not os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip():
        raise RuntimeError(
            "Workflow LLM: set SOAPBOXX_OLLAMA_MODEL for Ollama, or configure GROQ_API_KEY and "
            "SOAPBOXX_WORKFLOW_LLM_BACKEND=groq (default backend is groq when a Groq key is present)."
        )
    return _ollama_chat(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        json_format=json_format,
        stage=stage,
    )


def call_llm_with_retry(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "You follow instructions exactly. When asked for JSON, respond with ONLY valid JSON — no markdown fences, no commentary.",
    client: Any = None,
    json_format: bool = False,
    stage: str = "workflow.llm",
) -> Dict[str, Any]:
    """Retries are handled inside :func:`_ollama_chat` / ``ollama_api_chat`` (bounded exponential)."""
    return call_llm(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        client=client,
        json_format=json_format,
        stage=stage,
    )


def call_llm_json(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    parser: Callable[[str], Any] = json.loads,
    client: Any = None,
) -> Any:
    """Resolve structured workflow JSON from the LLM envelope (binary policy, no middle tier).

    - **Default:** use non-empty ``data``; if ``data`` is empty, parse ``text`` (local models often omit ``data``).
    - **Strict** (``SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0``): non-empty ``data`` only; ``text`` ignored for structure.

    Transport integrity only. Optional semantic checks: set ``SOAPBOXX_LLM_VALIDATE_WORKFLOW_DATA=1``
    to require at least one known workflow key on the resolved object (see ``llm_data_contracts``).
    """
    env = call_llm_with_retry(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        client=client,
        json_format=True,
    )
    if not isinstance(env, dict):
        raise TypeError("call_llm_json: expected envelope dict from LLM")
    raw_data = env.get("data")
    data = raw_data if isinstance(raw_data, dict) else {}
    tr = env.get("text")
    text = tr if isinstance(tr, str) else ""

    allow_text = _llm_envelope_text_fallback_enabled()

    if allow_text:
        if len(data) > 0:
            result: Any = data
        else:
            if not text.strip():
                raise ValueError(
                    'call_llm_json: "data" is empty and "text" is empty — nothing to parse.'
                )
            _LOG_WF.warning(
                'call_llm_json: using structured JSON from envelope "text" because "data" was empty.'
            )
            result = parser(_strip_json_fence(text))
    else:
        if len(data) > 0:
            result = data
        else:
            raise ValueError(
                'call_llm_json (strict mode): expected non-empty "data" '
                '(SOAPBOXX_LLM_ENVELOPE_TEXT_FALLBACK=0 disables parsing JSON from "text").'
            )

    if llm_env_truthy("SOAPBOXX_LLM_VALIDATE_WORKFLOW_DATA"):
        try:
            from .llm_data_contracts import (
                WORKFLOW_LLM_KNOWN_KEYS,
                validate_workflow_data_has_known_keys,
            )
        except ImportError:
            from llm_data_contracts import (  # type: ignore
                WORKFLOW_LLM_KNOWN_KEYS,
                validate_workflow_data_has_known_keys,
            )
        validate_workflow_data_has_known_keys(result, expected=WORKFLOW_LLM_KNOWN_KEYS)

    return result


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


def _ts_missing(v: Any) -> bool:
    if v is None:
        return True
    s = str(v).strip().lower()
    return s in {"", "n/a", "na", "none", "null", "—", "-"}


def _cue_tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z']+", (text or "").lower()) if len(t) > 2}


def _cue_overlap(a: str, b: str) -> float:
    sa, sb = _cue_tokens(a), _cue_tokens(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(max(len(sa), len(sb), 1))


def _normalize_transcript_cues(raw: Any) -> List[Dict[str, Any]]:
    cues: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return cues
    for row in raw[:6000]:
        if not isinstance(row, dict):
            continue
        txt = str(row.get("text") or "").strip()
        if len(txt) < 10:
            continue
        ts = row.get("timestamp")
        start_sec = row.get("start_sec")
        if start_sec is None:
            try:
                start_sec = float(str(ts).strip().rstrip("s"))
            except Exception:
                start_sec = None
        cues.append({"text": txt, "timestamp": ts, "start_sec": start_sec})
    return cues


def _align_missing_timestamps_with_cues(rows: Any, cues: List[Dict[str, Any]]) -> int:
    """Fill missing evidence timestamps using transcript cue overlap; returns rows updated."""
    if not isinstance(rows, list) or not cues:
        return 0
    updated = 0
    overlap_floor = 0.10
    for row in rows:
        if not isinstance(row, dict):
            continue
        if not _ts_missing(row.get("timestamp")):
            continue
        probe = str(row.get("evidence") or row.get("claim") or "").strip()
        if len(probe) < 10:
            continue
        best = None
        best_sc = 0.0
        for cue in cues:
            ct = str(cue.get("text") or "")
            if len(ct) < 10:
                continue
            sc = _cue_overlap(probe, ct)
            if sc > best_sc:
                best_sc = sc
                best = cue
        if best is None or best_sc < overlap_floor:
            continue
        start = best.get("start_sec")
        if isinstance(start, (int, float)):
            row["timestamp"] = round(float(start), 1)
            updated += 1
            continue
        ts = str(best.get("timestamp") or "").strip()
        if ts:
            row["timestamp"] = ts
            updated += 1
    return updated


def _education_spine_score(claim_text: str) -> int:
    low = (claim_text or "").lower()
    score = 0
    for k in (
        "rockefeller",
        "foundation",
        "school board",
        "schooling",
        "curriculum",
        "standardized",
        "soviet",
        "prussia",
        "prussian",
        "centralization",
        "decentralization",
        "education system",
        "district",
    ):
        if k in low:
            score += 2
    if "school" in low or "education" in low:
        score += 1
    return score


def _sanitize_evidence_map_claims(
    rows: List[Dict[str, Any]],
    *,
    spine_hint: str = "",
) -> List[Dict[str, Any]]:
    """
    Remove truncated ASR claim lines and duplicate beats (same claim text, different ids).
    When ``spine_hint`` looks like an education episode, drop obvious tangents and sort on-theme rows first.
    """
    try:
        from .episode_report_v3 import (
            _claim_conflicts_spine_hint,
            _dedupe_repeated_sentences,
            _is_broken_evidence_claim_line,
            _strategist_mic_line_is_praise_or_meta,
        )
    except ImportError:
        from episode_report_v3 import (
            _claim_conflicts_spine_hint,
            _dedupe_repeated_sentences,
            _is_broken_evidence_claim_line,
            _strategist_mic_line_is_praise_or_meta,
        )

    seen = set()
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        cl = str(r.get("claim") or "").strip()
        if not cl or _is_broken_evidence_claim_line(cl):
            continue
        if _strategist_mic_line_is_praise_or_meta(cl):
            continue
        if spine_hint and _claim_conflicts_spine_hint(cl, spine_hint):
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
    low_spine = (spine_hint or "").lower()
    if any(
        k in low_spine
        for k in (
            "rockefeller",
            "school",
            "education",
            "brainwash",
            "psyop",
            "curriculum",
        )
    ):
        out.sort(key=lambda row: -_education_spine_score(str(row.get("claim") or "")))
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
    if _workflow_llm_backend() == "groq" and _groq_api_key():
        return True
    return bool(os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip())


def _editorial_pass_enabled() -> bool:
    """
    Optional polish pass on unified markdown (Ollama).

    - ``SOAPBOXX_EDITORIAL_PASS=0`` (or ``false`` / ``no`` / ``off``): off.
    - ``SOAPBOXX_EDITORIAL_PASS=1`` (or ``true`` / ``yes`` / ``on``): on if a model is set.
    - **Unset:** on when ``SOAPBOXX_OLLAMA_MODEL`` is set (one light pass for real episodes).
    """
    v = os.getenv("SOAPBOXX_EDITORIAL_PASS", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return _llm_available()
    return _llm_available()


def maybe_editorial_pass_unified_markdown(
    markdown: str,
    meta: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool]:
    """
    One editorial pass: tighten wording, fix obvious ASR artifacts, dedupe redundant bullets.
    Uses workflow LLM (Groq or Ollama; see :func:`call_llm`). Returns ``(markdown, applied)``;
    on failure returns original markdown.
    """
    if not _editorial_pass_enabled() or not (markdown or "").strip():
        return markdown, False
    m = meta or {}
    title = str(m.get("title") or m.get("Title") or "").strip()
    try:
        cap = int(os.getenv("SOAPBOXX_EDITORIAL_MAX_INPUT_CHARS", "120000") or "120000")
    except ValueError:
        cap = 120000
    cap = max(8000, min(cap, 500000))
    md_in = markdown if len(markdown) <= cap else (
        markdown[:cap] + "\n\n*[Editorial input truncated for context limit]*\n"
    )
    try:
        mt = int(os.getenv("SOAPBOXX_EDITORIAL_MAX_TOKENS", "6000") or "6000")
    except ValueError:
        mt = 6000
    mt = max(1500, min(mt, 32000))
    prompt = f"""You are an experienced podcast editor. Polish this SoapBoxx episode report markdown for a working creator.

Rules:
- Preserve all major ## / ### headings and section order; keep tables if present.
- Fix obvious ASR/transcription glitches (broken brackets, stutter repeats).
- Tighten the working thesis or primary topic line to one clear sentence only where the text already implies it.
- Do not invent facts, guests, numbers, or quotes not supported by the document.
- Remove or merge bullets that repeat the same point verbatim.
- Output ONLY the full revised markdown document — no preamble, no closing notes.

Episode title (context): {title or "(untitled)"}

---

{md_in}
"""
    try:
        env = call_llm(
            prompt,
            max_tokens=mt,
            temperature=0.22,
            system=(
                "Put the full revised markdown document ONLY in the JSON \"text\" field. "
                'Use \"data\": {}. No markdown fences inside \"text\". No commentary before or after the document.'
            ),
            json_format=False,
        )
        out = (env.get("text") or "").strip()
        if len(out) < min(400, len(markdown) // 4) and len(markdown) > 800:
            return markdown, False
        try:
            from .episode_report_v3 import finalize_unified_markdown_export
        except ImportError:  # pragma: no cover
            from episode_report_v3 import finalize_unified_markdown_export  # type: ignore
        return finalize_unified_markdown_export(out), True
    except Exception:
        return markdown, False


def _workflow_ai_enrichment_enabled() -> bool:
    return os.getenv("SOAPBOXX_WORKFLOW_USE_AI", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _atomic_structure_lock_from_report_v3(r3: Optional[Dict[str, Any]]) -> bool:
    """
    When the v3 report was built from atomic ground truth, workflow AI enrichment must not
    replace evidence_map or guests / guest_recommendations (SSOT — see episode_report_v3).
    """
    if not r3 or not isinstance(r3, dict):
        return False
    meta = r3.get("meta") if isinstance(r3.get("meta"), dict) else {}
    if str(meta.get("structured_intelligence_source") or "").strip() == "atomic_pipeline":
        return True
    ap = r3.get("atomic_pipeline")
    return isinstance(ap, dict) and bool(ap)


def _snapshot_workflow_rows(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for r in rows:
        if isinstance(r, dict):
            out.append(dict(r))
    return out


def enrich_workflow_report_minimal(
    transcript: str,
    body: Dict[str, Any],
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
    report_v3: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single LLM call when the quality gate skips full multi-step enrichment (very short transcript
    or highly duplicated lines). Uses the same transcript window as full enrichment
    (``SOAPBOXX_WORKFLOW_MAX_CHARS``). Produces a smaller but valid workflow slice.

    When ``report_v3`` indicates atomic ground truth, the LLM must not replace ``evidence_map``
    rows (baseline from ``workflow_report_from_v3_report`` is preserved).
    """
    out = dict(body)
    lock = _atomic_structure_lock_from_report_v3(report_v3)
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

Output JSON only. Put that single object in the \"data\" field of the response contract (\"text\" may be \"\" ).
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
    if (
        not lock
        and isinstance(data.get("evidence_map"), list)
        and data["evidence_map"]
    ):
        em = _filter_grounded_evidence_map(transcript or "", data["evidence_map"][:8])
        out["evidence_map"] = _sanitize_evidence_map_claims(em)
    if isinstance(data.get("follow_up_questions"), list) and data["follow_up_questions"]:
        if lock:
            valid_ids = {
                str(e.get("id"))
                for e in (out.get("evidence_map") or [])
                if isinstance(e, dict) and e.get("id")
            }
            if valid_ids:
                fu = [
                    q
                    for q in data["follow_up_questions"]
                    if isinstance(q, dict)
                    and str(q.get("claim_id") or "") in valid_ids
                ]
                if fu:
                    out["follow_up_questions"] = fu
        else:
            out["follow_up_questions"] = data["follow_up_questions"]
    _sanitize_workflow_highlights(out)
    return out


def enrich_workflow_report_with_ai(
    transcript: str,
    body: Dict[str, Any],
    *,
    client: Any = None,
    episode_meta: Optional[Dict[str, Any]] = None,
    report_v3: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Fill workflow JSON using multi-step LLM extraction (highlights, evidence, Q&A, guests,
    segments, analytics). Caller supplies base `body` from `workflow_report_from_v3_report`;
    non-empty AI sections replace the corresponding lists.

    ``episode_meta`` (title, creator, genre, …) is passed into follow-up generation so questions
    are anchored to the show and claims, not generic podcast boilerplate.

    When ``report_v3`` indicates atomic ground truth, ``evidence_map`` and
    ``guests`` (legacy alias ``guest_recommendations``) from ``body`` are immutable: enrichment may add highlights,
    analytics, segments, and filtered follow-ups only.
    """
    out = dict(body)
    _g0 = workflow_guest_rows(out)
    if _g0:
        set_workflow_guest_rows(out, _g0)  # mirror canonical ``guests`` + legacy alias
    lock = _atomic_structure_lock_from_report_v3(report_v3)
    baseline_em = _snapshot_workflow_rows(out.get("evidence_map")) if lock else []
    baseline_guests = _snapshot_workflow_rows(workflow_guest_rows(out)) if lock else []
    baseline_fuq = _snapshot_workflow_rows(out.get("follow_up_questions")) if lock else []
    excerpt = _workflow_transcript_excerpt(transcript)
    if not excerpt:
        return out

    highlights = generate_highlights(excerpt, client=client, episode_meta=episode_meta)
    if highlights:
        out["highlights"] = highlights

    ev_mode = _workflow_evidence_mode()
    if lock:
        pass  # evidence_map stays baseline from workflow_report_from_v3_report
    elif ev_mode == "v3":
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
        if lock:
            valid_ids = {
                str(e.get("id")) for e in em if isinstance(e, dict) and e.get("id")
            }
            if valid_ids:
                questions = [
                    q
                    for q in questions
                    if isinstance(q, dict) and str(q.get("claim_id") or "") in valid_ids
                ]
            else:
                questions = []
            if not questions and baseline_fuq:
                questions = baseline_fuq
        if questions:
            out["follow_up_questions"] = questions
    elif lock and baseline_fuq:
        out["follow_up_questions"] = baseline_fuq

    if not lock:
        allow = _grounded_guest_name_allowlist_for_workflow(report_v3, transcript or "")
        guests = generate_guest_recommendations(
            em,
            client=client,
            highlights=out.get("highlights") or [],
            episode_meta=episode_meta,
            transcript=transcript or "",
            grounded_name_allowlist=allow if allow else None,
        )
        if allow and not guests:
            guests = generate_guest_recommendations(
                em,
                client=client,
                highlights=out.get("highlights") or [],
                episode_meta=episode_meta,
                transcript=transcript or "",
                grounded_name_allowlist=None,
            )
        if not guests and report_v3 and isinstance(report_v3, dict):
            cid_fb = ""
            for e in em:
                if isinstance(e, dict) and str(e.get("id") or "").strip():
                    cid_fb = str(e.get("id") or "").strip()
                    break
            guests = generate_guest_archetypes_from_issues(report_v3, cid_fb or "c1", max_archetypes=4)
        if guests:
            for g in guests:
                if not isinstance(g, dict):
                    continue
                if not str(g.get("title") or "").strip():
                    r = str(g.get("role") or "").strip()
                    if r:
                        g["title"] = r
                g.setdefault("topic_angle", g.get("angle"))
            set_workflow_guest_rows(out, guests)

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

    if lock:
        # Only restore SSOT snapshots when they actually contain rows. An empty baseline must not
        # overwrite valid mapper output (e.g. Tier-3 guests) when the snapshot was stale or empty.
        if baseline_em:
            out["evidence_map"] = baseline_em
        if baseline_guests:
            set_workflow_guest_rows(out, baseline_guests)

    _prune_follow_up_questions_to_evidence_map(out)
    _sanitize_workflow_highlights(out)
    return out


def validate_json(report: Dict[str, Any], *, strict: bool = True) -> Dict[str, Any]:
    """
    Validate v3 JSON structure. With strict=False, only checks types and refs when evidence exists.
    """
    md = report.get("metadata")
    if isinstance(md, dict) and md.get("export_status") in ("insufficient_signal", "degraded"):
        return report

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
        from .episode_report_v3 import (
            render_episode_report_v3_markdown,
            render_unified_episode_export_markdown,
        )
        from .episode_progress import (
            attach_export_telemetry_to_metadata,
            persist_episode_progress_after_export,
            prepare_bundle_for_export,
        )
    except ImportError:
        from episode_report_v3 import (  # type: ignore
            render_episode_report_v3_markdown,
            render_unified_episode_export_markdown,
        )
        from episode_progress import (  # type: ignore
            attach_export_telemetry_to_metadata,
            persist_episode_progress_after_export,
            prepare_bundle_for_export,
        )

    m = meta or {}
    bundle = {
        "report_v3": report_v3 or {},
        "workflow_report": report,
        "meta": {
            "generated_at": m.get("generated") or m.get("generated_at"),
            "title": m.get("title"),
            "creator": m.get("creator"),
            "genre": m.get("genre"),
        },
    }
    prepare_bundle_for_export(bundle)
    attach_export_telemetry_to_metadata(m, bundle)
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    tg = r3.get("truth_mode_gate") if isinstance(r3.get("truth_mode_gate"), dict) else {}
    truth_mode = (os.getenv("SOAPBOXX_MODE") or "truth").strip().lower()
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    rr_mode = str(rr.get("output_mode") or "").strip().lower()
    r3_mode = str(r3.get("output_mode") or "").strip().lower()
    truth_blocked = (
        str(tg.get("mode") or "").strip().lower() == "truth"
        and tg.get("passed") is False
    )
    if not truth_blocked and truth_mode != "growth" and (rr_mode == "diagnostic" or r3_mode == "diagnostic"):
        truth_blocked = True
    if truth_blocked:
        # Bundle from the workflow path never includes ``markdown_v3`` (that lives on
        # ``generate_episode_report_v3`` output). Without a fallback this branch produced an
        # empty ``markdown_export`` and Local Workflow never wrote ``episode_report_unified.md``.
        md_diag = str(bundle.get("markdown_v3") or "").strip()
        if not md_diag and r3:
            try:
                md_diag = render_episode_report_v3_markdown(r3)
            except Exception:
                md_diag = ""
        report["markdown_export"] = md_diag
    else:
        report["markdown_export"] = render_unified_episode_export_markdown(bundle)
    persist_episode_progress_after_export(bundle)


def attach_summary_and_score(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add `summary` (one-line string) and `score` (0–100) for UI, doctor checks, and CI validation.
    Score is heuristic from signal_mode and weak_claims count.
    """
    md0 = report.get("metadata")
    if isinstance(md0, dict) and md0.get("export_status") in ("insufficient_signal", "degraded"):
        if md0.get("export_status") == "degraded":
            report["summary"] = (
                "Export degraded: Ollama transport failed after retries "
                "(see metadata.export_blockers)."
            )
        else:
            report["summary"] = (
                "Export withheld: insufficient grounded signal for a network-grade report "
                "(see metadata.export_blockers)."
            )
        report["score"] = 0
        return report

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


def _prune_follow_up_questions_to_evidence_map(report: Dict[str, Any]) -> None:
    """Drop follow-ups whose ``claim_id`` is not in ``evidence_map`` (LLM id drift or post-hoc row drops)."""
    em = report.get("evidence_map") or []
    if not isinstance(em, list):
        return
    valid = {
        str(e.get("id"))
        for e in em
        if isinstance(e, dict) and str(e.get("id") or "").strip()
    }
    if not valid:
        return
    fuq = report.get("follow_up_questions")
    if not isinstance(fuq, list) or not fuq:
        return
    pruned = [
        q
        for q in fuq
        if isinstance(q, dict) and str(q.get("claim_id") or "").strip() in valid
    ]
    if len(pruned) != len(fuq):
        _LOG_WF.warning(
            "Dropped %d follow_up_question(s) with claim_id not in evidence_map",
            len(fuq) - len(pruned),
        )
    report["follow_up_questions"] = pruned


def _sanitize_workflow_highlights(report: Dict[str, Any], spine_hint: str = "") -> None:
    """Remove lyric/outro/caption-style lines from workflow highlights (mutates ``report``)."""
    try:
        from .episode_report_v3 import (
            _appendix_surface_line_keeps,
            _is_garbled_insight_line,
            is_low_signal_insight_line,
        )
    except ImportError:
        from episode_report_v3 import (
            _appendix_surface_line_keeps,
            _is_garbled_insight_line,
            is_low_signal_insight_line,
        )

    hl = report.get("highlights") or []
    if not isinstance(hl, list) or not hl:
        return
    kept: List[Dict[str, Any]] = []
    n = 0
    for h in hl:
        if not isinstance(h, dict):
            continue
        ins = str(h.get("insight") or "").strip()
        if not ins or _is_garbled_insight_line(ins):
            continue
        if spine_hint and len(spine_hint.strip()) >= 12:
            if not _appendix_surface_line_keeps(ins, spine_hint):
                continue
        elif is_low_signal_insight_line(ins):
            continue
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


def _guest_generation_required(r3: Dict[str, Any]) -> bool:
    """Alias for workflow internals (same rule as :func:`should_generate_guests`)."""
    return should_generate_guests(r3)


# Order guest archetypes for sequencing: decision-first, then tension, bridge, credibility, packaging.
_GUEST_ARCHETYPE_PRIORITY: Tuple[str, ...] = ("structure", "tension", "application", "evidence", "packaging")

_SEQUENCE_HEADINGS: Tuple[str, ...] = (
    "Primary guest (start here)",
    "Secondary guest (next step)",
    "Optional guest (if scaling)",
)


def _archetype_priority_index(kind: str) -> int:
    k = str(kind or "").strip().lower()
    try:
        return _GUEST_ARCHETYPE_PRIORITY.index(k)
    except ValueError:
        return 99


def _sort_archetypes_by_priority(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Stable sort: structure → tension → application → evidence → packaging."""
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda ie: (_archetype_priority_index(str(ie[1].get("archetype_kind") or "")), ie[0]))
    return [r for _, r in indexed]


def _label_archetype_sequence(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    labels = ("primary", "secondary", "optional")
    out: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        heading = _SEQUENCE_HEADINGS[i] if i < len(_SEQUENCE_HEADINGS) else f"Step {i + 1}"
        seq = labels[i] if i < len(labels) else "optional"
        rr = dict(r)
        rr["guest_sequence"] = seq
        rr["sequence_label"] = heading
        out.append(rr)
    return out


def _primary_commitment_line(primary: Dict[str, Any]) -> str:
    """One decisive line so the creator knows what to book first (no extra archetypes)."""
    nm = str(primary.get("name") or "this archetype").strip()
    fix = str(primary.get("what_it_fixes") or "").strip().replace("**", "")
    fix = " ".join(fix.split())
    if len(fix) > 160:
        fix = fix[:159].rstrip() + "…"
    if fix:
        return f"**Start with this:** {nm} — this immediately targets the biggest gap: {fix}"
    return f"**Start with this:** {nm} — book this role first, then layer the next step."


def _next_episode_move_for_kind(archetype_kind: str) -> str:
    """One concrete execution step for the **primary** archetype only (no LLM)."""
    k = str(archetype_kind or "").strip().lower()
    moves = {
        "structure": "Break the episode into 3 segments: setup → conflict → resolution.",
        "tension": "Introduce a direct disagreement within the first 10 minutes.",
        "application": "End each section with ‘what this means today’ in 1–2 sentences.",
        "evidence": "Have the guest cite one primary source and explain it live.",
        "packaging": "Pull 2–3 standalone statements during recording for clips.",
    }
    return moves.get(k, moves["structure"])


def _archetype_row_from_parts(
    *,
    name: str,
    role: str,
    why: str,
    look_for: str,
    fixes: str,
    claim_id: str,
    relevance: int = 9,
    archetype_kind: str = "structure",
) -> Dict[str, Any]:
    return {
        "name": name,
        "title": "Guest archetype",
        "role": role,
        "claim_id": claim_id,
        "angle": why,
        "topic_angle": look_for,
        "what_it_fixes": fixes,
        "relevance": relevance,
        "guest_archetype": True,
        "archetype_kind": archetype_kind,
    }


def generate_guest_archetypes_from_issues(
    r3: Dict[str, Any],
    claim_id: str,
    *,
    max_archetypes: int = 3,
) -> List[Dict[str, Any]]:
    """
    Issue-driven coaching archetypes, then **real public names** from the outreach pool overlaid on
    ``name`` / ``title`` so exports show bookable people while keeping why/look_for/fixes text.
    """
    snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
    topic = str(snap.get("primary_topic") or snap.get("title") or "this episode").strip()
    topic_short = topic[:140] if topic else "this episode"
    genre = str(snap.get("genre") or "").strip().lower()
    blob = gather_issue_blob_for_guests(r3)

    def _has(*needles: str) -> bool:
        return any(n in blob for n in needles)

    candidates: List[Dict[str, Any]] = []

    if _has(
        "structure",
        "arc",
        "segment",
        "chapter",
        "narrative",
        "drift",
        "unclear",
        "through-line",
        "throughline",
        "outline",
        "mixed theme",
        "mixed themes",
        "weak structure",
    ):
        candidates.append(
            _archetype_row_from_parts(
                name="Narrative structure specialist (arc & beats)",
                role="Structure fix",
                why=(
                    f"Your episode has usable material around {topic_short}, but it needs a clearer "
                    f"narrative spine so listeners feel progression—not drift."
                ),
                look_for=(
                    "Storytellers who specialize in historical arcs; authors or editors who routinely "
                    "break content into beginning → conflict → resolution."
                ),
                fixes=(
                    "Turns long-form explanation into **compelling story progression** and easier clip cuts."
                ),
                claim_id=claim_id,
                archetype_kind="structure",
            )
        )

    if _has(
        "tension",
        "conflict",
        "debate",
        "opposing",
        "contrarian",
        "counter",
        "disagree",
        "both sides",
        "pushback",
    ):
        candidates.append(
            _archetype_row_from_parts(
                name="Contrarian or steel-manned opposing voice",
                role="Tension fix",
                why=(
                    "The episode reads flat if every claim lands in the same direction—listeners engage "
                    "when a credible counter-case is on the table."
                ),
                look_for=(
                    "Experts comfortable naming the strongest opposing view *fairly*; historians with "
                    "debated interpretations relevant to your topic."
                ),
                fixes=(
                    "Creates **clip-worthy conflict**, stronger discussion, and clearer stakes."
                ),
                claim_id=claim_id,
                archetype_kind="tension",
            )
        )

    if _has(
        "philosophy",
        "religion",
        "theology",
        "abstract",
        "meaning",
        "relevance",
        "today",
        "application",
        "drift",
        "mixed theme",
        "mixed themes",
    ):
        candidates.append(
            _archetype_row_from_parts(
                name="Modern application thinker (story → meaning → action)",
                role="Relevance fix",
                why=(
                    f"Some threads around {topic_short} risk floating in abstraction unless someone "
                    f"repeatedly bridges back to decisions listeners make this week."
                ),
                look_for=(
                    "Educators or practitioners who translate historical lessons into modern tradeoffs; "
                    "hosts who end segments with a concrete ‘so what now?’"
                ),
                fixes=(
                    "Bridges **story → meaning → action**, improving retention and shareable takeaways."
                ),
                claim_id=claim_id,
                archetype_kind="application",
            )
        )

    if _has("evidence", "ground", "verify", "quote", "claim", "fact", "source"):
        candidates.append(
            _archetype_row_from_parts(
                name="Evidence / verification partner",
                role="Credibility fix",
                why="When claims outrun what the tape can support, a verification-minded guest tightens what you can say out loud.",
                look_for=(
                    "Researchers comfortable with primary sources; beat reporters used to "
                    "‘confirmed vs alleged’ language."
                ),
                fixes="Reduces credibility risk and sharpens what belongs in marketing vs the episode.",
                claim_id=claim_id,
                relevance=8,
                archetype_kind="evidence",
            )
        )

    if _has("clip", "hook", "share", "moment", "quotable", "packaging"):
        candidates.append(
            _archetype_row_from_parts(
                name="Clip-first editorial producer",
                role="Packaging fix",
                why="Strong ideas still fail if there aren’t clean standalone moments for short-form.",
                look_for="Editors who design segments around one beat per clip; producers who script cold-opens from transcript peaks.",
                fixes="Surfaces **obvious cut points** and titles that match what actually happens on the tape.",
                claim_id=claim_id,
                relevance=8,
                archetype_kind="packaging",
            )
        )

    # Genre nudges (non-exclusive; still issue-driven above)
    if genre and "history" in genre and not any("Narrative structure" in str(c.get("name")) for c in candidates):
        candidates.insert(
            0,
            _archetype_row_from_parts(
                name="Historical narrative specialist (timeline + causality)",
                role="Structure fix",
                why=f"History episodes win when listeners can track causality—not only topics—around {topic_short}.",
                look_for="Historians or storytellers who teach chronology as argument, not trivia.",
                fixes="Makes the episode feel **intentionally shaped** rather than encyclopedic.",
                claim_id=claim_id,
                archetype_kind="structure",
            ),
        )

    # Dedupe by name, then priority-sort (structure → … → packaging), then cap 2–3.
    seen: set[str] = set()
    uniq: List[Dict[str, Any]] = []
    for c in candidates:
        nm = str(c.get("name") or "")
        if not nm or nm in seen:
            continue
        seen.add(nm)
        uniq.append(c)

    out = _sort_archetypes_by_priority(uniq)[:max_archetypes]

    if not out:
        out = [
            _archetype_row_from_parts(
                name="Narrative structure specialist (arc & beats)",
                role="Structure fix",
                why=f"Ground the episode in one defensible arc about {topic_short} before adding more themes.",
                look_for="Guests who routinely impose story structure on complex material (story editors, narrative historians).",
                fixes="Improves clarity, pacing, and clip discoverability.",
                claim_id=claim_id,
                archetype_kind="structure",
            ),
            _archetype_row_from_parts(
                name="Contrarian or steel-manned opposing voice",
                role="Tension fix",
                why="Add a credible counter-case so the episode isn’t a monologue of agreement.",
                look_for="Experts who disagree without strawmen; historians with contested interpretations.",
                fixes="Creates tension segments listeners actually quote.",
                claim_id=claim_id,
                archetype_kind="tension",
            ),
            _archetype_row_from_parts(
                name="Modern application thinker (story → meaning → action)",
                role="Relevance fix",
                why="Translate the episode’s ideas into a next move your audience can try.",
                look_for="Practitioners who close loops: ‘here’s what changes in your week if this is true.’",
                fixes="Improves follow-through and shareability of takeaways.",
                claim_id=claim_id,
                archetype_kind="application",
            ),
        ][:max_archetypes]
    elif len(out) == 1 and max_archetypes >= 2:
        fillers = [
            _archetype_row_from_parts(
                name="Contrarian or steel-manned opposing voice",
                role="Tension fix",
                why="Add a credible counter-case so the episode isn’t a monologue of agreement.",
                look_for="Experts who disagree without strawmen; historians with contested interpretations.",
                fixes="Creates tension segments listeners actually quote.",
                claim_id=claim_id,
                archetype_kind="tension",
            ),
            _archetype_row_from_parts(
                name="Modern application thinker (story → meaning → action)",
                role="Relevance fix",
                why="Translate the episode’s ideas into a next move your audience can try.",
                look_for="Practitioners who close loops: ‘here’s what changes in your week if this is true.’",
                fixes="Improves follow-through and shareability of takeaways.",
                claim_id=claim_id,
                archetype_kind="application",
            ),
        ]
        names = {str(r.get("name") or "") for r in out}
        for f in _sort_archetypes_by_priority(fillers):
            nm = str(f.get("name") or "")
            if not nm or nm in names:
                continue
            names.add(nm)
            out.append(f)
            if len(out) >= max_archetypes:
                break

    out = _sort_archetypes_by_priority(out)[:max_archetypes]

    out = _label_archetype_sequence(out)
    if out:
        out[0] = dict(out[0])
        out[0]["commitment_line"] = _primary_commitment_line(out[0])
        out[0]["next_episode_move"] = _next_episode_move_for_kind(str(out[0].get("archetype_kind") or ""))
    # Replace archetype-only labels in `name` with real public figures (keep coaching fields).
    snap_os = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
    claims_os = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]
    subs_os = _extract_subject_entities_from_claims(claims_os)
    if not subs_os:
        for key in ("primary_topic", "title", "creator"):
            v = str(snap_os.get(key) or "").strip()
            if v:
                subs_os = [v]
                break
    dom_os = _infer_domain_from_entities(subs_os) if subs_os else "general_history"
    pool_os = _extended_outreach_pool(str(dom_os), claim_id, need=max(len(out), 3))
    if pool_os:
        for idx, row in enumerate(out):
            src = pool_os[idx % len(pool_os)]
            d = dict(row)
            d["name"] = str(src.get("name") or d.get("name") or "").strip()
            d["title"] = str(src.get("title") or d.get("title") or "").strip()
            out[idx] = d
    return out


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
            "neuroscientist",
            "neuroscience",
            "huberman",
            "brain plasticity",
            "neuroplasticity",
            "circadian",
            "dopamine",
            "brain function",
            "brain regeneration",
            "sensory system",
            "andrew huberman",
        )
    ):
        tshort = (primary_topic or title or "this conversation")[:140]
        return [
            {
                "name": "Dr. Robert Sapolsky",
                "title": "Neuroendocrinologist & stress / behavior science communicator",
                "role": "Neuroscience / behavior",
                "claim_id": claim_id,
                "angle": f"Pressures how strong 'brain change' and behavior claims can be from mechanisms—stress, habits, and plasticity in humans ({tshort[:72]}).",
                "topic_angle": "Mechanism, effect sizes, and common misconceptions",
                "relevance": 10,
            },
            {
                "name": "Dr. Matthew Walker",
                "title": "Sleep scientist & author (Why We Sleep)",
                "role": "Sleep / circadian",
                "claim_id": claim_id,
                "angle": "When the episode links brain function to sleep, performance, and recovery—separates settled science from pop framing.",
                "topic_angle": "Sleep, circadian timing, and cognitive outcomes",
                "relevance": 10,
            },
            {
                "name": "Dr. Lisa Feldman Barrett",
                "title": "Psychologist & affective / brain science (constructed emotion framework)",
                "role": "Affective / cognitive neuroscience (communication)",
                "claim_id": claim_id,
                "angle": "Guards against over-simple 'brain area does X' stories—how concepts and context shape what brains do on mic.",
                "topic_angle": "Constructs, language, and brain evidence",
                "relevance": 9,
            },
            {
                "name": "Science editor or health desk journalist",
                "title": "Editing / science communication",
                "role": "Science communication",
                "claim_id": claim_id,
                "angle": f"Tightens what can be said responsibly about neuroscience and behavior for a general audience around: {tshort[:90]}.",
                "topic_angle": "Clarity, hedging, and defensibility",
                "relevance": 8,
            },
            {
                "name": "Editorial producer / story editor",
                "title": "Structure",
                "role": "Editorial",
                "claim_id": claim_id,
                "angle": "Forces one thesis and one verification arc so clips map to a checkable through-line.",
                "topic_angle": "Packaging and defensibility",
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

    subs_for_domain: List[str] = []
    for x in (title, primary_topic):
        xs = str(x or "").strip()
        if xs:
            subs_for_domain.append(xs)
    for c in (r3.get("claims") or [])[:6]:
        if isinstance(c, dict):
            t = str(c.get("text") or "").strip()
            if len(t) >= 16:
                subs_for_domain.append(t[:260])
    domain = _infer_domain_from_entities(subs_for_domain) if subs_for_domain else "general_history"
    named = _extended_outreach_pool(domain, claim_id, need=5)
    if named:
        for idx, row in enumerate(named):
            row.setdefault("source", "topic_fallback_named_pool")
            row.setdefault("relevance", max(5, 10 - idx))
        return named[:5]
    fallback_named = _guest_rows_from_outreach_domain("general_history", claim_id, limit=5)
    if fallback_named:
        for idx, row in enumerate(fallback_named):
            row.setdefault("source", "topic_fallback_named_pool")
            row.setdefault("relevance", max(5, 10 - idx))
        return fallback_named[:5]
    topic = primary_topic or title or "this episode"
    return [
        {
            "name": "Editorial producer / story editor",
            "title": "Structure",
            "role": "Structure",
            "claim_id": claim_id,
            "angle": (
                f"Tightens thesis and clip strategy for: {topic[:120]} "
                "so listeners leave with one memorable through-line."
            ),
            "topic_angle": "Clarity and packaging",
            "relevance": 6,
            "source": "topic_fallback_last_resort",
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


# --- Episode-grounded individuals (verbatim from title / claims / evidence only; no invented names) ---

_ORGANIZATION_TAIL_MARKERS: Tuple[str, ...] = (
    " university",
    " institute",
    " foundation",
    " corporation",
    " department",
    " administration",
    " agency",
    " committee",
    " commission",
    " podcast",
    " network",
    " party",
    " government",
    " senate",
    " congress",
    " times",
    " post",
    " journal",
    " review",
)

_NON_PERSON_SUBSTRINGS: Tuple[str, ...] = (
    "policy",
    "policies",
    "timeline",
    "treaty",
    "battle",
    "federal",
    "federal ",
    " state ",
    "states ",
    "government",
    "congress",
    "senate",
    "removal",
    "removal ",
    "thesis",
    "argument",
    "episode",
    "narrative",
    "incentive",
    "market ",
    "economy",
)

_SINGLE_TOKEN_NON_PERSON: FrozenSet[str] = frozenset(
    {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
        "american",
        "western",
        "eastern",
        "northern",
        "southern",
        "european",
        "christian",
        "muslim",
        "jewish",
        "republican",
        "democratic",
        "democrat",
        "republicans",
        "democrats",
        "today",
        "tomorrow",
        "yesterday",
        "federal",
        "policy",
        "removal",
        "timelines",
        "test",
        "quote",
        "guest",
        "host",
        "episode",
        "transcript",
    }
)


def _likely_organization_span(span: str) -> bool:
    s = (span or "").strip().lower()
    if not s:
        return True
    return any(marker in s for marker in _ORGANIZATION_TAIL_MARKERS)


def _looks_like_person_span(span: str) -> bool:
    span = (span or "").strip()
    if not span or _likely_organization_span(span):
        return False
    low = span.lower()
    if any(tok in low for tok in _NON_PERSON_SUBSTRINGS):
        return False
    parts = span.split()
    if len(parts) >= 2:
        return all(p and p[0].isupper() for p in parts)
    if len(parts) == 1:
        p0 = parts[0]
        if len(p0) < 3 or not p0[0].isupper():
            return False
        return p0.lower() not in _SINGLE_TOKEN_NON_PERSON
    return False


def _title_guest_name_candidates(snap: Dict[str, Any]) -> List[str]:
    """Names explicitly signaled in episode title (podcast guest patterns)."""
    title = str(snap.get("title") or "").strip()
    if not title:
        return []
    out: List[str] = []
    for pat in (
        r"\(\s*with\s+([^)]+)\)",
        r"\bwith\s+([A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){1,4})",
    ):
        for m in re.findall(pat, title, flags=re.IGNORECASE):
            cand = str(m).strip(" -:;,.")
            if cand and _looks_like_person_span(cand):
                out.append(cand)
    for seg in re.split(r"\s+[-–—]\s+", title):
        seg = seg.strip()
        if not seg:
            continue
        seg = re.sub(r"^#?\d+\s*", "", seg).strip()
        m = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z'.-]+){1,4})$", seg)
        if m:
            cand = m.group(1).strip()
            if cand and _looks_like_person_span(cand):
                out.append(cand)
    dedup: List[str] = []
    seen: Set[str] = set()
    for n in out:
        k = _normalize_person_name(n)
        if not k or k in seen:
            continue
        seen.add(k)
        dedup.append(n.strip())
    return dedup[:6]


def _merged_person_spans_from_plain_text(text: str) -> List[str]:
    if not (text or "").strip():
        return []
    words: List[str] = []
    for raw in text.replace(",", " ").split():
        w = _normalize_subject_token(raw)
        if w:
            words.append(w)
    merged = _merge_capitalized_spans(words)
    out: List[str] = []
    for span in merged:
        if _looks_like_person_span(span):
            out.append(span.strip())
    return out


def _pick_claim_id_for_name(name: str, claim_rows: List[Dict[str, Any]]) -> str:
    nl = (name or "").lower()
    best = ""
    for c in claim_rows or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "")
        t = _safe_claim_text(c).lower()
        if nl and nl in t and cid:
            return cid
    if claim_rows and isinstance(claim_rows[0], dict):
        return str(claim_rows[0].get("id") or "")
    return ""


def _snippet_for_name_in_text(name: str, text: str, max_len: int = 200) -> str:
    if not name or not text:
        return ""
    low = text.lower()
    idx = low.find(name.lower())
    if idx < 0:
        return (text[:max_len] + ("…" if len(text) > max_len else "")).strip()
    start = max(0, idx - 40)
    end = min(len(text), idx + len(name) + 80)
    sn = text[start:end].strip()
    if start > 0:
        sn = "…" + sn
    if end < len(text):
        sn = sn + "…"
    if len(sn) > max_len:
        sn = sn[: max_len - 1] + "…"
    return sn


def _guest_rows_from_episode_grounded_individuals(
    r3: Dict[str, Any],
    claim_rows_for_subjects: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Real people **only** when their names appear verbatim in title, claims, or evidence quotes.
    Does not fabricate individuals to pad the guest table.
    """
    snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
    ordered_names: List[str] = []
    seen_n: Set[str] = set()

    def _add_name(n: str) -> None:
        n = (n or "").strip()
        if not n or not _looks_like_person_span(n):
            return
        k = _normalize_person_name(n)
        if not k or k in seen_n:
            return
        seen_n.add(k)
        ordered_names.append(n)

    for n in _title_guest_name_candidates(snap):
        _add_name(n)

    text_blobs: List[str] = []
    for c in claim_rows_for_subjects or []:
        t = _safe_claim_text(c)
        if t.strip():
            text_blobs.append(t)
    for row in r3.get("evidence_mapping") or []:
        if not isinstance(row, dict):
            continue
        ev = str(row.get("evidence") or "").strip()
        if ev:
            text_blobs.append(ev)
        cl = str(row.get("claim") or "").strip()
        if cl:
            text_blobs.append(cl)

    for blob in text_blobs:
        for span in _merged_person_spans_from_plain_text(blob):
            _add_name(span)

    rows: List[Dict[str, Any]] = []
    for name in ordered_names[:6]:
        claim_id = _pick_claim_id_for_name(name, claim_rows_for_subjects)
        angle_src = ""
        for blob in text_blobs:
            if name.lower() in blob.lower():
                angle_src = blob
                break
        angle = _snippet_for_name_in_text(name, angle_src or (text_blobs[0] if text_blobs else ""))
        rows.append(
            {
                "name": name,
                "title": "Named in this episode (verbatim text)",
                "role": "Episode figure",
                "claim_id": claim_id,
                "angle": angle or "Appears in episode title or structured claims / pull quotes.",
                "topic_angle": "Grounded in episode text — not a model-invented person.",
                "relevance": 10,
                "source": "episode_grounded_person",
            }
        )
    return rows


def _merge_grounded_guest_rows_first(
    grounded: List[Dict[str, Any]],
    other: List[Dict[str, Any]],
    *,
    max_rows: int = 8,
) -> List[Dict[str, Any]]:
    """Prefer verbatim people; keep other rows only for non-overlapping names."""
    if not grounded:
        return other
    gn = {_normalize_person_name(str(g.get("name") or "")) for g in grounded if str(g.get("name") or "").strip()}
    keep_other: List[Dict[str, Any]] = []
    for row in other or []:
        if not isinstance(row, dict):
            continue
        nm = _normalize_person_name(str(row.get("name") or ""))
        if nm and nm in gn:
            continue
        keep_other.append(row)
    return (list(grounded) + keep_other)[:max_rows]


def _report_v3_claim_rows_for_grounding(r3: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not r3 or not isinstance(r3, dict):
        return []
    cr = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]
    if cr:
        return cr
    ap = r3.get("atomic_pipeline")
    if isinstance(ap, dict):
        return [c for c in (ap.get("claims") or []) if isinstance(c, dict)]
    return []


def _grounded_guest_name_allowlist_for_workflow(
    report_v3: Optional[Dict[str, Any]],
    transcript: str,
) -> List[str]:
    """
    Verbatim people for LLM guest allowlists: v3 title/claims/evidence plus capitalized spans
    from transcript (conservative heuristics — no invented names).
    """
    names: List[str] = []
    seen: Set[str] = set()

    def _add(n: str) -> None:
        n = (n or "").strip()
        if not n or not _looks_like_person_span(n):
            return
        k = _normalize_person_name(n)
        if not k or k in seen:
            return
        seen.add(k)
        names.append(n)

    if report_v3 and isinstance(report_v3, dict):
        crs = _report_v3_claim_rows_for_grounding(report_v3)
        for g in _guest_rows_from_episode_grounded_individuals(report_v3, crs):
            if isinstance(g, dict):
                _add(str(g.get("name") or ""))

    for span in _merged_person_spans_from_plain_text((transcript or "")[:1_200_000]):
        _add(span)
        if len(names) >= 24:
            break
    return names[:24]


def _workflow_guest_rows_from_atomic_envelope(
    ap: Dict[str, Any],
    episode_snapshot: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Build workflow guest rows (``guests`` / ``guest_recommendations``) directly from the v3 report's ``atomic_pipeline``
    (envelope JSON). Decoupled from v3 ``guests`` list and from legacy generic-guest heuristics
    so atomic graph output is not lost when claim/label text does not round-trip through v3 rows.
    Each row sets ``source`` = ``atomic_pipeline`` for downstream debugging.

    ``name`` prefers **real public figures** from the static outreach pool; atomic role/topic stays in ``angle``.
    """
    raw = ap.get("guest_recommendations") or []
    if not isinstance(raw, list) or not raw:
        return []
    claims = [c for c in (ap.get("claims") or []) if isinstance(c, dict)]
    claim_by_id = {str(c.get("id")): c for c in claims if c.get("id")}
    primary_cid = next(iter(claim_by_id.keys()), "a1") if claim_by_id else "a1"
    subs = _extract_subject_entities_from_claims(claims)
    snap = episode_snapshot if isinstance(episode_snapshot, dict) else {}
    if not subs:
        for key in ("primary_topic", "title", "creator"):
            v = str(snap.get(key) or "").strip()
            if v:
                subs = [v]
                break
    domain = _infer_domain_from_entities(subs) if subs else "general_history"
    outreach_named = _guest_rows_from_outreach_domain(str(domain), str(primary_cid), limit=8)
    name_pool = [str(r.get("name") or "").strip() for r in outreach_named if str(r.get("name") or "").strip()]
    tg = ap.get("topic_graph") if isinstance(ap.get("topic_graph"), dict) else {}
    nodes = tg.get("nodes") if isinstance(tg.get("nodes"), list) else []
    topic_by_id = {
        str(n.get("topic_id")): n for n in nodes if isinstance(n, dict) and n.get("topic_id")
    }
    out: List[Dict[str, Any]] = []
    j = 0
    for g in raw:
        if not isinstance(g, dict):
            continue
        tid = str(g.get("target_topic_id") or "")
        topic = topic_by_id.get(tid) if tid else None
        if not isinstance(topic, dict):
            topic = {}
        label = str(topic.get("label") or "").strip() or "topic cluster"
        target_claim = ""
        for cid in topic.get("evidence_claim_ids") or []:
            bc = claim_by_id.get(str(cid))
            if bc:
                target_claim = _safe_claim_text(bc)
                break
        if not target_claim:
            for bc in claim_by_id.values():
                target_claim = _safe_claim_text(bc)
                if target_claim:
                    break
        gt = str(g.get("guest_type") or "academic")
        title_g = gt.replace("_", " ").title()
        reason = g.get("recommendation_reason") if isinstance(g.get("recommendation_reason"), dict) else {}
        why = str(reason.get("primary_angle") or "").strip()
        if not why:
            why = str(reason.get("what_they_would_challenge") or "").strip()
        role_ctx = f"{title_g} — {label[:120]}"
        display_name = name_pool[j % len(name_pool)] if name_pool else f"{title_g} — {label[:120]}"
        angle_text = why or _clean_claim_text(target_claim)[:240]
        if name_pool and role_ctx:
            angle_text = f"{angle_text} (Atomic angle: {role_ctx})" if angle_text else f"Atomic angle: {role_ctx}"
        claim_id = ""
        ecids = topic.get("evidence_claim_ids") or []
        if ecids:
            claim_id = str(ecids[j % len(ecids)])
        elif claim_by_id:
            klist = list(claim_by_id.keys())
            claim_id = str(klist[j % len(klist)])
        try:
            rs = float(g.get("relevance_score") or 0.0)
        except (TypeError, ValueError):
            rs = 0.0
        rel = int(min(10, max(5, round(5 + rs * 5))))
        out.append(
            {
                "name": display_name,
                "title": gt,
                "role": gt,
                "claim_id": claim_id,
                "angle": angle_text,
                "topic_angle": angle_text,
                "relevance": rel,
                "source": "atomic_pipeline",
            }
        )
        j += 1
    return out[:6]


_SUBJECT_FALLBACK_STOPWORDS = frozenset(
    {
        "The",
        "This",
        "That",
        "These",
        "Those",
        "They",
        "There",
        "Their",
        "When",
        "What",
        "Where",
        "Which",
        "While",
        "With",
        "Without",
        "Your",
        "Here",
        "Some",
        "Many",
        "Most",
        "People",
        "Someone",
        "But",
        "And",
        "For",
        "Not",
        "You",
        "All",
        "Can",
        "Her",
        "Was",
        "One",
        "Our",
        "Out",
        "Its",
        "His",
        "She",
        "Had",
        "Who",
        "How",
        "Why",
        "Such",
        "Also",
        "Like",
        "Just",
        "About",
        "Because",
        "After",
        "Before",
        "During",
        "Then",
        "Than",
        "From",
        "Into",
        "Being",
        "Been",
        "Have",
        "Will",
        "Would",
        "Could",
        "Should",
        "Every",
        "Each",
        "Other",
        "Another",
        "Even",
        "Only",
        "Very",
    }
)

# Leading/trailing punctuation on transcript tokens (commas, quotes, brackets) before cap checks.
_SUBJECT_TOKEN_STRIP_CHARS = ".,;:!?\"'()[]{}"


def _normalize_subject_token(raw: str) -> str:
    """Strip boundary punctuation so ``Wright,`` and ``(Robert`` normalize before ``isupper`` checks."""
    if not raw:
        return ""
    return raw.strip(_SUBJECT_TOKEN_STRIP_CHARS)


def _merge_capitalized_spans(words: List[str]) -> List[str]:
    """
    Merge consecutive capitalized tokens in **original word order** into entity-like spans.
    Lowercase / stopword tokens break the span so ``Robert met Billy`` yields two entities,
    not ``Robert Billy``.
    """
    merged: List[str] = []
    buffer: List[str] = []
    for w in words:
        w = _normalize_subject_token(w)
        if not w:
            continue
        ok = (
            len(w) > 2
            and w[0].isupper()
            and w not in _SUBJECT_FALLBACK_STOPWORDS
        )
        if ok:
            buffer.append(w)
        else:
            if buffer:
                merged.append(" ".join(buffer))
                buffer = []
    if buffer:
        merged.append(" ".join(buffer))
    return merged


def _score_claim_importance(claim: Any) -> float:
    """Heuristic narrative weight for a claim (structural only, no ML)."""
    text = _safe_claim_text(claim)
    score = 0.0
    score += min(len(text) / 200.0, 2.0)
    for raw in text.split():
        w = _normalize_subject_token(raw)
        if w and w[0].isupper():
            score += 0.2
    triggers = (
        "killed",
        "warning",
        "refused",
        "hired",
        "departed",
        "rumor",
        "death",
    )
    low = text.lower()
    score += sum(0.5 for t in triggers if t in low)
    return score


def _extract_subject_entities_from_claims(claims: List[Any]) -> List[str]:
    """
    Tier-2 subject extraction when atomic graph guests are empty: merged spans, claim-weighted
    ranking, deduped.
    """
    raw_entities: List[str] = []
    weighted_entities: List[Tuple[str, float]] = []

    for c in claims or []:
        text = _safe_claim_text(c)
        if not text.strip():
            continue
        importance = _score_claim_importance(c)
        words: List[str] = []
        for raw in text.replace(",", " ").split():
            w = _normalize_subject_token(raw)
            if w:
                words.append(w)
        merged = _merge_capitalized_spans(words)
        for m in merged:
            raw_entities.append(m)
            weighted_entities.append((m, importance))

    freq: Dict[str, int] = {}
    for e in raw_entities:
        freq[e] = freq.get(e, 0) + 1

    ranked = sorted(
        weighted_entities,
        key=lambda x: (x[1], freq.get(x[0], 0)),
        reverse=True,
    )

    seen: Set[str] = set()
    out: List[str] = []
    for name, _ in ranked:
        if name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= 10:
            break

    return out


def _infer_domain_from_entities(entities: List[str]) -> str:
    """Map extracted entity names to a coarse subject domain (rule-based, no LLM)."""
    blob = " ".join(entities).lower()
    if any(
        k in blob
        for k in (
            "neuroscientist",
            "neuroscience",
            "neuroplasticity",
            "brain plasticity",
            "huberman",
            "andrew huberman",
            "circadian",
            "dopamine",
            "cortisol",
            "optogenetics",
            "synapse",
            "hippocampus",
            "amygdala",
            "prefrontal",
            "sensory system",
            "physiology",
            "brain regeneration",
        )
    ):
        return "neuroscience_health"
    if any(
        k in blob
        for k in (
            "rockefeller",
            "carnegie",
            "foundation",
            "education system",
            "school system",
            "curriculum",
            "standardized",
            "common core",
            "pedagogy",
            "charter school",
            "department of education",
            "brainwash",
            "psyop",
        )
    ):
        return "education_policy"
    if any(k in blob for k in ("billy", "jesse", "outlaw", "miller", "killer")):
        return "outlaw_history"
    if any(k in blob for k in ("lawman", "sheriff", "deputy", "marshal", "posse")):
        return "law_enforcement_history"
    if any(k in blob for k in ("war", "tribe", "perce", "native", "nez")):
        return "indigenous_history"
    if any(k in blob for k in ("trade", "economy", "network", "market")):
        return "economic_history"
    return "general_history"


_DOMAIN_GUEST_MAP: Dict[str, List[Tuple[str, str]]] = {
    "outlaw_history": [
        ("True Crime Historian", "Expert in outlaw networks and frontier violence"),
        ("Western Author", "Focuses on historical outlaw figures and narratives"),
    ],
    "law_enforcement_history": [
        ("Legal Historian", "Studies early law enforcement systems"),
        ("Criminologist", "Analyzes patterns of crime and enforcement"),
    ],
    "indigenous_history": [
        ("Indigenous Historian", "Focuses on Native American history and conflict"),
        ("Anthropologist", "Studies tribal systems and cultural dynamics"),
    ],
    "economic_history": [
        ("Economic Historian", "Analyzes trade systems and incentives"),
    ],
    "general_history": [
        ("Historian", "General expertise in historical analysis and context"),
    ],
}


# Static outreach layer: real experts + podcasts to contact (no API; expand per domain over time).
_OUTREACH_BY_DOMAIN: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "outlaw_history": {
        "experts": [
            {
                "name": "Tom Clavin",
                "type": "author",
                "why": "Writes extensively on Old West lawmen and outlaws (Wyatt Earp, Tombstone).",
                "angle": "How myth vs reality shaped figures like Jesse Evans and frontier violence.",
                "best_fit": "Narrative/history breakdown episodes.",
                "outreach_hook": (
                    "We’re breaking down overlooked outlaw networks and wanted someone who understands "
                    "how these stories get distorted over time."
                ),
            },
            {
                "name": "T.J. Stiles",
                "type": "author",
                "why": "Pulitzer Prize–winning biographer (Jesse James).",
                "angle": "Economic and social incentives behind outlaw behavior.",
                "best_fit": "Deeper analytical episode.",
                "outreach_hook": (
                    "We’re exploring how outlaw figures weren’t just criminals but products of "
                    "economic systems."
                ),
            },
            {
                "name": "Michael Wallis",
                "type": "author",
                "why": "Leading voice on the American West (Billy the Kid, Route 66).",
                "angle": "Storytelling vs historical truth in the Wild West.",
                "best_fit": "Audience-friendly storytelling episode.",
                "outreach_hook": (
                    "We’re unpacking how Wild West stories get romanticized vs what actually happened."
                ),
            },
            {
                "name": "Anne F. Hyde",
                "type": "historian",
                "why": "Cultural and Indigenous intersections in the West.",
                "angle": "Power structures, violence, and identity in frontier systems.",
                "best_fit": "More academic / serious angle.",
                "outreach_hook": (
                    "We’re trying to understand how power and violence actually operated on the "
                    "frontier beyond the myths."
                ),
            },
        ],
        "podcasts": [
            {
                "name": "Legends of the Old West",
                "why": "Direct overlap with frontier outlaw and lawman narratives.",
                "pitch_angle": (
                    "We’ve built a system that breaks Wild West narratives into structured insights—"
                    "would love to explore a deep-dive collaboration."
                ),
            },
            {
                "name": "The Wild West Podcast",
                "why": "Same niche with a consistent audience.",
                "pitch_angle": (
                    "We analyze how outlaw stories connect across episodes and time periods—"
                    "curious if a crossover fits your format."
                ),
            },
            {
                "name": "Hardcore History",
                "why": "Aspirational; aligns with long-form narrative breakdowns.",
                "pitch_angle": (
                    "We’re building tools that turn long-form history into structured, analyzable narratives."
                ),
            },
            {
                "name": "True Crime Garage",
                "why": "Bridges outlaw history to broader true-crime listeners.",
                "pitch_angle": (
                    "We’re exploring early American crime systems and how they compare to modern patterns."
                ),
            },
        ],
    },
    "law_enforcement_history": {
        "experts": [
            {
                "name": "Paul R. Spitzer",
                "type": "historian",
                "why": "U.S. marshals, posses, and frontier policing.",
                "angle": "How formal and informal enforcement coexisted on the frontier.",
                "best_fit": "Law-and-order vs vigilante themes.",
                "outreach_hook": (
                    "We’re dissecting how law enforcement narratives form—and where the record disagrees."
                ),
            },
        ],
        "podcasts": [
            {
                "name": "Criminal",
                "why": "Crime and justice storytelling with a broad audience.",
                "pitch_angle": "We connect historical enforcement patterns to how we tell crime stories today.",
            },
        ],
    },
    "indigenous_history": {
        "experts": [
            {
                "name": "Pekka Hämäläinen",
                "type": "historian",
                "why": "Indigenous power and diplomacy on the North American continent.",
                "angle": "Centering Native nations in frontier conflict narratives.",
                "best_fit": "Serious historical treatment of power and survival.",
                "outreach_hook": (
                    "We want voices who foreground Indigenous agency—not just as backdrop to frontier myths."
                ),
            },
        ],
        "podcasts": [
            {
                "name": "This Land",
                "why": "Indigenous politics and history.",
                "pitch_angle": "We’re grounding podcast narratives in structured claims about power and land.",
            },
        ],
    },
    "economic_history": {
        "experts": [
            {
                "name": "Bradford DeLong",
                "type": "economist",
                "why": "Long-run economic history and incentives.",
                "angle": "Markets, coercion, and institutions in historical context.",
                "best_fit": "Analytical episodes on systems, not just events.",
                "outreach_hook": (
                    "We’re linking episode claims to how economic incentives actually operated."
                ),
            },
        ],
        "podcasts": [
            {
                "name": "Planet Money",
                "why": "Accessible economics storytelling.",
                "pitch_angle": "We extract testable claims from episodes—economic angles are a natural fit.",
            },
        ],
    },
    "neuroscience_health": {
        "experts": [
            {
                "name": "Robert Sapolsky",
                "type": "neuroscientist / primatologist",
                "why": "Stress, behavior, and how brain narratives get oversimplified in public talk.",
                "angle": "Separates mechanistic strength from pop-brain storylines.",
                "best_fit": "Neuroscience and behavior longforms where listeners may over-trust a simple mechanism.",
                "outreach_hook": (
                    "We extracted testable brain/behavior claims and want a mechanism-literate read—not vibes."
                ),
            },
            {
                "name": "Matthew Walker",
                "type": "sleep scientist",
                "why": "Sleep, circadian timing, and how performance claims should be qualified.",
                "angle": "Prevents 'sleep = magic bullet' overclaims; grounds outcomes in what is well-supported.",
                "best_fit": "Episodes linking brain health, recovery, and daily routines.",
                "outreach_hook": "We want sleep-science defensibility for claims listeners will repeat in clips.",
            },
            {
                "name": "Lisa Feldman Barrett",
                "type": "psychologist / cognitive neuroscience (emotion)",
                "why": "How language and context shape 'brain' explanations for broad audiences.",
                "angle": "Catches over-simple 'this brain region does that' public narratives.",
                "best_fit": "Episodes that mix emotion, mind, and neuroscience storytelling.",
                "outreach_hook": "We want an accuracy pass on how brain claims are phrased for a general show.",
            },
        ],
        "podcasts": [
            {
                "name": "Huberman Lab",
                "why": "Deep-dive science communication for a broad audience.",
                "pitch_angle": "We’re structuring claims the way serious science comm episodes should be stress-tested.",
            },
        ],
    },
    "education_policy": {
        "experts": [
            {
                "name": "Diane Ravitch",
                "type": "historian",
                "why": "U.S. education policy, reform narratives, and what evidence actually supports.",
                "angle": "Separates reform rhetoric from classroom and institutional reality.",
                "best_fit": "Episodes debating school systems, standards, and incentives.",
                "outreach_hook": (
                    "We’re stress-testing claims about who shaped schools and what the record shows."
                ),
            },
            {
                "name": "Jonathan Kozol",
                "type": "author",
                "why": "Inequality, schooling, and how policy lands in real districts.",
                "angle": "Grounds abstract ‘systems’ talk in lived outcomes.",
                "best_fit": "Human-impact framing for education episodes.",
                "outreach_hook": (
                    "We want someone who can connect policy claims to what happens in classrooms."
                ),
            },
            {
                "name": "E.D. Hirsch Jr.",
                "type": "education scholar",
                "why": "Curriculum, cultural literacy, and what ‘standards’ actually change.",
                "angle": "Tests whether the episode’s causal story about schooling holds up.",
                "best_fit": "Curriculum- and standards-heavy episodes.",
                "outreach_hook": (
                    "We’re validating how curriculum and incentives interact in the claims we extracted."
                ),
            },
        ],
        "podcasts": [
            {
                "name": "Have You Heard",
                "why": "Education policy and research for a general audience.",
                "pitch_angle": "We structured claims about schooling—looking for policy-literate crossover.",
            },
        ],
    },
    "general_history": {
        "experts": [
            {
                "name": "Jill Lepore",
                "type": "historian",
                "why": "American political and cultural history; narrative craft for serious audiences.",
                "angle": "Separates myth from record and sharpens how claims are framed.",
                "best_fit": "Credibility pass on a narrative-heavy episode.",
                "outreach_hook": (
                    "We’re stress-testing our episode’s claims against the historical record—"
                    "would value your read."
                ),
            },
            {
                "name": "David W. Blight",
                "type": "historian",
                "why": "U.S. history, memory, and how public stories form around events.",
                "angle": "Pressure-tests emotional beats against documented context.",
                "best_fit": "Episodes where the story risks outpacing the evidence.",
                "outreach_hook": (
                    "We want a historian’s eye on whether our through-line matches how the field reads the sources."
                ),
            },
        ],
        "podcasts": [
            {
                "name": "Show in your niche with overlapping audience",
                "why": "Faster wins than cold-contacting only major names.",
                "pitch_angle": (
                    "We structured this episode’s thesis and claims—happy to share a one-pager for a fit check."
                ),
            },
        ],
    },
}


def _looks_like_specific_person_name(name: str) -> bool:
    """Reject generic outreach placeholders; accept Firstname Lastname–style public figures."""
    s = (name or "").strip()
    if len(s) < 4:
        return False
    low = s.lower()
    if any(
        x in low
        for x in (
            "public historian",
            "university faculty",
            "faculty (local)",
            "/ university",
            "hypothetical",
            "placeholder",
            "podcast in your niche",
            "show in your niche",
        )
    ):
        return False
    role_only = {
        "historian",
        "criminologist",
        "anthropologist",
        "economist",
        "author",
        "expert",
        "journalist",
        "researcher",
        "psychologist",
        "sociologist",
    }
    if low in role_only:
        return False
    parts = [p.strip(" .,\"'") for p in re.split(r"[\s,]+", s) if p.strip(" .,\"'\t")]
    alpha = [p for p in parts if any(c.isalpha() for c in p)]
    return len(alpha) >= 2


def _guest_rows_from_outreach_domain(domain: str, claim_id: str, *, limit: int = 6) -> List[Dict[str, Any]]:
    """Bookable rows backed by the static outreach pool (real names, not job-title-only labels)."""
    block = _OUTREACH_BY_DOMAIN.get(domain) or _OUTREACH_BY_DOMAIN.get("general_history") or {}
    experts = list(block.get("experts") or [])
    rows: List[Dict[str, Any]] = []
    for idx, ex in enumerate(experts[:limit]):
        nm = str(ex.get("name") or "").strip()
        if not _looks_like_specific_person_name(nm):
            continue
        typ = str(ex.get("type") or "expert").strip()
        why = str(ex.get("why") or "").strip()
        ang = str(ex.get("angle") or "").strip()
        bf = str(ex.get("best_fit") or "").strip()
        rows.append(
            {
                "name": nm,
                "title": typ.title() if typ else "Expert",
                "role": "subject_matter_expert",
                "claim_id": claim_id,
                "angle": why or ang,
                "topic_angle": bf or ang or why or domain.replace("_", " ").title(),
                "relevance": max(5, 10 - idx),
                "source": "subject_fallback_tier3",
                "reason": "named_public_figure_outreach_pool",
            }
        )
    return rows


def _extended_outreach_pool(domain: str, claim_id: str, *, need: int) -> List[Dict[str, Any]]:
    """Enough distinct real names for overlaying archetype rows (falls back across domains)."""
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for dom in (
        domain,
        "neuroscience_health",
        "education_policy",
        "general_history",
        "outlaw_history",
        "economic_history",
    ):
        for r in _guest_rows_from_outreach_domain(str(dom), claim_id, limit=need):
            nm = str(r.get("name") or "").strip()
            if nm and nm not in seen:
                seen.add(nm)
                out.append(r)
            if len(out) >= need:
                return out
    return out


def _named_guest_rows_for_topic_r3(r3: Dict[str, Any], claim_id: str, *, need: int = 5) -> List[Dict[str, Any]]:
    """
    Bookable **named** rows for padding guest recommendations (avoids generic role-only archetypes).
    """
    snap = r3.get("episode_snapshot") or {}
    title = str(snap.get("title") or "").strip()
    primary_topic = str(snap.get("primary_topic") or "").strip()
    subs: List[str] = []
    for x in (title, primary_topic):
        if x:
            subs.append(x)
    for c in (r3.get("claims") or [])[:8]:
        if isinstance(c, dict):
            t = str(c.get("text") or "").strip()
            if len(t) >= 12:
                subs.append(t[:280])
    for ins in (r3.get("clean_insights") or [])[:5]:
        s = str(ins).strip()
        if len(s) >= 12:
            subs.append(s[:280])
    domain = _infer_domain_from_entities(subs) if subs else "general_history"
    rows = _extended_outreach_pool(domain, claim_id, need=max(need, 4))
    for i, r in enumerate(rows):
        r.setdefault("source", "named_outreach_pad")
        r.setdefault("relevance", max(5, 10 - i))
    return rows[:need]


def _outreach_targets_for_domain(domain: str) -> Dict[str, Any]:
    """Return static expert + podcast outreach lists for a domain key (deal-flow layer)."""
    block = _OUTREACH_BY_DOMAIN.get(domain) or _OUTREACH_BY_DOMAIN["general_history"]
    return {
        "domain_key": domain,
        "domain_label": domain.replace("_", " ").title(),
        "experts": [dict(e) for e in block.get("experts") or []],
        "podcasts": [dict(p) for p in block.get("podcasts") or []],
    }


def _should_emit_guest_outreach_targets(
    guest_recommendations: List[Any],
    *,
    guests_from_subject_fallback: bool,
    claim_rows_for_subjects: List[Dict[str, Any]],
) -> bool:
    """
    True when Tier-3 / subject-fallback guests warrant the outreach bundle.
    Uses ``guests_from_subject_fallback`` (survives minor ``source`` string drift) plus a loose
    ``tier3`` substring check on row sources.
    """
    if claim_rows_for_subjects and guests_from_subject_fallback:
        return True
    if claim_rows_for_subjects:
        for g in guest_recommendations or []:
            if isinstance(g, dict) and str(g.get("source") or "") == "episode_grounded_person":
                return True
    for g in guest_recommendations or []:
        if not isinstance(g, dict):
            continue
        src = str(g.get("source") or "").lower()
        if "tier3" in src:
            return True
    return False


def _build_intelligent_guest_rows(
    subjects: List[str],
    claims: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Tier 3: map episode entities → domain → **named** public figures from the outreach pool.

    Falls back to role-only rows only when no vetted names exist for the domain.
    """
    claim_rows = claims or []
    domain = _infer_domain_from_entities(subjects)
    cid0 = ""
    if claim_rows and isinstance(claim_rows[0], dict):
        cid0 = str(claim_rows[0].get("id") or "")
    sig = ", ".join(subjects[:8])
    main = _guest_rows_from_outreach_domain(domain, cid0, limit=6)
    for row in main:
        row.setdefault("entity_signals", sig)
        row.setdefault("reason", "named_public_figure_outreach_pool")
    if main:
        return main

    archetypes = _DOMAIN_GUEST_MAP.get(domain) or _DOMAIN_GUEST_MAP["general_history"]
    rows: List[Dict[str, Any]] = []
    for idx, (title, angle) in enumerate(archetypes[:5]):
        rows.append(
            {
                "name": title,
                "title": title,
                "role": "subject_matter_expert",
                "claim_id": cid0,
                "angle": angle,
                "topic_angle": domain.replace("_", " ").title(),
                "relevance": max(5, 10 - idx),
                "source": "subject_fallback_tier3",
                "reason": "derived_from_entity_domain_mapping",
                "entity_signals": sig,
            }
        )
    return rows


def _subject_fallback_guest_rows_from_report_claims(
    r3: Dict[str, Any],
    claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Prefer **bookable expert angles** (domain archetypes from claim entities), not transcript figures.

    Verbatim people from the tape stay out of the primary guest table; use archetypes / issues-based
    rows so hosts see historians, analysts, and producers — not Jesse James as a suggested guest.
    """
    if not claims:
        return []
    subj = _extract_subject_entities_from_claims(claims)
    if subj:
        built = _build_intelligent_guest_rows(subj, claims)
        if built:
            return built
    cid = str(claims[0].get("id") or "c1")
    arch = generate_guest_archetypes_from_issues(r3, cid, max_archetypes=4)
    if arch:
        return arch
    return _topic_specific_guest_fallback(r3, cid)


_BOOKING_TITLE_BY_GUEST_NAME: Dict[str, str] = {
    "diane ravitch": "Education policy historian",
    "jonathan kozol": "Author & public education advocate",
    "e.d. hirsch jr.": "Education scholar (cultural literacy)",
    "e.d. hirsch": "Education scholar (cultural literacy)",
    "jill lepore": "Historian & essayist",
    "david w. blight": "Historian (American slavery & memory)",
    "katy milkman": "Behavioral scientist",
    "diane f. halpern": "Psychologist (critical thinking)",
}


def _workflow_title_for_coach_strategy_guest(name: str) -> str:
    """
    ``coach_report.guest_strategy`` rows use ``guest_type`` as the display name and historically
    set ``title`` to the meaningless word *Suggested* for the workflow table. Map known public
    figures to a real booking title; otherwise use a neutral professional label.
    """
    nm = (name or "").strip()
    if not nm:
        return "Expert guest"
    key = re.sub(r"\s+", " ", nm.lower()).strip()
    if key in _BOOKING_TITLE_BY_GUEST_NAME:
        return _BOOKING_TITLE_BY_GUEST_NAME[key]
    parts = nm.split()
    if len(parts) >= 2 and parts[0][0:1].isupper():
        return "Expert guest (booking target)"
    if len(parts) == 1 and nm[0:1].isupper() and len(nm) > 3:
        return "Expert guest"
    return nm[:56] + ("…" if len(nm) > 56 else "")


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
    snap = dict(r3.get("episode_snapshot") or {})
    try:
        from .episode_intelligence import (
            _primary_topic_is_crime_news_template,
            _refine_genre_from_title,
            _sanitize_episode_snapshot,
            _title_signals_education_or_institutions_history,
            override_primary_topic_with_storyline,
        )
    except ImportError:
        from episode_intelligence import (
            _primary_topic_is_crime_news_template,
            _refine_genre_from_title,
            _sanitize_episode_snapshot,
            _title_signals_education_or_institutions_history,
            override_primary_topic_with_storyline,
        )

    _sanitize_episode_snapshot(snap, claims)
    # Belt & braces: refine genre on the workflow snapshot too so downstream renderers never
    # echo a stale "Entertainment" label when the title clearly signals education / politics / etc.
    snap["genre"] = _refine_genre_from_title(
        str(snap.get("title") or ""), str(snap.get("genre") or "")
    )
    evidence_map = _sanitize_evidence_map_claims(
        evidence_map,
        spine_hint=f"{snap.get('title') or ''} {snap.get('primary_topic') or ''}".strip(),
    )
    # Subject / entity extraction may need atomic or evidence rows when top-level claims is empty.
    claim_rows_for_subjects = claims or _workflow_claim_rows_for_subject_fallback(r3)

    guest_recommendations: List[Dict[str, Any]] = []
    guests_from_atomic_envelope = False
    guests_from_subject_fallback = False
    ap = r3.get("atomic_pipeline")
    if isinstance(ap, dict) and ap:
        ag = _workflow_guest_rows_from_atomic_envelope(
            ap,
            r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else None,
        )
        if ag:
            guest_recommendations = ag
            guests_from_atomic_envelope = True

    if not guest_recommendations:
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
                    "title": _workflow_title_for_coach_strategy_guest(gt),
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
        sf = _subject_fallback_guest_rows_from_report_claims(r3, claim_rows_for_subjects)
        if sf:
            guest_recommendations = sf
            guests_from_subject_fallback = True
    if not guest_recommendations:
        snap = r3.get("episode_snapshot") or {}
        topic = str(snap.get("primary_topic") or snap.get("title") or "this episode")[:120]
        cid = str(claims[0].get("id")) if claims else (
            str(claim_rows_for_subjects[0].get("id")) if claim_rows_for_subjects else ""
        )
        if _guest_generation_required(r3):
            guest_recommendations = generate_guest_archetypes_from_issues(r3, cid or "c1")
        if not guest_recommendations:
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
    cid_fallback = (
        str(claims[0].get("id"))
        if claims
        else (str(claim_rows_for_subjects[0].get("id")) if claim_rows_for_subjects else "c1")
    )
    if (
        not guests_from_atomic_envelope
        and not guests_from_subject_fallback
        and _guest_rows_are_generic(guest_recommendations)
    ):
        if _guest_generation_required(r3):
            arch = generate_guest_archetypes_from_issues(r3, cid_fallback)
            guest_recommendations = arch if len(arch) >= 2 else _topic_specific_guest_fallback(r3, cid_fallback)
        else:
            guest_recommendations = _topic_specific_guest_fallback(r3, cid_fallback)
    excluded_names = _extract_in_episode_names(r3)
    guest_recommendations = _filter_already_featured_guests(guest_recommendations, excluded_names)
    if not guest_recommendations:
        sf = _subject_fallback_guest_rows_from_report_claims(r3, claim_rows_for_subjects)
        if sf:
            guest_recommendations = sf
            guests_from_subject_fallback = True
    if not guest_recommendations:
        guest_recommendations = _filter_already_featured_guests(
            _topic_specific_guest_fallback(r3, cid_fallback),
            excluded_names,
        )
    if (
        not guests_from_atomic_envelope
        and not guests_from_subject_fallback
        and len(guest_recommendations) < 4
    ):
        if not any(isinstance(g, dict) and g.get("guest_archetype") for g in guest_recommendations):
            extras = _filter_already_featured_guests(
                _named_guest_rows_for_topic_r3(r3, cid_fallback, need=5),
                excluded_names,
            )
            guest_recommendations = _dedupe_guest_rows(guest_recommendations + extras)
    guest_recommendations = guest_recommendations[:5]

    if _guest_generation_required(r3) and not guest_recommendations:
        guest_recommendations = generate_guest_archetypes_from_issues(r3, cid_fallback)
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
    storylines = [str(x).strip() for x in (aa.get("what_worked") or []) if str(x).strip()]
    title_s = str(snap.get("title") or "").strip()
    if title_s and _title_signals_education_or_institutions_history(title_s):
        storylines = [x for x in storylines if not _primary_topic_is_crime_news_template(x)]
    if not storylines:
        pt_line = str(snap.get("primary_topic") or "").strip()
        if pt_line and not _primary_topic_is_crime_news_template(pt_line):
            storylines = [pt_line[:280]]
        elif title_s and len(title_s) > 12:
            storylines = [f"Through-line (from title/theme): {title_s[:220]}"]
    analytics = {
        "storylines": storylines[:5],
        "topic_signals": list(aa.get("what_failed") or []),
        "actionable_steps": list(aa.get("next_move") or []),
    }

    # Second-pass primary_topic override now that analytics.storylines is available.
    # Without this, the top-of-report "Core Narrative" can still show a stale crime-beat template
    # (or the raw clickbait title) even though analytics correctly extracted the real thesis.
    override_primary_topic_with_storyline(
        snap,
        storylines=analytics.get("storylines"),
        narrative=(r3.get("narrative") if isinstance(r3.get("narrative"), list) else None),
    )
    # Propagate the sanitized + storyline-overridden snap back to r3 so the appendix / downstream
    # renderers read the corrected primary_topic rather than the raw brief snapshot.
    if isinstance(r3.get("episode_snapshot"), dict):
        r3["episode_snapshot"]["primary_topic"] = snap.get("primary_topic")
        if snap.get("why_it_matters"):
            r3["episode_snapshot"]["why_it_matters"] = snap.get("why_it_matters")

    # Final circuit breaker before serializing workflow JSON (nothing below may clear guests).
    if not guest_recommendations and claim_rows_for_subjects:
        tier3 = _subject_fallback_guest_rows_from_report_claims(r3, claim_rows_for_subjects)
        if tier3:
            guest_recommendations = tier3
            guests_from_subject_fallback = True

    guest_outreach_targets: Optional[Dict[str, Any]] = None
    if _should_emit_guest_outreach_targets(
        guest_recommendations,
        guests_from_subject_fallback=guests_from_subject_fallback,
        claim_rows_for_subjects=claim_rows_for_subjects,
    ):
        subj_oo = _extract_subject_entities_from_claims(claim_rows_for_subjects)
        dom = _infer_domain_from_entities(subj_oo) if subj_oo else "general_history"
        guest_outreach_targets = _outreach_targets_for_domain(dom)

    out: Dict[str, Any] = {
        "highlights": highlights,
        "evidence_map": evidence_map,
        "follow_up_questions": follow_up,
        "guests": guest_recommendations,
        "guest_recommendations": guest_recommendations,
        "segments": segments,
        "analytics": analytics,
        "guests_from_subject_fallback": guests_from_subject_fallback,
    }
    if guest_outreach_targets is not None:
        out["guest_outreach_targets"] = guest_outreach_targets
    _sanitize_workflow_highlights(
        out,
        spine_hint=f"{snap.get('title') or ''} {snap.get('primary_topic') or ''}".strip(),
    )
    sm = r3.get("signal_mode")
    if sm:
        out["signal_mode"] = sm
    cr = r3.get("coach_report")
    if cr:
        out["coach_report"] = cr
    return out


def _workflow_fallback_evidence_enabled() -> bool:
    """Synthetic scaffold claims (discouraged). Default off — use ``SOAPBOXX_WORKFLOW_FALLBACK_EVIDENCE=1`` to enable."""
    return (os.getenv("SOAPBOXX_WORKFLOW_FALLBACK_EVIDENCE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _ensure_fallback_evidence(
    report: Dict[str, Any], transcript: str
) -> None:
    """If offline produced no evidence rows, optionally add one anchor (legacy; off by default)."""
    if report.get("evidence_map"):
        return
    if not _workflow_fallback_evidence_enabled():
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
    # Neutral claim when the v2 brief is empty/offline — avoid topic-mismatched boilerplate.
    claim_line = (
        "Primary tension (edit to fit): pick one argumentative through-line from the tape, "
        "then align clips and follow-ups to that line — verify against the excerpt below."
    )
    report["evidence_map"] = [
        {
            "id": "c1",
            "claim": claim_line,
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

    AI steps fill highlights, evidence_map, follow_up_questions, guests (legacy ``guest_recommendations`` alias), segments, analytics.

    Pass ``report_v3`` (and optional ``brief_warnings``) to reuse an already-built v3 report and avoid a
    second ``generate_episode_report_v3`` call (e.g. from ``FeedbackEngine.generate_network_brief_v3``).
    """
    try:
        from .episode_report_v3 import generate_episode_report_v3
    except ImportError:
        from episode_report_v3 import generate_episode_report_v3

    transcript_cues = _normalize_transcript_cues(metadata.get("transcript_cues"))
    meta = {
        k: str(v)
        for k, v in metadata.items()
        if v is not None and k != "transcript_cues"
    }
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
    trace_id = str(metadata.get("trace_id") or metadata.get("run_id") or uuid.uuid4())
    meta_out["trace_id"] = trace_id
    try:
        from .ollama_chat_http import reset_transport_log, set_trace_id
    except ImportError:
        from ollama_chat_http import reset_transport_log, set_trace_id  # type: ignore
    reset_transport_log()
    set_trace_id(trace_id)
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
                    transcript or "",
                    body,
                    client=llm_client,
                    episode_meta=enrich_meta,
                    report_v3=r3,
                )
                enrich_tier = "full"
            else:
                body = enrich_workflow_report_minimal(
                    transcript or "",
                    body,
                    client=llm_client,
                    episode_meta=enrich_meta,
                    report_v3=r3,
                )
                enrich_tier = "minimal"
            mode = "local+ai"
            if _atomic_structure_lock_from_report_v3(r3):
                meta_out["atomic_structure_lock_applied"] = True
        except Exception as e:
            source_warnings.append(f"AI workflow enrichment failed: {e}")
            try:
                from .ollama_chat_http import OllamaTransportError
            except ImportError:
                from ollama_chat_http import OllamaTransportError  # type: ignore

            cur: Optional[BaseException] = e
            while cur:
                if isinstance(cur, OllamaTransportError):
                    meta_out["ollama_transport_degraded"] = True
                    break
                cur = cur.__cause__

    _run_v3_reality_check_into_meta(r3, transcript or "", meta_out, source_warnings)

    meta_out["workflow_mode"] = mode
    meta_out["workflow_enrichment_tier"] = enrich_tier
    meta_out["source_warnings"] = source_warnings
    try:
        from .ollama_chat_http import get_transport_log
    except ImportError:
        from ollama_chat_http import get_transport_log  # type: ignore
    _ote = get_transport_log()
    if _ote:
        meta_out["ollama_transport_events"] = _ote
        _last_bad = next((x for x in reversed(_ote) if not x.get("ok")), None)
        if _last_bad and _last_bad.get("failure_code"):
            meta_out["ollama_last_transport_failure_code"] = _last_bad["failure_code"]
    _apply_workflow_version_metadata(meta_out)

    report: Dict[str, Any] = {
        "metadata": meta_out,
        **body,
    }
    try:
        from .transcript_structure_extract import apply_rule_based_structure_bootstrap
    except ImportError:
        from transcript_structure_extract import apply_rule_based_structure_bootstrap  # type: ignore

    apply_rule_based_structure_bootstrap(report, r3, transcript or "")
    _prune_follow_up_questions_to_evidence_map(report)
    try:
        from .evaluation_pipeline import (
            build_evaluation_snapshot,
            evaluate_snapshot,
            finalize_evaluation,
        )
    except ImportError:
        from evaluation_pipeline import (  # type: ignore
            build_evaluation_snapshot,
            evaluate_snapshot,
            finalize_evaluation,
        )

    eval_meta = {
        "run_id": "",
        "trace_id": str(meta_out.get("trace_id") or ""),
        "episode_id": str(metadata.get("episode_id") or metadata.get("title") or ""),
        "title": str(metadata.get("title") or ""),
        "creator": str(metadata.get("creator") or ""),
        "genre": str(metadata.get("genre") or ""),
    }
    try:
        from .episode_report_v3 import strict_export_enabled
    except ImportError:
        from episode_report_v3 import strict_export_enabled  # type: ignore
    eval_meta["strict_export_enabled"] = strict_export_enabled()

    snapshot = build_evaluation_snapshot(report, r3, eval_meta)
    evaluation = evaluate_snapshot(snapshot)
    finalize_evaluation(
        meta_out,
        snapshot,
        evaluation,
        profile_context={"report_v3": r3, "meta": meta_out},
    )
    report["metadata"] = meta_out

    ins = meta_out.get("export_status") in ("insufficient_signal", "degraded")
    if not ins:
        _ensure_fallback_evidence(report, transcript or "")

    weak_claims: List[Dict[str, Any]] = []
    if ins:
        weak_claims = []
    elif mode == "local+ai" and _llm_available():
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
    if transcript_cues:
        fixed_r3 = _align_missing_timestamps_with_cues(
            r3.get("evidence_mapping"),
            transcript_cues,
        )
        fixed_report = _align_missing_timestamps_with_cues(
            report.get("evidence_map"),
            transcript_cues,
        )
        fixed = fixed_r3 + fixed_report
        if fixed > 0:
            source_warnings.append(
                f"Aligned {fixed} evidence row timestamp(s) from transcript cues."
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
- Do not output "claim_id" — the pipeline assigns it to CLAIM ID above; only "question" and "question_type" per object.

Output JSON array only (3 objects):
[
  {{"question":"...","question_type":"counter"}},
  {{"question":"...","question_type":"validation"}},
  {{"question":"...","question_type":"application"}}
]
"""
        data = call_llm_json(prompt, max_tokens=900, temperature=0.2, client=client)
        if not isinstance(data, list):
            data = []
        for q in data:
            if isinstance(q, dict):
                qq = dict(q)
                # Local models often echo the wrong id; strict validation keys off evidence_map ids.
                qq["claim_id"] = eid
                questions.append(qq)
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
        # Never trust the rewriter for ids/types — SSOT is the pre-refine list (matches evidence_map).
        new_q["claim_id"] = q.get("claim_id")
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
    grounded_name_allowlist: Optional[List[str]] = None,
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
    allow = [str(x).strip() for x in (grounded_name_allowlist or []) if str(x).strip()]
    allow_json = json.dumps(allow[:24], ensure_ascii=False)
    booking_name_policy = """
- **`name` (booking target):** A **real, publicly known** figure — format **Firstname Lastname** (or a
  widely recognized public name such as **Pekka Hämäläinen**). Prefer authors, journalists, academics,
  or practitioners **you know from verifiable public biography** in the episode’s domain. **Do not**
  fabricate plausible-sounding fake people.
- **`title`:** Their credential or role (e.g. "Professor of History, Yale"; "Staff writer, The Atlantic").
- **Forbidden in `name`:** generic job labels alone ("Historian", "Skeptical expert", "Domain practitioner"),
  pure archetypes, or bracket-only role descriptions.
"""
    if allow:
        name_rules = f"""
EPISODE_FIGURES_MENTIONED (verbatim strings from the transcript — **do not** use as guest `name`):
{allow_json}
- Those strings are **subjects inside the story**, not outreach targets. Recommend **outside** experts
  (real named figures) who could contextualize, fact-check, or debate the same themes.
{booking_name_policy}
- `topic_focus` and `angle` must tie each expert to THIS episode's claims and stakes.
"""
    else:
        name_rules = booking_name_policy
    count_rule = "Return 3–4 guests when you can do so without inventing names; fewer is acceptable when the allowlist is short." if allow else "Return 3–4 guests."
    prompt = f"""
TASK: Suggest guests who are **topic-specific to THIS episode only** — not generic podcast guests.

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
{name_rules}
- `title`: short professional title aligned with that domain (or "Featured voice" when the best fit is a role label, not a named booking).
- `angle`: one sentence: what they add **to this episode's argument or story** (cite mechanism, institution, or stake from context).
- Map `maps_to_claim_id` to c1, c2, … when those ids exist; else c1.
- `relevance`: 0–10 (how on-topic for THIS episode).

Response contract (mandatory): reply with ONE JSON object with top-level keys "text" and "data" only.
Put the payload below inside "data" as a JSON object (not a top-level array). "text" may be "" or a one-line summary.

Inside "data" use exactly this shape (same guest list as v2 brief field name: ``guests``):
{{
  "guests": [
    {{
      "name": "string",
      "title": "string",
      "topic_focus": "string",
      "angle": "string",
      "maps_to_claim_id": "c1",
      "relevance": 9
    }}
  ]
}}

Rules: {count_rule} "data" must be an object. Do NOT return a top-level JSON array.
"""
    raw = call_llm_json(prompt, max_tokens=1400, client=client)
    rows_in: Any
    if isinstance(raw, list):
        rows_in = raw
    elif isinstance(raw, dict):
        rows_in = raw.get("guests") or raw.get("guest_recommendations") or []
        if not isinstance(rows_in, list):
            rows_in = []
    else:
        rows_in = []
    data = rows_in
    out = [x for x in data if isinstance(x, dict)][:5]
    primary_cid = ""
    for e in evidence_map:
        if isinstance(e, dict) and str(e.get("id") or "").strip():
            primary_cid = str(e.get("id") or "").strip()
            break
    for g in out:
        cid = str(g.get("maps_to_claim_id") or g.get("claim_id") or "").strip()
        if cid:
            g["claim_id"] = cid
        elif not str(g.get("claim_id") or "").strip():
            g["claim_id"] = primary_cid or "c1"
        role = str(g.get("role") or "").strip()
        title = str(g.get("title") or "").strip()
        if not role and title:
            g["role"] = title
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
    _align_guest_ids_to_evidence_map(evidence_map, out)
    return [g for g in out if _guest_name_is_plausible_booking(g)] or out


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
    spine_h = f"{str(meta.get('title') or '')} {str(meta.get('primary_topic') or '')}".strip()
    evidence_map = _sanitize_evidence_map_claims(evidence_map, spine_hint=spine_h)
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
    allow_cloud = _grounded_guest_name_allowlist_for_workflow(None, transcript or "")
    guests = generate_guest_recommendations(
        evidence_map,
        client=client,
        highlights=highlights,
        episode_meta=meta,
        transcript=transcript or "",
        grounded_name_allowlist=allow_cloud if allow_cloud else None,
    )
    if allow_cloud and not guests and evidence_map:
        guests = generate_guest_recommendations(
            evidence_map,
            client=client,
            highlights=highlights,
            episode_meta=meta,
            transcript=transcript or "",
            grounded_name_allowlist=None,
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
        "segments": segments,
        "analytics": analytics,
        "weak_claims": weak_claims,
    }
    set_workflow_guest_rows(report, guests)
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
    "workflow_guest_rows",
    "set_workflow_guest_rows",
    "call_llm",
    "call_llm_json",
    "maybe_editorial_pass_unified_markdown",
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
    "generate_guest_archetypes_from_issues",
    "should_generate_guests",
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
    md0, ed_ok = maybe_editorial_pass_unified_markdown(
        str(out.get("markdown_export") or ""),
        meta,
    )
    if ed_ok:
        out["markdown_export"] = md0
        om = out.get("metadata")
        if isinstance(om, dict):
            om["editorial_pass_applied"] = True
    # Belt & braces: workflow CLI historically wrote JSON right after editorial pass; always run
    # the same export sanitizer the FeedbackEngine path uses so local runs match ``episode_brief``.
    try:
        from .episode_report_v3 import finalize_unified_markdown_export
    except ImportError:  # pragma: no cover
        from episode_report_v3 import finalize_unified_markdown_export  # type: ignore

    out["markdown_export"] = finalize_unified_markdown_export(
        str(out.get("markdown_export") or "")
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
