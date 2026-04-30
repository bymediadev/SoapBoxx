# tests/test_episode_report_brief_v2_wiring.py
from __future__ import annotations

import os

import pytest

from backend.episode_brief_v2 import format_brief_v2_markdown_section, segments_from_transcript_for_brief_v2


def test_segments_from_transcript_roundtrip():
    t = "Para one.\n\nPara two with more words here.\n\n" + ("x " * 900)
    segs = segments_from_transcript_for_brief_v2(t, chunk_chars=200)
    assert len(segs) >= 1
    assert all("id" in s and "text" in s for s in segs)


def test_format_brief_v2_markdown_shows_failure():
    b = {
        "thesis": None,
        "claims": [{"is_spine_eligible": False}, {"is_spine_eligible": True}],
        "status": {"is_shippable": False, "fail_reasons": ["INSUFFICIENT_SPINE_MATERIAL"]},
    }
    md = format_brief_v2_markdown_section(b)
    assert "Thesis construction failed" in md
    assert "INSUFFICIENT_SPINE_MATERIAL" in md


@pytest.mark.skipif(
    not os.getenv("SOAPBOXX_RUN_BRIEF_V2_INTEGRATION"),
    reason="Set SOAPBOXX_RUN_BRIEF_V2_INTEGRATION=1 to run (calls full generate_episode_report_v3).",
)
def test_generate_episode_report_v3_attaches_brief_v2_when_env_on():
    pytest.importorskip("backend.episode_report_v3")
    from backend.episode_report_v3 import generate_episode_report_v3

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("SOAPBOXX_BRIEF_V2", "1")
        # Minimal metadata; real test needs offline/mock brief — skip by default
        out = generate_episode_report_v3(
            "short",
            {"title": "T", "creator": "C", "genre": "News"},
            strict_references=False,
        )
        assert "episode_brief_v2" in (out.get("report_v3") or {})


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
