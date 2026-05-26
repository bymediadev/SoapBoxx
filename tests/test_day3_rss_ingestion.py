"""
Day 3 — RSS ingestion (source layer).

PASS: parse RSS, ingest creates episodes, re-ingest has no duplicates,
descriptions + raw_rss_json stored.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.models import Episode, Podcast
from backend.services.rss_service import ingest_rss_xml, parse_rss
from tests.utils.db_reset import reset_v1_tables

pytestmark = pytest.mark.v1_day3

FIXTURE_RSS = Path(__file__).parent / "fixtures" / "sample_rss.xml"
RSS_URL = "https://example.com/fixture-feed.xml"


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_rss_parse():
    xml = FIXTURE_RSS.read_text(encoding="utf-8")
    title, link, items = parse_rss(xml)
    assert title == "SoapBoxx Test Show"
    assert link == "https://example.com/podcast"
    assert len(items) == 2
    assert items[0].guid == "soapboxx-fixture-ep1"
    assert items[0].audio_url == "https://example.com/ep1.mp3"
    assert items[0].description == "First fixture episode description."


def test_rss_ingest_creates_episodes(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        xml = FIXTURE_RSS.read_text(encoding="utf-8")
        result = ingest_rss_xml(db, xml, rss_url=RSS_URL)
        assert result.created == 2
        assert result.skipped == 0
        assert len(result.episode_ids) == 2
        assert result.created_episode_ids == result.episode_ids

        count = db.scalar(select(func.count()).select_from(Episode))
        assert count == 2

        podcast = db.get(Podcast, result.podcast_id)
        assert podcast is not None
        assert podcast.description == "Fixture feed for Day 3 RSS tests"

        ep = db.get(Episode, result.episode_ids[0])
        assert ep is not None
        assert ep.description == "First fixture episode description."
        assert ep.raw_rss_json is not None
        raw = json.loads(ep.raw_rss_json)
        assert raw.get("title") == "Episode 1 — Fixture"
    finally:
        db.close()


def test_no_duplicate_ingestion(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        xml = FIXTURE_RSS.read_text(encoding="utf-8")
        first = ingest_rss_xml(db, xml, rss_url=RSS_URL)
        second = ingest_rss_xml(db, xml, rss_url=RSS_URL)

        assert first.created == 2
        assert second.created == 0
        assert second.skipped == 2
        assert first.created_episode_ids == first.episode_ids
        assert second.created_episode_ids == []

        count = db.scalar(select(func.count()).select_from(Episode))
        assert count == 2
    finally:
        db.close()


def test_duplicate_fallback_title_and_date(v1_db_clean):
    """Idempotent when guid missing but title + published_at match."""
    from backend.api.deps import get_session_factory

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>No Guid Show</title>
<item>
  <title>Same Episode</title>
  <pubDate>Mon, 15 Jan 2024 12:00:00 GMT</pubDate>
  <enclosure url="https://example.com/a.mp3" type="audio/mpeg"/>
</item>
</channel></rss>"""
    db = get_session_factory()()
    try:
        r1 = ingest_rss_xml(db, xml, rss_url="https://example.com/no-guid.xml")
        r2 = ingest_rss_xml(db, xml, rss_url="https://example.com/no-guid.xml")
        assert r1.created == 1
        assert r2.created == 0
        assert r2.skipped == 1
    finally:
        db.close()


def test_ingest_rss_api(v1_client, v1_db_clean, monkeypatch):
    xml = FIXTURE_RSS.read_text(encoding="utf-8")
    dispatched_calls = []

    monkeypatch.setattr(
        "backend.api.routes.ingest.ingest_rss_feed",
        lambda db, url, podcast_id=None: ingest_rss_xml(
            db, xml, rss_url=url, podcast_id=podcast_id
        ),
    )
    monkeypatch.setattr(
        "backend.api.routes.ingest.dispatch_processing_for_episodes",
        lambda db, episode_ids, trigger: dispatched_calls.append(
            {"episode_ids": list(episode_ids), "trigger": trigger}
        )
        or list(episode_ids),
    )

    r = v1_client.post("/ingest/rss", json={"rss_url": RSS_URL})
    assert r.status_code == 201
    body = r.json()
    assert body["episodes_created"] == 2
    assert body["episodes_dispatched"] == 2
    assert body["podcast_id"] > 0
    assert dispatched_calls == [
        {"episode_ids": body["episode_ids"], "trigger": "rss_ingest"}
    ]

    r2 = v1_client.post("/ingest/rss", json={"rss_url": RSS_URL})
    assert r2.json()["episodes_created"] == 0
    assert r2.json()["episodes_skipped"] == 2
    assert r2.json()["episodes_dispatched"] == 0
    assert len(dispatched_calls) == 1
