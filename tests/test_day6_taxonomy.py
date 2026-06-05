"""Day 6 — taxonomy + library tree."""

from __future__ import annotations

import pytest

from backend.services.taxonomy_service import create_taxonomy_node, get_library_tree
from tests.utils.db_reset import reset_v1_tables

pytestmark = pytest.mark.v1_day6


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_create_taxonomy(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        node = create_taxonomy_node(db, "Business", "domain")
        assert node.id is not None
    finally:
        db.close()


def test_taxonomy_tree(v1_db_clean):
    from backend.api.deps import get_session_factory

    db = get_session_factory()()
    try:
        domain = create_taxonomy_node(db, "Business", "domain")
        child = create_taxonomy_node(
            db, "Startups", "subcategory", parent_id=int(domain.id)
        )
        assert child.parent_id == int(domain.id)
    finally:
        db.close()


def test_synthetic_tree_when_taxonomy_empty(v1_db_clean):
    """Catalog categories without running seed_taxonomy.py."""
    from backend.api.deps import get_session_factory
    from backend.models import Podcast

    db = get_session_factory()()
    try:
        db.add(Podcast(name="Planet Money", rss_url="https://example.com/pm.xml"))
        db.add(Podcast(name="Why Mastermind", rss_url="https://example.com/wm.xml"))
        db.commit()
        tree = get_library_tree(db)
        assert tree
        domain_names = [n["name"] for n in tree]
        assert "Business" in domain_names or "Library" in domain_names
        all_pods = []
        def walk(nodes):
            for n in nodes:
                all_pods.extend(n.get("podcasts") or [])
                walk(n.get("children") or [])
        walk(tree)
        names = {p["name"] for p in all_pods}
        assert "Planet Money" in names
        assert "Why Mastermind" in names
    finally:
        db.close()


def test_podcast_taxonomy_map(v1_client, v1_db_clean):
    pr = v1_client.post("/podcasts", json={"name": "Mapped Show"})
    pid = pr.json()["id"]
    dom = v1_client.post(
        "/taxonomy/nodes",
        json={"name": "Business", "node_type": "domain"},
    )
    v1_client.post(
        "/taxonomy/map",
        json={"podcast_id": pid, "taxonomy_node_id": dom.json()["id"]},
    )
    tree = v1_client.get("/library/tree")
    assert tree.status_code == 200
    data = tree.json()
    assert any(n.get("name") == "Business" for n in data)
