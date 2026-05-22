"""CLI to pull stored episode or library JSON."""

from __future__ import annotations

import argparse
import json
import sys

from .pull import export_library_snapshot, pull_episode, pull_podcast


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pull SoapBoxx stored data")
    p.add_argument("--episode", type=int, metavar="ID", help="Pull one episode bundle")
    p.add_argument("--podcast", type=int, metavar="ID", help="Pull one show + episodes")
    p.add_argument("--library", action="store_true", help="Export library snapshot")
    args = p.parse_args(argv)

    if args.episode:
        data = pull_episode(args.episode)
        if not data:
            print(f"No episode {args.episode}", file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, default=str))
        return 0
    if args.podcast:
        data = pull_podcast(args.podcast)
        if not data:
            print(f"No podcast {args.podcast}", file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, default=str))
        return 0
    if args.library:
        print(json.dumps(export_library_snapshot(), indent=2, default=str))
        return 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
