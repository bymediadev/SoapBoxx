# backend/soapboxx_v2_pipeline.py
"""
SOAPBOXX v2 — **canonical end-to-end integration** (orchestration only; no new inference).

**Invariant:** each stage *transforms or rejects* — it must not invent meaning, infer missing
context, or turn weak signal into hard structure. Episode **title** is *not* a parameter of
this runner and is **never** passed to :func:`backend.claim_filter_v2.filter_claim_candidates`
or :func:`backend.clip_engine_v2.extract_clips_v2`. (Optional :func:`backend.thesis_engine_v2.construct_thesis_v2`
``episode_metadata`` is supported only for leakage *checks* when explicitly supplied by the
caller; the default is **no** metadata.)

**Pipeline (see tests for failure simulators):**

1. **Ingestion** — `segments[]` with ``id`` + ``text`` (``start_time`` / ``end_time`` optional).
2. **Claim filter v2** — :func:`backend.claim_filter_v2.filter_claim_candidates`.
3. **Evaluation map** — stable ``claim_id`` → ``source_segment_id`` (traceability only).
4. **Cluster engine** — structural graph → connected components
   :func:`backend.clip_engine_v2.structural_connected_components` on accepted claim texts.
5. **Thesis v2** — :func:`backend.thesis_engine_v2.construct_thesis_v2` (≥3-claim + ≥2-segment
   rules, anti-hallucination gates) when ``include_thesis`` and enough claims exist.
6. **Clip v2** — :func:`backend.clip_engine_v2.extract_clips_v2` (claim-bounded, score floor).
7. **Output** — thesis, clips, filter traces, component list; optional debug bundle.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from backend.claim_filter_v2 import filter_claim_candidates, STAGE_CLAIM_FILTER
from backend.clip_engine_v2 import extract_clips_v2, structural_connected_components
from backend.thesis_engine_v2 import construct_thesis_v2

PIPELINE_NAME = "soapboxx_v2"
PIPELINE_VERSION = "1.0.0"

PIPELINE_STEPS: Tuple[Tuple[str, str], ...] = (
    ("1_ingestion", "timestamped segments in"),
    ("2_claim_filter", "filter_claim_candidates → accepted / rejected + traces"),
    ("3_evaluation_map", "claim_id → source_segment_id (traceability)"),
    ("4_structural_clusters", "structural_connected_components (graph)"),
    ("5_thesis_v2", "construct_thesis_v2 (optional)"),
    ("6_clips_v2", "extract_clips_v2 (optional)"),
    ("7_output", "thesis, clips, debug"),
)


def normalize_timestamped_segments(
    raw: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for i, s in enumerate(raw):
        if not isinstance(s, Mapping):
            continue
        sid = s.get("id", f"s{i+1}")
        text = s.get("text", s.get("content", s.get("sentence", "")))
        st = s.get("start_time", s.get("start", s.get("t")))
        en = s.get("end_time", s.get("end"))
        row: Dict[str, Any] = {"id": str(sid), "text": str(text or "")}
        if st is not None:
            try:
                row["start_time"] = float(st)
            except (TypeError, ValueError):
                row["start_time"] = 0.0
        if en is not None:
            try:
                row["end_time"] = float(en)
            except (TypeError, ValueError):
                row["end_time"] = row.get("start_time", 0.0)
        if "start_time" not in row and "t" in s:
            try:
                row["start_time"] = float(s["t"])
            except (TypeError, ValueError):
                pass
        out.append(row)
    return out


def _downstream_accepted(accepted: Sequence[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    claims: List[Dict[str, Any]] = []
    em: Dict[str, str] = {}
    for i, r in enumerate(accepted):
        if r.get("decision") not in (None, "ACCEPTED"):
            continue
        text = (r.get("text") or "").strip()
        if not text:
            continue
        sid = str(r.get("source_segment_id") or "")
        if not sid:
            continue
        cid = f"c_v2_{i+1}"
        d = {
            "id": cid,
            "text": text,
            "claim_score": r.get("claim_score"),
        }
        claims.append(d)
        em[cid] = sid
    return claims, em


def run_soapboxx_v2_pipeline(
    segments: Sequence[Mapping[str, Any]],
    *,
    mode: str = "debug",
    transcript_context: Optional[str] = None,
    include_thesis: bool = True,
    include_clips: bool = True,
    thesis_episode_metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run the full v2 path. **Does not** accept an episode title; to run thesis leakage checks,
    pass a mapping via ``thesis_episode_metadata`` (optional). Default is **no** title metadata.

    * ``include_thesis`` / ``include_clips`` — skip heavy stages (tests / minimal runs).
    """
    segs = normalize_timestamped_segments(segments)
    blob = transcript_context
    if blob is None and segs:
        blob = "\n\n".join(x["text"] for x in segs if x.get("text"))

    cf = filter_claim_candidates(
        segs,
        transcript_context=blob,
        use_scoring=True,
        mode=mode if mode in ("debug", "production") else "debug",  # type: ignore[arg-type]
    )
    acc = [x for x in (cf.get("accepted_claims") or []) if isinstance(x, dict)]
    rej = [x for x in (cf.get("rejected_claims") or []) if isinstance(x, dict)]
    reject_rate = len(rej) / max(1, len(acc) + len(rej))
    accept_rate = len(acc) / max(1, len(acc) + len(rej))

    claims, eval_map = _downstream_accepted(acc)
    texts = [c["text"] for c in claims]
    components: List[List[int]] = structural_connected_components(texts) if texts else []

    thesis: Optional[Dict[str, Any]] = None
    clips: Dict[str, Any] = {"clips": []}
    tmeta = thesis_episode_metadata

    if include_thesis:
        if not claims:
            thesis = {
                "thesis": None,
                "supporting_clusters": [],
                "confidence_score": 0.0,
                "generation_status": "INSUFFICIENT_SIGNAL",
                "reason": "NO_ACCEPTED_CLAIMS",
            }
        else:
            thesis = construct_thesis_v2(
                accepted_claims=claims,
                evaluation_map=eval_map,
                source_segments=segs,
                episode_metadata=tmeta,
            )
    if include_clips and claims:
        clips = extract_clips_v2(
            accepted_claims=claims,
            evaluation_map=eval_map,
            source_segments=segs,
        )

    reason = (thesis or {}).get("reason") or ""
    insufficient_thesis = (
        thesis is not None
        and (thesis.get("thesis") is None)
        and (
            "INSUFFICIENT" in str(reason)
            or "NO_THESIS" in str(reason)
            or "NO_ACCEPTED" in str(reason)
            or thesis.get("generation_status") == "INSUFFICIENT_SIGNAL"
        )
    )

    return {
        "pipeline": PIPELINE_NAME,
        "version": PIPELINE_VERSION,
        "stages": dict(PIPELINE_STEPS),
        "claim_filter": {
            "stage": STAGE_CLAIM_FILTER,
            "accepted": acc,
            "rejected": rej,
            "accept_rate": round(accept_rate, 4),
            "reject_rate": round(reject_rate, 4),
        },
        "evaluation_map": eval_map,
        "structural_components": {
            "claim_ids_ordered": [c["id"] for c in claims],
            "components": [ [claims[i]["id"] for i in comp] for comp in components ],
        },
        "thesis": thesis,
        "clips": clips,
        "flags": {
            "insufficient_thesis": insufficient_thesis,
        },
    }


__all__ = [
    "PIPELINE_NAME",
    "PIPELINE_VERSION",
    "PIPELINE_STEPS",
    "normalize_timestamped_segments",
    "run_soapboxx_v2_pipeline",
]
