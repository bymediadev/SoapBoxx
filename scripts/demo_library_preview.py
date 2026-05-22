#!/usr/bin/env python3
"""
Seed sample sources + measurements and print the insights library tree.

Run from repo root:
  python scripts/demo_library_preview.py
  python -m frontend.main_window   # then open Coach tab → Insights library
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SAMPLE_TRANSCRIPT = (
    "Host: Welcome back to the show. Today we're diving into startups.\n"
    "Guest: Thanks for having me. The biggest mistake founders make is speed without focus.\n"
    "Host: That's interesting. Can you give an example?\n"
    "Guest: Sure. We scaled hiring before product-market fit and burned eighteen months.\n"
    "Host: What would you do differently?\n"
    "Guest: Measure one metric weekly and kill projects that don't move it.\n"
) * 8


def _print_tree(tree: list) -> None:
    print("\n=== Insights library (what the Coach tab tree shows) ===\n")
    if not tree:
        print("  (empty — run with --seed to add sample shows)\n")
        return
    for cat in tree:
        print(f"[Category] {cat['category'].upper()}")
        for auth in cat.get("authors") or []:
            print(f"  +-- Author: {auth['author']}")
            for show in auth.get("shows") or []:
                n = show.get("episode_count", 0)
                print(f"      +-- Show: {show['title']}  ({n} episode(s))")
                for ep in show.get("episodes") or []:
                    hook = ep.get("hook_time")
                    q = ep.get("question_count")
                    extras = []
                    if hook is not None:
                        extras.append(f"hook {hook:.0f}s")
                    if q is not None:
                        extras.append(f"{q} questions")
                    suffix = f"  [{', '.join(extras)}]" if extras else ""
                    print(f"            - {ep.get('title', 'Episode')}{suffix}")
        print()


def main() -> int:
    from backend.library import (
        enqueue_episode,
        get_library_tree,
        list_pending_queue,
        run_weekly_batch,
    )
    from backend.library.db import LibraryDB
    from backend.intelligence_v1.config import default_db_path

    db_path = default_db_path()
    print(f"Database: {db_path}")

    samples = [
        {
            "category": "business",
            "show_title": "My First Million",
            "author": "Sam Parr",
            "episode_title": "Demo — Startup mistakes",
            "ref": "demo-mfm-ep1-" + SAMPLE_TRANSCRIPT[:40],
        },
        {
            "category": "interview",
            "show_title": "The Diary of a CEO",
            "author": "Steven Bartlett",
            "episode_title": "Demo — Founder interview",
            "ref": "demo-diary-ep1-" + SAMPLE_TRANSCRIPT[:40],
        },
        {
            "category": "business",
            "show_title": "Acquired",
            "author": "Ben Gilbert",
            "episode_title": "Demo — Company deep dive",
            "ref": "demo-acquired-ep1-" + SAMPLE_TRANSCRIPT[:40],
        },
    ]

    for s in samples:
        enqueue_episode(
            source_type="paste",
            source_ref=SAMPLE_TRANSCRIPT + s["ref"],
            category=s["category"],
            show_title=s["show_title"],
            author=s["author"],
            episode_title=s["episode_title"],
        )

    pending = list_pending_queue()
    print(f"Queued: {len(pending)} episode(s)")
    if pending:
        summary = run_weekly_batch()
        print(
            f"Batch {summary.get('label')}: "
            f"{summary.get('processed')} ok, {summary.get('failed')} failed"
        )

    tree = get_library_tree()
    _print_tree(tree)

    print("=== Sample measurements (JSON, one episode) ===\n")
    db = LibraryDB()
    db.init_schema()
    if tree:
        ep_id = tree[0]["authors"][0]["shows"][0]["episodes"][0]["id"]
        bundle = db.get_episode_bundle(ep_id)
        if bundle and bundle.get("metrics"):
            m = bundle["metrics"]
            print(
                json.dumps(
                    {
                        "hook_time_seconds": m.get("hook_time"),
                        "guest_talk_pct": m.get("guest_talk_pct"),
                        "question_count": m.get("question_count"),
                        "followup_count": m.get("followup_count"),
                    },
                    indent=2,
                )
            )

    print("\n--- Open the app ---")
    print("  python -m frontend.main_window")
    print("  Coach tab: scroll to 'Insights library - weekly batch'\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
