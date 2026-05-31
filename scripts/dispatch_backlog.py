#!/usr/bin/env python3
"""Dispatch or process pending episodes (Planet Money backlog)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Drain pending episode pipeline")
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max episodes (default 100)",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Process on this machine (no Celery); use --limit 3 for long STT",
    )
    args = parser.parse_args()

    from backend.api.deps import get_session_factory
    from backend.services.episode_pipeline_service import drain_pending_pipeline

    db = get_session_factory()()
    try:
        out = drain_pending_pipeline(
            db,
            limit=max(1, min(args.limit, 400)),
            trigger="cli_dispatch_backlog",
            prefer_celery=not args.sync,
        )
        if args.sync or out.get("dispatched", 0) == 0:
            if out.get("mode") != "sync" and out.get("pending", 0) > 0:
                out = drain_pending_pipeline(
                    db,
                    limit=max(1, min(args.limit, 10)),
                    trigger="cli_dispatch_backlog_sync",
                    prefer_celery=False,
                )
    finally:
        db.close()

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
