# backend/coach_synth.py
"""
Optional LLM pass: replaces template-heavy coach prose with transcript-grounded analysis and, when the model
returns optional fields, an **episode-specific action plan** (fix list, follow-ups, segment upgrade, bottom line,
where-it-breaks, clip ideas). The user prompt includes a ``CURRENT_COACH_SKETCH`` so the model can beat—not
echo—the generic template.

**$0 options (no OpenAI billing):**
- **Ollama** — local; set ``SOAPBOXX_OLLAMA_MODEL`` and run Ollama (same stack as the v2 brief).
- **Groq** — free API tier (sign up at https://console.groq.com ); set ``GROQ_API_KEY`` or
  ``SOAPBOXX_GROQ_API_KEY`` and optionally ``SOAPBOXX_COACH_SYNTH_BACKEND=groq``.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

_COACH_SYNTH_SYSTEM = """You are a senior podcast editorial director for ONE show: precise, non-generic, transcript-grounded.
Your job is not pep-talk — it is a **customized, executable plan** for this episode (title, creator, genre, claims, excerpt).

Hard rules:
- Ground specifics in the EXCERPT and METADATA. Do not invent quotes, names, dates, or statistics not supported there.
- If something cannot be defended from the excerpt, say what to verify or cut — do not fabricate.
- Sections must **not** repeat the same sentence across keys (especially uncomfortable_insight vs contrarian_hook vs analytical_read).
- themes[].discussed / implying / matters must name **this** episode's threads (reference subject matter from the tape when possible).
- Optional "action" fields must beat the CURRENT_COACH_SKETCH: use imperative verbs, name the show or topic where it helps, and tie steps to claims or moments from the excerpt.

Required JSON keys (always present; use arrays/strings as specified, never null for these):
- "analytical_read": 2–4 strings, 1–3 sentences each — what is *actually happening* in this cut (arc, risk, missing proof).
- "uncomfortable_insight_body": one string, 2–5 sentences — hardest honest read the host can still use.
- "contrarian_hook_body": one string, 2–4 sentences — non-obvious angle (mechanism, incentive, frame shift).
- "themes": 2–4 objects {"discussed","implying","matters"} — one sentence per field unless "discussed" needs two short sentences.

Optional JSON keys (include when you can improve on the sketch; omit or use [] if not):
- "immediate_fix_plan": 3–5 strings — first step doable before next publish; reference this episode's thesis or a claim id where natural.
- "follow_up_questions": 4–6 strings — sharp interview questions or self-interview prompts tied to the claims/excerpt.
- "segment_upgrade": one string — one concrete structural or edit fix for **this** recording (timing, reframing, evidence block).
- "bottom_line": object {"good","must_change","if_fixed"} — each one tight sentence, episode-specific.
- "where_it_breaks_issues": 2–5 strings — pressure points for **this** tape (not generic podcast advice).
- "clip_moments": 1–3 strings — clip concepts anchored in what was said (paraphrase; no fake quotes).

Output **only** one JSON object. No markdown fences. No commentary outside the JSON."""


def _coach_synth_enabled() -> bool:
    return os.getenv("SOAPBOXX_COACH_SYNTH", "").strip().lower() in ("1", "true", "yes", "on")


def _groq_api_key() -> str:
    return (
        os.getenv("SOAPBOXX_GROQ_API_KEY", "").strip()
        or os.getenv("GROQ_API_KEY", "").strip()
    )


def _coach_synth_backend() -> str:
    forced = os.getenv("SOAPBOXX_COACH_SYNTH_BACKEND", "").strip().lower()
    if forced in ("openai", "ollama", "groq"):
        return forced
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"
    if _groq_api_key():
        return "groq"
    if os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip():
        return "ollama"
    return ""


def _clip(s: str, max_len: int) -> str:
    t = (s or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rsplit(" ", 1)[0] + "…"


def _parse_json_object(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _normalize_synth_payload(obj: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    ar = obj.get("analytical_read")
    if isinstance(ar, list):
        paras = [_clip(str(x).strip(), 720) for x in ar if str(x).strip()]
        out["analytical_read"] = paras[:4]
    ub = obj.get("uncomfortable_insight_body")
    if isinstance(ub, str) and ub.strip():
        out["uncomfortable_insight_body"] = _clip(ub.strip(), 1400)
    cb = obj.get("contrarian_hook_body")
    if isinstance(cb, str) and cb.strip():
        out["contrarian_hook_body"] = _clip(cb.strip(), 1200)
    th = obj.get("themes")
    themes_out: List[Dict[str, str]] = []
    if isinstance(th, list):
        for i, row in enumerate(th[:6]):
            if not isinstance(row, dict):
                continue
            d = _clip(str(row.get("discussed") or "").strip(), 320)
            im = _clip(str(row.get("implying") or "").strip(), 280)
            ma = _clip(str(row.get("matters") or "").strip(), 280)
            if len(d) < 14:
                continue
            themes_out.append(
                {
                    "label": f"Theme {len(themes_out) + 1}",
                    "discussed": d,
                    "implying": im or "See discussed — host treats this thread as load-bearing for the episode's argument.",
                    "matters": ma or "Sharpens what is at stake if this thread stays implicit.",
                }
            )
            if len(themes_out) >= 4:
                break
    if themes_out:
        out["themes"] = themes_out

    fix = obj.get("immediate_fix_plan")
    if isinstance(fix, list):
        steps = [_clip(str(x).strip(), 260) for x in fix if str(x).strip()]
        if len(steps) >= 2:
            out["immediate_fix_plan"] = steps[:5]

    fuq = obj.get("follow_up_questions")
    if isinstance(fuq, list):
        qs = [_clip(str(x).strip(), 240) for x in fuq if str(x).strip()]
        if len(qs) >= 3:
            out["follow_up_questions"] = qs[:8]

    su = obj.get("segment_upgrade")
    if isinstance(su, str) and len(su.strip()) > 28:
        out["segment_upgrade"] = _clip(su.strip(), 720)

    bl = obj.get("bottom_line")
    if isinstance(bl, dict):
        g = _clip(str(bl.get("good") or "").strip(), 320)
        m = _clip(str(bl.get("must_change") or "").strip(), 320)
        iff = _clip(str(bl.get("if_fixed") or "").strip(), 320)
        if g or m or iff:
            out["bottom_line"] = {"good": g, "must_change": m, "if_fixed": iff}

    wib = obj.get("where_it_breaks_issues")
    if isinstance(wib, list):
        issues = [_clip(str(x).strip(), 300) for x in wib if str(x).strip()]
        if len(issues) >= 2:
            out["where_it_breaks_issues"] = issues[:6]

    clips = obj.get("clip_moments")
    if isinstance(clips, list):
        cms = [_clip(str(x).strip(), 260) for x in clips if str(x).strip()]
        if cms:
            out["clip_moments"] = cms[:4]

    return out


def _build_synth_user_block(
    brief: Dict[str, Any],
    transcript: str,
    coach_report: Dict[str, Any],
    *,
    signal_mode: str,
    output_mode: str,
    clean_insights: List[str],
    claims: List[Dict[str, Any]],
    excerpt_chars: int,
) -> str:
    snap = brief.get("episode_snapshot") or {}
    meta = {
        "title": snap.get("title"),
        "creator": snap.get("creator"),
        "genre": snap.get("genre"),
        "primary_topic": snap.get("primary_topic"),
        "why_it_matters": snap.get("why_it_matters"),
    }
    thesis = str((coach_report or {}).get("episode_thesis") or "").strip()
    narr = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()][:5]
    claim_lines: List[str] = []
    for c in claims[:10]:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        tx = str(c.get("text") or "").strip()
        if cid and tx:
            claim_lines.append(f"- [{cid}] {tx[:400]}")
    excerpt = (transcript or "").strip()[:excerpt_chars]
    wb = coach_report.get("where_it_breaks") if isinstance(coach_report.get("where_it_breaks"), dict) else {}
    issues_cur = [str(x).strip() for x in (wb.get("issues") or []) if str(x).strip()][:6]
    sketch = {
        "where_it_breaks_issues": issues_cur,
        "immediate_fix_plan": [
            str(x).strip() for x in (coach_report.get("immediate_fix_plan") or [])[:5] if str(x).strip()
        ],
        "follow_up_questions": [
            str(x).strip() for x in (coach_report.get("follow_up_questions") or [])[:8] if str(x).strip()
        ],
        "segment_upgrade": _clip(str(coach_report.get("segment_upgrade") or "").strip(), 520),
        "bottom_line": coach_report.get("bottom_line") if isinstance(coach_report.get("bottom_line"), dict) else {},
        "clip_moments": [
            str(x).strip()
            for x in ((coach_report.get("opportunities") or {}).get("clip_moments") or [])[:4]
            if str(x).strip()
        ],
    }
    parts = [
        f"SIGNAL_MODE: {signal_mode}",
        f"OUTPUT_MODE: {output_mode}",
        "",
        "EPISODE_SNAPSHOT:",
        json.dumps(meta, ensure_ascii=False, indent=2),
        "",
        f"EPISODE_THESIS (one line, may be heuristic): {thesis}",
        "",
        "NARRATIVE_BULLETS (from brief):",
        "\n".join(f"- {n}" for n in narr) or "- (none)",
        "",
        "HIGHLIGHTS / INSIGHT SEEDS:",
        "\n".join(f"- {str(x)[:360]}" for x in (clean_insights or [])[:8] if str(x).strip())
        or "- (none)",
        "",
        "CLAIMS:",
        "\n".join(claim_lines) or "- (none)",
        "",
        "CURRENT_COACH_SKETCH (generic template — optional JSON fields should REPLACE these when you can do better):",
        json.dumps(sketch, ensure_ascii=False, indent=2),
        "",
        "TRANSCRIPT_EXCERPT (ground truth for specifics):",
        excerpt,
    ]
    return "\n".join(parts)


def _synthesize_openai(user_block: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return {}
    model = os.getenv("SOAPBOXX_OPENAI_COACH_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    try:
        from openai import OpenAI
    except ImportError:
        return {"_error": "openai package not installed"}
    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.42,
            max_tokens=3600,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _COACH_SYNTH_SYSTEM},
                {"role": "user", "content": user_block},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:  # pragma: no cover - network
        return {"_error": str(e)}
    obj = _parse_json_object(raw)
    if not obj:
        return {"_error": "invalid_json"}
    return {**_normalize_synth_payload(obj), "_model": model, "_backend": "openai"}


def _synthesize_groq(user_block: str) -> Dict[str, Any]:
    """Groq OpenAI-compatible API — free tier at signup (no OpenAI credits)."""
    api_key = _groq_api_key()
    if not api_key:
        return {"_error": "missing_groq_api_key"}
    model = os.getenv("SOAPBOXX_GROQ_COACH_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"
    base = os.getenv("SOAPBOXX_GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/")
    try:
        from openai import OpenAI
    except ImportError:
        return {"_error": "openai package not installed"}
    client = OpenAI(api_key=api_key, base_url=f"{base}/")
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.42,
            max_tokens=3600,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _COACH_SYNTH_SYSTEM},
                {"role": "user", "content": user_block},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as e:  # pragma: no cover - network
        return {"_error": str(e)}
    obj = _parse_json_object(raw)
    if not obj:
        return {"_error": "invalid_json"}
    return {**_normalize_synth_payload(obj), "_model": model, "_backend": "groq"}


def _synthesize_ollama(user_block: str) -> Dict[str, Any]:
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        return {}
    try:
        from .episode_intelligence import _ollama_chat_invoke
    except ImportError:
        from episode_intelligence import _ollama_chat_invoke  # type: ignore
    try:
        raw = _ollama_chat_invoke(
            _COACH_SYNTH_SYSTEM,
            user_block,
            max_tokens=3600,
            temperature=0.4,
            stage="episode_report_v3.coach_synth",
            append_brief_envelope_suffix=False,
        )
    except Exception as e:  # pragma: no cover - network
        return {"_error": str(e)}
    obj = _parse_json_object(raw)
    if not obj:
        return {"_error": "invalid_json"}
    out = _normalize_synth_payload(obj)
    out["_model"] = model
    out["_backend"] = "ollama"
    return out


def merge_coach_synthesis(coach_report: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, str]:
    """
    Merge normalized LLM fields into coach_report (in-place).
    Returns meta dict for coach_report['meta']['coach_synth'].
    """
    meta: Dict[str, str] = {"ok": "1"}
    err = str(patch.get("_error") or "").strip()
    if err:
        meta["ok"] = "0"
        meta["error"] = err[:500]
        return meta
    fields: List[str] = []
    if patch.get("uncomfortable_insight_body"):
        ui = coach_report.get("uncomfortable_insight")
        if isinstance(ui, dict):
            ui["body"] = patch["uncomfortable_insight_body"]
            fields.append("uncomfortable_insight")
    if patch.get("contrarian_hook_body"):
        ch = coach_report.get("contrarian_hook")
        if isinstance(ch, dict):
            ch["body"] = patch["contrarian_hook_body"]
            fields.append("contrarian_hook")
    if patch.get("themes"):
        coach_report["themes"] = patch["themes"]
        fields.append("themes")
    ar = patch.get("analytical_read") or []
    if isinstance(ar, list) and ar:
        ed = coach_report.get("episode_diagnosis")
        if isinstance(ed, dict):
            body = ed.get("body")
            if isinstance(body, list):
                insert_at = 0
                for i, line in enumerate(body):
                    if isinstance(line, str) and "**Thesis (one sentence):**" in line:
                        insert_at = i + 1
                        break
                block = ["", "**Model read (transcript-grounded):**", *ar]
                for j, line in enumerate(block):
                    body.insert(insert_at + j, line)
                fields.append("analytical_read")
    if patch.get("immediate_fix_plan"):
        coach_report["immediate_fix_plan"] = list(patch["immediate_fix_plan"])
        fields.append("immediate_fix_plan")
    if patch.get("follow_up_questions"):
        coach_report["follow_up_questions"] = list(patch["follow_up_questions"])
        fields.append("follow_up_questions")
    if patch.get("segment_upgrade"):
        coach_report["segment_upgrade"] = str(patch["segment_upgrade"])
        fields.append("segment_upgrade")
    if patch.get("bottom_line") and isinstance(patch["bottom_line"], dict):
        bl = coach_report.setdefault("bottom_line", {})
        for k in ("good", "must_change", "if_fixed"):
            v = str(patch["bottom_line"].get(k) or "").strip()
            if v:
                bl[k] = v
        fields.append("bottom_line")
    if patch.get("where_it_breaks_issues"):
        wib = coach_report.setdefault("where_it_breaks", {"issues": [], "rule": ""})
        if isinstance(wib, dict):
            prev_rule = str(wib.get("rule") or "").strip()
            wib["issues"] = list(patch["where_it_breaks_issues"])
            if prev_rule:
                wib["rule"] = prev_rule
        fields.append("where_it_breaks")
    if patch.get("clip_moments"):
        raw_opp = coach_report.get("opportunities")
        if not isinstance(raw_opp, dict):
            raw_opp = {}
            coach_report["opportunities"] = raw_opp
        raw_opp["clip_moments"] = list(patch["clip_moments"])
        fields.append("clip_moments")
    if patch.get("_backend"):
        meta["backend"] = str(patch["_backend"])
    if patch.get("_model"):
        meta["model"] = str(patch["_model"])
    meta["fields"] = ",".join(fields) if fields else ""
    if not fields and not err:
        meta["ok"] = "0"
        meta["error"] = "empty_payload"
    return meta


def maybe_enrich_coach_report_with_llm(
    brief: Dict[str, Any],
    transcript: str,
    coach_report: Dict[str, Any],
    *,
    signal_mode: str,
    output_mode: str,
    clean_insights: List[str],
    claims: List[Dict[str, Any]],
) -> None:
    """
    When SOAPBOXX_COACH_SYNTH=1 and a backend is available (OpenAI, Groq, or Ollama), run one synthesis pass
    **after** identity / thesis repair in ``build_v3_report`` so coach copy matches the final thesis.
    Replaces template coach prose with transcript-grounded copy and (when the model returns them)
    episode-specific action fields: fix plan, follow-ups, segment upgrade, bottom line, where-it-breaks,
    and clip moments — see ``merge_coach_synthesis``.
    """
    if not _coach_synth_enabled():
        return
    backend = _coach_synth_backend()
    excerpt = int(os.getenv("SOAPBOXX_COACH_SYNTH_EXCERPT_CHARS", "14000").strip() or "14000")
    excerpt = max(2000, min(excerpt, 120_000))
    user_block = _build_synth_user_block(
        brief,
        transcript,
        coach_report,
        signal_mode=signal_mode,
        output_mode=output_mode,
        clean_insights=clean_insights,
        claims=claims,
        excerpt_chars=excerpt,
    )
    patch: Dict[str, Any] = {}
    if backend == "openai":
        patch = _synthesize_openai(user_block)
    elif backend == "groq":
        patch = _synthesize_groq(user_block)
    elif backend == "ollama":
        patch = _synthesize_ollama(user_block)
    cr_meta = coach_report.setdefault("meta", {})
    if not backend:
        cr_meta["coach_synth"] = {
            "ok": "0",
            "skipped": "no_backend",
            "hint": (
                "Free: install Ollama + SOAPBOXX_OLLAMA_MODEL, or free cloud Groq key "
                "(GROQ_API_KEY) + SOAPBOXX_COACH_SYNTH_BACKEND=groq. Paid: OPENAI_API_KEY."
            ),
        }
        return
    synth_meta = merge_coach_synthesis(coach_report, patch)
    cr_meta["coach_synth"] = synth_meta


__all__ = [
    "maybe_enrich_coach_report_with_llm",
    "merge_coach_synthesis",
    "_coach_synth_enabled",
    "_normalize_synth_payload",
]
