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
        assert db.get(EpisodeFeatures, eid) is not None
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
