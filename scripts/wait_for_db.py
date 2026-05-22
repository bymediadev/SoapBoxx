"""Wait until DATABASE_URL accepts connections (local Docker or Railway Postgres)."""

from __future__ import annotations

import os
import sys
import time


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("wait_for_db: DATABASE_URL not set", file=sys.stderr)
        return 1

    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_SERVICE_NAME"):
        if "127.0.0.1" in url or "localhost" in url:
            print(
                "FATAL: DATABASE_URL uses localhost inside Railway. "
                "Remove manual DATABASE_URL and reference Postgres plugin variable.",
                file=sys.stderr,
            )
            return 1

    max_attempts = int(os.environ.get("DB_WAIT_ATTEMPTS", "30"))
    delay = float(os.environ.get("DB_WAIT_DELAY", "2"))

    from sqlalchemy import create_engine, text

    from backend.api.config import _normalize_database_url

    engine = create_engine(_normalize_database_url(url), pool_pre_ping=True)
    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"wait_for_db: ready (attempt {attempt})", flush=True)
            return 0
        except Exception as exc:
            last_err = exc
            print(f"wait_for_db: attempt {attempt}/{max_attempts}: {exc}", flush=True)
            time.sleep(delay)

    print(f"wait_for_db: gave up after {max_attempts} attempts: {last_err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
