#!/usr/bin/env python3
"""CLI: run SoapBoxx Phase 1 intelligence pipeline on audio or transcript."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description="SoapBoxx intelligence_v1 pipeline")
    parser.add_argument("input", help="Audio file path or --transcript text file")
    parser.add_argument("--category", default="general", help="Episode category for benchmarks")
    parser.add_argument("--title", default="", help="Episode title")
    parser.add_argument(
        "--transcript",
        action="store_true",
        help="Input is a .txt transcript file (skip STT)",
    )
    args = parser.parse_args()

    from intelligence_v1.pipeline import process_episode, process_transcript_only

    path = Path(args.input)
    if args.transcript:
        text = path.read_text(encoding="utf-8") if path.is_file() else args.input
        report = process_transcript_only(
            text,
            args.category,
            title=args.title or (path.stem if path.is_file() else "Transcript"),
        )
    else:
        report = process_episode(
            path if path.is_file() else args.input,
            args.category,
            title=args.title,
        )

    print(report.get("markdown", ""))
    print(f"\n[episode_id={report.get('episode_id')} db={report.get('source_path', 'n/a')}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
