"""Template C narrative documentary playbook."""

from __future__ import annotations

from backend.models import EpisodeFeatures
from backend.services.coaching_report_service import build_coaching_report
from backend.services.library_benchmarks import LibraryBenchmarks
from backend.services.template_c_playbook import (
    build_template_c_playbook,
    template_c_listener_experience,
)

FORBIDDEN = ("good", "bad", "score", "rank", "best", "weak", "engaging", "engagement")


def _planet_money_factory_town() -> EpisodeFeatures:
    return EpisodeFeatures(
        episode_id=1,
        hook_length_seconds=32.0,
        intro_length_seconds=6.0,
        question_count=3,
        speaking_turns=8,
        host_guest_ratio=0.542,
        topic_shift_count=0,
        cta_present=True,
    )


def test_playbook_has_actionable_review_prompts():
    pb = build_template_c_playbook(_planet_money_factory_town(), library_measured=4)
    assert pb.form == "Narrative documentary"
    assert pb.review_these
    assert any("replay" in r.lower() for r in pb.review_these)
    assert any("question" in r.lower() for r in pb.review_these)
    assert pb.how_its_built
    assert "32" in " ".join(pb.how_its_built) or "seconds" in " ".join(pb.how_its_built).lower()


def test_playbook_feels_like_relatable_reference():
    pb = build_template_c_playbook(_planet_money_factory_town())
    assert "planet money" in pb.feels_like.lower()


def test_listener_experience_relatable_not_metric_dump():
    lines = template_c_listener_experience(_planet_money_factory_town())
    blob = " ".join(lines).lower()
    assert "planet money" in blob or "documentary" in blob
    assert "questions: 3" not in blob


def test_coaching_report_includes_template_playbook():
    lib = LibraryBenchmarks(
        n_measured=4,
        hook_seconds=[30.0, 50.0, 70.0, 90.0],
        intro_seconds=[10.0, 30.0, 60.0, 120.0],
        question_counts=[3, 8, 14, 20],
        speaking_turns=[5, 10, 15, 20],
        guest_ratios=[0.45, 0.5, 0.52, 0.55],
        topic_shifts=[0, 1, 1, 2],
    )

    class _FakeSession:
        pass

    report = build_coaching_report(
        _FakeSession(), _planet_money_factory_town(), library=lib
    )
    assert report.template_playbook is not None
    assert report.template_playbook["form"] == "Narrative documentary"
    assert len(report.template_playbook["review_these"]) >= 3
    blob = " ".join(
        report.template_playbook["review_these"]
        + report.template_playbook["how_its_built"]
        + report.editorial_tradeoffs
    ).lower()
    assert not any(w in blob for w in FORBIDDEN)
