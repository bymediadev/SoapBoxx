"""Episode CRUD + pipeline steps (Days 2–7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import (
    CoachingReportRead,
    EpisodeCreate,
    EpisodeFeaturesRead,
    EpisodeRead,
    ProcessEpisodeRequest,
    ProcessEpisodeResponse,
    TranscribeRequest,
    TranscribeResponse,
    TranslationRead,
)
from backend.services.coaching_report_service import coaching_report_for_episode
from backend.services.episode_pipeline_service import run_episode_pipeline
from backend.models import Episode, EpisodeFeatures, EpisodeTranslation, Podcast
from backend.services.feature_service import run_feature_extraction
from backend.services.pipeline_status import (
    STATUS_NEW,
    episode_state_payload,
    queue_episode,
)
from backend.services.transcription_service import transcribe_episode
from backend.services.translation_service import run_translation

router = APIRouter(prefix="/episodes", tags=["episodes"])


def _translation_read(db: Session, row: EpisodeTranslation) -> TranslationRead:
    features = db.get(EpisodeFeatures, row.episode_id)
    report_raw = coaching_report_for_episode(db, features)
    report = CoachingReportRead.model_validate(report_raw) if report_raw else None
    return TranslationRead(
        episode_id=row.episode_id,
        template_id=row.template_id,
        insight_text=row.insight_text,
        report=report,
    )


@router.post("", response_model=EpisodeRead, status_code=status.HTTP_201_CREATED)
def create_episode(body: EpisodeCreate, db: Session = Depends(get_db)) -> Episode:
    podcast = db.get(Podcast, body.podcast_id)
    if not podcast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Podcast {body.podcast_id} not found",
        )
    row = Episode(
        podcast_id=body.podcast_id,
        title=body.title.strip(),
        audio_url=body.audio_url,
        duration_seconds=body.duration_seconds,
        published_at=body.published_at,
        pipeline_status=STATUS_NEW,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{episode_id}/queue", status_code=status.HTTP_204_NO_CONTENT)
def queue_episode_for_pipeline(episode_id: int, db: Session = Depends(get_db)) -> None:
    try:
        queue_episode(db, episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{episode_id}/state")
def get_episode_state(episode_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        return episode_state_payload(db, episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{episode_id}", response_model=EpisodeRead)
def get_episode(episode_id: int, db: Session = Depends(get_db)) -> Episode:
    row = db.get(Episode, episode_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Episode {episode_id} not found",
        )
    return row


@router.post("/{episode_id}/process", response_model=ProcessEpisodeResponse)
def process_episode_endpoint(
    episode_id: int,
    body: ProcessEpisodeRequest | None = None,
    db: Session = Depends(get_db),
) -> ProcessEpisodeResponse:
    """Transcribe (if needed) → extract 7 metrics → template translation."""
    body = body or ProcessEpisodeRequest()
    try:
        result = run_episode_pipeline(
            db,
            episode_id,
            transcript=body.transcript,
            force_retranscribe=body.force_retranscribe,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        msg = str(exc).removeprefix("Error: ").strip()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {exc}",
        ) from exc
    return ProcessEpisodeResponse(**result.to_dict())


@router.post("/{episode_id}/transcribe", response_model=TranscribeResponse)
def transcribe_episode_endpoint(
    episode_id: int,
    body: TranscribeRequest | None = None,
    db: Session = Depends(get_db),
) -> TranscribeResponse:
    try:
        result = transcribe_episode(
            db,
            episode_id,
            transcript=body.transcript if body else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TranscribeResponse(
        episode_id=result.episode_id,
        transcript_length=result.transcript_length,
        segment_count=result.segment_count,
    )


@router.get("/{episode_id}/features", response_model=EpisodeFeaturesRead)
def get_features_endpoint(
    episode_id: int, db: Session = Depends(get_db)
) -> EpisodeFeaturesRead:
    feat = db.get(EpisodeFeatures, episode_id)
    if not feat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Features not found",
        )
    return feat


@router.post("/{episode_id}/features", response_model=EpisodeFeaturesRead)
def extract_features_endpoint(
    episode_id: int, db: Session = Depends(get_db)
) -> EpisodeFeaturesRead:
    try:
        run_feature_extraction(db, episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    feat = db.get(EpisodeFeatures, episode_id)
    if not feat:
        raise HTTPException(status_code=500, detail="Features not saved")
    return feat


@router.post("/{episode_id}/translate", response_model=TranslationRead)
def translate_episode_endpoint(
    episode_id: int, db: Session = Depends(get_db)
) -> TranslationRead:
    try:
        run_translation(db, episode_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    row = db.get(EpisodeTranslation, episode_id)
    if not row:
        raise HTTPException(status_code=500, detail="Translation not saved")
    return _translation_read(db, row)


@router.get("/{episode_id}/translation", response_model=TranslationRead)
def get_translation(episode_id: int, db: Session = Depends(get_db)) -> TranslationRead:
    row = db.get(EpisodeTranslation, episode_id)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Translation not found",
        )
    return _translation_read(db, row)
