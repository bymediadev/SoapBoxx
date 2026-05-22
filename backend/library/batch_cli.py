"""CLI for weekly batch and queue management."""

from __future__ import annotations

import argparse
import json
import sys

from .batch import run_weekly_batch
from .catalog import get_library_tree
from .queue import enqueue_episode, list_pending_queue


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="SoapBoxx library weekly batch")
    p.add_argument("--run", action="store_true", help="Process pending queue")
    p.add_argument("--list-queue", action="store_true", help="List pending items")
    p.add_argument("--tree", action="store_true", help="Print library tree JSON")
    p.add_argument("--enqueue-paste", metavar="REF", help="Enqueue paste by ref id")
    p.add_argument("--enqueue-youtube", metavar="URL", help="Enqueue YouTube URL")
    p.add_argument("--show", default="", help="Show title")
    p.add_argument("--author", default="", help="Host / author")
    p.add_argument("--category", default="general", help="Category id")
    p.add_argument("--episode-title", default="", help="Episode title")
    p.add_argument("--limit", type=int, default=None, help="Max items per run")
    args = p.parse_args(argv)

    if args.enqueue_paste:
        r = enqueue_episode(
            source_type="paste",
            source_ref=args.enqueue_paste,
            category=args.category,
            show_title=args.show,
            author=args.author,
            episode_title=args.episode_title,
        )
        print(json.dumps(r, indent=2))
        return 0

    if args.enqueue_youtube:
        r = enqueue_episode(
            source_type="youtube",
            source_ref=args.enqueue_youtube,
            category=args.category,
            show_title=args.show,
            author=args.author,
            episode_title=args.episode_title,
        )
        print(json.dumps(r, indent=2))
        return 0

    if args.list_queue:
        print(json.dumps(list_pending_queue(), indent=2))
        return 0

    if args.tree:
        print(json.dumps(get_library_tree(), indent=2))
        return 0

    if args.run:
        summary = run_weekly_batch(limit=args.limit)
        print(json.dumps(summary, indent=2))
        return 0 if summary.get("failed", 0) == 0 else 1

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
