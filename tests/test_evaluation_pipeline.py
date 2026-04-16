"""Contract tests for snapshot evaluator/finalizer pipeline."""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from evaluation_pipeline import (  # noqa: E402
    build_evaluation_snapshot,
    compute_input_quality_score,
    compute_limited_reason,
    evaluate_snapshot,
    finalize_evaluation,
    sanitize_input_quality_components_v1,
)


def _row(claim: str, evidence: str, rid: str) -> dict:
    return {
        "id": rid,
        "claim": claim,
        "evidence": evidence,
        "timestamp": None,
        "type": "rule_anchor",
    }


def test_snapshot_evaluator_uses_canonical_counts_for_structure():
    wf = {
        "metadata": {},
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [
            {"question": "Q1", "question_type": "counter", "claim_id": "c1"},
            {"question": "Q2", "question_type": "validation", "claim_id": "c2"},
        ],
    }
    r3 = {"evidence_mapping": [], "segments": []}
    snap = build_evaluation_snapshot(wf, r3, {"strict_export_enabled": True, "title": "T"})
    ev = evaluate_snapshot(snap)
    assert ev["structure_state"] == "STRONG"
    assert ev["structure_diagnostics"]["evidence_rows"] == 2
    assert ev["structure_diagnostics"]["segments"] == 1
    assert ev["signal_valid"] is True
    assert ev["output_mode_valid"] is True
    assert ev["production_candidate"] is True
    assert ev.get("user_export_mode") == "full"
    assert ev.get("limited_reason") is None
    assert isinstance(ev.get("input_quality_score"), float)
    assert isinstance(ev.get("decision"), dict) and ev["decision"].get("tier")
    assert ev.get("evaluation_version") == "v1"
    assert ev.get("system_version")
    assert ev.get("schema_version")
    assert "unified_failure_category" in ev
    assert isinstance(ev.get("retry_blocked"), bool)


def test_evaluator_filters_stale_structural_reality_failures():
    wf = {
        "metadata": {
            "v3_reality_check": {
                "passed": False,
                "failures": [
                    "FAIL: evidence rows 0 < min_evidence_rows 2",
                    "FAIL: segments 0 < min_segments 1",
                ],
                "would_ship": True,
                "ship_blockers": [],
            }
        },
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [],
    }
    r3 = {"evidence_mapping": [], "segments": []}
    snap = build_evaluation_snapshot(wf, r3, {"strict_export_enabled": True, "title": "T"})
    ev = evaluate_snapshot(snap)
    # Structural failures coming from pre-bootstrap v3 reality checks should not block
    # canonical post-bootstrap export evaluation.
    assert ev["export_status"] == "ok"
    assert ev["export_blockers_by_source"]["v3_reality"] == []


def test_snapshot_quantifies_cross_source_discrepancy():
    wf = {
        "metadata": {},
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [],
    }
    r3 = {"evidence_mapping": [], "segments": []}
    snap = build_evaluation_snapshot(wf, r3, {"strict_export_enabled": True, "title": "T"})
    disc = snap["source_discrepancies"]
    assert disc["evidence_count"]["workflow"] == 2
    assert disc["evidence_count"]["report_v3"] == 0
    assert disc["evidence_count"]["delta"] == 2
    assert disc["evidence_count"]["mismatch"] is True
    assert disc["segment_count"]["workflow"] == 1
    assert disc["segment_count"]["report_v3"] == 0
    assert disc["segment_count"]["delta"] == 1
    assert disc["segment_count"]["mismatch"] is True


def test_output_mode_validity_is_independent_of_content_counts():
    wf = {
        "metadata": {},
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [],
    }
    # Diagnostic mode should only affect output_mode_valid / production_candidate.
    r3 = {"evidence_mapping": [], "segments": [], "output_mode": "diagnostic"}
    snap = build_evaluation_snapshot(wf, r3, {"strict_export_enabled": True, "title": "T"})
    ev = evaluate_snapshot(snap)
    assert ev["export_status"] == "ok"
    assert ev["signal_valid"] is True
    assert ev["evaluation_eligible"] is True
    assert ev["output_mode_valid"] is False
    assert ev["production_candidate"] is False
    assert ev.get("user_export_mode") == "limited"
    assert ev.get("limited_reason") == "content"


def test_export_status_degraded_when_ollama_transport_failed():
    """Single finalizer path: transport exhaustion sets export_status degraded (not insufficient_signal)."""
    wf = {
        "metadata": {
            "ollama_transport_degraded": True,
            "ollama_last_transport_failure_code": "timeout_read_body",
        },
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [
            {"question": "Q1", "question_type": "counter", "claim_id": "c1"},
        ],
    }
    r3 = {"output_mode": "full", "segments": [{"id": "s1"}], "evidence_mapping": []}
    snap = build_evaluation_snapshot(wf, r3, {"strict_export_enabled": True, "title": "T"})
    assert snap.get("ollama_transport_degraded") is True
    ev = evaluate_snapshot(snap)
    assert ev["export_status"] == "degraded"
    assert any("Ollama transport exhausted" in str(b) for b in ev["export_blockers"])
    ob = ev.get("export_blockers_by_source") or {}
    assert isinstance(ob.get("ollama_transport"), list) and ob["ollama_transport"]
    meta: Dict[str, Any] = {}
    out = finalize_evaluation(meta, snap, ev)
    assert out["export_status"] == "degraded"
    assert out.get("user_export_mode") == "limited"
    assert out.get("limited_reason") == "system"


def test_snapshot_hash_is_deterministic_for_same_inputs():
    wf = {
        "metadata": {},
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [
            {"question": "Q1", "question_type": "counter", "claim_id": "c1"},
            {"question": "Q2", "question_type": "validation", "claim_id": "c2"},
        ],
    }
    r3 = {"output_mode": "diagnostic", "segments": [], "evidence_mapping": []}
    meta = {"strict_export_enabled": True, "title": "T", "creator": "C", "genre": "G"}
    s1 = build_evaluation_snapshot(wf, r3, meta)
    s2 = build_evaluation_snapshot(wf, r3, meta)
    assert s1["snapshot_hash"] == s2["snapshot_hash"]


def test_snapshot_hash_ignores_trace_id_for_determinism():
    """trace_id is observability-only; hash must not drift across runs."""
    wf = {
        "metadata": {},
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [
            {"question": "Q1", "question_type": "counter", "claim_id": "c1"},
            {"question": "Q2", "question_type": "validation", "claim_id": "c2"},
        ],
    }
    r3 = {"output_mode": "diagnostic", "segments": [], "evidence_mapping": []}
    base = {"strict_export_enabled": True, "title": "T", "creator": "C", "genre": "G"}
    a = build_evaluation_snapshot(wf, r3, {**base, "trace_id": "run-a"})
    b = build_evaluation_snapshot(wf, r3, {**base, "trace_id": "run-b"})
    assert a["snapshot_hash"] == b["snapshot_hash"]
    assert a.get("trace_id") != b.get("trace_id")


def test_snapshot_hash_parallel_builds_match():
    wf = {
        "metadata": {},
        "evidence_map": [
            _row("C1 claim text here for grounded check.", "E1 evidence here.", "c1"),
            _row("C2 claim text here for grounded check.", "E2 evidence here.", "c2"),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [
            {"question": "Q1", "question_type": "counter", "claim_id": "c1"},
        ],
    }
    r3 = {"output_mode": "full", "segments": [{"id": "s1"}], "evidence_mapping": []}
    meta = {"strict_export_enabled": True, "title": "T", "creator": "C", "genre": "G", "trace_id": "p1"}

    def _build():
        return build_evaluation_snapshot(wf, r3, meta)

    hashes = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(_build) for _ in range(8)]
        for f in as_completed(futs):
            hashes.append(f.result()["snapshot_hash"])
    assert len(set(hashes)) == 1


def test_batch_snapshot_build_no_hash_drift():
    """Sequential repeated builds must not drift (lightweight stand-in for long batch runs)."""
    wf = {
        "metadata": {},
        "evidence_map": [
            _row(
                "First grounded claim has enough words to pass the export grounded checks.",
                "First grounded evidence quote has enough words to pass the export grounded checks.",
                "c1",
            ),
            _row(
                "Second grounded claim has enough words to pass the export grounded checks.",
                "Second grounded evidence quote has enough words to pass the export grounded checks.",
                "c2",
            ),
        ],
        "segments": [{"id": "s1"}],
        "follow_up_questions": [
            {"question": "Q1", "question_type": "counter", "claim_id": "c1"},
            {"question": "Q2", "question_type": "validation", "claim_id": "c2"},
        ],
    }
    r3 = {"output_mode": "diagnostic", "segments": [], "evidence_mapping": []}
    meta = {"strict_export_enabled": True, "title": "T", "creator": "C", "genre": "G"}
    h0 = None
    for _ in range(40):
        h = build_evaluation_snapshot(wf, r3, meta)["snapshot_hash"]
        if h0 is None:
            h0 = h
        assert h == h0


def test_sanitize_input_quality_components_v1_strips_unknown_keys():
    raw = {
        "input_quality_score": 0.5,
        "extra_dynamic": 99.0,
        "transcript_length_score": 0.1,
        "extraction_success_score": 0.2,
        "grounding_density_score": 0.3,
    }
    s = sanitize_input_quality_components_v1(raw)
    assert "extra_dynamic" not in s
    assert set(s.keys()) <= {
        "input_quality_score",
        "transcript_length_score",
        "extraction_success_score",
        "grounding_density_score",
    }


def test_finalize_writes_single_authority_fields():
    wf = {"metadata": {}, "evidence_map": [], "segments": [], "follow_up_questions": []}
    snap = build_evaluation_snapshot(wf, {}, {"strict_export_enabled": True, "title": "T"})
    ev = evaluate_snapshot(snap)
    meta = {}
    out = finalize_evaluation(meta, snap, ev)
    assert out["evaluation_finalized"] is True
    assert "evaluation_snapshot_hash" in out
    assert out["export_status"] in ("ok", "insufficient_signal")
    assert isinstance(out["export_blockers_by_source"], dict)
    assert isinstance(out["signal_valid"], bool)
    assert isinstance(out["evaluation_eligible"], bool)
    assert isinstance(out["output_mode_valid"], bool)
    assert isinstance(out["production_candidate"], bool)
    assert out.get("user_export_mode") in ("full", "limited")
    lr = out.get("limited_reason")
    assert lr is None or lr in ("content", "input", "system")
    assert isinstance(out.get("input_quality_score"), float)
    assert isinstance(out.get("input_quality_components"), dict)
    assert isinstance(out.get("decision"), dict) and "tier" in out["decision"]
    assert out["decision"].get("metrics_ref") == "input_quality_components"
    assert "scores" not in out["decision"]
    assert isinstance(out["decision"].get("trace"), dict)
    assert out.get("system_version")
    assert out.get("evaluation_version") == "v1"
    assert out.get("schema_version")
    assert "retry_blocked" in out
    assert "unified_failure_category" in out


def test_compute_input_quality_score_long_text_zero_extraction_is_input():
    """Long tape with no extraction yield should score below threshold (input/pipeline read problem)."""
    iqs = compute_input_quality_score(5000, 0, 0)
    assert iqs < 0.3


def test_compute_input_quality_score_grounding_damped_for_small_claim_counts():
    """Perfect evidence:claim ratio at cc=1 is damped by min(1, cc/5); at cc=5 it is not."""
    low_claims = compute_input_quality_score(2000, 1, 1)
    higher_claims = compute_input_quality_score(2000, 5, 5)
    assert higher_claims > low_claims


def test_compute_limited_reason_short_transcript_is_input():
    snap = {"transcript_word_count": 80, "readiness_band": "weak", "claim_count": 0, "canonical_evidence_count": 0}
    iqs = compute_input_quality_score(80, 0, 0)
    assert iqs < 0.3
    r = compute_limited_reason(
        user_export_mode="limited",
        export_status="insufficient_signal",
        snapshot=snap,
        export_blockers=["grounded evidence rows 0 < 2 (canonical)"],
        blockers_by_source={"ollama_transport": []},
        input_quality_score=iqs,
    )
    assert r == "input"


def test_compute_limited_reason_transport_is_system():
    snap = {"transcript_word_count": 2000, "readiness_band": "strong"}
    r = compute_limited_reason(
        user_export_mode="limited",
        export_status="degraded",
        snapshot=snap,
        export_blockers=["Ollama transport exhausted retries (timeout)."],
        blockers_by_source={"ollama_transport": ["Ollama transport exhausted retries (timeout)."]},
        input_quality_score=compute_input_quality_score(2000, 0, 0),
    )
    assert r == "system"


def test_final_field_writes_only_in_evaluation_pipeline():
    repo = Path(__file__).resolve().parents[1]
    py_files = []
    for root in ("backend", "scripts"):
        py_files.extend((repo / root).rglob("*.py"))
    pattern = re.compile(
        r'\["(?:export_status|signal_valid|evaluation_eligible|production_candidate|output_mode_valid)"\]\s*=',
    )
    violators = []
    for p in py_files:
        if p.name == "evaluation_pipeline.py":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if pattern.search(text):
            violators.append(str(p.relative_to(repo)))
    assert not violators, f"Final field writes found outside evaluation_pipeline.py: {violators}"

