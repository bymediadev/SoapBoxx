"""
SoapBoxx V1 API entrypoint.

Local:  uvicorn main:app --reload
Deploy: Railpack / Railway use Procfile or railpack.json (uvicorn main:app)
"""

from __future__ import annotations

import os

# Load repo-root .env into the process (GEMINI_API_KEY, ASSEMBLYAI_API_KEY, …).
# pydantic-settings reads .env only for its own fields; services use os.getenv.
# No-op on Railway (no .env file); real env vars always win (override=False).
try:
    from dotenv import load_dotenv

    load_dotenv(override=False)
except ImportError:
    pass

from backend.api.app import app

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
