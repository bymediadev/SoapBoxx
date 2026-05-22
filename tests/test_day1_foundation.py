"""
Day 1 — Foundation (PASS/FAIL).

PASS: API running, DB connected, V1 schema created.
See SOAPBOXX_V1_7DAY_EXECUTION.md Day 1.
"""

from __future__ import annotations

import pytest

from tests.conftest import V1_TABLES
from tests.utils.v1_helpers import api_is_running, db_ping, tables_exist

pytestmark = pytest.mark.v1_day1


def test_api_starts(v1_client):
    assert api_is_running(v1_client)


def test_db_connection(v1_db_ready):
    from backend.api.deps import get_engine

    assert db_ping(get_engine()) is True


def test_tables_exist(v1_db_ready):
    from backend.api.deps import get_engine

    missing = tables_exist(get_engine(), V1_TABLES)
    assert not missing, f"Missing tables: {missing}"


def test_health_full_stack_when_infra_up(v1_db_ready, v1_client):
    """Optional: status ok when Postgres + Redis available."""
    pytest.importorskip("redis")
    from backend.api.deps import check_redis

    if check_redis().get("status") != "connected":
        pytest.skip("Redis not running")

    r = v1_client.get("/health")
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "connected"
    assert body["redis"]["status"] == "connected"
