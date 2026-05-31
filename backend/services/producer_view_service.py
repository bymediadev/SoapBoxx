"""Layer 3 — fuse transcript intelligence + audio events at output only."""

from __future__ import annotations

from typing import List, Optional


def _event_type(event: dict) -> str:
    return str(event.get("type") or event.get("signal") or "")


def _parse_mmss(label: str) -> Optional[float]:
    label = (label or "").strip().split("–")[0].split("-")[0].strip()
    if ":" not in label:
        return None
    parts = label.split(":")
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return None
    return None


def _event_seconds(event: dict) -> Optional[float]:
    if event.get("timestamp") is not None:
        return float(event["timestamp"])
    if event.get("start_seconds") is not None:
        return float(event["start_seconds"])
    return _parse_mmss(str(event.get("time_label") or ""))


def _align_fusion_notes(
    *,
    narrative_engine: Optional[dict],
    motion_events: List[dict],
) -> List[str]:
    """Moment-level overlay: when meaning shift and delivery shift land near each other."""
    notes: List[str] = []
    timeline = (narrative_engine or {}).get("timeline") or []
    if not timeline or not motion_events:
        return notes

    for beat in timeline[:8]:
        beat_t = _parse_mmss(str(beat.get("time_label") or ""))
        if beat_t is None:
            continue
        nearby = [
            e
            for e in motion_events
            if _event_seconds(e) is not None and abs(_event_seconds(e) - beat_t) <= 45.0
        ]
        if not nearby:
            continue
        kinds = sorted({_event_type(e) for e in nearby if _event_type(e)})
        if kinds:
            notes.append(
                f"Overlay @ {beat.get('time_label')}: narrative beat "
                f"\"{beat.get('label', '')}\" near audio {', '.join(kinds)}."
            )
    return notes[:3]


def build_producer_view(
    *,
    structural_identity: List[str],
    leverage_points: List[str],
    narrative_engine: Optional[dict],
    producer_notes: Optional[dict],
    audio_motion: Optional[dict],
    transcript_limitations: Optional[List[str]] = None,
) -> dict:
    """
    Final producer view: screenplay (transcript) + camera movement (audio events).
    Transcript fields pass through unchanged; audio is additive event stream.
    """
    layers = ["transcript"]
    motion_events: List[dict] = []
    motion_notes: List[str] = []

    if audio_motion and audio_motion.get("events"):
        layers.append("audio")
        motion_events = list(audio_motion["events"])
        motion_notes.append(
            f"Audio event stream: {len(motion_events)} discrete delivery moment(s) "
            "(energy-based motion only — not pitch, tone, or meaning)."
        )

    fusion_notes: List[str] = _align_fusion_notes(
        narrative_engine=narrative_engine,
        motion_events=motion_events,
    )
    if narrative_engine and motion_events and not fusion_notes:
        fusion_notes.append(
            "Overlay: compare narrative timeline beats with audio events on replay — "
            "linguistic pivots may not coincide with felt delivery shifts."
        )
    if producer_notes and motion_events:
        drag_flags = [
            f for f in (producer_notes.get("edit_flags") or []) if "drag" in f.lower()
        ]
        silence_events = [e for e in motion_events if _event_type(e) == "silence_cluster"]
        if drag_flags and silence_events:
            fusion_notes.append(
                "Overlay: text flagged potential drag near silence cluster event(s) — verify on listen."
            )

    return {
        "layers": layers,
        "structural_identity": list(structural_identity),
        "leverage_points": list(leverage_points),
        "motion_track": motion_events,
        "motion_notes": motion_notes,
        "fusion_notes": fusion_notes[:3],
        "transcript_limitations": list(transcript_limitations or []),
        "audio_available": "audio" in layers,
    }
