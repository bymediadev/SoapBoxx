"""Helpers for V1 automated tests — no mocking of core DB logic."""

from __future__ import annotations

from typing import Iterable, List

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def api_is_running(client) -> bool:
    """FastAPI responds on /health."""
    r = client.get("/health")
    return r.status_code == 200 and r.json().get("service") == "soapboxx-v1-api"


def db_ping(engine: Engine) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def table_exists(engine: Engine, name: str) -> bool:
    return name in inspect(engine).get_table_names()


def tables_exist(engine: Engine, names: Iterable[str]) -> List[str]:
    present = set(inspect(engine).get_table_names())
    return [n for n in names if n not in present]
