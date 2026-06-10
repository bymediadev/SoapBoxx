"""Consolidated LLM access for Layer 2 enhancement (not Layer 1 measurement)."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Sequence

import httpx

from backend.http_verify import httpx_verify_arg

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.I)

# Free-tier friendly models (verified against generativelanguage.googleapis.com).
# gemini-2.0-* returns limit:0 on free tier — deprecated/shut down.
_DEFAULT_NARRATIVE_MODEL = "gemini-2.5-flash"
_NARRATIVE_MODEL_FALLBACKS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
)


def gemini_api_key() -> Optional[str]:
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = (os.getenv(name) or "").strip()
        if val:
            return val
    return None


def narrative_model_candidates() -> List[str]:
    """
    Ordered model list for narrative analysis.
    Override primary via SOAPBOXX_NARRATIVE_MODEL; optional comma list in
    SOAPBOXX_NARRATIVE_MODEL_FALLBACKS appends after primary.
    """
    primary = (os.getenv("SOAPBOXX_NARRATIVE_MODEL") or _DEFAULT_NARRATIVE_MODEL).strip()
    extra_raw = (os.getenv("SOAPBOXX_NARRATIVE_MODEL_FALLBACKS") or "").strip()
    extra = [m.strip() for m in extra_raw.split(",") if m.strip()] if extra_raw else []

    ordered: List[str] = []
    for name in [primary, *extra, *_NARRATIVE_MODEL_FALLBACKS]:
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def narrative_model_name() -> str:
    candidates = narrative_model_candidates()
    return candidates[0] if candidates else _DEFAULT_NARRATIVE_MODEL


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


def _should_try_next_model(status_code: int, error_message: str) -> bool:
    msg = (error_message or "").lower()
    if status_code in (404, 429):
        return True
    if status_code == 403 and ("quota" in msg or "limit" in msg):
        return True
    return False


def _call_gemini_model(
    *,
    model_name: str,
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: float,
) -> tuple[Optional[Dict[str, Any]], Optional[int], str]:
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
        with httpx.Client(timeout=timeout_seconds, verify=httpx_verify_arg()) as client:
            resp = client.post(url, params={"key": api_key}, json=payload)
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
        return None, None, str(exc)

    if resp.status_code >= 400:
        try:
            err = resp.json().get("error", {})
            message = str(err.get("message") or resp.text)
        except (ValueError, json.JSONDecodeError):
            message = resp.text
        return None, resp.status_code, message

    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        return None, None, str(exc)

    candidates = data.get("candidates") or []
    if not candidates:
        return None, 200, "empty candidates"
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    parsed = _extract_json(text)
    if not parsed:
        return None, 200, "unparseable json"
    parsed["_model_used"] = model_name
    return parsed, 200, ""


def run_gemini_json(
    *,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    models: Optional[Sequence[str]] = None,
    timeout_seconds: float = 45.0,
) -> Optional[Dict[str, Any]]:
    """
    Call Gemini generateContent and parse a JSON object from the response.
    Tries an ordered model list when quota or availability errors occur.
    Returns None when no API key, all models fail, or output is unparseable.
    """
    api_key = gemini_api_key()
    if not api_key:
        return None

    candidates = list(models or [])
    if model:
        candidates = [model.strip(), *[m for m in candidates if m != model.strip()]]
    if not candidates:
        candidates = narrative_model_candidates()

    for model_name in candidates:
        parsed, status, err = _call_gemini_model(
            model_name=model_name,
            api_key=api_key,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=timeout_seconds,
        )
        if parsed:
            return parsed
        if status is not None and _should_try_next_model(status, err):
            continue
        break

    return None
