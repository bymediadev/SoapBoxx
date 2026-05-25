"""Day 4 — transcription + segments."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select

from backend.models import Episode, TranscriptSegment
from backend.services.transcription_service import (
    _maybe_prepare_audio_for_cloud_stt,
    _size_hint_from_url,
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


def test_size_hint_from_url_reads_query_param():
    assert _size_hint_from_url("https://example.com/audio.mp3?size=30000000") == 30000000
    assert _size_hint_from_url("https://example.com/audio.mp3") is None


def test_prepare_audio_for_cloud_stt_compresses_when_near_limit(tmp_path, monkeypatch):
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x" * 90)

    monkeypatch.setenv("SOAPBOXX_STT_MAX_BYTES", "100")
    monkeypatch.setenv("SOAPBOXX_STT_SOFT_BYTES", "80")

    def _fake_compress(src, dst, *, bitrate):
        assert src == source
        dst.write_bytes(b"y" * 60)

    monkeypatch.setattr(
        "backend.services.transcription_service._compress_audio_file_for_stt",
        _fake_compress,
    )

    prepared, cleanup = _maybe_prepare_audio_for_cloud_stt(source)
    assert prepared != source
    assert cleanup == prepared
    assert prepared.read_bytes() == b"y" * 60


def test_prepare_audio_for_cloud_stt_raises_when_compression_still_too_large(
    tmp_path, monkeypatch
):
    source = tmp_path / "source.mp3"
    source.write_bytes(b"x" * 110)

    monkeypatch.setenv("SOAPBOXX_STT_MAX_BYTES", "100")
    monkeypatch.setenv("SOAPBOXX_STT_SOFT_BYTES", "80")

    def _fake_compress(src, dst, *, bitrate):
        dst.write_bytes(b"z" * 105)

    monkeypatch.setattr(
        "backend.services.transcription_service._compress_audio_file_for_stt",
        _fake_compress,
    )

    with pytest.raises(ValueError, match="still .* after compression"):
        _maybe_prepare_audio_for_cloud_stt(source)
