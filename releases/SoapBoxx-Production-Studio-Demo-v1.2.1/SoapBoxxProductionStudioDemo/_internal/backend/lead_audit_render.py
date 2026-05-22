"""
Lead-facing 1-page Markdown “cold outreach audit” from an existing v3 bundle.

No extra LLM calls: maps strategist-shaped data (or honest insufficient-signal copy)
into a short, email/screenshot-friendly card.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from episode_report_v3 import (
    _derive_strategist_report_from_bundle,
    evidence_mapping_row_is_export_grounded,
    evidence_row_is_export_grounded,
    strategist_truth_gate_bundle,
)


def _snapshot_and_meta(bundle: Dict[str, Any]) -> Tuple[str, str]:
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    snap = dict(r3.get("episode_snapshot") or {})
    meta = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    show = str(snap.get("creator") or meta.get("creator") or "—").strip() or "—"
    ep = str(snap.get("title") or meta.get("title") or "—").strip() or "—"
    return show, ep


def _looks_like_caption_noise(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return True
    low = t.lower()
    if "gt;" in low or "&gt;" in low or "&nbsp;" in low:
        return True
    if t.count(">>") >= 2:
        return True
    if t in ("—", "-", "..."):
        return True
    return False


def _working_bullets_from_bundle(bundle: Dict[str, Any], limit: int = 3) -> List[str]:
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    out: List[str] = []
    for h in wf.get("highlights") or []:
        if isinstance(h, dict):
            s = str(h.get("insight") or "").strip()
            if s and not _looks_like_caption_noise(s):
                out.append(s)
        if len(out) >= limit:
            return out[:limit]
    for x in r3.get("clean_insights") or []:
        s = str(x).strip()
        if s and s not in out and not _looks_like_caption_noise(s):
            out.append(s)
        if len(out) >= limit:
            break
    return out[:limit]


def _structure_state_from_bundle(bundle: Dict[str, Any]) -> str:
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    return str(wmeta.get("structure_state") or "").upper().strip()


def _weak_structure_line(bundle: Dict[str, Any]) -> str:
    if _structure_state_from_bundle(bundle) == "WEAK":
        return "⚠️ Weak structure: partial signal extracted, selection layer not fully activated."
    return ""


def _trim_for_card(s: str, max_chars: int = 200) -> str:
    t = " ".join((s or "").split())
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


# Bias anchor pick toward tension / pivot language (memorable in outreach), not just “longest quote”.
_CONTRAST_SHIFT_NEEDLES: Tuple[str, ...] = (
    " but ",
    " however",
    " although",
    " though ",
    " instead",
    " yet ",
    " actually ",
    " still ",
    " unlike ",
    " contrary ",
    " opposite ",
    " rather than ",
    " on the other hand",
)


def _contrast_shift_score(claim: str, evidence: str) -> int:
    blob = f" {claim} {evidence} ".lower()
    n = 0
    for needle in _CONTRAST_SHIFT_NEEDLES:
        if needle in blob:
            n += 1
    return min(n, 3)


def _anchor_sort_key(row: Dict[str, Any]) -> Tuple[int, int, float, int]:
    primary = 1 if row.get("primary") in (True, "true", "yes", 1, "1") else 0
    cscore = _contrast_shift_score(
        str(row.get("claim") or ""),
        str(row.get("evidence") or ""),
    )
    st_raw = row.get("strength")
    try:
        st = float(st_raw)
    except (TypeError, ValueError):
        st = 0.0
    conf_raw = row.get("confidence")
    try:
        conf = float(conf_raw)
    except (TypeError, ValueError):
        conf = 0.0
    ev_len = len(str(row.get("evidence") or "").strip())
    return (primary, cscore, max(st, conf * 10.0), ev_len)


def _gather_grounded_evidence_rows(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    rows: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for e in wf.get("evidence_map") or []:
        if isinstance(e, dict) and evidence_row_is_export_grounded(e):
            sig = f"{e.get('claim')}|{e.get('evidence')}"
            if sig not in seen:
                seen.add(sig)
                rows.append(e)
    for e in r3.get("evidence_mapping") or []:
        if isinstance(e, dict) and evidence_mapping_row_is_export_grounded(e):
            sig = f"{e.get('claim')}|{e.get('evidence')}"
            if sig not in seen:
                seen.add(sig)
                rows.append(e)
    rows.sort(key=_anchor_sort_key, reverse=True)
    return rows


def pick_best_anchor_row(bundle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Highest-priority grounded evidence row for outreach specificity (no LLM).

    Order: ``primary`` → **contrast / pivot language** → model strength → quote length.
    """
    rows = _gather_grounded_evidence_rows(bundle)
    return rows[0] if rows else None


def _anchor_target(sr: Dict[str, Any]) -> str:
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    thesis = str(core.get("thesis") or "").strip()
    if thesis:
        return _trim_for_card(thesis.lower(), 120)
    cp = str(sr.get("core_problem") or "").strip()
    if cp:
        return _trim_for_card(cp.lower(), 120)
    return "a clear position the listener can track"


def _anchor_structural_break(sr: Dict[str, Any]) -> str:
    cp = str(sr.get("core_problem") or "").strip()
    if cp:
        clean = cp[:1].lower() + cp[1:]
        return _trim_for_card(clean.rstrip("."), 150)
    return "the episode never lands on one argument the listener can repeat back"


def format_anchor_line(row: Dict[str, Any], sr: Dict[str, Any]) -> str:
    quote = str(row.get("evidence") or "").strip()
    if not quote:
        quote = str(row.get("claim") or "").strip()
    quote = _trim_for_card(quote, 220)
    ts = str(row.get("timestamp") or "").strip()
    prefix = f"**Around {ts},** " if ts else ""
    target = _anchor_target(sr)
    structural_break = _anchor_structural_break(sr)
    return (
        f"{prefix}**on the tape:** “{quote}” — but it isn't developed into "
        f"{target}, so {structural_break}."
    )


def _resolve_blockers(bundle: Dict[str, Any]) -> List[str]:
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    if wmeta.get("export_status") in ("insufficient_signal", "degraded"):
        eb = wmeta.get("export_blockers") or []
        if not isinstance(eb, list):
            return [str(eb).strip()] if str(eb).strip() else []
        return [str(x).strip() for x in eb if str(x).strip()]
    abort, reasons = strategist_truth_gate_bundle(bundle)
    if abort:
        return [str(x).strip() for x in reasons if str(x).strip()]
    return []


def _render_lead_audit_insufficient(
    show: str,
    ep: str,
    bundle: Dict[str, Any],
    blockers: List[str],
) -> str:
    working = _working_bullets_from_bundle(bundle)
    primary = blockers[0] if blockers else "The tape did not meet the minimum bar for a grounded strategic read."
    missed = (
        blockers[1]
        if len(blockers) > 1
        else "Shareable positioning and a crisp outreach hook stay undefined until structure is visible on the transcript."
    )
    coach = (bundle.get("report_v3") or {}).get("coach_report") if isinstance(bundle.get("report_v3"), dict) else {}
    coach = coach if isinstance(coach, dict) else {}
    bl = coach.get("bottom_line") if isinstance(coach.get("bottom_line"), dict) else {}
    one_fix = str(bl.get("if_fixed") or bl.get("must_change") or "").strip()
    if not one_fix:
        one_fix = "Improve transcript quality (captions, ASR cleanup, or a longer excerpt) and re-run so claims and beats can be verified."
    upside = (
        "You get a defensible read on what to say to sponsors and guests—without guessing from silence."
    )
    lines = [
        f"# Podcast audit — {show} · {ep}",
        "",
        "**One-line read:** "
        "Limited-signal run: here is the directional take until the transcript supports a fully grounded outreach card.",
    ]
    weak_line = _weak_structure_line(bundle)
    if weak_line:
        lines.extend(["", weak_line])
    lines.append("")
    if working:
        lines.append("## What's working")
        for w in working:
            lines.append(f"- {w}")
        lines.append("")
    lines.extend(
        [
            "## What's costing you",
            f"**Primary issue:** {primary}",
            f"**Missed opportunity:** {missed}",
            "",
            "## If you fixed one thing first",
            f"**Lever:** {one_fix}",
            f"**Upside:** {upside}",
            "",
            "---",
            "",
            "*Structure and claims in the full report are labeled honestly when confidence is low; no scores or synthetic metrics are implied here.*",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _meaningful_working_from_sr(sr: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for x in sr.get("what_working") or []:
        s = str(x).strip()
        if not s or s == "—" or _looks_like_caption_noise(s):
            continue
        out.append(s)
        if len(out) >= 3:
            break
    return out


def _render_lead_audit_full(show: str, ep: str, sr: Dict[str, Any], bundle: Dict[str, Any]) -> str:
    anchor = pick_best_anchor_row(bundle)

    read = str(sr.get("punchline_header") or sr.get("conviction_statement") or "").strip()
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    if not read:
        read = str(core.get("thesis") or "").strip()
    if not read:
        read = "The episode needs one clear through-line before cold outreach can sound specific."

    if not anchor:
        read = (
            "Without one quotable on-tape moment that passes the evidence bar, this stays in the "
            "'accurate pattern' zone — not the 'they actually listened' zone. "
            f"{_trim_for_card(read, 220)}"
        )

    working = _meaningful_working_from_sr(sr)

    core_problem = str(sr.get("core_problem") or "").strip()
    missing = [str(x).strip() for x in (sr.get("what_missing") or []) if str(x).strip()]
    if not core_problem and missing:
        core_problem = missing[0]
    if not core_problem:
        core_problem = "The central argument is hard to state in one sentence from how the episode unfolds."

    missed = missing[1] if len(missing) > 1 else ""
    if not missed:
        sv = sr.get("strategic_value_for_network") if isinstance(sr.get("strategic_value_for_network"), dict) else {}
        missed = str(sv.get("where_it_underperforms") or "").strip()
    if not missed:
        missed = "A sharper hook and proof moments that a stranger could repeat back after one skim."

    lever = str(sr.get("one_line_fix") or "").strip()
    if not lever:
        up = sr.get("upgrade_plan") if isinstance(sr.get("upgrade_plan"), dict) else {}
        recs = up.get("recommendations") if isinstance(up.get("recommendations"), list) else []
        lever = str(recs[0]).strip() if recs else "Reframe around one claim, one tension beat, and one listener action."

    sv = sr.get("strategic_value_for_network") if isinstance(sr.get("strategic_value_for_network"), dict) else {}
    upside = str(sv.get("what_improving_unlocks") or "").strip()
    if not upside:
        ae = sr.get("audience_engagement_intelligence") if isinstance(sr.get("audience_engagement_intelligence"), dict) else {}
        upside = str(ae.get("listener_takeaway_gap") or ae.get("weekly_improvement_insight") or "").strip()
    if not upside:
        upside = "Clearer positioning in outreach, stronger clip candidates, and a more specific ask."

    lines = [
        f"# Podcast audit — {show} · {ep}",
        "",
        f"**One-line read:** {read}",
    ]
    weak_line = _weak_structure_line(bundle)
    if weak_line:
        lines.extend(["", weak_line])
    lines.append("")
    if anchor:
        lines.append(format_anchor_line(anchor, sr))
        lines.append("")
    if working:
        lines.extend(
            [
                "## What's working",
                f"- {working[0]}",
            ]
        )
        if len(working) > 1:
            lines.append(f"- {working[1]}")
        if len(working) > 2:
            lines.append(f"- {working[2]}")
        lines.append("")
    lines.extend(
        [
        "## What's costing you",
        f"**Primary issue:** {core_problem}",
        f"**Missed opportunity:** {missed}",
        "",
        "## If you fixed one thing first",
        f"**Lever:** {lever}",
        f"**Upside:** {upside}",
        "",
        "---",
        "",
        "*Structure is drawn from the transcript; the full strategist report labels confidence where sections are thin or interpretive.*",
        "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def render_lead_audit_markdown(bundle: Dict[str, Any]) -> str:
    """
    Build the 1-page lead audit from a v3 result bundle
    (``report_v3``, ``workflow_report``, optional ``blueprint_v1``, optional ``meta``).
    """
    show, ep = _snapshot_and_meta(bundle)
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}

    blockers = _resolve_blockers(bundle)
    if wmeta.get("export_status") in ("insufficient_signal", "degraded") or blockers:
        if wmeta.get("export_status") in ("insufficient_signal", "degraded") and not blockers:
            blockers = [
                "Minimum evidence and/or segment bars were not met, or checks did not pass.",
            ]
        return _render_lead_audit_insufficient(show, ep, bundle, blockers)

    sr = _derive_strategist_report_from_bundle(bundle)
    return _render_lead_audit_full(show, ep, sr, bundle)
