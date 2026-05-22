"""Podcast CRUD — Day 2 source layer."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.api.schemas import PodcastCreate, PodcastRead
from backend.models import Podcast

router = APIRouter(prefix="/podcasts", tags=["podcasts"])


@router.post("", response_model=PodcastRead, status_code=status.HTTP_201_CREATED)
def create_podcast(body: PodcastCreate, db: Session = Depends(get_db)) -> Podcast:
    row = Podcast(name=body.name.strip(), rss_url=body.rss_url)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=List[PodcastRead])
def list_podcasts(db: Session = Depends(get_db)) -> List[Podcast]:
    return db.query(Podcast).order_by(Podcast.id).all()
