"""Health and readiness."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import check_database, check_redis

router = APIRouter(tags=["health"])


@router.get("/health/live")
def health_live() -> dict:
    """Liveness only — no DB/Redis (Railway edge + healthcheck)."""
    return {"status": "ok", "service": "soapboxx-v1-api", "check": "live"}


@router.get("/health")
def health() -> dict:
    db = check_database()
    rd = check_redis()
    # Postgres required for "ok"; Redis optional (reported in body either way).
    ok = db.get("status") == "connected"
    return {
        "status": "ok" if ok else "degraded",
        "service": "soapboxx-v1-api",
        "database": db,
        "redis": rd,
    }
