#!/usr/bin/env python3
"""
CLI: generate a network episode brief (Markdown + JSON) from transcript or audio.

**Primary:** v3 Episode Report (`--v3`). **Secondary:** v2 compact brief without `--v3`
(see `docs/network_episode_brief_v3.md` and `network_episode_brief_v2.md`).

Usage (LLM is Ollama-only; set a model name):
  set SOAPBOXX_OLLAMA_MODEL=llama3.1:8b
  set OLLAMA_HOST=http://127.0.0.1:11434
  python scripts/episode_brief.py --transcript path/to.txt --title "Ep title" --creator "Show" --out brief.md
  python scripts/episode_brief.py --transcript t.txt --v3 --out report_v3.md

Optional:
  SOAPBOXX_OFFLINE=1 - skip LLM; empty v2 brief shell + warnings (no synthetic narrative)
  Large episodes: raise single-pass limit so the full transcript is sent in one call, e.g.
    set SOAPBOXX_BRIEF_MAX_CHARS=100000
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    root = _repo_root()
    sys.path.insert(0, os.path.join(root, "backend"))

    parser = argparse.ArgumentParser(description="SoapBoxx network episode brief")
    parser.add_argument("--transcript", "-t", help="Path to transcript .txt")
    parser.add_argument("--audio", "-a", help="Path to audio (mp3/wav/etc.); transcribes via backend Transcriber")
    parser.add_argument("--title", default="", help="Episode title")
    parser.add_argument("--creator", "-c", default="", help="Show / creator name")
    parser.add_argument("--genre", "-g", default="", help="Genre")
    parser.add_argument("--out", "-o", help="Write Markdown to this path")
    parser.add_argument("--json-out", help="Also write full brief JSON to this path")
    parser.add_argument(
        "--v3",
        action="store_true",
        help="Emit v3 Episode Report (markdown_v3 + report_v3 JSON fields)",
    )
    parser.add_argument(
        "--json-v3-out",
        help="Write full v3 report JSON (report_v3) to this path",
    )
    args = parser.parse_args()

    if not args.transcript and not args.audio:
        parser.error("Provide --transcript or --audio")

    text = ""
    if args.transcript:
        with open(args.transcript, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    else:
        from transcriber import Transcriber

        with open(args.audio, "rb") as f:
            data = f.read()
        tr = Transcriber(service=os.getenv("SOAPBOXX_TRANSCRIBER", "openai"))
        text = tr.transcribe(data)
        if not text or text.startswith("Error"):
            print(text or "Transcription failed", file=sys.stderr)
            return 1

    meta = {
        "title": args.title,
        "creator": args.creator,
        "genre": args.genre,
    }

    if args.v3:
        from episode_report_v3 import generate_episode_report_v3

        result = generate_episode_report_v3(text, meta, strict_references=True)
        md = result.get("markdown_v3") or ""
    else:
        from episode_intelligence import generate_episode_brief

        result = generate_episode_brief(text, meta)
        md = result.get("markdown", "")

    if args.out:
        out_path = args.out if os.path.isabs(args.out) else os.path.join(root, args.out)
        _d = os.path.dirname(out_path)
        if _d:
            os.makedirs(_d, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Wrote {out_path}")
    else:
        print(md)

    if args.json_out:
        jp = args.json_out if os.path.isabs(args.json_out) else os.path.join(root, args.json_out)
        _jd = os.path.dirname(jp)
        if _jd:
            os.makedirs(_jd, exist_ok=True)
        if args.v3:
            payload = {
                "brief": result.get("brief"),
                "report_v3": result.get("report_v3"),
                "warnings": result.get("warnings"),
                "model": result.get("model"),
                "workflow_version": result.get("workflow_version"),
            }
        else:
            payload = {
                "brief": result.get("brief"),
                "warnings": result.get("warnings"),
                "model": result.get("model"),
            }
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"Wrote {jp}")

    if args.json_v3_out and args.v3:
        jp = args.json_v3_out if os.path.isabs(args.json_v3_out) else os.path.join(root, args.json_v3_out)
        _jd = os.path.dirname(jp)
        if _jd:
            os.makedirs(_jd, exist_ok=True)
        with open(jp, "w", encoding="utf-8") as f:
            json.dump(result.get("report_v3"), f, indent=2, ensure_ascii=False)
        print(f"Wrote {jp}")

    for w in result.get("warnings") or []:
        print(f"Warning: {w}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
