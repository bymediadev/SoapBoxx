#!/usr/bin/env python3
"""Start the Celery worker that consumes queued SoapBoxx pipeline jobs."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    python = sys.executable
    pool = (os.environ.get("SOAPBOXX_WORKER_POOL") or "").strip() or "solo"
    loglevel = (os.environ.get("SOAPBOXX_WORKER_LOGLEVEL") or "").strip() or "info"
    concurrency = (os.environ.get("SOAPBOXX_WORKER_CONCURRENCY") or "").strip()

    cmd = [
        python,
        "-m",
        "celery",
        "-A",
        "backend.workers.celery_app",
        "worker",
        "--loglevel",
        loglevel,
        "--pool",
        pool,
    ]
    if concurrency:
        cmd.extend(["--concurrency", concurrency])

    from backend.api.config import get_settings

    settings = get_settings()
    enable_beat = (os.environ.get("SOAPBOXX_ENABLE_BEAT") or "").strip().lower()
    use_beat = enable_beat not in ("0", "false", "no")
    if use_beat and (
        settings.pipeline_drain_minutes > 0 or settings.rss_sync_minutes > 0
    ):
        cmd.append("-B")

    print(
        (
            "Starting SoapBoxx worker "
            f"(pool={pool}, loglevel={loglevel}, "
            f"concurrency={concurrency or 'default'})"
        ),
        flush=True,
    )
    return subprocess.call(cmd, cwd=str(ROOT), env=os.environ.copy())


if __name__ == "__main__":
    raise SystemExit(main())
