"""V1 full pipeline health check."""

from __future__ import annotations

import os

import pytest

from backend.models import Episode, EpisodeFeatures, EpisodeTranslation, TranscriptSegment
from tests.utils.db_reset import reset_v1_tables
from tests.utils.pipeline import run_all_steps, seed_episode_with_transcript

pytestmark = pytest.mark.v1_e2e


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


@pytest.mark.skipif(
    os.getenv("SOAPBOXX_V1_E2E", "1").strip().lower() in ("0", "false", "no"),
    reason="Set SOAPBOXX_V1_E2E=1 to run full pipeline test",
)
def test_full_pipeline(v1_db_clean):
    from backend.api.deps import get_session_factory
    from sqlalchemy import func, select

    db = get_session_factory()()
    try:
        episode_id = seed_episode_with_transcript(db)
        run_all_steps(db, episode_id)

        ep = db.get(Episode, episode_id)
        assert ep and ep.full_transcript

        seg_n = db.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.episode_id == episode_id)
        )
        assert seg_n and seg_n > 0
        assert db.get(EpisodeFeatures, episode_id) is not None
        assert db.get(EpisodeTranslation, episode_id) is not None
    finally:
        db.close()
