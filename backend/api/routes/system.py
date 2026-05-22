"""System visibility — activity feed + pipeline motion."""

from __future__ import annotations

from typing import Any, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.services.system_state_service import get_pipeline_status, get_system_activity

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/activity")
def system_activity(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> List[Any]:
    """Recent ingests, pipeline steps, and completions."""
    return get_system_activity(db, limit=limit)


@router.get("/activity_feed")
def system_activity_feed(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> List[Any]:
    """Alias for Lovable activity panels."""
    return get_system_activity(db, limit=limit)
