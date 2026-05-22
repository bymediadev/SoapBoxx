# backend/youtube_subtitles.py
"""
Deterministic English subtitle fetch for YouTube (minimal requests, rate-limit friendly).

Strategy:
1. If ``{video_id}.en.vtt`` (or a single ``{video_id}.en*.vtt``) already exists under ``out_dir``, skip yt-dlp entirely.
2. Otherwise try **manual** captions only: ``--write-subs --sub-langs en`` (one request batch).
3. If still missing, try **auto** captions only: ``--write-auto-subs --sub-langs en``.

Does not request multiple locale variants (no en-af, en-ar, …). Use ``en`` only.

**Audio download (ASR path):** :func:`download_youtube_best_audio` pulls a single best-audio track for
local/cloud transcription when YouTube captions are missing or too noisy. Requires ``ffmpeg`` (same
as typical ``yt-dlp -x`` installs).

Env (optional):
  SOAPBOXX_YTDLP_SLEEP_INTERVAL — seconds between phases (default 1.0)
  SOAPBOXX_YTDLP_MAX_SLEEP — passed to yt-dlp ``--max-sleep-interval`` (default 5)
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import parse_qs, urlparse


def parse_youtube_video_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[\w-]{11}", s):
        return s
    parsed = urlparse(s)
    if "youtube.com" in (parsed.netloc or "").lower():
        if parsed.path.startswith("/watch"):
            q = parse_qs(parsed.query)
            v = q.get("v", [""])[0]
            if len(v) == 11:
                return v
        m = re.search(r"/(?:embed|v|shorts)/([\w-]{11})", parsed.path)
        if m:
            return m.group(1)
    if "youtu.be" in (parsed.netloc or "").lower():
        m = re.match(r"^/([\w-]{11})", parsed.path or "")
        if m:
            return m.group(1)
    raise ValueError(f"Could not parse YouTube video id from: {url_or_id!r}")


def resolve_existing_en_vtt(out_dir: Path, video_id: str) -> Optional[Path]:
    """Return path to an existing English VTT if present (prefer exact ``id.en.vtt``)."""
    exact = out_dir / f"{video_id}.en.vtt"
    if exact.is_file():
        return exact
    matches: List[Path] = sorted(out_dir.glob(f"{video_id}.en*.vtt"))
    for p in matches:
        if p.is_file() and p.suffix.lower() == ".vtt":
            return p
    return None


def _yt_dlp_base(out_dir: Path, output_template: str) -> List[str]:
    return [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--no-playlist",
        "--sub-format",
        "vtt",
        "-o",
        output_template,
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "--sleep-interval",
        os.getenv("SOAPBOXX_YTDLP_SLEEP_REQUESTS", "1"),
        "--max-sleep-interval",
        os.getenv("SOAPBOXX_YTDLP_MAX_SLEEP", "5"),
    ]


def download_youtube_en_vtt(
    url: str,
    out_dir: Path,
    *,
    video_id: Optional[str] = None,
) -> Optional[Path]:
    """
    Ensure one English VTT exists for the video; return its path or None.

    Uses at most two yt-dlp invocations (manual en, then auto en). Skips entirely if a file already exists.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = video_id or parse_youtube_video_id(url)
    existing = resolve_existing_en_vtt(out_dir, vid)
    if existing is not None:
        return existing

    output_template = str(out_dir / "%(id)s")
    base = _yt_dlp_base(out_dir, output_template)
    sleep_between = float(os.getenv("SOAPBOXX_YTDLP_SLEEP_INTERVAL", "1.0"))

    phases: List[List[str]] = [
        # Manual captions only (no auto) — fewer subtitle tracks requested
        base
        + [
            "--write-subs",
            "--no-write-auto-subs",
            "--sub-langs",
            "en",
            "--",
            url,
        ],
        # Auto captions only — if manual missing
        base
        + [
            "--write-auto-subs",
            "--no-write-subs",
            "--sub-langs",
            "en",
            "--",
            url,
        ],
    ]

    for i, cmd in enumerate(phases):
        if i:
            time.sleep(sleep_between)
        try:
            subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return resolve_existing_en_vtt(out_dir, vid)
        found = resolve_existing_en_vtt(out_dir, vid)
        if found is not None:
            return found

    return resolve_existing_en_vtt(out_dir, vid)


def resolve_existing_audio(out_dir: Path, video_id: str) -> Optional[Path]:
    """Return a previously downloaded audio file for ``video_id``, if any."""
    out_dir = Path(out_dir)
    for ext in (".m4a", ".opus", ".webm", ".mp3", ".ogg", ".wav"):
        p = out_dir / f"{video_id}{ext}"
        if p.is_file():
            return p
    return None


def download_youtube_best_audio(
    url: str,
    out_dir: Path,
    *,
    video_id: Optional[str] = None,
) -> Optional[Path]:
    """
    Download the best **audio-only** stream and extract to ``m4a`` for ASR.

    Used when YouTube captions are weak and :class:`transcriber.Transcriber` should read the episode
    audio. Requires ``ffmpeg`` (typical ``yt-dlp`` setups).

    **OpenAI Whisper HTTP** (``SOAPBOXX_TRANSCRIBER=openai``) caps audio at ~25MB in ``transcriber.py``.
    Long episodes: use ``SOAPBOXX_TRANSCRIBER=local`` or ``assemblyai``, or set
    ``SOAPBOXX_YOUTUBE_ASR_AUDIO_QUALITY`` to a higher ffmpeg VBR level (e.g. ``5``) to shrink ``m4a``.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = video_id or parse_youtube_video_id(url)
    existing = resolve_existing_audio(out_dir, vid)
    if existing is not None:
        return existing

    quality = (os.getenv("SOAPBOXX_YOUTUBE_ASR_AUDIO_QUALITY") or "0").strip() or "0"
    output_template = str(out_dir / f"{vid}.%(ext)s")
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "-f",
        "bestaudio/best",
        "--extract-audio",
        "--audio-format",
        "m4a",
        "--audio-quality",
        quality,
        "-o",
        output_template,
        "--retries",
        "3",
        "--fragment-retries",
        "3",
        "--sleep-interval",
        os.getenv("SOAPBOXX_YTDLP_SLEEP_REQUESTS", "1"),
        "--max-sleep-interval",
        os.getenv("SOAPBOXX_YTDLP_MAX_SLEEP", "5"),
        "--",
        url,
    ]
    try:
        subprocess.run(cmd, check=False, capture_output=True, text=True)
    except OSError:
        return resolve_existing_audio(out_dir, vid)
    return resolve_existing_audio(out_dir, vid)
