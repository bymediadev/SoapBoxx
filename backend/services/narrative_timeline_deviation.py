"""Layer C — compare episode narrative shape to feed baseline (deviation, not trend)."""

from __future__ import annotations

from typing import List, Optional, Sequence

from backend.models import EpisodeFeatures
from backend.services.library_benchmarks import LibraryBenchmarks
from backend.services.narrative_timeline_service import (
    NarrativeEngineMap,
    build_narrative_engine_map,
)


def _primary_close_ratio(map_: NarrativeEngineMap, runtime: float) -> Optional[float]:
    if runtime <= 0 or not map_.open_loops:
        return None
    primary = map_.open_loops[0]
    if not primary.closed_at:
        return None
    return primary.closed_at / runtime


def build_narrative_deviation_notes(
    engine: NarrativeEngineMap,
    *,
    runtime_seconds: float,
    show: LibraryBenchmarks,
    show_transcripts: Sequence[tuple[str, Optional[list]]],
) -> List[str]:
    """
    Shape delta vs feed: when did this episode close its main thread vs others?
    Requires other measured episodes on the same feed with transcripts.
    """
    if show.n_measured < 2 or not show_transcripts:
        return []

    this_ratio = _primary_close_ratio(engine, runtime_seconds)
    if this_ratio is None:
        return [
            "Main thread still open at episode end — no closure timing to compare with this feed yet."
        ]

    peer_ratios: List[float] = []
    for text, segs in show_transcripts:
        if not (text or "").strip():
            continue
        peer = build_narrative_engine_map(text, segs)
        if not peer.open_loops:
            continue
        rt = runtime_seconds
        if segs:
            try:
                rt = float(segs[-1].get("end") or runtime_seconds)
            except (TypeError, ValueError, IndexError):
                pass
        r = _primary_close_ratio(peer, rt)
        if r is not None:
            peer_ratios.append(r)

    if len(peer_ratios) < 2:
        return []

    earlier = sum(1 for r in peer_ratios if this_ratio < r - 0.05)
    later = sum(1 for r in peer_ratios if this_ratio > r + 0.05)
    n = len(peer_ratios)

    notes: List[str] = []
    if earlier >= max(2, n // 2):
        notes.append(
            f"Main thread closure lands earlier in the runtime than most other measured "
            f"episodes on this feed ({earlier} of {n} close later)"
        )
    elif later >= max(2, n // 2):
        notes.append(
            f"Main thread stays unresolved longer than most other measured episodes "
            f"on this feed ({later} of {n} close earlier)"
        )
    else:
        notes.append(
            f"Main thread closure timing sits near the middle of this feed's measured episodes"
        )

    return notes[:2]
