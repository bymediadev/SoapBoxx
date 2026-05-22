"""V1 feature extraction — exactly 7 metrics (Day 5)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.features.rule_based import (
    _SPEAKER_LINE,
    _TOPIC_SHIFT_MARKERS,
    _words,
    cta_present,
    extract_rule_features,
    hook_time_seconds,
    question_count,
    topic_changes,
)
from backend.models import Episode, EpisodeFeatures, TranscriptSegment
from backend.services.pipeline_status import (
    STATUS_FAILED,
    STATUS_MEASURED,
    record_event,
    set_episode_status,
)

_WPS = 2.5


@dataclass
class FeatureResult:
    episode_id: int
    features: Dict[str, Any]


def _estimate_seconds(word_count: int) -> float:
    return round(max(0.0, word_count / _WPS), 2)


def intro_length_seconds(text: str, segments: Optional[List[Dict[str, Any]]] = None) -> float:
    """Seconds until guest voice or first topic shift (opening block)."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    intro_words = 0
    for ln in lines:
        m = _SPEAKER_LINE.match(ln)
        if m:
            if m.group(1).lower().startswith("guest"):
                break
            intro_words += _words(_SPEAKER_LINE.sub("", ln))
            continue
        if _TOPIC_SHIFT_MARKERS.search(ln) and intro_words > 30:
            break
        intro_words += _words(ln)
    if intro_words < 10:
        intro_words = min(120, _words(text) // 8)
    return _estimate_seconds(intro_words)


def extract_v1_features(
    transcript: str,
    segments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Seven V1 metrics for episode_features table."""
    base = extract_rule_features(transcript, segments)
    guest_pct = float(base.get("guest_talk_percentage") or 50.0)
    host_pct = float(base.get("host_talk_percentage") or 50.0)
    total = guest_pct + host_pct
    ratio = round(guest_pct / total, 4) if total > 0 else 0.5

    return {
        "hook_length_seconds": float(base.get("hook_time_seconds") or 0),
        "intro_length_seconds": intro_length_seconds(transcript, segments),
        "question_count": int(base.get("question_count") or 0),
        "speaking_turns": int(base.get("speaking_turns") or 0),
        "host_guest_ratio": ratio,
        "topic_shift_count": int(base.get("topic_changes") or 0),
        "cta_present": bool(base.get("cta_present")),
    }


def run_feature_extraction(db: Session, episode_id: int) -> FeatureResult:
    episode = db.get(Episode, episode_id)
    if not episode:
        raise ValueError(f"Episode {episode_id} not found")
    try:
        return _run_feature_extraction(db, episode, episode_id)
    except Exception as exc:
        set_episode_status(db, episode, STATUS_FAILED, error=str(exc), commit=False)
        record_event(
            db,
            "pipeline.failed",
            f"Feature extraction failed: {exc}",
            podcast_id=int(episode.podcast_id),
            episode_id=int(episode.id),
            commit=False,
        )
        db.commit()
        raise


def _run_feature_extraction(db: Session, episode: Episode, episode_id: int) -> FeatureResult:
    text = (episode.full_transcript or "").strip()
    if len(text) < 40:
        raise ValueError("Episode has no transcript; run transcription first")

    seg_rows = (
        db.query(TranscriptSegment)
        .filter(TranscriptSegment.episode_id == episode_id)
        .order_by(TranscriptSegment.start_time)
        .all()
    )
    segments = [
        {
            "start": r.start_time,
            "end": r.end_time,
            "text": r.text,
        }
        for r in seg_rows
    ]

    metrics = extract_v1_features(text, segments or None)
    row = db.get(EpisodeFeatures, episode_id)
    if not row:
        row = EpisodeFeatures(episode_id=episode_id)
        db.add(row)

    row.hook_length_seconds = metrics["hook_length_seconds"]
    row.intro_length_seconds = metrics["intro_length_seconds"]
    row.question_count = metrics["question_count"]
    row.speaking_turns = metrics["speaking_turns"]
    row.host_guest_ratio = metrics["host_guest_ratio"]
    row.topic_shift_count = metrics["topic_shift_count"]
    row.cta_present = metrics["cta_present"]
    set_episode_status(db, episode, STATUS_MEASURED, commit=False)
    record_event(
        db,
        "pipeline.measured",
        f"Structure measured: {episode.title}",
        podcast_id=int(episode.podcast_id),
        episode_id=int(episode.id),
        meta=metrics,
        commit=False,
    )
    db.commit()
    return FeatureResult(episode_id=episode_id, features=metrics)
