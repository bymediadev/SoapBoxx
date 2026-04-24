# backend/episode_report_v3.py
"""
**Primary** SoapBoxx episode workflow (v3): coach-style Episode Report (10 sections), signal mode
(HIGH_SIGNAL / LOW_SIGNAL), structured evidence, engagement triads, guests, segments,
actionable analytics, reference validation, semantic deduplication, and ``dual_lens`` (parallel
narrative/analytical assembly + weights — see ``lens_engine_prompts.assemble_dual_lens_package``).

Builds on normalized **v2** brief JSON from episode_intelligence.generate_episode_brief.
The coach always surfaces a single-sentence thesis line (argument-shaped); low-signal runs pair it with an honest-read note.

**Structured intelligence source of truth:** when enabled (default; ``SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=1`` or
``atomic_ground_truth=True`` on :func:`build_v3_report`), claims and graph-derived guests come **only** from
``atomic_pipeline.run_atomic_pipeline`` — v3 does not re-extract claims, re-cluster topics, or synthesize guests
from narrative heuristics. Narrative/coach/dual_lens remain presentation layers on top of the same transcript
and brief context. Set ``SOAPBOXX_V3_ATOMIC_GROUND_TRUTH=0`` to restore brief-only claim rows (legacy/tests).
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

# Reuse claim cleanup from v2 pipeline
try:
    from .episode_intelligence import (  # type: ignore
        _clean_claim_text,
        _is_asr_artifact_line,
        _is_dangling_pronoun_line,
        _is_garbage_claim_text,
        _is_meta_topic_line,
        _is_narrative_meta_noise,
        _is_production_chatter_line,
        _sanitize_episode_snapshot,
        _trim_anchor_display_text,
        _utc_now_iso,
        generate_episode_brief,
        render_markdown,
    )
except ImportError:
    from episode_intelligence import (  # type: ignore
        _clean_claim_text,
        _is_asr_artifact_line,
        _is_dangling_pronoun_line,
        _is_garbage_claim_text,
        _is_meta_topic_line,
        _is_narrative_meta_noise,
        _is_production_chatter_line,
        _sanitize_episode_snapshot,
        _trim_anchor_display_text,
        _utc_now_iso,
        generate_episode_brief,
        render_markdown,
    )

try:
    from .lens_engine_prompts import assemble_dual_lens_package  # type: ignore
except ImportError:
    from lens_engine_prompts import assemble_dual_lens_package  # type: ignore

try:
    from .episode_quality_gates import evaluate_v3_quality_gates  # type: ignore
except ImportError:
    from episode_quality_gates import evaluate_v3_quality_gates  # type: ignore

try:
    from .episode_quality_gates import (  # type: ignore
        _claim_line_is_intro_filler,
        build_identity_anchor,
        jaccard_tokens,
    )
except ImportError:
    from episode_quality_gates import (  # type: ignore
        _claim_line_is_intro_filler,
        build_identity_anchor,
        jaccard_tokens,
    )

try:
    from .argument_rigor import evaluate_argument_rigor_report  # type: ignore
except ImportError:
    from argument_rigor import evaluate_argument_rigor_report  # type: ignore

try:
    from .guest_generation_decision import build_guest_decision_trace  # type: ignore
except ImportError:
    from guest_generation_decision import build_guest_decision_trace  # type: ignore

try:
    from .semantic_grounding_validator import apply_semantic_grounding_validator  # type: ignore
except ImportError:
    from semantic_grounding_validator import apply_semantic_grounding_validator  # type: ignore

try:
    from .claim_quality_gate import apply_claim_quality_gate  # type: ignore
except ImportError:
    from claim_quality_gate import apply_claim_quality_gate  # type: ignore

try:
    from .system_health import apply_system_health_label  # type: ignore
except ImportError:
    from system_health import apply_system_health_label  # type: ignore

try:
    from .report_invariants import validate_v3_invariants  # type: ignore
except ImportError:
    from report_invariants import validate_v3_invariants  # type: ignore

try:
    from .atomic_pipeline import envelope_to_json, run_atomic_pipeline
except ImportError:
    try:
        from atomic_pipeline import envelope_to_json, run_atomic_pipeline  # type: ignore
    except ImportError:  # pragma: no cover
        envelope_to_json = None  # type: ignore[assignment]
        run_atomic_pipeline = None  # type: ignore[assignment]

REPORT_V3_VERSION = "3"
# Canonical markdown H1 used by all episode markdown renderers (duplicate-guard splits on this exact line).
EPISODE_REPORT_MARKDOWN_H1 = "# SoapBoxx Episode Report"
SEMANTIC_DUP_THRESHOLD = 0.8
MIN_EVIDENCE_CONFIDENCE = 0.2
TRUTH_MODE_FAILURE_TITLE = "## Truth mode gate: report withheld"
_TRUTH_MODE_ALLOWED = {"truth", "growth"}


def _episode_product_mode() -> str:
    """
    Product posture switch:
    - ``truth`` (default): enforce falsifiability gates and withhold polished report on failure.
    - ``growth``: keep current behavior (best-effort output even when structure is weak).
    """
    raw = (os.getenv("SOAPBOXX_MODE") or "truth").strip().lower()
    if raw in _TRUTH_MODE_ALLOWED:
        return raw
    return "truth"


def _truth_mode_failure_markdown(
    reasons: Sequence[str], *, title: str = "", creator: str = ""
) -> str:
    ep = f"{creator + ' · ' if creator else ''}{title}".strip() or "Unknown episode"
    lines = [
        EPISODE_REPORT_MARKDOWN_H1,
        "",
        TRUTH_MODE_FAILURE_TITLE,
        "",
        "This run is blocked by hard falsifiability gates. No strategist packaging is emitted.",
        "",
        f"**Episode:** {ep}",
        "",
        "### Failed checks",
    ]
    seen: Set[str] = set()
    for r in reasons:
        s = str(r).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        lines.append(f"- {s}")
    if len(lines) == 10:
        lines.append("- Truth-mode gate failed with no details (unexpected state).")
    lines.extend(
        [
            "",
            "### Required to unlock output",
            "- Thesis must be falsifiable and not just episode/title packaging.",
            "- Claims must be atomic, standalone, and structurally coherent.",
            "- Evidence must map to direct on-tape anchors, not interpretive restatements.",
            "",
            "*Set `SOAPBOXX_MODE=growth` to emit growth-first guidance without truth-mode blocking.*",
            "",
        ]
    )
    return "\n".join(lines)


def evaluate_truth_mode_hard_gates(
    report: Dict[str, Any],
    *,
    transcript: str,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Hard product gates for ``SOAPBOXX_MODE=truth``.
    Returns ``(passed, reasons, metrics)``.
    """
    reasons: List[str] = []
    r3 = report if isinstance(report, dict) else {}
    snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
    meta = r3.get("meta") if isinstance(r3.get("meta"), dict) else {}
    cr = r3.get("coach_report") if isinstance(r3.get("coach_report"), dict) else {}
    nr = (
        r3.get("narrative_reconstruction")
        if isinstance(r3.get("narrative_reconstruction"), dict)
        else {}
    )
    thesis = str(cr.get("episode_thesis") or nr.get("core_thesis") or "").strip()
    title = str(snap.get("title") or meta.get("title") or "").strip()
    primary_topic = str(snap.get("primary_topic") or "").strip()

    try:
        from .episode_quality_gates import claim_structure_score
    except ImportError:
        from episode_quality_gates import claim_structure_score  # type: ignore

    thesis_ok = bool(thesis) and len(thesis.split()) >= 8
    if thesis_ok and title and text_similarity(thesis, title) >= 0.90:
        thesis_ok = False
    if thesis_ok and primary_topic and text_similarity(thesis, primary_topic) >= 0.92:
        thesis_ok = False
    # One-word labels / slogans are not falsifiable thesis lines.
    if thesis_ok and len(re.findall(r"[A-Za-z0-9]+", thesis)) < 5:
        thesis_ok = False
    if not thesis_ok:
        reasons.append("Thesis is not falsifiable (too short, title-like, or slogan-like).")

    claims = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]
    claim_rows = 0
    atomic_claims = 0
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or "")).strip()
        if not txt:
            continue
        claim_rows += 1
        score = float(claim_structure_score(txt))
        if (
            score >= 0.45
            and not _is_garbage_claim_text(txt)
            and 7 <= len(txt.split()) <= 45
            and txt.count(";") <= 1
        ):
            atomic_claims += 1
    if claim_rows < 3:
        reasons.append(f"Atomic claims gate failed: {claim_rows} claim rows found (< 3).")
    elif atomic_claims < 3:
        reasons.append(
            f"Atomic claims gate failed: {atomic_claims}/{claim_rows} claims pass atomic structure (need >= 3)."
        )

    t_low = (transcript or "").lower()
    direct_rows = 0
    supporting_claim_ids: Set[str] = set()
    interpretation_leaks = 0
    for row in (r3.get("evidence_mapping") or []):
        if not isinstance(row, dict):
            continue
        ev = str(row.get("evidence") or "").strip()
        cl = str(row.get("claim") or "").strip()
        cid = str(row.get("id") or "").strip()
        low_ev = ev.lower()
        if any(
            m in low_ev
            for m in (
                "explains how this lands",
                "what to do this week",
                "insight →",
                "meaning →",
                "application",
            )
        ):
            interpretation_leaks += 1
        if (
            evidence_mapping_row_is_export_grounded(row)
            and len(low_ev) >= 20
            and low_ev in t_low
            and len(cl.split()) >= 6
        ):
            direct_rows += 1
            if cid:
                supporting_claim_ids.add(cid)
    if direct_rows < 3:
        reasons.append(
            f"Direct evidence gate failed: only {direct_rows} direct on-tape evidence rows found (need >= 3)."
        )
    if len(supporting_claim_ids) < 2:
        reasons.append(
            "Evidence coverage gate failed: evidence does not support at least two distinct claim IDs."
        )
    if interpretation_leaks > 0:
        reasons.append(
            "Evidence/interpretation separation failed: interpretive language detected inside evidence rows."
        )

    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    if not metrics or int(metrics.get("transcript_word_count") or 0) <= 0:
        reasons.append("Scoring gate failed: readiness metrics are missing or invalid.")

    gate_metrics = {
        "thesis_ok": thesis_ok,
        "claim_rows": claim_rows,
        "atomic_claims": atomic_claims,
        "direct_evidence_rows": direct_rows,
        "evidence_claim_coverage": len(supporting_claim_ids),
        "interpretation_leaks": interpretation_leaks,
    }
    return (len(reasons) == 0, reasons, gate_metrics)


def _count_episode_report_markdown_h1(md: str) -> int:
    """Count top-level report title lines (exact H1), not substring hits inside prose."""
    if not isinstance(md, str) or not md.strip():
        return 0
    return sum(1 for line in md.splitlines() if line.strip() == EPISODE_REPORT_MARKDOWN_H1)


def ensure_single_episode_report_markdown(text: str) -> str:
    """
    If multiple ``# SoapBoxx Episode Report`` headers appear (concat leak / double render),
    keep **only the last** block so exports stay single-canonical.
    """
    if not isinstance(text, str):
        return text  # type: ignore[return-value]
    if not text.strip():
        return text
    lines = text.splitlines()
    idxs = [i for i, ln in enumerate(lines) if ln.strip() == EPISODE_REPORT_MARKDOWN_H1]
    if len(idxs) <= 1:
        return text
    body = "\n".join(lines[idxs[-1] :]).strip()
    return body + "\n" if body else text


def _strict_episode_report_h1_pre_check(md: str, *, where: str) -> None:
    """
    Fail fast when ``SOAPBOXX_STRICT_EPISODE_REPORT_HEADER=1`` and more than one report H1 is present
    **before** dedupe — surfaces accidental dual render paths in CI or local debugging.
    """
    v = (os.getenv("SOAPBOXX_STRICT_EPISODE_REPORT_HEADER") or "").strip().lower()
    if v not in ("1", "true", "yes", "on"):
        return
    n = _count_episode_report_markdown_h1(md)
    if n > 1:
        raise AssertionError(
            f"Duplicate '{EPISODE_REPORT_MARKDOWN_H1}' headers ({n}) in {where} — fix dual render paths."
        )


def _transcript_normalize_enabled() -> bool:
    """
    Default **on** (dedupe lines, collapse blank runs) for real-episode transcripts.
    Set ``SOAPBOXX_TRANSCRIPT_NORMALIZE=0`` (or ``false`` / ``no`` / ``off``) to disable.
    """
    v = os.getenv("SOAPBOXX_TRANSCRIPT_NORMALIZE", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    return True


def normalize_transcript_for_v3(text: str) -> str:
    """
    Deterministic transcript cleanup before v2 brief / v3 report (no LLM).

    - Normalizes ``\\r\\n`` / ``\\r`` to ``\\n``.
    - Strips repeated YouTube ``Kind: captions Language: …`` header junk per line.
    - Trims trailing whitespace per line.
    - Collapses runs of **3+** blank lines to **2** blank lines.
    - Drops **consecutive duplicate** non-blank lines (exact match after ``rstrip``).
      A blank line between two identical lines breaks deduplication so repeated
      paragraphs separated by whitespace are kept.
    """
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    try:
        from .transcript_structure_extract import strip_youtube_caption_metadata
    except ImportError:  # pragma: no cover
        from transcript_structure_extract import strip_youtube_caption_metadata  # type: ignore

    text = strip_youtube_caption_metadata(text)
    lines = text.split("\n")
    out: List[str] = []
    prev_content: Optional[str] = None
    blank_run_out = 0
    for line in lines:
        s = line.rstrip()
        if not s:
            if blank_run_out < 2:
                out.append("")
                blank_run_out += 1
            prev_content = None
            continue
        blank_run_out = 0
        if prev_content is not None and s == prev_content:
            continue
        prev_content = s
        out.append(s)
    return "\n".join(out).strip()


def transcript_for_v3_pipeline(text: str) -> str:
    """
    Return ``normalize_transcript_for_v3`` unless normalization is disabled (see ``_transcript_normalize_enabled``).

    Set ``SOAPBOXX_TRANSCRIPT_CONTROL_CLEAN=1`` to run
    :func:`report_control_workflow.pipeline.extract.clean_transcript` (extra ASR/filler passes)
    **before** brief + v3. Off by default so verbatim atomic grounding stays unchanged.
    """
    if not _transcript_normalize_enabled():
        return text or ""
    if (os.getenv("SOAPBOXX_TRANSCRIPT_CONTROL_CLEAN") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        try:
            from report_control_workflow.pipeline.extract import clean_transcript
        except ImportError:  # pragma: no cover
            return normalize_transcript_for_v3(text or "")
        return clean_transcript(text or "")
    return normalize_transcript_for_v3(text or "")


def _workflow_body_guest_rows(workflow: Dict[str, Any]) -> List[Any]:
    """Delegate to :func:`soapboxx_v3_workflow.workflow_guest_rows` (alias drift self-heal)."""
    try:
        from .soapboxx_v3_workflow import workflow_guest_rows
    except ImportError:
        from soapboxx_v3_workflow import workflow_guest_rows  # type: ignore
    return workflow_guest_rows(workflow)


def _workflow_guest_name_is_spurious(name: str) -> bool:
    """Filter caption tokens / locale codes mistaken for people in workflow guest rows."""
    n = (name or "").strip().lower()
    if len(n) < 3:
        return True
    if n in frozenset(
        {"kind", "language", "captions", "en", "auto", "en-us", "en-gb", "off", "on"}
    ):
        return True
    if "kind:" in n and "caption" in n:
        return True
    if re.match(r"^[a-z]{2}(-[a-z]{2})?$", n):
        return True
    return False


def _workflow_guest_rows_to_strategist_opportunities(wf: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Map ``workflow_report`` guest rows into strategist ``guest_content_opportunities`` shape
    so markdown export is not empty when the workflow layer produced names/angles.
    """
    rows = _workflow_body_guest_rows(wf)
    out: List[Dict[str, str]] = []
    for g in rows:
        if not isinstance(g, dict):
            continue
        who = str(g.get("name") or "").strip()
        if not who or _workflow_guest_name_is_spurious(who):
            continue
        title = str(g.get("title") or g.get("role") or "").strip()
        angle = str(g.get("topic_angle") or g.get("angle") or "").strip()
        src = str(g.get("source") or "").strip()
        # Verbatim figures (Jesse James, etc.) are evidence, not bookable "guest opportunities".
        if src == "episode_grounded_person":
            continue
        why = title or "Suggested angle for this episode"
        unlock = angle or "Tie picks to claims and evidence before outreach."
        out.append(
            {
                "who_type": who[:160],
                "why_they_matter": why[:220],
                "what_they_unlock": unlock[:280],
            }
        )
        if len(out) >= 6:
            break
    return out


def _strategist_opportunity_is_generic_role(g: Dict[str, Any]) -> bool:
    """Role-only strategist lines that collide with named workflow outreach rows."""
    who = str(g.get("who_type") or "").strip().lower()
    if not who:
        return True
    if who in frozenset(
        {
            "skeptical domain practitioner",
            "researcher or analyst (primary sources)",
            "contrarian voice (steel-manned)",
            "editorial producer / story editor",
            "domain practitioner",
            "skeptical expert",
            "research analyst",
        }
    ):
        return True
    if who.startswith("contrarian voice") or who.startswith("researcher or analyst"):
        return True
    return False


def _merge_strategist_guest_opportunities(sr: Dict[str, Any], wf: Dict[str, Any]) -> Dict[str, Any]:
    """Prefer workflow guest rows (episode-grounded first), then existing strategist slots."""
    sr = dict(sr or {})
    wf_ops = _workflow_guest_rows_to_strategist_opportunities(wf)
    existing = [x for x in (sr.get("guest_content_opportunities") or []) if isinstance(x, dict)]
    valid_existing = [g for g in existing if str(g.get("who_type") or "").strip()]
    if wf_ops:
        valid_existing = [g for g in valid_existing if not _strategist_opportunity_is_generic_role(g)]
    combined = wf_ops + valid_existing
    if not combined:
        try:
            from soapboxx_v3_workflow import _guest_rows_from_outreach_domain
        except ImportError:
            from .soapboxx_v3_workflow import _guest_rows_from_outreach_domain  # type: ignore
        named = _guest_rows_from_outreach_domain("general_history", "c1", limit=5)
        sr["guest_content_opportunities"] = [
            {
                "who_type": str(r.get("name") or "")[:160],
                "why_they_matter": str(r.get("title") or "Expert")[:220],
                "what_they_unlock": str(r.get("angle") or r.get("topic_angle") or "")[:280],
            }
            for r in named
            if str(r.get("name") or "").strip()
        ]
        if sr["guest_content_opportunities"]:
            return sr
        sr["guest_content_opportunities"] = [
            {
                "who_type": "Domain practitioner",
                "why_they_matter": "Grounds claims in execution reality.",
                "what_they_unlock": "Concrete tradeoffs.",
            },
            {
                "who_type": "Skeptical expert",
                "why_they_matter": "Introduces productive tension.",
                "what_they_unlock": "Shareable conflict.",
            },
            {
                "who_type": "Research analyst",
                "why_they_matter": "Separates claims from assumptions.",
                "what_they_unlock": "Defensible evidence.",
            },
        ]
        return sr
    seen: set = set()
    deduped: List[Dict[str, str]] = []
    for g in combined:
        k = str(g.get("who_type") or "").strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        deduped.append(
            {
                "who_type": str(g.get("who_type") or "").strip(),
                "why_they_matter": str(g.get("why_they_matter") or "").strip(),
                "what_they_unlock": str(g.get("what_they_unlock") or "").strip(),
            }
        )
    sr["guest_content_opportunities"] = deduped[:5]
    return sr


def _compressed_export_guest_markdown_lines(bundle: Dict[str, Any]) -> List[str]:
    """Short guest bullets for compressed exports (workflow signal only, no invented names)."""
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    lines: List[str] = []
    for g in _workflow_guest_rows_to_strategist_opportunities(wf)[:4]:
        who = str(g.get("who_type") or "").strip()
        if not who:
            continue
        tail = str(g.get("what_they_unlock") or "").strip()
        if len(tail) > 200:
            tail = tail[:199].rstrip() + "…"
        lines.append(f"- **{who}:** {tail}".strip() if tail else f"- **{who}**")
    return lines


INSIGHT_TRANSFORM_RULES = """
You are NOT allowed to output raw transcript fragments.

For every extracted quote:
1. Rewrite it into a complete, clear sentence
2. Extract the underlying idea (not the wording)
3. Convert it into a generalized insight

Bad Output:
- "those are all ways that you can start to think about..."

Good Output:
- "Identifying environmental temptations is the first step in designing better habits."

If the sentence is incomplete or low-signal -> DISCARD IT.
""".strip()

NARRATIVE_RECONSTRUCTION = """
If no clear narrative is detected, you MUST infer one using:

1. Repeated keywords/themes
2. Speaker intent (advice, story, explanation)
3. Outcome the speaker is pushing toward

Output format:
- Core Thesis (1 sentence)
- Supporting Mechanism (how it works)
- Practical Translation (what it means in real life)

You are NOT allowed to return "no narrative".
""".strip()

EVIDENCE_MAPPING_RULES = """
Each claim must include:

1. Claim (rewritten insight)
2. Function:
   - supports_argument
   - example
   - anecdote
   - mechanism
3. Usage:
   - how a creator can use this in content

Bad:
- random sentence + timestamp

Good:
- "Preparation reduces failure rate" | function: mechanism | usage: teaching segment
""".strip()

STRATEGY_RULES = """
For every insight, generate:

1. Application (real-world action)
2. Content Angle (how to turn into a segment)

Do not leave insights abstract.
""".strip()

QUESTION_RULES = """
Generate questions using these lenses:

1. Failure Case:
   - When does this NOT work?

2. Constraint:
   - What real-world condition breaks this?

3. Contrarian:
   - What would an expert disagree with?

4. Application:
   - What should someone do differently tomorrow?

Avoid generic questions.
""".strip()

GUEST_RULES = """
You must recommend 3-5 guests based on:

1. Validating the idea
2. Challenging the idea
3. Applying the idea in real-world scenarios

Each guest must include:
- Type
- Reason
- Content angle
""".strip()

TAKEAWAY_RULES = """
Generate ONE clear takeaway:

- Max 15 words
- Must be repeatable
- Must sound like something a host would say on-air

Bad:
- vague summary

Good:
- "You don't rise to goals - you fall to systems."
""".strip()

_FILLER_PREFIX = re.compile(
    r"^(The speaker|Host|Guest)\s+(argues|says|claims|notes|states|criticizes)\s+that\s+",
    re.I,
)
_REF_ID = re.compile(r"\bc(\d+)\b", re.I)


def _tokens(s: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", (s or "").lower())


def text_similarity(a: str, b: str) -> float:
    """
    Similarity in [0, 1], calibrated for duplicate detection.
    Blend of Jaccard (word sets) and normalized sequence ratio.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return SequenceMatcher(None, a, b).ratio()
    inter = len(ta & tb)
    union = len(ta | tb)
    jacc = inter / union if union else 0.0
    seq = SequenceMatcher(None, a, b).ratio()
    return float(0.55 * jacc + 0.45 * seq)


def _dedupe_strategist_highlights_vs_claims(
    highlights: List[str],
    claims: List[str],
    *,
    sim_threshold: float = 0.92,
) -> List[str]:
    """Drop highlight lines that are near-verbatim repeats of top claims (reads as one story, not two lists)."""
    out: List[str] = []
    c_clean = [str(c).strip() for c in claims if str(c).strip()]
    for h in highlights:
        hs = str(h).strip()
        if not hs:
            continue
        if any(text_similarity(hs, c) >= sim_threshold for c in c_clean):
            continue
        out.append(hs)
    if not out and highlights:
        return [str(highlights[0]).strip()] if str(highlights[0]).strip() else []
    return out


def _strategist_question_upgrade_from_thesis(thesis: str) -> List[str]:
    """Host-facing prompts tied to the episode spine (avoid three identical generic coaching lines)."""
    spine = _claim_focus_phrase(str(thesis or "").strip(), max_words=18, max_chars=140)
    if not spine or spine == "this claim":
        spine = "the spine claim above"
    spine = spine.rstrip().rstrip(".?!").strip() or "the spine claim above"
    return [
        f"What is the strongest fair counterargument to: {spine}?",
        "What one primary source, dataset, or witness would most clearly confirm or falsify that line?",
        "What is one concrete listener action this week if the thesis is directionally right?",
    ]


def _evidence_anchor_row_is_redundant(claim: str, anchor: str) -> bool:
    """True when anchor text does not add a distinct pull-quote vs the claim line."""
    cl, an = (claim or "").strip(), (anchor or "").strip()
    if not cl or not an:
        return False
    if cl == an:
        return True
    return text_similarity(cl, an) >= 0.94


def remove_semantic_duplicates(
    items: Sequence[str],
    *,
    threshold: float = SEMANTIC_DUP_THRESHOLD,
    key: Optional[Callable[[str], str]] = None,
) -> List[str]:
    """
    Drop items semantically similar to an earlier kept item (similarity > threshold).
    Keeps the first occurrence (caller should sort by strength if needed).
    Uses text similarity only (embedding dedup was removed in the Ollama-only stack).
    """
    raw = [str(x).strip() for x in items if str(x).strip()]
    if not raw:
        return []
    getter = key or (lambda s: s)
    kept: List[str] = []
    for item in raw:
        k = getter(item)
        if any(text_similarity(k, getter(o)) > threshold for o in kept):
            continue
        kept.append(item)
        if len(kept) >= 20:
            break
    return kept


def _limit_words(text: str, max_words: int = 20) -> str:
    words = (text or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(",;:")


def _is_garbled_insight_line(text: str) -> bool:
    """Broken grammar / word-salad from sloppy model output — never show as a highlight.

    Length alone is not a grammatical defect: short but clean bullets (e.g. a 3–5 word
    strategist highlight) should not be treated as garbled. This filter focuses on
    stutter/grammar signals, leaving length policy to callers.
    """
    s = (text or "").strip()
    if not s:
        return True
    words = s.split()
    if len(words) < 2:
        return True
    low = s.lower()
    if re.search(r"\bquite\s+while\b", low):
        return True
    if re.search(r"\bcannot\s+quite\s+\w+\s+while\b", low):
        return True
    if "cannot quite" in low and "while" in low and len(words) < 16:
        return True
    return False


def is_low_signal_insight_line(text: str) -> bool:
    """
    Heuristic filter for transcript junk that should never surface as a "highlight":
    lyrics, outros, repeated interjections, scheduling banter, caption metadata.
    """
    s = (text or "").strip()
    if not s:
        return True
    if _is_meta_topic_line(s) or _is_narrative_meta_noise(s):
        return True
    if _is_prompt_like_claim_line(s):
        return True
    low = s.lower()
    # Caption / platform boilerplate
    if any(
        x in low
        for x in (
            "kind: captions",
            "language: en",
            "subscribe",
            "like and subscribe",
            "hit the bell",
        )
    ):
        return True
    # Repeated filler / interjections (lyrics, reactions)
    if re.search(r"\b(?:oh\s*,?\s*){3,}", low):
        return True
    if re.search(r"\b(?:okay\s*,?\s*){3,}", low):
        return True
    # Outro / scheduling / music-break chatter
    if any(
        x in low
        for x in (
            "forward to talking",
            "talk to you in about",
            "see you in a few",
            "we'll be right back",
            "whole world to me",
            "making love",
        )
    ):
        return True
    # Short lyric-y fragments without argumentative content
    if "whole world" in low and len(s.split()) < 12:
        return True
    # Nonsense or ultra-vague "wellness" fragments often picked from noisy transcripts
    if "sometimes you always" in low:
        return True
    words = s.split()
    if len(words) < 6 and any(x in low for x in ("oh", "yeah", "baby", "love")):
        return True
    # Radio / meditation intros — atmospheric, not argumentative (common in sleep/spiritual pods)
    atmospheric = (
        "tonight we are",
        "tonight we're",
        "we are going to sit",
        "sit with a man",
        "the kind that waits",
        "spaces between tasks",
        "silence after",
        "after the lights go out",
        "let your breath",
        "particular quiet",
        "more like a question",
        "circling in the back of your mind",
        "understood suffering better than",
        "in the particular quiet",
    )
    if any(x in low for x in atmospheric):
        return True
    if low.startswith("let your ") and any(
        x in low for x in ("breath", "rhythm", "body", "mind", "shoulders")
    ):
        return True
    # Conversational filler lines that repeatedly leak into highlights/questions in long transcripts.
    # These are vague framing stubs rather than independently defensible claims.
    if low.startswith("it's like you're just a speck"):
        return True
    if low.startswith("it made me realize how much of it was"):
        return True
    if low.startswith("it's like that's another example of like"):
        return True
    if low.startswith("one out of five, one out of five"):
        return True
    if "that's like any kids like what" in low:
        return True
    if len(words) > 45 and low.count(" like ") >= 4:
        return True
    if "you bought an airstream" in low:
        return True
    if low.startswith("hey guys, three quick things"):
        return True
    if low.startswith("just went up to like humble"):
        return True
    host_banter_markers = (
        "wrote the greatest thing ever",
        "i'm like, \"oh, we got",
        "it's funny when i have guys like you in here",
        "i've been watching you grow ever since",
        "it's cool to see behind the scenes",
        "you enjoy your cooking in here",
        "that's what it's about, though",
    )
    if any(m in low for m in host_banter_markers):
        return True
    # Short generic affirmations without topic nouns are usually banter, not analyzable claims.
    if len(words) <= 12 and re.search(r"\b(i think|for sure|it's funny|that's what)\b", low):
        topic_nouns = ("education", "school", "policy", "media", "power", "institution", "evidence")
        if not any(n in low for n in topic_nouns):
            return True
    if _is_garbled_insight_line(s):
        return True
    return False


def _is_prompt_like_claim_line(text: str) -> bool:
    """
    Detect conversational prompts / host setup lines that should not be treated as defensible claims.
    These often leak from transcript turns and degrade spine/actionability quality.
    """
    s = (text or "").strip()
    if not s:
        return True
    low = s.lower()
    starts = (
        "tell me about ",
        "because so for my podcast",
        "which if i if i forget",
        "try to remind me",
        "i feel like as soon as",
    )
    if any(low.startswith(p) for p in starts):
        return True
    if low.endswith("?") and len(s.split()) < 24:
        return True
    if re.search(r"\b(?:purpose,\s*){2,}purpose\b", low):
        return True
    if low.startswith("it's actually really important") and len(s.split()) < 18:
        return True
    return False


def _claims_non_filler_for_thesis(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop intro/warm-up lines so thesis + suggested argument use substantive claims first."""
    out: List[Dict[str, Any]] = []
    for c in claims or []:
        if not isinstance(c, dict):
            continue
        t = str(c.get("text") or "").strip()
        if not t or _claim_line_is_intro_filler(t):
            continue
        out.append(c)
    return out


def _thesis_is_identity_stub(line: str, snap: Dict[str, Any]) -> bool:
    """True when the thesis is mostly packaging (title echo / through-line wrapper), not an argument."""
    t = _clean_claim_text(str(line or "")).strip()
    if not t:
        return True
    low = t.lower()
    if "through-line for listeners" in low:
        return True
    title = str(snap.get("title") or "").strip()
    if title and len(title) > 14:
        try:
            if jaccard_tokens(t, title) >= 0.82:
                return True
        except Exception:
            pass
        if title.lower() in low and len(t) <= len(title) + 48:
            return True
    return False


def _trim_insight_line(text: str, max_words: int = 26) -> str:
    """
    Prefer a complete sentence under max_words; avoid chopping mid-clause when possible.
    """
    t = (text or "").strip()
    if not t:
        return t
    words = t.split()
    if len(words) <= max_words:
        return t
    chunk = " ".join(words[:max_words])
    for sep in (". ", "? ", "! ", "; "):
        idx = chunk.rfind(sep)
        if idx >= 48:
            return chunk[: idx + 1].strip()
    cut = chunk.rsplit(" ", 1)[0]
    return cut.rstrip(",;:\"'") + "…"


def clean_key_highlights(raw_highlights: Union[str, Sequence[str]]) -> List[str]:
    """
    Input: messy transcript-derived highlights (strings or list of strings).
    Output: 3–5 sharp standalone insights (claim-style, ≤20 words, deduped).
    """
    if isinstance(raw_highlights, str):
        lines = [ln.strip() for ln in raw_highlights.splitlines() if ln.strip()]
    else:
        lines = [str(x).strip() for x in raw_highlights if str(x).strip()]
    cleaned: List[str] = []
    for ln in lines:
        s = _FILLER_PREFIX.sub("", _clean_claim_text(ln))
        s = re.sub(r"\s+", " ", s).strip()
        if len(s) < 12:
            continue
        if _is_meta_topic_line(s) or _is_narrative_meta_noise(s):
            continue
        if is_low_signal_insight_line(s):
            continue
        s = _trim_insight_line(s, max_words=26)
        if s and not is_low_signal_insight_line(s) and s not in cleaned:
            cleaned.append(s)
    deduped = remove_semantic_duplicates(cleaned, threshold=SEMANTIC_DUP_THRESHOLD)
    out = [x for x in deduped if not is_low_signal_insight_line(x)][:5]
    return out


def generate_engagement_questions(claim: Dict[str, Any]) -> Dict[str, str]:
    """
    Tension-focused triad per claim: counterpunch, validation, application.
    """
    raw = _clean_claim_text(str(claim.get("text") or "")).strip()
    short = _claim_focus_phrase(raw, max_words=24, max_chars=220)
    return {
        "counterpunch": f'What would someone who disagrees say about this: "{short}"?',
        "validation": f'Is there real evidence behind this, or is it rhetoric? Push on: "{short}"',
        "application": f"What does this mean in real life for listeners—what should they do differently?",
    }


def map_guest_to_claim(guest: Dict[str, Any], claim: Dict[str, Any]) -> Dict[str, str]:
    """Every guest tied to one specific claim; no generic blurbs."""
    tgt = _clean_claim_text(str(claim.get("text") or ""))
    name = str(guest.get("name") or "Guest").strip()
    role = str(guest.get("title") or guest.get("role") or "Expert").strip()
    why = str(guest.get("angle") or guest.get("why_this_episode") or "").strip()
    if not why:
        why = f"Pressure-tests the claim: {tgt[:100]}{'…' if len(tgt) > 100 else ''}"
    return {
        "guest": name,
        "role": role,
        "why_this_episode": why,
        "target_claim": tgt,
    }


_RE_TS = re.compile(r"(?:^|\s)(?:(\d+):(\d+)(?::(\d+))?\.(\d+)|(\d+\.?\d*))\s*s\b", re.I)
# Full line prefix like [00:02:00] (hours may be 0; podcast lines use HH:MM:SS)
_RE_BRACKET_HMS = re.compile(r"^\s*\[\s*(\d{1,2}):(\d{2}):(\d{2})\s*\]\s*")
_RE_LEADING_TS = re.compile(r"^\s*\[?\s*(\d+\.?\d*)\s*s?\s*\]?\s*", re.I)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "for", "with", "is",
    "are", "was", "were", "be", "being", "been", "it", "this", "that", "as", "at", "by",
    "from", "you", "your", "we", "they", "their", "our", "i", "he", "she", "them", "his",
    "her", "not", "do", "does", "did", "can", "could", "should", "would",
}

# Words so common in tech/business transcripts they should not carry evidence match alone.
_GENERIC_EVIDENCE_WORDS = frozenset(
    {
        "ai",
        "artificial",
        "intelligence",
        "business",
        "businesses",
        "small",
        "companies",
        "company",
        "leaders",
        "leader",
        "tech",
        "technology",
        "podcast",
        "episode",
        "today",
        "host",
        "guest",
        "really",
        "just",
        "even",
        "here",
        "think",
        "things",
        "many",
        "some",
        "people",
        "listen",
        "listeners",
        "talk",
        "into",
        "world",
        "like",
        "make",
        "get",
        "going",
        "know",
        "isnt",
        "isn't",
        "dont",
        "don't",
        "big",
        "giant",
        "giants",
        "future",
        "next",
        "time",
        "way",
        "ways",
        "work",
        "works",
        "said",
        "says",
    }
)


def _token_hits_sentence(word: str, sentence_lower: str) -> bool:
    """Plural/stem-friendly membership for overlap scoring."""
    if not word or not sentence_lower:
        return False
    if word in sentence_lower:
        return True
    if len(word) > 4 and word.endswith("s") and word[:-1] in sentence_lower:
        return True
    if len(word) > 3 and not word.endswith("s") and (word + "s") in sentence_lower:
        return True
    return False


def _distinctive_claim_tokens(claim_text: str) -> List[str]:
    """Non-stopword, non-generic tokens we expect to see in supporting evidence."""
    out: List[str] = []
    for w in _tokens(claim_text):
        if len(w) < 3 or w in _STOPWORDS or w in _GENERIC_EVIDENCE_WORDS:
            continue
        out.append(w)
    return out


def _distinctive_coverage(claim_text: str, sentence_text: str) -> float:
    """Fraction of distinctive claim words present in the sentence (0..1)."""
    dist = _distinctive_claim_tokens(claim_text)
    if not dist:
        return 0.0
    low = (sentence_text or "").lower()
    hits = sum(1 for w in dist if _token_hits_sentence(w, low))
    return hits / float(len(dist))


def _soft_evidence_concept_bonus(claim_text: str, sentence_lower: str) -> float:
    """
    Small boosts when paraphrases align (concerned/worried, cost/money, complexity/learning curve).
    """
    bonus = 0.0
    ct = set(_tokens(claim_text))
    if "concerned" in ct and any(
        x in sentence_lower for x in ("worried", "worry", "worries", "worrying")
    ):
        bonus += 0.14
    if ("costs" in ct or "cost" in ct) and any(
        x in sentence_lower for x in ("cost", "costs", "expensive", "price", "pricing")
    ):
        bonus += 0.12
    if "complexity" in ct and (
        "learning curve" in sentence_lower
        or ("curve" in sentence_lower and "learn" in sentence_lower)
    ):
        bonus += 0.12
    return min(0.22, bonus)


@dataclass
class EvidenceClaim:
    id: str
    timestamp: Optional[float]
    claim: str
    function: str
    usage: str


@dataclass
class SentenceUnit:
    idx: int
    text: str
    timestamp: Optional[float]


def _parse_timestamp_line(line: str) -> Tuple[Optional[float], str]:
    """
    Strip common transcript prefixes and return (seconds, rest of line).
    Prefer [HH:MM:SS] so we do not leave ':02:00]' junk in evidence text.
    """
    s = line or ""
    m = _RE_BRACKET_HMS.match(s)
    if m:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
        total = float(h * 3600 + mi * 60 + sec)
        return total, s[m.end() :].strip()
    m = _RE_LEADING_TS.match(s)
    if not m:
        return None, s
    try:
        return float(m.group(1)), s[m.end() :].strip()
    except ValueError:
        return None, s


def _trim_snippet_with_focus(text: str, claim_words: Sequence[str], max_len: int) -> str:
    s = (text or "").strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    low = s.lower()
    hit_idx = -1
    for w in claim_words:
        idx = low.find(w)
        if idx >= 0:
            hit_idx = idx if hit_idx < 0 else min(hit_idx, idx)
    if hit_idx < 0:
        return s[: max_len - 3].rsplit(" ", 1)[0] + "..."
    start = max(0, hit_idx - 28)
    end = min(len(s), start + max_len - 3)
    chunk = s[start:end].strip()
    if start > 0:
        chunk = "..." + chunk
    if end < len(s):
        chunk = chunk.rsplit(" ", 1)[0] + "..."
    return chunk


def _split_into_sentence_units(transcript: str) -> List[SentenceUnit]:
    """Sentence-level index for claim evidence assignment."""
    out: List[SentenceUnit] = []
    idx = 0
    for line in (transcript or "").splitlines():
        ts, rest = _parse_timestamp_line(line)
        line_text = (rest or "").strip()
        if not line_text:
            continue
        chunks = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line_text) if s.strip()]
        if not chunks:
            chunks = [line_text]
        for s in chunks:
            out.append(SentenceUnit(idx=idx, text=s, timestamp=ts))
            idx += 1
    return out


def _remove_fillers(text: str) -> str:
    s = (text or "").strip()
    s = re.sub(
        r"^(?:well|so|and so|you know|i mean|like)\b[\s,.-]*",
        "",
        s,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", s).strip()


def _truncate_words(text: str, max_words: int = 25) -> str:
    """
    Trim to max_words without trailing ellipsis (workflow JSON validation rejects '...').
    Prefer ending at a sentence boundary inside the kept span.
    """
    words = (text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    chunk = " ".join(words[:max_words])
    for sep in (". ", "? ", "! ", "; "):
        idx = chunk.rfind(sep)
        if idx >= 28:
            return chunk[: idx + 1].strip()
    tail = " ".join(words[: max(1, max_words - 1)])
    return tail.rstrip(",;:\"'") + "."


def _strip_orphan_timestamp_junk(text: str) -> str:
    """Remove leftover ':MM:SS]' fragments when timestamp parsing was wrong."""
    s = (text or "").strip()
    s = re.sub(r"^[\s:]*\d{1,2}:\d{2}(?::\d{2})?\s*\]\s*", "", s)
    return s


def _clean_evidence_snippet(text: str, max_words: int = 25) -> str:
    return _truncate_words(_remove_fillers(_strip_orphan_timestamp_junk(text)), max_words=max_words)


def _keyword_overlap(claim_text: str, sentence_text: str) -> float:
    c = {w for w in _tokens(claim_text) if w not in _STOPWORDS and len(w) > 2}
    s = {w for w in _tokens(sentence_text) if w not in _STOPWORDS and len(w) > 2}
    if not c or not s:
        return 0.0
    return len(c & s) / len(c)


def _score_sentence_for_claim(claim_text: str, sentence_text: str) -> float:
    """
    Blend semantic + keyword overlap + *distinctive* word coverage.
    Generic AI/business words alone must not outrank a sentence that shares the claim's specific terms.
    """
    sem = text_similarity(claim_text, sentence_text)
    key = _keyword_overlap(claim_text, sentence_text)
    dcov = _distinctive_coverage(claim_text, sentence_text)
    dist = _distinctive_claim_tokens(claim_text)
    low = (sentence_text or "").lower()
    base = (0.32 * sem) + (0.28 * key) + (0.40 * dcov)
    base += _soft_evidence_concept_bonus(claim_text, low)
    base = min(1.0, base)
    if len(dist) >= 3 and dcov < 0.34:
        base *= 0.38
    elif len(dist) >= 2 and dcov < 0.26:
        base *= 0.48
    return float(max(0.0, min(base, 1.0)))


def _deduplicate_claims_for_evidence(claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not txt:
            continue
        if any(text_similarity(txt, _clean_claim_text(str(o.get("text") or ""))) > 0.9 for o in out):
            continue
        out.append(c)
    return out


def _assign_unique_sentence_evidence(
    claims: List[Dict[str, Any]],
    sentence_units: List[SentenceUnit],
    *,
    near_dup_threshold: float = 0.85,
) -> Dict[str, Dict[str, Any]]:
    """
    Assign 1 distinct sentence per claim, avoiding reused/near-duplicate snippets.
    Pairs (claim, sentence) are sorted by score globally so a sentence goes to the claim
    that matches it best — not to whichever long claim is processed first.
    """
    used_idx: Set[int] = set()
    selected_snippets: List[str] = []
    assigned: Dict[str, Dict[str, Any]] = {}
    claim_done: Set[str] = set()

    pairs: List[Tuple[float, str, SentenceUnit]] = []
    for c in claims:
        cid = str(c.get("id") or "")
        claim_txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid or not claim_txt:
            continue
        for su in sentence_units:
            score = _score_sentence_for_claim(claim_txt, su.text)
            if score <= 0.10:
                continue
            pairs.append((score, cid, su))
    pairs.sort(key=lambda x: (-x[0], x[1], x[2].idx))

    for score, cid, su in pairs:
        if cid in claim_done:
            continue
        if su.idx in used_idx:
            continue
        snip = _clean_evidence_snippet(su.text, max_words=25)
        if not snip:
            continue
        if any(text_similarity(snip, prev) > near_dup_threshold for prev in selected_snippets):
            continue
        used_idx.add(su.idx)
        selected_snippets.append(snip)
        assigned[cid] = {
            "timestamp": su.timestamp,
            "evidence": snip,
            "confidence": round(max(0.0, min(score, 1.0)), 3),
            "source_type": "direct_statement",
        }
        claim_done.add(cid)
    return assigned


def _fallback_evidence_for_claim(
    claim_text: str,
    sentence_units: Sequence[SentenceUnit],
    used_snippets: Sequence[str],
) -> Tuple[Optional[float], str, float, str]:
    """
    Fallback policy when confidence is below gate:
    - Prefer highest keyword-overlap sentence not near-duplicate of used evidence.
    - If no good match, fallback to snippet matcher.
    """
    best: Optional[Tuple[float, SentenceUnit]] = None
    for su in sentence_units:
        snip = _clean_evidence_snippet(su.text, max_words=25)
        if not snip:
            continue
        if any(text_similarity(snip, prev) > 0.86 for prev in used_snippets):
            continue
        key = _keyword_overlap(claim_text, su.text)
        sem = text_similarity(claim_text, su.text)
        dcov = _distinctive_coverage(claim_text, su.text)
        low = su.text.lower()
        score = (0.22 * sem) + (0.28 * key) + (0.50 * dcov) + _soft_evidence_concept_bonus(
            claim_text, low
        )
        if best is None or score > best[0]:
            best = (score, su)
    if best and best[0] >= 0.18:
        score, su = best
        return (
            su.timestamp,
            _clean_evidence_snippet(su.text, max_words=25),
            max(MIN_EVIDENCE_CONFIDENCE, float(score)),
            "low_confidence_fallback",
        )
    return None, "", 0.0, "low_confidence_fallback"


def _find_evidence_snippet(transcript: str, claim_text: str, max_len: int = 180) -> Tuple[Optional[float], str]:
    """Best-effort quote + optional timestamp from plain or lightly timestamped transcript."""
    if not transcript or not claim_text:
        return None, ""
    t = transcript.strip()
    claim_words = [w for w in _tokens(claim_text) if len(w) > 2][:8]
    if not claim_words:
        return None, ""
    best_ts: Optional[float] = None
    best_snip = ""
    best_score = 0
    for line in t.splitlines():
        ts, rest = _parse_timestamp_line(line)
        low = rest.lower()
        score = sum(1 for w in claim_words if w in low)
        if score > best_score and rest.strip():
            best_score = score
            best_ts = ts
            snip = _trim_snippet_with_focus(rest, claim_words, max_len)
            best_snip = snip
    if not best_snip:
        # fallback: first sentence containing a claim keyword
        for sent in re.split(r"(?<=[.!?])\s+", t):
            low = sent.lower()
            if sum(1 for w in claim_words if w in low) >= 2:
                s = sent.strip()
                s = _trim_snippet_with_focus(s, claim_words, max_len)
                return None, s
    return best_ts, best_snip


def _find_evidence_snippet_unique(
    transcript: str,
    claim_text: str,
    used_snippets: Sequence[str],
    max_len: int = 180,
) -> Tuple[Optional[float], str]:
    """Pick a best snippet that is not near-duplicate of already used snippets."""
    ts, snip = _find_evidence_snippet(transcript, claim_text, max_len=max_len)
    if not snip:
        return ts, snip
    if not any(text_similarity(snip, u) > 0.86 for u in used_snippets):
        return ts, snip

    claim_words = [w for w in _tokens(claim_text) if len(w) > 2][:8]
    best_ts: Optional[float] = None
    best_snip = ""
    best_score = -1.0
    candidates: List[Tuple[Optional[float], str]] = []
    for line in (transcript or "").splitlines():
        lts, rest = _parse_timestamp_line(line)
        rest = rest.strip()
        if not rest:
            continue
        candidates.append((lts, rest))
        # Also evaluate sentence-level candidates when a line contains many sentences.
        for sent in re.split(r"(?<=[.!?])\s+", rest):
            ss = sent.strip()
            if ss and ss != rest:
                candidates.append((lts, ss))

    used_token_set = set(_tokens(" ".join(used_snippets)))
    long_claim_words = {w for w in claim_words if len(w) >= 6}
    for lts, rest in candidates:
        overlap = sum(1 for w in claim_words if w in rest.lower())
        if overlap <= 0:
            continue
        novel_overlap = sum(1 for w in claim_words if w in rest.lower() and w not in used_token_set)
        long_word_overlap = sum(1 for w in long_claim_words if w in rest.lower())
        dup_penalty = max((text_similarity(rest, u) for u in used_snippets), default=0.0)
        score = (
            float(overlap)
            + (0.7 * novel_overlap)
            + (0.8 * long_word_overlap)
            - (dup_penalty * 3.0)
        )
        if score > best_score:
            best_score = score
            best_ts = lts
            best_snip = rest
    if best_snip:
        best_snip = _trim_snippet_with_focus(best_snip, claim_words, max_len)
        return best_ts, best_snip
    return ts, snip


def extract_claims(cleaned_transcript: str, claims: Sequence[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or ""))
        if txt:
            out.append(txt)
    if out:
        return out[:8]
    sentences = [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+", cleaned_transcript or "")
        if s.strip()
    ]
    return [s for s in sentences if len(s.split()) >= 7][:8]


def _is_low_signal_fragment(text: str) -> bool:
    t = (text or "").strip()
    if len(t.split()) < 6:
        return True
    if t.endswith(("...", "…")):
        return True
    if t and t[-1] not in ".!?":
        return True
    low = t.lower()
    if _is_meta_topic_line(t) or _is_narrative_meta_noise(t):
        return True
    bad_markers = ("you know", "kind of", "sort of", "those are all ways", "um", "uh")
    if any(b in low for b in bad_markers):
        return True
    # Mid-sentence splices pasted as "insights"
    if re.search(r"\b(if you will|tentacle|bullpen of little)\b", low):
        return True
    if low.endswith((" to.", " by.", " for.", " and.", " the.")) and len(t.split()) < 18:
        return True
    # Truncated mid-clause (ASR splice ending on a function word)
    if re.search(r"\s(at|if|the|we|it|or|and|for|of|who)\s*\.\s*$", low):
        return True
    # "at 2 in the." / "work of." / "who carry."
    if re.search(
        r"\b(in the|work of|who carry|and who|to fight|still present)\s*\.\s*$", low
    ):
        return True
    # Stuttered repetition (ASR / copy glitch)
    if re.search(r"\b(\w{3,})\s+(?:\1\s+){2,}", low):
        return True
    return False


def _asr_truncation_markers(low: str, t: str) -> bool:
    """Shared ASR splice / ellipsis / stutter heuristics for claim and evidence strings."""
    if t.endswith(("...", "…")):
        return True
    if low.endswith((" to.", " by.", " for.", " and.", " the.")) and len(t.split()) < 18:
        return True
    if re.search(r"\s(at|if|the|we|it|or|and|for|of|who)\s*\.\s*$", low):
        return True
    if re.search(
        r"\b(in the|work of|who carry|and who|to fight|still present)\s*\.\s*$", low
    ):
        return True
    if re.search(r"\b(\w{3,})\s+(?:\1\s+){2,}", low):
        return True
    return False


def _is_broken_evidence_claim_line(text: str) -> bool:
    """
    True when a *claim* line is an ASR splice / truncation — not when it is short but complete.
    (Do not use ``_is_low_signal_fragment`` here: that rejects short valid claims.)
    """
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if _is_meta_topic_line(t) or _is_narrative_meta_noise(t):
        return True
    if _asr_truncation_markers(low, t):
        return True
    # Broken comma splices / filler questions common in ASR (not defensible "claims")
    if re.search(r"\bi think the\s*,", low):
        return True
    if re.search(r",\s*no,\s*not too much", low):
        return True
    if "you a little worried" in low and "?" in t:
        return True
    if re.search(r"yeah,\s*yeah,\s*yeah", low):
        return True
    if "what was it?" in low and len(t.split()) < 14:
        return True
    if low.count(",") >= 4 and len(t.split()) < 22:
        return True
    if t[-1] not in ".!?" and len(t.split()) > 12:
        return True
    # Mid-dialogue splice pasted as a "claim" (quoted speech + tail fragment)
    if t.count('"') >= 2 and len(t.split()) < 22 and t[-1] not in ".!?":
        return True
    if re.search(r'"\s*[A-Za-z].*\.\"\s+[A-Za-z]', t) and len(t.split()) < 24:
        return True
    # Distribution / CTA lines misclassified as argumentative claims
    if _is_distribution_cta_claim_line(t):
        return True
    return False


def _is_distribution_cta_claim_line(text: str) -> bool:
    low = (text or "").lower()
    if len(low) < 10:
        return False
    return any(
        k in low
        for k in (
            "patreon",
            "pin comment",
            "link in my description",
            "join my patreon",
            "early uncensored",
            "subscribe for",
            "hit the notification",
            "like and subscribe",
        )
    )


def _claim_conflicts_spine_hint(claim_text: str, spine_hint: str) -> bool:
    """
    When the episode spine is institutional/education, drop claims that are clearly
    meta-chat / tangents (Epstein chatter, Patreon, showbiz, COVID travel beats, unrelated
    name-drops) with no spine overlap.
    """
    spine = (spine_hint or "").lower()
    cl = (claim_text or "").lower()
    if len(spine) < 16 or len(cl) < 20:
        return False
    spine_edu = any(
        k in spine
        for k in (
            "rockefeller",
            "school",
            "education",
            "curriculum",
            "foundation",
            "brainwash",
            "psyop",
            "standardized",
        )
    )
    spine_edu = spine_edu or any(
        k in spine
        for k in (
            "christian",
            "faith",
            "church",
            "daniel",
            "business",
            "ai",
        )
    )
    if not spine_edu:
        return False
    anchor_touch = any(
        k in cl
        for k in (
            "rockefeller",
            "school",
            "education",
            "curriculum",
            "foundation",
            "standardized",
            "department of education",
            "brainwash",
        )
    )
    if anchor_touch:
        return False
    if any(
        k in cl
        for k in (
            "epstein",
            "patreon",
            "impulsive",
            "googly",
            "basketball writer",
            "humanitarian",
            "notification bell",
        )
    ):
        return True
    if any(
        k in cl
        for k in (
            "spread the virus",
            "zion national",
            "the redwoods",
            "went up to the redwoods",
            "going inside and being in the ac",
            "worst way to spread",
            "don't go outside",
            "do not go outside",
            "national park",
            "wasn't a single car",
            "wasnt a single car",
            "no single car",
            "driving through the national",
            "driving through the park",
            "last minute podcast",
            "go on your show",
            "very, very cool",
        )
    ):
        return True
    if "if you've been looking for a community" in cl and "it's called" in cl:
        return True
    if "so decentralized" in cl and "school" not in cl and "education" not in cl:
        return True
    if "rothschild" in cl:
        return True
    # Social / rapport filler on an education-history spine (not on-mic argument).
    if not anchor_touch:
        if "that's nice" in cl or "that’s nice" in cl:
            return True
        if "nice though" in cl and ("having a place" in cl or "to yourself" in cl):
            return True
        if re.match(r"^that'?s\s+nice\b", cl.strip()):
            return True
    # Nature / rapport beats on an education-policy spine (no institutional anchor).
    if "trees" in cl and ("biggest" in cl or "redwood" in cl or "world" in cl):
        return True
    if "touch with the outdoors" in cl or "get in touch with the outdoors" in cl:
        return True
    if "best medicine" in cl and len(cl.split()) < 16:
        return True
    if re.match(r"^(?:i mean,?\s+)?it changed my life\b", cl) and "school" not in cl and "education" not in cl:
        return True
    return False


def _strategist_mic_line_is_praise_or_meta(text: str) -> bool:
    """Host-to-host praise, booking chatter, or production meta — not episode argument lines."""
    t = (text or "").strip()
    low = t.lower()
    if len(low) < 20:
        return False
    if "go on your show" in low or "want to go on your" in low:
        return True
    if "last minute podcast" in low:
        return True
    if re.match(r"^that'?s why we'?re going to", low):
        return True
    if "i love" in low and any(
        x in low
        for x in (
            "your documentary",
            "stage of journalism",
            "stage of entertainment",
            "entertainment and media",
        )
    ):
        return True
    if "very, very cool" in low and "show" in low:
        return True
    if "that's nice" in low or "that’s nice" in low:
        if "having a place" in low or "nice though" in low or "to yourself" in low:
            return True
    if re.match(r"^that'?s\s+nice\b", low):
        return True
    return False


def _thesis_line_is_keyword_bullet_list(line: str) -> bool:
    """
    True when ``episode_thesis`` is a tag list (semicolons / short comma clauses) rather than one sentence.
    """
    t = (line or "").strip()
    if len(t) < 20:
        return False
    parts = [p.strip() for p in re.split(r"[;|]+", t) if p.strip()]
    if len(parts) < 3 and t.count(",") >= 3:
        parts = [p.strip() for p in t.split(",") if p.strip()]
    if len(parts) < 3:
        return False
    avg = sum(len(p.split()) for p in parts) / len(parts)
    low = t.lower()
    has_arg = any(
        x in low
        for x in (
            " argues ",
            " proves ",
            " demonstrates ",
            " shows ",
            " because ",
            " listeners ",
            " episode ",
        )
    )
    return avg <= 6 and not has_arg


def _normalize_keyword_salad_thesis(thesis: str, snap: Dict[str, Any]) -> str:
    if not _thesis_line_is_keyword_bullet_list(thesis):
        return thesis
    try:
        from .episode_intelligence import _title_signals_education_or_institutions_history
    except ImportError:
        from episode_intelligence import _title_signals_education_or_institutions_history

    title = str(snap.get("title") or "").strip()
    if _title_signals_education_or_institutions_history(title):
        return (
            "The episode argues that institutional and philanthropic forces shaped mass schooling and public attitudes — "
            "defend one specific, falsifiable mechanism on mic with primary sources, not slogans."
        )
    low_t = title.lower()
    if any(k in low_t for k in ("christian", "church", "faith", "biblical", "daniel")) and any(
        k in low_t for k in ("business", "ai", "market", "company")
    ):
        return (
            "The episode argues that faith-led operators must adapt to AI-era business incentives without outsourcing "
            "discernment — defend one measurable outcome (retention, revenue, or operating risk) and one concrete mechanism."
        )
    return _identity_spine_fallback_sentence(snap, build_identity_anchor({}, snap))


def _appendix_surface_line_keeps(text: str, spine_hint: str) -> bool:
    """Same spine / praise / ASR gates as strategist highlights, for workflow markdown appendix."""
    s = str(text or "").strip()
    if not s or is_low_signal_insight_line(s) or _is_meta_topic_line(s):
        return False
    if _strategist_mic_line_is_praise_or_meta(s):
        return False
    if _is_prompt_like_claim_line(s):
        return False
    if spine_hint and len(spine_hint.strip()) >= 16 and _claim_conflicts_spine_hint(s, spine_hint):
        return False
    if _is_broken_evidence_claim_line(s):
        return False
    # Newer surface-level gates: ASR splices, dangling pronouns, and production/equipment chatter
    # never belong as a surfaced highlight, quote, guest angle, or segment title.
    if _is_asr_artifact_line(s):
        return False
    if _is_dangling_pronoun_line(s):
        return False
    if _is_production_chatter_line(s):
        return False
    return True


def _is_broken_evidence_quote_line(text: str) -> bool:
    """
    True when an *evidence* pull-quote looks truncated or stutter-corrupted.
    Slightly more lenient than claim lines (longer quotes allowed before flagging missing terminal punct).
    """
    t = (text or "").strip()
    if not t:
        return True
    low = t.lower()
    if _is_meta_topic_line(t) or _is_narrative_meta_noise(t):
        return True
    if _asr_truncation_markers(low, t):
        return True
    if t[-1] not in ".!?" and len(t.split()) > 28:
        return True
    return False


def _generalize_sentence(text: str) -> str:
    s = _clean_claim_text(text).strip()
    if not s:
        return s
    # Strip bracket timestamps before leading \W+ trim — otherwise `[00:00:15]` becomes `00:00:15]`.
    s = re.sub(
        r"^\[[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\]\s*",
        "",
        s,
    )
    s = re.sub(r"^\W+", "", s)
    s = re.sub(r"\s+", " ", s)
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".!?":
        s += "."
    return _trim_insight_line(s, max_words=26)


def _polish_outbound_sentence(text: str, *, max_words: int = 26) -> str:
    """
    Light presentation cleanup for external-facing markdown:
    keep meaning, remove spoken filler, normalize casing/punctuation.
    """
    s = _generalize_sentence(str(text or ""))
    if not s:
        return s
    s = re.sub(r"(?i)\b(oh my gosh,?\s*man,?|you know,?|i mean,?)\b", "", s)
    s = re.sub(r"(?i)^like[\s,]+", "", s).strip()
    s = re.sub(r"(?i)^(?:then\s+)?you\s+have\s+the\s+cdc\s+reported\b", "The CDC reported", s)
    s = re.sub(r"\s*,\s*,\s*", ", ", s)
    s = re.sub(r"\s+([,.;!?])", r"\1", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".!?":
        s += "."
    return _trim_insight_line(s, max_words=max_words)


def _polish_followup_question_text(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return s
    m = re.search(r"([\"'“”‘’])([^\"“”‘’]{12,260})([\"'“”‘’])", s)
    if m:
        claim_q = _polish_outbound_sentence(m.group(2), max_words=30).rstrip(".!?")
        s = f"{s[:m.start(2)]}{claim_q}{s[m.end(2):]}"
    s = re.sub(r"\s*,\s*,\s*", ", ", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def _workflow_claim_line_is_actionable(text: str) -> bool:
    """
    Keep only workflow claim lines that are long and specific enough to support follow-ups, guests,
    or clip packaging. Filters out short slogan fragments that pass generic ASR gates.
    """
    s = str(text or "").strip()
    if not s:
        return False
    wc = len(s.split())
    if wc < 9:
        return False
    low = s.lower()
    if any(k in low for k in ("let's just", "lets just", "trying to", "kind of", "sort of")) and wc < 13:
        return False
    if _is_meta_topic_line(s) or _is_narrative_meta_noise(s) or is_low_signal_insight_line(s):
        return False
    return True


def _line_is_actionable_step(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return False
    low = s.lower()
    if len(s.split()) < 5:
        return False
    return any(
        low.startswith(v) or f" {v} " in low
        for v in (
            "verify",
            "confirm",
            "check",
            "compare",
            "pull",
            "cite",
            "re-cut",
            "rewrite",
            "cut",
            "add",
            "state",
            "label",
            "test",
            "ship",
            "record",
            "source",
        )
    )


def _workflow_actionable_steps(
    wf_analytics: Dict[str, Any],
    r3_analytics: Dict[str, Any],
    coach_report: Dict[str, Any],
    *,
    max_steps: int = 6,
) -> List[str]:
    """Prefer explicit action verbs; backfill from coach fix plan when analytics text is thin."""
    src = [str(x).strip() for x in (wf_analytics.get("actionable_steps") or r3_analytics.get("next_move") or []) if str(x).strip()]
    out: List[str] = []
    for s in src:
        if _line_is_actionable_step(s) and s not in out:
            out.append(s)
        if len(out) >= max_steps:
            return out[:max_steps]
    for s in [str(x).strip() for x in (coach_report.get("immediate_fix_plan") or []) if str(x).strip()]:
        if _line_is_actionable_step(s) and s not in out:
            out.append(s)
        if len(out) >= max_steps:
            return out[:max_steps]
    if not out:
        out = [
            "Confirm thesis vs tape, then cut one beat that does not test the core claim.",
            "Add one primary-source citation line before the first clipable claim.",
            "Close with one concrete listener action this week and how you will measure progress.",
        ]
    return out[:max_steps]


def transform_into_insights(
    raw_claims: Sequence[str],
    *,
    rules: str = INSIGHT_TRANSFORM_RULES,
) -> List[str]:
    _ = rules
    cleaned: List[str] = []
    for rc in raw_claims:
        g = _generalize_sentence(str(rc))
        if not g or _is_low_signal_fragment(g):
            continue
        cleaned.append(g)
    return remove_semantic_duplicates(cleaned, threshold=SEMANTIC_DUP_THRESHOLD)[:5]


def _top_theme_terms(text: str, top_n: int = 6) -> List[str]:
    counts: Dict[str, int] = {}
    for tok in _tokens(text):
        if tok in _STOPWORDS or len(tok) < 4:
            continue
        counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ranked[:top_n]]


def build_or_reconstruct_narrative(
    brief: Dict[str, Any],
    cleaned_transcript: str,
    insights: Sequence[str],
    *,
    rules: str = NARRATIVE_RECONSTRUCTION,
    output_mode: str = "full",
) -> Dict[str, Any]:
    _ = rules
    if output_mode == "diagnostic":
        return dict(_diagnostic_narrative_block())

    def _practical_action(seed: str) -> str:
        s = _clean_claim_text(seed)
        if not s:
            return "Run one simple 7-day experiment and track one measurable behavior change."
        phrase = " ".join(_tokens(s)[:6]) or "the main claim"
        return f"Test this week: apply {phrase} in one repeatable routine and measure the result."

    def _looks_meta(line: str) -> bool:
        low = (line or "").lower()
        bad = (
            "lacks a clear focus",
            "may confuse the audience",
            "no clear narrative",
            "insufficient signal",
            "not enough information",
            "mixed thoughts",
            "listeners are encouraged",
            "discussion highlights",
            "conversation suggests",
        )
        return any(b in low for b in bad)

    def _is_actionable(line: str) -> bool:
        low = (line or "").strip().lower()
        prefixes = (
            "test ",
            "run ",
            "choose ",
            "set ",
            "track ",
            "remove ",
            "add ",
            "make ",
            "do ",
            "pick ",
            "apply ",
        )
        return low.startswith(prefixes)

    bullets = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    bullets = [
        b
        for b in bullets
        if not _is_narrative_meta_noise(b) and not _is_meta_topic_line(b)
    ]
    if len(bullets) >= 2:
        thesis = bullets[0]
        mechanism = bullets[1]
        practical = bullets[2] if len(bullets) >= 3 else (
            insights[0] if insights else "Convert the main claim into one behavior listeners can test this week."
        )
        if _looks_meta(practical) or not _is_actionable(practical):
            practical = _practical_action(thesis)
        return {
            "core_thesis": _generalize_sentence(thesis),
            "supporting_mechanism": _generalize_sentence(mechanism),
            "practical_translation": _generalize_sentence(practical),
            "reconstructed": False,
        }
    terms = _top_theme_terms(cleaned_transcript)
    t1 = terms[0] if terms else "behavior"
    t2 = terms[1] if len(terms) > 1 else "results"
    seed = insights[0] if insights else "Clear systems outperform vague intentions."
    return {
        "core_thesis": _generalize_sentence(seed),
        "supporting_mechanism": _generalize_sentence(
            f"Repeated focus on {t1} and {t2} suggests process design drives consistent outcomes."
        ),
        "practical_translation": _generalize_sentence(_practical_action(seed)),
        "reconstructed": True,
    }


def _classify_claim_function(claim: str, evidence: str) -> str:
    low = f"{claim} {evidence}".lower()
    if any(k in low for k in ("because", "therefore", "leads to", "drives", "causes")):
        return "mechanism"
    if any(k in low for k in ("for example", "for instance", "such as")):
        return "example"
    if any(k in low for k in ("i ", "we ", "my ", "our ", "story")):
        return "anecdote"
    return "supports_argument"


def _derive_usage(claim: str, function: str) -> str:
    if function == "mechanism":
        return "Use as a teaching segment that explains cause-and-effect."
    if function == "example":
        return "Use as a concrete illustration before the main takeaway."
    if function == "anecdote":
        return "Use as a story beat to humanize the argument."
    return "Use as a framing claim for the episode thesis."


def build_evidence_mapping(
    claims: List[Dict[str, Any]],
    transcript: str,
) -> List[Dict[str, Any]]:
    """
    Structured evidence rows: id, claim, evidence, timestamp, type.
    Drops clips with no usable evidence string.
    """
    out: List[Dict[str, Any]] = []
    claims = _deduplicate_claims_for_evidence(claims)
    sentence_units = _split_into_sentence_units(transcript)
    if sentence_units:
        assigned = _assign_unique_sentence_evidence(claims, sentence_units)
    else:
        assigned = {}
    for c in claims:
        cid = str(c.get("id") or "")
        claim_txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid or not claim_txt:
            continue
        used_snips = [str(r.get("evidence") or "") for r in out if str(r.get("evidence") or "").strip()]
        row_data = assigned.get(cid)
        if row_data:
            ts = row_data.get("timestamp")
            ev = str(row_data.get("evidence") or "")
            conf = float(row_data.get("confidence") or 0.0)
            source_type = str(row_data.get("source_type") or "direct_statement")
        else:
            ts, ev = _find_evidence_snippet(transcript, claim_txt)
            ev = _clean_evidence_snippet(ev, max_words=25)
            conf = 0.45
            source_type = "fallback_match"
        if source_type == "direct_statement" and conf < MIN_EVIDENCE_CONFIDENCE:
            fts, fev, fconf, fsrc = _fallback_evidence_for_claim(
                claim_txt, sentence_units, used_snips
            )
            if fev:
                ts, ev, conf, source_type = fts, fev, fconf, fsrc
            else:
                ts2, ev2 = _find_evidence_snippet(transcript, claim_txt)
                ev2 = _clean_evidence_snippet(ev2, max_words=25)
                if ev2:
                    ts, ev, conf, source_type = (
                        ts2,
                        ev2,
                        MIN_EVIDENCE_CONFIDENCE,
                        "fallback_match",
                    )
        if not ev or len(ev.strip()) < 12:
            continue
        if _is_broken_evidence_claim_line(claim_txt):
            continue
        if _is_broken_evidence_quote_line(ev):
            continue
        fn = _classify_claim_function(claim_txt, ev)
        usage = _derive_usage(claim_txt, fn)
        row = EvidenceClaim(
            id=cid,
            timestamp=ts,
            claim=claim_txt,
            function=fn,
            usage=usage,
        )
        built = asdict(row)
        built["evidence"] = ev
        built["confidence"] = round(max(0.0, min(conf, 1.0)), 3)
        built["source_type"] = source_type
        ctype = str(c.get("claim_type") or "interpretation").lower()
        if ctype == "fact":
            built["type"] = "factual"
        elif ctype == "belief":
            built["type"] = "opinion_host"
        else:
            built["type"] = "interpretive"
        out.append(built)
    return out


def derive_application(insight: str) -> str:
    return (
        f"Convert this into one weekly test: {insight[:96]}{'…' if len(insight) > 96 else ''}"
    )


def derive_content_angle(insight: str) -> str:
    return (
        f"Use this as a segment hook, then pressure-test it with one counterexample."
    )


def inject_strategy_layer(insights: Sequence[str]) -> List[Dict[str, str]]:
    strategies: List[Dict[str, str]] = []
    for insight in insights:
        strategies.append(
            {
                "insight": insight,
                "application": derive_application(insight),
                "content_angle": derive_content_angle(insight),
            }
        )
    return strategies


def _first_question_token(claim: str) -> str:
    words = _tokens(claim)
    for w in words:
        if w not in _STOPWORDS:
            return w
    return "this claim"


_RE_DIALOGUE_SPEAKER_PREFIX = re.compile(
    r"^(?:host|guest|moderator|speaker\s*\d+|spk\s*\d+|announcer|narrator)\s*:\s*",
    re.I,
)


def _strip_dialogue_speaker_prefix(text: str) -> str:
    """Drop leading Host:/Guest: style tags from ASR/claim lines (keeps the spoken content)."""
    t = (text or "").strip()
    if not t:
        return t
    for _ in range(3):
        t2 = _RE_DIALOGUE_SPEAKER_PREFIX.sub("", t).strip()
        if t2 == t:
            break
        t = t2
    return t


def _claim_focus_phrase(claim: str, *, max_words: int = 26, max_chars: int = 200) -> str:
    """
    Short natural excerpt for embedding in host-style questions.
    Prefer a full clause/sentence when possible; avoid chopping mid-list (uses _trim_insight_line).
    """
    raw = str(claim or "").strip()
    txt = _strip_dialogue_speaker_prefix(_clean_claim_text(raw))
    if not txt:
        return "this claim"
    if len(txt) <= max_chars:
        return txt
    trimmed = _trim_insight_line(txt, max_words=max_words)
    if len(trimmed) <= max_chars:
        return trimmed
    cut = trimmed[: max_chars].rsplit(" ", 1)[0].rstrip(",;:\"'")
    if cut and cut[-1] not in ".!?":
        return cut + "."
    return cut


def _claim_id_numeric_suffix(cid: str) -> int:
    m = re.match(r"(?i)^[ac](\d+)$", str(cid).strip())
    if not m:
        return 0
    try:
        return int(m.group(1))
    except ValueError:
        return 0


def generate_questions(claims: Sequence[Dict[str, Any]], mode: str = "tension") -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    for c in claims:
        cid = str(c.get("id") or "")
        raw = str(c.get("text") or "")
        if not cid or not raw.strip():
            continue
        if mode != "tension":
            out[cid] = generate_engagement_questions(c)
            continue
        focus = _claim_focus_phrase(raw)
        slot = _claim_id_numeric_suffix(cid) % 3
        if slot == 0:
            contrarian = f"What would a domain expert challenge about '{focus}'?"
            validation = f"What concrete evidence would confirm or disprove '{focus}' this month?"
            application = f"What one change should a listener make tomorrow based on '{focus}'?"
        elif slot == 1:
            contrarian = f"What is the strongest counterexample listeners already believe that undercuts '{focus}'?"
            validation = (
                f"If '{focus}' is wrong, what should we expect to see in public records or data — "
                f"and did the episode check?"
            )
            application = f"What decision does '{focus}' imply for a listener this week (one sentence)?"
        else:
            contrarian = (
                f"Which definitions stay fuzzy in the argument around '{focus}' "
                f"(terms, agencies, or time periods)?"
            )
            validation = f"What primary source would move you from suspicion to proof on '{focus}'?"
            application = f"What follow-up question would you add in part two to pressure-test '{focus}'?"
        failure_case = f"When does '{focus}' fail, even if the intent is right?"
        out[cid] = {
            "failure_case": failure_case,
            "constraint": f"What real-world constraint blocks '{focus}' despite effort?",
            "contrarian": contrarian,
            "application": application,
            # Backward-compatible keys consumed by existing markdown/workflow adapters.
            "counterpunch": contrarian,
            "validation": validation,
        }
    return out


def identify_gaps(insights: Sequence[str]) -> List[str]:
    gaps: List[str] = []
    for i in insights:
        low = i.lower()
        if "because" not in low and "therefore" not in low:
            gaps.append("Mechanism is implied but not explicit.")
        if len(i.split()) < 9:
            gaps.append("Claim is concise but may lack concrete execution detail.")
    return remove_semantic_duplicates(gaps, threshold=0.92)[:4]


def recommend_guests(
    narrative: Dict[str, str],
    gaps: Sequence[str],
) -> List[Dict[str, str]]:
    _ = GUEST_RULES
    core = str(narrative.get("core_thesis") or "the core episode thesis")
    rows: List[Dict[str, str]] = [
        {
            "type": "Katy Milkman",
            "reason": f"Behavioral science lens on the thesis: {core[:80]}{'…' if len(core) > 80 else ''}",
            "angle": "evidence on habits, friction, and follow-through vs aspiration",
        },
        {
            "type": "Adam Grant",
            "reason": "Surfaces counter-evidence and tradeoffs the host may underweight.",
            "angle": "organizational psychology and constructive disagreement",
        },
        {
            "type": "Angela Duckworth",
            "reason": "Challenges assumptions about grit, goals, and what actually predicts outcomes.",
            "angle": "research-backed pushback on intuitive narratives",
        },
    ]
    if gaps:
        rows.append(
            {
                "type": "James Clear",
                "reason": gaps[0],
                "angle": "systems, environment design, and repeatable weekly actions",
            }
        )
    return rows[:5]


def compress_to_one_line(text: str, *, style: str = "memorable") -> str:
    _ = style
    words = (text or "").split()
    if not words:
        return "Strong systems beat vague intentions."
    short = " ".join(words[:15])
    return short.rstrip(" ,;:.") + "."


def generate_takeaway(narrative: Dict[str, Any], *, output_mode: str = "full") -> str:
    _ = TAKEAWAY_RULES
    if output_mode == "diagnostic" or narrative.get("diagnostic"):
        return (
            "Diagnostic mode: verify before you package — pick one thread, label fact vs. opinion, "
            "then decide what is safe to clip or repeat."
        )
    seed = str(narrative.get("core_thesis") or "")
    line = compress_to_one_line(seed, style="memorable")
    if len(line.split()) > 15:
        line = " ".join(line.split()[:15]).rstrip(" ,;:.") + "."
    return line


def _segment_planning_title_from_claim_text(txt: str, *, max_chars: int = 180) -> str:
    """
    Segment list labels: keep more of the claim than a hard 72-char cut, but stay readable.
    Prefer word boundaries (same helpers as insight trimming).
    """
    t = _clean_claim_text(str(txt or "")).strip()
    if not t:
        return ""
    if len(t) <= max_chars:
        return t
    trimmed = _trim_insight_line(t, max_words=32)
    if len(trimmed) <= max_chars:
        return trimmed
    cut = trimmed[:max_chars].rsplit(" ", 1)[0].rstrip(",;:\"'")
    return cut + ("…" if len(cut) < len(t) else "")


def build_executable_segments(
    claims: List[Dict[str, Any]],
    *,
    max_segments: int = 3,
) -> List[Dict[str, Any]]:
    """2–3 recording-ready segment specs; trigger_clip must be a real claim id."""
    segments: List[Dict[str, Any]] = []
    for i, c in enumerate(claims[:max_segments]):
        cid = str(c.get("id") or "")
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not cid:
            continue
        title = _segment_planning_title_from_claim_text(txt, max_chars=180)
        segments.append(
            {
                "segment_title": title or f"Segment {i + 1}",
                "trigger_clip": cid,
                "host_angle": "skeptical",
                "guest_angle": "defensive",
                "goal": str(c.get("why_it_matters") or "Separate perception from evidence."),
            }
        )
    return segments


def detect_signal_mode(brief: Dict[str, Any]) -> str:
    """
    HIGH_SIGNAL: clear thesis line with enough claim substance to argue and verify.
    LOW_SIGNAL: missing thesis, outline-only, or single thin claim — do not force a fake arc.
    """
    claims = [
        c
        for c in (brief.get("claims") or [])
        if isinstance(c, dict) and str(c.get("text") or "").strip()
    ]
    if not claims:
        return "LOW_SIGNAL"

    conf_score = {"low": 0.0, "medium": 0.6, "high": 1.0}
    strengths: List[float] = []
    unique_fps: Set[str] = set()
    for c in claims:
        txt = _clean_claim_text(str(c.get("text") or ""))
        if not txt:
            continue
        fp = re.sub(r"[^a-z0-9]+", " ", txt.lower()).strip()[:180]
        if fp:
            unique_fps.add(fp)
        length_score = min(len(txt.split()) / 12.0, 1.0)
        conf = conf_score.get(str(c.get("confidence") or "").lower(), 0.3)
        mechanism_bonus = 0.15 if any(k in txt.lower() for k in ("because", "leads", "causes", "fails", "works")) else 0.0
        strengths.append((0.55 * length_score) + (0.35 * conf) + mechanism_bonus)

    avg_strength = sum(strengths) / len(strengths) if strengths else 0.0
    uniqueness_ratio = (len(unique_fps) / len(claims)) if claims else 0.0

    # Slightly lenient vs older 0.68 / 0.65 so borderline substantive two-claim episodes still
    # earn HIGH_SIGNAL when wording is tight but lacks a literal "because".
    if len(claims) >= 2 and avg_strength >= 0.62 and uniqueness_ratio >= 0.55:
        return "HIGH_SIGNAL"
    # Three+ distinct claims with moderate substance — still clip/argue-grade even if wording is tight.
    if len(claims) >= 3 and avg_strength >= 0.52 and uniqueness_ratio >= 0.45:
        return "HIGH_SIGNAL"
    if len(claims) == 1:
        conf = str(claims[0].get("confidence") or "").lower()
        txt = str(claims[0].get("text") or "").strip()
        if conf == "high" and len(txt) >= 45 and any(k in txt.lower() for k in ("because", "therefore", "fails", "works")):
            return "HIGH_SIGNAL"
        if conf in ("high", "medium") and len(txt) >= 55 and "because" in txt.lower():
            return "HIGH_SIGNAL"
    return "LOW_SIGNAL"


def _brief_flags_insufficient_narrative(brief: Dict[str, Any]) -> bool:
    """True when v2/brief explicitly says the episode has no usable arc (do not invent one)."""
    snap = brief.get("episode_snapshot") or {}
    pt = str(snap.get("primary_topic") or "").lower()
    if "insufficient signal" in pt or "no clear narrative" in pt:
        return True
    for line in brief.get("narrative") or []:
        low = str(line).lower()
        if "insufficient signal" in low or "no clear narrative" in low:
            return True
    return False


def _structural_packaging_ok(signal_mode: str, report_readiness: Dict[str, Any]) -> bool:
    """
    Enough grounded claims + evidence rows to justify full packaging when highlights are noisy
    or the signal classifier is borderline LOW (many atomic claims still extracted and anchored).
    """
    metrics = (report_readiness or {}).get("metrics") if isinstance(report_readiness, dict) else {}
    if not isinstance(metrics, dict):
        return False
    er = int((metrics or {}).get("evidence_row_count") or 0)
    cc = int((metrics or {}).get("claim_count") or 0)
    if er < 2 or cc < 2:
        return False
    sm = str(signal_mode or "").strip().upper()
    if sm == "HIGH_SIGNAL":
        return True
    # LOW_SIGNAL but 3+ claims + 2+ evidence rows: classifier was conservative; structure is still shippable.
    if sm == "LOW_SIGNAL" and cc >= 3:
        return True
    return False


def classify_output_mode(
    brief: Dict[str, Any],
    *,
    signal_mode: str,
    clean_insights: Sequence[str],
    report_readiness: Dict[str, Any],
) -> Tuple[str, List[str]]:
    """
    full — enough signal to justify prescriptive packaging (clips, spin-off, habit actions).
    diagnostic — withhold fake coherence; surface review + verification guidance instead.

    Primary gate: insufficient-narrative metadata, LOW_SIGNAL without grounded structure, or fewer
    than two reliable highlights (unless ≥2 evidence rows and ≥2 claims — HIGH_SIGNAL, or LOW with
    ≥3 claims and ≥2 evidence rows). Readiness ``band`` can be ``weak`` solely because the transcript is
    under ~500 words while claims are still strong — that case does not automatically force
    diagnostic mode.
    """
    if _brief_flags_insufficient_narrative(brief):
        return "diagnostic", [
            "Brief or metadata reports insufficient narrative / weak arc — prescriptive packaging withheld.",
        ]
    good = [
        x
        for x in clean_insights
        if str(x).strip() and not is_low_signal_insight_line(str(x))
    ]
    metrics = (report_readiness or {}).get("metrics") if isinstance(report_readiness, dict) else {}
    claim_ct = int((metrics or {}).get("claim_count") or 0)
    structure_ok = _structural_packaging_ok(signal_mode, report_readiness)
    if len(good) < 2 and not structure_ok:
        return "diagnostic", [
            "Fewer than two reliable highlight lines after quality filtering — prescriptive packaging withheld.",
        ]
    if signal_mode == "LOW_SIGNAL" and not structure_ok:
        return "diagnostic", [
            "Episode classified LOW_SIGNAL (thin thesis or weak claims) — prescriptive packaging withheld.",
        ]
    band = str((report_readiness or {}).get("band") or "").strip().lower()
    # ``minimal`` often means very short transcript *or* no claims — but a dense short clip can
    # still be HIGH_SIGNAL with solid claims; allow full mode in that case.
    if band == "minimal" and not (
        signal_mode == "HIGH_SIGNAL" and len(good) >= 2 and claim_ct >= 1
    ) and not structure_ok:
        return "diagnostic", [
            "Readiness band is minimal (very short transcript or missing claims) — prescriptive packaging withheld.",
        ]
    if band == "weak" and (signal_mode == "HIGH_SIGNAL" or structure_ok):
        return "full", []
    if band == "weak":
        return "diagnostic", [
            "Readiness band is weak — verify structure before treating clips or spin-offs as ready.",
        ]
    return "full", []


def _diagnostic_narrative_block() -> Dict[str, Any]:
    """Honest reconstruction when we must not invent a central 'thesis' for growth packaging."""
    return {
        "core_thesis": (
            "No dominant thesis line — the episode splits across competing threads rather than one "
            "defensible arc."
        ),
        "supporting_mechanism": (
            "Listeners will hear policy, personal commentary, and rhetorical claims in parallel; "
            "that fragmentation makes clip and takeaway packaging unreliable until edited."
        ),
        "practical_translation": (
            "Before you optimize for clips: separate factual reporting from opinion, flag what still "
            "needs verification, then choose one thread worth defending in public."
        ),
        "reconstructed": True,
        "diagnostic": True,
    }


def _evidence_timestamp_hint(evidence_mapping: List[Dict[str, Any]], limit: int = 5) -> str:
    """Suggest manual review windows from anchored evidence rows."""
    ts_vals: List[str] = []
    for row in evidence_mapping or []:
        if not isinstance(row, dict):
            continue
        ts = row.get("timestamp")
        if ts is None:
            continue
        try:
            ts_vals.append(f"{float(ts):.0f}s")
        except (TypeError, ValueError):
            continue
        if len(ts_vals) >= limit:
            break
    if not ts_vals:
        return (
            "No timestamped evidence rows — skim the transcript for moments that pair one clear claim "
            "with one concrete detail."
        )
    joined = ", ".join(ts_vals[:limit])
    return f"Manual review: prioritize segments around these anchor times — {joined}."


def compute_report_readiness(
    transcript: str,
    *,
    signal_mode: str,
    claim_count: int,
    evidence_row_count: int,
) -> Dict[str, Any]:
    """
    Honest expectations banner: transcript depth, signal mode, and what to do next.
    Shown in coach markdown and unified export so weak inputs read as tool limits, not bad prose.
    """
    words = len((transcript or "").split())
    notes: List[str] = []
    actions: List[str] = []

    if words < 150:
        notes.append("Transcript is very short — claims and evidence will be thin.")
        actions.append("Upload a longer transcript or full episode text for stronger structure.")
    elif words < 500:
        notes.append("Transcript is on the short side — borderline signal for automated claims.")
        actions.append("Aim for ~600+ words of continuous speech when possible.")

    if claim_count == 0:
        notes.append("No claims were extracted from the episode brief.")
        actions.append("Re-run with a richer brief pass or enable Ollama (SOAPBOXX_OLLAMA_MODEL).")

    if signal_mode == "LOW_SIGNAL":
        notes.append("Brief is classified as LOW_SIGNAL (thin thesis or weak / few claims).")
        actions.append("Tighten one thesis line and add timestamped examples in the source.")

    if evidence_row_count < 2 and claim_count >= 2:
        notes.append("Few evidence rows matched the transcript — verification will feel thin.")
        actions.append("Include bracketed times [MM:SS] or clear quotes so evidence can anchor.")

    if not notes:
        notes.append("Enough text and structure for a useful coach report.")

    if words < 150 or claim_count == 0:
        band = "minimal"
    elif signal_mode == "LOW_SIGNAL" or words < 500:
        band = "weak"
    elif signal_mode == "HIGH_SIGNAL" and evidence_row_count >= 2:
        band = "strong"
    else:
        band = "moderate"

    return {
        "band": band,
        "notes": notes[:8],
        "suggested_actions": actions[:4],
        "metrics": {
            "transcript_word_count": words,
            "claim_count": claim_count,
            "evidence_row_count": evidence_row_count,
            "signal_mode": signal_mode,
        },
    }


def merge_workflow_followups_into_engagement(
    report_v3: Dict[str, Any],
    workflow_report: Dict[str, Any],
) -> None:
    """
    When workflow AI produced follow_up_questions, fold them into ``engagement_questions``
    so coach markdown matches the workflow JSON (counterpunch / validation / application).
    Mutates ``report_v3`` in place.
    """
    fu = workflow_report.get("follow_up_questions") or []
    if not fu:
        return
    by_cid: Dict[str, Dict[str, str]] = {}
    for q in fu:
        if not isinstance(q, dict):
            continue
        cid = str(q.get("claim_id") or "").strip()
        qt = str(q.get("question_type") or "").lower().strip()
        text = str(q.get("question") or "").strip()
        if not cid or not text:
            continue
        tri = by_cid.setdefault(cid, {})
        if qt == "counter":
            tri["counterpunch"] = text
            tri["contrarian"] = text
        elif qt == "validation":
            tri["validation"] = text
        elif qt == "application":
            tri["application"] = text
    if not by_cid:
        return
    eng = dict(report_v3.get("engagement_questions") or {})
    for cid, tri in by_cid.items():
        if len(tri) < 2:
            continue
        prev = eng.get(cid) if isinstance(eng.get(cid), dict) else {}
        eng[cid] = {**prev, **tri}
    report_v3["engagement_questions"] = eng


def build_actionable_analytics(
    brief: Dict[str, Any],
    *,
    signal_mode: str = "LOW_SIGNAL",
) -> Dict[str, List[str]]:
    eg = brief.get("evidence_gaps") or {}
    supported = [str(x) for x in (eg.get("supported") or []) if str(x).strip()]
    weak = [str(x) for x in (eg.get("weak_or_unsupported") or []) if str(x).strip()]
    pm = brief.get("production_moves") or {}
    seg = pm.get("segment_to_run") or {}
    next_moves: List[str] = []
    g = (seg.get("goal") or "").strip()
    if g:
        next_moves.append(g)
    for row in brief.get("action_plan_7d") or []:
        t = str(row.get("task") or "").strip()
        if t and len(next_moves) < 4:
            next_moves.append(t)
    if not supported:
        snap = brief.get("episode_snapshot") or {}
        pt = str(snap.get("primary_topic") or "").strip()
        narr = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
        n0 = narr[0] if narr else ""
        if n0 and len(n0) > 18 and not _is_narrative_meta_noise(n0):
            supported = [n0[:280]]
        elif (
            pt
            and len(pt) > 12
            and not _is_meta_topic_line(pt)
            and "insufficient" not in pt.lower()
        ):
            supported = [f"Through-line (best effort): {pt[:220]}"]
        elif signal_mode == "LOW_SIGNAL":
            supported = ["Topic angles that could anchor a thesis once you pick one main line."]
        else:
            supported = ["Claims surfaced from transcript excerpts with structure scores above the keep threshold."]
    if not weak:
        weak = (
            [
                "No single thesis line yet; competing ideas may split attention.",
                "Hard for listeners to know what to clip or share.",
            ]
            if signal_mode == "LOW_SIGNAL"
            else ["Claims that lack timestamped or third-party verification."]
        )
    if not next_moves:
        next_moves = (
            [
                "Pick one thesis before you hit record; queue other topics for later episodes.",
                "Open with one story or number, not a topic list.",
                "Close with one test: what you'll measure and what would change your mind.",
            ]
            if signal_mode == "LOW_SIGNAL"
            else [
                "Pressure-test the strongest claim with one dedicated segment next episode."
            ]
        )
    return {
        "what_worked": supported[:5],
        "what_failed": weak[:5],
        "next_move": next_moves[:5],
    }


def _coach_follow_up_questions(
    brief: Dict[str, Any],
    engagement: Dict[str, Any],
    *,
    signal_mode: str,
    max_q: int = 6,
) -> List[str]:
    """
    4–6 sharp, usable questions: brief host questions first, then one engagement angle per claim
    (breadth-first) so we do not repeat three long quote-blocks from a single claim.
    """
    out: List[str] = []
    pm = brief.get("production_moves") or {}
    for q in pm.get("host_questions") or []:
        s = str(q).strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= max_q:
            return remove_semantic_duplicates(out, threshold=0.88)[:max_q]
    tri_keys: Tuple[str, ...] = ("counterpunch", "validation", "application")
    claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict) and str(c.get("id") or "").strip()]

    def _add_if_fresh(s: str) -> bool:
        s = str(s or "").strip()
        if not s:
            return False
        if any(text_similarity(s, o) > 0.88 for o in out):
            return False
        out.append(s)
        return True

    # Breadth-first: round 1 = counterpunch for each claim, round 2 = validation, then application.
    for key in tri_keys:
        if len(out) >= max_q:
            break
        for c in claims:
            if len(out) >= max_q:
                break
            cid = str(c.get("id") or "")
            tri = engagement.get(cid) or {}
            s = str(tri.get(key) or "").strip()
            _add_if_fresh(s)

    if len(out) < max_q:
        eg = brief.get("evidence_gaps") or {}
        for x in eg.get("proof_needed") or []:
            s = str(x).strip()
            if s:
                _add_if_fresh(f"What primary source or experiment would settle this: {s}?")
            if len(out) >= max_q:
                break
    if len(out) < 4:
        snap = brief.get("episode_snapshot") or {}
        pt = str(snap.get("primary_topic") or "").strip()
        if signal_mode == "LOW_SIGNAL":
            pool = [
                f"If you had to cut half this episode and keep one idea, what stays - and what becomes its own episode: {pt or 'your strongest thread'}?",
                "What metric would prove the opening worked - and what would you change if it didn't?",
                "What would a skeptical listener say you assumed without saying?",
            ]
        else:
            pool = [
                "What is the strongest fair counterargument to your sharpest claim - and what evidence would you accept?",
                "What should listeners do differently this week based on this episode alone?",
            ]
        for p in pool:
            if len(out) >= max_q:
                break
            _add_if_fresh(p)
    deduped = remove_semantic_duplicates(out, threshold=0.88)
    return deduped[:max_q]


def _coach_themes_from_brief(
    brief: Dict[str, Any], clean_insights: List[str], max_themes: int = 4
) -> List[Dict[str, str]]:
    snap = brief.get("episode_snapshot") or {}
    primary = str(snap.get("primary_topic") or "").strip()
    narrative = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    narrative = [n for n in narrative if not _is_narrative_meta_noise(n) and not _is_meta_topic_line(n)]
    seeds: List[str] = []
    if primary:
        seeds.append(primary)
    for n in narrative:
        if n not in seeds:
            seeds.append(n)
    for ins in clean_insights:
        if ins not in seeds:
            seeds.append(ins)
    if not seeds:
        seeds = ["Episode themes (add transcript depth for sharper themes)."]
    out: List[Dict[str, str]] = []
    for i, line in enumerate(seeds[:max_themes]):
        label = f"Theme {i + 1}"
        discussed = line[:240] + ("…" if len(line) > 240 else "")
        out.append(
            {
                "label": label,
                "discussed": discussed,
                "implying": "The show is treating this as actionable for the listener, not background noise.",
                "matters": "Turn this into one decision, one example, and one next step - or it stays noise.",
            }
        )
    return out


_COACH_THEME_BOILERPLATE_IMPLYING = (
    "The show is treating this as actionable for the listener, not background noise."
)
_COACH_THEME_BOILERPLATE_MATTERS = (
    "Turn this into one decision, one example, and one next step - or it stays noise."
)


def _compact_spine_for_diagnostic(
    spine: Dict[str, Any], report: Dict[str, Any], *, max_claims: int = 8
) -> Dict[str, Any]:
    """
    Diagnostic runs can carry dozens of atomic-pruned ASR rows; the coach HTML becomes unreadable
    if we list all of them again under **The spine** (and they duplicate the appendix). Keep the
    strongest on-spine lines only.
    """
    snap = report.get("episode_snapshot") or {}
    thesis = str(spine.get("thesis") or "").strip()
    hint = f"{snap.get('title') or ''} {snap.get('primary_topic') or ''} {thesis}".strip()
    kept: List[Dict[str, str]] = []
    seen: set[str] = set()
    for c in spine.get("claims") or []:
        if not isinstance(c, dict):
            continue
        line = str(c.get("line") or "").strip()
        cid = str(c.get("id") or "").strip()
        if not line or not cid:
            continue
        if is_low_signal_insight_line(line):
            continue
        if not _appendix_surface_line_keeps(line, hint):
            continue
        k = _normalized_evidence_claim_key(line)
        if not k or k in seen:
            continue
        seen.add(k)
        kept.append({"id": cid, "line": line})
        if len(kept) >= max_claims:
            break
    out = dict(spine)
    if kept:
        out["claims"] = kept
    elif spine.get("claims"):
        out["claims"] = (spine.get("claims") or [])[:5]
    return out


def _format_coach_themes_lines(
    themes: List[Any], *, h2: str = "## 2. Extracted themes", h2_clean: str = ""
) -> List[str]:
    """Avoid repeating the same implying/matters block under every theme when coach used boilerplate."""
    themes = [t for t in themes if isinstance(t, dict)]
    if not themes:
        return []
    h2b = h2_clean or h2
    lines: List[str] = ["", h2]
    all_boiler = all(
        str(t.get("implying") or "").strip() == _COACH_THEME_BOILERPLATE_IMPLYING
        and str(t.get("matters") or "").strip() == _COACH_THEME_BOILERPLATE_MATTERS
        for t in themes
    )
    if all_boiler:
        lines.append(
            "*Each line names a distinct thread; the same listener-action framing applies to each.*"
        )
        seen_disc: set[str] = set()
        kept_discussed: List[str] = []
        for th in themes:
            d = str(th.get("discussed") or "").strip()
            if not d:
                continue
            if d.lower().startswith("the core theme of this episode is"):
                continue
            nk = _normalized_evidence_claim_key(d)
            if nk in seen_disc:
                continue
            if any(text_similarity(d, prev) >= 0.74 for prev in kept_discussed):
                continue
            seen_disc.add(nk)
            kept_discussed.append(d)
            lab = str(th.get("label") or "Theme").strip()
            lines.append(f"- **{lab}:** {d}")
        lines.extend(
            [
                "",
                f"- **What this implies:** {_COACH_THEME_BOILERPLATE_IMPLYING}",
                f"- **Why it matters:** {_COACH_THEME_BOILERPLATE_MATTERS}",
                "",
            ]
        )
    else:
        if "(clean" in h2:
            clean_h = h2
        else:
            clean_h = f"{h2} (clean + structured)"
        lines = ["", clean_h]
        for th in themes:
            lines.append(f"**{th.get('label', 'Theme')}:**")
            lines.append(f"- What was discussed: {th.get('discussed', '')}")
            lines.append(f"- What the host is implying: {th.get('implying', '')}")
            lines.append(f"- Why it matters: {th.get('matters', '')}")
            lines.append("")
    return lines


def _polish_thesis_one_sentence(raw: str) -> str:
    """
    One sentence, clear stance: strip fluff, take first sentence, enforce ending punctuation.
    """
    s = _clean_claim_text(str(raw or "")).strip()
    if not s:
        return "Name one proposition a skeptical listener should accept after this episode."
    # Drop common filler openers (stance should read direct).
    low = s.lower()
    for prefix in (
        "this episode argues that ",
        "the episode argues that ",
        "the through-line: ",
        "the through-line for listeners:",
        "the through-line for listeners :",
        "in this episode, ",
    ):
        if low.startswith(prefix):
            s = s[len(prefix) :].strip()
            low = s.lower()
            break
    # First sentence only (avoid multi-sentence "thesis" blobs).
    for sep in (". ", "! ", "? "):
        if sep in s[: min(400, len(s))]:
            cut = s.split(sep, 1)[0] + sep.strip()[0]
            s = cut.strip()
            break
    else:
        if s.endswith("."):
            pass
        elif s and s[-1] not in ".!?":
            s += "."
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 220:
        s = s[:217].rsplit(" ", 1)[0] + "."
    return s


def _finalize_episode_thesis_line(
    snap: Dict[str, Any],
    thesis_quality: Optional[Dict[str, str]],
    signal_mode: str,
    claims: List[Dict[str, Any]],
    clean_insights: List[str],
) -> str:
    """Non-negotiable one-sentence thesis for spine + coach (argument, not vibes)."""
    use_claims = _claims_non_filler_for_thesis(claims)
    tq = thesis_quality
    if tq and str(tq.get("suggested_argument") or "").strip():
        out = _polish_thesis_one_sentence(str(tq["suggested_argument"]))
        out = _normalize_keyword_salad_thesis(out, snap)
        out = _coerce_thesis_off_episode_title(out, snap, {})
        if not _thesis_line_is_quote_like(out) and not _thesis_is_identity_stub(out, snap):
            return out
    if use_claims:
        raw = str(use_claims[0].get("text") or "").strip()
        if (
            raw
            and len(raw.split()) >= 8
            and not _looks_like_quote_fragment_thesis(raw)
        ):
            out = _polish_thesis_one_sentence(raw)
            out = _normalize_keyword_salad_thesis(out, snap)
            out = _coerce_thesis_off_episode_title(out, snap, {})
            if not _thesis_line_is_quote_like(out) and not _thesis_is_identity_stub(out, snap):
                return out
    out = _polish_thesis_one_sentence(
        _suggested_argument_thesis(snap, clean_insights, use_claims or claims or [])
    )
    out = _normalize_keyword_salad_thesis(out, snap)
    out = _coerce_thesis_off_episode_title(out, snap, {})
    if _thesis_is_identity_stub(out, snap):
        out = _polish_thesis_one_sentence(
            _suggested_argument_thesis(snap, clean_insights, use_claims or claims or [])
        )
        out = _normalize_keyword_salad_thesis(out, snap)
        out = _coerce_thesis_off_episode_title(out, snap, {})
    if not _thesis_line_is_quote_like(out):
        return out
    # Hard fallback: ensure the final thesis is an argumentative scaffold, not transcript dialogue.
    return _identity_spine_fallback_sentence(
        snap, "State one falsifiable claim this episode can defend on mic."
    )


def _default_expert_guest_blocks_for_topic(snap: Dict[str, Any], title: str) -> List[Dict[str, str]]:
    """
    When v3 has no mapped guests, suggest **domain-appropriate** archetypes — not a hard-coded education default.
    """
    blob = f"{str(snap.get('primary_topic') or '')} {title}".lower()
    if any(
        k in blob
        for k in (
            "neuro",
            "neuroscience",
            "brain plasticity",
            "neuroplasticity",
            "huberman",
            "circadian",
            "dopamine",
            "cortisol",
            "sleep",
            "synapse",
            "hippocampus",
            "optogenetics",
            "sensory system",
            "brain regeneration",
        )
    ):
        return [
            {
                "guest_type": "Neuroscience or physiology researcher (R1 lab)",
                "adds": "Verifies mechanistic claims against primary literature—protocols, effect sizes, and what is still contested.",
            },
            {
                "guest_type": "Science journalist (health / behavior beat)",
                "adds": "Separates established brain and behavior science from pop simplifications listeners may already believe.",
            },
        ]
    if any(
        k in blob
        for k in (
            "education",
            "school",
            "curriculum",
            "pedagogy",
            "student",
            "teacher",
            "district",
            "university policy",
        )
    ):
        return [
            {
                "guest_type": "Diane Ravitch",
                "adds": "U.S. education policy and reform narratives — stress-tests institutional claims with evidence.",
            },
            {
                "guest_type": "Jonathan Kozol",
                "adds": "Human-impact framing when the episode mixes policy with lived classroom outcomes.",
            },
        ]
    if any(k in blob for k in ("business", "founder", "startup", "ceo", "market", "revenue", "valuation")):
        return [
            {
                "guest_type": "Operator with P&L responsibility",
                "adds": "Pressure-tests whether the thesis survives hiring, capital, and execution tradeoffs—not just vision.",
            },
            {
                "guest_type": "Industry analyst or beats reporter",
                "adds": "Grounds competitive and market claims in numbers, filings, and comparable cases.",
            },
        ]
    return [
        {
            "guest_type": "Domain practitioner with measurement responsibility",
            "adds": "Tests whether the episode’s main claim would change a real-world decision, budget, or policy input.",
        },
        {
            "guest_type": "Methodologist (applied stats / social science)",
            "adds": "Challenges causality and effect-size language so the story does not overclaim from anecdotes.",
        },
    ]


def _personalized_coach_intro(creator: str, genre: str, title: str) -> str:
    """Light 'made for you' framing (creator / genre / title)."""
    c = (creator or "").strip()
    g = (genre or "").strip()
    t = (title or "").strip()
    if c and g:
        return f"*For **{c}**'s show - **{g}** format - tailored to this episode:*"
    if c:
        return f"*For **{c}**'s show, tailored to this episode:*"
    if g:
        return f"*Given your **{g}** format:*"
    if t:
        tail = t if len(t) <= 120 else t[:117] + "…"
        return f'*Tailored to "{tail}":*'
    return ""


def _pick_uncomfortable_title(title: str) -> str:
    opts = (
        "Why this episode is weaker than it sounds",
        "Where the argument breaks under pressure",
        "The uncomfortable read",
    )
    key = sum(ord(c) for c in (title or "")[:200]) % len(opts)
    return opts[key]


def _build_uncomfortable_insight(
    snap: Dict[str, Any],
    where_issues: List[str],
    signal_mode: str,
    title: str,
    clean_insights: List[str],
    episode_thesis: str,
) -> Dict[str, str]:
    """Direct, slightly sharp — the hook traditional coaching avoids."""
    tit = _pick_uncomfortable_title(title)
    parts: List[str] = []
    if signal_mode == "LOW_SIGNAL":
        parts.append(
            "The tape has more *topics* than *proof* — listeners may agree in the room and still "
            "repeat nothing specific tomorrow."
        )
    if where_issues:
        w0 = str(where_issues[0]).strip()
        parts.append(f"The pressure point is: {w0}")
    elif clean_insights:
        parts.append(
            "You signal stakes early, but the middle often stays atmospheric — the falsifiable claim "
            "arrives late or not at all."
        )
    else:
        parts.append(
            "Without a named mechanism, the story stays persuasive but not checkable — which caps clips and shares."
        )
    if episode_thesis:
        parts.append(
            f"If your thesis is “{episode_thesis[:160]}{'…' if len(episode_thesis) > 160 else ''}”, "
            "ask what would make you *wrong* on mic — not just what would make you sound fair."
        )
    pt = str(snap.get("primary_topic") or "").strip()
    if pt and not _is_meta_topic_line(pt) and len(title) > 8:
        parts.append(
            f"Someone scanning only the title may expect a harder verdict on “{pt[:80]}” than the conversation actually delivers."
        )
    body = " ".join(parts)
    return {"title": tit, "body": body}


def _build_claim_stakes_compact(
    claims: List[Dict[str, Any]],
    engagement: Dict[str, Any],
    max_rows: int = 5,
) -> List[str]:
    """
    Conclusions-only: one line per claim (what to prove on mic) — hides triad machinery.
    """
    out: List[str] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        raw = _clean_claim_text(str(c.get("text") or ""))[:200]
        if not raw:
            continue
        if _is_prompt_like_claim_line(raw):
            continue
        tri = engagement.get(cid) if isinstance(engagement.get(cid), dict) else {}
        counter = str((tri or {}).get("counterpunch") or "").strip()
        validate = str((tri or {}).get("validation") or "").strip()
        app = str((tri or {}).get("application") or "").strip()
        move = app or validate or counter
        if not move:
            move = "Name one source or number that would change your mind."
        line = f"**[{cid}]** {raw} — *On mic:* {move[:180]}{'…' if len(move) > 180 else ''}"
        out.append(line)
        if len(out) >= max_rows:
            break
    return out


_QUOTE_FRAGMENT_OPENERS = (
    "unfortunately,",
    "we're talking",
    "we are talking",
    "no, i'm",
    "no i'm",
    "at this point,",
    "thanks to things like",
    "i'm not even",
    "i am not even",
)


def _looks_like_quote_fragment_thesis(text: str) -> bool:
    """Cold opens often masquerade as a thesis — long quotes, hedges, or dialogue scraps."""
    t = (text or "").strip()
    if len(t) < 28:
        return False
    low = t.lower()
    if any(low.startswith(p) for p in _QUOTE_FRAGMENT_OPENERS):
        return True
    if len(t.split()) > 44:
        return True
    if t[0] in "\"'“”‘" and len(t) > 80:
        return True
    if t[-1] not in ".!?" and len(t) > 72:
        return True
    return False


def _thesis_line_is_quote_like(text: str) -> bool:
    """
    Final thesis must not be a raw transcript quote.
    """
    t = _clean_claim_text(str(text or "")).strip()
    if not t:
        return True
    low = t.lower()
    if _looks_like_quote_fragment_thesis(t):
        return True
    if re.match(r"^\[[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\]\s*", t):
        return True
    if re.match(r"^(?:host|guest|speaker|interviewer|caller)\s*:\s*", low):
        return True
    if re.search(r"\b(?:host|guest|speaker)\s*:\s*", low):
        return True
    if t and t[0] in "\"'“”‘":
        return True
    if re.match(r"^(?:well|yeah|look|you know|i mean)\b", low):
        return True
    return False


def _suggested_argument_thesis(
    snap: Dict[str, Any],
    clean_insights: List[str],
    claims: List[Dict[str, Any]],
) -> str:
    """One-sentence argumentative thesis — not a transcript quote."""
    claims = _claims_non_filler_for_thesis(claims) or claims
    title = str(snap.get("title") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()
    if title and len(title) > 12:
        tail = title.split(":")[-1].strip() if ":" in title else title
        tail = tail[:160].strip()
        if claims:
            raw = str(claims[0].get("text") or "").strip()
            g = _generalize_sentence(raw) if raw else ""
            if g and len(g) > 20 and not _looks_like_quote_fragment_thesis(g):
                frag = g[:200] + ("…" if len(g) > 200 else "")
                return f"{tail}: commit the episode to proving {frag}"
        if pt and not _is_meta_topic_line(pt) and len(pt) > 8:
            ptu = pt[:160] + ("…" if len(pt) > 160 else "")
            return f'{tail} — drive the edit around "{ptu}": one bet, one counter, one payoff.'
        return (
            f"{tail} — state one falsifiable claim this tape can defend; "
            f"cut beats that do not pressure-test it."
        )
    if pt and not _is_meta_topic_line(pt) and len(pt) > 8:
        return (
            f"{pt[:200]}{'…' if len(pt) > 200 else ''} — "
            f"one falsifiable claim, defended on the record."
        )
    if claims:
        g = _generalize_sentence(str(claims[0].get("text") or ""))
        if g and not _looks_like_quote_fragment_thesis(g):
            return g
    if len(clean_insights) > 1 and not _looks_like_quote_fragment_thesis(clean_insights[1]):
        return _generalize_sentence(clean_insights[1])
    return (
        "State one sentence: what single proposition should a skeptical listener accept after this episode?"
    )


def _derive_contrarian_hook(
    snap: Dict[str, Any],
    where_issues: List[str],
    clean_insights: List[str],
    title: str,
) -> str:
    """Non-obvious angle — complements 'organized' coaching."""
    if where_issues:
        w0 = str(where_issues[0]).strip()
        return (
            f"The edit points at: {w0} — the hidden angle is often **who benefits** if listeners stay "
            f"emotional but never name the rule, sponsor, or metric. Say that actor once, on mic."
        )
    if title:
        return (
            f"Listeners may already agree with the *vibe* of “{title[:90]}{'…' if len(title) > 90 else ''}”. "
            f"The gap is usually the **mechanism**: what rule, product design, or incentive makes the harm predictable?"
        )
    if clean_insights:
        return (
            "Steel-man the strongest counter-case you did not fully address — that is usually where "
            "the shareable clip lives."
        )
    return (
        "Name one stakeholder or incentive that wins if the audience feels the problem but cannot describe the system."
    )


def build_coach_report(
    brief: Dict[str, Any],
    transcript: str,
    signal_mode: str,
    *,
    clean_insights: List[str],
    evidence_mapping: List[Dict[str, Any]],
    engagement: Dict[str, Any],
    guests_v3: List[Dict[str, Any]],
    analytics: Dict[str, List[str]],
    claims: List[Dict[str, Any]],
    output_mode: str = "full",
    diagnostic_reasons: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Podcaster-facing coach structure (10 sections). Filled from brief + v3 fields; no transcript paste.
    """
    snap = brief.get("episode_snapshot") or {}
    title = str(snap.get("title") or "")
    narrative = [str(x).strip() for x in (brief.get("narrative") or []) if str(x).strip()]
    competing_topics: List[str] = []
    if narrative:
        competing_topics = narrative[:6]
    elif clean_insights:
        competing_topics = clean_insights[:6]
    else:
        pt = str(snap.get("primary_topic") or "").strip()
        if pt:
            competing_topics = [pt]

    thesis_quality: Optional[Dict[str, str]] = None
    fragment_lead: Optional[str] = None

    if signal_mode == "HIGH_SIGNAL" and claims:
        thesis = str(claims[0].get("text") or "").strip()
        if _looks_like_quote_fragment_thesis(thesis):
            thesis_quality = {
                "issue": "Lead claim reads like a cold-open clip, not a one-sentence argument.",
                "suggested_argument": _suggested_argument_thesis(snap, clean_insights, claims),
                "fix": "Reframe as stakes or mechanism — clips support a thesis; they are rarely the thesis.",
            }
            fragment_lead = thesis
    elif clean_insights and _looks_like_quote_fragment_thesis(clean_insights[0]):
        thesis_quality = {
            "issue": "First highlight reads like a clip, not a thesis.",
            "suggested_argument": _suggested_argument_thesis(snap, clean_insights, claims),
            "fix": "Open with the clip; state a separate one-sentence thesis.",
        }

    episode_thesis = _finalize_episode_thesis_line(
        snap, thesis_quality, signal_mode, claims, clean_insights
    )

    # --- 1. Diagnosis (thesis first; everything else supports it) ---
    diagnosis_lines: List[str] = []
    if output_mode == "diagnostic":
        diagnosis_lines.append(
            "**Report output:** Diagnostic mode — spin-off, clip, and habit-action blocks below are "
            "review-first, not publish-ready packaging."
        )
        if diagnostic_reasons:
            diagnosis_lines.append("**Why diagnostic:** " + " ".join(diagnostic_reasons))

    diagnosis_lines.append(f"**Thesis (one sentence):** {episode_thesis}")

    if signal_mode == "HIGH_SIGNAL" and claims:
        if fragment_lead:
            diagnosis_lines.append(
                "**Thesis check:** Your strongest line reads like transcript, not a publishable claim."
            )
            diagnosis_lines.append(f"**Verbatim lead (act one, not thesis):** {fragment_lead}")
        eg = brief.get("evidence_gaps") or {}
        sup = eg.get("supported") or []
        wk = eg.get("weak_or_unsupported") or []
        if sup:
            diagnosis_lines.append(
                "**Support:** " + "; ".join(str(x) for x in sup[:2] if str(x).strip())
            )
        if wk:
            diagnosis_lines.append(
                "**Gaps:** " + "; ".join(str(x) for x in wk[:2] if str(x).strip())
            )
    else:
        diagnosis_lines.append(
            "**Honest read:** The transcript reads exploratory or thin for one arc — "
            "or SoapBoxx could not extract a claim without inventing it."
        )
        if competing_topics:
            diagnosis_lines.append(
                "**Competing threads:** " + " | ".join(competing_topics[:5])
            )
        if clean_insights and _looks_like_quote_fragment_thesis(clean_insights[0]):
            diagnosis_lines.append(
                "**Note:** First highlight reads like a clip — open with it, but keep the thesis line separate."
            )

    diagnosis_lines.append(
        "**Retention:** One thesis → one repeatable idea for clips and shares."
    )

    themes = _coach_themes_from_brief(brief, clean_insights, max_themes=4)

    what_worked = list(analytics.get("what_worked") or [])[:5]
    pm = brief.get("production_moves") or {}
    clip_cands = pm.get("clip_candidates") or []
    for cl in clip_cands[:2]:
        s = str(cl).strip()
        if s and s not in what_worked:
            what_worked.append(f"Clip angle: {s}")
        if len(what_worked) >= 5:
            break

    where_issues: List[str] = list(analytics.get("what_failed") or [])[:5]
    rule_fix = (
        "One episode = one decision: pick the tradeoff you are defending, then cut everything that does not serve it."
        if signal_mode == "LOW_SIGNAL"
        else "Every segment must point back to the thesis; if it doesn't, it's a different episode."
    )

    contrarian_hook = {
        "title": "The angle listeners might miss",
        "body": _derive_contrarian_hook(snap, where_issues, clean_insights, title),
    }
    uncomfortable_insight = _build_uncomfortable_insight(
        snap, where_issues, signal_mode, title, clean_insights, episode_thesis
    )
    claim_stakes = _build_claim_stakes_compact(claims, engagement)
    personalized_intro = _personalized_coach_intro(
        str(snap.get("creator") or ""),
        str(snap.get("genre") or ""),
        title,
    )

    strongest = (
        clean_insights[0]
        if clean_insights
        else (competing_topics[0] if competing_topics else "Main theme")
    )
    spin_title = f"Deeper on: {strongest[:56]}{'…' if len(strongest) > 56 else ''}"
    spin_structure = (
        "(1) State the single problem. (2) One framework or story. (3) One listener action. (4) What you'll measure."
    )
    clip_ops: List[str] = []
    for cl in clip_cands[:2]:
        clip_ops.append(
            f"**Moment:** {str(cl)[:200]} - **Why:** Concrete promise + payoff; easy to title and share."
        )
    if not clip_ops and clean_insights:
        clip_ops.append(
            "**Moment:** Lead with your clearest promise - **Why:** Sets expectation so the rest of the episode can deliver."
        )
    seg_weak = str((pm.get("segment_to_run") or {}).get("name") or "Thesis line").strip()
    segment_idea = (
        f'Add a tight "{seg_weak}" block that forces one conclusion before you move topics - fixes drift without new gear.'
    )

    questions = _coach_follow_up_questions(
        brief, engagement, signal_mode=signal_mode, max_q=6
    )

    guest_blocks: List[Dict[str, str]] = []
    if signal_mode == "LOW_SIGNAL":
        strategy_intro = (
            "Exploratory guests (broad operators, skeptical peers) - pressure-test priorities, "
            "not credentials alone."
        )
        if not guests_v3:
            guest_blocks.append(
                {
                    "guest_type": "Operator / producer",
                    "adds": "Real tradeoffs from analytics and shipping schedule - turns topics into decisions.",
                }
            )
            guest_blocks.append(
                {
                    "guest_type": "Friendly skeptic host",
                    "adds": "Forces you to pick one thesis by disagreeing with your default.",
                }
            )
        for g in guests_v3[:3]:
            guest_blocks.append(
                {
                    "guest_type": str(g.get("guest") or g.get("role") or "Guest"),
                    "adds": str(g.get("why_this_episode") or "Sharpens the angle with lived experience."),
                }
            )
    else:
        strategy_intro = (
            "Expert guests (specific authority) - bring verification, edge cases, and citations tied to your thesis."
        )
        for g in guests_v3[:3]:
            guest_blocks.append(
                {
                    "guest_type": str(g.get("guest") or g.get("role") or "Expert"),
                    "adds": str(g.get("why_this_episode") or "Evidence and counterexamples for the main claim."),
                }
            )
        if not guest_blocks:
            t_low = (title or "").lower()
            if any(k in t_low for k in ("christian", "church", "faith", "biblical", "daniel")) and any(
                k in t_low for k in ("business", "ai", "company", "market")
            ):
                guest_blocks.extend(
                    [
                        {
                            "guest_type": "Faith-driven business operator",
                            "adds": "Pressure-tests whether the thesis survives real P&L, hiring, and operational tradeoffs.",
                        },
                        {
                            "guest_type": "AI governance / policy analyst",
                            "adds": "Separates plausible AI risk from hype and grounds claims in timelines and constraints.",
                        },
                    ]
                )
            else:
                guest_blocks.extend(_default_expert_guest_blocks_for_topic(snap, title))

    segment_upgrade = (
        f'**Single-ladder close (90s):** (1) One-sentence thesis. (2) One example or number. '
        f'(3) One behavior change. Fixes "outline without payoff" in a {signal_mode.lower()} episode.'
    )

    fix_plan_src = list(analytics.get("next_move") or [])[:5]
    _pad = [
        "Say your thesis out loud in the cold open; if you can't, rewrite before you record.",
        "Cut one competing topic and schedule it as a separate episode.",
        "End with one measurable test (metric or behavior) for the next show.",
    ]
    immediate_fix = list(fix_plan_src[:3])
    for p in _pad:
        if len(immediate_fix) >= 3:
            break
        if p not in immediate_fix:
            immediate_fix.append(p)
    immediate_fix = immediate_fix[:3]

    good = (
        "There is raw material and intent - enough to coach."
        if clean_insights or claims
        else "Metadata and topic scope are present; the work is shaping, not summarizing."
    )
    must_change = (
        "Pick one thesis and starve the rest until it lands."
        if signal_mode == "LOW_SIGNAL"
        else "Tighten evidence and conclusion around the lead claim."
    )
    if_fixed = (
        "Retention, clips, and referrals rise when listeners can repeat your idea in one sentence."
    )

    if output_mode == "diagnostic":
        spin_title = "Defer spin-off planning until one thesis thread survives an edit pass."
        spin_structure = (
            "Not assigned — the episode reads as multi-threaded or under-verified for a packaged spin-off brief."
        )
        clip_ops = [
            f"No high-signal auto clip picks. {_evidence_timestamp_hint(evidence_mapping)}",
            "Skip outros, transitions, and lyric fragments; favor one claim plus one checkable detail.",
        ]
        segment_idea = (
            "Next recording: a **validation block** — state the strongest public-facing claim, what would "
            "change your mind, and what primary source you would accept."
        )
        segment_upgrade = (
            "**Diagnostic close (90s):** Name the single sentence you'd defend if quoted; flag what still "
            "needs sourcing before you optimize for distribution."
        )
        immediate_fix = [
            "Tag assertions as reporting vs. inference vs. opinion before clipping.",
            "Write down two primary sources you want before repeating the hottest claim in public.",
            "Isolate segments that mix incompatible frames (news vs. rally vs. personal story).",
        ]
        good = (
            "There is usable tension for an informed audience; the gap is defensibility and arc — "
            "not chemistry or effort."
        )
        must_change = (
            "Stop expanding with growth packaging on a fragmented spine — verify or edit before you clip."
        )
        if_fixed = (
            "Clips and repurposing work once one arc is legible and claims are labeled for the audience you want."
        )
        strategy_intro = (
            "Diagnostic bookings: prioritize verification, sourcing, and steel-manned counterarguments — "
            "not generic motivation angles."
        )
        guest_blocks = [
            {
                "guest_type": "Reporter or records researcher",
                "adds": "Primary documents and timelines — reduces reliance on rhetorical peaks alone.",
            },
            {
                "guest_type": "Friendly skeptic (peer)",
                "adds": "Surfaces the strongest counter-case before you publish or clip.",
            },
        ]

    out_cr: Dict[str, Any] = {
        "signal_mode": signal_mode,
        "output_mode": output_mode,
        "episode_diagnosis": {
            "mode": signal_mode,
            "body": diagnosis_lines,
        },
        "thesis_quality": thesis_quality,
        "episode_thesis": episode_thesis,
        "personalized_intro": personalized_intro,
        "contrarian_hook": contrarian_hook,
        "uncomfortable_insight": uncomfortable_insight,
        "claim_stakes": claim_stakes,
        "themes": themes,
        "what_worked": what_worked[:5],
        "where_it_breaks": {"issues": where_issues, "rule": rule_fix},
        "opportunities": {
            "spinoff_title": spin_title,
            "spinoff_structure": spin_structure,
            "clip_moments": clip_ops,
            "segment_idea": segment_idea,
        },
        "follow_up_questions": questions,
        "guest_strategy": {"intro": strategy_intro, "guests": guest_blocks[:4]},
        "segment_upgrade": segment_upgrade,
        "immediate_fix_plan": immediate_fix,
        "bottom_line": {"good": good, "must_change": must_change, "if_fixed": if_fixed},
        "meta": {
            "title": title,
            "transcript_words": len((transcript or "").split()),
        },
    }
    return out_cr


def validate_references(
    report: Union[Dict[str, Any], str],
    *,
    valid_claim_ids: Optional[Set[str]] = None,
) -> Tuple[bool, List[str]]:
    """
    Ensure every referenced cN exists in valid_claim_ids.
    If valid_claim_ids is None, derive from report['claims'] or report['evidence_mapping'].

    Claim ids may be renumbered to ``aN`` by some pipeline stages while text blobs still carry
    ``[cN]`` references. Validation therefore compares numeric suffixes first (``c1`` matches
    ``a1``), then falls back to strict id matching when ids do not follow the expected pattern.
    """
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except json.JSONDecodeError:
            report = {"_raw": report}
    valid = valid_claim_ids
    if valid is None:
        valid = set()
        for c in report.get("claims") or []:
            if isinstance(c, dict) and c.get("id"):
                valid.add(str(c["id"]))
        for e in report.get("evidence_mapping") or []:
            if isinstance(e, dict) and e.get("id"):
                valid.add(str(e["id"]))
    blob = json.dumps(report, ensure_ascii=False)
    refs: Set[str] = set()
    ref_nums: Set[str] = set()
    for m in _REF_ID.finditer(blob):
        n = str(int(m.group(1)))
        refs.add(f"c{n}")
        ref_nums.add(n)
    valid_nums: Set[str] = set()
    for vid in valid:
        m = re.match(r"(?i)^[ac](\d+)$", str(vid).strip())
        if not m:
            continue
        valid_nums.add(str(int(m.group(1))))
    if not valid:
        if not refs:
            return True, []
        return False, [
            f"Dangling reference {r}: no claims defined in report" for r in sorted(refs)
        ]
    if valid_nums:
        bad_nums = sorted((n for n in ref_nums if n not in valid_nums), key=lambda x: int(x))
        bad = [f"c{n}" for n in bad_nums]
    else:
        bad = sorted(refs - valid)
    errors = [f"Invalid claim reference {bid}: not in {sorted(valid)}" for bid in bad]
    return len(bad) == 0, errors


# Cross-layer narrative alignment: single compile-time transform (see ``build_v3_report``).
# Jaccard tiers (short-text–aware): soft warning → repair → collapse — not one binary gate.
_CONSISTENCY_SOFT_WARN = 0.10
_CONSISTENCY_REPAIR = 0.07
_CONSISTENCY_COLLAPSE = 0.05


def _line_is_raw_title_packaging(line: str, snap: Dict[str, Any]) -> bool:
    """True when ``line`` is the episode title (or duplicate primary_topic), not an argumentative thesis."""
    t = (line or "").strip()
    if len(t) < 4:
        return False
    title = str(snap.get("title") or "").strip()
    pt = str(snap.get("primary_topic") or "").strip()

    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").lower()).strip()

    nt, ntitle, npt = norm(t), norm(title), norm(pt)
    if title and nt == ntitle:
        return True
    if pt and npt == nt and title and npt == ntitle:
        return True
    return False


def _coerce_thesis_off_episode_title(
    line: str,
    snap: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None,
) -> str:
    """Replace title/duplicate-topic strings with an honest argumentative placeholder."""
    if not _line_is_raw_title_packaging(line, snap):
        return line
    m = meta if isinstance(meta, dict) else {}
    anchor = build_identity_anchor(m, snap)
    return _identity_spine_fallback_sentence(snap, anchor)


def _identity_spine_fallback_sentence(snap: Dict[str, Any], anchor: str) -> str:
    """
    When narrative/coach lines are realigned to the identity anchor, we must not substitute the
    raw **episode title** as the argumentative thesis — titles are packaging, not claims (especially
    clickbait-shaped titles that share no tokens with transcript-sourced claims).
    """
    pt = str(snap.get("primary_topic") or "").strip()
    title = str(snap.get("title") or "").strip()
    if pt and not _is_meta_topic_line(pt):
        if not title or pt.lower() != title.lower():
            return pt[:280]
    if title:
        return (
            "The episode title is packaging — name one falsifiable claim this tape actually proves on mic."
        )
    return anchor[:280] if len(anchor) >= 8 else (
        "State one sentence this episode proves on the record."
    )


def _jaccard_tier(j: float) -> str:
    if j >= _CONSISTENCY_SOFT_WARN:
        return "ok"
    if j >= _CONSISTENCY_REPAIR:
        return "soft"
    if j >= _CONSISTENCY_COLLAPSE:
        return "repair"
    return "collapse"


def _refresh_coach_thesis_surfaces_after_identity(report: Dict[str, Any]) -> None:
    """
    After identity repair, ``episode_diagnosis`` can still show the pre-repair thesis line while
    ``coach_report.episode_thesis`` was updated — fix that drift. Also collapse obvious keyword-salad
    thesis lines toward a falsifiable sentence when title signals education/institutions.
    """
    cr = report.get("coach_report")
    if not isinstance(cr, dict):
        return
    snap = report.get("episode_snapshot") if isinstance(report.get("episode_snapshot"), dict) else {}
    et = str(cr.get("episode_thesis") or "").strip()
    if et and _thesis_line_is_keyword_bullet_list(et):
        et2 = _normalize_keyword_salad_thesis(et, snap)
        if et2 and et2.strip():
            cr["episode_thesis"] = et2
            et = et2.strip()
            nr = report.get("narrative_reconstruction")
            if isinstance(nr, dict):
                nr["core_thesis"] = et2
    et_final = str(cr.get("episode_thesis") or "").strip()
    if not et_final:
        return
    ed = cr.get("episode_diagnosis")
    if not isinstance(ed, dict):
        return
    body = ed.get("body")
    if not isinstance(body, list):
        return
    new_body: List[str] = []
    for line in body:
        s = str(line)
        if s.strip().startswith("**Thesis (one sentence):**"):
            new_body.append(f"**Thesis (one sentence):** {et_final}")
        else:
            new_body.append(s)
    ed["body"] = new_body
    # Keep uncomfortable-insight thesis quote aligned when thesis text was repaired downstream.
    ui = cr.get("uncomfortable_insight")
    if isinstance(ui, dict):
        ub = str(ui.get("body") or "").strip()
        if ub and "if your thesis is" in ub.lower():
            ub = re.sub(
                r"(?is)(if your thesis is [\"“]).{8,220}?([\"”],\s*ask what would make you \*wrong\* on mic)",
                rf"\1{et_final[:180]}\2",
                ub,
            )
            ui["body"] = ub


def _verification_hint_for_claim_text(text: str) -> str:
    """Short producer-facing hint: where to verify when the line looks citation-shaped."""
    t = (text or "").strip()
    if not t:
        return ""
    low = t.lower()
    if "cdc" in low:
        return "Confirm on CDC.gov primary releases (match exact report title + year before marketing)."
    if "fda" in low:
        return "Cross-check FDA.gov labeling or safety communications for the same wording."
    if "who" in low and "world health" in low:
        return "Use WHO.int primary pages or situation reports; avoid second-hand paraphrase alone."
    if "study" in low or "research shows" in low or "peer-reviewed" in low or "meta-analysis" in low:
        return "Name DOI, journal, or institutional PDF; avoid unattributed 'studies say.'"
    if re.search(r"\b20[12]\d\b", t) and any(
        w in low for w in ("law", "bill", "court", "ruling", "supreme", "statute", "executive order")
    ):
        return "Pin statute, docket, or legislative text (Congress.gov / court records) before repeating publicly."
    if "rockefeller" in low or ("foundation" in low and "grant" in low):
        return "Prefer 990s, grant databases, or contemporaneous documents over recap-only framing."
    return ""


def _apply_evidence_verification_hints(report: Dict[str, Any]) -> None:
    """Attach optional ``verification_note`` on evidence rows for producer-facing exports."""
    rows = report.get("evidence_mapping")
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        cl = str(row.get("claim") or "")
        hint = _verification_hint_for_claim_text(cl)
        if hint:
            row["verification_note"] = hint


def _v3_producer_workflow_markdown_lines(
    *,
    section_heading: str = "## 0b. Producer workflow (how to read this export)",
) -> List[str]:
    return [
        section_heading,
        "",
        "**A. Host & edit room (ship the episode):** The spine, §1 diagnosis, §1a–§1c, §8 segment upgrade, "
        "§9 fix plan, and appendix evidence — use these to cut, re-record, label reporting vs. opinion, and source.",
        "",
        "**B. Growth & packaging (after A is honest):** §3–§7, §5 opportunities, §6 follow-ups, §11 dual lens — "
        "treat as optional until thesis + verification are defensible.",
        "",
        "**Rule:** Anything not clearly grounded in your tape or a primary source you can name is **hypothesis** "
        "until you verify it. SoapBoxx does not replace legal, medical, or fact-check review.",
        "",
    ]


def _producer_workflow_orientation_lines() -> List[str]:
    """How a working producer should read the two halves of the report."""
    return _v3_producer_workflow_markdown_lines()


def _format_argument_rigor_lines(
    report: Dict[str, Any], *, section_heading: str = "## 0c. Argument rigor (constraint gate)"
) -> List[str]:
    """Scoreboard for claim/mechanism/evidence quality gates."""
    rigor = report.get("argument_rigor")
    if not isinstance(rigor, dict):
        return []
    score = int(rigor.get("score") or 0)
    status = str(rigor.get("status") or "REVIEW").strip().upper()
    gates = rigor.get("gates") if isinstance(rigor.get("gates"), list) else []

    lines: List[str] = [
        section_heading,
        "",
        f"**Argument rigor score:** {score}% · **Status:** {status}",
        "",
    ]
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        mark = "PASS" if gate.get("passed") else "FAIL"
        label = str(gate.get("label") or gate.get("id") or "Gate").strip()
        msg = str(gate.get("message") or "").strip()
        if msg and msg != "PASS":
            lines.append(f"- [{mark}] {label} — {msg}")
        else:
            lines.append(f"- [{mark}] {label}")
    if status != "PASS":
        lines.append("")
        lines.append(
            "*Use this as a pre-commit quality gate: weak fields should block distribution until rewritten.*"
        )
    lines.append("")
    return lines


def _sensitive_content_readiness_lines(report: Dict[str, Any]) -> List[str]:
    """Extra §0 bullets when heuristics detect health stats or high-risk people claims."""
    claims_blob = " ".join(
        str(c.get("text") or "") for c in (report.get("claims") or [])[:48] if isinstance(c, dict)
    ).lower()
    hits: List[str] = []
    if any(
        x in claims_blob
        for x in (
            "cdc",
            "suicide",
            "kill themselves",
            "killing themselves",
            "self-harm",
            "mental health crisis",
            "psychiatric",
        )
    ):
        hits.append(
            "**Health / crisis statistics:** Do not repeat numbers in marketing until you hold the primary "
            "source (report title, table, date). This tool does not verify medical or crisis statistics."
        )
    if any(x in claims_blob for x in ("minor", "underage", "child ", "children", "teen", "kids")) and any(
        x in claims_blob for x in ("abuse", "predator", "sexual", "exploit", "traffick")
    ):
        hits.append(
            "**Sensitive people-focused allegations:** Require corroboration and legal review before publication."
        )
    if not hits:
        return []
    out = ["**Extra readiness (sensitive topics detected):**"]
    out.extend(f"- {h}" for h in hits)
    out.append("")
    return out


def _format_producer_sign_off_section(
    report: Dict[str, Any],
    spine: Dict[str, Any],
    *,
    output_mode: str,
    signoff_heading: str = "",
) -> List[str]:
    """Pre-publish checklist block for producer-facing exports."""
    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else {}
    wb = cr.get("where_it_breaks") if isinstance(cr.get("where_it_breaks"), dict) else {}
    issues = [str(x).strip() for x in (wb.get("issues") or []) if str(x).strip()][:6]
    spine_claims = [c for c in (spine.get("claims") or []) if isinstance(c, dict)]
    h = (signoff_heading or "").strip() or "## 12. Producer sign-off (pre-publish)"

    lines: List[str] = [
        "",
        "---",
        h,
        "",
        "Internal checklist before clips, sponsor angles, or growth packaging leave your shop.",
        "",
        "### Claims you are willing to defend on mic (spine + tape)",
    ]
    if spine_claims:
        for c in spine_claims:
            cid = str(c.get("id") or "").strip()
            line = str(c.get("line") or "").strip()
            if not cid or not line:
                continue
            hint = _verification_hint_for_claim_text(line)
            if hint:
                lines.append(f"- **[{cid}]** {line} — *Verify:* {hint}")
            else:
                lines.append(
                    f"- **[{cid}]** {line} — *Label on mic:* reporting vs. interpretation vs. opinion."
                )
    else:
        lines.append("- *(No spine claims — repair extraction or add claims before signing.)*")

    lines.extend(["", "### Pressure points to clear (automation + your ear)"])
    if issues:
        for issue in issues:
            lines.append(f"- {issue}")
    else:
        lines.append(
            "- *(No automated pressure points — still stress-test the two most emotional claims yourself.)*"
        )
    if str(output_mode or "").strip().lower() == "diagnostic":
        lines.extend(
            [
                "",
                "**Diagnostic mode:** Treat spin-off, clip, and distribution language as **draft** until you "
                "complete verification on the spine thesis and top claims.",
            ]
        )
    lines.extend(
        [
            "",
            "### Sign when comfortable",
            "- [ ] I checked spine claims against the transcript (and primary sources where cited).",
            "- [ ] I labeled hot lines as reporting / inference / opinion before clipping.",
            "- [ ] I will not ship unverified health or legal allegations in public marketing copy.",
            "",
        ]
    )
    return lines


def apply_identity_consistency_to_report_v3(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    **Single enforcement point** for v3: run from ``build_v3_report`` only.

    - **Spine:** ``narrative_reconstruction`` fields use tiered Jaccard vs identity anchor.
    - **Coach:** ``episode_thesis`` is **not** blindly copied when both layers are plausibly
      on-identity: it mirrors the narrative spine only when the narrative layer was repaired,
      or when the coach line is severely off-anchor. Otherwise coach wording can diverge from
      reconstruction (interpretive layer preserved).
    - **Observability:** ``_consistency_tier_histogram``, ``_consistency_jaccard_samples``,
      ``_consistency_soft_suggestions`` (pressure for future edits / batch analytics — not silent).

    Sets ``_consistency_drift_notes`` when soft drift is detected; ``_consistency_fix_applied``
    when any replacement runs. Does not change claims, evidence rows, or scores.
    """
    meta = report.get("meta") if isinstance(report.get("meta"), dict) else {}
    snap = report.get("episode_snapshot") if isinstance(report.get("episode_snapshot"), dict) else {}
    anchor = build_identity_anchor(meta, snap)
    if len(anchor) < 8:
        return report

    fallback_thesis = _identity_spine_fallback_sentence(snap, anchor)

    drift_notes: List[str] = []
    soft_suggestions: List[str] = []
    tier_hist: Dict[str, int] = {"ok": 0, "soft": 0, "repair": 0, "collapse": 0}
    jaccard_samples: List[Dict[str, Any]] = []

    def _bump_tier(tier: str) -> None:
        if tier in tier_hist:
            tier_hist[tier] += 1

    fix = False
    narrative_layer_mutated = False
    nr = report.get("narrative_reconstruction")
    if not isinstance(nr, dict):
        nr = {}
        report["narrative_reconstruction"] = nr

    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else None

    def _align_nr_field(key: str) -> None:
        nonlocal fix, narrative_layer_mutated
        val = str(nr.get(key) or "").strip()
        if not val:
            return
        j = jaccard_tokens(val, anchor)
        tier = _jaccard_tier(j)
        _bump_tier(tier)
        jaccard_samples.append({"field": f"narrative_reconstruction.{key}", "jaccard": round(j, 4), "tier": tier})
        if tier == "ok":
            return
        if tier == "soft":
            drift_notes.append(f"{key}: soft_drift_vs_identity (jaccard={j:.3f})")
            soft_suggestions.append(
                f"Tighten {key} toward title/topic identity (jaccard={j:.3f}); "
                f"revisit before the next export if drift persists across episodes."
            )
            return
        if tier in ("repair", "collapse"):
            nr[key] = fallback_thesis
            fix = True
            narrative_layer_mutated = True
            drift_notes.append(f"{key}: realigned_to_identity (tier={tier}, jaccard={j:.3f})")

    # Primary spine first, then supporting fields (same tier rules).
    for key in ("core_thesis", "supporting_mechanism", "practical_translation"):
        _align_nr_field(key)

    insights = [str(x).strip() for x in (report.get("clean_insights") or [])[:5] if str(x).strip()]
    combined = " ".join(
        [
            str(nr.get("core_thesis") or ""),
            " ".join(insights[:3]),
        ]
    ).strip()
    if combined:
        jc = jaccard_tokens(combined, anchor)
        ct = _jaccard_tier(jc)
        _bump_tier(ct)
        jaccard_samples.append(
            {"field": "combined(core_thesis+clean_insights)", "jaccard": round(jc, 4), "tier": ct}
        )
        if jc < _CONSISTENCY_COLLAPSE:
            nr["core_thesis"] = fallback_thesis
            drift_notes.append("combined_insights_gate: collapse_to_identity_anchor")
            fix = True
            narrative_layer_mutated = True

    spine = str(nr.get("core_thesis") or fallback_thesis).strip()

    # Coach thesis: mirror repaired narrative, or fix standalone coach drift — else preserve coach.
    if cr is not None and spine:
        old_et = str(cr.get("episode_thesis") or "").strip()
        j_et = jaccard_tokens(old_et, anchor) if old_et else 1.0
        t_et = _jaccard_tier(j_et)
        if old_et:
            _bump_tier(t_et)
            jaccard_samples.append({"field": "coach_report.episode_thesis", "jaccard": round(j_et, 4), "tier": t_et})
        if narrative_layer_mutated:
            if old_et != spine:
                cr["episode_thesis"] = spine
                fix = True
                drift_notes.append("episode_thesis: mirrored_to_repaired_narrative_spine")
        elif old_et and t_et in ("repair", "collapse"):
            cr["episode_thesis"] = spine
            fix = True
            drift_notes.append("episode_thesis: realigned (off_anchor; narrative layer unchanged)")
        elif old_et and t_et == "soft":
            drift_notes.append(f"episode_thesis: soft_drift_vs_identity (jaccard={j_et:.3f})")
            soft_suggestions.append(
                f"Coach thesis wording drifts from identity (jaccard={j_et:.3f}); "
                f"optional manual contrast vs narrative reconstruction."
            )

    # Clip hooks: only rewrite on severe drift (collapse tier) — thesis vs packaging can differ.
    if cr is not None:
        opp = cr.get("opportunities") if isinstance(cr.get("opportunities"), dict) else {}
        cms_raw = opp.get("clip_moments") or []
        if isinstance(cms_raw, list) and cms_raw:
            new_cms: List[str] = []
            changed_cm = False
            for i, cm in enumerate(cms_raw):
                s = str(cm).strip()
                if not s:
                    continue
                j = jaccard_tokens(s, anchor)
                ct = _jaccard_tier(j)
                _bump_tier(ct)
                jaccard_samples.append(
                    {"field": f"coach_report.opportunities.clip_moments[{i}]", "jaccard": round(j, 4), "tier": ct}
                )
                if ct == "collapse":
                    new_cms.append(f"Anchor clips to the episode thesis: {spine[:120]}")
                    changed_cm = True
                else:
                    new_cms.append(s)
            if changed_cm:
                opp["clip_moments"] = new_cms[:8]
                cr["opportunities"] = opp
                fix = True

    # Title strings score "ok" vs the identity anchor (anchor includes the title), so Jaccard never
    # triggers repair — yet raw title/duplicate-topic lines are still not argumentative theses.
    if len(anchor) >= 8:
        coerced_title = False
        if cr is not None:
            et = str(cr.get("episode_thesis") or "").strip()
            et2 = _coerce_thesis_off_episode_title(et, snap, meta)
            if et2 != et:
                cr["episode_thesis"] = et2
                coerced_title = True
        nr_final = report.get("narrative_reconstruction")
        if isinstance(nr_final, dict):
            ct = str(nr_final.get("core_thesis") or "").strip()
            ct2 = _coerce_thesis_off_episode_title(ct, snap, meta)
            if ct2 != ct:
                nr_final["core_thesis"] = ct2
                coerced_title = True
        if coerced_title:
            fix = True
            drift_notes.append(
                "thesis_fields: coerced_off_raw_title_packaging (title echo is not a claim)"
            )

    report["_consistency_tier_histogram"] = tier_hist
    report["_consistency_jaccard_samples"] = jaccard_samples
    if soft_suggestions:
        report["_consistency_soft_suggestions"] = soft_suggestions
    if drift_notes:
        report["_consistency_drift_notes"] = drift_notes
    if fix:
        report["_consistency_fix_applied"] = True
    return report


def _distinctive_token_set(text: str) -> Set[str]:
    """Content tokens for cross-layer overlap (not stopwords / generic transcript filler)."""
    return {
        w
        for w in _tokens(text)
        if len(w) > 2 and w not in _STOPWORDS and w not in _GENERIC_EVIDENCE_WORDS
    }


def _union_identity_distinctive_bag(report: Dict[str, Any]) -> Set[str]:
    meta = report.get("meta") if isinstance(report.get("meta"), dict) else {}
    snap = report.get("episode_snapshot") if isinstance(report.get("episode_snapshot"), dict) else {}
    anchor = build_identity_anchor(meta, snap)
    bag = _distinctive_token_set(anchor)
    for c in report.get("claims") or []:
        if isinstance(c, dict):
            bag |= _distinctive_token_set(str(c.get("text") or ""))
    return bag


def _filter_clean_insights_identity_coherence(report: Dict[str, Any]) -> bool:
    """
    Drop clean_insight lines that share no distinctive vocabulary with the identity anchor + claims.
    Conservative: no-op when the bag is too small or every line would be removed.
    """
    ins = report.get("clean_insights")
    if not isinstance(ins, list) or not ins:
        return False
    bag = _union_identity_distinctive_bag(report)
    if len(bag) < 2:
        return False
    new: List[str] = []
    for line in ins:
        s = str(line).strip()
        if not s:
            continue
        if _distinctive_token_set(s) & bag:
            new.append(s)
    if not new or len(new) >= len(ins):
        return False
    rr = report.get("report_readiness") if isinstance(report.get("report_readiness"), dict) else {}
    if len(new) < 2 and _structural_packaging_ok(str(report.get("signal_mode") or ""), rr):
        return False
    report["_clean_insights_coherence_filtered"] = len(ins) - len(new)
    report["clean_insights"] = new
    return True


def _refresh_dual_lens_and_takeaway(
    report: Dict[str, Any],
    brief: Dict[str, Any],
    cleaned: str,
    meta: Dict[str, str],
) -> None:
    """
    Recompute dual_lens + takeaway after identity / claim / SGV passes mutate narrative and coach text.
    Initial assembly happens earlier with pre-pass state; without this, exports can show a stale core story.
    """
    sm = str(report.get("signal_mode") or "")
    report["dual_lens"] = assemble_dual_lens_package(
        brief,
        cleaned,
        meta,
        signal_mode=sm,
        narrative_reconstruction=report.get("narrative_reconstruction") or {},
        coach_report=report.get("coach_report") or {},
        claims=list(report.get("claims") or []),
    )
    report["takeaway"] = generate_takeaway(
        report.get("narrative_reconstruction") or {},
        output_mode=str(report.get("output_mode") or "full"),
    )


def _v3_atomic_ground_truth_resolve(explicit: Optional[bool]) -> bool:
    if explicit is not None:
        return bool(explicit)
    v = os.getenv("SOAPBOXX_V3_ATOMIC_GROUND_TRUTH", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _brief_claim_row_from_atomic(c: Any) -> Dict[str, Any]:
    cat = str(getattr(c, "category", "") or "")
    if cat == "historical_fact":
        claim_type = "fact"
    elif cat == "rhetorical":
        claim_type = "belief"
    else:
        claim_type = "interpretation"
    return {
        "id": c.id,
        "text": _clean_claim_text(str(getattr(c, "raw_statement", "") or "")),
        "claim_type": claim_type,
        "confidence": getattr(c, "confidence", "medium"),
        "evidence_basis": getattr(c, "evidence_basis", "unknown"),
    }


def _filter_claim_rows_after_atomic(
    claims: List[Dict[str, Any]],
    *,
    min_score: float = 0.38,
    spine_hint: str = "",
) -> List[Dict[str, Any]]:
    """
    Drop ASR junk and low-structure sentences from atomic claim rows; renumber ``a1``… for stability.
    """
    try:
        from .episode_quality_gates import claim_structure_score
    except ImportError:
        from episode_quality_gates import claim_structure_score  # type: ignore
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for c in claims:
        if not isinstance(c, dict):
            continue
        txt = str(c.get("text") or "").strip()
        if not txt:
            continue
        if _claim_line_is_intro_filler(txt):
            continue
        if _is_broken_evidence_claim_line(txt):
            continue
        if _strategist_mic_line_is_praise_or_meta(txt):
            continue
        if spine_hint and _claim_conflicts_spine_hint(txt, spine_hint):
            continue
        scored.append((float(claim_structure_score(txt)), dict(c)))
    if not scored:
        return claims[:3] if claims else []
    scored.sort(key=lambda x: -x[0])
    kept = [c for s, c in scored if s >= min_score]
    if len(kept) < 2:
        kept = [c for _, c in scored[: min(5, len(scored))]]
    seen: Set[str] = set()
    deduped: List[Dict[str, Any]] = []
    for c in kept:
        k = re.sub(r"\s+", " ", str(c.get("text") or "").strip().lower())
        if not k or k in seen:
            continue
        seen.add(k)
        deduped.append(c)
    out: List[Dict[str, Any]] = []
    for i, c in enumerate(deduped[:24], start=1):
        row = dict(c)
        row["id"] = f"a{i}"
        out.append(row)
    return out


def _claim_text_fingerprint_for_atomic_align(text: str) -> str:
    s = _clean_claim_text(str(text or "")).strip()
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.lower())[:160]


def _claim_text_keys_from_v3_rows(claims: Sequence[Dict[str, Any]]) -> Set[str]:
    keys: Set[str] = set()
    for c in claims or []:
        if not isinstance(c, dict):
            continue
        fp = _claim_text_fingerprint_for_atomic_align(str(c.get("text") or ""))
        if fp:
            keys.add(fp)
    return keys


def _atomic_claim_ids_matching_text_keys(ap: Dict[str, Any], text_keys: Set[str]) -> Set[str]:
    allowed: Set[str] = set()
    for c in ap.get("claims") or []:
        if not isinstance(c, dict):
            continue
        raw = str(c.get("raw_statement") or c.get("text") or "")
        fp = _claim_text_fingerprint_for_atomic_align(raw)
        if fp and fp in text_keys:
            cid = str(c.get("id") or "").strip()
            if cid:
                allowed.add(cid)
    return allowed


def _filter_atomic_pipeline_json_to_claim_allowlist(
    ap: Dict[str, Any],
    allowed_ids: Set[str],
) -> Dict[str, Any]:
    """
    Prune serialized ``atomic_pipeline`` so JSON consumers see the same on-spine claims as v3 ``claims``.
    ``allowed_ids`` are **atomic** claim ids (e.g. ``c1``), not renumbered ``a1`` rows.
    """
    if not isinstance(ap, dict) or not allowed_ids:
        return ap
    out = copy.deepcopy(ap)
    out["claims"] = [
        c for c in (out.get("claims") or []) if isinstance(c, dict) and str(c.get("id") or "") in allowed_ids
    ]
    out["verification"] = [
        v
        for v in (out.get("verification") or [])
        if isinstance(v, dict) and str(v.get("claim_id") or "") in allowed_ids
    ]
    kept_ins: List[Dict[str, Any]] = []
    for ins in out.get("insights") or []:
        if not isinstance(ins, dict):
            continue
        dfc = ins.get("derived_from_claim_ids") or []
        if any(str(x) in allowed_ids for x in dfc):
            kept_ins.append(ins)
    out["insights"] = kept_ins
    out["clips"] = [
        c
        for c in (out.get("clips") or [])
        if isinstance(c, dict) and str(c.get("source_claim_id") or "") in allowed_ids
    ]
    kept_insight_ids = {str(i.get("id")) for i in kept_ins if i.get("id")}
    out["actions"] = [
        a
        for a in (out.get("actions") or [])
        if isinstance(a, dict) and str(a.get("insight_id") or "") in kept_insight_ids
    ]
    tg = out.get("topic_graph") if isinstance(out.get("topic_graph"), dict) else {}
    nodes = [n for n in (tg.get("nodes") or []) if isinstance(n, dict)]
    kept_nodes: List[Dict[str, Any]] = []
    for n in nodes:
        ecids = [str(x) for x in (n.get("evidence_claim_ids") or [])]
        if any(x in allowed_ids for x in ecids):
            kept_nodes.append(n)
    kept_topic_ids = {str(n.get("topic_id")) for n in kept_nodes if n.get("topic_id")}
    out["topic_graph"] = {
        "nodes": kept_nodes,
        "edges": [
            e
            for e in (tg.get("edges") or [])
            if isinstance(e, dict)
            and str(e.get("from_topic_id") or "") in kept_topic_ids
            and str(e.get("to_topic_id") or "") in kept_topic_ids
        ],
    }
    gr = [g for g in (out.get("guest_recommendations") or []) if isinstance(g, dict)]
    out["guest_recommendations"] = [
        g for g in gr if str(g.get("target_topic_id") or "") in kept_topic_ids
    ]
    if not out["guest_recommendations"] and gr:
        out["guest_recommendations"] = gr[: min(6, len(gr))]
    diag = out.get("diagnostics")
    if not isinstance(diag, dict):
        diag = {}
    else:
        diag = dict(diag)
    diag["claims_spine_pruned"] = True
    diag["claims_after_spine_prune"] = len(out["claims"])
    out["diagnostics"] = diag
    return out


def _pick_outreach_display_name(
    outreach_rows: List[Dict[str, Any]],
    *,
    label: str,
    why: str,
    target_claim: str,
    title_g: str,
    used_names: Set[str],
) -> str:
    """
    Match static outreach pool names to the graph guest using token overlap (Jaccard),
    so we do not always assign the i-th name modulo pool size regardless of fit.
    """
    if not outreach_rows:
        return f"{title_g} — {label[:120]}"
    tc = _strip_dialogue_speaker_prefix(_clean_claim_text(str(target_claim or "")))
    bucket = f"{label} {why} {tc} {title_g}"
    best_nm = ""
    best_sc = -1.0
    for r in outreach_rows:
        nm = str(r.get("name") or "").strip()
        if not nm or nm in used_names:
            continue
        row_blob = f"{r.get('angle', '')} {r.get('topic_angle', '')} {r.get('reason', '')}"
        sc = jaccard_tokens(bucket, str(row_blob))
        if sc > best_sc:
            best_sc = sc
            best_nm = nm
    if best_sc >= 0.05 and best_nm:
        return best_nm
    for r in outreach_rows:
        nm = str(r.get("name") or "").strip()
        if nm and nm not in used_names:
            return nm
    r0 = outreach_rows[0]
    return str(r0.get("name") or "").strip() or f"{title_g} — {label[:120]}"


def _v3_guests_from_atomic_recommendations(
    guests: Sequence[Any],
    topic_graph: Any,
    claim_by_id: Dict[str, Dict[str, Any]],
    *,
    episode_snapshot: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Map atomic guest recommendations to v3 guest rows.

    Uses the workflow outreach pool for **real public names** where possible; role+topic label is kept
    as supporting context in ``why_this_episode``.
    """
    out: List[Dict[str, Any]] = []
    nodes = list(getattr(topic_graph, "nodes", None) or [])
    topic_by_id = {str(getattr(n, "topic_id", "")): n for n in nodes if getattr(n, "topic_id", None)}

    primary_cid = next(iter(claim_by_id.keys()), "a1") if claim_by_id else "a1"
    name_pool: List[str] = []
    used_outreach_names: Set[str] = set()
    try:
        from soapboxx_v3_workflow import (
            _extract_subject_entities_from_claims,
            _guest_rows_from_outreach_domain,
            _infer_domain_from_entities,
        )
    except ImportError:
        from .soapboxx_v3_workflow import (
            _extract_subject_entities_from_claims,
            _guest_rows_from_outreach_domain,
            _infer_domain_from_entities,
        )
    claims_list = list(claim_by_id.values())
    subs = _extract_subject_entities_from_claims(claims_list)
    snap = episode_snapshot if isinstance(episode_snapshot, dict) else {}
    if not subs:
        for key in ("primary_topic", "title", "creator"):
            v = str(snap.get(key) or "").strip()
            if v:
                subs = [v]
                break
    domain = _infer_domain_from_entities(subs) if subs else "general_history"
    outreach_rows = _guest_rows_from_outreach_domain(str(domain), str(primary_cid), limit=8)
    name_pool = [str(r.get("name") or "").strip() for r in outreach_rows if str(r.get("name") or "").strip()]

    for _, g in enumerate(guests):
        tid = str(getattr(g, "target_topic_id", "") or "")
        topic = topic_by_id.get(tid)
        label = ""
        if topic is not None:
            label = str(getattr(topic, "label", "") or "").strip()
        if not label:
            label = "topic cluster"
        target_claim = ""
        if topic is not None:
            for cid in list(getattr(topic, "evidence_claim_ids", None) or []):
                bc = claim_by_id.get(str(cid))
                if bc:
                    target_claim = str(bc.get("text") or "")
                    break
        if not target_claim:
            for bc in claim_by_id.values():
                target_claim = str(bc.get("text") or "")
                if target_claim:
                    break
        reason = getattr(g, "recommendation_reason", None)
        why = ""
        if reason is not None:
            why = str(getattr(reason, "primary_angle", "") or "").strip()
            if not why:
                why = str(getattr(reason, "what_they_would_challenge", "") or "").strip()
        gt = str(getattr(g, "guest_type", "") or "academic")
        title_g = gt.replace("_", " ").title()
        role_context = f"{title_g} — {label[:120]}"
        display = _pick_outreach_display_name(
            list(outreach_rows),
            label=label,
            why=why,
            target_claim=target_claim,
            title_g=title_g,
            used_names=used_outreach_names,
        )
        if display in name_pool:
            used_outreach_names.add(str(display))
        why_rich = why
        if name_pool and role_context:
            why_rich = f"{why} (Angle: {role_context})" if why else f"Suggested angle: {role_context}"
        out.append(
            {
                "guest": display,
                "role": gt,
                "why_this_episode": why_rich,
                "target_claim": _clean_claim_text(target_claim),
            }
        )
    return out


def build_v3_report(
    brief: Dict[str, Any],
    transcript: str,
    *,
    metadata: Optional[Dict[str, str]] = None,
    atomic_ground_truth: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Assemble full v3 report dict: clean insights, evidence rows, engagement, guests, segments, analytics.

    When atomic ground truth is on (default), structured claims and graph guests come from
    ``run_atomic_pipeline`` only; brief ``claims`` / ``guests`` rows are not used for those fields.
    """
    meta = dict(metadata or {})
    cleaned = transcript_for_v3_pipeline(transcript or "")
    snap_for_spine = dict(brief.get("episode_snapshot") or {})
    _sanitize_episode_snapshot(snap_for_spine, [])
    spine_hint = f"{snap_for_spine.get('title') or ''} {snap_for_spine.get('primary_topic') or ''}".strip()
    use_atomic = _v3_atomic_ground_truth_resolve(atomic_ground_truth)
    atomic_env: Any = None
    atomic_err: Optional[str] = None
    if use_atomic and run_atomic_pipeline is not None:
        try:
            atomic_env = run_atomic_pipeline(cleaned)
        except Exception as e:
            atomic_err = str(e)
            atomic_env = None

    if atomic_env is not None:
        claims = [_brief_claim_row_from_atomic(c) for c in atomic_env.claims]
        claims = _filter_claim_rows_after_atomic(claims, spine_hint=spine_hint)
        brief = {**brief, "claims": claims}
    elif use_atomic:
        claims = []
        brief = {**brief, "claims": claims}
    else:
        claims = [c for c in (brief.get("claims") or []) if isinstance(c, dict)]
    claim_by_id = {str(c.get("id")): c for c in claims if c.get("id")}

    raw_claims = extract_claims(cleaned, claims)
    transformed_insights = transform_into_insights(raw_claims, rules=INSIGHT_TRANSFORM_RULES)
    if transformed_insights:
        clean_insights = clean_key_highlights(transformed_insights)
    else:
        fallback_narrative = [str(x) for x in (brief.get("narrative") or []) if str(x).strip()]
        claim_texts = [str(c.get("text") or "") for c in claims]
        clean_insights = clean_key_highlights(fallback_narrative + claim_texts)

    evidence_mapping = build_evidence_mapping(claims, cleaned)
    for row in evidence_mapping:
        row.setdefault("function", "supports_argument")
        row.setdefault("usage", "Use as a framing claim for the episode thesis.")
    engagement = generate_questions(claims, mode="tension")
    strategies = inject_strategy_layer(clean_insights)

    guests_v3: List[Dict[str, Any]] = []
    if atomic_env is not None:
        guests_v3 = _v3_guests_from_atomic_recommendations(
            atomic_env.guest_recommendations,
            atomic_env.topic_graph,
            claim_by_id,
            episode_snapshot=dict(brief.get("episode_snapshot") or {}),
        )
    else:
        for g in brief.get("guests") or []:
            if not isinstance(g, dict):
                continue
            mid = str(g.get("maps_to_claim_id") or "").strip()
            claim = claim_by_id.get(mid) or (claims[0] if claims else {})
            if not claim:
                continue
            guests_v3.append(map_guest_to_claim(g, claim))
    gaps = identify_gaps(clean_insights)
    signal_mode = detect_signal_mode(brief)
    report_readiness = compute_report_readiness(
        cleaned,
        signal_mode=signal_mode,
        claim_count=len(claims),
        evidence_row_count=len(evidence_mapping),
    )
    v3_gates = evaluate_v3_quality_gates(brief, cleaned)
    report_readiness["quality_gates"] = v3_gates
    try:
        from .intelligence_ship_gate import assess_brief_intelligence_ship
    except ImportError:  # pragma: no cover
        from intelligence_ship_gate import assess_brief_intelligence_ship  # type: ignore
    ship_doc = assess_brief_intelligence_ship(brief)
    if ship_doc:
        report_readiness["intelligence_ship"] = ship_doc
        sg = str(ship_doc.get("ship_gate") or "").strip().upper()
        if sg == "FAIL":
            report_readiness["suggested_mode"] = "internal_only"
        elif sg == "REVIEW":
            report_readiness["suggested_mode"] = "review_required"
        elif sg == "PASS":
            report_readiness["suggested_mode"] = "external_ok"
    rnotes = report_readiness.get("notes")
    if not isinstance(rnotes, list):
        rnotes = []
        report_readiness["notes"] = rnotes
    for n in v3_gates.get("notes") or []:
        if n not in rnotes:
            rnotes.append(n)
    if ship_doc:
        for n in ship_doc.get("notes") or []:
            if isinstance(n, str) and n.strip() and n not in rnotes:
                rnotes.append(n)
    if atomic_err:
        rnotes.append(f"atomic_pipeline_error: {atomic_err}")

    output_mode, diagnostic_reasons = classify_output_mode(
        brief,
        signal_mode=signal_mode,
        clean_insights=clean_insights,
        report_readiness=report_readiness,
    )
    if v3_gates.get("force_diagnostic") and output_mode != "diagnostic":
        output_mode = "diagnostic"
        diagnostic_reasons = list(diagnostic_reasons or []) + [
            "Automated quality gates flagged title/topic mismatch or weak claim structure — prescriptive packaging withheld.",
        ]
    report_readiness["output_mode"] = output_mode
    report_readiness["diagnostic_reasons"] = diagnostic_reasons

    narrative = build_or_reconstruct_narrative(
        brief,
        cleaned,
        transformed_insights,
        rules=NARRATIVE_RECONSTRUCTION,
        output_mode=output_mode,
    )

    forced_guests = recommend_guests(narrative, gaps=gaps)
    if atomic_env is None and len(guests_v3) < 3:
        for fg in forced_guests:
            guests_v3.append(
                {
                    "guest": fg.get("type"),
                    "role": fg.get("type"),
                    "why_this_episode": fg.get("reason"),
                    "target_claim": narrative.get("core_thesis"),
                    "angle": fg.get("angle"),
                }
            )
            if len(guests_v3) >= 5:
                break

    segments = build_executable_segments(claims, max_segments=3)
    analytics = build_actionable_analytics(brief, signal_mode=signal_mode)
    coach_report = build_coach_report(
        brief,
        cleaned,
        signal_mode,
        clean_insights=clean_insights,
        evidence_mapping=evidence_mapping,
        engagement=engagement,
        guests_v3=guests_v3,
        analytics=analytics,
        claims=claims,
        output_mode=output_mode,
        diagnostic_reasons=diagnostic_reasons,
    )
    narrative = dict(narrative)
    _et = (coach_report or {}).get("episode_thesis")
    if _et and str(_et).strip():
        narrative["core_thesis"] = str(_et).strip()

    dual_lens = assemble_dual_lens_package(
        brief,
        cleaned,
        meta,
        signal_mode=signal_mode,
        narrative_reconstruction=narrative,
        coach_report=coach_report,
        claims=claims,
    )

    snap = dict(brief.get("episode_snapshot") or {})
    _sanitize_episode_snapshot(snap, claims)
    try:
        from .episode_intelligence import (  # type: ignore
            _refine_genre_from_title,
            override_primary_topic_with_storyline,
        )
    except ImportError:
        from episode_intelligence import (  # type: ignore
            _refine_genre_from_title,
            override_primary_topic_with_storyline,
        )
    # Re-refine genre on the v3 snapshot even when ``_normalize_brief`` already ran — belt & braces
    # so education/politics/history titles can't revert to a stale ``Entertainment`` label after
    # downstream copies of the brief snapshot are merged.
    snap["genre"] = _refine_genre_from_title(
        str(snap.get("title") or ""), str(snap.get("genre") or "")
    )
    # Storylines from v3 analytics take priority over a stale crime-beat or clickbait primary_topic.
    # narrative_reconstruction is a dict with optional "bullets" / "core_thesis"; extract list shapes.
    narrative_bullets: List[Any] = []
    if isinstance(narrative, dict):
        nb = narrative.get("bullets")
        if isinstance(nb, list):
            narrative_bullets = [str(x) for x in nb if x]
        ct = narrative.get("core_thesis")
        if isinstance(ct, str) and ct.strip():
            narrative_bullets.insert(0, ct.strip())
    elif isinstance(narrative, list):
        narrative_bullets = list(narrative)
    override_primary_topic_with_storyline(
        snap,
        storylines=(analytics.get("what_worked") if isinstance(analytics, dict) else None),
        narrative=narrative_bullets or None,
    )
    report: Dict[str, Any] = {
        "workflow_version": REPORT_V3_VERSION,
        "signal_mode": signal_mode,
        "dual_lens": dual_lens,
        "coach_report": coach_report,
        "episode_snapshot": snap,
        "narrative_reconstruction": narrative,
        "clean_insights": clean_insights,
        "evidence_mapping": evidence_mapping,
        "strategies": strategies,
        "engagement_questions": engagement,
        "guests": guests_v3,
        "segments": segments,
        "takeaway": generate_takeaway(narrative, output_mode=output_mode),
        "analytics_actionable": analytics,
        "claims": claims,
        "output_mode": output_mode,
        "meta": {
            "title": meta.get("title") or snap.get("title") or "",
            "creator": meta.get("creator") or snap.get("creator") or "",
            "genre": snap.get("genre") or meta.get("genre") or "",
            "generated_at": meta.get("generated_at") or _utc_now_iso(),
            "structured_intelligence_source": (
                "atomic_pipeline" if atomic_env is not None else "strict_episode_brief"
            ),
        },
        "report_readiness": report_readiness,
    }
    if atomic_env is not None and envelope_to_json is not None:
        raw_ap = envelope_to_json(atomic_env)
        pre_claim_n = len(raw_ap.get("claims") or [])
        align_keys = _claim_text_keys_from_v3_rows(claims)
        allowed_atomic = _atomic_claim_ids_matching_text_keys(raw_ap, align_keys)
        if allowed_atomic:
            pruned = _filter_atomic_pipeline_json_to_claim_allowlist(raw_ap, allowed_atomic)
            if len(pruned.get("claims") or []) > 0:
                report["atomic_pipeline"] = pruned
                post_claim_n = len(pruned.get("claims") or [])
                if pre_claim_n > post_claim_n + 2 and isinstance(rnotes, list):
                    rnotes.append(
                        f"spine_coherence: pruned {pre_claim_n - post_claim_n} off-spine atomic claim(s); "
                        "`atomic_pipeline` JSON now aligns with v3 export claims (matched transcript lines)."
                    )
            else:
                report["atomic_pipeline"] = raw_ap
        else:
            report["atomic_pipeline"] = raw_ap
            if align_keys and isinstance(rnotes, list):
                rnotes.append(
                    "spine_coherence: could not align atomic_pipeline to filtered claims; left full atomic envelope."
                )
    r3 = apply_identity_consistency_to_report_v3(report)
    _refresh_coach_thesis_surfaces_after_identity(r3)
    r3 = apply_claim_quality_gate(r3)
    r3 = apply_semantic_grounding_validator(r3)
    if _filter_clean_insights_identity_coherence(r3):
        r3["strategies"] = inject_strategy_layer(r3.get("clean_insights") or [])
    try:
        from .coach_synth import maybe_enrich_coach_report_with_llm
    except ImportError:
        from coach_synth import maybe_enrich_coach_report_with_llm  # type: ignore
    cr_final = r3.get("coach_report")
    if isinstance(cr_final, dict):
        maybe_enrich_coach_report_with_llm(
            brief,
            cleaned,
            cr_final,
            signal_mode=signal_mode,
            output_mode=output_mode,
            clean_insights=list(r3.get("clean_insights") or []),
            claims=list(r3.get("claims") or []),
        )
    _refresh_dual_lens_and_takeaway(r3, brief, cleaned, meta)
    _apply_evidence_verification_hints(r3)
    rigor = evaluate_argument_rigor_report(r3)
    r3["argument_rigor"] = rigor
    rr_final = r3.get("report_readiness")
    if isinstance(rr_final, dict):
        rr_final["argument_rigor_score"] = rigor.get("score")
        rr_final["argument_rigor_status"] = rigor.get("status")
        rr_notes = rr_final.get("notes")
        if not isinstance(rr_notes, list):
            rr_notes = []
            rr_final["notes"] = rr_notes
        for note in rigor.get("notes") or []:
            s = str(note).strip()
            if s and s not in rr_notes:
                rr_notes.append(s)
    try:
        from .episode_reference_shelf import collect_reference_shelf
    except ImportError:
        from episode_reference_shelf import collect_reference_shelf  # type: ignore
    r3["reference_shelf"] = collect_reference_shelf(r3)
    r3["_guest_decision_trace"] = build_guest_decision_trace(r3)
    apply_system_health_label(r3)
    r3["_invariant_contract_check"] = validate_v3_invariants(r3)
    return r3


def validate_v3_report_or_raise(report: Dict[str, Any]) -> None:
    valid = {str(c.get("id")) for c in (report.get("claims") or []) if c.get("id")}
    for e in report.get("evidence_mapping") or []:
        if isinstance(e, dict) and e.get("id"):
            valid.add(str(e["id"]))
    ok, errs = validate_references(report, valid_claim_ids=valid)
    if not ok:
        raise ValueError("; ".join(errs))


def build_episode_spine(
    r3: Dict[str, Any],
    workflow_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single structured object: **thesis → claims → guests**. All other sections are supporting detail.
    ``workflow_report`` adds guest rows with ``claim_id`` when enrichment ran.
    """
    wf = workflow_report or {}
    snap = r3.get("episode_snapshot") or {}
    nr = r3.get("narrative_reconstruction") or {}
    cr = r3.get("coach_report") or {}

    thesis = str(cr.get("episode_thesis") or "").strip()
    if not thesis:
        thesis = str(nr.get("core_thesis") or "").strip()
    tq = cr.get("thesis_quality") if isinstance(cr.get("thesis_quality"), dict) else None
    if not thesis and tq and str(tq.get("suggested_argument") or "").strip():
        thesis = str(tq["suggested_argument"]).strip()
    if not thesis or _is_meta_topic_line(thesis):
        thesis = str(snap.get("primary_topic") or "").strip()
    if not thesis:
        ins = r3.get("clean_insights") or []
        if ins and str(ins[0]).strip():
            thesis = _generalize_sentence(str(ins[0]))[:280]
    if not thesis:
        thesis = (
            "State one argumentative thesis this episode should prove — then align every claim and guest to it."
        )

    claims_out: List[Dict[str, str]] = []
    for c in r3.get("claims") or []:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        txt = _clean_claim_text(str(c.get("text") or ""))[:360]
        if txt:
            claims_out.append({"id": cid, "line": txt})

    if not claims_out:
        for row in (r3.get("evidence_mapping") or [])[:12]:
            if not isinstance(row, dict):
                continue
            cid = str(row.get("id") or "").strip()
            if not cid:
                continue
            cl = _clean_claim_text(str(row.get("claim") or ""))[:360]
            if cl:
                claims_out.append({"id": cid, "line": cl})

    guests_out: List[Dict[str, str]] = []
    gr = _workflow_body_guest_rows(wf)
    for g in gr[:10]:
        if not isinstance(g, dict):
            continue
        guests_out.append(
            {
                "name": str(g.get("name") or "").strip(),
                "title": str(g.get("title") or g.get("role") or "").strip(),
                "claim_id": str(g.get("claim_id") or "").strip(),
                "angle": str(g.get("topic_angle") or g.get("angle") or "").strip(),
            }
        )
    if not guests_out:
        for g in (r3.get("guests") or [])[:6]:
            if not isinstance(g, dict):
                continue
            guests_out.append(
                {
                    "name": str(g.get("guest") or "").strip(),
                    "title": str(g.get("role") or "").strip(),
                    "claim_id": "",
                    "angle": str(g.get("why_this_episode") or "").strip(),
                }
            )

    return {"thesis": thesis, "claims": claims_out, "guests": guests_out}


def format_episode_spine_markdown_lines(
    spine: Dict[str, Any], *, first_heading: str = "## The spine", footer: Optional[str] = None
) -> List[str]:
    """Markdown block: thesis, then claims, then guests — everything routes through these."""
    lines: List[str] = [
        first_heading,
        "",
        f"**Thesis (one sentence):** {spine.get('thesis', '')}",
        "",
        "**Claims:**",
    ]
    claims = spine.get("claims") or []
    if claims:
        for c in claims:
            if not isinstance(c, dict):
                continue
            cid = str(c.get("id") or "")
            line = str(c.get("line") or "").strip()
            if cid and line:
                lines.append(f"- **[{cid}]** {line}")
    else:
        lines.append(
            "- *(No claims in this run — enable Ollama + strict episode brief extraction, "
            "or paste claims into your episode JSON for the v3 report.)*"
        )

    lines.extend(["", "**Guests:**"])
    guests = spine.get("guests") or []
    if guests:
        lines.append("| Guest | Role | Serves claim | Why book them |")
        lines.append("| --- | --- | --- | --- |")
        for g in guests:
            if not isinstance(g, dict):
                continue
            nm = str(g.get("name") or "").replace("|", "\\|")
            tl = str(g.get("title") or "").replace("|", "\\|")
            cid = str(g.get("claim_id") or "") or "—"
            ang = str(g.get("angle") or "").replace("|", "\\|")
            lines.append(f"| {nm} | {tl} | {cid} | {ang} |")
    else:
        lines.append(
            "- *(No guests mapped — run workflow AI enrichment, or use the Guest Strategy section below.)*"
        )

    if footer is not None:
        if footer:
            lines.append(footer)
    else:
        lines.append(
            "*Below: detail that should back the thesis, claims, and guest picks.*"
        )
    return lines




def _v3_export_framing() -> str:
    v = (os.getenv("SOAPBOXX_V3_FRAMING") or "full").strip().lower()
    if v in ("freebie", "preview", "teaser"):
        return "freebie"
    return "full"


def _export_header_tagline_for_framing() -> str:
    if _v3_export_framing() == "freebie":
        return (
            "*SoapBoxx **preview** — questions and booking direction from the transcript, "
            f"with optional deeper quality notes. v{REPORT_V3_VERSION}*"
        )
    return _export_header_tagline()


def _v3_what_this_is_block_lines() -> List[str]:
    return [
        "## What this is",
        "",
        "- A **teaser** from your tape: follow-up questions, guest angles, a tight thesis/claims/guests spine, "
        "and producer coaching in one pass.",
        "- The full product is built around **live, transcript-grounded questions**, booking/research workflows, "
        "and (over time) **category / show rankings** and competitive analytics — this PDF is a **light freebie**, "
        "not a full producer sign-off pack.",
        "",
    ]


def _v3_readiness_substance_lines(
    rr: Dict[str, Any],
    *,
    sm: str,
    rnotes: List[str],
    ract: List[str],
    metrics: Dict[str, Any],
    om: str,
    max_notes: Optional[int] = None,
    include_suggested_actions: bool = True,
) -> List[str]:
    """Readiness field lines (no section heading) — used for §0, Quick snapshot, or Deeper."""
    lines: List[str] = []
    band = str(rr.get("band") or "").strip()
    if band:
        lines.append(f"**Band:** {band}")
    if om:
        lines.append(f"**Output mode:** {om}")
    if om == "diagnostic" and rr.get("diagnostic_reasons"):
        lines.append("**Why diagnostic:**")
        for dr in rr.get("diagnostic_reasons") or []:
            lines.append(f"- {dr}")
    if metrics:
        wc = metrics.get("transcript_word_count")
        cc = metrics.get("claim_count")
        er = metrics.get("evidence_row_count")
        lines.append(
            f"*Words: {wc} · Claims: {cc} · Evidence rows: {er} "
            f"· Signal: {metrics.get('signal_mode', sm)}*"
        )
    nlist = [str(x).strip() for x in (rnotes or []) if str(x).strip()]
    if max_notes is not None and nlist:
        nlist = nlist[: max(0, int(max_notes))]
    if nlist:
        lines.append("")
        lines.append("**What this means:**")
        for n in nlist:
            lines.append(f"- {n}")
    if include_suggested_actions and ract:
        lines.append("")
        lines.append("**Suggested next steps:**")
        for a in ract:
            lines.append(f"- {a}")
    return lines


def _v3_coach_report_core_markdown_lines(
    cr: Any,
    *,
    om: str,
    skip_followup_and_guest: bool = False,
    hash_prefix: str = "##",
) -> List[str]:
    """All coach sections: Episode Diagnosis through Bottom Line. Uses ## or ### headings via hash_prefix."""
    h = (hash_prefix or "##").rstrip() or "##"
    lines: List[str] = [
        f"{h} 1. Episode Diagnosis",
    ]
    if not cr:
        lines.append("*Coach report unavailable - run `build_v3_report` with full pipeline.*")
        return lines

    intro = str(cr.get("personalized_intro") or "").strip()
    if intro:
        lines.append(intro)
    ed = cr.get("episode_diagnosis") or {}
    for para in ed.get("body") or []:
        lines.append(str(para))
    ui = cr.get("uncomfortable_insight") or {}
    ch = cr.get("contrarian_hook") or {}
    ui_body = str(ui.get("body") or "").strip() if isinstance(ui, dict) else ""
    ch_body = str(ch.get("body") or "").strip() if isinstance(ch, dict) else ""
    verify_boiler = "claims that lack timestamped"
    if ui_body and ch_body:
        if text_similarity(ui_body, ch_body) >= 0.55:
            ch = {}
        elif verify_boiler in ui_body.lower() and verify_boiler in ch_body.lower():
            ch = {}
    if isinstance(ui, dict) and ui_body:
        utit = str(ui.get("title") or "The uncomfortable read").strip()
        lines.extend([f"{h} 1a. {utit}", ui_body])
    if isinstance(ch, dict) and str(ch.get("body") or "").strip():
        lines.extend(
            [
                f"{h} 1b. {ch.get('title') or 'The angle listeners might miss'}",
                str(ch.get("body") or "").strip(),
            ]
        )
    stakes = cr.get("claim_stakes") or []
    if isinstance(stakes, list) and stakes:
        if om == "diagnostic":
            stakes = stakes[:5]
        lines.append("")
        lines.append(f"{h} 1c. Claim stakes (on-mic conclusions)")
        for row in stakes:
            lines.append(f"- {row}")
        lines.append("")
    lines.extend(
        _format_coach_themes_lines(cr.get("themes") or [], h2=f"{h} 2. Extracted themes")
    )
    lines.append(f"{h} 3. What Worked")
    for x in cr.get("what_worked") or []:
        lines.append(f"- {x}")
    if not cr.get("what_worked"):
        lines.append("- *(No strengths flagged yet - add transcript depth.)*")
    wb = cr.get("where_it_breaks") or {}
    lines.append("")
    lines.append(f"{h} 4. Where It Breaks")
    for x in (wb or {}).get("issues") or []:
        lines.append(f"- {x}")
    lines.append(f"- **Rule:** {(wb or {}).get('rule', '')}")
    lines.append("")
    lines.append(f"{h} 5. Actionable Content Opportunities")
    opp = cr.get("opportunities") or {}
    lines.append("**A. Spin-off episode idea**")
    lines.append(f"- **Title:** {opp.get('spinoff_title', '')}")
    lines.append(f"- **Structure:** {opp.get('spinoff_structure', '')}")
    lines.append("")
    lines.append("**B. Clip opportunity**")
    for cm in opp.get("clip_moments") or []:
        lines.append(f"- {cm}")
    if not opp.get("clip_moments"):
        lines.append("- *(No clip candidates in brief - lead with your clearest promise.)*")
    lines.append("")
    lines.append("**C. Segment idea**")
    lines.append(f"- {opp.get('segment_idea', '')}")
    if not skip_followup_and_guest:
        lines.append("")
        lines.append(f"{h} 6. Smarter Follow-Up Questions")
        for q in cr.get("follow_up_questions") or []:
            lines.append(f"- {q}")
        gs = cr.get("guest_strategy") or {}
        lines.append("")
        lines.append(f"{h} 7. Guest Strategy")
        lines.append(str(gs.get("intro", "")))
        for g in gs.get("guests") or []:
            if isinstance(g, dict):
                lines.append(
                    f"- **{g.get('guest_type', 'Guest')}** - {g.get('adds', '')}"
                )
    lines.append("")
    lines.append(f"{h} 8. Segment Upgrade")
    lines.append(str(cr.get("segment_upgrade", "")))
    lines.append("")
    lines.append(f"{h} 9. Immediate Fix Plan (CRITICAL)")
    for i, step in enumerate(cr.get("immediate_fix_plan") or [], start=1):
        lines.append(f"{i}. {step}")
    bl = cr.get("bottom_line") or {}
    lines.append("")
    lines.append(f"{h} 10. Bottom Line")
    lines.append(
        f"{bl.get('good', '')} {bl.get('must_change', '')} {bl.get('if_fixed', '')}".strip()
    )
    return lines


def _v3_markdown_trailer(
    lines: List[str],
    report: Dict[str, Any],
    spine: Dict[str, Any],
    *,
    om: str,
    diagnostic_ids: set[str],
    dual_section_heading: str = "## 11. Dual lens (parallel read + weights)",
    signoff_heading: str = "",
) -> None:
    """Dual lens, producer sign-off, appendix, reference shelf, engagement triads, footer (mutates `lines`)."""
    dl = report.get("dual_lens")
    if isinstance(dl, dict) and dl.get("episode_lens_type"):
        w = dl.get("weights") or {}
        lines.extend(
            [
                "",
                dual_section_heading,
                f"**Episode lens:** {dl.get('episode_lens_type')} "
                f"(heuristic confidence {dl.get('confidence', '—')}) · "
                f"**Weights:** narrative {w.get('narrative')} / analytical {w.get('analytical')}",
            ]
        )
        syn = dl.get("synthesis") if isinstance(dl.get("synthesis"), dict) else {}
        cp = str(syn.get("core_positioning") or "").strip()
        if cp:
            lines.extend(["", "### Core positioning (weighted)", cp])
        cn = syn.get("collision_notes") or []
        if cn:
            lines.extend(["", "### Synthesis (collisions)"])
            for c in cn:
                lines.append(f"- {c}")
        eb = syn.get("execution_bias") if isinstance(syn.get("execution_bias"), dict) else {}
        if eb:
            lines.extend(["", "### Execution bias"])
            lines.append(f"- **Clips:** {eb.get('clips', '')}")
            lines.append(f"- **Actions:** {eb.get('actions', '')}")
        inj = str(dl.get("prompt_injection") or "").strip()
        if inj:
            lines.extend(["", "### Prompt injection (downstream LLM)", "```text", inj, "```"])

    lines.extend(
        _format_producer_sign_off_section(
            report, spine, output_mode=om, signoff_heading=signoff_heading
        )
    )

    lines.extend(
        [
            "",
            "---",
            "## Appendix - Evidence & engagement (structured)",
        ]
    )
    for row in report.get("evidence_mapping") or []:
        if not isinstance(row, dict):
            continue
        if om == "diagnostic" and diagnostic_ids:
            rid = str(row.get("id") or "").strip()
            if rid and rid not in diagnostic_ids:
                continue
        ts = row.get("timestamp")
        ts_s = f"{float(ts):.1f}s" if ts is not None else "n/a"
        vn = str(row.get("verification_note") or "").strip()
        row_line = (
            f"- **[{row.get('id')}]** {ts_s} | {row.get('type')} | **Claim:** {row.get('claim')} "
            f"| **Evidence:** {row.get('evidence')}"
        )
        if vn:
            row_line += f" | **Producer verify:** {vn}"
        lines.append(row_line)
    if not report.get("evidence_mapping"):
        lines.append(
            "- *(No evidence rows; low-signal or offline brief - coach sections above still apply.)*"
        )

    try:
        from .episode_reference_shelf import (
            collect_reference_shelf,
            format_named_strings_markdown,
            format_reference_shelf_markdown,
            proper_nouns_from_claims,
        )
    except ImportError:
        from episode_reference_shelf import (  # type: ignore
            collect_reference_shelf,
            format_named_strings_markdown,
            format_reference_shelf_markdown,
            proper_nouns_from_claims,
        )
    shelf = report.get("reference_shelf")
    if not isinstance(shelf, list):
        shelf = collect_reference_shelf(report)
    lines.extend(format_reference_shelf_markdown(shelf))
    lines.extend(format_named_strings_markdown(proper_nouns_from_claims(report)))

    lines.extend(
        [
            "",
            "**Per-claim pressure tests (detail — optional)**",
        ]
    )
    eq_keys = sorted(
        (report.get("engagement_questions") or {}).keys(),
        key=lambda x: int(x[1:]) if str(x)[1:].isdigit() else 0,
    )
    if om == "diagnostic" and diagnostic_ids:
        eq_keys = [k for k in eq_keys if str(k).strip() in diagnostic_ids]
    for cid in eq_keys:
        tri = report["engagement_questions"][cid]
        lines.append(f"### [{cid}]")
        lines.append(f"- **Counterpunch:** {tri.get('counterpunch')}")
        lines.append(f"- **Validation:** {tri.get('validation')}")
        lines.append(f"- **Application:** {tri.get('application')}")

    lines.extend(["", "---", f"*SoapBoxx Episode Intelligence - workflow v{REPORT_V3_VERSION}*"])


def _render_episode_report_v3_markdown_freebie(
    report: Dict[str, Any],
    *,
    workflow_report: Optional[Dict[str, Any]] = None,
) -> str:
    """Teaser/preview order: questions + guests + snapshot + spine; coaching; heavy gates in Deeper; appendix last."""
    meta = report.get("meta") or {}
    snap = report.get("episode_snapshot") or {}
    title = meta.get("title") or snap.get("title", "")
    creator = meta.get("creator") or snap.get("creator", "")
    genre = snap.get("genre") or meta.get("genre") or ""
    gen = meta.get("generated_at") or _utc_now_iso()
    sm = (report.get("signal_mode") or "") or (
        (report.get("coach_report") or {}).get("signal_mode") or "LOW_SIGNAL"
    )
    cr = report.get("coach_report") or {}

    rr = report.get("report_readiness") or {}
    rnotes = [str(x).strip() for x in (rr.get("notes") or []) if str(x).strip()]
    ract = [str(x).strip() for x in (rr.get("suggested_actions") or []) if str(x).strip()]
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}

    om_coach = str(rr.get("output_mode") or "").strip().lower()
    sig_label = _episode_signal_badge(rr if isinstance(rr, dict) else {}, report)
    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
        _export_header_tagline_for_framing(),
        "",
        f"**Title:** {title}",
        f"**Show / creator:** {creator or '—'}",
        f"**Genre:** {genre or '—'}",
        f"**Generated:** {gen}",
        f"**Classifier signal:** {sm} · **Readiness:** {sig_label}",
        _signal_badge_caption(sig_label, om_coach),
    ]
    lines.extend(_v3_what_this_is_block_lines())
    lines.extend(
        [
            "## 1. Smarter follow-up questions",
            "",
        ]
    )
    if cr and (cr.get("follow_up_questions") or []):
        for q in cr.get("follow_up_questions") or []:
            lines.append(f"- {q}")
        lines.append(
            "*Transcript-grounded. In a live product, this layer is meant to update as you record.*"
        )
    else:
        lines.append(
            "- *(No follow-up list in this run — run the full pipeline with coach enabled.)*"
        )
    lines.append("")
    lines.extend(["## 2. Guest strategy", ""])
    if cr and isinstance(cr.get("guest_strategy"), dict):
        gs = cr.get("guest_strategy") or {}
        intro_g = str(gs.get("intro", "") or "").strip()
        if intro_g:
            lines.append(intro_g)
        for g in gs.get("guests") or []:
            if isinstance(g, dict):
                lines.append(
                    f"- **{g.get('guest_type', 'Guest')}** - {g.get('adds', '')}"
                )
    else:
        lines.append(
            "- *(No guest lines in this run — run the full pipeline with coach enabled.)*"
        )
    lines.append("")
    lines.append("## 3. Quick snapshot")
    lines.append("")
    lines.append(f"**Readiness label:** {sig_label}")
    om = str(rr.get("output_mode") or "").strip().lower()
    lines.extend(
        _v3_readiness_substance_lines(
            rr if isinstance(rr, dict) else {},
            sm=sm,
            rnotes=rnotes,
            ract=ract,
            metrics=metrics,
            om=om,
            max_notes=2,
            include_suggested_actions=False,
        )
    )
    lines.append(
        ""
        "*Full readiness notes, producer workflow orientation, and argument-rigor scoreboard: "
        'see "Deeper" (section 12) below.*'
    )
    lines.append("")

    spine = build_episode_spine(report, workflow_report)
    diagnostic_ids: set[str] = set()
    if om == "diagnostic":
        spine = _compact_spine_for_diagnostic(spine, report)
        diagnostic_ids = {
            str(c.get("id") or "").strip()
            for c in (spine.get("claims") or [])
            if isinstance(c, dict) and str(c.get("id") or "").strip()
        }
    _fb_spine_coda = (
        "*Coaching detail follows in section 5. The full product is aimed at **live Q&A**, **booking and research**, "
        "and (over time) **show/category analytics** — this export is a light preview, not a full sign-off pack.*"
    )
    lines.extend(
        format_episode_spine_markdown_lines(
            spine, first_heading="## 4. The spine", footer=_fb_spine_coda
        )
    )
    lines.append("")
    lines.append("## 5. Episode coaching (detail)")
    lines.append(
        "Subsections use the same numbering as the full export, minus follow-up questions and guest strategy — "
        "those are covered up front in sections 1–2."
    )
    lines.append("")
    lines.extend(
        _v3_coach_report_core_markdown_lines(
            cr, om=om, skip_followup_and_guest=True, hash_prefix="###"
        )
    )
    lines.extend(
        [
            "",
            "## 12. Deeper: Readiness, workflow & quality checks",
            "",
            "### Readiness (full detail)",
            "",
        ]
    )
    if isinstance(rr, dict):
        lines.extend(
            _v3_readiness_substance_lines(
                rr,
                sm=sm,
                rnotes=rnotes,
                ract=ract,
                metrics=metrics,
                om=om,
                max_notes=None,
                include_suggested_actions=True,
            )
        )
    lines.extend(_sensitive_content_readiness_lines(report))
    lines.extend(
        _v3_producer_workflow_markdown_lines(
            section_heading="### Producer workflow (how to read this export)"
        )
    )
    lines.extend(
        _format_argument_rigor_lines(
            report, section_heading="### Argument rigor (constraint gate)"
        )
    )
    _v3_markdown_trailer(
        lines,
        report,
        spine,
        om=om,
        diagnostic_ids=diagnostic_ids,
        dual_section_heading="## 13. Dual lens (parallel read + weights)",
        signoff_heading="## 14. Producer sign-off (pre-publish)",
    )
    raw = "\n".join(lines)
    _strict_episode_report_h1_pre_check(
        raw, where="_render_episode_report_v3_markdown_freebie"
    )
    return ensure_single_episode_report_markdown(raw)


def render_episode_report_v3_markdown(
    report: Dict[str, Any],
    *,
    workflow_report: Optional[Dict[str, Any]] = None,
) -> str:
    """SoapBoxx Episode Report — coach layout (10 sections); uses `coach_report` when present."""
    if _v3_export_framing() == "freebie":
        return _render_episode_report_v3_markdown_freebie(
            report, workflow_report=workflow_report
        )
    meta = report.get("meta") or {}
    snap = report.get("episode_snapshot") or {}
    title = meta.get("title") or snap.get("title", "")
    creator = meta.get("creator") or snap.get("creator", "")
    genre = snap.get("genre") or meta.get("genre") or ""
    gen = meta.get("generated_at") or _utc_now_iso()
    sm = (report.get("signal_mode") or "") or (
        (report.get("coach_report") or {}).get("signal_mode") or "LOW_SIGNAL"
    )
    cr = report.get("coach_report") or {}

    rr = report.get("report_readiness") or {}
    band = str(rr.get("band") or "").strip()
    rnotes = [str(x).strip() for x in (rr.get("notes") or []) if str(x).strip()]
    ract = [str(x).strip() for x in (rr.get("suggested_actions") or []) if str(x).strip()]
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}

    om_coach = str(rr.get("output_mode") or "").strip().lower()
    sig_label = _episode_signal_badge(rr if isinstance(rr, dict) else {}, report)
    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
        _export_header_tagline_for_framing(),
        "",
        f"**Title:** {title}",
        f"**Show / creator:** {creator or '—'}",
        f"**Genre:** {genre or '—'}",
        f"**Generated:** {gen}",
        f"**Classifier signal:** {sm} · **Readiness:** {sig_label}",
        _signal_badge_caption(sig_label, om_coach),
        "",
        "## 0. Readiness & expectations",
    ]
    if band:
        lines.append(f"**Band:** {band}")
    om = str(rr.get("output_mode") or "").strip().lower()
    if om:
        lines.append(f"**Output mode:** {om}")
    if om == "diagnostic" and rr.get("diagnostic_reasons"):
        lines.append("**Why diagnostic:**")
        for dr in rr.get("diagnostic_reasons") or []:
            lines.append(f"- {dr}")
    if metrics:
        wc = metrics.get("transcript_word_count")
        cc = metrics.get("claim_count")
        er = metrics.get("evidence_row_count")
        lines.append(
            f"*Words: {wc} · Claims: {cc} · Evidence rows: {er} · Signal: {metrics.get('signal_mode', sm)}*"
        )
    if rnotes:
        lines.append("")
        lines.append("**What this means:**")
        for n in rnotes:
            lines.append(f"- {n}")
    if ract:
        lines.append("")
        lines.append("**Suggested next steps:**")
        for a in ract:
            lines.append(f"- {a}")
    lines.extend(_sensitive_content_readiness_lines(report))
    lines.extend(_producer_workflow_orientation_lines())
    lines.extend(_format_argument_rigor_lines(report))
    spine = build_episode_spine(report, workflow_report)
    diagnostic_ids: set[str] = set()
    if om == "diagnostic":
        spine = _compact_spine_for_diagnostic(spine, report)
        diagnostic_ids = {
            str(c.get("id") or "").strip()
            for c in (spine.get("claims") or [])
            if isinstance(c, dict) and str(c.get("id") or "").strip()
        }
    lines.extend(
        [
            "",
            *format_episode_spine_markdown_lines(spine),
            "",
        ]
    )
    lines.extend(_v3_coach_report_core_markdown_lines(cr, om=om, skip_followup_and_guest=False))

    _v3_markdown_trailer(
        lines, report, spine, om=om, diagnostic_ids=diagnostic_ids
    )
    raw = "\n".join(lines)
    _strict_episode_report_h1_pre_check(raw, where="render_episode_report_v3_markdown")
    return ensure_single_episode_report_markdown(raw)


def _normalized_evidence_claim_key(claim: str) -> str:
    """Stable key for deduping near-duplicate claim lines across evidence rows."""
    return re.sub(r"[^a-z0-9]+", " ", (claim or "").lower()).strip()[:140]


def _dedupe_adjacent_comma_clauses(text: str) -> str:
    """Drop consecutive duplicate comma-separated clauses (common ASR/LLM stutter in evidence lines)."""
    t = (text or "").strip()
    if "," not in t or len(t) < 20:
        return t
    parts = [re.sub(r"\s+", " ", p.strip()) for p in t.split(",")]
    out: List[str] = []
    prev_key: Optional[str] = None
    for p in parts:
        if not p:
            continue
        key = p.lower()
        if prev_key == key:
            continue
        out.append(p)
        prev_key = key
    return ", ".join(out).strip()


def _dedupe_repeated_sentences(text: str, *, max_words: int = 220) -> str:
    """
    Collapse stuttered ASR/LLM repeats (same sentence back-to-back) and trim length.
    """
    t = (text or "").strip()
    if not t:
        return t
    t = re.sub(r"\s*\[cut\]\s*$", "", t, flags=re.I).strip()
    t = _dedupe_adjacent_comma_clauses(t)
    parts = re.split(r"(?<=[.!?])\s+", t)
    out: List[str] = []
    prev: Optional[str] = None
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if prev is not None and p == prev:
            continue
        out.append(p)
        prev = p
    joined = " ".join(out).strip()
    words = joined.split()
    if len(words) > max_words:
        joined = _truncate_words(joined, max_words=max_words)
    return joined


def _export_header_tagline() -> str:
    """Single line: version + where to read more (compact)."""
    return (
        f"*SoapBoxx Episode Intelligence · Episode Report v{REPORT_V3_VERSION} · "
        f"Spec: `docs/network_episode_brief_v3.md`*"
    )


def _signal_badge_caption(badge: str, output_mode: str) -> str:
    """One line explaining what the badge means for the reader."""
    om = (output_mode or "").strip().lower()
    b = (badge or "").strip().lower()
    if om == "diagnostic":
        return "*This run is **review-first**: verify claims and arc before clips or growth packaging.*"
    if b == "strong":
        return (
            "*Signal: **strong** — enough structure to run the host/edit pass (§0b), then clips and verification.*"
        )
    if b == "moderate":
        return "*Signal: **moderate** — solid direction; tighten claims and evidence where noted.*"
    return "*Signal: **low** — exploratory or thin extraction; use as an edit checklist, not a finished package.*"


def _episode_signal_badge(report_readiness: Dict[str, Any], r3: Dict[str, Any]) -> str:
    """Human-readable signal label for the export header (strong / moderate / low)."""
    rr = report_readiness or {}
    band = str(rr.get("band") or "").strip().lower()
    sm = str((r3 or {}).get("signal_mode") or "").strip().upper()
    if band == "strong":
        return "strong"
    if band == "moderate":
        return "moderate"
    if band in ("weak", "minimal"):
        return "low"
    if sm == "LOW_SIGNAL":
        return "low"
    if sm == "HIGH_SIGNAL":
        return "moderate"
    return "moderate"


def _format_master_blueprint_v1_section(bundle: Dict[str, Any]) -> List[str]:
    """Markdown block when ``bundle`` includes ``blueprint_v1`` from Master Blueprint v1."""
    bp = bundle.get("blueprint_v1")
    if not isinstance(bp, dict):
        return []
    sr = bp.get("strategist_report") if isinstance(bp.get("strategist_report"), dict) else None
    if sr:
        snap = sr.get("snapshot") if isinstance(sr.get("snapshot"), dict) else {}
        core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
        up = sr.get("upgrade_plan") if isinstance(sr.get("upgrade_plan"), dict) else {}
        sf = up.get("structure_fix") if isinstance(up.get("structure_fix"), dict) else {}
        aud = (
            sr.get("audience_engagement_intelligence")
            if isinstance(sr.get("audience_engagement_intelligence"), dict)
            else {}
        )
        sv = (
            sr.get("strategic_value_for_network")
            if isinstance(sr.get("strategic_value_for_network"), dict)
            else {}
        )
        lines: List[str] = [
            "## Podcast performance & growth intelligence",
            "",
            f"**Positioning:** {str(bp.get('product_positioning') or 'A podcast performance and growth intelligence layer').strip()}",
            "",
        ]
        punchline = str(sr.get("punchline_header") or "").strip()
        if not punchline:
            punchline = "This episode underperforms due to weak positioning and lack of clear takeaway, but can be significantly improved with stronger framing, sharper questions, and more structured delivery."
        lines.append("**Podcast Performance Insight**")
        lines.append(f"> {punchline}")
        lines.append("")
        score = snap.get("overall_score")
        signal = str(snap.get("signal_strength") or "").strip()
        diagnosis = str(snap.get("diagnosis") or "").strip()
        scoring_basis = str(snap.get("scoring_basis") or "").strip()
        if score or signal or diagnosis:
            lines.append("**Snapshot**")
            lines.append(f"- Overall score: {score if score not in (None, '') else '—'} / 10")
            if signal:
                lines.append(f"- Signal strength: {signal}")
            if diagnosis:
                lines.append(f"- Diagnosis: {diagnosis}")
            if scoring_basis:
                lines.append(f"- Scoring basis: {scoring_basis}")
            lines.append("")
        thesis = str(core.get("thesis") or "").strip()
        if thesis:
            lines.append(f"**Thesis:** {thesis}")
            lines.append("")
        key_claims = [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()]
        evidence_anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
        tension_position = core.get("tension_position") if isinstance(core.get("tension_position"), dict) else {}
        if key_claims:
            lines.append("**Key claims**")
            for c in key_claims[:3]:
                lines.append(f"- {c}")
            lines.append("")
        if evidence_anchors:
            lines.append("**Evidence anchors**")
            for row in evidence_anchors[:3]:
                cl = str(row.get("claim") or "").strip()
                an = str(row.get("anchor") or "").strip()
                if cl and an:
                    lines.append(f"- {cl} -> {an}")
            lines.append("")
        implicit_argument = str(tension_position.get("implicit_argument") or "").strip()
        stronger_position = str(tension_position.get("stronger_position") or "").strip()
        if implicit_argument or stronger_position:
            lines.append("**Tension call**")
            if implicit_argument:
                lines.append(f"- {implicit_argument}")
            if stronger_position:
                lines.append(f"- {stronger_position}")
            lines.append("")
        working = [str(x).strip() for x in (sr.get("what_working") or []) if str(x).strip()]
        missing = [str(x).strip() for x in (sr.get("what_missing") or []) if str(x).strip()]
        if working:
            lines.append("**What's working**")
            for w in working[:5]:
                lines.append(f"- {w}")
            lines.append("")
        if missing:
            lines.append("**What's missing / weak**")
            for m in missing[:5]:
                lines.append(f"- {m}")
            lines.append("")
        repo = str(up.get("reposition_episode") or "").strip()
        if repo:
            lines.append(f"**Repositioning:** {repo}")
        if sf:
            lines.append("**Structure fix**")
            for k, label in (
                ("opening_hook", "Opening hook"),
                ("midpoint_tension", "Midpoint tension"),
                ("closing_takeaway", "Closing takeaway"),
            ):
                v = str(sf.get(k) or "").strip()
                if v:
                    lines.append(f"- {label}: {v}")
        clips = [str(x).strip() for x in (up.get("clip_opportunities") or []) if str(x).strip()]
        if clips:
            lines.append("**Clip opportunities**")
            for c in clips[:4]:
                lines.append(f"- {c}")
        if repo or sf or clips:
            lines.append("")
        if aud:
            lines.append("**Audience & engagement intelligence**")
            for k, label in (
                ("listener_takeaway_gap", "Listener takeaway gap"),
                ("behavior_change", "Behavior change"),
                ("weekly_improvement_insight", "Weekly improvement insight"),
            ):
                v = str(aud.get(k) or "").strip()
                if v:
                    lines.append(f"- {label}: {v}")
            lines.append("")
        qs = [str(x).strip() for x in (sr.get("question_upgrade") or []) if str(x).strip()]
        if qs:
            lines.append("**Question upgrade**")
            for q in qs[:3]:
                lines.append(f"- {q}")
            lines.append("")
        guests = [g for g in (sr.get("guest_content_opportunities") or []) if isinstance(g, dict)]
        if guests:
            lines.append("**Guest & content opportunities**")
            for g in guests[:4]:
                who = str(g.get("who_type") or "").strip()
                why = str(g.get("why_they_matter") or "").strip()
                unlock = str(g.get("what_they_unlock") or "").strip()
                if who:
                    tail = " ".join([x for x in (why, unlock) if x]).strip()
                    lines.append(f"- **{who}:** {tail}".rstrip())
            lines.append("")
        if sv:
            lines.append("**Strategic value (network)**")
            wu = str(sv.get("what_improving_unlocks") or "").strip()
            upf = str(sv.get("where_it_underperforms") or "").strip()
            if wu:
                lines.append(f"- What improving unlocks: {wu}")
            if upf:
                lines.append(f"- Where it underperforms: {upf}")
            lines.append("")
        nli = [str(x).strip() for x in (sr.get("network_level_insight") or []) if str(x).strip()]
        if nli:
            lines.append("**Network-level insight**")
            for x in nli[:4]:
                lines.append(f"- {x}")
            lines.append("")
        rollout = str(sr.get("network_rollout_line") or "").strip()
        if rollout:
            lines.append(f"> {rollout}")
            lines.append("")
        one_line_fix = str(sr.get("one_line_fix") or "").strip()
        if not one_line_fix:
            one_line_fix = "If this episode were reframed around a clear argument and structured for tension, it would become significantly more engaging and shareable."
        conviction = str(sr.get("conviction_statement") or "").strip()
        if conviction:
            lines.append(f"**Conviction:** {conviction}")
            lines.append("")
        lines.append(f"**1-Line Fix:** {one_line_fix}")
        return lines
    th = str(bp.get("thesis") or "").strip()
    if not th:
        return []
    lines: List[str] = [
        "## Master blueprint (v1)",
        "",
    ]
    cl = bp.get("classification") or {}
    if isinstance(cl, dict) and (cl.get("type") or str(cl.get("reasoning") or "").strip()):
        ct = str(cl.get("type") or "—")
        cf = cl.get("confidence")
        rs = str(cl.get("reasoning") or "").strip()
        tail = f" — {rs}" if rs else ""
        lines.append(f"**Classification:** {ct} (confidence {cf}){tail}".rstrip())
        lines.append("")
    lines.append(f"**Thesis:** {th}")
    lines.append("")
    syn = bp.get("synthesis") or {}
    if isinstance(syn, dict) and any(str(syn.get(k) or "").strip() for k in syn):
        lines.append("**Synthesis**")
        labels = (
            ("key_insight", "Key insight"),
            ("friction_point", "Friction"),
            ("strength", "Gets right"),
            ("gap", "Gap"),
        )
        for key, lab in labels:
            v = str(syn.get(key) or "").strip()
            if v:
                lines.append(f"- **{lab}:** {v}")
        lines.append("")
    clips = bp.get("clips") or []
    if isinstance(clips, list) and clips:
        lines.append("**Clip candidates**")
        for c in clips[:5]:
            if not isinstance(c, dict):
                continue
            txt = str(c.get("text") or "").strip()
            if not txt:
                continue
            reason = str(c.get("reason") or "").strip()
            lines.append(f"- {txt}" + (f" — *{reason}*" if reason else ""))
        lines.append("")
    acts = bp.get("actions") or []
    if isinstance(acts, list) and acts:
        lines.append("**Suggested actions**")
        for a in acts:
            s = str(a).strip()
            if s:
                lines.append(f"- {s}")
    return lines


def _strategist_punchline_from_signal(
    snap: Dict[str, Any],
    key_claims: List[str],
    weaknesses: List[str],
) -> str:
    """One-line performance read: avoid repeating Snapshot **Diagnosis** (always ``weaknesses[0]``) verbatim."""
    title = str(snap.get("title") or "").strip()
    head = title[:100] + ("…" if len(title) > 100 else "") if title else "This episode"
    w0 = str(weaknesses[0]).strip() if weaknesses else ""
    w1 = str(weaknesses[1]).strip() if len(weaknesses) > 1 else ""
    w2 = str(weaknesses[2]).strip() if len(weaknesses) > 2 else ""
    k0 = str(key_claims[0]).strip() if key_claims else ""
    tail_src = ""
    if w1 and (not w0 or text_similarity(w0, w1) < 0.92):
        tail_src = w1
    elif w2 and w0 and text_similarity(w0, w2) < 0.92:
        tail_src = w2
    elif k0:
        tail_src = k0
    elif w0:
        tail_src = w0
    if tail_src:
        tail = tail_src[:220] + ("…" if len(tail_src) > 220 else "")
        return f"{head} — {tail}"
    return f"{head} — tighten to one defended claim, one proof, and one listener action."


def _strategist_network_lines_from_insights(
    highlights: List[str],
    weaknesses: List[str],
    thesis: str,
) -> List[str]:
    """Network bullets from workflow highlights first, then coach weaknesses, then thesis anchor."""
    out: List[str] = []
    for h in highlights:
        hs = str(h).strip()
        if not hs or is_low_signal_insight_line(hs) or _is_meta_topic_line(hs):
            continue
        out.append(hs[:220] + ("…" if len(hs) > 220 else ""))
        if len(out) >= 3:
            break
    for w in weaknesses:
        if len(out) >= 4:
            break
        ws = str(w).strip()
        if ws and ws not in out:
            out.append(ws[:200] + ("…" if len(ws) > 200 else ""))
    th = (thesis or "").strip()
    if len(out) < 2 and th:
        out.append(f"Through-line to stress-test on mic: {th[:200]}{'…' if len(th) > 200 else ''}")
    while len(out) < 2:
        out.append("Name the one claim a skeptical listener should repeat tomorrow.")
    return out[:4]


def _strategist_thesis_is_meta_spine_prompt(thesis: str) -> bool:
    """Coach/meta thesis that tells the host to name a spine — not itself the on-mic claim under test."""
    t = (thesis or "").strip().lower()
    if len(t) < 28:
        return False
    if "falsifiable" in t and ("packaging" in t or "episode title" in t or "title is" in t):
        return True
    if "name one falsifiable" in t:
        return True
    return False


def _strategist_tension_from_claims(thesis: str, key_claims: List[str]) -> Dict[str, str]:
    """Avoid duplicating thesis as both implicit and stronger position."""
    c0 = str(key_claims[0]).strip() if key_claims else ""
    th = str(thesis or "").strip()
    if th and _strategist_thesis_is_meta_spine_prompt(th):
        if not c0 or _strategist_mic_line_is_praise_or_meta(c0):
            return {
                "implicit_argument": (
                    "What the tape spends airtime on before the spine is explicit: rapport beats, tangents, "
                    "and asides that are not yet treated as the episode's single proof obligation."
                ),
                "stronger_position": f"Editorial north star: {th[:280]}{'…' if len(th) > 280 else ''}",
            }
    if c0 and th:
        a, b = c0[:220], th[:220]
        same = a.lower() == b.lower() or (
            len(a) > 24 and len(b) > 24 and a[:40].lower() == b[:40].lower()
        )
        if same:
            return {
                "implicit_argument": f"What the mic keeps circling: {c0[:280]}{'…' if len(c0) > 280 else ''}",
                "stronger_position": "Name the strongest counter-case and one proof that would flip you.",
            }
        return {
            "implicit_argument": f"What the episode leans on listeners to accept: {c0[:280]}{'…' if len(c0) > 280 else ''}",
            "stronger_position": f"The thesis line to keep honest: {th[:280]}{'…' if len(th) > 280 else ''}",
        }
    if th:
        return {
            "implicit_argument": th,
            "stronger_position": "Pressure-test that claim with the best available counterexample.",
        }
    return {
        "implicit_argument": "State one crisp claim the tape is trying to settle.",
        "stronger_position": "Pressure-test that claim with the best available counterexample.",
    }


_NETWORK_INSIGHT_CANNED_ORDER = (
    "weak positioning across shows",
    "lack of shareable moments",
    "structural engagement issues",
    "high-upside opportunities",
)


def _strategist_network_insight_is_canned(rows: Any) -> bool:
    if not isinstance(rows, list) or len(rows) != 4:
        return False
    got = tuple(str(x).strip().lower() for x in rows)
    return got == _NETWORK_INSIGHT_CANNED_ORDER


def _strategist_punchline_is_canned(s: str) -> bool:
    t = (s or "").strip().lower()
    if not t:
        return True
    return any(
        m in t
        for m in (
            "who gets protected when incentives",
            "strong topic, but the episode keeps shifting claims",
            "underperforms due to weak positioning and lack of clear takeaway",
            "circles the same point without committing",
        )
    )


def _strategist_one_line_fix_is_canned(s: str) -> bool:
    t = (s or "").strip().lower()
    return "if this episode were reframed around a clear argument" in t


def _strategist_conviction_is_canned(s: str) -> bool:
    t = (s or "").strip().lower()
    return (
        "this episode is underperforming because it avoids" in t
        or "avoids the hard argument" in t
        or "underperforms because it avoids taking a hard position" in t
        or "underperforms because it avoids committing to one argument" in t
    )


def _strategist_rollout_is_canned(s: str) -> bool:
    t = (s or "").strip().lower()
    return "if we applied this across your network" in t


def _strategist_anchor_is_synthetic(anchor: str) -> bool:
    """True for legacy fake 'scene' copy; False for honest 'no quote paired' lines."""
    t = (anchor or "").strip().lower()
    if not t or "no verbatim pull quote" in t:
        return False
    return any(
        m in t
        for m in (
            "host revisits the same argument",
            "repeats the same point without",
            "repeats a point without escalating",
            "same point is repeated without",
            "central exchange, the same point",
            "without escalating the argument",
            "without a concrete counterexample",
            "early exchange, the host repeats",
        )
    )


def _strategist_tension_is_blueprint_shell_duplicate(tp: Any) -> bool:
    """Detect 'This episode treats…' / 'But the stronger…' with duplicated bodies."""
    if not isinstance(tp, dict):
        return True
    a = str(tp.get("implicit_argument") or "").strip()
    b = str(tp.get("stronger_position") or "").strip()
    if not a or not b:
        return True
    la, lb = a.lower(), b.lower()
    if "this episode treats this as true:" in la and "but the stronger position is this:" in lb:
        body_a = a.split(":", 1)[-1].strip() if ":" in a else a
        body_b = b.split(":", 1)[-1].strip() if ":" in b else b
        ba, bb = body_a.lower(), body_b.lower()
        if body_a and body_b and (ba == bb or ba in bb or bb in ba):
            return True
    return False


def _strategic_where_underperforms_is_canned(s: str) -> bool:
    t = (s or "").strip().lower()
    return (
        "the current structure leaves growth on the table" in t
        or "argument clarity and tension are not carrying the episode" in t
    )


def _merge_strategist_blueprint_with_derived(
    bp: Dict[str, Any], derived: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Blueprint strategist wins for bespoke LLM copy, but known template / drift strings
    are replaced from bundle-derived fields so exports stay episode-anchored.
    """
    out = dict(bp)
    d_core = dict(derived.get("core_breakdown") or {})
    d_anchors = [x for x in (d_core.get("evidence_anchors") or []) if isinstance(x, dict)]
    d_tp = d_core.get("tension_position") if isinstance(d_core.get("tension_position"), dict) else {}

    if _strategist_punchline_is_canned(str(out.get("punchline_header") or "")):
        out["punchline_header"] = derived.get("punchline_header", out.get("punchline_header"))
    if _strategist_one_line_fix_is_canned(str(out.get("one_line_fix") or "")):
        out["one_line_fix"] = derived.get("one_line_fix", out.get("one_line_fix"))
    if _strategist_conviction_is_canned(str(out.get("conviction_statement") or "")):
        out["conviction_statement"] = derived.get("conviction_statement", out.get("conviction_statement"))
    if _strategist_rollout_is_canned(str(out.get("network_rollout_line") or "")):
        out["network_rollout_line"] = derived.get("network_rollout_line", out.get("network_rollout_line"))
    if _strategist_network_insight_is_canned(out.get("network_level_insight")):
        out["network_level_insight"] = list(derived.get("network_level_insight") or [])

    cb = dict(out.get("core_breakdown") or {})
    thesis_bp = str(cb.get("thesis") or "").strip()
    d_thesis = str(d_core.get("thesis") or "").strip()
    snap_d = derived.get("episode_snapshot") if isinstance(derived.get("episode_snapshot"), dict) else {}
    if "who gets protected when incentives" in thesis_bp.lower():
        cb["thesis"] = str(d_core.get("thesis") or thesis_bp)
    elif thesis_bp and snap_d and _line_is_raw_title_packaging(thesis_bp, snap_d):
        cb["thesis"] = d_thesis or _identity_spine_fallback_sentence(
            snap_d, build_identity_anchor({}, snap_d)
        )
    kc = [str(x).strip() for x in (cb.get("key_claims") or []) if str(x).strip()]
    tp = cb.get("tension_position")
    if _strategist_tension_is_blueprint_shell_duplicate(tp):
        if d_tp.get("implicit_argument") or d_tp.get("stronger_position"):
            cb["tension_position"] = dict(d_tp)

    anchors = [dict(x) for x in (cb.get("evidence_anchors") or []) if isinstance(x, dict)]
    for i, row in enumerate(anchors):
        an = str(row.get("anchor") or "")
        if _strategist_anchor_is_synthetic(an) and i < len(d_anchors):
            row["anchor"] = str(d_anchors[i].get("anchor") or row.get("anchor") or "")
        anchors[i] = row
    cb["evidence_anchors"] = anchors
    out["core_breakdown"] = cb

    diag_bp = str(((out.get("snapshot") or {}) if isinstance(out.get("snapshot"), dict) else {}).get("diagnosis") or "").strip()
    if _strategist_punchline_is_canned(diag_bp) or "weak positioning and lack of clear takeaway" in diag_bp.lower():
        snap = dict(out.get("snapshot") or {})
        snap["diagnosis"] = str((derived.get("snapshot") or {}).get("diagnosis") or snap.get("diagnosis") or "")
        out["snapshot"] = snap
    if _strategist_punchline_is_canned(str(out.get("core_problem") or "")) or (
        "weak positioning and lack of clear takeaway" in str(out.get("core_problem") or "").lower()
    ):
        out["core_problem"] = str(derived.get("core_problem") or out.get("core_problem") or "")

    sv = dict(out.get("strategic_value_for_network") or {})
    if _strategic_where_underperforms_is_canned(str(sv.get("where_it_underperforms") or "")):
        d_sv = dict(derived.get("strategic_value_for_network") or {})
        sv["where_it_underperforms"] = str(
            d_sv.get("where_it_underperforms") or sv.get("where_it_underperforms") or ""
        )
        out["strategic_value_for_network"] = sv

    for fk in ("title", "creator", "genre", "report_mode", "product_positioning"):
        if fk in derived and (not str(out.get(fk) or "").strip()):
            out[fk] = derived[fk]
    return out


def _derive_strategist_core_from_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Episode-grounded strategist dict (no blueprint merge). Caller runs truth gate."""
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    snap = dict(r3.get("episode_snapshot") or {})
    claims = [c for c in (r3.get("claims") or []) if isinstance(c, dict)]
    thesis = str(((r3.get("coach_report") or {}).get("episode_thesis") or snap.get("primary_topic") or "").strip())
    if not thesis:
        thesis = "The episode needs one clear argument with explicit tension and a concrete listener takeaway."
    thesis = _coerce_thesis_off_episode_title(thesis, snap, {})
    if not (thesis or "").strip():
        thesis = "The episode needs one clear argument with explicit tension and a concrete listener takeaway."
    thesis = _normalize_keyword_salad_thesis(thesis, snap)
    if _thesis_line_is_quote_like(thesis):
        thesis = _identity_spine_fallback_sentence(
            snap, "State one falsifiable claim this episode can defend on mic."
        )
    snap_for_spine = dict(snap)
    _sanitize_episode_snapshot(snap_for_spine, [])
    spine_hint = f"{snap_for_spine.get('title') or ''} {snap_for_spine.get('primary_topic') or ''}".strip()

    def _keep_strategist_claim_line(txt: str) -> bool:
        s = str(txt or "").strip()
        if not s or _is_broken_evidence_claim_line(s):
            return False
        if is_low_signal_insight_line(s):
            return False
        if _strategist_mic_line_is_praise_or_meta(s):
            return False
        if spine_hint and _claim_conflicts_spine_hint(s, spine_hint):
            return False
        return True

    def _keep_strategist_highlight_line(txt: str) -> bool:
        s = str(txt or "").strip()
        if not s or is_low_signal_insight_line(s) or _is_meta_topic_line(s):
            return False
        if _strategist_mic_line_is_praise_or_meta(s):
            return False
        if spine_hint and _claim_conflicts_spine_hint(s, spine_hint):
            return False
        if _is_broken_evidence_claim_line(s):
            return False
        return True

    key_claims: List[str] = []
    for c in claims:
        s = str(c.get("text") or "").strip()
        if _keep_strategist_claim_line(s):
            key_claims.append(s)
        if len(key_claims) >= 3:
            break
    if not key_claims:
        for e in wf.get("evidence_map") or []:
            if not isinstance(e, dict):
                continue
            s = str(e.get("claim") or "").strip()
            if _keep_strategist_claim_line(s):
                key_claims.append(s)
            if len(key_claims) >= 3:
                break
    evidence_anchors: List[Dict[str, str]] = []
    for i, cl in enumerate(key_claims[:3]):
        anchor = ""
        if i < len(wf.get("evidence_map") or []):
            row = (wf.get("evidence_map") or [])[i]
            if isinstance(row, dict):
                anchor = str(row.get("evidence") or "").strip()
        if not anchor and i < len(r3.get("evidence_mapping") or []):
            row2 = (r3.get("evidence_mapping") or [])[i]
            if isinstance(row2, dict):
                anchor = str(row2.get("evidence") or "").strip()
        if not anchor:
            anchor = (
                "No verbatim pull quote was paired in workflow evidence for this claim — "
                "add one before sharing."
            )
        else:
            anchor = _clean_claim_text(anchor)
        evidence_anchors.append({"claim": cl, "anchor": anchor})
    highlights = []
    for h in wf.get("highlights") or []:
        if not isinstance(h, dict):
            continue
        s = str(h.get("insight") or "").strip()
        if _keep_strategist_highlight_line(s):
            highlights.append(s)
        if len(highlights) >= 3:
            break
    if len(highlights) < 3:
        for x in (r3.get("clean_insights") or []):
            s = str(x).strip()
            if not s or s in highlights:
                continue
            if _keep_strategist_highlight_line(s):
                highlights.append(s)
            if len(highlights) >= 3:
                break
    highlights = _dedupe_strategist_highlights_vs_claims(highlights, key_claims)[:3]
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    word_count = int(metrics.get("transcript_word_count") or 0)
    claim_count = int(metrics.get("claim_count") or len(key_claims or []))
    evidence_row_count = int(metrics.get("evidence_row_count") or len(evidence_anchors or []))
    mode = "evidence" if (word_count >= 120 and claim_count >= 1 and evidence_row_count >= 1) else "interpretive"
    weaknesses: List[str] = []
    bl = (r3.get("coach_report") or {}).get("bottom_line") or {}
    for k in ("must_change", "if_fixed"):
        v = str(bl.get(k) or "").strip()
        if not v:
            continue
        lv = v.lower()
        if any(
            bad in lv
            for bad in (
                "no claims were extracted",
                "low_signal",
                "diagnostic mode",
                "enable ollama",
                "reality check",
            )
        ):
            continue
        weaknesses.append(v)
        if len(weaknesses) >= 3:
            break
    if mode == "interpretive":
        while len(weaknesses) < 3:
            fill = [
                "The episode resets topics before one claim is defended.",
                "No speaker pressure-tests the central claim once it appears.",
                "The close ends without one explicit listener action.",
            ][len(weaknesses)]
            weaknesses.append(fill)
    else:
        while len(weaknesses) < 3:
            fill = [
                "The strongest claim appears, but no one challenges it with a hard counterexample.",
                "Evidence is present, but the argument does not escalate after the midpoint.",
                "The close does not convert the argument into one concrete listener action.",
            ][len(weaknesses)]
            weaknesses.append(fill)
    clips: List[str] = []
    for e in wf.get("evidence_map") or []:
        if not isinstance(e, dict):
            continue
        s = str(e.get("claim") or "").strip()
        if _keep_strategist_claim_line(s):
            clips.append(s)
        if len(clips) >= 3:
            break
    if len(clips) < 2:
        clips.extend([str(x).strip() for x in key_claims if str(x).strip() and str(x).strip() not in clips][: 2 - len(clips)])
    behavior_change = "Apply one explicit listener behavior change tied to the core argument this week."
    recommendations = [
        "Open with one explicit argument in the first 60 seconds.",
        "Force a midpoint counterargument that challenges the core claim.",
        "Close with one concrete listener action and proof of progress.",
    ]
    punchline_header = _strategist_punchline_from_signal(snap, key_claims, weaknesses)
    tension_position = _strategist_tension_from_claims(thesis, key_claims)
    network_level_insight = _strategist_network_lines_from_insights(highlights, weaknesses, thesis)
    diag_w = str(weaknesses[0]).strip() if weaknesses else ""
    if diag_w:
        network_level_insight = [
            str(x).strip()
            for x in network_level_insight
            if str(x).strip() and text_similarity(str(x).strip(), diag_w) < 0.86
        ]
    for extra in weaknesses[1:] if weaknesses else []:
        if len(network_level_insight) >= 4:
            break
        es = str(extra).strip()
        if not es:
            continue
        if diag_w and text_similarity(es, diag_w) >= 0.86:
            continue
        if any(text_similarity(es, x) >= 0.9 for x in network_level_insight):
            continue
        network_level_insight.append(es[:200] + ("…" if len(es) > 200 else ""))
    if len(network_level_insight) < 2 and (thesis or "").strip():
        th = (thesis or "").strip()
        tline = f"Through-line to stress-test on mic: {th[:200]}{'…' if len(th) > 200 else ''}"
        if all(text_similarity(tline, x) < 0.88 for x in network_level_insight):
            network_level_insight.append(tline)
    network_level_insight = network_level_insight[:4]
    et_short = str(snap.get("title") or snap.get("primary_topic") or "this episode")[:90]
    reposition_episode = (
        f"Re-cut \"{et_short}\" around the **Thesis (fixed)** block: lead with that spine in plain language, "
        "then remove beats that do not test it (tangents can ship as their own episodes)."
    )
    one_line_fix = (
        f"Rebuild the open so listeners hear the spine claim for \"{et_short}\" in 60 seconds, "
        f"then cut beats that do not test it."
    )
    conv_topic = str(snap.get("primary_topic") or snap.get("title") or "the stakes")[:90]
    title_s = str(snap.get("title") or "").strip()
    conv_for_conviction = str(snap.get("primary_topic") or "").strip()
    if (
        not conv_for_conviction
        or (title_s and text_similarity(conv_for_conviction, title_s) >= 0.88)
        or (title_s and conv_topic.strip().lower() == title_s.lower()[: len(conv_topic.strip())])
    ):
        conv_for_conviction = _claim_focus_phrase(thesis, max_words=20, max_chars=160)
    if not conv_for_conviction or conv_for_conviction == "this claim":
        conv_for_conviction = conv_topic
    conviction_statement = (
        f"The episode lands when listeners can repeat one clear sentence about what the episode proves — "
        f"not the title alone: {conv_for_conviction}"
    )
    wu_src = (
        weaknesses[2]
        if len(weaknesses) > 2
        else (weaknesses[1] if len(weaknesses) > 1 else (weaknesses[0] if weaknesses else ""))
    )
    where_under = str(wu_src).strip() if str(wu_src).strip() else (
        "Argument clarity is not yet carrying the episode end-to-end."
    )
    for m in weaknesses[:3]:
        if m and text_similarity(where_under, str(m)) >= 0.92:
            where_under = (
                "Packaging and energy run ahead of proof: a skeptical listener still cannot "
                "repeat the one claim that must survive a hostile edit."
            )
            break
    show_title = str(snap.get("title") or "this show")[:80]
    network_rollout = (
        f"Apply the same spine discipline across \"{show_title}\": one defended claim per episode "
        f"before growth packaging."
    )
    return {
        "punchline_header": punchline_header,
        "core_problem": weaknesses[0],
        "snapshot": {
            # Heuristic defaults when deriving a strategist-shaped view without a real blueprint.
            # Suppressed when strict export emits an insufficient-signal card instead (see
            # ``workflow_export_should_abort_insufficient`` / ``render_insufficient_signal_export_markdown``).
            "overall_score": 6,
            "signal_strength": "Moderate",
            "diagnosis": weaknesses[0],
            "scoring_basis": "8-10 clear thesis + strong clips + actionable takeaway; 5-7 decent story but weak clarity/payoff; 1-4 unclear point and low engagement value",
        },
        "core_breakdown": {
            "thesis": thesis,
            "key_claims": key_claims[:3],
            "evidence_anchors": evidence_anchors[:3],
            "tension_position": tension_position,
        },
        "what_working": highlights[:3],
        "what_missing": weaknesses[:3],
        "upgrade_plan": {
            "reposition_episode": reposition_episode,
            "structure_fix": {
                "opening_hook": "State the argument immediately.",
                "midpoint_tension": "Test the argument against the strongest opposing view.",
                "closing_takeaway": "Commit one specific listener action.",
            },
            "clip_opportunities": clips[:3],
            "recommendations": recommendations,
        },
        "audience_engagement_intelligence": {
            "listener_takeaway_gap": "The listener needs one unmistakable point and one action.",
            "behavior_change": behavior_change,
            "weekly_improvement_insight": "Ship each episode around one argument, one tension beat, and one behavior change.",
        },
        "question_upgrade": _strategist_question_upgrade_from_thesis(thesis),
        "guest_content_opportunities": [
            {"who_type": "Domain practitioner", "why_they_matter": "Grounds claims in execution reality.", "what_they_unlock": "Concrete tradeoffs."},
            {"who_type": "Skeptical expert", "why_they_matter": "Introduces productive tension.", "what_they_unlock": "Shareable conflict."},
            {"who_type": "Research analyst", "why_they_matter": "Separates claims from assumptions.", "what_they_unlock": "Defensible evidence."},
        ],
        "strategic_value_for_network": {
            "what_improving_unlocks": "Higher retention, stronger clip yield, and clearer show positioning.",
            "where_it_underperforms": where_under,
        },
        "network_level_insight": network_level_insight,
        "network_rollout_line": network_rollout,
        "one_line_fix": one_line_fix,
        "conviction_statement": conviction_statement,
        "report_mode": mode,
        "product_positioning": "A podcast performance and growth intelligence layer",
        "title": str(snap.get("title") or ""),
        "creator": str(snap.get("creator") or ""),
        "genre": str(snap.get("genre") or ""),
        "episode_snapshot": snap,
    }


def _derive_strategist_report_from_bundle(bundle: Dict[str, Any]) -> Dict[str, Any]:
    abort, rs = strategist_truth_gate_bundle(bundle)
    if abort:
        raise ValueError(
            "strategist derivation blocked (insufficient signal): " + "; ".join(rs)
        )
    derived = _derive_strategist_core_from_bundle(bundle)
    bp = bundle.get("blueprint_v1")
    if isinstance(bp, dict) and isinstance(bp.get("strategist_report"), dict):
        sr = bp.get("strategist_report") or {}
        if isinstance(sr, dict) and sr:
            return _merge_strategist_blueprint_with_derived(dict(sr), derived)
    return derived


# --- Strict export: no “full report” shell when grounding is missing (network-grade failure card) ---

_EXPORT_PLACEHOLDER_MARKERS = (
    "primary tension (edit to fit)",
    "verify against the excerpt below",
    "pick one argumentative through-line from the tape",
)


def strict_export_enabled() -> bool:
    """When True (default), strategist markdown is withheld if gates fail (see workflow export helpers)."""
    v = (os.getenv("SOAPBOXX_STRICT_EXPORT") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def evidence_row_is_export_grounded(row: Any) -> bool:
    """True if an evidence_map row looks like real claim+quote, not offline scaffold or placeholders."""
    if not isinstance(row, dict):
        return False
    c = str(row.get("claim") or "").strip()
    ev = str(row.get("evidence") or "").strip()
    if len(c) < 12 or len(ev) < 20:
        return False
    low = c.lower()
    for p in _EXPORT_PLACEHOLDER_MARKERS:
        if p in low:
            return False
    if _is_broken_evidence_claim_line(c) or _is_broken_evidence_quote_line(ev):
        return False
    return True


def evidence_mapping_row_is_export_grounded(row: Any) -> bool:
    """Same bar as workflow ``evidence_map`` rows, for ``report_v3.evidence_mapping`` dicts."""
    return evidence_row_is_export_grounded(row)


def bundle_grounded_evidence_counts(
    bundle: Dict[str, Any],
) -> Tuple[int, int, int]:
    """
    Grounded evidence rows: ``(max(workflow, r3), n_workflow, n_report_v3)``.
    Shared by the truth gate and structural tier (compression under uncertainty).
    """
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    n_wf = sum(1 for e in (wf.get("evidence_map") or []) if evidence_row_is_export_grounded(e))
    n_r3 = sum(
        1
        for e in (r3.get("evidence_mapping") or [])
        if evidence_mapping_row_is_export_grounded(e)
    )
    return (max(n_wf, n_r3), n_wf, n_r3)


def export_compression_enabled() -> bool:
    """When True (default), omit optional packaging sections when signal density is borderline."""
    v = (os.getenv("SOAPBOXX_EXPORT_COMPRESSION") or "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def export_structural_tier(bundle: Dict[str, Any]) -> str:
    """
    ``full`` — emit full strategist sections (upgrade, guests, network, etc.).

    ``compressed`` — after core spine (through *What's Missing*), omit inflated packaging sections,
    then add :func:`compressed_action_bullets` (max three imperative lines from existing signal only),
    then optional 1-Line Fix. No fake upgrade/guest/network blocks.

    Tier uses ``report_v3.signal_mode``, transcript word count, and grounded evidence counts.
    """
    if not export_compression_enabled():
        return "full"
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    sm = str(r3.get("signal_mode") or "").upper().strip()
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    try:
        wc = int(metrics.get("transcript_word_count") or 0)
    except (TypeError, ValueError):
        wc = 0
    n_ev, _, _ = bundle_grounded_evidence_counts(bundle)

    if sm == "LOW_SIGNAL":
        return "compressed"
    if n_ev <= 2:
        return "compressed"
    if wc > 0 and wc < 400:
        return "compressed"
    if sm == "MEDIUM_SIGNAL" and (wc < 600 or n_ev < 3):
        return "compressed"
    return "full"


def _clip_action_text(s: str, max_chars: int) -> str:
    t = (s or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1].rstrip() + "…"


def _action_texts_too_similar(a: str, b: str, *, threshold: float = 0.78) -> bool:
    """Block two bullets that restate the same move (e.g. thesis vs near-duplicate claim)."""
    x = (a or "").strip().lower()
    y = (b or "").strip().lower()
    if not x or not y:
        return False
    if x in y or y in x:
        return len(min(x, y, key=len)) >= 24
    return SequenceMatcher(None, x, y).ratio() >= threshold


_COMPRESSED_ACTION_FALLBACK = (
    "No actionable steps could be derived from the available signal. "
    "Record a clearer primary claim and at least one supporting example in the next episode."
)


def _action_coarse_intent_bucket(text: str) -> str:
    """
    Bucket rendered bullet text so near-duplicate *actions* (different wording) collapse.
    """
    low = (text or "").lower()
    if any(
        k in low
        for k in (
            "rebuild the open",
            "thesis in one beat",
            "listener gets this thesis",
        )
    ):
        return "thesis_open"
    if any(
        k in low
        for k in (
            "do not ship clip",
            "cut around the tape",
            "trace to this anchor",
            "clearly carries this claim",
        )
    ):
        return "claim_clip"
    if any(k in low for k in ("pressures this tension", "exchange that pressures")):
        return "tension"
    if "fix this before publish" in low:
        return "must_change"
    # Fallback: normalized stem (avoids splitting synonymous bullets poorly)
    stem = re.sub(r"[^a-z0-9]+", " ", low)[:56].strip()
    return stem or "misc"


def _dedupe_action_bullets_by_intent(bullets: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for b in bullets:
        if not (b or "").strip():
            continue
        bucket = _action_coarse_intent_bucket(b)
        if bucket in seen:
            continue
        seen.add(bucket)
        out.append(b.strip())
    return out[:3]


def compressed_action_bullets(bundle: Dict[str, Any], sr: Dict[str, Any]) -> List[str]:
    """
    Up to **three** imperative lines for compressed exports only.

    Uses **only** strings already present in ``sr`` and ``bundle["report_v3"]``. One bullet per
    *source lane* where possible: thesis → primary claim line → ``must_change`` or tension, with
    similarity checks so lanes do not restate the same move. If nothing can be built, returns a
    single honest **fallback** line (still no LLM inference).

    Near-duplicate bullets are dropped using coarse intent buckets (not just string prefixes).
    """
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    thesis = str(core.get("thesis") or "").strip()
    if not thesis:
        thesis = str((r3.get("coach_report") or {}).get("episode_thesis") or "").strip()
    if not thesis:
        thesis = str((r3.get("episode_snapshot") or {}).get("primary_topic") or "").strip()

    kc = [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()][:2]
    tp = sr.get("tension_position") if isinstance(sr.get("tension_position"), dict) else {}
    ia = str(tp.get("implicit_argument") or "").strip()
    sp = str(tp.get("stronger_position") or "").strip()
    tension_line = sp or ia

    anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
    em = [e for e in (r3.get("evidence_mapping") or []) if isinstance(e, dict)]

    claim_line = ""
    if kc:
        claim_line = kc[0]
    elif em:
        claim_line = str(em[0].get("claim") or "").strip()
    elif anchors:
        claim_line = str(anchors[0].get("claim") or "").strip()

    bl = (r3.get("coach_report") or {}).get("bottom_line") if isinstance(r3.get("coach_report"), dict) else {}
    must_change = str(bl.get("must_change") or "").strip() if isinstance(bl, dict) else ""

    ordered: List[str] = []

    if thesis:
        ordered.append(
            f"Rebuild the open so the listener gets this thesis in one beat: {_clip_action_text(thesis, 180)}"
        )

    if claim_line and not _action_texts_too_similar(claim_line, thesis):
        ordered.append(
            f"Do not ship clip packaging until one cut clearly carries this claim: {_clip_action_text(claim_line, 160)}"
        )

    third: Optional[str] = None
    if must_change and not _action_texts_too_similar(must_change, thesis) and not _action_texts_too_similar(
        must_change, claim_line
    ):
        third = f"Fix this before publish: {_clip_action_text(must_change, 200)}"
    elif tension_line and not _action_texts_too_similar(tension_line, thesis) and not _action_texts_too_similar(
        tension_line, claim_line
    ):
        third = f"Keep or add one exchange that pressures this tension: {_clip_action_text(tension_line, 160)}"

    if third:
        ordered.append(third)

    out = _dedupe_action_bullets_by_intent([x for x in ordered if x])
    if not out:
        return [_COMPRESSED_ACTION_FALLBACK]
    return out[:3]


def strategist_truth_gate_bundle(bundle: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Single epistemic gate for strategist markdown **and** :func:`_derive_strategist_report_from_bundle`.

    When :func:`strict_export_enabled`, a full strategist export (scores, packaging, derived shell)
    is allowed only if:

    - ``workflow_report.metadata.v3_reality_check`` did not record a failure (when present).
    - At least **two** grounded evidence rows across workflow + v3 (``max`` of both layers).
    - At least **one** segment across workflow + v3 (``max`` of both layers).

    Using ``max`` avoids dual-reality: if either layer has real structure, we do not invent a
    contradictory shell from the other empty layer.

    **Blueprint:** ``blueprint_v1.strategist_report`` does **not** bypass this gate. The blueprint
    supplies structure only after the same evidence / segment / reality checks pass — otherwise
    a bad model payload cannot be treated as canonical over thin transcript signal.
    When a blueprint strategist payload is present, :func:`_derive_strategist_report_from_bundle`
    still merges in episode-derived lines for known template / drift fields (see
    :func:`_merge_strategist_blueprint_with_derived`).
    """
    if not strict_export_enabled():
        return False, []
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    md = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    reasons: List[str] = []

    rc = md.get("v3_reality_check")
    if isinstance(rc, dict) and rc.get("passed") is False:
        fails = rc.get("failures") or []
        if isinstance(fails, list) and fails:
            reasons.extend(str(x) for x in fails if str(x).strip())
        else:
            reasons.append("v3 reality check did not pass (no failure strings recorded).")

    n_ev, n_wf, n_r3 = bundle_grounded_evidence_counts(bundle)

    n_seg = max(
        len(wf.get("segments") or []),
        len(r3.get("segments") or []),
    )

    if n_ev < 2:
        reasons.append(
            f"grounded evidence rows {n_ev} < 2 (workflow={n_wf}, report_v3={n_r3})"
        )
    if n_seg < 1:
        reasons.append(f"segments {n_seg} < 1 (workflow and report_v3)")

    return (len(reasons) > 0, reasons)


def workflow_export_should_abort_insufficient(
    workflow_report: Dict[str, Any],
    report_v3: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Deprecated: use :func:`strategist_truth_gate_bundle` with
    ``{"workflow_report": ..., "report_v3": ...}`` (metadata lives under ``workflow_report``).
    """
    wf = dict(workflow_report or {})
    md = metadata or {}
    if md:
        wf["metadata"] = md
    return strategist_truth_gate_bundle({"workflow_report": wf, "report_v3": report_v3 or {}})


def _humanize_export_blocker(raw: str) -> str:
    """Turn internal blocker strings into short, user-facing explanations."""
    s = str(raw).strip()
    if not s:
        return s
    low = s.lower()
    if "grounded evidence rows" in low and "< 2" in s:
        return (
            "Not enough on-tape evidence rows to anchor claims and clips "
            "(need at least two grounded quotes)."
        )
    if "segments" in low and "< 1" in s:
        return "No clear segment or chapter structure detected (need at least one segment)."
    if "ollama transport" in low or "transport exhausted" in low:
        return (
            "Local enrichment transport hit limits; some structure may be missing even when "
            "the tape has more in it."
        )
    if "reality check" in low or ("v3 reality" in low and "fail" in low):
        return "Consistency / reality checks did not pass for this run."
    if "output_mode" in low and "diagnostic" in low:
        return "The pipeline ran in diagnostic mode, which is not shippable as a full brief."
    return s


def _resolve_limited_reason_label(
    bundle: Dict[str, Any],
    blockers: List[str],
    wmeta: Dict[str, Any],
    export_status: str,
    transcript_word_count: int,
    readiness_band: str,
) -> str:
    """Prefer finalized ``limited_reason``; otherwise match :func:`evaluation_pipeline.compute_limited_reason`."""
    lr0 = str(wmeta.get("limited_reason") or "").strip().lower()
    if lr0 in ("content", "input", "system"):
        return lr0
    try:
        from evaluation_pipeline import compute_input_quality_score, compute_limited_reason
    except ImportError:
        return "content"

    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    n_ev, _, _ = bundle_grounded_evidence_counts({"workflow_report": wf, "report_v3": r3})
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    cc = int(metrics.get("claim_count") or 0)
    if cc <= 0:
        cl = r3.get("claims")
        if isinstance(cl, list):
            cc = len([x for x in cl if isinstance(x, dict)])
    iqs = compute_input_quality_score(int(transcript_word_count), cc, int(n_ev))

    eb = wmeta.get("export_blockers")
    if not isinstance(eb, list) or not eb:
        eb = list(blockers or [])
    bbs = wmeta.get("export_blockers_by_source")
    if not isinstance(bbs, dict):
        bbs = {}
    snap = {
        "transcript_word_count": int(transcript_word_count),
        "readiness_band": str(readiness_band or "").strip().lower(),
        "claim_count": cc,
        "canonical_evidence_count": int(n_ev),
    }
    out = compute_limited_reason(
        user_export_mode="limited",
        export_status=str(export_status or ""),
        snapshot=snap,
        export_blockers=[str(x) for x in eb if str(x).strip()],
        blockers_by_source=bbs,
        input_quality_score=iqs,
    )
    return str(out or "content")


def render_limited_signal_export_markdown(
    bundle: Dict[str, Any], blockers: List[str]
) -> str:
    """
    **Limited Signal** user-facing export: directional guidance + confidence, not silence.

    Internal diagnostics stay in ``export_blockers``; this layer interprets them as actionable signal.
    """
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    snap = dict(r3.get("episode_snapshot") or {})
    m = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    title = str(snap.get("title") or "").strip() or str(m.get("title") or "").strip() or "—"
    creator = str(snap.get("creator") or "").strip() or str(m.get("creator") or "").strip()
    genre = str(snap.get("genre") or "").strip()
    primary_topic = str(snap.get("primary_topic") or "").strip()
    cr = r3.get("coach_report") if isinstance(r3.get("coach_report"), dict) else {}
    thesis = str(cr.get("episode_thesis") or "").strip()
    rr = r3.get("report_readiness") if isinstance(r3.get("report_readiness"), dict) else {}
    metrics = rr.get("metrics") if isinstance(rr.get("metrics"), dict) else {}
    word_count = int(metrics.get("transcript_word_count") or 0)
    readiness_band = str(rr.get("band") or "").strip().lower()
    signal_mode = str(metrics.get("signal_mode") or r3.get("signal_mode") or "").strip()

    # Even in limited/degraded exports, keep metadata and thesis lines in the same "clean"
    # format as full exports so QA checks (genre drift, quote-like thesis) remain enforceable.
    try:
        from .episode_intelligence import _refine_genre_from_title  # type: ignore
    except ImportError:
        from episode_intelligence import _refine_genre_from_title  # type: ignore
    genre = _refine_genre_from_title(title, genre)
    thesis_fixed = _normalize_keyword_salad_thesis(
        _coerce_thesis_off_episode_title(thesis, snap, {}), snap
    )
    if not thesis_fixed:
        thesis_fixed = _identity_spine_fallback_sentence(
            snap, "State one falsifiable claim this episode can defend on mic."
        )
    if _thesis_line_is_quote_like(thesis_fixed):
        thesis_fixed = _identity_spine_fallback_sentence(
            snap, "State one falsifiable claim this episode can defend on mic."
        )

    raw_blockers = [str(x).strip() for x in (blockers or []) if str(x).strip()]
    bp = bundle.get("blueprint_v1")
    if isinstance(bp, dict) and isinstance(bp.get("strategist_report"), dict) and bp.get("strategist_report"):
        raw_blockers = list(raw_blockers) + [
            "Master Blueprint strategist output was withheld: it does not bypass "
            "transcript/workflow truth checks.",
        ]
    if not raw_blockers:
        raw_blockers = [
            "Minimum evidence and/or segment bars were not met, or checks did not pass.",
        ]

    human = [_humanize_export_blocker(b) for b in raw_blockers]
    # De-dupe while preserving order
    seen: set = set()
    human_unique: List[str] = []
    for h in human:
        if h and h not in seen:
            seen.add(h)
            human_unique.append(h)

    export_status = str(wmeta.get("export_status") or "").strip().lower()
    limited_reason = _resolve_limited_reason_label(
        bundle, raw_blockers, wmeta, export_status, word_count, readiness_band
    )
    verdict_line = {
        "content": "## Episode verdict: **C — Weak episode (limited read)**",
        "input": "## Episode verdict: **C — Unreadable input (low confidence)**",
        "system": "## Episode verdict: **C — System limited (retry recommended)**",
    }.get(limited_reason, "## Episode verdict: **C — Weak episode (limited read)**")

    whats_going_on: List[str] = [
        "This episode did not provide enough **structured signal** for a full breakdown "
        "(low evidence, weak segmentation, and/or transcript quality limits what can be verified).",
        "",
        "**Translation:** the content lacks a clear analyzable spine on the tape, or the transcript "
        "is too weak to extract it reliably.",
    ]
    if export_status == "degraded":
        whats_going_on = [
            "Enrichment or transport hit limits (for example local model timeouts). "
            "You may still have usable audio—what’s missing is **reliably extracted structure**.",
            "",
            "**Translation:** treat this as a partial read until you re-run with stable enrichment "
            "or a cleaner transcript.",
        ]

    pattern_issues = [
        "**No clear structure** — ideas drift instead of building in stages.",
        "**Low specificity** — abstract talk without concrete claims or scenes.",
        "**Weak segmentation** — few “moments” to anchor clips or chapter-style insights.",
    ]
    # Tie pattern list to humanized blockers when obvious
    if any("evidence" in x.lower() for x in human_unique):
        pattern_issues[0] = pattern_issues[0] + " *(reinforced by thin evidence rows.)*"
    if any("segment" in x.lower() for x in human_unique):
        pattern_issues[2] = pattern_issues[2] + " *(reinforced by missing segments.)*"

    fix_next = [
        "**Force a clear episode thesis early** — “This episode is about X; we’ll show it through Y.”",
        "**Break the conversation into segments** — chapters, not one long ramble.",
        "**Add concrete examples** — stories beat philosophy-only blocks for clips and growth.",
    ]

    growth_lines = [
        "Episodes like this (ambient, philosophical, or passive-listening formats) often:",
        "",
        "- perform well for **passive listening / retention**",
        "- perform poorly for **clips and growth** unless you add stakes and scenes",
        "",
        "**Decide:** is this a **growth episode** or a **retention episode**? Right now it reads "
        "as neither optimized.",
    ]
    g_low = genre.lower()
    if any(x in g_low for x in ("sleep", "ambient", "meditation", "asmr")):
        growth_lines = [
            "This genre often optimizes for **calm or sleep**, not for **clip-friendly tension**.",
            "",
            "**Decide:** if growth matters, add one sharp, concrete beat; if not, own the format and "
            "measure retention instead of clip velocity.",
        ]

    why_limited: List[str] = [
        "Deeper scoring and clip picks would be guesswork without grounded evidence and segments.",
        "",
        "*This remains honest: there are **no synthetic scores** or faux-authoritative packaging here.*",
        "",
        "**Why this is limited** (plain language): the run had **insufficient signal** for a "
        "full network-grade strategist export — same bar as before, better coaching.",
    ]
    detail_bits: List[str] = []
    if word_count:
        detail_bits.append(f"Transcript words (when counted): ~{word_count}")
    if signal_mode:
        detail_bits.append(f"Signal mode: {signal_mode}")
    if primary_topic and "insufficient" not in primary_topic.lower():
        detail_bits.append(f"Primary topic (best effort): {primary_topic}")
    elif thesis:
        detail_bits.append(f"Working thesis (best effort): {thesis}")
    if detail_bits:
        why_limited.insert(0, "")
        why_limited.insert(0, " · ".join(detail_bits))

    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
        verdict_line,
        "",
        f"**Show / episode:** {creator + ' · ' if creator else ''}{title}",
        f"**Genre:** {genre or '—'}",
        f"**Thesis (fixed):** {thesis_fixed}",
        "",
        "### What's going on",
    ]
    lines.extend(whats_going_on)
    lines.extend(
        [
            "",
            "### Likely issues (from pattern + this run)",
            "",
        ]
    )
    for i, p in enumerate(pattern_issues[:3], start=1):
        lines.append(f"{i}. {p}")
    lines.append("")
    lines.append("**From this run specifically:**")
    for h in human_unique[:6]:
        lines.append(f"- {h}")
    lines.extend(
        [
            "",
            "### What to fix next episode",
            "",
        ]
    )
    for f in fix_next:
        lines.append(f"- {f}")
    lines.extend(
        [
            "",
            "### Growth insight",
            "",
        ]
    )
    lines.extend(growth_lines)
    lines.extend(["", "### Why this is limited", ""])
    lines.extend(why_limited)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "*Technical details for support / QA:* "
        + "; ".join(str(x) for x in raw_blockers[:8])
    )
    lines.append("")
    raw = "\n".join(lines).strip() + "\n"
    _strict_episode_report_h1_pre_check(raw, where="render_limited_signal_export_markdown")
    return ensure_single_episode_report_markdown(raw)


def render_insufficient_signal_export_markdown(
    bundle: Dict[str, Any], blockers: List[str]
) -> str:
    """Backward-compatible name for :func:`render_limited_signal_export_markdown`."""
    return render_limited_signal_export_markdown(bundle, blockers)


def _render_strategist_export_markdown(bundle: Dict[str, Any]) -> str:
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    r3b = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    wmeta = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    if wmeta.get("export_status") in ("insufficient_signal", "degraded"):
        blockers = wmeta.get("export_blockers") or []
        if not isinstance(blockers, list):
            blockers = [str(blockers)]
        return render_insufficient_signal_export_markdown(bundle, [str(x) for x in blockers if str(x).strip()])
    # Authoritative path: if a unified evaluator already finalized export_status, do not run
    # a second independent truth gate here.
    if wmeta.get("export_status") == "ok":
        abort = False
        reasons: List[str] = []
    else:
        abort, reasons = strategist_truth_gate_bundle(bundle)
    if abort:
        return render_insufficient_signal_export_markdown(bundle, reasons)

    sr = _derive_strategist_report_from_bundle(bundle)
    sr = _merge_strategist_guest_opportunities(sr, wf)
    bp = bundle.get("blueprint_v1") if isinstance(bundle.get("blueprint_v1"), dict) else {}
    title = str(sr.get("title") or (((bundle.get("report_v3") or {}).get("episode_snapshot") or {}).get("title") or "")).strip()
    creator = str(sr.get("creator") or (((bundle.get("report_v3") or {}).get("episode_snapshot") or {}).get("creator") or "")).strip()
    genre = str(sr.get("genre") or (((bundle.get("report_v3") or {}).get("episode_snapshot") or {}).get("genre") or "")).strip()
    snap = sr.get("snapshot") if isinstance(sr.get("snapshot"), dict) else {}
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    evidence_anchors = [x for x in (core.get("evidence_anchors") or []) if isinstance(x, dict)]
    tension_position = core.get("tension_position") if isinstance(core.get("tension_position"), dict) else {}
    up = sr.get("upgrade_plan") if isinstance(sr.get("upgrade_plan"), dict) else {}
    sf = up.get("structure_fix") if isinstance(up.get("structure_fix"), dict) else {}
    sv = sr.get("strategic_value_for_network") if isinstance(sr.get("strategic_value_for_network"), dict) else {}
    diag_s = str(snap.get("diagnosis") or "").strip()
    core_s = str(sr.get("core_problem") or "").strip()
    lines: List[str] = [
        "# SoapBoxx Episode Report",
        "",
    ]
    try:
        from .episode_progress import format_progress_markdown_lines
    except ImportError:
        from episode_progress import format_progress_markdown_lines

    lines.extend(format_progress_markdown_lines(bundle))
    lines.extend(
        [
        "## Podcast performance & growth intelligence",
        "",
        f"**Title:** {title or '—'}",
        f"**Show / creator:** {creator or '—'}",
        f"**Genre:** {genre or '—'}",
        f"**Positioning:** {str(bp.get('product_positioning') or sr.get('product_positioning') or 'A podcast performance and growth intelligence layer').strip()}",
        "",
        "**How to read this:** **Thesis (fixed)** is the one line the episode should prove. **Claims** are on-mic bets to test against that line. "
        "The **Workflow execution checklist** (after the horizontal rule) is the same story as editor rows—guests are outreach targets, not cast. "
        "Use both layers together when you edit.",
        "",
        "## Podcast Performance Insight",
        f"> {str(sr.get('punchline_header') or '').strip() or 'State the spine claim in minute one, then force one counter before the close.'}",
        "",
        "## Snapshot",
        f"- Score: {snap.get('overall_score', '—')} / 10",
        f"- Signal: {str(snap.get('signal_strength') or '—').strip()}",
        f"- Diagnosis: {diag_s}",
        "",
        "## Core Breakdown",
        f"**Thesis (fixed):** {_polish_outbound_sentence(str(core.get('thesis') or '').strip(), max_words=30)}",
        "",
        "**Claims:**",
        ]
    )
    spine_hint_core = f"{title} {str(core.get('thesis') or '')}".strip()
    if core_s and core_s.lower() != diag_s.lower():
        try:
            ix = lines.index("## Core Breakdown")
            lines.insert(ix, f"- Core problem: {core_s}")
        except ValueError:
            pass
    kept_core_claims: List[str] = []
    for c in [str(x).strip() for x in (core.get("key_claims") or []) if str(x).strip()]:
        if not _appendix_surface_line_keeps(c, spine_hint_core):
            continue
        kept_core_claims.append(c)
        if len(kept_core_claims) >= 3:
            break
    for c in kept_core_claims:
        lines.append(f"- {_polish_outbound_sentence(c, max_words=30)}")
    if evidence_anchors:
        lines.extend(["", "## Evidence Anchors"])
        rows3 = [x for x in evidence_anchors[:3] if isinstance(x, dict)]
        pairs: List[Tuple[str, str]] = []
        for row in rows3:
            cl = str(row.get("claim") or "").strip()
            an = str(row.get("anchor") or "").strip()
            if cl and an:
                pairs.append((cl, an))
        n_red = sum(1 for c, a in pairs if _evidence_anchor_row_is_redundant(c, a))
        if n_red >= 2 and n_red == len(pairs):
            lines.append(
                "- **Gap:** Each top claim still pairs only with the same on-mic sentence — add one "
                "contrasting verbatim pull quote per claim before you ship clips."
            )
            for cl, _ in pairs:
                lines.append(f"  - {cl}")
        else:
            for cl, an in pairs:
                if _evidence_anchor_row_is_redundant(cl, an):
                    lines.append(
                        f"- **Claim:** {_polish_outbound_sentence(cl, max_words=30)} → **Evidence:** *(Same line as the claim on the tape—pair with a "
                        f"contrasting pull quote when you edit.)*"
                    )
                else:
                    lines.append(
                        f"- {_polish_outbound_sentence(cl, max_words=30)} -> {_polish_outbound_sentence(an, max_words=30)}"
                    )
    implicit_argument = str(tension_position.get("implicit_argument") or "").strip()
    stronger_position = str(tension_position.get("stronger_position") or "").strip()
    if implicit_argument or stronger_position:
        lines.extend(["", "## Tension Call"])
        if implicit_argument:
            lines.append(f"- {implicit_argument}")
        if stronger_position and (
            not implicit_argument
            or text_similarity(implicit_argument, stronger_position) < 0.88
        ):
            lines.append(f"- {stronger_position}")
    lines.extend(["", "## What's Working"])
    for w in [str(x).strip() for x in (sr.get("what_working") or []) if str(x).strip()][:3]:
        lines.append(f"- {_polish_outbound_sentence(w, max_words=30)}")
    lines.extend(["", "## What's Missing"])
    for m in [str(x).strip() for x in (sr.get("what_missing") or []) if str(x).strip()][:3]:
        lines.append(f"- {_polish_outbound_sentence(m, max_words=30)}")

    tier = export_structural_tier(bundle)
    if tier == "compressed":
        lines.extend(
            [
                "",
                "*Packaging sections omitted (upgrade plan, guest slots, network framing): transcript length or signal density is below the bar for actionable distribution advice. Do not treat omitted blocks as hidden recommendations.*",
            ]
        )
        guest_lines = _compressed_export_guest_markdown_lines(bundle)
        if guest_lines:
            lines.extend(
                [
                    "",
                    "## Guest angles (from structured workflow)",
                    "",
                    "These rows come from the same **workflow** guest list used in JSON exports "
                    "(episode text + graph angles), not from the omitted packaging block.",
                ]
            )
            lines.extend(guest_lines)
        act = compressed_action_bullets(bundle, sr)
        if act:
            lines.extend(["", "## If You Had to Act Anyway"])
            for b in act:
                lines.append(f"- {b}")
        one_line_fix_c = str(sr.get("one_line_fix") or "").strip()
        if one_line_fix_c:
            lines.extend(["", "## 1-Line Fix", one_line_fix_c])
        raw = "\n".join(lines).strip() + "\n"
        _strict_episode_report_h1_pre_check(raw, where="_render_strategist_export_markdown(compressed)")
        return ensure_single_episode_report_markdown(raw)

    lines.extend(["", "## Upgrade Plan"])
    repo = str(up.get("reposition_episode") or "").strip()
    if repo:
        lines.append(f"**Reposition:** {repo}")
    lines.append("")
    lines.append("**Structure:**")
    for k, label in (("opening_hook", "Hook"), ("midpoint_tension", "Tension"), ("closing_takeaway", "Takeaway")):
        v = str(sf.get(k) or "").strip()
        if v:
            lines.append(f"- {label}: {v}")
    for r in [str(x).strip() for x in (up.get("recommendations") or []) if str(x).strip()][:3]:
        lines.append(f"- Recommendation: {r}")
    lines.append("")
    lines.append("**Clips:**")
    for c in [str(x).strip() for x in (up.get("clip_opportunities") or []) if str(x).strip()][:3]:
        lines.append(f"- {_polish_outbound_sentence(c, max_words=30)}")
    lines.extend(["", "## Questions That Should Have Been Asked"])
    for q in [str(x).strip() for x in (sr.get("question_upgrade") or []) if str(x).strip()][:3]:
        lines.append(f"- {q}")
    lines.extend(["", "## Guest Opportunities"])
    for g in [x for x in (sr.get("guest_content_opportunities") or []) if isinstance(x, dict)][:3]:
        who = str(g.get("who_type") or "").strip()
        why = str(g.get("why_they_matter") or "").strip()
        unlock = str(g.get("what_they_unlock") or "").strip()
        if who:
            lines.append(f"- {who} -> {why} {unlock}".strip())
    lines.extend(["", "## Strategic Value"])
    wu = str(sv.get("what_improving_unlocks") or "").strip()
    upf = str(sv.get("where_it_underperforms") or "").strip()
    missing_b = [str(x).strip() for x in (sr.get("what_missing") or []) if str(x).strip()]
    if upf and any(text_similarity(upf, m) >= 0.86 for m in missing_b):
        upf = ""
    if wu and upf and text_similarity(wu, upf) >= 0.86:
        upf = ""
    if wu:
        lines.append(f"- {wu}")
    if upf:
        lines.append(f"- {upf}")
    lines.extend(["", "## Network Insight"])
    working_b = [str(x).strip() for x in (sr.get("what_working") or []) if str(x).strip()]
    n_net = 0
    for x in [str(x).strip() for x in (sr.get("network_level_insight") or []) if str(x).strip()][:6]:
        if any(text_similarity(x, w) >= 0.88 for w in working_b):
            continue
        if any(text_similarity(x, m) >= 0.82 for m in missing_b):
            continue
        if diag_s and text_similarity(x, diag_s) >= 0.82:
            continue
        lines.append(f"- {x}")
        n_net += 1
        if n_net >= 4:
            break
    rollout = str(sr.get("network_rollout_line") or "").strip()
    if rollout:
        lines.extend(["", f"> {rollout}"])
    one_line_fix = str(sr.get("one_line_fix") or "").strip()
    conviction = str(sr.get("conviction_statement") or "").strip()
    if conviction:
        lines.extend(["", "## Conviction", conviction])
    if one_line_fix:
        lines.extend(["", "## 1-Line Fix", one_line_fix])
    raw = "\n".join(lines).strip() + "\n"
    _strict_episode_report_h1_pre_check(raw, where="_render_strategist_export_markdown(full)")
    return ensure_single_episode_report_markdown(raw)


def render_workflow_execution_appendix_markdown(bundle: Dict[str, Any]) -> str:
    """
    Sections 1–7: highlights, evidence, follow-ups, **booking-oriented** guest table, segments,
    analytics. Uses the same filters as :func:`soapboxx_v3_workflow.workflow_guest_rows` so verbatim
    transcript figures never appear as “Suggested Guest”.
    """
    r3 = bundle.get("report_v3") or {}
    wf = bundle.get("workflow_report") or {}
    snap_ax = dict(r3.get("episode_snapshot") or {})
    spine_hint_ax = f"{snap_ax.get('title') or ''} {snap_ax.get('primary_topic') or ''}".strip()
    lines: List[str] = [
        "## Workflow execution checklist",
        "",
        "*From enriched `workflow_report`: highlights, anchors, follow-ups, guests, segments. "
        "Guest rows are **outreach-oriented**; names that only appear *in* the story are omitted.*",
        "",
    ]

    # --- 1. Key Highlights
    hl_rows: List[str] = []
    for h in (wf.get("highlights") or [])[:8]:
        if isinstance(h, dict):
            ins = str(h.get("insight") or "").strip()
            if (
                ins
                and not _is_meta_topic_line(ins)
                and not _is_narrative_meta_noise(ins)
                and not is_low_signal_insight_line(ins)
                and not _is_garbled_insight_line(ins)
                and _appendix_surface_line_keeps(ins, spine_hint_ax)
            ):
                hl_rows.append(ins)
    if not hl_rows:
        for x in (r3.get("clean_insights") or [])[:8]:
            s = str(x).strip()
            if (
                s
                and not _is_meta_topic_line(s)
                and not _is_narrative_meta_noise(s)
                and not is_low_signal_insight_line(s)
                and not _is_garbled_insight_line(s)
                and _appendix_surface_line_keeps(s, spine_hint_ax)
            ):
                hl_rows.append(s)
    lines.append("## 1. Key Highlights")
    if hl_rows:
        for h in hl_rows:
            lines.append(f"- {_polish_outbound_sentence(h, max_words=30)}")
    else:
        lines.append(
            "- *(No highlights passed quality filters — rerun with a richer transcript or check Ollama / `warnings`.)*"
        )
    lines.append("")

    # --- 2. Key beats & pull quotes
    lines.append("## 2. Key beats & pull quotes")
    em_wf = wf.get("evidence_map") or []
    ev_count = 0
    seen_ev_keys: Set[str] = set()
    if em_wf:
        for e in em_wf[:20]:
            if not isinstance(e, dict):
                continue
            cid = str(e.get("id") or "")
            ts = e.get("timestamp")
            ts_s = f"{float(ts):.1f}s" if ts is not None else "n/a"
            typ = str(e.get("type") or "other")
            cl_raw = str(e.get("claim") or "").strip()
            ev_raw = _dedupe_repeated_sentences(str(e.get("evidence") or "").strip())
            if not _appendix_surface_line_keeps(cl_raw, spine_hint_ax):
                continue
            if not _workflow_claim_line_is_actionable(cl_raw):
                continue
            if _is_broken_evidence_claim_line(cl_raw):
                continue
            if _is_broken_evidence_quote_line(ev_raw):
                continue
            ek = _normalized_evidence_claim_key(cl_raw)
            if ek and ek in seen_ev_keys:
                continue
            if ek:
                seen_ev_keys.add(ek)
            # Display-only trim: strip leading filler ("Yeah,", "Like,", …) and normalize casing so
            # anchors don't surface as mid-sentence fragments. Keeps the original timestamp.
            cl_disp = _polish_outbound_sentence(_trim_anchor_display_text(cl_raw), max_words=30)
            ev_disp = _polish_outbound_sentence(_trim_anchor_display_text(ev_raw), max_words=30)
            label = "Quote" if typ.lower() == "pull_quote" else "Evidence"
            moment = "Moment" if typ.lower() == "pull_quote" else "Claim"
            lines.append(
                f"- **[{cid}]** {ts_s} | {typ} | **{moment}:** {cl_disp} | **{label}:** {ev_disp}"
            )
            ev_count += 1
            if ev_count >= 12:
                break
    else:
        for row in (r3.get("evidence_mapping") or [])[:20]:
            if not isinstance(row, dict):
                continue
            cl_raw = str(row.get("claim") or "").strip()
            if not _appendix_surface_line_keeps(cl_raw, spine_hint_ax):
                continue
            if not _workflow_claim_line_is_actionable(cl_raw):
                continue
            if _is_broken_evidence_claim_line(cl_raw):
                continue
            ev_r_raw = _dedupe_repeated_sentences(str(row.get("evidence") or "").strip())
            if _is_broken_evidence_quote_line(ev_r_raw):
                continue
            ek = _normalized_evidence_claim_key(cl_raw)
            if ek and ek in seen_ev_keys:
                continue
            if ek:
                seen_ev_keys.add(ek)
            ts = row.get("timestamp")
            ts_s = f"{float(ts):.1f}s" if ts is not None else "n/a"
            cl_disp = _polish_outbound_sentence(_trim_anchor_display_text(cl_raw), max_words=30)
            ev_disp = _polish_outbound_sentence(_trim_anchor_display_text(ev_r_raw), max_words=30)
            lines.append(
                f"- **[{row.get('id')}]** {ts_s} | {row.get('type')} | "
                f"**Claim:** {cl_disp} | **Evidence:** {ev_disp}"
            )
            ev_count += 1
            if ev_count >= 12:
                break
    if ev_count == 0:
        lines.append(
            "- *(No evidence rows — see coach report appendix in `markdown_v3`.)*"
        )
    lines.append("")

    # --- 3. Follow-Up Questions
    lines.append("## 3. Follow-Up Questions")
    claim_text_by_id: Dict[str, str] = {}
    for er in (wf.get("evidence_map") or []):
        if not isinstance(er, dict):
            continue
        cid_er = str(er.get("id") or "").strip()
        cl_er = str(er.get("claim") or "").strip()
        if cid_er and cl_er and cid_er not in claim_text_by_id:
            claim_text_by_id[cid_er] = cl_er
    for c in (r3.get("claims") or []):
        if not isinstance(c, dict):
            continue
        cid_c = str(c.get("id") or "").strip()
        cl_c = str(c.get("text") or "").strip()
        if cid_c and cl_c and cid_c not in claim_text_by_id:
            claim_text_by_id[cid_c] = cl_c
    fu = wf.get("follow_up_questions") or []
    if fu:
        # Dedupe by (claim_id, normalized question text). Without this, when one claim has several
        # triadic variants and another claim is off-topic, surfaced questions concentrate on the
        # same anchor instead of spreading across distinct claim ids — wasting slots.
        seen_fu_keys: Set[Tuple[str, str]] = set()
        per_claim_counts: Dict[str, int] = {}
        MAX_PER_CLAIM = 2
        MAX_TOTAL = 8
        emitted = 0
        for q in fu:
            if not isinstance(q, dict):
                continue
            qt = str(q.get("question") or "").strip()
            cid = str(q.get("claim_id") or "")
            if not qt:
                continue
            cl_src = str(claim_text_by_id.get(cid) or "").strip()
            if cl_src and not _appendix_surface_line_keeps(cl_src, spine_hint_ax):
                continue
            # Questions usually quote the source claim in single quotes. If that quoted text is
            # low-signal / off-spine, drop the question even when claim_id metadata is present.
            qm = re.search(r"[\"'“”‘’]([^\"“”‘’]{12,260})[\"'“”‘’]", qt)
            if qm:
                quoted_claim = str(qm.group(1) or "").strip()
                if quoted_claim and not _appendix_surface_line_keeps(quoted_claim, spine_hint_ax):
                    continue
            if per_claim_counts.get(cid, 0) >= MAX_PER_CLAIM:
                continue
            norm = re.sub(r"\s+", " ", qt.lower())[:200]
            key = (cid, norm)
            if key in seen_fu_keys:
                continue
            seen_fu_keys.add(key)
            per_claim_counts[cid] = per_claim_counts.get(cid, 0) + 1
            lines.append(f"- **[{cid}]** {_polish_followup_question_text(qt)}")
            emitted += 1
            if emitted >= MAX_TOTAL:
                break
    else:
        eng = r3.get("engagement_questions") or {}
        for cid in sorted(
            eng.keys(),
            key=lambda x: int(x[1:]) if str(x)[1:].isdigit() else 0,
        ):
            cl_src = str(claim_text_by_id.get(str(cid)) or "").strip()
            if cl_src and not _appendix_surface_line_keeps(cl_src, spine_hint_ax):
                continue
            tri = eng.get(cid) or {}
            for label, key in (
                ("Counter", "counterpunch"),
                ("Validation", "validation"),
                ("Application", "application"),
            ):
                t = str(tri.get(key) or "").strip()
                if t and _appendix_surface_line_keeps(t, spine_hint_ax):
                    lines.append(f"- **[{cid}]** ({label}) {_polish_followup_question_text(t)}")
    lines.append("")

    em_claim_ids_for_table: List[str] = []
    for e in (wf.get("evidence_map") or []):
        if not isinstance(e, dict):
            continue
        cl_raw = str(e.get("claim") or "").strip()
        if not _appendix_surface_line_keeps(cl_raw, spine_hint_ax):
            continue
        if not _workflow_claim_line_is_actionable(cl_raw):
            continue
        cid_t = str(e.get("id") or "").strip()
        if cid_t and cid_t not in em_claim_ids_for_table:
            em_claim_ids_for_table.append(cid_t)

    # --- 4. Guest / Research Recommendations (filtered via workflow_guest_rows)
    lines.append("## 4. Guest / Research Recommendations")
    gr = _workflow_body_guest_rows(wf)
    if gr:
        use_rich = bool(
            gr
            and isinstance(gr[0], dict)
            and gr[0].get("guest_archetype")
            and (gr[0].get("what_it_fixes") or gr[0].get("topic_angle"))
        )
        if use_rich:
            lines.append(
                "**Guest strategy — what to bring on next** *(tied to this episode’s weaknesses, not a name list)*"
            )
            lines.append("")
            first = gr[0] if gr and isinstance(gr[0], dict) else {}
            commit = str(first.get("commitment_line") or "").strip()
            if commit:
                lines.append(commit)
                lines.append("")
            n = 0
            for g in gr[:8]:
                if not isinstance(g, dict):
                    continue
                n += 1
                nm = str(g.get("name") or "Guest archetype").strip()
                why = str(g.get("angle") or "").strip()
                look = str(g.get("topic_angle") or "").strip()
                fix = str(g.get("what_it_fixes") or "").strip()
                seq = str(g.get("sequence_label") or "").strip()
                head = f"### {seq}: {nm}" if seq else f"### {n}. {nm}"
                lines.append(head)
                lines.append("")
                if why:
                    lines.append(f"- **Why:** {why}")
                if look:
                    lines.append(f"- **Look for:** {look}")
                if fix:
                    lines.append(f"- **What it fixes:** {fix}")
                nem = str(g.get("next_episode_move") or "").strip()
                if nem and str(g.get("guest_sequence") or "") == "primary":
                    lines.append(f"- **Next episode move:** {nem}")
                lines.append("")
        else:
            # Decide whether to show the "Claim" column. When every row would collapse to the
            # same placeholder id (a1 / c1 / blank) and we have no evidence-map claim ids to
            # redistribute them across, the column is pure noise — drop it instead of pretending
            # that all guests map to the same claim.
            raw_cids = [
                str(g.get("claim_id") or "").strip()
                for g in gr[:8]
                if isinstance(g, dict)
            ]
            degenerate_cids = all(cid in ("a1", "", "c1") for cid in raw_cids) if raw_cids else True
            show_claim_col = not (degenerate_cids and not em_claim_ids_for_table)
            if show_claim_col:
                lines.append("| Suggested Guest | Title | Topic / Angle | Claim | Relevance |")
                lines.append("| --- | --- | --- | --- | --- |")
            else:
                lines.append("| Suggested Guest | Title | Topic / Angle | Relevance |")
                lines.append("| --- | --- | --- | --- |")
            for gi, g in enumerate(gr[:8]):
                if not isinstance(g, dict):
                    continue
                cid_disp = str(g.get("claim_id") or "").strip()
                if cid_disp in ("a1", "", "c1") and em_claim_ids_for_table:
                    cid_disp = em_claim_ids_for_table[min(gi, len(em_claim_ids_for_table) - 1)]
                disp_title = str(g.get("title") or g.get("role", "") or "").strip()
                if disp_title.lower() == "suggested":
                    try:
                        from .soapboxx_v3_workflow import _workflow_title_for_coach_strategy_guest
                    except ImportError:
                        from soapboxx_v3_workflow import _workflow_title_for_coach_strategy_guest  # type: ignore
                    disp_title = _workflow_title_for_coach_strategy_guest(str(g.get("name") or ""))
                if show_claim_col:
                    lines.append(
                        f"| {g.get('name', '')} | {disp_title} | "
                        f"{g.get('topic_angle') or g.get('angle', '')} | {cid_disp} | "
                        f"{g.get('relevance', '')} |"
                    )
                else:
                    lines.append(
                        f"| {g.get('name', '')} | {disp_title} | "
                        f"{g.get('topic_angle') or g.get('angle', '')} | "
                        f"{g.get('relevance', '')} |"
                    )
    else:
        lines.append(
            "- *(See coach report guest strategy in `markdown_v3`, or enable workflow AI enrichment.)*"
        )
    lines.append("")

    lines.append("## 5. Segment Planning")
    segs = wf.get("segments") or []
    segment_emitted = 0
    if segs:
        for s in segs[:12]:
            if not isinstance(s, dict):
                continue
            title = str(s.get("title") or s.get("segment_id") or "").strip()
            if title and not _appendix_surface_line_keeps(title, spine_hint_ax):
                continue
            goal = str(s.get("goal") or "").strip()
            if goal and not _appendix_surface_line_keeps(goal, spine_hint_ax):
                continue
            lines.append(f"- **{title}** — {goal}")
            segment_emitted += 1
            if segment_emitted >= 5:
                break
    else:
        for s in (r3.get("segments") or [])[:12]:
            if isinstance(s, dict):
                st = str(s.get("segment_title", "") or "").strip()
                if st and not _appendix_surface_line_keeps(st, spine_hint_ax):
                    continue
                goal = str(s.get("goal") or "").strip()
                if goal and not _appendix_surface_line_keeps(goal, spine_hint_ax):
                    continue
                lines.append(f"- {st} — {goal}")
                segment_emitted += 1
                if segment_emitted >= 5:
                    break
    if segment_emitted == 0:
        cr_seg = (r3.get("coach_report") or {}) if isinstance(r3.get("coach_report"), dict) else {}
        seg_up = str(cr_seg.get("segment_upgrade") or "").strip()
        if seg_up:
            lines.append(f"- {seg_up}")
            segment_emitted += 1
        for step in [str(x).strip() for x in (cr_seg.get("immediate_fix_plan") or []) if str(x).strip()]:
            if _line_is_actionable_step(step):
                lines.append(f"- {step}")
                segment_emitted += 1
            if segment_emitted >= 3:
                break
    if segment_emitted == 0:
        lines.append(
            "- Confirm thesis in first 60 seconds, force a midpoint counterargument, and close with one weekly action."
        )
    lines.append("")

    lines.append("## 6. Analytics / Narrative Tracking")
    an = wf.get("analytics") or {}
    aa = r3.get("analytics_actionable") or {}
    cr_ax = (r3.get("coach_report") or {}) if isinstance(r3.get("coach_report"), dict) else {}
    story = list(an.get("storylines") or aa.get("what_worked") or [])[:6]
    topics = list(an.get("topic_signals") or aa.get("what_failed") or [])[:8]
    steps = _workflow_actionable_steps(an, aa, cr_ax, max_steps=6)
    if story:
        lines.append("**Recurring / supporting themes:**")
        for x in story:
            lines.append(f"- {x}")
    if topics:
        lines.append("**Topic signals:** " + ", ".join(str(t) for t in topics))
    if steps:
        lines.append("**Next moves:**")
        for x in steps:
            lines.append(f"- {x}")
    if not story and not topics and not steps:
        lines.append("- *(No analytics block — see `markdown_v3` coach diagnosis.)*")
    lines.append("")

    # Section 7 ("Episode Comparison Graph (Optional)") was an empty heading — removed because
    # shipping a blank section reads as noise. When a cross-episode graph becomes available, add
    # it back only when it has actual rows.
    lines.append(f"*SoapBoxx Episode Intelligence — workflow appendix — v{REPORT_V3_VERSION}*")
    return "\n".join(lines)


# Appendix closing tag (line-start). Dashes may be em/en/hyphen after editorial LLM passes.
_RE_WORKFLOW_APPENDIX_FOOTER_LINE = re.compile(
    r"(?m)^[ \t]*\*SoapBoxx Episode Intelligence\s*[\u2014\u2013\-]\s*workflow appendix\s*"
    r"[\u2014\u2013\-]\s*v\s*\d+\s*\*",
    re.I,
)


def _unified_export_tail_is_duplicate_noise(tail: str) -> bool:
    """True when content after the workflow appendix footer is a second report / template leak."""
    ts = (tail or "").strip()
    if not ts:
        return False
    low = ts.lower()
    low_norm = (
        low.replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )
    if len(ts) > 2000:
        return True
    if low.startswith("core narrative"):
        return True
    if re.match(r"(?is)^core narrative\s*:", ts[:200].lstrip()):
        return True
    dup_markers = (
        "## workflow execution checklist",
        "# soapboxx episode report",
        "execution layer (mandatory)",
        "execution layer",
        "core narrative:",
        "1. key highlights",
        "2. key beats",
        "## appendix - evidence",
        "canonical unified brief is above",
        "soapboxx episode intelligence — workflow",
        "*soapboxx episode intelligence",
        "criminal enterprise, law enforcement",
        "guest rows loaded from soapboxx_workflow_report",
        "no-worry publishing standard",
        "if you want more",
        "what this doesn't do",
        "local pipeline highlights",
        "transcript-anchor table",
        "shipping checklist are hidden",
    )
    if any(m in low_norm for m in dup_markers):
        return True
    # Second numbered appendix (1. Key Highlights …) after the real checklist already ended.
    if re.search(r"(?mi)^\s*1\.\s*key highlights\b", ts):
        return True
    # Legacy/local execution template tails often restart numbering from 8/9/10 after footer.
    if re.search(r"(?mi)^\s*(8|9|10)\.\s*(episode comparison graph|what this does(?:n't|n['’]t) do|if you want more)\b", ts):
        return True
    return False


# Numbered meta sections that add no value: "Episode Comparison Graph" is an empty placeholder,
# "What this doesn't do" is product-marketing disclaimer boilerplate, "If you want more" is an
# upsell block. We strip any of them wherever they appear in the body, not only when tacked on
# after the appendix footer. Section numbers are permissive (7-10) because editorial LLM passes
# sometimes renumber.
# Phrase marker for meta/marketing sections — matched only when the line starts with a heading
# or a numbered-section prefix (``#`` / ``8.`` / ``10.``) to avoid swallowing paragraph text that
# happens to reference one of these phrases.
_RE_META_MARKETING_PHRASE = re.compile(
    r"(?i)(?:"
    r"episode\s+comparison\s+graph"
    r"|what\s+this\s+does(?:n['’]t|\s+not)\s+do"
    r"|if\s+you\s+want\s+more"
    r"|no[-\s]worry\s+publishing\s+standard"
    r")"
)
# Numbered-section prefix accepts 7-20 so editorial LLM renumbering (e.g. "11. If you want more")
# is still caught by the strip pass. Plain `#`-prefixed headings match at any depth (1-6).
_RE_HEADING_OR_NUMBERED = re.compile(
    r"^\s*(?:(#{1,6})\s+|(?:(?:7|8|9|1[0-9]|20)[.\)]\s+))"
)

# Standalone plain-text section markers emitted by the editorial LLM without any heading prefix.
# Example: a line that just reads ``No-worry publishing standard`` followed by a short checklist.
# We treat such lines as **virtual headings** so their body gets stripped too.
_RE_PLAIN_META_MARKETING_HEADING = re.compile(
    r"^\s*(?:"
    r"no[-\s]worry\s+publishing\s+standard"
    r"|if\s+you\s+want\s+more(?:\s*[…\.\s]*)?"
    r"|episode\s+comparison\s+graph(?:\s*\(optional\))?"
    r"|what\s+this\s+does(?:n['’]t|\s+not)\s+do(?:\s*\(yet\))?"
    r")\s*:?\s*$",
    re.IGNORECASE,
)

# Lines invented by the editorial LLM as a pseudo-prelude under the H1 — our real renderer never
# emits these, so we drop them wherever they appear. Keeping this narrow (prefix-only) avoids
# collateral damage on strategist paragraphs that happen to mention the same phrases.
# Optional ``**`` wrappers appear when the polish pass markdown-ifies invented labels.
_RE_HALLUCINATED_PRELUDE_LINE = re.compile(
    r"^\s*(?:\*{0,2}\s*)?(?:"
    r"Primary\s+workflow\s*(?:\*{0,2}\s*)?:"
    r"|Compact\s+brief\s*\(v2(?:\s+filename)?\)\s*(?:\*{0,2}\s*)?:"
    r"|Compact\s+brief\s*(?:\*{0,2}\s*)?:"
    # ``**Core Narrative:** rest`` (colon before closing ``**``) and ``Core Narrative: rest``
    r"|Core\s+Narrative\s*:\s*\*{0,2}"
    r"|Core\s+Narrative\s*(?:\*{0,2}\s*)?:"
    r")",
    re.IGNORECASE,
)


def _sync_genre_line_from_title(md: str) -> str:
    """When the editorial pass echoes ``Genre: Entertainment`` but ``Title:`` clearly signals
    education/politics/etc., rewrite the genre line using :func:`_refine_genre_from_title`.

    This fixes LLM reformats that ignore the already-correct ``episode_snapshot`` in JSON.
    """
    if not (md or "").strip():
        return md
    try:
        from .episode_intelligence import _refine_genre_from_title  # type: ignore
    except ImportError:
        from episode_intelligence import _refine_genre_from_title  # type: ignore

    title_val: Optional[str] = None
    lines = md.splitlines()
    for ln in lines[:120]:
        t_m = re.match(
            r"^\s*(?:\*\*)?Title:(?:\*\*)?\s*(.+?)\s*$",
            ln,
            flags=re.IGNORECASE,
        )
        if t_m and title_val is None:
            title_val = t_m.group(1).strip().strip('"“”')
            continue
    if not title_val:
        return md

    def _rewrite_genre_line(ln: str) -> str:
        g_m = re.match(
            r"^\s*((?:\*\*)?Genre:(?:\*\*)?\s*)(.+?)\s*$",
            ln,
            flags=re.IGNORECASE,
        )
        if not g_m:
            return ln
        prefix, genre_raw = g_m.group(1), g_m.group(2).strip()
        refined = _refine_genre_from_title(title_val, genre_raw)
        if refined == genre_raw:
            return ln
        return f"{prefix}{refined}"

    return "\n".join(_rewrite_genre_line(ln) for ln in lines)


def _is_meta_marketing_heading_line(ln: str) -> bool:
    """True when the line is a (numbered or markdown) heading for a meta/marketing section."""
    m = _RE_HEADING_OR_NUMBERED.match(ln)
    if m and _RE_META_MARKETING_PHRASE.search(ln):
        return True
    # Editorial LLM sometimes drops the heading prefix entirely and just emits
    # ``No-worry publishing standard`` on its own line; still treat as a section start.
    return bool(_RE_PLAIN_META_MARKETING_HEADING.match(ln))


def _strip_hallucinated_prelude_lines(md: str) -> str:
    """Drop ``Core Narrative:`` / ``Primary workflow:`` / ``Compact brief (v2 filename):`` lines.

    Our renderer never emits these — they are hallucinated by the editorial LLM polish pass when it
    reformats the header. Stripping them keeps the export's declared metadata authoritative (Title /
    Show / Genre / Generated), without letting a stale ``primary_topic`` leak back as ``Core Narrative``.
    """
    if not (md or "").strip():
        return md
    kept: List[str] = []
    for ln in md.splitlines():
        if _RE_HALLUCINATED_PRELUDE_LINE.match(ln):
            continue
        kept.append(ln)
    cleaned = "\n".join(kept)
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def _strip_meta_marketing_sections(md: str) -> str:
    """
    Remove 'Episode Comparison Graph (Optional)', 'What this doesn't do (yet)', and
    'If you want more…' sections and the 'No-worry publishing standard' block anywhere they
    appear in the markdown body.

    A section runs from its heading up to the next heading (``#``-prefixed *or* a top-level
    numbered ``N.`` line that is not another meta marker), the appendix footer, or end of
    document. This lets us drop the whole block (heading + bullets) in a single pass.
    """
    if not (md or "").strip():
        return md
    lines = md.splitlines(keepends=False)
    out: List[str] = []
    skipping = False
    skip_level = 0
    for ln in lines:
        if skipping:
            if _RE_WORKFLOW_APPENDIX_FOOTER_LINE.match(ln):
                skipping = False
                out.append(ln)
                continue
            m_h = re.match(r"\s*(#{1,6})\s+", ln)
            if m_h and len(m_h.group(1)) <= skip_level:
                skipping = False
                if _is_meta_marketing_heading_line(ln):
                    skipping = True
                    skip_level = len(m_h.group(1))
                    continue
                out.append(ln)
                continue
            # A top-level numbered section line ("11. Something") terminates skipping too,
            # unless it's another meta marker (which we immediately re-enter).
            m_num = re.match(r"\s*(\d{1,2})[.\)]\s+", ln)
            if m_num and not skip_level <= 1:
                # Only treat numbered lines as "sibling headings" when the current skipped
                # section started from an unheaded numbered line (skip_level was left as 2).
                if _is_meta_marketing_heading_line(ln):
                    continue
                skipping = False
                out.append(ln)
                continue
            continue
        if _is_meta_marketing_heading_line(ln):
            m_h = re.match(r"\s*(#{1,6})\s+", ln)
            skip_level = len(m_h.group(1)) if m_h else 2
            skipping = True
            continue
        out.append(ln)
    cleaned = "\n".join(out)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def finalize_unified_markdown_export(md: str) -> str:
    """
    Drop accidental **second copies** of the report sometimes appended after the workflow appendix
    footer (e.g. editorial LLM pass re-outputting highlights / execution blocks).
    The canonical export ends at the italic ``*SoapBoxx Episode Intelligence — workflow appendix*`` line.

    Also strips meta-marketing sections (Episode Comparison Graph placeholder, "What this doesn't
    do", "If you want more…", "No-worry publishing standard") wherever they appear, since those
    are either empty or boilerplate disclaimers that add no episode-specific value.

    Matching is **regex + last occurrence**: line-based search alone misses cases where the model
    appends ``Core Narrative:`` on the same line as the footer or drops the newline before the leak.
    """
    if not (md or "").strip():
        return md
    # Pass 1a: drop LLM-invented prelude lines ("Core Narrative:", "Primary workflow:", …) that
    # the editorial polish pass sometimes inserts between the H1 and the Title/Show metadata.
    md = _strip_hallucinated_prelude_lines(md)
    # Pass 1b: strip marketing/placeholder sections anywhere in the body.
    md = _strip_meta_marketing_sections(md)
    # Pass 1c: fix ``Genre: Entertainment`` echoed by the polish pass when ``Title:`` clearly
    # signals education / politics / history (snapshot-aware refiners already ran on JSON).
    md = _sync_genre_line_from_title(md)
    # Pass 2: strip duplicate tail after the appendix footer (pre-existing behavior).
    matches = list(_RE_WORKFLOW_APPENDIX_FOOTER_LINE.finditer(md))
    if not matches:
        return md
    m = matches[-1]
    cut = m.end()
    rest = md[cut:].lstrip("\n\r \t")
    if not rest:
        return md[:cut].rstrip() + "\n"
    if len(rest) < 60:
        return md[:cut].rstrip() + "\n"
    if _unified_export_tail_is_duplicate_noise(rest):
        return md[:cut].rstrip() + "\n"
    return md


def render_unified_episode_export_markdown(bundle: Dict[str, Any]) -> str:
    """
    One markdown string for sharing: **strategist export** plus optional **workflow execution appendix**
    (highlights → analytics) so a single file matches the “canonical unified brief” UX.

    Compression / truth gates apply to the strategist layer via :func:`_render_strategist_export_markdown`.

    Set ``SOAPBOXX_UNIFIED_APPENDIX=0`` to omit sections 1–7 (strategist-only; smaller paste).
    """
    strategist = _render_strategist_export_markdown(bundle).rstrip()
    raw_appendix = (os.getenv("SOAPBOXX_UNIFIED_APPENDIX") or "1").strip().lower()
    if raw_appendix in ("0", "false", "no", "off"):
        out = strategist + "\n"
        _strict_episode_report_h1_pre_check(out, where="render_unified_episode_export_markdown(strategist-only)")
        return ensure_single_episode_report_markdown(out)
    appendix = render_workflow_execution_appendix_markdown(bundle).strip()
    if not appendix:
        out = strategist + "\n"
        _strict_episode_report_h1_pre_check(out, where="render_unified_episode_export_markdown(no-appendix)")
        return ensure_single_episode_report_markdown(out)
    combined = strategist + "\n\n---\n\n" + appendix + "\n"
    out = finalize_unified_markdown_export(combined)
    _strict_episode_report_h1_pre_check(out, where="render_unified_episode_export_markdown(full)")
    return ensure_single_episode_report_markdown(out)


def generate_episode_report_v3(
    transcript: str,
    metadata: Optional[Dict[str, str]] = None,
    *,
    client: Any = None,
    use_new_api: bool = True,
    api_key: Optional[str] = None,
    strict_references: bool = True,
    include_v2_markdown: bool = True,
    atomic_ground_truth: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Full v3 pipeline: base brief (v2 generator) + v3 enrichment + markdown.

    Applies :func:`transcript_for_v3_pipeline` before the brief pass (normalization is **on** by
    default; set ``SOAPBOXX_TRANSCRIPT_NORMALIZE=0`` to disable).

    ``atomic_ground_truth`` is forwarded to :func:`build_v3_report` (see module docstring).
    """
    meta = dict(metadata or {})
    transcript = transcript_for_v3_pipeline(transcript or "")
    base = generate_episode_brief(
        transcript,
        meta,
        client=client,
        use_new_api=use_new_api,
        api_key=api_key,
    )
    brief = base.get("brief") or {}
    report = build_v3_report(
        brief, transcript or "", metadata=meta, atomic_ground_truth=atomic_ground_truth
    )
    warnings = list(base.get("warnings") or [])
    product_mode = _episode_product_mode()
    truth_gate = {
        "mode": product_mode,
        "passed": True,
        "reasons": [],
        "metrics": {},
    }

    if product_mode == "truth":
        passed, reasons, gate_metrics = evaluate_truth_mode_hard_gates(
            report, transcript=transcript or ""
        )
        truth_gate = {
            "mode": product_mode,
            "passed": bool(passed),
            "reasons": list(reasons or []),
            "metrics": gate_metrics,
        }
        if not passed:
            rr = report.get("report_readiness")
            if not isinstance(rr, dict):
                rr = {}
                report["report_readiness"] = rr
            rr["output_mode"] = "diagnostic"
            dr = rr.get("diagnostic_reasons")
            if not isinstance(dr, list):
                dr = []
            for r in reasons:
                if r not in dr:
                    dr.append(r)
            rr["diagnostic_reasons"] = dr
            report["output_mode"] = "diagnostic"
            report["truth_mode_gate"] = truth_gate

    if strict_references:
        validate_v3_report_or_raise(report)

    if product_mode == "truth" and not truth_gate.get("passed"):
        md_v3 = _truth_mode_failure_markdown(
            list(truth_gate.get("reasons") or []),
            title=str((report.get("meta") or {}).get("title") or meta.get("title") or ""),
            creator=str(
                (report.get("meta") or {}).get("creator") or meta.get("creator") or ""
            ),
        )
    else:
        md_v3 = render_episode_report_v3_markdown(report)
    out: Dict[str, Any] = {
        "report_v3": report,
        "markdown_v3": md_v3,
        "brief": brief,
        "warnings": warnings,
        "model": base.get("model"),
        "workflow_version": REPORT_V3_VERSION,
        "truth_mode_gate": truth_gate,
    }
    if include_v2_markdown:
        if product_mode == "truth" and not truth_gate.get("passed"):
            out["markdown"] = md_v3
        else:
            out["markdown"] = base.get("markdown") or render_markdown(
                brief, meta.get("generated_at")
            )
    out["meta"] = {
        "generated_at": meta.get("generated_at"),
        "title": meta.get("title"),
        "creator": meta.get("creator"),
        "genre": meta.get("genre"),
    }
    out["episode_spine"] = build_episode_spine(report, None)
    try:
        from .episode_progress import (
            attach_export_telemetry_to_metadata,
            persist_episode_progress_after_export,
            prepare_bundle_for_export,
        )
    except ImportError:
        from episode_progress import (  # type: ignore
            attach_export_telemetry_to_metadata,
            persist_episode_progress_after_export,
            prepare_bundle_for_export,
        )

    prepare_bundle_for_export(out)
    attach_export_telemetry_to_metadata(out.get("meta") or {}, out)
    if product_mode == "truth" and not truth_gate.get("passed"):
        out["markdown_export"] = md_v3
    else:
        out["markdown_export"] = render_unified_episode_export_markdown(out)
    persist_episode_progress_after_export(out)
    return out


def dialin_production_warnings(bundle: Dict[str, Any]) -> List[str]:
    """
    High-signal checklist when a real-episode run still looks weak: environment and upstream
    extraction failures are the usual cause — not “v2 vs v3”. Results are merged into bundle
    ``warnings`` by :func:`feedback_engine.FeedbackEngine.generate_network_brief_v3`.
    """
    lines: List[str] = []
    offline = os.getenv("SOAPBOXX_OFFLINE", "").strip().lower() in ("1", "true", "yes")
    ollama = (os.getenv("SOAPBOXX_OLLAMA_MODEL") or "").strip()
    brief_model = str(bundle.get("model") or "").strip()

    if offline:
        lines.append(
            "DIAL-IN: SOAPBOXX_OFFLINE is on — the strict JSON brief is skipped. "
            "Unset SOAPBOXX_OFFLINE in `.env` for full v3 quality (Ollama + coach/workflow)."
        )
    elif not ollama or brief_model == "brief-unavailable":
        lines.append(
            "DIAL-IN: SOAPBOXX_OLLAMA_MODEL is not set or brief failed to load — claims stay a thin shell. "
            "Set `SOAPBOXX_OLLAMA_MODEL=llama3.1:8b` (or your model) and ensure Ollama is running (`preflight` / health)."
        )

    r3 = bundle.get("report_v3")
    if not isinstance(r3, dict):
        return lines
    meta = r3.get("meta") if isinstance(r3.get("meta"), dict) else {}
    src = str(meta.get("structured_intelligence_source") or "")
    claims = r3.get("claims") if isinstance(r3.get("claims"), list) else []
    n_claims = len(claims)
    if src == "strict_episode_brief" and n_claims < 2 and not offline and ollama:
        lines.append(
            f"DIAL-IN: Only {n_claims} claim(s) after build — for long shows, check Ollama errors, "
            "raise `SOAPBOXX_BRIEF_MAX_CHARS` / `SOAPBOXX_BRIEF_CONTRACT_MAX_CHARS`, and run `python scripts/preflight_soapboxx.py`."
        )
    if src == "atomic_pipeline" and n_claims < 1:
        lines.append(
            "DIAL-IN: Atomic pipeline returned no claims — check `atomic_pipeline` / stderr; graph guests will be weak until claims exist."
        )

    cr = r3.get("coach_report")
    if isinstance(cr, dict) and n_claims >= 4:
        fu = cr.get("follow_up_questions") or []
        if isinstance(fu, list) and len(fu) < 2:
            lines.append(
                "DIAL-IN: Few coach follow-ups despite many claims — enable `SOAPBOXX_COACH_SYNTH=1` "
                "with Ollama or Groq for sharper prompts."
            )

    wf = bundle.get("workflow_report")
    if isinstance(wf, dict):
        wm = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
        st = str(wm.get("export_status") or "").strip().lower()
        if st in ("degraded", "insufficient_signal"):
            lines.append(
                f"DIAL-IN: workflow `export_status` is {st!r} — workflow JSON may be thin; read `workflow_report.metadata` and bundle warnings."
            )

    return lines


__all__ = [
    "REPORT_V3_VERSION",
    "SEMANTIC_DUP_THRESHOLD",
    "clean_key_highlights",
    "text_similarity",
    "remove_semantic_duplicates",
    "generate_engagement_questions",
    "map_guest_to_claim",
    "build_evidence_mapping",
    "build_executable_segments",
    "detect_signal_mode",
    "build_actionable_analytics",
    "build_coach_report",
    "validate_references",
    "build_v3_report",
    "apply_identity_consistency_to_report_v3",
    "apply_claim_quality_gate",
    "apply_semantic_grounding_validator",
    "apply_system_health_label",
    "validate_v3_invariants",
    "render_episode_report_v3_markdown",
    "render_unified_episode_export_markdown",
    "EPISODE_REPORT_MARKDOWN_H1",
    "ensure_single_episode_report_markdown",
    "finalize_unified_markdown_export",
    "render_workflow_execution_appendix_markdown",
    "build_episode_spine",
    "format_episode_spine_markdown_lines",
    "generate_episode_report_v3",
    "validate_v3_report_or_raise",
    "compute_report_readiness",
    "merge_workflow_followups_into_engagement",
    "is_low_signal_insight_line",
    "classify_output_mode",
    "strict_export_enabled",
    "strategist_truth_gate_bundle",
    "render_limited_signal_export_markdown",
    "evaluate_argument_rigor_report",
    "workflow_export_should_abort_insufficient",
    "bundle_grounded_evidence_counts",
    "export_structural_tier",
    "export_compression_enabled",
    "compressed_action_bullets",
    "dialin_production_warnings",
]
