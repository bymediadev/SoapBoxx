"""Presentation-only report renderer (no decision/scoring changes)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from report_renderer import (  # noqa: E402
    CLIENT_REPORT_KEYS,
    get_editorial_weights,
    generate_client_report,
    generate_client_report_markdown,
    render_report,
    render_report_markdown,
    resolve_editorial_profile_key,
    validate_client_report,
    validate_report_output,
)


def _minimal_eval(tier: str, *, transport_degraded: bool = False) -> dict:
    return {
        "decision": {
            "tier": tier,
            "transport_degraded": transport_degraded,
            "trace": {"transport_degraded": transport_degraded},
        },
        "input_quality_components": {
            "input_quality_score": 0.8,
            "extraction_success_score": 0.7,
            "grounding_density_score": 0.6,
        },
    }


def test_render_report_has_summary_verdict_and_no_raw_scores_in_output():
    r = render_report(_minimal_eval("highlight"))
    assert "summary" in r and "verdict" in r
    assert r.get("system_version")
    assert r.get("schema_version")
    assert "0." not in r["summary"]  # no numeric scores in summary
    assert "High-quality" in r["verdict"] or "standout" in r["verdict"].lower()
    validate_report_output(r)


def test_reject_input_issues():
    ev = _minimal_eval("reject_input")
    ev["render_mode"] = "analyst"
    r = render_report(ev)
    assert r["issues"]
    assert r["quality_breakdown"]["input_quality"] in ("good", "weak", "failed")


def test_transport_system_notes():
    ev = _minimal_eval("accept_strong", transport_degraded=True)
    ev["render_mode"] = "analyst"
    r = render_report(ev)
    assert r["system_notes"]
    assert "degraded" in r["system_notes"].lower()


def test_insights_from_report_v3():
    ev = _minimal_eval("accept_moderate")
    ev["report_v3"] = {"clean_insights": ["First insight line.", "Second insight line."]}
    ev["render_mode"] = "analyst"
    r = render_report(ev)
    assert len(r["insights"]) >= 2
    assert r["insight_roles"][0] == "lead"
    assert all(x == "supporting" for x in r["insight_roles"][1:])


def test_insights_follow_clean_insight_source_order():
    ev = _minimal_eval("accept_moderate")
    ev["report_v3"] = {
        "clean_insights": [
            "First bullet in source order.",
            "Second bullet in source order.",
        ],
    }
    ev["render_mode"] = "analyst"
    r = render_report(ev)
    assert r["insights"][0].startswith("First bullet")
    assert r["insights"][1].startswith("Second bullet")


def test_markdown_contains_sections():
    ev = _minimal_eval("low_confidence")
    ev["report_v3"] = {"clean_insights": ["Only one takeaway here."]}
    ev["render_mode"] = "analyst"
    r = render_report(ev)
    md = render_report_markdown(r)
    assert "## Summary" in md
    assert "## Verdict" in md
    assert "### Lead takeaway" in md


def test_markdown_also_notable_when_multiple_insights():
    ev = _minimal_eval("accept_moderate")
    ev["report_v3"] = {"clean_insights": ["Alpha insight text.", "Beta insight text."]}
    ev["render_mode"] = "analyst"
    r = render_report(ev)
    md = render_report_markdown(r)
    assert "### Also notable" in md


def test_explicit_editorial_profile_on_result_and_meta():
    ev = _minimal_eval("accept_moderate")
    ev["editorial_profile"] = "solo"
    assert resolve_editorial_profile_key(ev) == "solo"
    r = render_report(ev)
    assert r["editorial_profile"] == "solo"

    ev2 = _minimal_eval("accept_moderate")
    ev2["meta"] = {"editorial_profile": "news"}
    assert resolve_editorial_profile_key(ev2) == "news"
    assert render_report(ev2)["editorial_profile"] == "news"


def test_infer_interview_from_episode_snapshot():
    ev = _minimal_eval("accept_moderate")
    ev["report_v3"] = {
        "episode_snapshot": {"genre": "Talk", "title": "Interview with Jane Doe"},
        "clean_insights": ["A", "B"],
    }
    assert resolve_editorial_profile_key(ev) == "interview"


def test_invalid_profile_falls_back_to_balanced_weights():
    w = get_editorial_weights("not_a_real_profile")
    assert w == get_editorial_weights("balanced")


def test_markdown_mentions_editorial_preset():
    ev = _minimal_eval("accept_moderate")
    ev["editorial_profile"] = "interview"
    ev["report_v3"] = {"clean_insights": ["One."]}
    ev["render_mode"] = "analyst"
    md = render_report_markdown(render_report(ev))
    assert "interview" in md.lower()


def test_reader_mode_hides_noncritical_issues_and_quality_breakdown():
    ev = _minimal_eval("accept_moderate")
    ev["render_mode"] = "reader"
    ev["report_v3"] = {"clean_insights": ["A takeaway."]}
    r = render_report(ev)
    assert r["issues"] == []
    assert r["system_notes"] is None
    md = render_report_markdown(r)
    assert "## Quality breakdown" not in md


def test_default_mode_is_analyst():
    ev = _minimal_eval("accept_moderate")
    r = render_report(ev)
    assert r["render_mode"] == "analyst"


def test_sales_mode_growth_memo_shape():
    ev = _minimal_eval("accept_moderate")
    ev["render_mode"] = "sales"
    r = render_report(ev)
    assert r["render_mode"] == "sales"
    assert "Podcast Growth Breakdown" in r["verdict"]
    assert r["insights"] and len(r["insights"]) <= 7
    assert isinstance(r["quality_breakdown"], dict) and "confidence" in r["quality_breakdown"]


def test_generate_client_report_forces_sales_mode():
    ev = _minimal_eval("accept_moderate")
    r = generate_client_report(ev)
    assert set(r.keys()) == CLIENT_REPORT_KEYS
    validate_client_report(r)
    assert "render_mode" not in r and "schema_version" not in r and "verdict" not in r
    assert r["summary"]
    assert r["issues"]
    assert r["insights"]
    assert r["clips"]
    assert r["cta"]
    md = generate_client_report_markdown(ev)
    assert "## Summary" in md
    assert "## What’s limiting growth" in md
    assert "## Clip ideas" in md
    assert "## Call to action" in md


def test_client_report_simplified_low_signal():
    ev = _minimal_eval("accept_moderate")
    ev["report_v3"] = {"signal_mode": "LOW_SIGNAL", "clean_insights": ["A single strong line about the episode."]}
    r = generate_client_report(ev)
    assert len(r["insights"]) == 1
    assert len(r["clips"]) <= 1


def test_client_report_insights_follow_source_order():
    ev = _minimal_eval("accept_moderate")
    ev["report_v3"] = {
        "signal_mode": "HIGH_SIGNAL",
        "clean_insights": ["First ordered insight.", "Second ordered insight.", "Third ordered insight."],
        "narrative_reconstruction": {
            "core_thesis": "x" * 30,
            "supporting_mechanism": "y" * 30,
            "practical_translation": "z" * 30,
        },
        "segments": [{"name": "a"}, {"name": "b"}],
    }
    r = generate_client_report(ev)
    assert r["insights"][0].startswith("First ordered")
    assert r["insights"][1].startswith("Second ordered")
    assert len(r["insights"]) >= 2


def test_client_report_clips_are_single_idea_excerpts():
    ev = _minimal_eval("accept_strong")
    ev["report_v3"] = {
        "signal_mode": "HIGH_SIGNAL",
        "clean_insights": [
            "One idea here. A completely different second idea that would confuse a clip.",
        ],
        "narrative_reconstruction": {"core_thesis": "x" * 30, "supporting_mechanism": "y" * 30, "practical_translation": "z" * 30},
        "segments": [{"name": "a"}, {"name": "b"}],
    }
    r = generate_client_report(ev)
    assert r["clips"]
    assert "completely different" not in (r["clips"][0] or "").lower()


def test_fixed_profile_mode_skips_inference():
    ev = _minimal_eval("accept_moderate")
    ev["editorial_profile_mode"] = "fixed"
    ev["report_v3"] = {
        "episode_snapshot": {"genre": "Talk", "title": "Interview with Someone"},
        "clean_insights": ["x"],
    }
    assert resolve_editorial_profile_key(ev) == "balanced"


def test_registry_maps_case_fire_to_narrative():
    ev = _minimal_eval("accept_moderate")
    ev["meta"] = {"episode_format": "case_fire"}
    ev["report_v3"] = {"clean_insights": ["x"]}
    assert resolve_editorial_profile_key(ev) == "narrative"
