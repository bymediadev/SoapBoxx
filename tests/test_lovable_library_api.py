"""Library endpoints for Lovable web client."""

from __future__ import annotations

import pytest

from backend.services.rss_service import ingest_rss_xml
from tests.utils.db_reset import reset_v1_tables

pytestmark = pytest.mark.v1_day6


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_library_stats_and_episodes(v1_client, v1_db_clean):
    from backend.api.deps import get_session_factory
    from pathlib import Path

    xml = (Path(__file__).parent / "fixtures" / "sample_rss.xml").read_text(encoding="utf-8")
    db = get_session_factory()()
    try:
        ingest_rss_xml(db, xml, rss_url="https://example.com/lovable-feed")
    finally:
        db.close()

    stats = v1_client.get("/library/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["episodes_total"] == 2
    assert body["shows_total"] == 1
    assert body["queued_count"] == 2
    assert body["processing_count"] == 0

    eps = v1_client.get("/library/episodes?limit=5")
    assert eps.status_code == 200
    page = eps.json()
    assert page["total"] == 2
    items = page["episodes"]
    assert len(items) == 2
    assert all(i["status"] == "queued" for i in items)

    ready_page = v1_client.get("/library/episodes?status=ready")
    assert ready_page.json()["total"] == 0

    activity = v1_client.get("/system/activity?limit=10")
    assert activity.status_code == 200
    assert any(e["event_type"] == "ingest.completed" for e in activity.json())

    pipe = v1_client.get("/pipeline/status")
    assert pipe.status_code == 200
    assert pipe.json()["by_status"]["queued"] >= 2

    home = v1_client.get("/library/home?episodes_limit=5&activity_limit=10")
    assert home.status_code == 200
    bundle = home.json()
    assert bundle["stats"]["episodes_total"] == 2
    assert len(bundle["episodes"]) == 2
    assert bundle["pipeline"]["by_status"]["queued"] >= 2
    assert any(e["event_type"] == "ingest.completed" for e in bundle["activity"])
