"""Diary / WNBA-style episodes — rhetorical questions, no diarization."""

from backend.models import EpisodeFeatures
from backend.services.coaching_report_service import build_coaching_report
from backend.services.library_benchmarks import LibraryBenchmarks
from backend.services.template_classification import (
    is_rhetorical_question_heavy,
    template_id_from_features,
)


def _wnba_diary_features() -> EpisodeFeatures:
    return EpisodeFeatures(
        episode_id=5,
        hook_length_seconds=3.0,
        intro_length_seconds=11.0,
        question_count=44,
        speaking_turns=0,
        host_guest_ratio=0.5,
        topic_shift_count=2,
        feature_schema_version="v1",
        extraction_version="1.0.0",
        aggregation_version="1.2.0",
    )


def test_diary_not_classified_as_interview():
    f = _wnba_diary_features()
    assert template_id_from_features(f) == "C"
    assert is_rhetorical_question_heavy(f)


def test_diary_report_avoids_interview_framing():
    f = _wnba_diary_features()
    lib = LibraryBenchmarks(
        n_measured=5,
        hook_seconds=[20.0, 30.0, 40.0, 50.0, 60.0],
        intro_seconds=[10.0, 20.0, 30.0, 40.0, 50.0],
        question_counts=[3, 8, 12, 20, 44],
        speaking_turns=[0, 4, 8, 12, 16],
        guest_ratios=[0.5, 0.5, 0.52, 0.55, 0.58],
        topic_shifts=[0, 1, 1, 2, 2],
    )

    class _FakeSession:
        pass

    report = build_coaching_report(_FakeSession(), f, library=lib)
    blob = " ".join(
        report.listener_experience
        + report.structural_identity
        + [report.similar_to or ""]
        + report.transcript_limitations
    ).lower()
    assert "questions arrive often" not in blob
    assert "question-led interview" not in blob
    assert "diary" in blob or "rhetorical" in blob
    assert report.transcript_limitations
    assert report.structural_identity[0].startswith("Diary")


def test_interview_still_requires_turns():
    f = EpisodeFeatures(
        episode_id=1,
        question_count=20,
        speaking_turns=10,
        hook_length_seconds=30.0,
        intro_length_seconds=20.0,
    )
    assert template_id_from_features(f) == "B"
