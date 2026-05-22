"""YouTube → transcript (captions first, optional ASR fallback)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ingest import IngestResult


def _repo_cache_dir() -> Path:
    raw = (os.getenv("SOAPBOXX_INGEST_CACHE") or "").strip()
    if raw:
        return Path(raw)
    root = Path(__file__).resolve().parents[2]
    d = root / "data" / "ingest_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _vtt_to_text(vtt_path: Path) -> str:
    lines = vtt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: List[str] = []
    last = ""
    for line in lines:
        s = line.strip()
        if not s or s.startswith("WEBVTT") or "-->" in s or re.fullmatch(r"\d+", s):
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if not s or s == last:
            continue
        out.append(s)
        last = s
    return "\n".join(out)


def _fetch_metadata(url: str) -> Dict[str, str]:
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
        obj.get("uploader") or obj.get("channel") or obj.get("channel_id") or ""
    ).strip()
    cats = obj.get("categories")
    genre = ""
    if isinstance(cats, list) and cats:
        genre = str(cats[0] or "").strip()
    return {"title": title, "creator": creator, "genre": genre or "Podcast"}


def fetch_youtube_episode(
    url: str,
    *,
    title: str = "",
    creator: str = "",
    transcript_mode: str = "auto",
    cache_dir: Optional[Path] = None,
) -> IngestResult:
    """
    Pull transcript from YouTube.

    ``transcript_mode``: ``captions`` | ``asr`` | ``auto`` (captions, ASR if weak/missing).
    """
    from backend.youtube_subtitles import (
        download_youtube_best_audio,
        download_youtube_en_vtt,
        parse_youtube_video_id,
    )

    mode = (transcript_mode or "auto").strip().lower()
    if mode not in ("captions", "asr", "auto"):
        mode = "auto"

    vid = parse_youtube_video_id(url)
    watch = url if "youtube" in url or "youtu.be" in url else f"https://www.youtube.com/watch?v={vid}"
    out_dir = Path(cache_dir or _repo_cache_dir()) / vid
    out_dir.mkdir(parents=True, exist_ok=True)

    warnings: List[str] = []
    md = _fetch_metadata(watch)
    resolved_title = (title or md.get("title") or vid).strip()
    resolved_creator = (creator or md.get("creator") or "YouTube").strip()

    caption_text = ""
    if mode in ("captions", "auto"):
        vtt = download_youtube_en_vtt(watch, out_dir, video_id=vid)
        if vtt and vtt.is_file():
            raw = _vtt_to_text(vtt)
            try:
                from backend.transcript_structure_extract import clean_caption_transcript
            except ImportError:
                from transcript_structure_extract import clean_caption_transcript  # type: ignore

            caption_text = clean_caption_transcript(raw)
        else:
            warnings.append("No English YouTube captions found (install yt-dlp).")

    asr_text = ""
    if mode == "asr" or (mode == "auto" and len(caption_text.split()) < 200):
        ap = download_youtube_best_audio(watch, out_dir, video_id=vid)
        if ap and ap.is_file():
            try:
                from backend.intelligence_v1.transcribe import transcribe_file

                tr = transcribe_file(ap)
                asr_text = str(tr.get("transcript") or "").strip()
                if asr_text.startswith("Error"):
                    asr_text = ""
                    warnings.append(f"ASR failed: {tr}")
                else:
                    warnings.append("Transcript from downloaded audio (ASR).")
            except Exception as exc:
                warnings.append(f"ASR error: {exc}")
        else:
            warnings.append("Could not download audio for ASR (ffmpeg + yt-dlp required).")

    if mode == "asr" and asr_text:
        transcript = asr_text
        source = "youtube_asr"
    elif caption_text and (mode != "auto" or len(caption_text.split()) >= len(asr_text.split())):
        transcript = caption_text
        source = "youtube_captions"
    elif asr_text:
        transcript = asr_text
        source = "youtube_asr"
    else:
        transcript = caption_text or asr_text
        source = "youtube"

    if not transcript or len(transcript.split()) < 20:
        raise RuntimeError(
            "Could not extract a usable transcript from this URL. "
            "Try captions on YouTube, install yt-dlp/ffmpeg, or paste the transcript manually."
        )

    try:
        from backend.episode_coach_report import prepare_coach_transcript

        transcript, import_title = prepare_coach_transcript(transcript)
        if not title and import_title:
            resolved_title = import_title
    except Exception:
        pass

    return IngestResult(
        transcript=transcript.strip(),
        title=resolved_title,
        creator=resolved_creator,
        source_type="youtube",
        source_ref=watch,
        video_id=vid,
        warnings=warnings,
        extra={"transcript_source": source, "genre": md.get("genre", "")},
    )
