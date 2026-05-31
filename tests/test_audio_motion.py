"""Layer 2 audio events — synthetic PCM tests (no file download)."""

from __future__ import annotations

import math

from backend.services.audio_motion_extractor import (
    EXTRACTOR_VERSION,
    extract_motion_from_samples,
    motion_track_to_dict,
)
from backend.services.producer_view_service import build_producer_view

ALLOWED_TYPES = {"energy_spike", "energy_drop", "silence_cluster", "pace_shift"}


def _tone(freq: float, duration_s: float, sr: int = 16000, amp: float = 0.3) -> list[float]:
    n = int(duration_s * sr)
    return [amp * math.sin(2 * math.pi * freq * i / sr) for i in range(n)]


def _silence(duration_s: float, sr: int = 16000) -> list[float]:
    return [0.0] * int(duration_s * sr)


def test_events_are_discrete_with_schema_fields():
    samples = _tone(440, 6.0, amp=0.5) + _tone(880, 6.0, amp=0.15)
    events = extract_motion_from_samples(samples)
    assert events
    for ev in events:
        assert ev.type in ALLOWED_TYPES
        assert 0.0 <= ev.intensity <= 1.0
        d = ev.to_dict()
        assert "timestamp" in d
        assert "type" in d
        assert "intensity" in d
        assert "window_start" in d
        assert "window_end" in d


def test_silence_cluster_detected():
    loud = _tone(440, 4.0)
    quiet = _silence(2.5)
    tail = _tone(440, 4.0)
    samples = loud + quiet + tail
    events = extract_motion_from_samples(samples)
    assert any(e.type == "silence_cluster" for e in events)


def test_motion_track_output_flat_event_list():
    events = extract_motion_from_samples(_tone(220, 8.0))
    payload = motion_track_to_dict(events, episode_id=5)
    assert payload["extractor_version"] == EXTRACTOR_VERSION
    assert payload["episode_id"] == 5
    assert isinstance(payload["events"], list)


def test_producer_view_transcript_only_without_audio():
    view = build_producer_view(
        structural_identity=["Diary / explainer"],
        leverage_points=["Named band A"],
        narrative_engine={"timeline": []},
        producer_notes={"edit_flags": []},
        audio_motion=None,
    )
    assert view["layers"] == ["transcript"]
    assert view["audio_available"] is False
    assert view["motion_track"] == []


def test_producer_view_fuses_nearby_narrative_and_audio():
    audio = {
        "events": [
            {
                "timestamp": 250.0,
                "type": "energy_spike",
                "intensity": 0.78,
                "time_label": "4:10",
                "label": "Energy spike",
            }
        ]
    }
    view = build_producer_view(
        structural_identity=["Diary / explainer"],
        leverage_points=[],
        narrative_engine={
            "timeline": [{"time_label": "4:08", "label": "Loop opens"}]
        },
        producer_notes={"edit_flags": []},
        audio_motion=audio,
    )
    assert view["audio_available"] is True
    assert len(view["motion_track"]) == 1
    assert view["fusion_notes"]
    assert "energy_spike" in view["fusion_notes"][0]
