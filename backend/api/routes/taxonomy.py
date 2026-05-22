"""Taxonomy + library — Day 6."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import (
    PodcastTaxonomyMapRequest,
    TaxonomyNodeCreate,
    TaxonomyNodeRead,
)
from backend.services.taxonomy_service import (
    create_taxonomy_node,
    map_podcast_to_taxonomy,
)

router = APIRouter(tags=["taxonomy"])


@router.post(
    "/taxonomy/nodes",
    response_model=TaxonomyNodeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_node(body: TaxonomyNodeCreate, db: Session = Depends(get_db)) -> TaxonomyNodeRead:
    try:
        row = create_taxonomy_node(
            db, body.name, body.node_type, parent_id=body.parent_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return row


@router.post("/taxonomy/map", status_code=status.HTTP_204_NO_CONTENT)
def map_podcast(body: PodcastTaxonomyMapRequest, db: Session = Depends(get_db)) -> None:
    try:
        map_podcast_to_taxonomy(db, body.podcast_id, body.taxonomy_node_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
