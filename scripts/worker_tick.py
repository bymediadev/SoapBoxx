#!/usr/bin/env python3
"""
Process one batch of queued episodes (transcribe → features → translate).

Railway: run on a cron service every N minutes (see railway.worker.toml).
Uses GROQ_API_KEY or pasted transcript fallback when SOAPBOXX_DEMO_TRANSCRIPT=1.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    limit = int(os.environ.get("SOAPBOXX_WORKER_BATCH", "1"))
    use_demo = os.environ.get("SOAPBOXX_DEMO_TRANSCRIPT", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    from backend.api.deps import get_session_factory
    from backend.models import Episode, EpisodeTranslation
    from backend.services.episode_pipeline_service import (
        process_queued_episodes,
        run_episode_pipeline,
    )

    demo_path = ROOT / "tests" / "fixtures" / "sample_transcript.txt"
    demo_text = demo_path.read_text(encoding="utf-8").strip() if demo_path.is_file() else ""

    db = get_session_factory()()
    try:
        if use_demo and demo_text:
            pending = (
                db.query(Episode)
                .outerjoin(
                    EpisodeTranslation, EpisodeTranslation.episode_id == Episode.id
                )
                .filter(EpisodeTranslation.episode_id.is_(None))
                .order_by(Episode.id.asc())
                .limit(max(1, min(limit, 10)))
                .all()
            )
            results = []
            for ep in pending:
                try:
                    out = run_episode_pipeline(
                        db, int(ep.id), transcript=demo_text
                    )
                    results.append({"episode_id": int(ep.id), "ok": True, **out.to_dict()})
                except Exception as exc:
                    results.append(
                        {
                            "episode_id": int(ep.id),
                            "ok": False,
                            "error": str(exc),
                            "title": ep.title,
                        }
                    )
            payload = {
                "mode": "demo_transcript",
                "requested": limit,
                "attempted": len(pending),
                "succeeded": sum(1 for r in results if r.get("ok")),
                "failed": sum(1 for r in results if not r.get("ok")),
                "results": results,
            }
        else:
            payload = process_queued_episodes(db, limit=limit)
            payload["mode"] = "audio_stt"
    finally:
        db.close()

    print(json.dumps(payload, indent=2))
    return 0 if payload.get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
