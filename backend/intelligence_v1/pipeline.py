"""Orchestrator: audio → transcript → metrics → DB → benchmarks → prediction → report."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .analyzer import compute_category_benchmarks
from .categories import normalize_category, resolve_benchmarks
from .db import IntelligenceDB
from .metrics_extractor import extract_metrics
from .predictor import predict_tier
from .report import build_report
from .transcribe import transcribe_file

PathLike = Union[str, Path]


def _tier_enabled() -> bool:
    return os.getenv("SOAPBOXX_ENABLE_TIER", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def process_episode(
    file_or_transcript: PathLike,
    category: str = "general",
    *,
    title: str = "",
    db: Optional[IntelligenceDB] = None,
    skip_transcribe: bool = False,
) -> Dict[str, Any]:
    """
    Run the Phase 1 intelligence loop.

    ``file_or_transcript``: path to audio/video OR raw transcript text if
    ``skip_transcribe=True`` (pass transcript string with skip_transcribe=True).

    Returns final report dict (includes ``episode_id``, ``markdown``, metrics, etc.).
    """
    database = db or IntelligenceDB()
    database.init_schema()
    category = normalize_category(category)

    source_path: Optional[str] = None
    if skip_transcribe:
        transcript = str(file_or_transcript).strip()
        if not title:
            title = "Pasted transcript"
    else:
        path = Path(file_or_transcript)
        if path.is_file():
            tr = transcribe_file(path)
            transcript = tr["transcript"]
            source_path = tr.get("source_path")
            if not title:
                title = path.stem
        else:
            # Treat as transcript string when not a file
            transcript = str(file_or_transcript).strip()
            if not title:
                title = "Imported transcript"

    if len(transcript) < 40:
        raise ValueError("Transcript too short for intelligence pipeline")

    metrics = extract_metrics(transcript)
    episode_id = database.insert_episode(
        title=title or "Untitled",
        category=category,
        transcript=transcript,
        source_path=source_path,
    )
    database.save_metrics(episode_id, metrics)

    computed, sample_size = compute_category_benchmarks(
        category, db=database, persist=True
    )
    benchmarks, benchmark_note = resolve_benchmarks(
        category, computed, sample_size=sample_size
    )

    if _tier_enabled():
        prediction = predict_tier(metrics, benchmarks)
        database.save_prediction(
            episode_id,
            tier=str(prediction["tier"]),
            confidence=float(prediction["confidence"]),
            reasoning=list(prediction.get("reasoning") or []),
        )
    else:
        prediction = {
            "tier": "",
            "confidence": 0.0,
            "reasoning": [],
            "disabled": True,
        }

    report = build_report(
        title=title or "Untitled",
        category=category,
        metrics=metrics,
        benchmarks=benchmarks,
        prediction=prediction,
        episode_id=episode_id,
        benchmark_note=benchmark_note,
        show_tier=_tier_enabled(),
    )
    report["transcript_length"] = len(transcript)
    report["source_path"] = source_path
    return report


def process_transcript_only(
    transcript: str,
    category: str = "general",
    *,
    title: str = "",
    db: Optional[IntelligenceDB] = None,
) -> Dict[str, Any]:
    """Shortcut when audio transcription is already done."""
    return process_episode(
        transcript,
        category,
        title=title,
        db=db,
        skip_transcribe=True,
    )
