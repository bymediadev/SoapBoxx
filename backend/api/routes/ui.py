"""Built-in library UI — always registered; path anchored to backend package."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# backend/api/routes/ui.py -> backend/static/v1-library/index.html
_UI_INDEX = Path(__file__).resolve().parents[2] / "static" / "v1-library" / "index.html"

router = APIRouter(tags=["ui"])


@router.get("/ui", include_in_schema=False)
@router.get("/ui/", include_in_schema=False)
def soapboxx_ui() -> FileResponse:
    if not _UI_INDEX.is_file():
        logger.error("UI index missing at %s (cwd=%s)", _UI_INDEX, Path.cwd())
        raise HTTPException(
            status_code=503,
            detail=f"UI bundle not deployed (missing {_UI_INDEX.name} at backend/static/v1-library)",
        )
    return FileResponse(_UI_INDEX, media_type="text/html")
