"""Insight snapshots — weekly patterns (v1 aggregates)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.services.patterns_service import get_weekly_patterns

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/patterns/weekly")
def weekly_patterns(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Emerging structural patterns from episodes measured in the last 7 days."""
    return get_weekly_patterns(db)
