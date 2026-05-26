#!/usr/bin/env python3
"""Re-ingest stored feeds and auto-dispatch new episodes for processing."""

from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.api.deps import get_session_factory
    from backend.services.rss_service import sync_saved_rss_feeds

    db = get_session_factory()()
    try:
        payload = sync_saved_rss_feeds(db, dispatch_processing=True).to_dict()
    finally:
        db.close()

    if payload["podcasts_checked"] == 0:
        print("No podcasts with rss_url. Add feeds via POST /ingest/rss first.")
        return 0

    print(json.dumps(payload, indent=2))
    return 0 if payload["failed_podcasts"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
