"""
Railpack/Railway start entry (checked before main.py in some Railpack versions).

Runs migrations then serves the V1 API.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
