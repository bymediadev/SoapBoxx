"""Day 7 — translation layer."""

from __future__ import annotations

import pytest

from backend.models import EpisodeTranslation
from backend.services.translation_service import run_translation
from tests.utils.db_reset import reset_v1_tables
from backend.services.feature_service import run_feature_extraction
from tests.utils.pipeline import run_all_steps, seed_episode_with_transcript

pytestmark = pytest.mark.v1_day7

FORBIDDEN = ("good", "bad", "score", "rank", "best")


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_translation_created(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        run_all_steps(db, eid)
        assert db.get(EpisodeTranslation, eid) is not None
    finally:
        db.close()


def test_no_scoring_words(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        run_all_steps(db, eid)
        text = db.get(EpisodeTranslation, eid).insight_text.lower()
        assert not any(w in text for w in FORBIDDEN)
    finally:
        db.close()


def test_translation_not_empty(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        run_feature_extraction(db, eid)
        result = run_translation(db, eid)
        assert len(result.insight_text) > 50
    finally:
        db.close()


def test_get_translation_endpoint(v1_db_clean, v1_client):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        run_all_steps(db, eid)
    finally:
        db.close()

    r = v1_client.get(f"/episodes/{eid}/translation")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["episode_id"] == eid
    assert body["insight_text"]
    assert body["report"] is not None
    assert body["report"]["measurement_stamp"]["feature_schema_version"]
