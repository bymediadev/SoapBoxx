#!/usr/bin/env python3
"""Ingest RSS URLs from file and auto-dispatch new episodes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEED_FILE = ROOT / "data" / "seed_feeds.txt"


def main() -> int:
    from backend.api.deps import get_session_factory
    from backend.services.rss_service import (
        dispatch_processing_for_episodes,
        ingest_rss_feed,
    )

    if not SEED_FILE.is_file():
        print(f"Missing {SEED_FILE}")
        return 1

    urls = []
    for line in SEED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)

    if not urls:
        print(f"No URLs in {SEED_FILE}")
        return 0

    db = get_session_factory()()
    try:
        for url in urls:
            print(f"Ingest {url}")
            try:
                r = ingest_rss_feed(db, url.strip())
                dispatched_ids = dispatch_processing_for_episodes(
                    db,
                    r.created_episode_ids,
                    trigger="seed_feeds",
                )
                print(
                    "  "
                    f"podcast_id={r.podcast_id} created={r.created} "
                    f"skipped={r.skipped} dispatched={len(dispatched_ids)}"
                )
            except Exception as exc:
                db.rollback()
                print(f"  ERROR: {exc}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
