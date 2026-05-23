#!/usr/bin/env python3
"""
Demo pipeline without paid STT: paste transcript → features → translation.

Use for Railway/local when OPENAI_API_KEY is not set. Does not download audio.

Example:
  python scripts/demo_process_episode.py --episode-id 1
  python scripts/demo_process_episode.py --episode-id 1 --transcript-file path/to.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_TRANSCRIPT = (
    ROOT / "tests" / "fixtures" / "sample_transcript.txt"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Free demo: process episode with pasted text")
    parser.add_argument("--episode-id", type=int, required=True)
    parser.add_argument(
        "--transcript-file",
        type=Path,
        default=DEFAULT_TRANSCRIPT,
        help="Text file to use as transcript (default: tests/fixtures/sample_transcript.txt)",
    )
    args = parser.parse_args()

    path = args.transcript_file
    if not path.is_file():
        print(f"Transcript file not found: {path}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 40:
        print("Transcript too short (need at least 40 characters).", file=sys.stderr)
        return 1

    from backend.api.deps import get_session_factory
    from backend.services.episode_pipeline_service import run_episode_pipeline

    db = get_session_factory()()
    try:
        result = run_episode_pipeline(db, args.episode_id, transcript=text)
    except Exception as exc:
        print(f"Pipeline failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(json.dumps(result.to_dict(), indent=2))
    print(
        f"\nOK episode {args.episode_id} → status={result.status}, "
        f"template={result.template_id}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
