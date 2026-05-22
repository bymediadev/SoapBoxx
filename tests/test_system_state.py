"""System state layer — lifecycle + activity + patterns."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.services.rss_service import ingest_rss_xml
from backend.services.transcription_service import transcribe_episode
from tests.utils.db_reset import reset_v1_tables
from tests.utils.pipeline import FIXTURE_TRANSCRIPT

pytestmark = pytest.mark.v1_day6


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_episode_lifecycle_api(v1_client, v1_db_clean):
    from backend.api.deps import get_session_factory

    xml = (Path(__file__).parent / "fixtures" / "sample_rss.xml").read_text(encoding="utf-8")
    db = get_session_factory()()
    try:
        ing = ingest_rss_xml(db, xml, rss_url="https://example.com/lifecycle-feed")
        eid = ing.episode_ids[0]
        transcribe_episode(db, eid, transcript=FIXTURE_TRANSCRIPT.read_text(encoding="utf-8"))
    finally:
        db.close()

    state = v1_client.get(f"/episodes/{eid}/state")
    assert state.status_code == 200
    body = state.json()
    assert body["steps"]["transcribed"] is True
    assert body["status"] == "queued"
    assert body["next_action"] == "features"

    patterns = v1_client.get("/insights/patterns/weekly")
    assert patterns.status_code == 200
