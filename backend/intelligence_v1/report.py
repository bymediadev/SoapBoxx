"""Structured intelligence report (comparison + prediction + actions)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .config import coaching_prompt_path


def _fmt_delta(label: str, value: float, bench: Dict[str, float], *, lower_better: bool) -> str:
    avg = bench.get("avg") or 0
    if avg == 0:
        return f"- {label}: {value:.0f} (no category baseline yet)"
    if lower_better:
        flag = "better" if value <= avg else "slower/weaker"
    else:
        flag = "better" if value >= avg else "below avg"
    return f"- {label}: {value:.0f} vs category avg {avg:.0f} ({flag})"


def _rule_actions(
    metrics: Dict[str, Any],
    benchmarks: Dict[str, Dict[str, float]],
    prediction: Dict[str, Any],
) -> List[str]:
    actions: List[str] = []
    hook = float(metrics.get("hook_time_seconds") or 0)
    b_hook = benchmarks.get("hook_time_seconds") or {}
    if b_hook.get("avg") and hook > b_hook["avg"]:
        actions.append(
            f"Open with the core tension within {int(b_hook['avg'])}s — your hook was ~{int(hook)}s."
        )
    follow = int(metrics.get("followup_question_count") or 0)
    b_f = benchmarks.get("followup_question_count") or {}
    if b_f.get("avg") and follow < b_f["avg"]:
        actions.append(
            "After each guest answer, ask one why/how before switching topics "
            f"(category avg follow-ups ~{int(b_f['avg'])})."
        )
    if abs(
        float(metrics.get("guest_talk_percentage") or 0)
        - float(metrics.get("host_talk_percentage") or 0)
    ) > 25:
        actions.append("Rebalance airtime: shorter host monologues, longer guest answers.")
    if not metrics.get("cta_present"):
        actions.append("Close with one specific CTA (subscribe, next episode, or resource link).")
    for r in prediction.get("reasoning") or []:
        if "p10" in r.lower() or "below" in r.lower():
            actions.append(f"Address gap: {r}")
    if len(actions) < 3:
        actions.append("Prep 3 must-answer questions before the next recording.")
    return actions[:5]


def _llm_actions(
    metrics: Dict[str, Any],
    benchmarks: Dict[str, Dict[str, float]],
    prediction: Dict[str, Any],
) -> Optional[List[str]]:
    if not (
        (os.getenv("OPENAI_API_KEY") or "").strip()
        or (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip()
        or (os.getenv("GROQ_API_KEY") or os.getenv("SOAPBOXX_GROQ_API_KEY") or "").strip()
    ):
        return None
    system = "Return JSON only: {\"actions\": [\"...\"]}"
    if coaching_prompt_path().is_file():
        system = coaching_prompt_path().read_text(encoding="utf-8").strip()
    payload = {
        "metrics": metrics,
        "benchmarks": benchmarks,
        "prediction": prediction,
    }
    user = json.dumps(payload, indent=2)[:12000]
    try:
        try:
            from backend.episode_coach_report import _call_coach_llm
        except ImportError:
            from episode_coach_report import _call_coach_llm  # type: ignore

        env = _call_coach_llm(user, system)
        raw = env.get("json") or env.get("data") or env.get("text")
        if isinstance(raw, dict) and isinstance(raw.get("actions"), list):
            return [str(a).strip() for a in raw["actions"] if str(a).strip()][:5]
        if isinstance(raw, str):
            obj = json.loads(raw)
            if isinstance(obj.get("actions"), list):
                return [str(a).strip() for a in obj["actions"] if str(a).strip()][:5]
    except Exception:
        return None
    return None


def build_report(
    *,
    title: str,
    category: str,
    metrics: Dict[str, Any],
    benchmarks: Dict[str, Dict[str, float]],
    prediction: Dict[str, Any],
    episode_id: Optional[int] = None,
    benchmark_note: str = "",
    show_tier: bool = True,
) -> Dict[str, Any]:
    """Markdown + structured JSON for UI/CLI."""
    lines = ["# SoapBoxx Intelligence Report", ""]
    if episode_id is not None:
        lines.append(f"Episode ID: {episode_id}")
    lines.append(f"Title: {title}")
    lines.append(f"Category: {category}")
    src = str(metrics.get("feature_source") or "unknown")
    lines.append(f"Measurement: **{src}** (rule-based = reproducible)")
    if benchmark_note:
        lines.append(f"Benchmarks: {benchmark_note}")
    lines.append("")

    lines.append("## Measured structure")
    if metrics.get("speaking_turns") is not None:
        lines.append(f"- Speaking turns (labeled lines): {metrics.get('speaking_turns')}")
    if metrics.get("avg_sentence_length") is not None:
        lines.append(f"- Avg sentence length (words): {metrics.get('avg_sentence_length')}")
    lines.append(f"- Questions (`?` count): {metrics.get('question_count', 0)}")
    lines.append(f"- Topic shift markers: {metrics.get('topic_changes', 0)}")
    lines.append(f"- CTA present: {metrics.get('cta_present', False)}")
    lines.append("")

    lines.append("## Category comparison")
    lines.append(
        _fmt_delta(
            "Hook time (sec)",
            float(metrics.get("hook_time_seconds") or 0),
            benchmarks.get("hook_time_seconds") or {},
            lower_better=True,
        )
    )
    lines.append(
        _fmt_delta(
            "Follow-up questions",
            float(metrics.get("followup_question_count") or 0),
            benchmarks.get("followup_question_count") or {},
            lower_better=False,
        )
    )
    lines.append(
        _fmt_delta(
            "Guest talk %",
            float(metrics.get("guest_talk_percentage") or 0),
            benchmarks.get("guest_talk_percentage") or {},
            lower_better=False,
        )
    )
    lines.append(
        _fmt_delta(
            "Host talk %",
            float(metrics.get("host_talk_percentage") or 0),
            benchmarks.get("host_talk_percentage") or {},
            lower_better=False,
        )
    )
    lines.append("")

    if show_tier and not prediction.get("disabled"):
        lines.append("## Prediction (heuristic tier — optional)")
        lines.append(f"- Tier: **{prediction.get('tier', '?')}**")
        lines.append(f"- Confidence: {float(prediction.get('confidence', 0)) * 100:.0f}%")
        for r in prediction.get("reasoning") or []:
            lines.append(f"- {r}")
        lines.append("")

    actions = _rule_actions(metrics, benchmarks, prediction)
    if show_tier and _llm_actions(metrics, benchmarks, prediction):
        actions = _llm_actions(metrics, benchmarks, prediction) or actions
    lines.append("## Suggested focus (from measurements)")
    for a in actions:
        lines.append(f"- {a}")

    markdown = "\n".join(lines).strip()
    return {
        "episode_id": episode_id,
        "title": title,
        "category": category,
        "metrics": metrics,
        "benchmarks": benchmarks,
        "prediction": prediction,
        "actions": actions,
        "markdown": markdown,
        "benchmark_note": benchmark_note,
    }


def render_markdown(report: Dict[str, Any]) -> str:
    return str(report.get("markdown") or "").strip()
