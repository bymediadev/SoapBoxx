"""Day 1 — health endpoint and schema migrations."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")
pytest.importorskip("alembic")
pytest.importorskip("psycopg2")


def _v1_database_url() -> str | None:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("SOAPBOXX_V1_DATABASE_URL")
        or "postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1"
    )


@pytest.fixture(scope="module")
def v1_db_ready():
    url = _v1_database_url()
    os.environ["DATABASE_URL"] = url

    from backend.api.deps import get_engine

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")
    return url


def test_health_endpoint_degraded_without_infra():
    """App loads; health reports status without requiring live DB in import."""
    from fastapi.testclient import TestClient
    from backend.api.app import create_app

    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "soapboxx-v1-api"
    assert "database" in body
    assert "redis" in body


def test_migrations_apply_cleanly(v1_db_ready):
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    from backend.api.deps import get_engine

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", v1_db_ready)
    command.upgrade(cfg, "head")

    insp = inspect(get_engine())
    tables = set(insp.get_table_names())
    required = {
        "podcasts",
        "episodes",
        "transcript_segments",
        "episode_features",
        "taxonomy_nodes",
        "podcast_taxonomy_map",
        "alembic_version",
    }
    missing = required - tables
    assert not missing, f"Missing tables: {missing}"


def test_health_ok_when_postgres_and_redis_up(v1_db_ready):
    pytest.importorskip("redis")
    from fastapi.testclient import TestClient
    from backend.api.app import create_app
    from backend.api.deps import check_redis

    rd = check_redis()
    if rd.get("status") != "connected":
        pytest.skip(f"Redis not available: {rd}")

    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "connected"
    assert body["redis"]["status"] == "connected"
