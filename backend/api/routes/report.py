"""Layer 4 report views — producer and actions."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import EpisodeActionsReportRead, EpisodeProducerReportRead
from backend.services.report_views_service import (
    actions_report_for_episode,
    producer_report_for_episode,
)

router = APIRouter(prefix="/episodes", tags=["reports"])


@router.get("/{episode_id}/report/producer", response_model=EpisodeProducerReportRead)
def get_producer_report(
    episode_id: int, db: Session = Depends(get_db)
) -> EpisodeProducerReportRead:
    """Curated producer view: measurements + structure + patterns (no schema/cohort noise)."""
    payload = producer_report_for_episode(db, episode_id)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not measured yet (features + translation required)",
        )
    return EpisodeProducerReportRead.model_validate(payload)


@router.get("/{episode_id}/report/actions", response_model=EpisodeActionsReportRead)
def get_actions_report(
    episode_id: int, db: Session = Depends(get_db)
) -> EpisodeActionsReportRead:
    """Next-episode actions derived from editorial coach (review_these, edit flags)."""
    payload = actions_report_for_episode(db, episode_id)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Episode not measured yet",
        )
    return EpisodeActionsReportRead.model_validate(payload)
