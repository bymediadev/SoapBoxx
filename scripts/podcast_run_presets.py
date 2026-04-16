"""
Environment overlays for real podcast runs (long transcripts, multi-step v3, Ollama).

Use via ``run_youtube_podcast_v3_test.py --preset full|smoke`` (merges into the process
environment before ``episode_brief.py``). Existing ``os.environ`` values are **overridden**
by preset keys so the CLI is self-contained; unset a key in your shell if you need to
force a value after the preset.

Presets do **not** set ``SOAPBOXX_OLLAMA_MODEL`` or ``OLLAMA_HOST`` — keep those in ``.env``.
"""

from __future__ import annotations

from typing import Dict, List

# Long captions (~100k–200k+ chars), 30–90+ minute episodes, many LLM calls.
PRESET_FULL: Dict[str, str] = {
    # Per-request HTTP bounds (seconds). Generous for slow local models + large JSON bodies.
    "SOAPBOXX_OLLAMA_HTTP_TIMEOUT": "1200",
    "SOAPBOXX_OLLAMA_FIRST_BYTE_TIMEOUT": "600",
    "SOAPBOXX_OLLAMA_READ_BODY_TIMEOUT": "1200",
    # Observability: stderr JSON heartbeats + soft stall hints (long runs).
    "SOAPBOXX_OLLAMA_HEARTBEAT": "1",
    "SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC": "45",
    "SOAPBOXX_OLLAMA_HEARTBEAT_SOFT_SEC": "300",
    "SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS": "120000",
    # Brief / workflow windows (chars/words) — raise for full captions; tune to your GPU RAM.
    "SOAPBOXX_BRIEF_MAX_CHARS": "500000",
    "SOAPBOXX_WORKFLOW_MAX_WORDS": "500000",
}

# Faster iteration: shorter HTTP ceilings, smaller brief window, still heartbeats on.
PRESET_SMOKE: Dict[str, str] = {
    "SOAPBOXX_OLLAMA_HTTP_TIMEOUT": "900",
    "SOAPBOXX_OLLAMA_FIRST_BYTE_TIMEOUT": "120",
    "SOAPBOXX_OLLAMA_READ_BODY_TIMEOUT": "900",
    "SOAPBOXX_OLLAMA_HEARTBEAT": "1",
    "SOAPBOXX_OLLAMA_HEARTBEAT_INTERVAL_SEC": "30",
    "SOAPBOXX_OLLAMA_HEARTBEAT_SOFT_SEC": "180",
    "SOAPBOXX_OLLAMA_HEARTBEAT_STALL_MS": "60000",
    "SOAPBOXX_BRIEF_MAX_CHARS": "200000",
    "SOAPBOXX_WORKFLOW_MAX_WORDS": "200000",
}

PRESETS: Dict[str, Dict[str, str]] = {
    "full": PRESET_FULL,
    "smoke": PRESET_SMOKE,
}


def apply_preset(base: Dict[str, str], name: str) -> Dict[str, str]:
    """Return a copy of *base* with preset *name* merged (preset wins)."""
    out = dict(base)
    key = (name or "").strip().lower()
    if not key or key == "none":
        return out
    overlay = PRESETS.get(key)
    if overlay is None:
        raise ValueError(f"Unknown preset {name!r}. Choose: none, full, smoke.")
    out.update(overlay)
    return out


def describe_preset(name: str) -> str:
    key = (name or "").strip().lower()
    if not key or key == "none":
        return "none: do not change environment (use .env only)."
    overlay = PRESETS.get(key)
    if not overlay:
        return f"Unknown preset {name!r}."
    lines: List[str] = [f"preset {key!r} sets:"]
    for k in sorted(overlay.keys()):
        lines.append(f"  {k}={overlay[k]}")
    return "\n".join(lines)


def list_preset_names() -> List[str]:
    return sorted(PRESETS.keys())
