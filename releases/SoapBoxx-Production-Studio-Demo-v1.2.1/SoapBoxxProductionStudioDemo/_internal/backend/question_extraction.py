"""
Extract and frame host-ready interview questions from a transcript.
"""

from __future__ import annotations

import os
from typing import List, Literal, Optional, Sequence

from .question_framing import (
    build_live_capture_prompt,
    format_questions_for_display,
    parse_question_lines,
    question_style_from_env,
)

QuestionBackend = Literal["auto", "offline", "openai"]


def extract_questions_from_transcript(
    transcript: str,
    *,
    backend: QuestionBackend = "auto",
    min_chars: int = 50,
    known: Optional[Sequence[str]] = None,
    max_questions: int = 5,
) -> Optional[str]:
    """
    Return newline-separated host-ready questions, or None if extraction failed.
    """
    text = (transcript or "").strip()
    if len(text) < min_chars:
        return None

    mode = (backend or "auto").strip().lower()
    if mode not in ("auto", "offline", "openai"):
        mode = "auto"

    raw: Optional[str] = None
    if mode == "offline":
        raw = _extract_offline(text)
    elif mode == "openai":
        raw = _extract_openai(text)
    else:
        raw = _extract_offline(text) or _extract_openai(text)

    if not raw:
        return None

    questions = parse_question_lines(
        raw, known=known, max_items=max(1, min(12, int(max_questions)))
    )
    if not questions:
        return None
    return format_questions_for_display(questions)


def extract_questions_list(
    transcript: str,
    *,
    backend: QuestionBackend = "auto",
    min_chars: int = 50,
    known: Optional[Sequence[str]] = None,
    max_questions: int = 5,
) -> List[str]:
    """Structured list API for UI."""
    raw = extract_questions_from_transcript(
        transcript,
        backend=backend,
        min_chars=min_chars,
        known=known,
        max_questions=max_questions,
    )
    if not raw:
        return []
    return parse_question_lines(raw, known=known, max_items=max_questions)


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

        system, user = build_live_capture_prompt(
            transcript,
            style=question_style_from_env(),
            max_questions=int(os.getenv("SOAPBOXX_QUESTION_MAX", "5")),
        )
        response = client.chat.completions.create(
            model=os.getenv("SOAPBOXX_QUESTION_EXTRACT_MODEL", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=int(os.getenv("SOAPBOXX_QUESTION_MAX_TOKENS", "400")),
            temperature=float(os.getenv("SOAPBOXX_QUESTION_TEMPERATURE", "0.35")),
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

        system, user = build_live_capture_prompt(
            transcript,
            style=question_style_from_env(),
            max_questions=int(os.getenv("SOAPBOXX_QUESTION_MAX", "5")),
        )
        raw = _ollama_chat_invoke(
            system,
            user,
            max_tokens=int(os.getenv("SOAPBOXX_QUESTION_MAX_TOKENS", "512")),
            temperature=float(os.getenv("SOAPBOXX_QUESTION_TEMPERATURE", "0.25")),
            stage="question_extraction.framed",
            append_brief_envelope_suffix=False,
        )
        content = str(raw or "").strip()
        return content or None
    except Exception:
        return None
