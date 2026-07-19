"""
Local / cloud start entry (migrations + uvicorn).

Cloud (Railway/Render): start `python start.py` (wait → alembic → uvicorn).
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


def _on_cloud_host() -> bool:
    """True on Railway or Render (or if PLATFORM=cloud is set)."""
    return bool(
        os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("RAILWAY_SERVICE_NAME")
        or os.environ.get("RAILWAY_PROJECT_ID")
        or os.environ.get("RENDER")
        or os.environ.get("RENDER_SERVICE_ID")
        or os.environ.get("PLATFORM", "").strip().lower() == "cloud"
    )


def _redis_configured_for_worker() -> bool:
    url = (os.environ.get("REDIS_URL") or "").strip()
    if not url:
        return False
    return "127.0.0.1" not in url and "localhost" not in url


def _apply_cloud_pipeline_defaults() -> None:
    """Only auto-dispatch backlog on boot when a real Redis URL exists (worker queue)."""
    if not _on_cloud_host() or "PIPELINE_BOOT_DISPATCH_LIMIT" in os.environ:
        return
    if _redis_configured_for_worker():
        os.environ["PIPELINE_BOOT_DISPATCH_LIMIT"] = "50"
    else:
        os.environ["PIPELINE_BOOT_DISPATCH_LIMIT"] = "0"


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
    if _on_cloud_host() and url and ("127.0.0.1" in url or "localhost" in url):
        print(
            "FATAL: DATABASE_URL points to localhost on a cloud host.\n"
            "  Fix: Web service → Environment → link DATABASE_URL from Render Postgres\n"
            "  (or Railway Postgres). Do not paste .env local URLs (127.0.0.1).",
            flush=True,
        )
        sys.exit(1)


def _wait_for_database() -> int:
    if os.environ.get("BOOT_SKIP_DB_WAIT", "").strip().lower() in ("1", "true", "yes"):
        print("BOOT_SKIP_DB_WAIT=1 — skipping wait_for_db", flush=True)
        return 0
    if not os.environ.get("DATABASE_URL"):
        print(
            "WARNING: DATABASE_URL not set — skip DB wait; attach Postgres on the host.",
            flush=True,
        )
        return 1
    env = os.environ.copy()
    root = str(ROOT)
    env["PYTHONPATH"] = (
        root if not env.get("PYTHONPATH") else f"{root}{os.pathsep}{env['PYTHONPATH']}"
    )
    if _on_cloud_host() and "DB_WAIT_ATTEMPTS" not in env:
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


def _verify_pipeline_deps() -> None:
    """Fail at boot if core HTTP deps are missing.

    On Render free (512MB), skip importing openai/pydub/numpy at boot — they are
    large and only needed when processing audio later.
    """
    import importlib

    required = ("requests",)
    if not (
        os.environ.get("RENDER")
        or os.environ.get("RENDER_SERVICE_ID")
        or os.environ.get("SOAPBOXX_LIGHT_BOOT", "").strip().lower() in ("1", "true", "yes")
    ):
        required = ("requests", "openai", "pydub", "numpy")

    missing: list[str] = []
    for name in required:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        raise RuntimeError(
            f"Missing Python packages: {', '.join(missing)} — "
            "add them to requirements.txt and redeploy."
        )
    print(f"Pipeline deps OK ({', '.join(required)})", flush=True)


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
    _apply_cloud_pipeline_defaults()
    _log_database_url()
    _guard_database_url()
    wait_rc = _wait_for_database()
    if wait_rc != 0 and os.environ.get("DATABASE_URL"):
        print(
            "WARNING: database not reachable — skipping alembic; "
            "check Postgres + DATABASE_URL on the host. "
            "If you saw ECIRCUITBREAKER / password auth failed: wait ~15m, "
            "fix credentials, redeploy once.",
            flush=True,
        )
    else:
        _run_migrations()
    _verify_pipeline_deps()
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
