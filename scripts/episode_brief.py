#!/usr/bin/env python3
"""
CLI: generate a network episode brief (Markdown + JSON) from transcript or audio.

**Primary:** v3 Episode Report (`--v3`). **Secondary:** v2 compact brief without `--v3`
(see `docs/network_episode_brief_v3.md` and `network_episode_brief_v2.md`).

Usage (LLM is Ollama-only; set a model name — or copy ``.env.example`` to ``.env`` in repo root):
  set SOAPBOXX_OLLAMA_MODEL=llama3.1:8b
  set OLLAMA_HOST=http://127.0.0.1:11434
  python scripts/episode_brief.py --transcript path/to.txt --title "Ep title" --creator "Show" --out brief.md
  python scripts/episode_brief.py --transcript t.txt --v3 --out report_v3.md
  python scripts/episode_brief.py --transcript t.txt --v3 --lead-audit --out lead_audit.md

Network-facing editorial snapshot (markdown, no JSON pipeline):
  python scripts/episode_brief.py --transcript t.txt --network-snapshot --title "Ep" --creator "Show" --out snapshot.md

With ``--v3``, uses ``FeedbackEngine.generate_network_brief_v3`` (unified markdown + workflow JSON).
Set ``SOAPBOXX_BLUEPRINT_V1=1`` in ``.env`` for Master Blueprint v1 on that path.

With ``--v3 --lead-audit``, the main ``-o`` / stdout Markdown is the 1-page lead audit (cold outreach card).
Use ``--full-markdown-out`` if you also want the full unified export written to a second file.

Optional:
  SOAPBOXX_OFFLINE=1 - skip LLM; empty v2 brief shell + warnings (no synthetic narrative)
  Large episodes: raise single-pass limit so the full transcript is sent in one call, e.g.
    set SOAPBOXX_BRIEF_MAX_CHARS=200000
  Strict reality gate (exit non-zero if checks fail): set SOAPBOXX_V3_REALITY_STRICT=1
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_repo_dotenv() -> None:
    root = _repo_root()
    env_path = os.path.join(root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass


def main() -> int:
    root = _repo_root()
    _load_repo_dotenv()
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
        help="Full v3 path: unified markdown_export + workflow JSON + optional blueprint_v1 (see .env.example)",
    )
    parser.add_argument(
        "--json-v3-out",
        help="Write full v3 report JSON (report_v3) to this path",
    )
    parser.add_argument(
        "--lead-audit",
        action="store_true",
        help="With --v3: render the 1-page lead audit to -o / stdout (use --full-markdown-out for the long export)",
    )
    parser.add_argument(
        "--full-markdown-out",
        help="With --v3 --lead-audit: also write the full markdown_export to this path",
    )
    parser.add_argument(
        "--network-snapshot",
        action="store_true",
        help="Ollama-only: NETWORK_DEMO_EPISODE_SNAPSHOT_PROMPT + transcript -> markdown (no v3/JSON pipeline)",
    )
    args = parser.parse_args()

    if args.v3 and args.network_snapshot:
        parser.error("Use either --v3 or --network-snapshot, not both.")

    if args.lead_audit and not args.v3:
        parser.error("--lead-audit requires --v3")

    if args.full_markdown_out and not args.lead_audit:
        parser.error("--full-markdown-out is only used with --v3 --lead-audit")

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

    if args.network_snapshot:
        from blueprint_v1.llm_runner import run_text_prompt
        from blueprint_v1.prompts import NETWORK_DEMO_EPISODE_SNAPSHOT_PROMPT

        max_chars = int(os.getenv("SOAPBOXX_NETWORK_SNAPSHOT_MAX_CHARS", "120000"))
        body = text[:max_chars] if len(text) > max_chars else text
        ctx = (
            f"Episode title: {args.title or '(unknown)'}\n"
            f"Show / creator: {args.creator or '(unknown)'}\n"
            f"Genre: {args.genre or '(unknown)'}\n\n"
            f"---\n\nTRANSCRIPT:\n\n{body}"
        )
        full_user = f"{NETWORK_DEMO_EPISODE_SNAPSHOT_PROMPT}\n\n---\n\n{ctx}"
        md = run_text_prompt(
            full_user,
            system="Follow the user's output format exactly. Output markdown only. No preamble.",
            max_tokens=int(os.getenv("SOAPBOXX_NETWORK_SNAPSHOT_MAX_TOKENS", "4096")),
            temperature=float(os.getenv("SOAPBOXX_NETWORK_SNAPSHOT_TEMPERATURE", "0.2")),
        )
        if md is None:
            print(
                "Network snapshot failed: Ollama returned no text. "
                "Set SOAPBOXX_OLLAMA_MODEL and check OLLAMA_HOST / SOAPBOXX_OLLAMA_HTTP_TIMEOUT.",
                file=sys.stderr,
            )
            return 1
        result = {"warnings": [], "model": os.getenv("SOAPBOXX_OLLAMA_MODEL", "")}
    elif args.v3:
        from feedback_engine import FeedbackEngine

        fe = FeedbackEngine()
        result = fe.generate_network_brief_v3(
            text,
            title=args.title,
            creator=args.creator,
            genre=args.genre,
            strict_references=True,
            include_v2_markdown=True,
            include_workflow_json=True,
        )
        full_md = (
            result.get("markdown_export")
            or result.get("markdown_v3")
            or result.get("markdown")
            or ""
        )
        # Defensive: some UIs / older bundles surface ``markdown_v3`` or stale strings that never
        # went through :func:`finalize_unified_markdown_export`. Always normalize v3 markdown here.
        try:
            from episode_report_v3 import finalize_unified_markdown_export

            full_md = finalize_unified_markdown_export(str(full_md or ""))
        except Exception:
            pass
        md = full_md
        if args.lead_audit:
            from lead_audit_render import render_lead_audit_markdown

            bundle = {
                "report_v3": result.get("report_v3") or {},
                "workflow_report": result.get("workflow_report") or {},
                "blueprint_v1": result.get("blueprint_v1"),
                "meta": {"title": args.title, "creator": args.creator, "genre": args.genre},
            }
            md = render_lead_audit_markdown(bundle)
    else:
        from episode_intelligence import generate_episode_brief

        result = generate_episode_brief(text, meta)
        md = result.get("markdown", "")

    if args.out:
        out_path = args.out if os.path.isabs(args.out) else os.path.join(root, args.out)
        _d = os.path.dirname(out_path)
        if _d:
            os.makedirs(_d, exist_ok=True)
        # Use UTF-8 with BOM for markdown files so Windows PowerShell `Get-Content`
        # auto-detects encoding and does not display mojibake (e.g. "â€”").
        with open(out_path, "w", encoding="utf-8-sig") as f:
            f.write(md)
        print(f"Wrote {out_path}")
    else:
        print(md)

    if args.v3 and args.lead_audit and args.full_markdown_out:
        fmp = (
            args.full_markdown_out
            if os.path.isabs(args.full_markdown_out)
            else os.path.join(root, args.full_markdown_out)
        )
        _fd = os.path.dirname(fmp)
        if _fd:
            os.makedirs(_fd, exist_ok=True)
        full_md = (
            result.get("markdown_export")
            or result.get("markdown_v3")
            or result.get("markdown")
            or ""
        )
        try:
            from episode_report_v3 import finalize_unified_markdown_export

            full_md = finalize_unified_markdown_export(str(full_md or ""))
        except Exception:
            pass
        with open(fmp, "w", encoding="utf-8-sig") as f:
            f.write(full_md)
        print(f"Wrote {fmp}")

    if args.json_out:
        jp = args.json_out if os.path.isabs(args.json_out) else os.path.join(root, args.json_out)
        _jd = os.path.dirname(jp)
        if _jd:
            os.makedirs(_jd, exist_ok=True)
        if args.v3:
            payload = {
                "brief": result.get("brief"),
                "report_v3": result.get("report_v3"),
                "workflow_report": result.get("workflow_report"),
                "blueprint_v1": result.get("blueprint_v1"),
                "markdown_export": result.get("markdown_export"),
                "warnings": result.get("warnings"),
                "model": result.get("model"),
                "workflow_version": result.get("workflow_version"),
            }
        elif args.network_snapshot:
            payload = {
                "markdown_network_snapshot": md,
                "warnings": result.get("warnings"),
                "model": result.get("model"),
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

    if args.v3:
        strict = (os.getenv("SOAPBOXX_V3_REALITY_STRICT") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if strict:
            wf = result.get("workflow_report") or {}
            meta = wf.get("metadata") or {}
            chk = meta.get("v3_reality_check") or {}
            if not chk:
                print(
                    "SOAPBOXX_V3_REALITY_STRICT=1 but workflow_report has no v3_reality_check "
                    "(include_workflow_json must be true).",
                    file=sys.stderr,
                )
                return 1
            if not chk.get("passed") or not chk.get("would_ship"):
                print("Reality check strict fail — metadata.v3_reality_check:", file=sys.stderr)
                for line in chk.get("failures") or []:
                    print(f"  {line}", file=sys.stderr)
                for line in chk.get("ship_blockers") or []:
                    print(f"  {line}", file=sys.stderr)
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
