"""Locked measurement semantics — feature, extraction, aggregation (V1).

Bump only with explicit contract revision:
- FEATURE_SCHEMA_VERSION: meaning of the seven metrics changes
- EXTRACTION_VERSION: rule-based detection logic changes
- AGGREGATION_VERSION: band/benchmark/comparison logic changes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from backend.models import EpisodeFeatures

# Layer (A): what question / turn / transition marker mean.
FEATURE_SCHEMA_VERSION = "v1"

# Layer (B): rule_based + feature_service detection logic.
EXTRACTION_VERSION = "1.0.0"

# Layer (C): feed_leverage, library_benchmarks, show_variance, producer_notes.
AGGREGATION_VERSION = "1.2.0"

# Pre-versioning rows (migration backfill target).
LEGACY_STAMP = ("legacy", "legacy", "legacy")


@dataclass(frozen=True)
class MeasurementStamp:
    feature_schema_version: str
    extraction_version: str
    aggregation_version: str

    def as_tuple(self) -> Tuple[str, str, str]:
        return (
            self.feature_schema_version,
            self.extraction_version,
            self.aggregation_version,
        )


CURRENT_STAMP = MeasurementStamp(
    feature_schema_version=FEATURE_SCHEMA_VERSION,
    extraction_version=EXTRACTION_VERSION,
    aggregation_version=AGGREGATION_VERSION,
)


def stamp_from_row(row: EpisodeFeatures) -> Optional[MeasurementStamp]:
    fs = getattr(row, "feature_schema_version", None)
    ex = getattr(row, "extraction_version", None)
    ag = getattr(row, "aggregation_version", None)
    if not fs or not ex or not ag:
        return None
    if (fs, ex, ag) == LEGACY_STAMP:
        return None
    return MeasurementStamp(
        feature_schema_version=str(fs),
        extraction_version=str(ex),
        aggregation_version=str(ag),
    )


def stamp_for_row(row: Optional[EpisodeFeatures]) -> MeasurementStamp:
    if row is None:
        return CURRENT_STAMP
    found = stamp_from_row(row)
    return found if found is not None else CURRENT_STAMP


def stamps_compatible(anchor: MeasurementStamp, other: MeasurementStamp) -> bool:
    return anchor.as_tuple() == other.as_tuple()


def filter_comparable_rows(
    rows: Sequence[EpisodeFeatures],
    anchor: MeasurementStamp,
) -> Tuple[list[EpisodeFeatures], int]:
    """Keep only rows measured under the same three-layer stamp as anchor."""
    kept: list[EpisodeFeatures] = []
    excluded = 0
    for row in rows:
        other = stamp_from_row(row)
        if other is None or not stamps_compatible(anchor, other):
            excluded += 1
            continue
        kept.append(row)
    return kept, excluded


def cohort_note(excluded: int) -> Optional[str]:
    if excluded <= 0:
        return None
    word = "episode" if excluded == 1 else "episodes"
    return (
        f"{excluded} measured {word} excluded from comparison — different "
        f"measurement schema (feature, extraction, or aggregation version)."
    )


def stamp_dict(stamp: MeasurementStamp) -> dict:
    return {
        "feature_schema_version": stamp.feature_schema_version,
        "extraction_version": stamp.extraction_version,
        "aggregation_version": stamp.aggregation_version,
    }
