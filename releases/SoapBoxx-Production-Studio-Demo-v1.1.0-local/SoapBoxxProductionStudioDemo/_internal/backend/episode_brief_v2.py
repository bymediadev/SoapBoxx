# backend/episode_brief_v2.py
"""
Single **authority object** for v2 episode intelligence: ``build_episode_brief_v2``.

Nothing in downstream HTML should invent fields not present here. Routing:
**segments → Claim Filter v2 → spine tagging → gates → structural clusters →
dominant cluster → Thesis v2 → thesis_validator_v2 → status + evaluation**.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from backend.claim_filter_v2 import filter_claim_candidates
from backend.clip_engine_v2 import structural_connected_components
from backend.soapboxx_v2_pipeline import normalize_timestamped_segments
from backend.thesis_engine_v2 import construct_thesis_v2
from backend.thesis_validator_v2 import is_valid_thesis, thesis_validation_failure_reason

MIN_SPINE_CLAIMS = 3
MIN_SPINE_WORDS = 6
MIN_CLUSTER_SIZE = 2
_VERB = re.compile(
    r"(?i)\b("
    r"is|are|was|were|have|has|had|do|does|did|will|would|should|could|may|might|must|"
    r"believe|think|argue|claim|show|mean|happen|cause|lead|drive|prove|order|shoot|"
    r"follow|align|influence|threaten|operate|releas\w*|cite|name|confirm"
    r")\b",
)
_CTA = re.compile(
    r"(?i)\b("
    r"buy\s+now|sign\s+up|use\s+code|discount|free\s+trial|click\s+here|"
    r"subscribe\s+to|sponsor|promo\s+code|limited\s+time"
    r")\b",
)
_PROMO_PRODUCT = re.compile(
    r"(?i)\b("
    r"\bCRM\b|salesforce|hubspot|stripe\s*checkout|odoo|o\.?d\.?o|"
    r"build\s+a\s+custom\s+crm|manage\s+clients|onboarding\s+flow|"
    r"pick\s+the\s+plan|test\s+it\s+and\s+then"
    r")\b",
)
_SOCIAL_SCAFFOLD = re.compile(
    r"(?i)\b("
    r"excited\s+to\s+(?:interview|have\s+you)|top\s+of\s+the\s+list|"
    r"ripper\s+of\s+a\s+question|folks,?\s+if\s+you"
    r")\b",
)


def segments_from_transcript_for_brief_v2(
    transcript: str,
    *,
    chunk_chars: int = 1600,
    max_segments: int = 400,
    chunk_seconds: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Turn a raw transcript string into timestamped pseudo-segments for Claim Filter v2.
    Paragraphs are preserved when short; long paragraphs are split on ``chunk_chars``.
    Times are synthetic (0, 30s, …) for ordering only unless your ingest supplies real times.
    """
    t = (transcript or "").strip()
    if not t:
        return []
    paras = [p.strip() for p in t.split("\n\n") if p.strip()]
    chunks: List[str] = []
    for p in paras:
        if len(p) <= chunk_chars:
            chunks.append(p)
        else:
            for i in range(0, len(p), chunk_chars):
                chunks.append(p[i : i + chunk_chars])
    if not chunks:
        chunks = [t[:chunk_chars]]
    out: List[Dict[str, Any]] = []
    for i, c in enumerate(chunks[:max_segments]):
        st = float(i) * chunk_seconds
        out.append(
            {
                "id": f"s{i+1}",
                "text": c,
                "start_time": st,
                "end_time": st + chunk_seconds,
            }
        )
    return out


def format_brief_v2_markdown_section(brief_v2: Mapping[str, Any]) -> str:
    """Visible state block for unified export (no silent completeness)."""
    st = brief_v2.get("status") if isinstance(brief_v2.get("status"), Mapping) else {}
    fails = st.get("fail_reasons") or []
    lines = [
        "## Brief v2 (constraint pipeline)",
        "",
        f"- **Shippable (v2 bar):** `{bool(st.get('is_shippable'))}`",
    ]
    if fails:
        lines.append(f"- **Gate failures:** {', '.join(str(x) for x in fails)}")
    th = brief_v2.get("thesis")
    if th:
        lines.append(f"- **Thesis (v2):** {th}")
    else:
        lines.append("- **Thesis (v2):** *Thesis construction failed or was rejected by the v2 validator — see gate failures above.*")
    n_tag = len(brief_v2.get("claims") or [])
    n_spine = len([c for c in (brief_v2.get("claims") or []) if isinstance(c, dict) and c.get("is_spine_eligible")])
    lines.append(f"- **Tagged claims:** {n_tag} total, **{n_spine}** spine-eligible after promo/filler gates.")
    lines.append("")
    return "\n".join(lines)


def empty_episode_brief_v2() -> Dict[str, Any]:
    return {
        "claims": [],
        "clusters": [],
        "thesis": None,
        "thesis_engine": None,
        "evaluation": {},
        "metadata": {},
        "enrichment": {},
        "status": {"is_shippable": False, "fail_reasons": []},
    }


def _seg_time_lookup(segs: Sequence[Mapping[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for s in segs:
        if not isinstance(s, Mapping):
            continue
        sid = str(s.get("id") or "")
        if not sid:
            continue
        t = s.get("start_time", s.get("start", s.get("t")))
        try:
            out[sid] = float(t) if t is not None else 0.0
        except (TypeError, ValueError):
            out[sid] = 0.0
    return out


def classify_spine_row(
    *,
    text: str,
    decision: str,
    reason_codes: Optional[Sequence[str]] = None,
) -> Tuple[str, bool]:
    """
    Returns ``(type, is_spine_eligible)`` where type is ``interview`` | ``promo`` | ``filler``.
    """
    t = (text or "").strip()
    wc = len(t.split())
    codes = {str(x).upper() for x in (reason_codes or [])}
    if decision != "ACCEPTED":
        if any("PROMO" in c or "BUSINESS" in c or "SCAFFOLD" in c for c in codes):
            return "promo", False
        if "FILLER" in str(codes) or "PODCAST" in str(codes):
            return "filler", False
        return "filler", False
    if _PROMO_PRODUCT.search(t) or _CTA.search(t):
        return "promo", False
    if _SOCIAL_SCAFFOLD.search(t):
        return "filler", False
    if wc < MIN_SPINE_WORDS:
        return "filler", False
    if not _VERB.search(t):
        return "filler", False
    return "interview", True


def spine_hard_gate(claim: Mapping[str, Any]) -> Optional[str]:
    """Return failure code or None if claim may enter spine pool."""
    t = str(claim.get("text") or "")
    if len(t.split()) < MIN_SPINE_WORDS:
        return "SPINE_TOO_SHORT"
    if _CTA.search(t) or _PROMO_PRODUCT.search(t):
        return "SPINE_CTA_OR_PROMO"
    if not _VERB.search(t):
        return "SPINE_NO_VERB"
    return None


def build_episode_brief_v2(
    segments: Sequence[Mapping[str, Any]],
    *,
    metadata: Optional[Mapping[str, Any]] = None,
    enrichment: Optional[Mapping[str, Any]] = None,
    mode: str = "debug",
    transcript_context: Optional[str] = None,
    include_thesis: bool = True,
) -> Dict[str, Any]:
    """
    Single pipeline producing ``episode_brief_v2``. ``metadata`` should include
    authoritative ``genre`` / ``title`` from the workflow input (never overwritten here).
    """
    brief = empty_episode_brief_v2()
    fails: List[str] = []
    meta = dict(metadata) if isinstance(metadata, Mapping) else {}
    brief["metadata"] = meta
    brief["enrichment"] = dict(enrichment) if isinstance(enrichment, Mapping) else {"status": "not_provided"}

    segs = normalize_timestamped_segments(segments)
    seg_times = _seg_time_lookup(segs)
    blob = transcript_context or "\n\n".join(str(s.get("text") or "") for s in segs)

    cf = filter_claim_candidates(segs, transcript_context=blob, use_scoring=True, mode=mode if mode in ("debug", "production") else "debug")  # type: ignore[arg-type]

    tagged: List[Dict[str, Any]] = []
    idx = 0
    for row in cf.get("accepted_claims") or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        sid = str(row.get("source_segment_id") or "")
        typ, elig = classify_spine_row(
            text=text,
            decision=str(row.get("decision") or "ACCEPTED"),
            reason_codes=row.get("reason_codes"),
        )
        idx += 1
        cid = f"c_v2_{idx}"
        gate = spine_hard_gate({"text": text}) if elig else "FILTERED_INELIGIBLE"
        if elig and gate:
            typ, elig = "filler", False
        tagged.append(
            {
                "id": cid,
                "text": text,
                "type": typ,
                "is_spine_eligible": elig,
                "source_segment_id": sid,
                "timestamp": seg_times.get(sid, 0.0),
                "claim_score": row.get("claim_score"),
                "reason_codes": row.get("reason_codes"),
            }
        )
    for row in cf.get("rejected_claims") or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        sid = str(row.get("source_segment_id") or "")
        typ, _ = classify_spine_row(
            text=text,
            decision="REJECTED",
            reason_codes=row.get("reason_codes"),
        )
        tagged.append(
            {
                "id": None,
                "text": text,
                "type": typ,
                "is_spine_eligible": False,
                "source_segment_id": sid,
                "timestamp": seg_times.get(sid, 0.0),
                "claim_score": row.get("claim_score"),
                "reason_codes": row.get("reason_codes"),
                "rejection_reason": row.get("rejection_reason"),
            }
        )

    brief["claims"] = tagged
    spine = [c for c in tagged if c.get("is_spine_eligible") and c.get("id")]
    if len(spine) < MIN_SPINE_CLAIMS:
        fails.append("INSUFFICIENT_SPINE_MATERIAL")
        brief["status"] = {"is_shippable": False, "fail_reasons": fails}
        return brief

    texts = [str(c["text"]) for c in spine]
    comps_idx = structural_connected_components(texts)
    clusters_out: List[Dict[str, Any]] = []
    for comp in comps_idx:
        if len(comp) < MIN_CLUSTER_SIZE:
            continue
        members = [spine[i] for i in comp]
        sc = sum(float(m.get("claim_score") or 0) for m in members)
        clusters_out.append(
            {
                "claim_ids": [m["id"] for m in members],
                "score": len(members) * 0.1 + sc * 0.01,
                "size": len(members),
            }
        )
    brief["clusters"] = clusters_out

    if not clusters_out:
        fails.append("NO_DOMINANT_ARGUMENT")
        brief["status"] = {"is_shippable": False, "fail_reasons": fails}
        return brief

    main = max(clusters_out, key=lambda c: float(c.get("score") or 0))
    main_ids: Set[str] = set(main["claim_ids"])
    main_claims = [c for c in spine if c["id"] in main_ids]
    eval_map = {c["id"]: str(c["source_segment_id"]) for c in main_claims}

    evaluation: Dict[str, Any] = {
        "dominant_cluster_claim_ids": list(main_ids),
        "segment_ids": sorted({eval_map[cid] for cid in main_ids}),
        "claim_ids_missing_timestamp": [cid for cid in main_ids if seg_times.get(eval_map[cid], 0) <= 0],
    }
    brief["evaluation"] = evaluation

    thesis_payload: Optional[Dict[str, Any]] = None
    thesis_text: Optional[str] = None
    if include_thesis and len(main_claims) >= 3:
        thesis_payload = construct_thesis_v2(
            accepted_claims=main_claims,
            evaluation_map=eval_map,
            source_segments=segs,
            episode_metadata=None,
        )
        thesis_text = thesis_payload.get("thesis") if isinstance(thesis_payload, dict) else None
    elif include_thesis:
        fails.append("INSUFFICIENT_CLUSTER_FOR_THESIS")

    if thesis_text and not is_valid_thesis(thesis_text):
        fails.append(f"THESIS_INVALID:{thesis_validation_failure_reason(thesis_text)}")
        thesis_text = None
        if thesis_payload:
            thesis_payload = {**thesis_payload, "thesis": None, "generation_status": "UNSHIPPABLE"}

    brief["thesis"] = thesis_text
    brief["thesis_engine"] = thesis_payload

    if not evaluation["segment_ids"]:
        fails.append("LOW_EVIDENCE")
    elif len(evaluation["segment_ids"]) < 2 and thesis_text:
        fails.append("LOW_EVIDENCE")

    invalid_thesis = any(str(f).startswith("THESIS_INVALID") for f in fails)
    shippable = bool(
        thesis_text
        and len(spine) >= MIN_SPINE_CLAIMS
        and len(evaluation.get("segment_ids") or []) >= 2
        and not invalid_thesis
        and not any(f in ("LOW_EVIDENCE", "INSUFFICIENT_SPINE_MATERIAL", "NO_DOMINANT_ARGUMENT") for f in fails)
    )
    brief["status"] = {"is_shippable": shippable, "fail_reasons": fails}

    return brief


__all__ = [
    "MIN_SPINE_CLAIMS",
    "MIN_SPINE_WORDS",
    "MIN_CLUSTER_SIZE",
    "empty_episode_brief_v2",
    "classify_spine_row",
    "spine_hard_gate",
    "build_episode_brief_v2",
    "segments_from_transcript_for_brief_v2",
    "format_brief_v2_markdown_section",
]
