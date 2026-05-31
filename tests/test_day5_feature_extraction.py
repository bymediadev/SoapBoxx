"""Day 5 — seven structural metrics."""

from __future__ import annotations

import pytest

from backend.models import EpisodeFeatures
from backend.services.feature_service import extract_v1_features, run_feature_extraction
from tests.utils.db_reset import reset_v1_tables
from tests.utils.pipeline import FIXTURE_TRANSCRIPT, seed_episode_with_transcript

pytestmark = pytest.mark.v1_day5

REQUIRED = (
    "hook_length_seconds",
    "intro_length_seconds",
    "question_count",
    "speaking_turns",
    "host_guest_ratio",
    "topic_shift_count",
    "cta_present",
)


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_features_created(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        run_feature_extraction(db, eid)
        row = db.get(EpisodeFeatures, eid)
        assert row is not None
        assert row.feature_schema_version == "v1"
        assert row.extraction_version == "1.0.0"
        assert row.aggregation_version == "1.2.0"
    finally:
        db.close()


def test_required_metrics_present(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        result = run_feature_extraction(db, eid)
        for k in REQUIRED:
            assert k in result.features
    finally:
        db.close()


def test_feature_types(v1_db_clean):
    text = FIXTURE_TRANSCRIPT.read_text(encoding="utf-8")
    f = extract_v1_features(text)
    assert isinstance(f["question_count"], int)
    assert isinstance(f["cta_present"], bool)
    assert isinstance(f["host_guest_ratio"], float)


def test_hook_and_intro_bounded_for_unstructured_blob():
    # A long structureless transcript must not report the entire runtime as the
    # hook or intro — those describe the opening of the episode.
    from backend.services.transcription_service import build_segments_from_transcript

    blob = " ".join(
        f"We talk about idea {i} and why it matters to listeners today."
        for i in range(80)
    )
    raw = build_segments_from_transcript(blob)
    segments = [
        {"start": s["start_time"], "end": s["end_time"], "text": s["text"]}
        for s in raw
    ]
    assert len(segments) > 1

    f = extract_v1_features(blob, segments)
    total_end = segments[-1]["end"]

    assert 0 < f["hook_length_seconds"] <= 120.0
    assert f["hook_length_seconds"] < total_end
    assert 0 < f["intro_length_seconds"] <= 240.0
    assert f["intro_length_seconds"] < total_end


def test_hook_and_intro_use_exact_stt_timestamps():
    """Real Whisper segments should drive hook/intro, not word-rate estimates."""
    segments = [
        {"start": 0.0, "end": 18.5, "text": "Welcome to the show. Here is the setup."},
        {"start": 18.5, "end": 45.0, "text": "Anyway, let's talk about the main topic."},
        {"start": 45.0, "end": 120.0, "text": "Deep dive content continues for a while."},
    ]
    text = " ".join(s["text"] for s in segments)
    f = extract_v1_features(text, segments)

    assert f["hook_length_seconds"] == 18.5
    assert f["intro_length_seconds"] == 18.5
