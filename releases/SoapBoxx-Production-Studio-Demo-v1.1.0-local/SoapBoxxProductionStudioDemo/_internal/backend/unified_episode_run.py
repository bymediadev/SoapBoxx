"""
Single **orchestrated** episode run: v3 report (brief + coach) + workflow JSON + one canonical bundle.

Use :func:`run_unified_episode_pipeline` when you want **one import, one call, one predictable dict**
instead of manually calling ``generate_episode_report_v3`` then ``soapboxx_v3_workflow_local`` and
merging fields in scripts or the Local Workflow.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

UNIFIED_BUNDLE_VERSION = "1"

_WORKFLOW_LIST_KEYS: Tuple[str, ...] = (
    "highlights",
    "follow_up_questions",
    "guest_recommendations",
    "segments",
    "analytics",
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def canonicalize_workflow_report(workflow_report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of ``workflow_report`` with **stable surface keys** (empty lists instead of missing).

    The workflow object is ``{"metadata": {...}, ...body}`` — body list fields are normalized here.
    """
    if not isinstance(workflow_report, dict):
        return {
            "metadata": {},
            "highlights": [],
            "evidence_map": [],
            "follow_up_questions": [],
            "guest_recommendations": [],
            "segments": [],
            "analytics": [],
        }
    out = dict(workflow_report)
    md = out.get("metadata")
    if not isinstance(md, dict):
        out["metadata"] = {}
    for k in _WORKFLOW_LIST_KEYS:
        v = out.get(k)
        if not isinstance(v, list):
            out[k] = []
    em = out.get("evidence_map")
    if not isinstance(em, list):
        out["evidence_map"] = []
    wc = out.get("weak_claims")
    if wc is not None and not isinstance(wc, list):
        out["weak_claims"] = []
    return out


def build_unified_episode_bundle(
    *,
    v3_out: Dict[str, Any],
    workflow_report: Dict[str, Any],
    transcript: str,
) -> Dict[str, Any]:
    """
    Merge ``generate_episode_report_v3`` output with ``soapboxx_v3_workflow_local`` output.

    **Canonical keys** (always present):

    - ``bundle_version``
    - ``report_v3``, ``brief``, ``episode_spine``
    - ``workflow_report`` (canonicalized)
    - ``markdown_v3``, ``markdown_network`` (v2 one-pager), ``markdown_export`` (final unified)
    - ``warnings`` (merged, de-duplicated)
    - ``meta`` (episode-facing subset)
    - ``pipeline`` (how the run was executed)
    - ``dialin`` (high-signal operator hints from :func:`episode_report_v3.dialin_production_warnings`)
    """
    wf = canonicalize_workflow_report(workflow_report)
    r3 = v3_out.get("report_v3") if isinstance(v3_out.get("report_v3"), dict) else {}
    brief = v3_out.get("brief") if isinstance(v3_out.get("brief"), dict) else {}
    spine = v3_out.get("episode_spine") if isinstance(v3_out.get("episode_spine"), dict) else {}

    wfv3 = v3_out.get("markdown_v3") or ""
    wfnet = v3_out.get("markdown") or ""
    md_unified = str(workflow_report.get("markdown_export") or v3_out.get("markdown_export") or "")

    w1: List[str] = [str(x).strip() for x in (v3_out.get("warnings") or []) if str(x).strip()]
    md_wf = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    w2 = [str(x).strip() for x in (md_wf.get("source_warnings") or []) if str(x).strip()]
    warnings = list(dict.fromkeys([*w1, *w2]))

    meta_out: Dict[str, Any] = {
        "generated_at": (v3_out.get("meta") or {}).get("generated_at") or md_wf.get("generated"),
        "title": (v3_out.get("meta") or {}).get("title") or md_wf.get("title"),
        "creator": (v3_out.get("meta") or {}).get("creator") or md_wf.get("creator"),
        "genre": (v3_out.get("meta") or {}).get("genre") or md_wf.get("genre"),
        "trace_id": md_wf.get("trace_id"),
        "workflow_mode": md_wf.get("workflow_mode"),
        "workflow_enrichment_tier": md_wf.get("workflow_enrichment_tier"),
        "export_status": md_wf.get("export_status"),
    }

    try:
        from .episode_report_v3 import dialin_production_warnings
    except ImportError:
        from episode_report_v3 import dialin_production_warnings  # type: ignore

    dialin = dialin_production_warnings({**v3_out, "workflow_report": workflow_report})

    pipeline = {
        "bundle_version": UNIFIED_BUNDLE_VERSION,
        "transcript_sha256": _sha256_text(transcript or ""),
        "transcript_chars": len(transcript or ""),
        "layers": ["generate_episode_report_v3", "soapboxx_v3_workflow_local"],
        "workflow_mode": md_wf.get("workflow_mode"),
        "workflow_enrichment_tier": md_wf.get("workflow_enrichment_tier"),
        "structured_intelligence_source": (r3.get("meta") or {}).get("structured_intelligence_source"),
        "report_v3_output_mode": str(r3.get("output_mode") or ""),
        "signal_mode": str(r3.get("signal_mode") or ""),
    }

    return {
        "bundle_version": UNIFIED_BUNDLE_VERSION,
        "report_v3": r3,
        "brief": brief,
        "episode_spine": spine,
        "workflow_report": wf,
        "markdown_v3": wfv3,
        "markdown_network": wfnet,
        "markdown_export": md_unified,
        "warnings": warnings,
        "meta": meta_out,
        "pipeline": pipeline,
        "dialin": dialin,
        "model": v3_out.get("model"),
        "workflow_version": v3_out.get("workflow_version"),
    }


def run_unified_episode_pipeline(
    transcript: str,
    metadata: Optional[Dict[str, Any]] = None,
    *,
    strict_references: bool = True,
    include_v2_markdown: bool = True,
    atomic_ground_truth: Optional[bool] = None,
    validate_workflow: bool = True,
    workflow_strict_references: bool = False,
    client: Any = None,
    use_new_api: bool = True,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    One call: ``generate_episode_report_v3`` → ``soapboxx_v3_workflow_local`` → :func:`build_unified_episode_bundle`.

    ``metadata`` may include non-string values (e.g. ``trace_id``); string fields are passed into v3
    generation, the full mapping into workflow.
    """
    meta_any: Dict[str, Any] = dict(metadata or {})
    meta_str = {k: ("" if v is None else str(v)) for k, v in meta_any.items()}

    try:
        from .episode_report_v3 import generate_episode_report_v3
        from .soapboxx_v3_workflow import soapboxx_v3_workflow_local
    except ImportError:
        from episode_report_v3 import generate_episode_report_v3  # type: ignore
        from soapboxx_v3_workflow import soapboxx_v3_workflow_local  # type: ignore

    v3_out = generate_episode_report_v3(
        transcript or "",
        meta_str,
        client=client,
        use_new_api=use_new_api,
        api_key=api_key,
        strict_references=strict_references,
        include_v2_markdown=include_v2_markdown,
        atomic_ground_truth=atomic_ground_truth,
    )
    wf = soapboxx_v3_workflow_local(
        transcript or "",
        meta_any,
        validate=validate_workflow,
        strict_references=workflow_strict_references,
        client=client,
        report_v3=v3_out.get("report_v3") or {},
        brief_warnings=v3_out.get("warnings"),
    )
    return build_unified_episode_bundle(
        v3_out=v3_out,
        workflow_report=wf,
        transcript=transcript or "",
    )


__all__ = [
    "UNIFIED_BUNDLE_VERSION",
    "build_unified_episode_bundle",
    "canonicalize_workflow_report",
    "run_unified_episode_pipeline",
]
