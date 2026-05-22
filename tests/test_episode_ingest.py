"""Episode ingest framework."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from backend.episode_ingest import ingest_from_text, ingest_from_transcript_file
from backend.episode_ingest.youtube_source import fetch_youtube_episode


SAMPLE = """
Host: Why did the airline fail?
Guest: Unit economics broke when fuel spiked.
Host: What was the first sign?
Guest: Mass cancellations in 2022.
""" * 3


def test_ingest_from_text():
    r = ingest_from_text(SAMPLE, title="Test Show")
    assert len(r.transcript.split()) > 20
    assert r.source_type == "paste"


def test_ingest_transcript_file():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "ep.txt"
        p.write_text(SAMPLE, encoding="utf-8")
        r = ingest_from_transcript_file(p)
        assert r.source_type == "transcript_file"
        assert "airline" in r.transcript.lower()


def test_youtube_captions_path():
    with tempfile.TemporaryDirectory() as td:
        vtt = Path(td) / "abc12345678.en.vtt"
        vtt.write_text(
            "WEBVTT\n\n00:00:01.000\nSpirit Airlines filed for bankruptcy yesterday.\n"
            "00:00:05.000\nFares were too low to cover fuel costs in the crisis.\n"
            "00:00:12.000\nThe ultra low cost model stopped working for investors.\n"
            "00:00:20.000\nCrew shortages and cancellations made the brand toxic.\n",
            encoding="utf-8",
        )

        with patch(
            "backend.youtube_subtitles.parse_youtube_video_id",
            return_value="abc12345678",
        ), patch(
            "backend.youtube_subtitles.download_youtube_en_vtt",
            return_value=vtt,
        ), patch(
            "backend.episode_ingest.youtube_source._fetch_metadata",
            return_value={"title": "Spirit Airlines", "creator": "Ch", "genre": "News"},
        ), patch(
            "backend.youtube_subtitles.download_youtube_best_audio",
            return_value=None,
        ):
            r = fetch_youtube_episode(
                "https://www.youtube.com/watch?v=abc12345678",
                transcript_mode="captions",
                cache_dir=Path(td),
            )
        assert r.source_type == "youtube"
        assert "Spirit" in r.transcript or "bankruptcy" in r.transcript.lower()
