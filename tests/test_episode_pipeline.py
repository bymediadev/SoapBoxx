"""Full episode pipeline service (transcribe → features → translate)."""

from __future__ import annotations

import pytest

from backend.models import EpisodeFeatures, EpisodeTranslation
from backend.services.episode_pipeline_service import run_episode_pipeline
from tests.utils.db_reset import reset_v1_tables
from tests.utils.pipeline import seed_episode_with_transcript

pytestmark = pytest.mark.v1_day7


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_run_episode_pipeline_end_to_end(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        result = run_episode_pipeline(db, eid)
        assert result.status == "ready"
        assert result.template_id in ("A", "B", "C")
        assert result.insight_preview
        assert db.get(EpisodeFeatures, eid) is not None
        assert db.get(EpisodeTranslation, eid) is not None
        transcribe_step = next(s for s in result.steps if s.get("step") == "transcribe")
        assert transcribe_step.get("skipped") is True
        assert transcribe_step.get("reason") == "existing_transcript"
        assert transcribe_step.get("reused") is True
        assert result.transcript_source == "existing"
        assert result.segment_count == transcribe_step["segment_count"]
        assert result.segment_count > 0
        features_step = next(s for s in result.steps if s.get("step") == "features")
        assert features_step.get("recomputed") is True
    finally:
        db.close()
