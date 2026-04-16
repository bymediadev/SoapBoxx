#!/usr/bin/env python3
"""
Download English captions for a YouTube video and run the full v3 network brief pipeline
(``episode_brief.py --v3``) — for real 30–90+ minute podcast episodes.

Requires:
  - ``yt-dlp`` (``python -m yt_dlp``)
  - For LLM: ``SOAPBOXX_OLLAMA_MODEL``, ``ollama serve``, optional ``OLLAMA_HOST``

Examples:
  # Download only + transcript stats (no Ollama)
  set SOAPBOXX_OFFLINE=1
  python scripts/run_youtube_podcast_v3_test.py --url "https://www.youtube.com/watch?v=SwQhKFMxmDY" --dry-run

  # Full-length captions + recommended timeouts/heartbeats (100k+ char scale)
  python scripts/run_youtube_podcast_v3_test.py --preset full --id SwQhKFMxmDY --title "Episode" --creator "Podcast" --out reports/podcast_full.md --json-out reports/podcast_full.json

  # Faster smoke preset (optional --max-chars)
  python scripts/run_youtube_podcast_v3_test.py --preset smoke --id Bb-eLRjU7uQ --max-chars 120000 --out reports/smoke.md

  # Show env keys for each preset
  python scripts/run_youtube_podcast_v3_test.py --list-presets
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = ROOT / "scripts"


def _load_repo_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        pass


def vtt_to_text(vtt_path: Path) -> str:
    lines = vtt_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out: list[str] = []
    last = ""
    for line in lines:
        s = line.strip()
        if not s or s.startswith("WEBVTT") or "-->" in s or re.fullmatch(r"\d+", s):
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if not s:
            continue
        if s != last:
            out.append(s)
            last = s
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="YouTube captions → v3 SoapBoxx brief")
    parser.add_argument("--url", "-u", help="Full YouTube watch URL")
    parser.add_argument("--id", "-i", dest="video_id", help="11-char video id")
    parser.add_argument("--title", "-t", default="", help="Episode title (default: video id)")
    parser.add_argument("--creator", "-c", default="YouTube", help="Show / channel label")
    parser.add_argument("--genre", "-g", default="Podcast", help="Genre")
    parser.add_argument(
        "--out-dir",
        default="",
        help=f"Where to store .vtt and .txt (default: {ROOT}/reports/youtube_podcast_<ts>)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=0,
        help="Trim transcript to this many characters (0 = full)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download + write transcript + print stats only; do not run v3",
    )
    parser.add_argument("--out", "-o", default="", help="Markdown output (passed to episode_brief.py)")
    parser.add_argument("--json-out", default="", help="Optional JSON bundle output")
    parser.add_argument(
        "--preset",
        choices=["none", "full", "smoke"],
        default="none",
        help="Merge env overlay for long runs: full (timeouts+heartbeats+brief/workflow windows) or smoke (faster).",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Print preset descriptions and exit.",
    )
    args = parser.parse_args()

    _load_repo_dotenv()
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    from podcast_run_presets import apply_preset, describe_preset, list_preset_names

    if args.list_presets:
        print("Available presets:", ", ".join(["none"] + list_preset_names()), flush=True)
        for name in list_preset_names():
            print(flush=True)
            print(describe_preset(name), flush=True)
        return 0

    if not args.url and not args.video_id:
        parser.error("Provide --url or --id")

    sys.path.insert(0, str(ROOT / "backend"))
    from youtube_subtitles import download_youtube_en_vtt, parse_youtube_video_id

    vid = args.video_id or ""
    url = args.url or ""
    if url:
        vid = parse_youtube_video_id(url)
    if not re.fullmatch(r"[\w-]{11}", vid):
        print(f"Bad video id: {vid!r}", file=sys.stderr)
        return 1

    url = url or f"https://www.youtube.com/watch?v={vid}"
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "reports" / f"youtube_podcast_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Video: {vid}\nURL:   {url}\nOut:   {out_dir}", flush=True)
    vtt_path = download_youtube_en_vtt(url, out_dir, video_id=vid)
    if vtt_path is None:
        print("No English subtitles (manual or auto). Try another video or upload captions.", file=sys.stderr)
        return 2

    raw = vtt_to_text(vtt_path)
    if args.max_chars and len(raw) > args.max_chars:
        raw = raw[: args.max_chars]
    txt_path = out_dir / f"{vid}.txt"
    txt_path.write_text(raw, encoding="utf-8")

    words = len(raw.split())
    print(
        f"Transcript: {words:,} words, {len(raw):,} chars -> {txt_path}",
        flush=True,
    )

    if args.dry_run:
        print("Dry-run: skipping episode_brief.py (--dry-run).", flush=True)
        return 0

    title = args.title or vid
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "episode_brief.py"),
        "--transcript",
        str(txt_path),
        "--v3",
        "--title",
        title,
        "--creator",
        args.creator,
        "--genre",
        args.genre,
    ]
    if args.out:
        cmd += ["--out", args.out if os.path.isabs(args.out) else str(ROOT / args.out)]
    if args.json_out:
        cmd += ["--json-out", args.json_out if os.path.isabs(args.json_out) else str(ROOT / args.json_out)]

    print("Running:", " ".join(cmd), flush=True)
    env = apply_preset(os.environ.copy(), args.preset)
    if args.preset != "none":
        print(describe_preset(args.preset), flush=True)
    return subprocess.call(cmd, cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
