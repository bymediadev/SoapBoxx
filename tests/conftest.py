"""Shared V1 test fixtures."""

from __future__ import annotations

import os

import pytest

V1_TABLES = (
    "podcasts",
    "episodes",
    "transcript_segments",
    "episode_features",
    "taxonomy_nodes",
    "podcast_taxonomy_map",
)


def v1_database_url() -> str:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("SOAPBOXX_V1_DATABASE_URL")
        or "postgresql+psycopg2://soapboxx:soapboxx@127.0.0.1:5432/soapboxx_v1"
    )


@pytest.fixture(scope="session")
def v1_db_url():
    url = v1_database_url()
    os.environ["DATABASE_URL"] = url
    return url


@pytest.fixture(scope="session")
def v1_db_ready(v1_db_url):
    pytest.importorskip("psycopg2")
    from sqlalchemy import text

    from backend.api.deps import get_engine

    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"Postgres not available: {exc}")

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", v1_db_url)
    command.upgrade(cfg, "head")
    return v1_db_url


@pytest.fixture
def v1_client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from backend.api.app import create_app

    return TestClient(create_app())
