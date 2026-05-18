"""
Extract interview/research questions from a transcript (OpenAI or Ollama).
"""

from __future__ import annotations

import os
from typing import Literal, Optional

QuestionBackend = Literal["auto", "offline", "openai"]

_OPENAI_PROMPT = """Analyze the following transcript and extract all questions that would be valuable for research or discussion.
Focus on:
- Direct questions (ending with ?)
- Implicit questions or topics that could be phrased as questions
- Questions that would benefit from further research

Transcript: {transcript}

Return only the questions, one per line, without numbering or additional text.
"""

_OFFLINE_SYSTEM = "You extract podcast guest questions. Be concise and grounded in the transcript."
_OFFLINE_USER = (
    "Extract useful guest-interview questions from this transcript.\n"
    "Return only one question per line, no numbering, no extra text.\n\n"
    "TRANSCRIPT:\n{transcript}"
)


def extract_questions_from_transcript(
    transcript: str,
    *,
    backend: QuestionBackend = "auto",
    min_chars: int = 50,
) -> Optional[str]:
    """
    Return newline-separated questions, or None if extraction failed or skipped.
    """
    text = (transcript or "").strip()
    if len(text) < min_chars:
        return None

    mode = (backend or "auto").strip().lower()
    if mode not in ("auto", "offline", "openai"):
        mode = "auto"

    if mode == "offline":
        return _extract_offline(text)
    if mode == "openai":
        return _extract_openai(text)
    # auto: offline first, then openai
    return _extract_offline(text) or _extract_openai(text)


def _extract_openai(transcript: str) -> Optional[str]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key or api_key.lower() == "not set":
        return None
    try:
        from openai import OpenAI

        try:
            from .guest_research import _build_openai_sdk_client

            client = _build_openai_sdk_client(api_key)
        except Exception:
            client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=os.getenv("SOAPBOXX_QUESTION_EXTRACT_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "user", "content": _OPENAI_PROMPT.format(transcript=transcript)}
            ],
            max_tokens=200,
            temperature=0.3,
        )
        content = (response.choices[0].message.content or "").strip()
        return content or None
    except Exception:
        return None


def _extract_offline(transcript: str) -> Optional[str]:
    if not (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip():
        return None
    try:
        try:
            from .episode_intelligence import _ollama_chat_invoke
        except ImportError:
            from episode_intelligence import _ollama_chat_invoke  # type: ignore

        raw = _ollama_chat_invoke(
            _OFFLINE_SYSTEM,
            _OFFLINE_USER.format(transcript=transcript),
            max_tokens=512,
            temperature=0.2,
            stage="question_extraction.offline",
            append_brief_envelope_suffix=False,
        )
        content = str(raw or "").strip()
        return content or None
    except Exception:
        return None
