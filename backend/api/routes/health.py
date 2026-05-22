"""Health and readiness."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import check_database, check_redis

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db = check_database()
    rd = check_redis()
    ok = db.get("status") == "connected" and rd.get("status") == "connected"
    return {
        "status": "ok" if ok else "degraded",
        "service": "soapboxx-v1-api",
        "database": db,
        "redis": rd,
    }
