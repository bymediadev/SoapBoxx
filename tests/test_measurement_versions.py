"""Triple-layer measurement versioning and cohort guards."""

from __future__ import annotations

from backend.models import EpisodeFeatures
from backend.services.library_benchmarks import library_from_rows, load_library_benchmarks
from backend.services.measurement_versions import (
    CURRENT_STAMP,
    MeasurementStamp,
    cohort_note,
    filter_comparable_rows,
    stamp_dict,
    stamps_compatible,
)


def _row(**kwargs) -> EpisodeFeatures:
    defaults = dict(
        episode_id=1,
        hook_length_seconds=30.0,
        question_count=5,
        feature_schema_version=CURRENT_STAMP.feature_schema_version,
        extraction_version=CURRENT_STAMP.extraction_version,
        aggregation_version=CURRENT_STAMP.aggregation_version,
    )
    defaults.update(kwargs)
    return EpisodeFeatures(**defaults)


def test_stamps_compatible_requires_all_three_layers():
    anchor = CURRENT_STAMP
    same = MeasurementStamp("v1", "1.0.0", "1.2.0")
    diff_extraction = MeasurementStamp("v1", "1.1.0", "1.2.0")
    diff_aggregation = MeasurementStamp("v1", "1.0.0", "1.1.0")
    assert stamps_compatible(anchor, same)
    assert not stamps_compatible(anchor, diff_extraction)
    assert not stamps_compatible(anchor, diff_aggregation)


def test_filter_excludes_mixed_aggregation_version():
    anchor = _row(episode_id=1)
    compatible = _row(episode_id=2)
    stale = _row(episode_id=3, aggregation_version="0.9.0")
    kept, excluded = filter_comparable_rows([compatible, stale], CURRENT_STAMP)
    assert len(kept) == 1
    assert kept[0].episode_id == 2
    assert excluded == 1


def test_cohort_note_only_when_excluded():
    assert cohort_note(0) is None
    assert cohort_note(2) and "2 measured episodes" in cohort_note(2)


def test_library_load_respects_anchor_stamp(monkeypatch):
    rows = [
        _row(episode_id=1),
        _row(episode_id=2),
        _row(episode_id=3, extraction_version="0.9.0"),
    ]

    class _FakeResult:
        def scalars(self):
            return self

        def all(self):
            return rows

    class _FakeDb:
        def execute(self, _query):
            return _FakeResult()

    lib, excluded = load_library_benchmarks(_FakeDb(), anchor=_row(episode_id=1))
    assert excluded == 1
    assert lib.n_measured == 2


def test_stamp_dict_round_trip():
    d = stamp_dict(CURRENT_STAMP)
    assert d["feature_schema_version"] == "v1"
    assert d["extraction_version"] == "1.0.0"
    assert d["aggregation_version"] == "1.2.0"
