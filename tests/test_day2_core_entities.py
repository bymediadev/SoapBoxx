"""
Day 2 — Podcast + episode CRUD.

PASS: create podcast, create episode, retrieve episode via API.
"""

from __future__ import annotations

import pytest

from tests.utils.db_reset import reset_v1_tables

pytestmark = pytest.mark.v1_day2


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_create_podcast(v1_client, v1_db_clean):
    r = v1_client.post(
        "/podcasts",
        json={"name": "Test Show", "rss_url": "https://example.com/feed.xml"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["id"] is not None
    assert data["name"] == "Test Show"
    assert data["rss_url"] == "https://example.com/feed.xml"


def test_create_episode(v1_client, v1_db_clean):
    pr = v1_client.post("/podcasts", json={"name": "Test Show"})
    podcast_id = pr.json()["id"]

    r = v1_client.post(
        "/episodes",
        json={
            "podcast_id": podcast_id,
            "title": "Ep 1",
            "audio_url": "https://example.com/ep1.mp3",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["id"] is not None
    assert data["podcast_id"] == podcast_id
    assert data["title"] == "Ep 1"


def test_get_episode(v1_client, v1_db_clean):
    pr = v1_client.post("/podcasts", json={"name": "Test Show"})
    podcast_id = pr.json()["id"]
    er = v1_client.post(
        "/episodes",
        json={"podcast_id": podcast_id, "title": "Ep 1"},
    )
    episode_id = er.json()["id"]

    r = v1_client.get(f"/episodes/{episode_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Ep 1"
    assert r.json()["id"] == episode_id


def test_list_podcasts(v1_client, v1_db_clean):
    v1_client.post("/podcasts", json={"name": "Show A"})
    v1_client.post("/podcasts", json={"name": "Show B"})
    r = v1_client.get("/podcasts")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_create_episode_unknown_podcast(v1_client, v1_db_clean):
    r = v1_client.post(
        "/episodes",
        json={"podcast_id": 99999, "title": "Orphan"},
    )
    assert r.status_code == 404
