# backend/blueprint_v1/llm_runner.py
"""Optional Ollama JSON calls; safe fallbacks when offline."""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def _json_integrity_enabled() -> bool:
    v = (os.getenv("SOAPBOXX_JSON_INTEGRITY_LOG") or os.getenv("SOAPBOXX_OLLAMA_DEBUG") or "").strip().lower()
    return v in ("1", "true", "yes")


def json_integrity_hint(content: str, err: Optional[Exception] = None) -> Dict[str, Any]:
    """
    Failure-attribution heuristics when JSON parsing fails (not classification of ground truth).

    Biases toward likely token truncation vs other parse shapes for logging and optional retry policy.
    Does not measure semantic density or output quality inside valid JSON.
    """
    s = (content or "").strip()
    n = len(s)
    err_s = (str(err) if err else "").lower()
    msg = (getattr(err, "msg", "") or "").lower() if isinstance(err, json.JSONDecodeError) else err_s
    likely_truncation = (
        "unterminated string" in msg
        or "invalid \\escape" in msg and n > 500
        or ("expecting" in msg and "delimiter" in msg and n > 800)
    )
    tail = s[-160:].replace("\n", " ") if s else ""
    return {
        "content_chars": n,
        "likely_token_truncation": likely_truncation,
        "parse_error_class": type(err).__name__ if err else None,
        "tail_preview": tail,
    }


def _log_json_integrity(cleaned: str, err: Exception) -> None:
    if not _json_integrity_enabled():
        return
    hint = json_integrity_hint(cleaned, err)
    print(
        "[blueprint_v1.llm_runner] JSON integrity: "
        f"likely_truncation={hint['likely_token_truncation']} "
        f"chars={hint['content_chars']} "
        f"err={hint['parse_error_class']} "
        f"tail={hint['tail_preview']!r}",
        file=sys.stderr,
    )


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def run_json_prompt(
    user_prompt: str,
    *,
    system: str = "You output only valid JSON. No markdown fences.",
    max_tokens: int = 2_048,
    temperature: float = 0.2,
) -> Optional[Dict[str, Any]]:
    """
    Call Ollama ``/api/chat`` with JSON-shaped reply. Returns None if model unset or call fails.
    """
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        return None
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
        "format": "json",
    }
    try:
        req = urllib.request.Request(
            f"{host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=float(os.getenv("SOAPBOXX_OLLAMA_HTTP_TIMEOUT", "900"))) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        msg = (body.get("message") or {}).get("content") or ""
        cleaned = _strip_json_fence(msg)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as je:
            _log_json_integrity(cleaned, je)
            if (os.getenv("SOAPBOXX_OLLAMA_DEBUG") or "").strip().lower() in ("1", "true", "yes"):
                print(f"[blueprint_v1.llm_runner] Ollama JSON parse failed: {je}", file=sys.stderr)
            return None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as e:
        if (os.getenv("SOAPBOXX_OLLAMA_DEBUG") or "").strip().lower() in ("1", "true", "yes"):
            print(f"[blueprint_v1.llm_runner] Ollama JSON call failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def run_text_prompt(
    user_prompt: str,
    *,
    system: str = "You follow instructions precisely.",
    max_tokens: int = 4_096,
    temperature: float = 0.2,
) -> Optional[str]:
    """
    Call Ollama ``/api/chat`` for plain-text / markdown output (no ``format: json``).

    Use for network-facing editorial prompts; use ``run_json_prompt`` for JSON contracts.
    """
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip()
    if not model:
        return None
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    try:
        req = urllib.request.Request(
            f"{host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=float(os.getenv("SOAPBOXX_OLLAMA_HTTP_TIMEOUT", "900"))) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        msg = (body.get("message") or {}).get("content") or ""
        out = str(msg).strip()
        return out if out else None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        if (os.getenv("SOAPBOXX_OLLAMA_DEBUG") or "").strip().lower() in ("1", "true", "yes"):
            print(f"[blueprint_v1.llm_runner] Ollama text call failed: {type(e).__name__}: {e}", file=sys.stderr)
        return None
