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
    normalize_stt_segments,
    segments_for_transcript,
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


def test_unstructured_blob_is_chunked():
    # Cloud STT returns one unpunctuated/unlabeled blob; it must still split into
    # multiple time-estimated segments instead of one giant block.
    blob = " ".join(
        f"This is sentence number {i} about a topic we discuss in some depth."
        for i in range(60)
    )
    segs = build_segments_from_transcript(blob)
    assert len(segs) > 1
    # Synthetic timestamps are ordered and non-overlapping.
    for prev, nxt in zip(segs, segs[1:]):
        assert prev["end_time"] <= nxt["start_time"] + 1e-6
        assert nxt["end_time"] >= nxt["start_time"]


def test_blob_without_sentence_punctuation_uses_word_windows():
    blob = " ".join(f"word{i}" for i in range(300))
    segs = build_segments_from_transcript(blob)
    assert len(segs) > 1


def test_normalize_stt_segments_accepts_whisper_keys():
    raw = [
        {"start": 0.0, "end": 2.5, "text": " Hello there"},
        {"start_time": 2.5, "end_time": 5.0, "text": "General Kenobi"},
    ]
    segs = normalize_stt_segments(raw)
    assert len(segs) == 2
    assert segs[0]["start_time"] == 0.0
    assert segs[0]["end_time"] == 2.5
    assert segs[0]["text"] == "Hello there"
    assert segs[1]["text"] == "General Kenobi"


def test_segments_for_transcript_prefers_stt_timestamps():
    stt = [{"start": 0.0, "end": 12.0, "text": "Opening monologue."}]
    segs = segments_for_transcript("Opening monologue.", stt)
    assert len(segs) == 1
    assert segs[0]["end_time"] == 12.0


def test_extract_transcript_payload_parses_verbose_json_dict():
    from backend.transcriber import _extract_transcript_payload

    payload = {
        "text": " Hello world",
        "segments": [{"start": 0.0, "end": 1.2, "text": " Hello world"}],
    }
    text, segs = _extract_transcript_payload(payload)
    assert text == "Hello world"
    assert len(segs) == 1
    assert segs[0]["start_time"] == 0.0


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
