"""Layer 2 — discrete audio events from waveform (parallel to transcript intelligence).

Waveform → RMS windows → timestamped events. Not meaning, pitch, or prosody.
Optional dependency: pydub (already in requirements-v1-api.txt).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence

EXTRACTOR_VERSION = "1.1.0"

AudioEventType = Literal["energy_spike", "energy_drop", "silence_cluster", "pace_shift"]

_WINDOW_S = 2.0
_STEP_S = 1.0
_BASELINE_WINDOWS = 10
_SPIKE_STD_MULT = 1.75
_DROP_STD_MULT = 1.75
_PACE_DELTA_DB = 5.0
_MIN_SILENCE_S = 1.5
_MAX_EVENTS = 24
_MERGE_GAP_S = 3.0

_EVENT_LABELS: dict[str, str] = {
    "energy_spike": "Energy spike — sudden loudness increase",
    "energy_drop": "Energy drop — softening or transition",
    "silence_cluster": "Silence cluster — pause or cut space",
    "pace_shift": "Pace shift — sustained delivery change",
}


@dataclass
class AudioEvent:
    """Discrete producer moment on the delivery timeline."""

    timestamp: float
    type: AudioEventType
    intensity: float
    window_start: float
    window_end: float

    def to_dict(self) -> dict:
        return {
            "timestamp": round(self.timestamp, 1),
            "type": self.type,
            "intensity": round(max(0.0, min(1.0, self.intensity)), 2),
            "window_start": round(self.window_start, 1),
            "window_end": round(self.window_end, 1),
            "time_label": _fmt(self.timestamp),
            "label": _EVENT_LABELS.get(self.type, self.type),
        }


# Backward-compatible alias for callers importing AudioMotionEvent
AudioMotionEvent = AudioEvent


def _fmt(seconds: float) -> str:
    s = max(0.0, float(seconds))
    m = int(s // 60)
    rem = int(round(s % 60))
    return f"{m}:{rem:02d}"


def _window_rms_db(samples: Sequence[float]) -> float:
    if not samples:
        return -60.0
    mean_sq = sum(x * x for x in samples) / len(samples)
    rms = math.sqrt(max(mean_sq, 1e-12))
    return 20.0 * math.log10(rms) if rms > 0 else -60.0


def _clamp01(value: float, *, scale: float) -> float:
    if scale <= 0:
        return 0.5
    return max(0.0, min(1.0, value / scale))


def _compute_rms_windows(
    samples: Sequence[float],
    *,
    sample_rate: int,
    window_s: float = _WINDOW_S,
    step_s: float = _STEP_S,
) -> List[tuple[float, float, float]]:
    win = max(1, int(sample_rate * window_s))
    step = max(1, int(sample_rate * step_s))
    windows: List[tuple[float, float, float]] = []
    for i in range(0, len(samples) - win // 4, step):
        chunk = samples[i : i + win]
        if len(chunk) < win // 4:
            continue
        t0 = i / sample_rate
        t1 = (i + len(chunk)) / sample_rate
        windows.append((t0, t1, _window_rms_db(chunk)))
    return windows


def _rolling_baseline(windows: List[tuple[float, float, float]], end_idx: int) -> Optional[float]:
    start = max(0, end_idx - _BASELINE_WINDOWS)
    if end_idx - start < 3:
        return None
    chunk = [w[2] for w in windows[start:end_idx]]
    return sum(chunk) / len(chunk)


def _rolling_std(windows: List[tuple[float, float, float]], end_idx: int) -> float:
    start = max(0, end_idx - _BASELINE_WINDOWS)
    chunk = [w[2] for w in windows[start:end_idx]]
    if len(chunk) < 2:
        return 4.0
    mean = sum(chunk) / len(chunk)
    var = sum((x - mean) ** 2 for x in chunk) / len(chunk)
    return max(var**0.5, 2.0)


def extract_motion_from_samples(
    samples: Sequence[float],
    *,
    sample_rate: int = 16000,
) -> List[AudioEvent]:
    """
    Step 1: RMS windowing. Step 2: discrete event extraction.
    Testable without audio files.
    """
    if not samples or sample_rate <= 0:
        return []

    windows = _compute_rms_windows(samples, sample_rate=sample_rate)
    if len(windows) < 4:
        return []

    all_levels = [w[2] for w in windows]
    silence_threshold = sorted(all_levels)[max(0, int(len(all_levels) * 0.10) - 1)]
    silence_threshold = min(silence_threshold, -42.0)

    events: List[AudioEvent] = []

    # Silence clusters — span of contiguous low-RMS windows
    silence_start: Optional[float] = None
    silence_end: Optional[float] = None
    for t0, t1, db in windows:
        if db <= silence_threshold:
            if silence_start is None:
                silence_start = t0
            silence_end = t1
        elif silence_start is not None and silence_end is not None:
            if silence_end - silence_start >= _MIN_SILENCE_S:
                events.append(
                    AudioEvent(
                        timestamp=silence_start,
                        type="silence_cluster",
                        intensity=_clamp01(silence_end - silence_start, scale=4.0),
                        window_start=silence_start,
                        window_end=silence_end,
                    )
                )
            silence_start = None
            silence_end = None
    if silence_start is not None and silence_end is not None:
        if silence_end - silence_start >= _MIN_SILENCE_S:
            events.append(
                AudioEvent(
                    timestamp=silence_start,
                    type="silence_cluster",
                    intensity=_clamp01(silence_end - silence_start, scale=4.0),
                    window_start=silence_start,
                    window_end=silence_end,
                )
            )

    # Spike / drop / pace per window
    for i in range(2, len(windows)):
        t0, t1, cur = windows[i]
        baseline = _rolling_baseline(windows, i)
        if baseline is None:
            continue
        std = _rolling_std(windows, i)
        spike_thresh = baseline + _SPIKE_STD_MULT * std
        drop_thresh = baseline - _DROP_STD_MULT * std

        if cur >= spike_thresh:
            events.append(
                AudioEvent(
                    timestamp=t0,
                    type="energy_spike",
                    intensity=_clamp01(cur - baseline, scale=std * 2.5),
                    window_start=t0,
                    window_end=t1,
                )
            )
        elif cur <= drop_thresh:
            events.append(
                AudioEvent(
                    timestamp=t0,
                    type="energy_drop",
                    intensity=_clamp01(baseline - cur, scale=std * 2.5),
                    window_start=t0,
                    window_end=t1,
                )
            )

        # Pace shift: 10s mean vs prior 10s mean
        lookback = max(1, int(10.0 / _STEP_S))
        if i >= lookback * 2:
            recent = [w[2] for w in windows[i - lookback : i]]
            prior = [w[2] for w in windows[i - lookback * 2 : i - lookback]]
            recent_mean = sum(recent) / len(recent)
            prior_mean = sum(prior) / len(prior)
            delta = abs(recent_mean - prior_mean)
            if delta >= _PACE_DELTA_DB:
                events.append(
                    AudioEvent(
                        timestamp=t0,
                        type="pace_shift",
                        intensity=_clamp01(delta, scale=_PACE_DELTA_DB * 2),
                        window_start=windows[i - lookback][0],
                        window_end=t1,
                    )
                )

    events.sort(key=lambda e: e.timestamp)
    return _dedupe_events(events)[:_MAX_EVENTS]


def _dedupe_events(events: List[AudioEvent]) -> List[AudioEvent]:
    out: List[AudioEvent] = []
    for ev in events:
        if (
            out
            and out[-1].type == ev.type
            and ev.timestamp - out[-1].timestamp < _MERGE_GAP_S
        ):
            prev = out[-1]
            out[-1] = AudioEvent(
                timestamp=prev.timestamp,
                type=prev.type,
                intensity=max(prev.intensity, ev.intensity),
                window_start=min(prev.window_start, ev.window_start),
                window_end=max(prev.window_end, ev.window_end),
            )
        else:
            out.append(ev)
    return out


def extract_motion_from_audio_path(path: str) -> List[AudioEvent]:
    """Load audio file and extract discrete delivery events (Layer 2 only)."""
    try:
        from pydub import AudioSegment
    except ImportError:
        return []

    seg = AudioSegment.from_file(path)
    seg = seg.set_channels(1).set_frame_rate(16000)
    samples = [float(s) / 32768.0 for s in seg.get_array_of_samples()]
    return extract_motion_from_samples(samples, sample_rate=16000)


def motion_track_to_dict(events: Sequence[AudioEvent], *, episode_id: Optional[int] = None) -> dict:
    payload: dict = {
        "extractor_version": EXTRACTOR_VERSION,
        "events": [e.to_dict() for e in events],
        "n_events": len(events),
    }
    if episode_id is not None:
        payload["episode_id"] = episode_id
    return payload
