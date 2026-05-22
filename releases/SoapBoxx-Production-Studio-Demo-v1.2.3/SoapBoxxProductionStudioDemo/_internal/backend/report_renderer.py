"""
Human-facing report views over evaluation output.

Presentation only: does not compute scores, decisions, or retries. Pass in the same
structures written by :func:`evaluation_pipeline.finalize_evaluation` (plus optional
``report_v3`` / ``workflow_report`` for insights).

Insights are taken from ``report_v3.clean_insights`` then ``workflow_report.highlights``,
in source order, **deduped** and capped (no second ranking pass here).
Optional **editorial profiles** label how copy is tuned; see :func:`resolve_editorial_profile_key`.

Outbound client-ready exports use :func:`generate_client_report` (locked five-field dict;
no schema or diagnostics). Internal or analyst views use :func:`render_report`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

try:
    from .editorial_registry import (
        DEFAULT_EDITORIAL_PROFILES,
        get_merged_registry,
        registry_profile_for_meta,
    )
    from .system_contracts import REPORT_OUTPUT_SCHEMA_VERSION, SYSTEM_VERSION
except ImportError:
    from editorial_registry import (  # type: ignore
        DEFAULT_EDITORIAL_PROFILES,
        get_merged_registry,
        registry_profile_for_meta,
    )
    from system_contracts import REPORT_OUTPUT_SCHEMA_VERSION, SYSTEM_VERSION  # type: ignore

REPORT_SCHEMA_VERSION = REPORT_OUTPUT_SCHEMA_VERSION

# ---------------------------------------------------------------------------
# Editorial profiles (presentation-only): registry + mode (no scoring).
# ---------------------------------------------------------------------------

_VALID_PROFILES = frozenset({"balanced", "interview", "solo", "news", "narrative"})


@dataclass(frozen=True)
class EditorialWeights:
    """Multipliers for additive components of the insight ranker (not ML scores)."""

    highlight_flat: float
    highlight_struct: float  # scales workflow highlight timestamp / evidence bonus
    list_order: float
    length_sweet: float
    length_long_penalty: float
    tension: float
    thesis: float
    topic: float
    audio_penalty: float


# ``balanced`` matches the original single-profile heuristic.
EDITORIAL_WEIGHTS: Dict[str, EditorialWeights] = {
    "balanced": EditorialWeights(
        highlight_flat=0.42,
        highlight_struct=1.0,
        list_order=1.0,
        length_sweet=0.22,
        length_long_penalty=0.08,
        tension=0.07,
        thesis=0.35,
        topic=0.22,
        audio_penalty=0.35,
    ),
    # Guest + host: favour thesis/topic anchoring; dial back pure “drama” cues slightly.
    "interview": EditorialWeights(
        highlight_flat=0.48,
        highlight_struct=1.12,
        list_order=1.0,
        length_sweet=0.24,
        length_long_penalty=0.08,
        tension=0.05,
        thesis=0.46,
        topic=0.30,
        audio_penalty=0.35,
    ),
    # Monologue / single-voice: hooks and tension matter more than topic overlap.
    "solo": EditorialWeights(
        highlight_flat=0.38,
        highlight_struct=1.0,
        list_order=1.05,
        length_sweet=0.22,
        length_long_penalty=0.09,
        tension=0.095,
        thesis=0.38,
        topic=0.18,
        audio_penalty=0.35,
    ),
    # Fast headline-style: topic + conflict framing; tight clips.
    "news": EditorialWeights(
        highlight_flat=0.45,
        highlight_struct=1.08,
        list_order=0.95,
        length_sweet=0.2,
        length_long_penalty=0.07,
        tension=0.085,
        thesis=0.30,
        topic=0.34,
        audio_penalty=0.35,
    ),
    "narrative": EditorialWeights(
        highlight_flat=0.42,
        highlight_struct=1.0,
        list_order=1.0,
        length_sweet=0.22,
        length_long_penalty=0.08,
        tension=0.07,
        thesis=0.35,
        topic=0.22,
        audio_penalty=0.35,
    ),
}


def _read_profile_mode(evaluation_result: Dict[str, Any]) -> str:
    for blob in (
        evaluation_result.get("editorial_profile_mode"),
        (evaluation_result.get("meta") or {}).get("editorial_profile_mode")
        if isinstance(evaluation_result.get("meta"), dict)
        else None,
    ):
        if isinstance(blob, str) and blob.strip().lower() in ("auto", "fixed"):
            return blob.strip().lower()
    r3 = evaluation_result.get("report_v3")
    if isinstance(r3, dict):
        m = r3.get("editorial_profile_mode")
        if isinstance(m, str) and m.strip().lower() in ("auto", "fixed"):
            return m.strip().lower()
    return "auto"


def _normalize_profile_key(key: str) -> str:
    k = str(key or "").strip().lower()
    if k in EDITORIAL_WEIGHTS:
        return k
    return "balanced"


def resolve_editorial_profile_key(evaluation_result: Dict[str, Any]) -> str:
    """
    Resolve which profile to use (deterministic).

    **fixed** mode: never infers from title/genre; uses explicit profile, then
    :mod:`editorial_registry` lookup (``podcast_id``, ``show_slug``, ``show_format``, …),
    then :data:`editorial_registry.DEFAULT_EDITORIAL_PROFILES` + optional JSON overlay.

    **auto** mode: same explicit/registry rules, then light genre/title inference.
    """
    mode = _read_profile_mode(evaluation_result)
    meta = evaluation_result.get("meta") if isinstance(evaluation_result.get("meta"), dict) else {}
    merged = get_merged_registry()
    registry_hit = registry_profile_for_meta(meta, merged)

    for blob in (
        evaluation_result.get("editorial_profile"),
        meta.get("editorial_profile"),
        (evaluation_result.get("report_v3") or {}).get("editorial_profile")
        if isinstance(evaluation_result.get("report_v3"), dict)
        else None,
    ):
        if blob is None:
            continue
        key = str(blob).strip().lower()
        if key in _VALID_PROFILES:
            return _normalize_profile_key(key)

    if mode == "fixed":
        if registry_hit:
            return _normalize_profile_key(registry_hit)
        return "balanced"

    if registry_hit:
        return _normalize_profile_key(registry_hit)

    r3 = evaluation_result.get("report_v3")
    if isinstance(r3, dict):
        snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
        genre = str(snap.get("genre") or "").lower()
        title = str(snap.get("title") or "").lower()
        blob = f"{genre} {title}"
        if "interview" in blob or "conversation with" in blob:
            return "interview"
        if "news" in genre or "headline" in genre or "breaking" in title:
            return "news"
        if "solo" in genre or "monologue" in blob:
            return "solo"

    return "balanced"


def get_editorial_weights(profile_key: str) -> EditorialWeights:
    k = str(profile_key or "balanced").strip().lower()
    if k not in EDITORIAL_WEIGHTS:
        k = "balanced"
    return EDITORIAL_WEIGHTS[k]


# Mirrors ``decision_engine.DecisionTier`` values — string-only to avoid importing policy logic.
_TIER_SUMMARY = {
    "reject_input": "The material wasn’t strong enough to produce a full analysis.",
    "retry_extraction": "We couldn’t reliably pull out the main ideas from this episode.",
    "retry_grounding": "We found ideas but couldn’t tie them tightly to the tape.",
    "low_confidence": "Findings are useful but some parts are uncertain.",
    "accept_moderate": "You get solid, usable takeaways from this episode.",
    "accept_strong": "The takeaways are clear and well supported.",
    "highlight": "This episode stands out as especially strong material.",
}

_TIER_VERDICT_TITLE = {
    "reject_input": "Not enough usable input",
    "retry_extraction": "Could not reliably extract key ideas",
    "retry_grounding": "Ideas could not be fully validated against the tape",
    "low_confidence": "Some uncertainty in findings",
    "accept_moderate": "Decent quality insights",
    "accept_strong": "Strong, reliable insights",
    "highlight": "High-quality standout content",
}

_TIER_VERDICT_DETAIL = {
    "reject_input": "Upload a longer or cleaner transcript, or pick a segment with clearer speech.",
    "retry_extraction": "Try again after captions or transcript quality improve, or enable enrichment if available.",
    "retry_grounding": "More timestamped quotes or clearer claims will help lock findings to the recording.",
    "low_confidence": "Treat specifics as directional until grounding improves.",
    "accept_moderate": "Safe to use for planning; tighten clips if you need punchier moments.",
    "accept_strong": "Good basis for clips, positioning, and follow-up planning.",
    "highlight": "Prioritize this one for clips, packaging, or promotion.",
}


def _reliability_sentence(transport_degraded: bool, tier: str) -> str:
    if transport_degraded:
        return "Reliability is reduced because processing hit infrastructure limits—re-run when the system is healthy."
    if tier in ("reject_input", "retry_extraction", "retry_grounding"):
        return "Trust this as guidance on what to fix next, not as a scored audit."
    if tier == "low_confidence":
        return "Trust the direction; double-check specifics on the tape."
    return "You can treat this read as consistent with what’s on the transcript."


def _iqs_band(x: float) -> str:
    if x < 0.35:
        return "failed"
    if x < 0.65:
        return "weak"
    return "good"


def _extraction_band(x: float) -> str:
    if x < 0.35:
        return "failed"
    if x < 0.55:
        return "weak"
    return "good"


def _grounding_band(x: float) -> str:
    if x < 0.28:
        return "missing"
    if x < 0.52:
        return "weak"
    return "strong"


def _quality_breakdown(components: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not isinstance(components, dict):
        return {
            "input_quality": "unknown",
            "extraction": "unknown",
            "grounding": "unknown",
        }
    iqs = float(components.get("input_quality_score") or 0.0)
    ex = float(components.get("extraction_success_score") or 0.0)
    gd = float(components.get("grounding_density_score") or 0.0)
    return {
        "input_quality": _iqs_band(iqs),
        "extraction": _extraction_band(ex),
        "grounding": _grounding_band(gd),
    }


def _norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip().lower())[:200]


def _limit_sentences(text: str, max_sentences: int = 2) -> str:
    """At most ``max_sentences`` sentences (readability contract)."""
    t = str(text).strip()
    if not t:
        return t
    parts = re.split(r"(?<=[.!?])\s+", t)
    parts = [p.strip() for p in parts if p.strip()]
    if len(parts) <= max_sentences:
        return " ".join(parts)
    return " ".join(parts[:max_sentences]).strip()


def _assemble_insights_from_sources(evaluation_result: Dict[str, Any], limit: int = 7) -> List[str]:
    """
    Merge ``clean_insights`` then ``workflow_report.highlights`` insight text, preserve order,
    dedupe by normalized text, cap ``limit`` (always 7 for production reports).
    """
    out: List[str] = []
    seen: Set[str] = set()

    r3 = evaluation_result.get("report_v3")
    if isinstance(r3, dict):
        for x in r3.get("clean_insights") or []:
            s = str(x).strip()
            if not s:
                continue
            k = _norm_key(s)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(s)
            if len(out) >= limit:
                return out

    wf = evaluation_result.get("workflow_report")
    if isinstance(wf, dict):
        for h in wf.get("highlights") or []:
            if not isinstance(h, dict):
                continue
            s = str(h.get("insight") or "").strip()
            if not s:
                continue
            k = _norm_key(s)
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
            if len(out) >= limit:
                break
    return out[:limit]


def _scrub_internal_insight_lines(lines: List[str]) -> List[str]:
    """Drop lines that look like internal routing / debug (readability contract)."""
    block = ("retry_routing", "path_taken", "metrics_ref", "should_retry_any")
    out: List[str] = []
    for s in lines:
        low = s.lower()
        if any(b in low for b in block):
            continue
        out.append(s)
    return out


def _read_render_mode(evaluation_result: Dict[str, Any]) -> str:
    for blob in (
        evaluation_result.get("render_mode"),
        (evaluation_result.get("meta") or {}).get("render_mode")
        if isinstance(evaluation_result.get("meta"), dict)
        else None,
    ):
        if isinstance(blob, str) and blob.strip().lower() in ("analyst", "reader", "sales"):
            return blob.strip().lower()
    # Safe default for internal tooling/debugging.
    # Client-facing channels should pass ``render_mode=sales`` explicitly.
    return "analyst"


def _episode_identity(evaluation_result: Dict[str, Any]) -> Dict[str, str]:
    """Best-effort title/creator/genre for client-facing copy (no hard dependencies)."""
    title = ""
    creator = ""
    genre = ""
    meta = evaluation_result.get("meta") if isinstance(evaluation_result.get("meta"), dict) else {}
    if meta:
        title = str(meta.get("title") or meta.get("episode_title") or "").strip()
        creator = str(meta.get("creator") or meta.get("creator_name") or "").strip()
        genre = str(meta.get("genre") or "").strip()
    r3 = evaluation_result.get("report_v3")
    if isinstance(r3, dict):
        snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
        title = title or str(snap.get("title") or "").strip()
        creator = creator or str(snap.get("creator") or "").strip()
        genre = genre or str(snap.get("genre") or "").strip()
    return {"title": title, "creator": creator, "genre": genre}


def _sales_core_insight(tier: str, qb: Dict[str, str]) -> str:
    # Value-first framing: “what this is optimized for”
    if tier in ("reject_input", "retry_extraction"):
        return "This episode is optimized for passive listening, not audience growth."
    if tier in ("retry_grounding", "low_confidence"):
        return "This episode has useful ideas, but it’s not yet packaged in a way that creates clear shareable moments."
    if tier in ("accept_moderate",):
        return "This episode is close to a growth-friendly format, but it needs sharper structure and stronger clip anchors."
    return "This episode contains strong material that can be turned into reliable growth assets with light packaging work."


def _sales_limiters(tier: str, qb: Dict[str, str]) -> List[str]:
    out: List[str] = []
    # Use band labels to choose non-technical language.
    if tier in ("reject_input",):
        out.append("Key moments are hard to identify consistently, which reduces clip potential and discoverability.")
        out.append("The structure doesn’t surface clear “chapter” moments, so the episode is harder to package.")
        return out
    if qb.get("extraction") in ("failed", "weak") or tier == "retry_extraction":
        out.append("There isn’t a clear through-line or segment structure, so ideas don’t build toward moments.")
        out.append("Without defined segments, it’s harder to create chapters, hooks, and titles that drive clicks.")
    if qb.get("grounding") in ("missing", "weak") or tier in ("retry_grounding", "low_confidence"):
        out.append("There are few quotable, clip-worthy statements that stand alone in a short cut.")
        out.append("Abstract points aren’t anchored with enough examples or stories to be shareable.")
    if not out:
        out.append("The episode has solid substance; the main upside is packaging it into a repeatable growth format.")
    return out[:3]


def _sales_fixes(tier: str, qb: Dict[str, str]) -> List[str]:
    fixes: List[str] = []
    fixes.append("Add a clear thesis in the first 60 seconds: “This episode is about X, and here’s why it matters.”")
    fixes.append("Break the episode into 2–3 named segments (chapters) so it produces natural clip moments.")
    fixes.append("Anchor each abstract idea with a concrete story or example every 5–7 minutes.")
    if tier in ("reject_input", "retry_extraction") and qb.get("input_quality") in ("failed", "weak"):
        fixes.insert(0, "Improve transcript/caption quality (or record cleaner audio) so strong moments are extractable.")
    return fixes[:3]


def _sales_cta() -> str:
    return (
        "If you want, I can restructure one episode into a clip-ready outline and show exactly how to turn it into growth content."
    )


def _sales_confidence_label(tier: str, transport_degraded: bool, qb: Dict[str, str]) -> str:
    if transport_degraded:
        return "reduced"
    if tier in ("reject_input", "retry_extraction", "retry_grounding"):
        return "low"
    if tier == "low_confidence":
        return "medium"
    return "high"


REQUIRED_REPORT_OUTPUT_KEYS = frozenset(
    {
        "summary",
        "verdict",
        "insights",
        "quality_breakdown",
        "issues",
        "system_notes",
        "system_version",
        "schema_version",
    }
)


def validate_report_output(report: Dict[str, Any]) -> None:
    """Raise if the public report dict does not satisfy ``report_output_schema_v1``."""
    missing = REQUIRED_REPORT_OUTPUT_KEYS - frozenset(report.keys())
    if missing:
        raise ValueError(f"report_output_schema_v1 missing keys: {sorted(missing)}")


# Outbound client contract (sales / growth memo export): human fields only, fixed shape.
CLIENT_REPORT_KEYS = frozenset({"summary", "issues", "insights", "clips", "cta"})

_FORBIDDEN_CLIENT_KEY_TOKEN = (
    "claims",
    "verification",
    "segments",
    "analytics",
    "trace",
    "pipeline",
    "schema_version",
    "system_version",
    "quality_warnings",
    "_quality",
    "internal_score",
)


def validate_client_report(report: Dict[str, Any]) -> None:
    """Raise if the client export dict is not the locked five-field shape."""
    keys = frozenset(report.keys())
    if keys != CLIENT_REPORT_KEYS:
        raise ValueError(f"client_report_schema: expected keys {sorted(CLIENT_REPORT_KEYS)}, got {sorted(keys)}")
    for k in report.keys():
        lk = str(k).lower()
        if any(tok in lk for tok in _FORBIDDEN_CLIENT_KEY_TOKEN):
            raise ValueError(f"client_report_schema: forbidden key token in {k!r}")


def _client_simplified_mode(evaluation_result: Dict[str, Any]) -> bool:
    """
    Low-signal / thin-structure episodes: one insight, one clip, no expansion.
    Uses ``report_v3.signal_mode``, decision tier, narrative_reconstruction substance, and segment count.
    """
    r3 = evaluation_result.get("report_v3") if isinstance(evaluation_result.get("report_v3"), dict) else {}
    if str(r3.get("signal_mode") or "").strip().upper() == "LOW_SIGNAL":
        return True
    decision = evaluation_result.get("decision") if isinstance(evaluation_result.get("decision"), dict) else {}
    tier = str(decision.get("tier") or "").strip()
    if tier in ("reject_input", "retry_extraction"):
        return True
    nr = r3.get("narrative_reconstruction") if isinstance(r3.get("narrative_reconstruction"), dict) else {}
    parts = [
        str(nr.get("core_thesis") or "").strip(),
        str(nr.get("supporting_mechanism") or "").strip(),
        str(nr.get("practical_translation") or "").strip(),
    ]
    substantive = [p for p in parts if len(p) >= 24]
    if len(substantive) < 2:
        return True
    segs = r3.get("segments")
    if isinstance(segs, list) and len(segs) < 2:
        return True
    return False


def _first_idea_clip_line(s: str) -> str:
    """At most one punchy idea per clip line (first sentence / clause)."""
    t = str(s).strip()
    if not t:
        return t
    parts = re.split(r"(?<=[.!?])\s+", t)
    one = parts[0].strip() if parts else t
    if ";" in one:
        one = one.split(";")[0].strip()
    if " — " in one:
        one = one.split(" — ")[0].strip()
    return _truncate(one, 200)


def _insight_pool_for_client(evaluation_result: Dict[str, Any]) -> List[str]:
    raw = _assemble_insights_from_sources(evaluation_result, limit=12)
    return [_truncate(x, 220) for x in _scrub_internal_insight_lines(raw)]


def _truncate(s: str, max_chars: int = 220) -> str:
    s = s.strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1].rstrip() + "…"


def _issues_for_tier(tier: str, transport_degraded: bool) -> List[str]:
    issues: List[str] = []
    if tier == "reject_input":
        issues.append("There wasn’t enough usable transcript or structure to score this like a full episode review.")
    elif tier == "retry_extraction":
        issues.append("The tool couldn’t reliably extract claims and themes from the text you provided.")
    elif tier == "retry_grounding":
        issues.append("Claims and quotes didn’t line up tightly enough for a confident audit.")
    elif tier == "low_confidence":
        issues.append("Some findings may feel thin until quotes and segments are stronger.")
    if transport_degraded and tier not in ("reject_input",):
        issues.append("The analysis may be incomplete because enrichment or transport was degraded.")
    return issues


def render_report(evaluation_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a human-readable report skeleton from evaluation-shaped data.

    Expected keys (all optional except what you have):
    - ``decision``: dict from finalized metadata (``tier``, ``message`` — no trace in this output)
    - ``input_quality_components``: float metrics (used only to derive *bands*, not shown)
    - ``report_v3``, ``workflow_report``: optional sources for insight bullets
    - ``editorial_profile`` / ``editorial_profile_mode`` / ``render_mode``: presentation toggles

    Does **not** call the decision engine or change scores.

    Returns v1 fields including ``system_version`` / ``schema_version``; optional ``insight_roles``
    for UI. Does not expose raw scores, thresholds, or routing hints.

    Identity alignment runs in :func:`episode_report_v3.apply_identity_consistency_to_report_v3`
    at **v3 build time only** — not here — so render cannot silently diverge from a second pass.
    Claim substrate (:func:`claim_quality_gate.apply_claim_quality_gate`) and semantic grounding
    (:func:`semantic_grounding_validator.apply_semantic_grounding_validator`) run after identity in
    :func:`episode_report_v3.build_v3_report` (quality stamp, then lexical tie to claims) before
    guest trace and export.
    """
    editorial_profile = resolve_editorial_profile_key(evaluation_result)
    editorial_profile_mode = _read_profile_mode(evaluation_result)
    render_mode = _read_render_mode(evaluation_result)

    decision = evaluation_result.get("decision")
    if not isinstance(decision, dict):
        decision = {}

    tier = str(decision.get("tier") or "accept_moderate").strip()
    if tier not in _TIER_SUMMARY:
        tier = "accept_moderate"

    trace = decision.get("trace") if isinstance(decision.get("trace"), dict) else {}
    transport_degraded = bool(decision.get("transport_degraded") or trace.get("transport_degraded"))

    summary_a = _TIER_SUMMARY.get(tier, _TIER_SUMMARY["accept_moderate"])
    summary_b = _reliability_sentence(transport_degraded, tier)
    summary = _limit_sentences(f"{summary_a} {summary_b}", 2)

    verdict_title = _TIER_VERDICT_TITLE.get(tier, tier)
    verdict_detail = _TIER_VERDICT_DETAIL.get(tier, "")
    verdict = f"**{verdict_title}** — {verdict_detail}".strip()

    metrics_ref = str(decision.get("metrics_ref") or "input_quality_components")
    components = evaluation_result.get(metrics_ref)
    if components is None:
        components = evaluation_result.get("input_quality_components")

    quality_breakdown = _quality_breakdown(components if isinstance(components, dict) else None)

    # SALES MODE (default): value-first client-facing growth memo.
    if render_mode == "sales":
        ident = _episode_identity(evaluation_result)
        name = ident.get("creator") or "Podcast"
        title = ident.get("title") or ""
        header = f"Podcast Growth Breakdown — {name}".strip()
        if title:
            header = f"{header} ({title})"

        core = _sales_core_insight(tier, quality_breakdown)
        summary = _limit_sentences(core, 2)

        limiters = _sales_limiters(tier, quality_breakdown)
        fixes = _sales_fixes(tier, quality_breakdown)

        verdict = f"**{header}**\n\n**Opportunity:** {core}\n\n**CTA:** {_sales_cta()}"
        insights = [_truncate(x, 220) for x in fixes][:7]

        # Use schema fields but keep them client-facing (no internal jargon).
        issues = [_truncate(x, 220) for x in limiters]
        system_notes = None
        if transport_degraded:
            system_notes = "Processing was degraded; re-run for a more complete read."
        quality_breakdown = {
            "confidence": _sales_confidence_label(tier, transport_degraded, quality_breakdown),
            "focus": editorial_profile,
        }
        report: Dict[str, Any] = {
            "summary": summary,
            "verdict": verdict,
            "insights": insights,
            "quality_breakdown": quality_breakdown,
            "issues": issues,
            "system_notes": system_notes,
            "system_version": SYSTEM_VERSION,
            "schema_version": REPORT_SCHEMA_VERSION,
            "editorial_profile": editorial_profile,
            "editorial_profile_mode": editorial_profile_mode,
            "render_mode": render_mode,
        }
        validate_report_output(report)
        return report

    # ANALYST/READER MODE: internal diagnostic-friendly copy (previous behavior).
    raw_insights = _assemble_insights_from_sources(evaluation_result, limit=7)
    insights = [_truncate(x, 220) for x in _scrub_internal_insight_lines(raw_insights)]
    insight_roles: List[str] = []
    if insights:
        insight_roles.append("lead")
        insight_roles.extend(["supporting"] * (len(insights) - 1))

    issues = _issues_for_tier(tier, transport_degraded)

    system_notes: Optional[str] = None
    if transport_degraded:
        system_notes = (
            "Processing completed, but the system was degraded (for example model transport). "
            "Re-run when possible for a more complete read."
        )

    if render_mode == "reader":
        if tier not in ("reject_input", "retry_extraction", "retry_grounding"):
            issues = []
        if not transport_degraded:
            system_notes = None

    report: Dict[str, Any] = {
        "summary": summary,
        "verdict": verdict,
        "insights": insights,
        "insight_roles": insight_roles,
        "editorial_profile": editorial_profile,
        "editorial_profile_mode": editorial_profile_mode,
        "render_mode": render_mode,
        "quality_breakdown": quality_breakdown,
        "issues": issues,
        "system_notes": system_notes,
        "system_version": SYSTEM_VERSION,
        "schema_version": REPORT_SCHEMA_VERSION,
    }
    validate_report_output(report)
    return report


def render_report_markdown(report: Dict[str, Any]) -> str:
    """Optional: turn :func:`render_report` output into compact Markdown for export or UI."""
    reader = str(report.get("render_mode") or "").strip().lower() == "reader"
    sales = str(report.get("render_mode") or "").strip().lower() == "sales"
    lines: List[str] = [
        "## Summary",
        "",
        str(report.get("summary") or "").strip(),
        "",
    ]
    if sales:
        # In sales mode, verdict already contains a formatted memo block.
        lines.extend(["## Growth memo", "", str(report.get("verdict") or "").strip(), ""])
    else:
        lines.extend(["## Verdict", "", str(report.get("verdict") or "").strip(), ""])
    ep = report.get("editorial_profile")
    if isinstance(ep, str) and ep.strip():
        lines.extend([f"*Editorial preset: {ep.strip()}.*", ""])
    insights = report.get("insights") if isinstance(report.get("insights"), list) else []
    if insights:
        if sales:
            lines.extend(["## Quick fixes", ""])
            for ins in insights[:7]:
                lines.append(f"- {str(ins).strip()}")
            lines.append("")
        else:
            lead = insights[0]
            rest = insights[1:]
            lines.extend(["## Key insights", "", "### Lead takeaway", "", lead, ""])
            if rest:
                lines.extend(["### Also notable", ""])
                for ins in rest:
                    lines.append(f"- {ins}")
                lines.append("")

    iss = report.get("issues") if isinstance(report.get("issues"), list) else []
    if iss and sales:
        lines.extend(["## What’s limiting growth", ""])
        for it in iss[:3]:
            lines.append(f"- {str(it).strip()}")
        lines.append("")

    qb = report.get("quality_breakdown")
    if not reader and isinstance(qb, dict) and qb:
        if sales:
            # Keep this lightweight and non-technical.
            conf = str(qb.get("confidence") or "—").strip()
            lines.extend(["## Confidence", "", f"- **Confidence:** {conf}", ""])
        else:
            lines.extend(
                [
                    "## Quality breakdown",
                    "",
                    f"- **Input quality:** {qb.get('input_quality', '—')}",
                    f"- **Extraction:** {qb.get('extraction', '—')}",
                    f"- **Grounding:** {qb.get('grounding', '—')}",
                    "",
                ]
            )
    if not sales:
        if iss:
            lines.extend(["## Issues", ""])
            for it in iss:
                lines.append(f"- {it}")
            lines.append("")

    sn = report.get("system_notes")
    if isinstance(sn, str) and sn.strip():
        lines.extend(["## System notes", "", sn.strip(), ""])

    return "\n".join(lines).strip() + "\n"


def generate_client_report(evaluation_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Single outbound entry point: **locked client shape** (no schema_version, trace, or diagnostics).

    Fields: ``summary``, ``issues`` (growth blockers), ``insights`` (2–4, or 1 in simplified mode),
    ``clips`` (2–3, or 1 in simplified mode; derived only from the insight pool), ``cta``.

    Insight order is :func:`_assemble_insights_from_sources` (``clean_insights`` then
    ``workflow_report.highlights``), deduped — no re-ranking.
    """
    ev = dict(evaluation_result or {})
    ev["render_mode"] = "sales"
    inner = render_report(ev)

    simplified = _client_simplified_mode(ev)
    pool = _insight_pool_for_client(ev)

    decision = ev.get("decision") if isinstance(ev.get("decision"), dict) else {}
    tier = str(decision.get("tier") or "accept_moderate").strip()
    if tier not in _TIER_SUMMARY:
        tier = "accept_moderate"
    metrics_ref = str(decision.get("metrics_ref") or "input_quality_components")
    components = ev.get(metrics_ref)
    if components is None:
        components = ev.get("input_quality_components")
    qb = _quality_breakdown(components if isinstance(components, dict) else None)

    summary = str(inner.get("summary") or "").strip()
    issues = [str(x).strip() for x in (inner.get("issues") or []) if str(x).strip()]
    cta = _sales_cta()

    if simplified:
        if pool:
            insights_out = pool[:1]
        elif summary:
            insights_out = [summary[:220]]
        else:
            insights_out = [_truncate(_sales_core_insight(tier, qb), 220)]
        clips_out = [_first_idea_clip_line(insights_out[0])] if insights_out else []
    else:
        if len(pool) >= 2:
            insights_out = pool[: min(4, len(pool))]
        elif len(pool) == 1:
            insights_out = pool[:1]
        else:
            fixes = [_truncate(x, 220) for x in _sales_fixes(tier, qb)]
            insights_out = fixes[:2] if fixes else ([summary[:220]] if summary else [_truncate(_sales_core_insight(tier, qb), 220)])
        n_clip = min(
            3,
            (max(2, len(insights_out)) if len(insights_out) >= 2 else len(insights_out)),
        )
        src = pool if pool else insights_out
        clips_out = [_first_idea_clip_line(x) for x in src[:n_clip]]

    client: Dict[str, Any] = {
        "summary": summary,
        "issues": issues[:4],
        "insights": insights_out,
        "clips": clips_out,
        "cta": cta,
    }
    validate_client_report(client)
    return client


def generate_client_report_markdown(evaluation_result: Dict[str, Any]) -> str:
    """Markdown for :func:`generate_client_report` (locked client shape — not :func:`render_report`)."""
    r = generate_client_report(evaluation_result)
    lines: List[str] = [
        "## Summary",
        "",
        str(r.get("summary") or "").strip(),
        "",
        "## What’s limiting growth",
        "",
    ]
    for it in r.get("issues") or []:
        lines.append(f"- {str(it).strip()}")
    lines.extend(["", "## Insights", ""])
    for ins in r.get("insights") or []:
        lines.append(f"- {str(ins).strip()}")
    lines.extend(["", "## Clip ideas", ""])
    for cl in r.get("clips") or []:
        lines.append(f"- {str(cl).strip()}")
    lines.extend(["", "## Call to action", "", str(r.get("cta") or "").strip(), ""])
    return "\n".join(lines).strip() + "\n"
