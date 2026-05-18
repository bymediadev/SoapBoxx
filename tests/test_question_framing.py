"""Tests for host-ready question framing."""

from __future__ import annotations

from backend.question_framing import (
    build_live_capture_prompt,
    normalize_question_line,
    parse_question_lines,
)


def test_normalize_strips_numbering_and_adds_question_mark():
    q = normalize_question_line("1. What drew you into podcasting")
    assert q == "What drew you into podcasting?"


def test_normalize_rejects_short_junk():
    assert normalize_question_line("Why?") is None
    assert normalize_question_line("Transcript: hello there friend") is None


def test_parse_dedupes():
    raw = "What is your origin story?\nwhat is your origin story?\n2. How do you measure success today?"
    out = parse_question_lines(raw)
    assert len(out) == 2
    assert all(s.endswith("?") for s in out)


def test_build_live_capture_prompt_includes_style():
    _sys, user = build_live_capture_prompt("Host: welcome.", style="direct", max_questions=3)
    assert "3 questions" in user
    assert "Direct" in user or "direct" in user.lower()
    assert "welcome" in user
