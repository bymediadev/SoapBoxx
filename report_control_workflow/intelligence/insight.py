# report_control_workflow/intelligence/insight.py
"""Core takeaway selection + optional LLM synthesis (calls scoring for heuristics)."""

from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

from report_control_workflow.constants import CORE_INSIGHT_MAX_WORDS, DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER
from report_control_workflow.core.models import ClaimRow


def extract_core_insight(claims: Sequence[ClaimRow]) -> str:
    from report_control_workflow.pipeline.scoring import score_claim_strength, score_insight_novelty

    rows = [c for c in claims if (c.text or "").strip()]
    if not rows:
        return ""

    def combined(c: ClaimRow) -> float:
        return score_claim_strength(c.text) + score_insight_novelty(c.text)

    best = max(rows, key=combined)
    text = (best.text or "").strip()
    words = text.rstrip(".!?").split()
    if len(words) > CORE_INSIGHT_MAX_WORDS:
        text = " ".join(words[:CORE_INSIGHT_MAX_WORDS]) + "."
    elif text and not text.endswith("."):
        text += "."
    return text


def synthesize_core_insight(
    claims: Sequence[ClaimRow],
    llm_fn: Callable[[str], str],
) -> Optional[str]:
    from report_control_workflow.pipeline.scoring import score_insight_novelty

    rows = [c for c in claims if (c.text or "").strip()]
    if len(rows) < 2:
        return None
    lines = "\n".join(f"- {(c.text or '').strip()}" for c in rows)
    prompt = (
        "Combine the following claims into ONE sharp, declarative sentence under 20 words.\n\n"
        f"Claims:\n{lines}\n\n"
        "Rules:\n"
        "- Must be specific and testable\n"
        "- No vague phrasing (no 'various', 'in many ways', 'matters because')\n"
        "- One sentence only, ending with a period\n"
        "- No markdown or quotes\n"
        "Return the sentence only."
    )
    try:
        raw = (llm_fn(prompt) or "").strip()
    except Exception:  # pragma: no cover
        return None
    raw = re.sub(r"^[\"']|[\"']$", "", raw).strip()
    words = raw.split()
    if not raw or not raw.endswith(".") or len(words) > CORE_INSIGHT_MAX_WORDS:
        return None
    if score_insight_novelty(raw) < 0.35:
        return None
    return raw


def resolve_core_insight(
    claims: Sequence[ClaimRow],
    *,
    llm_fn: Optional[Callable[[str], str]] = None,
    synthesis_novelty_trigger: float = DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER,
) -> str:
    from report_control_workflow.pipeline.scoring import score_insight_novelty

    rows = [c for c in claims if (c.text or "").strip()]
    core = extract_core_insight(claims)
    if not llm_fn or len(rows) < 2:
        return core
    if core and score_insight_novelty(core) >= synthesis_novelty_trigger:
        return core
    synthesized = synthesize_core_insight(claims, llm_fn)
    return synthesized if synthesized else core
