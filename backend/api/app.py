"""FastAPI application factory — V1."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.api.config import get_settings
from backend.api.routes import (
    episodes,
    health,
    ingest,
    insights,
    library,
    pipeline,
    podcasts,
    system,
    taxonomy,
)

logger = logging.getLogger(__name__)


def _find_ui_directory() -> Path | None:
    """Locate v1-library UI (bundled under backend/static for Railway root=backend)."""
    candidates = [
        Path(__file__).resolve().parents[1] / "static" / "v1-library",
        Path(__file__).resolve().parents[2] / "static" / "v1-library",
    ]
    for raw in (os.environ.get("SOAPBOXX_ROOT", "").strip(), str(Path.cwd())):
        if raw:
            candidates.append(Path(raw).resolve() / "static" / "v1-library")
    seen: set[Path] = set()
    for ui in candidates:
        ui = ui.resolve()
        if ui in seen:
            continue
        seen.add(ui)
        if ui.is_dir() and (ui / "index.html").is_file():
            return ui
    return None


def create_app() -> FastAPI:
    app = FastAPI(
        title="SoapBoxx V1 API",
        description="Podcast library: ingest → measure → translate",
        version="1.0.0",
    )
    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"https://.*\.lovable\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(podcasts.router)
    app.include_router(episodes.router)
    app.include_router(ingest.router)
    app.include_router(taxonomy.router)
    app.include_router(library.router)
    app.include_router(system.router)
    app.include_router(pipeline.router)
    app.include_router(insights.router)

    @app.get("/")
    def root() -> dict:
        return {
            "service": "SoapBoxx V1 API",
            "docs": "/docs",
            "health": "/health",
            "ui": "/ui/",
        }

    ui_dir = _find_ui_directory()
    if ui_dir is not None:
        index_html = ui_dir / "index.html"

        @app.get("/ui", include_in_schema=False)
        @app.get("/ui/", include_in_schema=False)
        def soapboxx_ui() -> FileResponse:
            return FileResponse(index_html, media_type="text/html")

        logger.info("Serving SoapBoxx UI from %s", ui_dir)
    else:
        logger.warning(
            "SoapBoxx UI not found (no static/v1-library/index.html). cwd=%s",
            Path.cwd(),
        )

    return app


app = create_app()
