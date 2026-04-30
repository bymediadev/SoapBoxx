"""CLI guardrails for scripts/episode_intake.py (no network, no transcription)."""

import subprocess
import sys
from pathlib import Path


def test_intake_rejects_multiple_input_sources():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "episode_intake.py"
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "--transcript",
            "sample_transcript.txt",
            "--audio",
            "nope.wav",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 1
    assert "exactly one" in (cp.stderr or "").lower()


def test_intake_rejects_youtube_asr_without_url():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "episode_intake.py"
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "--transcript",
            "sample_transcript.txt",
            "--youtube-transcript",
            "asr",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 1
    assert "youtube-transcript" in (cp.stderr or "").lower()


def test_intake_rejects_youtube_auto_without_url():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "episode_intake.py"
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "--transcript",
            "sample_transcript.txt",
            "--youtube-transcript",
            "auto",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 1
    assert "youtube-transcript" in (cp.stderr or "").lower()


def test_intake_rejects_zero_input_sources():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "episode_intake.py"
    cp = subprocess.run(
        [sys.executable, str(script), "--title", "Only title"],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 1


def test_intake_rejects_unparseable_youtube_url_without_traceback():
    """Placeholder v= ids must fail fast before any network fetch."""
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "episode_intake.py"
    cp = subprocess.run(
        [
            sys.executable,
            str(script),
            "--url",
            "https://www.youtube.com/watch?v=VIDEO_ID",
            "--title",
            "t",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 1
    err = (cp.stderr or "") + (cp.stdout or "")
    assert "Invalid YouTube URL" in err
    assert "Traceback" not in err
