"""FastAPI dependencies — DB session and Redis."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, Optional

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings

_engine = None
_SessionLocal: Optional[sessionmaker[Session]] = None
_redis_client: Optional[redis.Redis] = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
        )
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
        )
    return _redis_client


def check_database() -> dict[str, Any]:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def check_redis() -> dict[str, Any]:
    try:
        client = get_redis()
        client.ping()
        return {"status": "connected"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
