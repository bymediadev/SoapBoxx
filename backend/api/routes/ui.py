"""Built-in library UI — always registered; path anchored to backend package."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

logger = logging.getLogger(__name__)

# Served path: backend/static/v1-library (deploy). Repo root static/ is kept in sync;
# resolve both so a missed copy does not ship a stale UI on Railway.
_BACKEND_STATIC = Path(__file__).resolve().parents[2] / "static" / "v1-library" / "index.html"
_REPO_STATIC = Path(__file__).resolve().parents[3] / "static" / "v1-library" / "index.html"


def _ui_index_path() -> Path:
    for candidate in (_BACKEND_STATIC, _REPO_STATIC):
        if candidate.is_file():
            return candidate
    return _BACKEND_STATIC

router = APIRouter(tags=["ui"])


@router.get("/ui", include_in_schema=False)
@router.get("/ui/", include_in_schema=False)
def soapboxx_ui() -> FileResponse:
    ui_index = _ui_index_path()
    if not ui_index.is_file():
        logger.error("UI index missing (cwd=%s)", Path.cwd())
        raise HTTPException(
            status_code=503,
            detail="UI bundle not deployed (missing static/v1-library/index.html)",
        )
    return FileResponse(
        ui_index,
        media_type="text/html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "X-SoapBoxx-Ui-Version": "coaching-v2",
        },
    )
