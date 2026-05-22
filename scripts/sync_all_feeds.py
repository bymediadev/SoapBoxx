#!/usr/bin/env python3
"""Re-ingest every podcast that has an rss_url (cron / weekly sync)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.api.deps import get_session_factory
    from backend.models import Podcast
    from backend.services.rss_service import ingest_rss_feed

    db = get_session_factory()()
    try:
        rows = (
            db.query(Podcast)
            .filter(Podcast.rss_url.isnot(None), Podcast.rss_url != "")
            .order_by(Podcast.id)
            .all()
        )
        if not rows:
            print("No podcasts with rss_url. Add feeds via POST /ingest/rss first.")
            return 0

        total_created = 0
        total_skipped = 0
        for pod in rows:
            url = (pod.rss_url or "").strip()
            print(f"[{pod.id}] {pod.name}")
            try:
                result = ingest_rss_feed(db, url, podcast_id=int(pod.id))
                total_created += result.created
                total_skipped += result.skipped
                print(f"    created={result.created} skipped={result.skipped}")
            except Exception as exc:
                print(f"    ERROR: {exc}")
        print(f"Done. created={total_created} skipped={total_skipped}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
