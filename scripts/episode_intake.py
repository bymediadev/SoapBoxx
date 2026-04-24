#!/usr/bin/env python3
"""
One-command intake runner for transcript- or URL-driven SoapBoxx outputs.

Purpose:
- Take a transcript OR YouTube URL + metadata
- Run v3 report + workflow JSON
- Write a clean run folder with all shareable artifacts

Example:
  python scripts/episode_intake.py ^
    --transcript "reports/stub_rockefeller_education_transcript.txt" ^
    --title "Brainwash! - The Rockefeller School Psyop WORSE Than You Think" ^
    --creator "Julian Dorey" ^
    --genre "Education / Society"

  python scripts/episode_intake.py ^
    --url "https://www.youtube.com/watch?v=SwQhKFMxmDY"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_repo_dotenv(root: str) -> None:
    env_path = os.path.join(root, ".env")
    if not os.path.isfile(env_path):
        return
    try:
        from dotenv import load_dotenv

        # Prefer repo .env over inherited shell/IDE (e.g. stale SOAPBOXX_OLLAMA_MODEL from an old session)
        load_dotenv(env_path, override=True)
    except ImportError:
        # dotenv is optional; env vars from shell still work.
        return


def _slug(s: str, max_len: int = 80) -> str:
    t = re.sub(r"[^a-zA-Z0-9]+", "_", str(s or "").strip()).strip("_")
    if not t:
        t = "episode"
    return t[:max_len]


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig") as f:
        f.write(text or "")


def _write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _vtt_to_text(vtt_path: str) -> str:
    """Minimal WEBVTT -> plain transcript conversion."""
    with open(vtt_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.read().splitlines()
    out: List[str] = []
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


def _run_preflight(root: str) -> None:
    preflight = os.path.join(root, "scripts", "preflight_soapboxx.py")
    cmd = [sys.executable, preflight, "--repo", root]
    cp = subprocess.run(cmd, cwd=root)
    if cp.returncode != 0:
        raise RuntimeError(f"Preflight failed (exit {cp.returncode})")


def _fetch_youtube_metadata(url: str) -> Dict[str, str]:
    """
    Best-effort metadata via yt-dlp JSON (title/uploader/channel/categories).
    Returns empty dict on failure so intake still runs.
    """
    if not url:
        return {}
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--no-playlist",
        "--dump-single-json",
        "--",
        url,
    ]
    try:
        cp = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except OSError:
        return {}
    if cp.returncode != 0 or not (cp.stdout or "").strip():
        return {}
    try:
        obj = json.loads(cp.stdout)
    except json.JSONDecodeError:
        return {}

    title = str(obj.get("title") or "").strip()
    creator = str(
        obj.get("uploader")
        or obj.get("channel")
        or obj.get("channel_id")
        or ""
    ).strip()
    cats = obj.get("categories")
    cat = ""
    if isinstance(cats, list) and cats:
        cat = str(cats[0] or "").strip()
    genre = cat or "Podcast"
    return {"title": title, "creator": creator, "genre": genre}


def _env_flag(name: str) -> str:
    return os.getenv(name, "").strip().lower()


def _groq_key() -> str:
    return os.getenv("SOAPBOXX_GROQ_API_KEY", "").strip() or os.getenv("GROQ_API_KEY", "").strip()


def _auto_configure_groq_split_brain() -> None:
    """
    When a Groq API key is present, route **workflow** + **coach synthesis** to Groq; keep
    Ollama for v2/strict **brief** extraction in episode_intelligence (set SOAPBOXX_OLLAMA_MODEL).
    """
    if not _groq_key():
        return
    if not os.getenv("SOAPBOXX_WORKFLOW_LLM_BACKEND", "").strip():
        os.environ["SOAPBOXX_WORKFLOW_LLM_BACKEND"] = "groq"
    if _env_flag("SOAPBOXX_COACH_SYNTH") in ("0", "false", "no", "off"):
        return
    if not os.getenv("SOAPBOXX_COACH_SYNTH_BACKEND", "").strip():
        os.environ["SOAPBOXX_COACH_SYNTH_BACKEND"] = "groq"
    if not os.getenv("SOAPBOXX_COACH_SYNTH", "").strip():
        os.environ["SOAPBOXX_COACH_SYNTH"] = "1"


def _detect_ollama_model() -> str:
    """Return first local Ollama model name, or empty string."""
    try:
        cp = subprocess.run(["ollama", "list"], check=False, capture_output=True, text=True)
    except OSError:
        return ""
    if cp.returncode != 0:
        return ""
    lines = [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        return ""
    # Typical output:
    # NAME            ID              SIZE      MODIFIED
    # llama3.1:8b     <id>            4.7 GB    ...
    for ln in lines[1:]:
        if ln.lower().startswith("name "):
            continue
        name = ln.split()[0].strip()
        if name and name.lower() != "name":
            return name
    return ""


def _auto_enable_coach_synth_with_ollama() -> None:
    """
    Zero-config local intelligence:
    - if user did not explicitly disable coach synth
    - and no paid/cloud key is configured
    - and Ollama has at least one local model
    then set env so coach synthesis runs via Ollama.
    """
    if _env_flag("SOAPBOXX_COACH_SYNTH") in ("0", "false", "no", "off"):
        return
    if os.getenv("OPENAI_API_KEY", "").strip() or _groq_key():
        return
    model = os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip() or _detect_ollama_model()
    if not model:
        return
    if not os.getenv("SOAPBOXX_OLLAMA_MODEL", "").strip():
        os.environ["SOAPBOXX_OLLAMA_MODEL"] = model
    if not os.getenv("SOAPBOXX_COACH_SYNTH_BACKEND", "").strip():
        os.environ["SOAPBOXX_COACH_SYNTH_BACKEND"] = "ollama"
    if not os.getenv("SOAPBOXX_COACH_SYNTH", "").strip():
        os.environ["SOAPBOXX_COACH_SYNTH"] = "1"


def main() -> int:
    root = _repo_root()
    _load_repo_dotenv(root)
    # Intake writes a shareable teaser; full "producer pack" order stays available via SOAPBOXX_V3_FRAMING=full.
    os.environ.setdefault("SOAPBOXX_V3_FRAMING", "freebie")
    _auto_configure_groq_split_brain()
    _auto_enable_coach_synth_with_ollama()
    sys.path.insert(0, os.path.join(root, "backend"))

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--transcript", default="", help="Path to transcript .txt")
    p.add_argument("--url", default="", help="YouTube watch URL (caption-first path)")
    p.add_argument("--id", dest="video_id", default="", help="YouTube video id (11 chars)")
    p.add_argument("--title", default="", help="Episode title (auto when --url/--id)")
    p.add_argument("--creator", default="", help="Show / creator name (auto when --url/--id)")
    p.add_argument("--genre", default="", help="Genre label (optional)")
    p.add_argument(
        "--runs-dir",
        default=os.path.join("runs", "intake"),
        help="Base output directory (default: runs/intake)",
    )
    p.add_argument(
        "--run-id",
        default="",
        help="Optional run folder name override (otherwise auto-generated)",
    )
    p.add_argument(
        "--strict-rigor",
        action="store_true",
        help="Exit non-zero when argument_rigor.status is FAIL.",
    )
    p.add_argument(
        "--preflight",
        action="store_true",
        help="Run scripts/preflight_soapboxx.py before intake.",
    )
    args = p.parse_args()

    if not args.transcript and not args.url and not args.video_id:
        print("Provide --transcript or --url/--id", file=sys.stderr)
        return 1

    video_id = str(args.video_id or "").strip()
    url = str(args.url or "").strip()
    title = str(args.title or "").strip()
    creator = str(args.creator or "").strip()
    genre = str(args.genre or "").strip()
    tx_path = ""
    transcript = ""

    if args.preflight:
        try:
            _run_preflight(root)
        except Exception as e:
            print(str(e), file=sys.stderr)
            return 1

    from feedback_engine import FeedbackEngine
    from episode_report_v3 import finalize_unified_markdown_export, render_episode_report_v3_markdown

    if args.transcript:
        tx_path = args.transcript if os.path.isabs(args.transcript) else os.path.join(root, args.transcript)
        if not os.path.isfile(tx_path):
            print(f"Transcript not found: {tx_path}", file=sys.stderr)
            return 1
        transcript = _read_text(tx_path)
        if not title:
            title = os.path.splitext(os.path.basename(tx_path))[0].replace("_", " ")
        if not creator:
            creator = "Unknown Creator"
        if not genre:
            genre = "Podcast"
    else:
        sys.path.insert(0, os.path.join(root, "backend"))
        from youtube_subtitles import download_youtube_en_vtt, parse_youtube_video_id

        if url:
            video_id = parse_youtube_video_id(url)
        if not re.fullmatch(r"[\w-]{11}", video_id or ""):
            print(f"Bad/empty YouTube video id: {video_id!r}", file=sys.stderr)
            return 1
        url = url or f"https://www.youtube.com/watch?v={video_id}"
        md = _fetch_youtube_metadata(url)
        if not title:
            title = str(md.get("title") or "").strip() or video_id
        if not creator:
            creator = str(md.get("creator") or "").strip() or "YouTube"
        if not genre:
            genre = str(md.get("genre") or "").strip() or "Podcast"
        if title:
            print(f"Resolved title:   {title}")
        if creator:
            print(f"Resolved creator: {creator}")
        if genre:
            print(f"Resolved genre:   {genre}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_folder_name = args.run_id.strip() or f"{_slug(creator, 36)}_{_slug(title, 72)}_{ts}"
    base_runs = args.runs_dir if os.path.isabs(args.runs_dir) else os.path.join(root, args.runs_dir)
    run_dir = os.path.join(base_runs, run_folder_name)
    os.makedirs(run_dir, exist_ok=True)

    if args.transcript:
        _write_text(os.path.join(run_dir, "transcript.txt"), transcript)
    else:
        vtt_path = download_youtube_en_vtt(url, run_dir, video_id=video_id)
        if vtt_path is None:
            print("No English subtitles found (manual or auto).", file=sys.stderr)
            return 2
        transcript = _vtt_to_text(str(vtt_path))
        tx_path = os.path.join(run_dir, "transcript.txt")
        _write_text(tx_path, transcript)

    fe = FeedbackEngine()
    out = fe.generate_network_brief_v3(
        transcript,
        title=title,
        creator=creator,
        genre=genre,
        strict_references=True,
        include_v2_markdown=True,
        include_workflow_json=True,
    )

    report_v3 = out.get("report_v3") or {}
    workflow_report = out.get("workflow_report") or {}
    unified_md = finalize_unified_markdown_export(
        str(out.get("markdown_export") or out.get("markdown_v3") or out.get("markdown") or "")
    )
    coach_md = render_episode_report_v3_markdown(report_v3, workflow_report=workflow_report)

    path_unified = os.path.join(run_dir, "episode_report_unified.md")
    path_coach = os.path.join(run_dir, "episode_report_v3.md")
    path_bundle = os.path.join(run_dir, "bundle.json")
    path_r3 = os.path.join(run_dir, "report_v3.json")
    path_wf = os.path.join(run_dir, "workflow_report.json")
    path_summary = os.path.join(run_dir, "intake_summary.json")

    _write_text(path_unified, unified_md)
    _write_text(path_coach, coach_md)
    _write_json(path_bundle, out if isinstance(out, dict) else {"result": out})
    _write_json(path_r3, report_v3 if isinstance(report_v3, dict) else {})
    _write_json(path_wf, workflow_report if isinstance(workflow_report, dict) else {})

    rr = report_v3.get("report_readiness") if isinstance(report_v3, dict) else {}
    ar = report_v3.get("argument_rigor") if isinstance(report_v3, dict) else {}
    summary = {
        "run_dir": run_dir,
        "input": {
            "transcript_path": tx_path,
            "url": url,
            "video_id": video_id,
        },
        "title": title,
        "creator": creator,
        "genre": genre,
        "output_mode": (rr or {}).get("output_mode"),
        "readiness_band": (rr or {}).get("band"),
        "argument_rigor_status": (ar or {}).get("status"),
        "argument_rigor_score": (ar or {}).get("score"),
        "warnings": out.get("warnings") if isinstance(out, dict) else [],
        "dialin_checklist": (out.get("dialin_checklist") or []) if isinstance(out, dict) else [],
        "artifacts": {
            "episode_report_unified_md": path_unified,
            "episode_report_v3_md": path_coach,
            "bundle_json": path_bundle,
            "report_v3_json": path_r3,
            "workflow_report_json": path_wf,
        },
    }
    _write_json(path_summary, summary)

    print(f"Wrote run folder: {run_dir}")
    print(f"- unified markdown: {path_unified}")
    print(f"- coach markdown:   {path_coach}")
    print(f"- report_v3 json:   {path_r3}")
    print(f"- workflow json:    {path_wf}")
    print(f"- summary json:     {path_summary}")
    dialin = (out.get("dialin_checklist") or []) if isinstance(out, dict) else []
    if dialin:
        print("", file=sys.stderr)
        print("DIAL-IN (fix these first for full v3 / bookable output):", file=sys.stderr)
        for ln in dialin:
            print(f"  - {ln}", file=sys.stderr)

    if args.strict_rigor and str((ar or {}).get("status") or "").upper() == "FAIL":
        print("argument_rigor.status=FAIL (strict mode)", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

