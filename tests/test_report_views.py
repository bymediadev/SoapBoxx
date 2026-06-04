"""Layer 4 report views — producer, actions, transcript warnings."""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.models import Episode, EpisodeFeatures
from backend.services.coaching_report_service import CoachingReport
from backend.services.report_views_service import (
    build_actions_report,
    build_producer_report,
    detect_transcript_warning,
)


def test_detect_demo_transcript():
    ep = Episode(id=1, podcast_id=1, title="Planet Money · Episode #1")
    ep.full_transcript = "Host: Welcome to the SoapBoxx test episode."
    w = detect_transcript_warning(ep)
    assert w is not None
    assert w["code"] == "demo_transcript"


def test_build_actions_from_playbook():
    ep = Episode(id=1, podcast_id=1, title="Test")
    ep.full_transcript = "Real transcript " * 20
    report = CoachingReport(
        template_playbook={
            "review_these": ["Check first 60s hook", "Scan question placement"],
            "how_its_built": ["Fast entry into premise"],
        },
        producer_notes={"edit_flags": ["Long segment at 12:00"]},
    )
    out = build_actions_report(ep, report)
    assert len(out["actions"]) >= 2
    assert out["actions"][0]["category"] == "replay"
    assert any("Check first 60s" in a["text"] for a in out["actions"])
    assert out["keep_patterns"]


def test_producer_report_omits_cohort_fields():
    ep = Episode(id=1, podcast_id=1, title="Show")
    ep.full_transcript = "x " * 100
    features = EpisodeFeatures(
        episode_id=1,
        hook_length_seconds=6.0,
        intro_length_seconds=10.0,
        question_count=3,
        speaking_turns=8,
        host_guest_ratio=0.5,
        topic_shift_count=0,
        cta_present=True,
    )
    report = CoachingReport(
        structural_identity=["Narrative thread"],
        listener_experience=["Sparse Q&A pacing"],
        measurement_cohort_note="16 episodes excluded",
        leverage_points=["Band A", "Band B", "Band C", "Band D"],
    )
    out = build_producer_report(ep, features, report, "C")
    assert "measurement_cohort_note" not in out
    assert "measurement_stamp" not in out
    assert "compared_with_library" not in out
    assert len(out["leverage_points"]) == 3
    assert out["measurements"]["question_count"] == 3
