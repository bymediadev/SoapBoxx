"""Probe Gemini models for free-tier availability. Loads key from .env only."""
from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.http_verify import requests_verify_arg

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from backend.llm_service import gemini_api_key, narrative_model_candidates

CANDIDATES = list(narrative_model_candidates()) + [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]


def probe(model: str, key: str) -> tuple[str, str]:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Return JSON: {\"ok\": true}"}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    try:
        with httpx.Client(timeout=30.0, verify=requests_verify_arg()) as client:
            resp = client.post(url, params={"key": key}, json=payload)
    except Exception as exc:
        return "error", str(exc)[:120]

    if resp.status_code == 200:
        return "ok", "200"

    try:
        err = resp.json().get("error", {})
        msg = str(err.get("message") or resp.text)[:180]
    except Exception:
        msg = resp.text[:180]
    return f"http_{resp.status_code}", msg


def main() -> None:
    key = gemini_api_key()
    if not key:
        print("NO_KEY")
        raise SystemExit(1)

    print("model\tstatus\tdetail")
    for model in CANDIDATES:
        status, detail = probe(model, key)
        print(f"{model}\t{status}\t{detail}")


if __name__ == "__main__":
    main()
