"""
Post-episode coach loop: transcript → structured Episode Coach Report (sections A–F).

Desktop canonical output for Reverb / FeedbackEngine. No dashboards, scoring systems,
or guest-matching — producer-level feedback for the *next* episode only.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

# Strict section order — do not add marketing or analytics sections here.
COACH_SECTION_KEYS: Tuple[str, ...] = (
    "episode_summary",
    "strong_moments",
    "weak_moments",
    "missed_opportunities",
    "host_behavior_patterns",
    "next_episode_improvements",
)

COACH_SECTION_TITLES: Dict[str, str] = {
    "episode_summary": "A. Episode Summary",
    "strong_moments": "B. Strong Moments",
    "weak_moments": "C. Weak Moments",
    "missed_opportunities": "D. Missed Opportunities",
    "host_behavior_patterns": "E. Host Behavior Patterns",
    "next_episode_improvements": "F. Next Episode Improvements",
}

_COACH_SYSTEM = """You are a senior podcast producer coaching ONE host on ONE episode transcript.
Your only job: help them improve their NEXT episode with specific, behavioral feedback.

Rules:
- Ground every point in the transcript. No invented quotes, guests, or facts.
- No generic podcast advice ("be authentic", "know your audience").
- No marketing language, hype, or scoring dashboards.
- Strong/weak moments: explain WHY they worked or failed (mechanism, pacing, question quality).
- Missed opportunities: name the follow-up question or angle they skipped at that moment.
- Host behavior: observable patterns only (interrupting, topic jumping, over-explaining, shallow probes).
- Next episode improvements (section F): 3–7 imperative, repeatable behaviors — most important section.
- Talk ratio % only if clearly inferable from speaker labels; otherwise omit metrics.

Output ONLY valid JSON with exactly these keys (arrays of strings except episode_summary):
{
  "episode_summary": "2-3 sentences max",
  "strong_moments": ["moment — why it worked", ...],
  "weak_moments": ["moment — why it failed", ...],
  "missed_opportunities": ["specific follow-up or angle", ...],
  "host_behavior_patterns": ["observable pattern", ...],
  "next_episode_improvements": ["specific behavioral change", ...]
}
2-5 items per list section except next_episode_improvements (3-7 items). No markdown fences."""


def _ensure_coach_llm_env() -> None:
    """Load BYOK secrets and Settings ollama model into the process environment."""
    try:
        try:
            from backend.user_api_secrets import load_user_api_secrets
        except ImportError:
            from user_api_secrets import load_user_api_secrets  # type: ignore

        load_user_api_secrets(override=True)
    except Exception:
        pass
    if (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip():
        return
    try:
        try:
            from backend.config import Config
        except ImportError:
            from config import Config  # type: ignore

        om = str(Config().get("ui_settings.soapbox.ollama_model", "") or "").strip()
        if om:
            os.environ["SOAPBOXX_OLLAMA_MODEL"] = om
    except Exception:
        pass


_RE_TACTIQ = re.compile(r"tactiq\.io", re.I)
_RE_TS_PREFIX = re.compile(
    r"^\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?\s+"
)
_RE_HASH_URL = re.compile(r"^#\s*https?://", re.I)


def prepare_coach_transcript(text: str) -> Tuple[str, Optional[str]]:
    """
    Normalize pasted imports (Tactiq, YouTube captions, VTT-ish lines).

    Returns ``(body, optional_title)``.
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return "", None

    title: Optional[str] = None
    lines: List[str] = []
    for ln in t.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if _RE_TACTIQ.search(s) or s.lower().startswith("# tactiq"):
            continue
        if _RE_HASH_URL.match(s):
            continue
        if s.startswith("#") and len(s) < 220 and title is None:
            candidate = s.lstrip("#").strip()
            if candidate and "http" not in candidate.lower():
                title = candidate
                continue
        s = _RE_TS_PREFIX.sub("", s).strip()
        if s:
            lines.append(s)

    joined = "\n".join(lines)
    try:
        try:
            from backend.transcript_structure_extract import clean_caption_transcript
        except ImportError:
            from transcript_structure_extract import clean_caption_transcript  # type: ignore

        body = clean_caption_transcript(joined)
    except Exception:
        body = re.sub(r"[ \t]{2,}", " ", joined)

    return (body or t).strip(), title


def _clip_transcript(text: str, max_chars: int = 120000) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    head = int(max_chars * 0.65)
    tail = max_chars - head - 80
    return f"{t[:head]}\n\n[…middle of transcript omitted for length…]\n\n{t[-tail:]}"


def _llm_available() -> bool:
    _ensure_coach_llm_env()
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return True
    if (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip():
        return True
    if (os.getenv("GROQ_API_KEY") or os.getenv("SOAPBOXX_GROQ_API_KEY") or "").strip():
        return True
    return False


def _call_openai_coach(user: str, system: str) -> Dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    try:
        from openai import OpenAI

        try:
            from backend.guest_research import _build_openai_sdk_client
        except ImportError:
            from guest_research import _build_openai_sdk_client  # type: ignore

        client = _build_openai_sdk_client(api_key)
    except Exception:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

    model = (
        os.getenv("SOAPBOXX_COACH_MODEL")
        or os.getenv("SOAPBOXX_OPENAI_MODEL")
        or "gpt-4o-mini"
    ).strip()
    create_kwargs: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": int(os.getenv("SOAPBOXX_COACH_MAX_TOKENS", "2200")),
        "temperature": float(os.getenv("SOAPBOXX_COACH_TEMPERATURE", "0.35")),
    }
    try:
        response = client.chat.completions.create(
            **create_kwargs,
            response_format={"type": "json_object"},
        )
    except TypeError:
        response = client.chat.completions.create(**create_kwargs)
    content = (response.choices[0].message.content or "").strip()
    parsed = _parse_json_object(content)
    return {
        "text": content,
        "json": parsed,
        "data": parsed,
        "model": model,
    }


def _call_coach_llm(user: str, system: str) -> Dict[str, Any]:
    """OpenAI first (BYOK), then workflow Groq/Ollama via llm_service."""
    _ensure_coach_llm_env()
    if (os.getenv("OPENAI_API_KEY") or "").strip():
        return _call_openai_coach(user, system)
    try:
        from backend.llm_service import call_llm
    except ImportError:
        from llm_service import call_llm  # type: ignore

    return call_llm(
        user,
        max_tokens=int(os.getenv("SOAPBOXX_COACH_MAX_TOKENS", "2200")),
        temperature=float(os.getenv("SOAPBOXX_COACH_TEMPERATURE", "0.35")),
        system=system,
        json_format=True,
        stage="episode_coach_report",
    )


def _parse_json_object(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        import json

        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _normalize_sections(obj: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    summary = str(obj.get("episode_summary") or "").strip()
    out["episode_summary"] = summary[:1200] if summary else ""

    for key in COACH_SECTION_KEYS[1:]:
        raw = obj.get(key)
        items: List[str] = []
        if isinstance(raw, list):
            for row in raw:
                line = str(row).strip()
                if len(line) >= 12:
                    items.append(line[:900])
        elif isinstance(raw, str) and raw.strip():
            items = [raw.strip()[:900]]
        if key == "next_episode_improvements":
            out[key] = items[:7]
        else:
            out[key] = items[:5]
    return out


def render_episode_coach_markdown(
    sections: Dict[str, Any],
    *,
    warnings: Optional[List[str]] = None,
) -> str:
    """Render strict A–F Episode Coach Report markdown."""
    lines: List[str] = ["# Episode Coach Report", ""]
    w = warnings or []
    if "llm_not_configured" in w:
        lines.append(
            "> **Producer coaching needs an LLM.** In **Settings**, paste your OpenAI API key "
            "(or set an **Ollama model** and run Ollama), click **Save**, then generate again."
        )
        lines.append("")
    elif any(str(x).startswith("llm_error:") for x in w):
        lines.append(
            "> **LLM call failed** — check your API key, model name, or Ollama/Groq status. "
            "Details are in the report warnings below."
        )
        lines.append("")
    summary = str(sections.get("episode_summary") or "").strip()
    lines.append(f"## {COACH_SECTION_TITLES['episode_summary']}")
    lines.append(summary or "(No summary generated.)")
    lines.append("")

    for key in COACH_SECTION_KEYS[1:]:
        title = COACH_SECTION_TITLES[key]
        lines.append(f"## {title}")
        items = sections.get(key) or []
        if not items:
            lines.append("- (None identified from this transcript.)")
        else:
            for item in items:
                item_s = str(item).strip()
                if not item_s.startswith("- "):
                    item_s = f"- {item_s}"
                lines.append(item_s)
        lines.append("")

    return "\n".join(lines).strip()


def _heuristic_sections(
    transcript: str,
    *,
    import_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Minimal offline fallback when no LLM is configured."""
    t = (transcript or "").strip()
    words = len(t.split())
    if import_title:
        summary = (
            f"Imported episode «{import_title[:160]}» ({words} words after cleanup). "
            "Configure an LLM in Settings for transcript-specific coaching."
        )
    else:
        summary = (
            f"This episode is about {words} words after cleanup. "
            "Configure an LLM in Settings (OpenAI key or Ollama model) for producer-level coaching."
        )
    return {
        "episode_summary": summary,
        "strong_moments": [
            "Guest had room to answer at least once — keep intentional pauses after questions."
        ],
        "weak_moments": [
            "Could not run full analysis offline — configure an LLM for transcript-specific coaching."
        ],
        "missed_opportunities": [
            "Paste a longer transcript and enable LLM to surface missed follow-ups."
        ],
        "host_behavior_patterns": [
            "Review whether you stack questions before the guest finishes (listen-back once)."
        ],
        "next_episode_improvements": [
            "Before recording: write 3 must-answer questions tied to this episode's theme.",
            "During: after each answer, ask one why/how follow-up before changing topic.",
            "After: read the Episode Coach Report with LLM enabled for concrete weak moments.",
        ],
    }


def generate_episode_coach_report(
    transcript: str,
    *,
    title: str = "",
    creator: str = "",
) -> Dict[str, Any]:
    """
    Generate structured Episode Coach Report (sections A–F).

    Returns dict with keys: sections, markdown, model, warnings.
    """
    raw_in = (transcript or "").strip()
    text, import_title = prepare_coach_transcript(raw_in)
    if not title and import_title:
        title = import_title

    if len(text) < 80:
        empty = _heuristic_sections(text or "", import_title=import_title)
        empty["episode_summary"] = "Transcript too short for meaningful coaching (need more dialogue)."
        return {
            "sections": empty,
            "markdown": render_episode_coach_markdown(
                empty, warnings=["transcript_too_short"]
            ),
            "model": "none",
            "warnings": ["transcript_too_short"],
        }

    if not _llm_available():
        sections = _heuristic_sections(text, import_title=import_title or title)
        warns = ["llm_not_configured"]
        return {
            "sections": sections,
            "markdown": render_episode_coach_markdown(sections, warnings=warns),
            "model": "heuristic",
            "warnings": warns,
        }

    meta = ""
    if title:
        meta += f"Title: {title}\n"
    if creator:
        meta += f"Show: {creator}\n"
    user = (
        f"{meta}\nTRANSCRIPT:\n{_clip_transcript(text)}\n\n"
        "Return JSON only per the schema. Section F must be the most actionable."
    )
    try:
        env = _call_coach_llm(user, _COACH_SYSTEM)
        raw = env.get("json") or env.get("data") or env.get("text")
        obj = _parse_json_object(raw)
        if not obj:
            sections = _heuristic_sections(text, import_title=import_title or title)
            warns = ["json_parse_failed"]
            return {
                "sections": sections,
                "markdown": render_episode_coach_markdown(sections, warnings=warns),
                "model": str(env.get("model") or "unknown"),
                "warnings": warns,
            }
        sections = _normalize_sections(obj)
        return {
            "sections": sections,
            "markdown": render_episode_coach_markdown(sections),
            "model": str(env.get("model") or "unknown"),
            "warnings": [],
        }
    except Exception as exc:
        sections = _heuristic_sections(text, import_title=import_title or title)
        warns = [f"llm_error:{exc}"]
        return {
            "sections": sections,
            "markdown": render_episode_coach_markdown(sections, warnings=warns),
            "model": "error",
            "warnings": warns,
        }
