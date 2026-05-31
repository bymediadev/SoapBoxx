"""Guards against Railway 502 causes on POST /episodes/{id}/process."""

from __future__ import annotations

from backend.api.config import Settings
from backend.models import Episode
from backend.services.episode_pipeline_service import episode_needs_stt


def test_auto_audio_motion_default_off() -> None:
    assert Settings().auto_audio_motion_on_process is False


def test_episode_needs_stt_when_no_transcript() -> None:
    ep = Episode(id=1, podcast_id=1, title="t", full_transcript="")
    assert episode_needs_stt(ep) is True


def test_episode_needs_stt_skips_when_transcript_exists() -> None:
    ep = Episode(id=1, podcast_id=1, title="t", full_transcript="hello world")
    assert episode_needs_stt(ep) is False
    assert episode_needs_stt(ep, force_retranscribe=True) is True
