"""Pipeline status — living system counts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import ProcessBatchResponse
from backend.services.episode_pipeline_service import process_queued_episodes
from backend.services.system_state_service import get_pipeline_status

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status")
def pipeline_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Episode counts by lifecycle state + active processing."""
    return get_pipeline_status(db)


@router.post("/process", response_model=ProcessBatchResponse)
def process_queued(
    limit: int = Query(1, ge=1, le=10, description="Max episodes to process"),
    db: Session = Depends(get_db),
) -> ProcessBatchResponse:
    """Run transcribe → features → translate on episodes without translation."""
    try:
        payload = process_queued_episodes(db, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return ProcessBatchResponse(**payload)
