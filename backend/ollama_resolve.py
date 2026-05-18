"""
Resolve which Ollama model SoapBoxx should use (guest research, episode brief, feedback, Reverb).

If ``SOAPBOXX_OLLAMA_MODEL`` is set, that name is used. Otherwise we probe ``OLLAMA_HOST``/api/tags
so an installed Ollama with pulled models works without extra .env entries.
"""

from __future__ import annotations

import os
import time
from typing import List, Optional, Tuple

import requests

try:
    from .http_verify import requests_verify_arg
except ImportError:
    from http_verify import requests_verify_arg  # type: ignore

_OLLAMA_TAGS_CACHE: Optional[Tuple[float, List[str]]] = None
_OLLAMA_TAGS_TTL = 45.0
_AUTOPICK_LOGGED = False


def ollama_host_base() -> str:
    return (
        os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434") or "http://127.0.0.1:11434"
    ).rstrip("/")


def fetch_ollama_model_names() -> List[str]:
    """Model names from ``GET /api/tags`` (short-lived process cache)."""
    global _OLLAMA_TAGS_CACHE
    now = time.monotonic()
    if _OLLAMA_TAGS_CACHE and (now - _OLLAMA_TAGS_CACHE[0]) < _OLLAMA_TAGS_TTL:
        return _OLLAMA_TAGS_CACHE[1]

    names: List[str] = []
    try:
        url = f"{ollama_host_base()}/api/tags"
        r = requests.get(url, timeout=(2.0, 6.0), verify=requests_verify_arg())
        if r.status_code != 200:
            _OLLAMA_TAGS_CACHE = (now, names)
            return names
        data = r.json()
        for m in data.get("models") or []:
            if isinstance(m, dict) and m.get("name"):
                n = str(m["name"]).strip()
                if n:
                    names.append(n)
    except Exception:
        names = []
    _OLLAMA_TAGS_CACHE = (now, names)
    return names


def pick_ollama_model_from_tags(names: List[str]) -> str:
    if not names:
        return ""
    preferred = (
        "llama3.1",
        "llama3.2",
        "llama3",
        "mistral-nemo",
        "mistral",
        "phi3",
        "gemma2",
        "qwen2.5",
        "qwen2",
        "llama2",
    )
    lower_to_original = {n.lower(): n for n in names}
    for p in preferred:
        for low, original in lower_to_original.items():
            if p in low:
                return original
    return names[0]


def resolved_ollama_model() -> str:
    """Explicit ``SOAPBOXX_OLLAMA_MODEL``, else a sensible default from local Ollama tags."""
    global _AUTOPICK_LOGGED
    explicit = (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip()
    if explicit:
        return explicit
    names = fetch_ollama_model_names()
    picked = pick_ollama_model_from_tags(names)
    if picked and not _AUTOPICK_LOGGED:
        _AUTOPICK_LOGGED = True
        print(
            f"SoapBoxx: SOAPBOXX_OLLAMA_MODEL not set; using Ollama model {picked!r} "
            f"(from {ollama_host_base()}/api/tags). Set SOAPBOXX_OLLAMA_MODEL to pin a model."
        )
    return picked
