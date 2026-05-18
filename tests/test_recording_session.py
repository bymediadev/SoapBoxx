"""Tests for RecordingSession episode shape."""

from __future__ import annotations

from datetime import datetime

from backend.soapboxx_core import RecordingSession


def test_recording_session_to_dict():
    sess = RecordingSession(
        session_id="session_1",
        start_time=datetime(2026, 5, 18, 12, 0, 0),
        transcript="Hello world.",
        audio_path="/tmp/ep.wav",
        metadata={"guest": "Ada"},
    )
    d = sess.to_dict()
    assert d["session_id"] == "session_1"
    assert d["transcript"] == "Hello world."
    assert d["audio_path"] == "/tmp/ep.wav"
    assert d["metadata"]["guest"] == "Ada"
    assert "audio_chunks" not in d
