"""Pipeline status — living system counts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.services.system_state_service import get_pipeline_status

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status")
def pipeline_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Episode counts by lifecycle state + active processing."""
    return get_pipeline_status(db)
