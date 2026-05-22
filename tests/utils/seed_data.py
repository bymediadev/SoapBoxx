"""Seed helpers for V1 tests (Day 2+)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from backend.models import Episode, Podcast


def create_podcast(
    db: Session,
    name: str,
    *,
    rss_url: Optional[str] = None,
) -> Podcast:
    row = Podcast(name=name, rss_url=rss_url)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def create_episode(
    db: Session,
    podcast_id: int,
    title: str,
    *,
    audio_url: Optional[str] = None,
) -> Episode:
    row = Episode(podcast_id=podcast_id, title=title, audio_url=audio_url)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
