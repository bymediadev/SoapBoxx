"""Library routes for web clients (Lovable)."""

from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.services.library_service import get_library_stats, list_episodes
from backend.services.taxonomy_service import get_library_tree

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/stats")
def library_stats(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Dashboard counts for Library home (episodes, shows, measured %, queued)."""
    return get_library_stats(db)


@router.get("/tree")
def library_tree(db: Session = Depends(get_db)) -> List[Any]:
    """Alias of taxonomy tree for Lovable (`GET /library/tree`)."""
    return get_library_tree(db)


@router.get("/episodes")
def library_episodes(
    db: Session = Depends(get_db),
    podcast_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> List[Any]:
    """Recent episodes with pipeline status (queued | ready | measured)."""
    return list_episodes(db, podcast_id=podcast_id, limit=limit, offset=offset)
