#!/usr/bin/env python3
"""Run transcribe → features → translate on episodes without translation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Process queued V1 episodes")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Max episodes to process (default 1, max 25)",
    )
    args = parser.parse_args()
    limit = max(1, min(args.limit, 25))

    from backend.api.deps import get_session_factory
    from backend.services.episode_pipeline_service import process_queued_episodes

    db = get_session_factory()()
    try:
        payload = process_queued_episodes(db, limit=limit)
    finally:
        db.close()

    print(json.dumps(payload, indent=2))
    return 0 if payload.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
