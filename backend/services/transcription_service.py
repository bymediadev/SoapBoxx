"""Transcription + segmentation — Day 4 (metadata → text)."""

from __future__ import annotations

import re
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from backend.models import Episode, TranscriptSegment
from backend.services.pipeline_status import (
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_TRANSCRIBING,
    record_event,
    set_episode_status,
)

_SPEAKER_LINE = re.compile(
    r"^\s*(host|guest|speaker\s*\d+|interviewer|narrator)\s*:\s*",
    re.I,
)
_WPS = 2.5


def _max_cloud_stt_bytes() -> int:
    return int(os.getenv("SOAPBOXX_STT_MAX_BYTES", str(25 * 1024 * 1024)))


def _cloud_stt_soft_bytes() -> int:
    raw = os.getenv("SOAPBOXX_STT_SOFT_BYTES", "").strip()
    if raw:
        return int(raw)
    return int(_max_cloud_stt_bytes() * 0.92)


@dataclass
class TranscriptionResult:
    episode_id: int
    transcript_length: int
    segment_count: int


def _words(text: str) -> int:
    return len((text or "").split())


def _estimate_seconds(word_count: int) -> float:
    return round(max(0.0, word_count / _WPS), 2)


def build_segments_from_transcript(transcript: str) -> List[dict]:
    """
    Build time-estimated segments from transcript text.

    Uses speaker lines or paragraphs; assigns synthetic start/end times.
    """
    text = (transcript or "").strip()
    if not text:
        return []

    chunks: List[str] = []
    current: List[str] = []
    for line in text.splitlines():
        if _SPEAKER_LINE.match(line.strip()) and current:
            chunks.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current))

    if len(chunks) <= 1:
        chunks = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not chunks:
        chunks = [text]

    segments: List[dict] = []
    t = 0.0
    for chunk in chunks:
        dur = _estimate_seconds(_words(chunk))
        segments.append(
            {"start_time": t, "end_time": t + dur, "text": chunk.strip()}
        )
        t += dur
    return segments


def _size_hint_from_url(url: str) -> Optional[int]:
    try:
        query = parse_qs(urlparse(url).query)
        raw = (query.get("size") or [None])[0]
        if raw is None:
            return None
        size = int(raw)
        return size if size > 0 else None
    except Exception:
        return None


def _probe_remote_audio_size(url: str, *, timeout: int = 20) -> Optional[int]:
    hinted = _size_hint_from_url(url)
    if hinted:
        return hinted

    try:
        req = Request(
            url,
            headers={"User-Agent": "SoapBoxx-V1/1.0"},
            method="HEAD",
        )
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.headers.get("Content-Length")
            if raw:
                size = int(raw)
                return size if size > 0 else None
    except Exception:
        return None
    return None


def _download_audio(url: str, dest: Path, *, timeout: int = 120) -> None:
    req = Request(url, headers={"User-Agent": "SoapBoxx-V1/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        with dest.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                fh.write(chunk)


def _compress_audio_file_for_stt(source: Path, target: Path, *, bitrate: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-b:a",
            bitrate,
            str(target),
        ]
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and target.is_file():
            return
        err = (proc.stderr or proc.stdout or "").strip()
        if err:
            print(f"⚠️ ffmpeg compression failed ({bitrate}): {err}", flush=True)

    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(source)
        audio = audio.set_channels(1).set_frame_rate(16000)
        audio.export(target, format="mp3", bitrate=bitrate)
    except Exception as exc:
        raise ValueError(f"Audio compression failed ({bitrate}): {exc}") from exc


def _maybe_prepare_audio_for_cloud_stt(source: Path) -> Tuple[Path, Optional[Path]]:
    """
    Return an audio file ready for cloud STT.

    Files near the upload cap are normalized and compressed before they hit the
    cloud STT client so we avoid request-time crashes on constrained hosts.
    """
    original_size = source.stat().st_size
    soft_limit = _cloud_stt_soft_bytes()
    max_limit = _max_cloud_stt_bytes()
    if original_size <= soft_limit:
        return source, None

    import tempfile

    last_size = original_size
    compressed_path: Optional[Path] = None
    for bitrate in ("64k", "48k", "32k"):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            candidate = Path(tmp.name)
        try:
            _compress_audio_file_for_stt(source, candidate, bitrate=bitrate)
            last_size = candidate.stat().st_size
            if last_size <= max_limit:
                print(
                    (
                        "✅ STT audio prepared for cloud upload: "
                        f"{original_size / (1024 * 1024):.1f}MB -> "
                        f"{last_size / (1024 * 1024):.1f}MB ({bitrate})"
                    ),
                    flush=True,
                )
                compressed_path = candidate
                return candidate, compressed_path
        except Exception:
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
            raise

        try:
            candidate.unlink(missing_ok=True)
        except OSError:
            pass

    raise ValueError(
        (
            f"Audio is {original_size / (1024 * 1024):.1f}MB and still "
            f"{last_size / (1024 * 1024):.1f}MB after compression, above the "
            f"{max_limit / (1024 * 1024):.0f}MB cloud STT limit. "
            "Paste a transcript or use a shorter episode."
        )
    )


def transcribe_episode(
    db: Session,
    episode_id: int,
    *,
    transcript: Optional[str] = None,
) -> TranscriptionResult:
    """
    Store full_transcript + transcript_segments on episode.

    If ``transcript`` is provided, skip STT (tests / paste path).
    Else requires ``episode.audio_url`` and runs Transcriber.
    """
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")

    set_episode_status(db, episode, STATUS_TRANSCRIBING, commit=False)
    record_event(
        db,
        "pipeline.transcribing",
        f"Transcribing: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        commit=False,
    )

    try:
        full_text = _run_transcription(episode, transcript)
    except Exception as exc:
        set_episode_status(
            db, episode, STATUS_FAILED, error=str(exc), commit=False
        )
        record_event(
            db,
            "pipeline.failed",
            f"Transcription failed: {exc}",
            podcast_id=int(episode.podcast_id),
            episode_id=int(episode.id),
            commit=False,
        )
        db.commit()
        raise

    segments = build_segments_from_transcript(full_text)
    episode.full_transcript = full_text

    db.query(TranscriptSegment).filter(
        TranscriptSegment.episode_id == episode_id
    ).delete()

    for seg in segments:
        db.add(
            TranscriptSegment(
                episode_id=episode_id,
                start_time=float(seg["start_time"]),
                end_time=float(seg["end_time"]),
                text=str(seg["text"]),
            )
        )
    set_episode_status(db, episode, STATUS_QUEUED, commit=False)
    record_event(
        db,
        "pipeline.transcribed",
        f"Transcript ready: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        meta={"segment_count": len(segments)},
        commit=False,
    )
    db.commit()
    return TranscriptionResult(
        episode_id=episode_id,
        transcript_length=len(full_text),
        segment_count=len(segments),
    )


def _run_transcription(episode: Episode, transcript: Optional[str]) -> str:
    if transcript is not None:
        full_text = transcript.strip()
    else:
        if not episode.audio_url:
            raise ValueError("Episode has no audio_url and no transcript provided")
        import tempfile

        from backend.intelligence_v1.transcribe import transcribe_file

        suffix = ".mp3"
        if "." in episode.audio_url.split("?")[0]:
            suffix = Path(episode.audio_url.split("?")[0]).suffix or suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        prepared_path: Optional[Path] = None
        cleanup_path: Optional[Path] = None
        try:
            _download_audio(episode.audio_url, tmp_path)
            prepared_path, cleanup_path = _maybe_prepare_audio_for_cloud_stt(tmp_path)
            tr = transcribe_file(prepared_path)
            full_text = str(tr.get("transcript") or "").strip()
        finally:
            if cleanup_path is not None:
                try:
                    cleanup_path.unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    if len(full_text) < 40:
        raise ValueError("Transcript too short")
    return full_text
