"""Consolidated LLM access for Layer 2 enhancement (not Layer 1 measurement)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import httpx

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.I)


def gemini_api_key() -> Optional[str]:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    return None


def narrative_model_name() -> str:
    return (os.getenv("SOAPBOXX_NARRATIVE_MODEL") or "gemini-2.0-flash").strip()


def narrative_semantic_enabled() -> bool:
    raw = (os.getenv("SOAPBOXX_NARRATIVE_SEMANTIC") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    body = (text or "").strip()
    if not body:
        return None
    fence = _JSON_FENCE.search(body)
    if fence:
        body = fence.group(1).strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_gemini_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    timeout_seconds: float = 90.0,
) -> Optional[Dict[str, Any]]:
    """
    Call Gemini generateContent and parse a JSON object from the response.
    Returns None when no API key, transport error, or unparseable output.
    """
    api_key = gemini_api_key()
    if not api_key:
        return None

    model_name = (model or narrative_model_name()).strip()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_name}:generateContent"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            resp = client.post(url, params={"key": api_key}, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return None

    candidates = data.get("candidates") or []
    if not candidates:
        return None
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    return _extract_json(text)
