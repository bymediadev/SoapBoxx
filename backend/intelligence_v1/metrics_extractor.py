"""Transcript → strict JSON metrics (LLM)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from .config import metric_prompt_path

METRIC_KEYS = (
    "hook_time_seconds",
    "guest_talk_percentage",
    "host_talk_percentage",
    "question_count",
    "followup_question_count",
    "story_count",
    "interruptions",
    "topic_changes",
    "cta_present",
)


def _load_system_prompt() -> str:
    p = metric_prompt_path()
    if p.is_file():
        return p.read_text(encoding="utf-8").strip()
    return (
        "Return JSON only with keys: hook_time_seconds, guest_talk_percentage, "
        "host_talk_percentage, question_count, followup_question_count, story_count, "
        "interruptions, topic_changes, cta_present."
    )


def _parse_json(raw: Any) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.I)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _normalize_metrics(obj: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["hook_time_seconds"] = max(0.0, float(obj.get("hook_time_seconds") or 0))
    g = max(0.0, min(100.0, float(obj.get("guest_talk_percentage") or 0)))
    h = max(0.0, min(100.0, float(obj.get("host_talk_percentage") or 0)))
    if g + h > 100.1:
        total = g + h or 1.0
        g, h = 100.0 * g / total, 100.0 * h / total
    out["guest_talk_percentage"] = round(g, 1)
    out["host_talk_percentage"] = round(h, 1)
    for k in (
        "question_count",
        "followup_question_count",
        "story_count",
        "interruptions",
        "topic_changes",
    ):
        out[k] = max(0, int(obj.get(k) or 0))
    out["cta_present"] = bool(obj.get("cta_present"))
    return out


def _heuristic_metrics(transcript: str) -> Dict[str, Any]:
    """Offline fallback when no LLM is configured."""
    t = transcript or ""
    words = len(t.split())
    questions = t.count("?")
    return _normalize_metrics(
        {
            "hook_time_seconds": 60.0 if words > 500 else 30.0,
            "guest_talk_percentage": 45.0,
            "host_talk_percentage": 55.0,
            "question_count": questions,
            "followup_question_count": max(0, questions // 3),
            "story_count": max(0, min(5, t.lower().count("story"))),
            "interruptions": 0,
            "topic_changes": max(0, min(10, t.lower().count("anyway") + t.lower().count("moving on"))),
            "cta_present": any(
                x in t.lower() for x in ("subscribe", "patreon", "follow", "link in")
            ),
        }
    )


def _ensure_llm_env() -> None:
    try:
        from backend.episode_coach_report import _ensure_coach_llm_env

        _ensure_coach_llm_env()
    except Exception:
        pass


def _call_llm_json(transcript: str, system: str) -> Dict[str, Any]:
    clip = transcript[:100_000]
    user = f"TRANSCRIPT:\n{clip}\n\nReturn JSON only."

    if (os.getenv("OPENAI_API_KEY") or "").strip():
        try:
            from backend.episode_coach_report import _call_openai_coach
        except ImportError:
            from episode_coach_report import _call_openai_coach  # type: ignore

        env = _call_openai_coach(user, system)
        obj = _parse_json(env.get("json") or env.get("text"))
        if obj:
            return obj
    try:
        from backend.llm_service import call_llm
    except ImportError:
        from llm_service import call_llm  # type: ignore

    env = call_llm(
        user,
        max_tokens=int(os.getenv("SOAPBOXX_METRICS_MAX_TOKENS", "800")),
        temperature=0.2,
        system=system,
        json_format=True,
        stage="intelligence_v1.metrics",
    )
    obj = _parse_json(env.get("json") or env.get("data") or env.get("text"))
    if not obj:
        raise RuntimeError("Metric extraction returned non-JSON")
    return obj


def _llm_metrics_enabled() -> bool:
    return os.getenv("SOAPBOXX_LLM_METRICS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def extract_metrics(
    transcript: str,
    segments: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Extract structured episode metrics.

    Default: **rule-based** (V1 instrumentation, reproducible).
    Optional: ``SOAPBOXX_LLM_METRICS=1`` for LLM estimates (opinion-adjacent).
    """
    raw = (transcript or "").strip()
    try:
        from backend.episode_coach_report import prepare_coach_transcript
    except ImportError:
        from episode_coach_report import prepare_coach_transcript  # type: ignore

    text, _title = prepare_coach_transcript(raw)
    if len(text) < 40:
        h = _heuristic_metrics(text or raw)
        h["feature_source"] = "heuristic"
        return h

    try:
        from backend.features import extract_rule_features
    except ImportError:
        from features import extract_rule_features  # type: ignore

    rb = extract_rule_features(text, segments)
    out = _normalize_metrics(rb)
    out["feature_source"] = "rule_based"
    for extra in ("speaking_turns", "avg_sentence_length"):
        if extra in rb:
            out[extra] = rb[extra]

    if not _llm_metrics_enabled():
        return out

    _ensure_llm_env()
    has_llm = bool(
        (os.getenv("OPENAI_API_KEY") or "").strip()
        or (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip()
        or (os.getenv("GROQ_API_KEY") or os.getenv("SOAPBOXX_GROQ_API_KEY") or "").strip()
    )
    if not has_llm:
        return out

    try:
        llm_raw = _call_llm_json(text, _load_system_prompt())
        llm_out = _normalize_metrics(llm_raw)
        llm_out["feature_source"] = "llm"
        return llm_out
    except Exception:
        return out
