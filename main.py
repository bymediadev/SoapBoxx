"""
SoapBoxx V1 API entrypoint.

Local:  uvicorn main:app --reload
Deploy: Railpack / Railway use Procfile or railpack.json (uvicorn main:app)
"""

from __future__ import annotations

import os

from backend.api.app import app

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
