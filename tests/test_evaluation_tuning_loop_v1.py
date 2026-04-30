# tests/test_evaluation_tuning_loop_v1.py
from __future__ import annotations

import pytest

from backend.evaluation_tuning_loop_v1 import (
    CoreMetricsV1,
    compute_core_metrics,
    compute_metrics_from_pipeline_result,
    detect_drift,
    detect_metric_oscillation,
    propose_bounded_tuning,
    run_tuning_batch,
)
from backend.soapboxx_v2_pipeline import run_soapboxx_v2_pipeline


def test_cps_fsi_trivial():
    m = compute_core_metrics(
        accepted_claims=[{"id": "c1", "text": "a b c d e f story detail."}, {"id": "c2", "text": "g h i j k l claim."}],
        rejected_claims=[{"text": "um"}] * 3,
        evaluation_map={"c1": "s1", "c2": "s2"},
        thesis=None,
        clip_output={"clips": [{"claim_ids": ["c1"]}]},
    )
    assert m.fsi == pytest.approx(3 / 5)
    # c1 in clip, c2 not -> supported 1/2
    assert m.cps == pytest.approx(0.5)
    assert m.n_clips == 1
    assert m.cvr == 1.0


def test_tss_repeated_cluster_theshold():
    th = {
        "supporting_clusters": [
            {"claim_ids": ["c1", "c2", "c3"]},
        ],
        "thesis": "x",
    }
    m = compute_core_metrics(
        accepted_claims=[{"id": f"c{i}"} for i in range(1, 4)],
        rejected_claims=[],
        evaluation_map={"c1": "s1", "c2": "s1", "c3": "s2"},
        thesis=th,
        clip_output=None,
        structural_components=[["c1", "c2", "c3"]],
    )
    assert m.n_thesis_repeated_clusters == 1
    assert m.tss == pytest.approx(1.0 / 1.0)  # one comp, one repeated
    m2 = compute_core_metrics(
        accepted_claims=[{"id": f"c{i}"} for i in range(1, 4)],
        rejected_claims=[],
        evaluation_map={"c1": "s1", "c2": "s1", "c3": "s1"},
        thesis=th,
        clip_output=None,
        structural_components=[["c1", "c2", "c3"]],
    )
    # still one segment in map for all three? single segment -> not "repeated" across segments
    assert m2.n_thesis_repeated_clusters == 0
    assert m2.tss == 0.0


def test_pipeline_metrics_round_trip():
    segs = [
        {"id": "s1", "text": "a b c d e f and policy detail here.", "start_time": 0, "end_time": 1},
        {"id": "s2", "text": "g h i j k l m n o p q claim detail.", "start_time": 2, "end_time": 3},
    ]
    r = run_soapboxx_v2_pipeline(segs, mode="debug")
    m = compute_metrics_from_pipeline_result(r)
    assert 0.0 <= m.cps <= 1.0
    assert 0.0 <= m.fsi <= 1.0


def test_tuning_rule_strict_filter_recommendation():
    m = CoreMetricsV1(
        cps=0.4,
        fsi=0.9,
        tss=0.7,
        cvr=0.9,
        n_accepted=5,
        n_rejected=45,
        n_supported=2,
        n_structural_components=0,
        n_thesis_repeated_clusters=0,
        n_clips=0,
        n_clips_valid=0,
    )
    p = propose_bounded_tuning(m)
    assert p["proposals"]
    assert any(x["engine"] == "claim_filter" for x in p["proposals"])


def test_oscillation_detects_oscillation():
    s = [
        {"cps": 0.8},
        {"cps": 0.4},
        {"cps": 0.75},
        {"cps": 0.35},
        {"cps": 0.78},
    ]
    assert detect_metric_oscillation(s, field_name="cps")


def test_run_tuning_batch():
    r = run_soapboxx_v2_pipeline(
        [{"id": "s1", "text": "um", "start_time": 0, "end_time": 1} for _ in range(3)], mode="debug"
    )
    out = run_tuning_batch([r])
    assert out["ok"]
    assert "aggregate_metrics" in out
    assert "tuning" in out


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
