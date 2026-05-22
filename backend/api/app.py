"""FastAPI application factory — V1."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
        }

    return app


app = create_app()
