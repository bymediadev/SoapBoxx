"""Day 4 — transcription + segments."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.models import Episode, TranscriptSegment
from backend.services.transcription_service import (
    build_segments_from_transcript,
    transcribe_episode,
)
from tests.utils.db_reset import reset_v1_tables

pytestmark = pytest.mark.v1_day4

TRANSCRIPT = Path(__file__).parent / "fixtures" / "sample_transcript.txt"


@pytest.fixture
def v1_db_clean(v1_db_ready):
    from backend.api.deps import get_engine

    reset_v1_tables(get_engine())
    yield


def test_transcription_created(v1_db_clean):
    from backend.api.deps import get_session_factory
    from tests.utils.pipeline import seed_episode_with_transcript

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        ep = db.get(Episode, eid)
        assert ep and ep.full_transcript and len(ep.full_transcript) > 100
    finally:
        db.close()


def test_segments_exist(v1_db_clean):
    from backend.api.deps import get_session_factory
    from tests.utils.pipeline import seed_episode_with_transcript

    db = get_session_factory()()
    try:
        eid = seed_episode_with_transcript(db)
        n = db.scalar(
            select(func.count())
            .select_from(TranscriptSegment)
            .where(TranscriptSegment.episode_id == eid)
        )
        assert n and n > 0
    finally:
        db.close()


def test_transcript_not_empty(v1_db_clean):
    text = TRANSCRIPT.read_text(encoding="utf-8")
    segs = build_segments_from_transcript(text)
    assert len(text) > 100
    assert len(segs) > 0


def test_transcribe_api(v1_client, v1_db_clean):
    from backend.api.deps import get_session_factory
    from backend.services.rss_service import ingest_rss_xml

    db = get_session_factory()()
    try:
        xml = (Path(__file__).parent / "fixtures" / "sample_rss.xml").read_text(
            encoding="utf-8"
        )
        ing = ingest_rss_xml(db, xml, rss_url="https://example.com/api-feed")
        eid = ing.episode_ids[0]
    finally:
        db.close()

    r = v1_client.post(
        f"/episodes/{eid}/transcribe",
        json={"transcript": TRANSCRIPT.read_text(encoding="utf-8")},
    )
    assert r.status_code == 200
    assert r.json()["segment_count"] > 0


def test_transcribe_rejects_oversize_remote_audio_before_download(v1_db_clean, monkeypatch):
    from backend.api.deps import get_session_factory
    from backend.services.rss_service import ingest_rss_xml

    db = get_session_factory()()
    try:
        xml = (Path(__file__).parent / "fixtures" / "sample_rss.xml").read_text(
            encoding="utf-8"
        )
        ing = ingest_rss_xml(db, xml, rss_url="https://example.com/api-feed")
        eid = ing.episode_ids[0]
        ep = db.get(Episode, eid)
        assert ep is not None
        ep.audio_url = "https://example.com/audio.mp3?size=30000000"
        db.commit()

        def _unexpected_download(*args, **kwargs):
            raise AssertionError("oversize audio should be rejected before download")

        monkeypatch.setattr(
            "backend.services.transcription_service._download_audio",
            _unexpected_download,
        )

        with pytest.raises(ValueError, match="cloud STT limit"):
            transcribe_episode(db, eid)

        db.refresh(ep)
        assert ep.pipeline_status == "failed"
        assert ep.pipeline_error
        assert "cloud STT limit" in ep.pipeline_error
    finally:
        db.close()
