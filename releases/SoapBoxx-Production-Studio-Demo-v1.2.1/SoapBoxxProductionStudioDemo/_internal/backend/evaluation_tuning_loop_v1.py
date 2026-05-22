# backend/evaluation_tuning_loop_v1.py
"""
Evaluation & Tuning Loop v1 — self-calibration **metrics and bounded recommendations**.

This module does **not** generate podcast content. It answers whether aggregate signals suggest
the stack is drifting (permissive / strict) and produces **capped** tuning hints for engineers.

**Safety:** at most one adjustment proposal per sub-engine per run; no more than
``MAX_RELATIVE_CHANGE`` relative change on any single numeric suggestion.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

# --- Target bands (from spec) ---
CPS_TARGET_MIN = 0.7
CPS_PERMISSIVE_ALERT = 0.5
FSI_RANGE = (0.4, 0.85)
TSS_TARGET_MIN = 0.6
CVR_TARGET_MIN = 0.85
MAX_RELATIVE_CHANGE = 0.15
OSCILLATION_FLIPS = 3


@dataclass
class CoreMetricsV1:
    """Serialized metrics for one episode (or one batch aggregate)."""

    cps: float
    fsi: float
    tss: float
    cvr: float
    n_accepted: int
    n_rejected: int
    n_supported: int
    n_structural_components: int
    n_thesis_repeated_clusters: int
    n_clips: int
    n_clips_valid: int
    details: Dict[str, Any] = field(default_factory=dict)


def _ids_from_accepted(accepted: Sequence[Mapping[str, Any]]) -> Set[str]:
    s: Set[str] = set()
    for i, c in enumerate(accepted):
        cid = str(c.get("id") or c.get("claim_id") or f"c_v2_{i+1}").strip()
        s.add(cid)
    return s


def _thesis_support_claim_ids(thesis: Optional[Mapping[str, Any]]) -> Set[str]:
    out: Set[str] = set()
    if not isinstance(thesis, Mapping):
        return out
    for cl in thesis.get("supporting_clusters") or []:
        if not isinstance(cl, Mapping):
            continue
        for x in cl.get("claim_ids") or []:
            out.add(str(x))
    return out


def _clip_claim_ids(clips: Optional[Mapping[str, Any]]) -> Set[str]:
    out: Set[str] = set()
    if not isinstance(clips, Mapping):
        return out
    for c in clips.get("clips") or []:
        if not isinstance(c, Mapping):
            continue
        for x in c.get("claim_ids") or []:
            out.add(str(x))
    return out


def _eval_segments_for_ids(
    claim_ids: Sequence[str],
    evaluation_map: Mapping[str, str],
) -> int:
    segs: Set[str] = set()
    for cid in claim_ids:
        if cid in evaluation_map:
            segs.add(evaluation_map[cid])
    return len(segs)


def _count_thesis_repeated_support(thesis: Optional[Mapping[str, Any]], evaluation_map: Mapping[str, str]) -> int:
    """
    A 'repeated' support cluster: ≥3 claim ids and material spans ≥2 source segments
    (repetition across segments, not a loose theme).
    """
    n = 0
    if not isinstance(thesis, Mapping):
        return 0
    for cl in thesis.get("supporting_clusters") or []:
        if not isinstance(cl, Mapping):
            continue
        cids = [str(x) for x in (cl.get("claim_ids") or [])]
        if len(cids) < 3:
            continue
        if _eval_segments_for_ids(cids, evaluation_map) >= 2:
            n += 1
    return n


def compute_core_metrics(
    *,
    accepted_claims: Sequence[Mapping[str, Any]],
    rejected_claims: Sequence[Mapping[str, Any]],
    evaluation_map: Mapping[str, str],
    thesis: Optional[Mapping[str, Any]] = None,
    clip_output: Optional[Mapping[str, Any]] = None,
    structural_components: Optional[Sequence[Sequence[str]]] = None,
) -> CoreMetricsV1:
    """
    **CPS** — share of accepted claims that appear in thesis and/or clip claim sets
    (post-hoc *support* in downstream engines).

    **FSI** — ``rejected / (accepted + rejected)``.

    **TSS** — ``thesis_repeated_support_clusters / max(1, total_clusters)`` where
    ``total_clusters`` is the number of structural components when provided, else
    the count of thesis ``supporting_clusters`` (at least 1 if thesis is present and non-empty).

    **CVR** — clips whose every ``claim_id`` is in the accepted-claim id set.
    """
    n_acc = len(accepted_claims)
    n_rej = len(rejected_claims)
    acc_ids = _ids_from_accepted(accepted_claims)

    t_sup = _thesis_support_claim_ids(thesis)
    c_sup = _clip_claim_ids(clip_output)
    supported = (t_sup | c_sup) & acc_ids
    n_sup = len(supported)

    cps = n_sup / max(1, n_acc)
    fsi = n_rej / max(1, n_acc + n_rej)

    comps: List[Sequence[str]] = list(structural_components) if structural_components is not None else []
    n_struct = max(1, len(comps))
    thr = _count_thesis_repeated_support(thesis, evaluation_map)
    th_clusters = thesis.get("supporting_clusters") if isinstance(thesis, Mapping) else None
    n_thesis_clusters = len(th_clusters) if isinstance(th_clusters, list) and th_clusters else 0
    total_for_tss = n_struct
    if structural_components is None and n_thesis_clusters:
        total_for_tss = max(total_for_tss, n_thesis_clusters)
    tss = thr / max(1, total_for_tss)

    clips = (clip_output or {}).get("clips") or []
    n_clips = len(clips)
    n_valid = 0
    for cl in clips:
        if not isinstance(cl, dict):
            continue
        cids = [str(x) for x in (cl.get("claim_ids") or [])]
        if not cids:
            continue
        if all(x in acc_ids for x in cids):
            n_valid += 1
    cvr = n_valid / max(1, n_clips) if n_clips else 1.0

    return CoreMetricsV1(
        cps=round(cps, 4),
        fsi=round(fsi, 4),
        tss=round(tss, 4),
        cvr=round(cvr, 4),
        n_accepted=n_acc,
        n_rejected=n_rej,
        n_supported=n_sup,
        n_structural_components=len(comps) if structural_components is not None else 0,
        n_thesis_repeated_clusters=thr,
        n_clips=n_clips,
        n_clips_valid=n_valid,
        details={
            "supported_claim_ids": sorted(supported)[:200],
        },
    )


def compute_metrics_from_pipeline_result(result: Mapping[str, Any]) -> CoreMetricsV1:
    """
    Adapts :func:`backend.soapboxx_v2_pipeline.run_soapboxx_v2_pipeline` output.
    Injects claim ``id`` values matching the pipeline (``c_v2_{i}``) so CPS/CVR line up.
    """
    cf = result.get("claim_filter") or {}
    acc_raw = [x for x in (cf.get("accepted") or []) if isinstance(x, dict)]
    rej = [x for x in (cf.get("rejected") or []) if isinstance(x, dict)]
    em = result.get("evaluation_map") or {}
    emd = em if isinstance(em, dict) else dict(em)  # type: ignore[assignment, arg-type]
    comprows = (result.get("structural_components") or {}).get("components") or []
    th = result.get("thesis")
    cl = result.get("clips")
    acc: List[Dict[str, Any]] = []
    for i, a in enumerate(acc_raw):
        acc.append({**a, "id": f"c_v2_{i+1}"})
    return compute_core_metrics(
        accepted_claims=acc,
        rejected_claims=rej,
        evaluation_map=emd,
        thesis=th if isinstance(th, dict) else None,
        clip_output=cl if isinstance(cl, dict) else None,
        structural_components=comprows if comprows else None,
    )


@dataclass
class DriftReportV1:
    filter_drift: bool
    generation_drift: bool
    clip_drift: bool
    messages: List[str]
    cps_change: Optional[float] = None
    tss_change: Optional[float] = None
    cvr_change: Optional[float] = None


def detect_drift(
    current: CoreMetricsV1,
    previous: Optional[CoreMetricsV1] = None,
) -> DriftReportV1:
    msgs: List[str] = []
    filter_d = generation_d = clip_d = False
    cps_c = tss_c = cvr_c = None
    if previous is not None:
        cps_c = current.cps - previous.cps
        tss_c = current.tss - previous.tss
        cvr_c = current.cvr - previous.cvr
        if cps_c < -0.12 and previous.cps >= CPS_TARGET_MIN * 0.9:
            filter_d = True
            msgs.append("CPS dropped sharply; check claim filter or scoring bridge.")
        if tss_c < -0.12 and previous.tss >= TSS_TARGET_MIN * 0.9:
            generation_d = True
            msgs.append("TSS dropped; thesis clustering / support may be unstable.")
        if cvr_c < -0.12 and previous.cvr >= CVR_TARGET_MIN * 0.9:
            clip_d = True
            msgs.append("CVR dropped; clip engine may be losing claim anchors.")
    if current.cps < CPS_PERMISSIVE_ALERT and current.fsi < FSI_RANGE[0]:
        msgs.append("CPS low with loose filter (FSI low); system may be too permissive.")
    if current.cps < CPS_PERMISSIVE_ALERT and current.fsi > FSI_RANGE[1]:
        msgs.append("CPS low with tight filter (FSI high); later stages may starve or filter too strict.")
    if current.cvr < CVR_TARGET_MIN and current.n_clips:
        clip_d = True
    return DriftReportV1(
        filter_drift=filter_d,
        generation_drift=generation_d,
        clip_drift=clip_d,
        messages=msgs,
        cps_change=cps_c,
        tss_change=tss_c,
        cvr_change=cvr_c,
    )


def _bound_delta(nominal: float, value: float) -> float:
    cap = max(abs(nominal) * MAX_RELATIVE_CHANGE, 1e-9)
    return max(-cap, min(cap, value - nominal))


@dataclass
class TuningProposalV1:
    engine: str
    action: str
    parameters: Dict[str, float]
    rationale: str


def propose_bounded_tuning(
    m: CoreMetricsV1,
    *,
    claim_score_min: float = 3.0,
    graph_edge_th: float = 0.11,
    min_clip_score: float = 4.0,
) -> Dict[str, Any]:
    """
    Returns at most one suggestion per engine (safety), each parameter shift capped at
    ``MAX_RELATIVE_CHANGE * reference`` for that knob.
    """
    props: List[TuningProposalV1] = []
    cps, fsi, tss, cvr = m.cps, m.fsi, m.tss, m.cvr

    if cps < CPS_PERMISSIVE_ALERT and fsi > FSI_RANGE[1] and not props:
        props.append(
            TuningProposalV1(
                engine="claim_filter",
                action="relax_strictness_slightly",
                parameters={
                    "suggested_claim_score_min_delta": round(claim_score_min * -MAX_RELATIVE_CHANGE, 2),
                    "abstraction_weight_mult": round(1.0 - 0.12, 2),
                },
                rationale="CPS low while FSI high: filter may be choking later-stage support.",
            )
        )
    if cps < CPS_PERMISSIVE_ALERT and fsi < FSI_RANGE[0] and not any(p.engine == "claim_filter" for p in props):
        props.append(
            TuningProposalV1(
                engine="claim_filter",
                action="tighten_information_weight",
                parameters={
                    "filler_weight_mult": round(1.0 + 0.12, 2),
                    "suggested_claim_score_min_delta": round(claim_score_min * MAX_RELATIVE_CHANGE, 2),
                },
                rationale="CPS low while FSI low: too much junk accepted; raise score bar / filler cost.",
            )
        )
    if tss < TSS_TARGET_MIN and not any(p.engine == "thesis" for p in props):
        props.append(
            TuningProposalV1(
                engine="thesis",
                action="tighten_structural_graph",
                parameters={
                    "suggested_graph_edge_th_delta": _bound_delta(graph_edge_th, graph_edge_th * (1.0 + MAX_RELATIVE_CHANGE)),
                },
                rationale="TSS low: require stronger inter-claim links before thesis support.",
            )
        )
    if cvr < CVR_TARGET_MIN and m.n_clips and not any(p.engine == "clips" for p in props):
        props.append(
            TuningProposalV1(
                engine="clips",
                action="tighten_clip_scoring",
                parameters={
                    "suggested_min_clip_score_delta": _bound_delta(min_clip_score, min_clip_score * (1.0 + MAX_RELATIVE_CHANGE)),
                },
                rationale="CVR low: require higher structural clip score before keep.",
            )
        )
    return {
        "proposals": [asdict(p) for p in props],
        "locks": {
            "max_relative_change": MAX_RELATIVE_CHANGE,
            "max_one_proposal_per_engine": True,
        },
    }


def detect_metric_oscillation(
    history: Sequence[Mapping[str, float]],
    *,
    field_name: str = "cps",
) -> bool:
    """
    True if the first difference of the metric (``v[i] - v[i-1]``) changes sign
    at least ``OSCILLATION_FLIPS`` times in the last series (failsafe before revert).
    """
    if len(history) < OSCILLATION_FLIPS + 2:
        return False
    vals = [float(x.get(field_name) or 0) for x in history]
    sign_changes = 0
    prev_d = 0.0
    for i in range(1, len(vals)):
        d = vals[i] - vals[i - 1]
        if i >= 2 and prev_d * d < 0 and abs(d) > 1e-6 and abs(prev_d) > 1e-6:
            sign_changes += 1
        prev_d = d
    return sign_changes >= OSCILLATION_FLIPS


def run_tuning_batch(
    runs: Sequence[Mapping[str, Any]],
    *,
    previous_cumulative: Optional[CoreMetricsV1] = None,
) -> Dict[str, Any]:
    """
    Aggregate metrics (mean of episode metrics) and emit drift + tuning over the batch.
    """
    mets: List[CoreMetricsV1] = []
    for r in runs:
        mets.append(compute_metrics_from_pipeline_result(r))
    if not mets:
        return {"ok": False, "reason": "no_runs", "metrics": None}

    def mean_attr(k: str) -> float:
        return float(sum(getattr(m, k) for m in mets) / max(1, len(mets)))

    agg = CoreMetricsV1(
        cps=round(mean_attr("cps"), 4),
        fsi=round(mean_attr("fsi"), 4),
        tss=round(mean_attr("tss"), 4),
        cvr=round(mean_attr("cvr"), 4),
        n_accepted=sum(m.n_accepted for m in mets),
        n_rejected=sum(m.n_rejected for m in mets),
        n_supported=sum(m.n_supported for m in mets),
        n_structural_components=max(m.n_structural_components for m in mets),
        n_thesis_repeated_clusters=sum(m.n_thesis_repeated_clusters for m in mets),
        n_clips=sum(m.n_clips for m in mets),
        n_clips_valid=sum(m.n_clips_valid for m in mets),
    )
    prev = previous_cumulative
    drift = detect_drift(agg, prev)
    tune = propose_bounded_tuning(agg)
    cps_seq = [{"cps": m.cps} for m in mets]
    return {
        "ok": True,
        "n_episodes": len(mets),
        "episode_metrics": [asdict(m) for m in mets],
        "aggregate_metrics": asdict(agg),
        "drift": asdict(drift),
        "tuning": tune,
        "oscillation_flags": {
            "cps_oscillating": detect_metric_oscillation(cps_seq, field_name="cps"),
            "revert_suggested": detect_metric_oscillation(cps_seq, field_name="cps") and len(mets) >= OSCILLATION_FLIPS + 2,
        },
    }


def export_metrics_json(m: CoreMetricsV1) -> str:
    return json.dumps(asdict(m), indent=2)


__all__ = [
    "CPS_TARGET_MIN",
    "CPS_PERMISSIVE_ALERT",
    "FSI_RANGE",
    "TSS_TARGET_MIN",
    "CVR_TARGET_MIN",
    "MAX_RELATIVE_CHANGE",
    "OSCILLATION_FLIPS",
    "CoreMetricsV1",
    "DriftReportV1",
    "TuningProposalV1",
    "compute_core_metrics",
    "compute_metrics_from_pipeline_result",
    "detect_drift",
    "propose_bounded_tuning",
    "detect_metric_oscillation",
    "run_tuning_batch",
    "export_metrics_json",
]
