"""Episode Coach Report (sections A–F) — focused post-episode loop."""

import pytest

from backend.episode_coach_report import (
    COACH_SECTION_KEYS,
    COACH_SECTION_TITLES,
    generate_episode_coach_report,
    prepare_coach_transcript,
    render_episode_coach_markdown,
    _normalize_sections,
)


SAMPLE_TRANSCRIPT = """
Host: Welcome back. Today we're talking about habit stacking with our guest Maya.
Maya: Thanks for having me. Habit stacking is when you attach a new habit to one you already do.
Host: Can you give a concrete example?
Maya: After I pour coffee, I write one line in my journal. The coffee is the anchor.
Host: What do hosts get wrong when they interview about habits?
Maya: They ask "tips for everyone" instead of digging into one failure story.
Host: Fair. We'll wrap in a minute — any last thought?
Maya: Pick one anchor this week. Test it for seven days before adding another.
""" * 3


def test_coach_section_keys_order():
    assert COACH_SECTION_KEYS[0] == "episode_summary"
    assert COACH_SECTION_KEYS[-1] == "next_episode_improvements"
    assert len(COACH_SECTION_TITLES) == len(COACH_SECTION_KEYS)


def test_render_markdown_includes_all_sections():
    sections = {
        "episode_summary": "Short episode on habit stacking.",
        "strong_moments": ["Anchor example — concrete and memorable."],
        "weak_moments": ["Rushed closing — guest had more to say."],
        "missed_opportunities": ["Ask for a failure story when guest mentioned it."],
        "host_behavior_patterns": ["Stacked two questions before Maya finished."],
        "next_episode_improvements": [
            "Pause 2 seconds after each guest answer before follow-up.",
            "Prepare one failure-story prompt per guest topic.",
            "End with one actionable challenge, not a generic wrap.",
        ],
    }
    md = render_episode_coach_markdown(sections)
    assert "# Episode Coach Report" in md
    for title in COACH_SECTION_TITLES.values():
        assert f"## {title}" in md
    assert "F. Next Episode Improvements" in md


def test_normalize_sections_caps_lists():
    raw = {
        "episode_summary": "x" * 2000,
        "strong_moments": [f"m{i}" for i in range(10)],
        "weak_moments": [],
        "missed_opportunities": ["a"],
        "host_behavior_patterns": ["b"],
        "next_episode_improvements": [f"i{i}" for i in range(12)],
    }
    out = _normalize_sections(raw)
    assert len(out["episode_summary"]) <= 1200
    assert len(out["strong_moments"]) <= 5
    assert len(out["next_episode_improvements"]) <= 7


def test_generate_heuristic_without_llm(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SOAPBOXX_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("SOAPBOXX_GROQ_API_KEY", raising=False)
    result = generate_episode_coach_report(SAMPLE_TRANSCRIPT)
    assert "markdown" in result
    assert "sections" in result
    assert result["model"] in ("heuristic", "none")
    assert "F. Next Episode Improvements" in result["markdown"]


def test_generate_short_transcript_warning():
    result = generate_episode_coach_report("hello")
    assert "transcript_too_short" in (result.get("warnings") or [])


def test_prepare_coach_transcript_strips_tactiq():
    raw = """# tactiq.io free youtube transcript
# Corruption and Greed: Why Spirit Airlines DIED
# https://www.youtube.com/watch?v=abc
00:00:01.000 Spirit Airlines filed for bankruptcy yesterday.
00:00:05.000 The ultra low cost model stopped working.
"""
    body, title = prepare_coach_transcript(raw)
    assert "tactiq" not in body.lower()
    assert "youtube.com" not in body
    assert "Spirit Airlines" in body
    assert title and "Spirit" in title


def test_heuristic_banner_when_llm_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SOAPBOXX_OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    result = generate_episode_coach_report(SAMPLE_TRANSCRIPT)
    assert "llm_not_configured" in (result.get("warnings") or [])
    assert "Settings" in result["markdown"]
    assert "tactiq" not in result["markdown"].lower()
