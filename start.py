"""
Local / fallback start entry (migrations + uvicorn).

Railway/Railpack: no preDeploy; start `python start.py` (alembic + uvicorn — see railway.toml).
"""

from __future__ import annotations

import os
import subprocess
import sys
import traceback
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASGI_TARGET = os.environ.get("ASGI_APP", "main:app").strip() or "main:app"


def _on_railway() -> bool:
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_SERVICE_NAME")
        or os.environ.get("RAILWAY_PROJECT_ID")
    )


def _log_database_url() -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("DATABASE_URL: (not set)", flush=True)
        return
    try:
        p = urlparse(url.replace("postgresql+psycopg2://", "postgresql://", 1))
        host = p.hostname or "?"
        print(f"DATABASE_URL: set (host={host}, db={p.path or '/?'})", flush=True)
    except Exception:
        print("DATABASE_URL: set (could not parse for log)", flush=True)


def _guard_database_url() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if _on_railway() and url and ("127.0.0.1" in url or "localhost" in url):
        print(
            "FATAL: DATABASE_URL points to localhost on Railway.\n"
            "  Fix: API service → Variables → reference DATABASE_URL from Postgres.\n"
            "  Do not copy .env.v1.example (127.0.0.1) into Railway.",
            flush=True,
        )
        sys.exit(1)


def _wait_for_database() -> int:
    if os.environ.get("BOOT_SKIP_DB_WAIT", "").strip().lower() in ("1", "true", "yes"):
        print("BOOT_SKIP_DB_WAIT=1 — skipping wait_for_db", flush=True)
        return 0
    if not os.environ.get("DATABASE_URL"):
        print(
            "WARNING: DATABASE_URL not set — skip DB wait; attach Postgres on Railway.",
            flush=True,
        )
        return 1
    env = os.environ.copy()
    if _on_railway() and "DB_WAIT_ATTEMPTS" not in env:
        env["DB_WAIT_ATTEMPTS"] = "12"
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "wait_for_db.py")],
        cwd=ROOT,
        check=False,
        env=env,
    ).returncode


def _run_migrations() -> int:
    if not os.environ.get("DATABASE_URL"):
        print("Skipping alembic (no DATABASE_URL).", flush=True)
        return 1
    print("Running alembic upgrade head...", flush=True)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
        cwd=ROOT,
    )
    if result.returncode != 0:
        print(
            f"alembic exited {result.returncode} — continuing boot "
            "(check DATABASE_URL / Postgres).",
            flush=True,
        )
    return result.returncode


def _verify_asgi_import() -> None:
    print(f"cwd={os.getcwd()}", flush=True)
    print(f"PORT={os.environ.get('PORT', '8000')}", flush=True)
    print(f"ASGI target={ASGI_TARGET}", flush=True)
    module_path, _, attr = ASGI_TARGET.partition(":")
    if not module_path or not attr:
        raise RuntimeError(f"Invalid ASGI_APP={ASGI_TARGET!r} (expected module:app)")

    import importlib

    mod = importlib.import_module(module_path)
    application = getattr(mod, attr, None)
    if application is None:
        raise AttributeError(f"{ASGI_TARGET} — missing attribute {attr!r}")
    print(f"Import OK: {ASGI_TARGET} ({type(application).__name__})", flush=True)


def main() -> None:
    print("=== SoapBoxx boot ===", flush=True)
    _log_database_url()
    _guard_database_url()
    wait_rc = _wait_for_database()
    if wait_rc != 0 and os.environ.get("DATABASE_URL"):
        print(
            "WARNING: database not reachable — migrations may fail; "
            "check Postgres plugin + DATABASE_URL reference.",
            flush=True,
        )
    _run_migrations()
    _verify_asgi_import()

    import uvicorn

    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting uvicorn {ASGI_TARGET} on 0.0.0.0:{port}", flush=True)
    uvicorn.run(ASGI_TARGET, host="0.0.0.0", port=port)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
