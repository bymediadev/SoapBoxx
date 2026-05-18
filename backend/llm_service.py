"""
Central LLM entry point for SoapBoxx (interim facade over workflow LLM).

UI and feature modules should import from here instead of ``soapboxx_v3_workflow``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from .soapboxx_v3_workflow import call_llm as _workflow_call_llm
    from .soapboxx_v3_workflow import call_llm_json as _workflow_call_llm_json
except ImportError:
    from soapboxx_v3_workflow import call_llm as _workflow_call_llm  # type: ignore
    from soapboxx_v3_workflow import call_llm_json as _workflow_call_llm_json  # type: ignore


def call_llm(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: str = "You follow instructions exactly. When asked for JSON, respond with ONLY valid JSON — no markdown fences, no commentary.",
    client: Any = None,
    json_format: bool = False,
    stage: str = "llm_service",
) -> Dict[str, Any]:
    """Workflow LLM (Ollama or Groq per env). Returns ``{"text", "data"}`` envelope."""
    return _workflow_call_llm(
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
    client: Any = None,
) -> Any:
    return _workflow_call_llm_json(
        prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        client=client,
    )


def call_llm_text(
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float = 0.2,
    system: Optional[str] = None,
    stage: str = "llm_service",
) -> str:
    """Convenience: return trimmed ``text`` from the envelope."""
    kwargs: Dict[str, Any] = {
        "max_tokens": max_tokens,
        "temperature": temperature,
        "json_format": False,
        "stage": stage,
    }
    if system is not None:
        kwargs["system"] = system
    env = call_llm(prompt, **kwargs)
    return (env.get("text") or "").strip()
