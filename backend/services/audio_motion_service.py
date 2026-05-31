"""Persist and load Layer 2 audio motion (optional, parallel to features)."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.models import Episode, EpisodeAudioMotion
from backend.services.audio_motion_extractor import (
    EXTRACTOR_VERSION,
    AudioMotionEvent,
    extract_motion_from_audio_path,
    motion_track_to_dict,
)
from backend.services.transcription_service import _download_audio


@dataclass
class AudioMotionResult:
    episode_id: int
    events: List[AudioMotionEvent]


def load_audio_motion(db: Session, episode_id: int) -> Optional[dict]:
    row = db.get(EpisodeAudioMotion, episode_id)
    if not row or not row.events_json:
        return None
    try:
        data = json.loads(row.events_json)
    except json.JSONDecodeError:
        return None
    data["extractor_version"] = row.extractor_version
    return data


def run_audio_motion_extraction(db: Session, episode_id: int) -> AudioMotionResult:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    if not episode.audio_url:
        raise ValueError("Episode has no audio_url — cannot extract audio motion")

    suffix = ".mp3"
    if "." in episode.audio_url.split("?")[0]:
        suffix = Path(episode.audio_url.split("?")[0]).suffix or suffix

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / f"episode_{episode_id}{suffix}"
        _download_audio(episode.audio_url, tmp_path)
        events = extract_motion_from_audio_path(str(tmp_path))

    payload = motion_track_to_dict(events, episode_id=episode_id)
    row = db.get(EpisodeAudioMotion, episode_id)
    if not row:
        row = EpisodeAudioMotion(episode_id=episode_id)
        db.add(row)
    row.extractor_version = EXTRACTOR_VERSION
    row.events_json = json.dumps(payload)
    db.commit()
    return AudioMotionResult(episode_id=episode_id, events=events)
