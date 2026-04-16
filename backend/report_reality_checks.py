"""
Creator-facing **reality checks** for v3 episode reports — not JSON shape tests.

Use these to assert outputs are specific, transcript-grounded, and worth shipping.
Designed for golden JSON (substring expectations) and CI gates with clear failure strings.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

# Reuse the same slop list as brief/markdown generation (single source of truth).
from episode_intelligence import BANNED_SUBSTRINGS, _has_banned_slop

# Extra phrases that often read as filler in creator-facing thesis / packaging.
_EXTRA_CREATOR_GENERIC = (
    "this episode talks about",
    "various aspects",
    "in today's world",
    "it is important to note",
    "interesting to hear",
    "they talk about their experiences",
)

_TENSION_MARKERS = (
    "but ",
    "however ",
    "didn't realize",
    "actually ",
    "turns out",
    "contradict",
    "tension",
    "rival",
    "competition",
    "risk",
    "breaks when",
)

_STOP = frozenset(
    """
    a an the and or but if to of in on for as at by from with into over per is are was were be been being
    it this that these those we you they he she i not no yes so than then too very just more most some any
    all can could should would will may might must about into out up down what when where why how who which
    """.split()
)


def is_generic_creator_text(text: str, extra_phrases: Optional[Sequence[str]] = None) -> bool:
    """True if text looks like AI filler / recap boilerplate (substring scan, case-insensitive)."""
    if not (text or "").strip():
        return True
    if _has_banned_slop(text):
        return True
    low = text.lower()
    for p in _EXTRA_CREATOR_GENERIC:
        if p in low:
            return True
    if extra_phrases:
        for p in extra_phrases:
            if p and str(p).lower() in low:
                return True
    return False


def extract_thesis_text(report: Mapping[str, Any]) -> str:
    """Best-effort thesis line from a v3 report dict."""
    nr = report.get("narrative_reconstruction") or {}
    t = str(nr.get("core_thesis") or "").strip()
    if t:
        return t
    cr = report.get("coach_report") or {}
    t = str(cr.get("episode_thesis") or "").strip()
    if t:
        return t
    snap = report.get("episode_snapshot") or {}
    return str(snap.get("primary_topic") or "").strip()


def collect_clip_proxy_texts(report: Mapping[str, Any]) -> List[str]:
    """
    Collect human-facing strings that should behave like “clip ideas”
    (segment titles, coach clip bullets — not raw transcript).
    """
    out: List[str] = []
    for seg in report.get("segments") or []:
        if isinstance(seg, dict):
            out.append(str(seg.get("segment_title") or ""))
    cr = report.get("coach_report") or {}
    opp = cr.get("opportunities") or {}
    for line in opp.get("clip_moments") or []:
        out.append(str(line))
    return [x for x in out if str(x).strip()]


def _content_words(text: str, *, min_len: int = 4) -> List[str]:
    raw = re.sub(r"[^\w\s-]", " ", (text or "").lower())
    words = []
    for w in raw.split():
        w = w.strip("-_")
        if len(w) < min_len or w in _STOP:
            continue
        words.append(w)
    return words


def thesis_grounding_ratio(thesis: str, transcript: str) -> float:
    """
    Fraction of thesis content-words that appear somewhere in the transcript (case-insensitive).
    1.0 = all content words found; 0.0 = none. Crude hallucination / drift guard.
    """
    t_words = _content_words(thesis)
    if not t_words:
        return 1.0
    pool = (transcript or "").lower()
    hits = sum(1 for w in t_words if w in pool)
    return hits / len(t_words)


def strong_clip_proxy(text: str) -> bool:
    """Heuristic: clip line has a turn / contrast / reveal cue."""
    low = (text or "").lower()
    return any(m in low for m in _TENSION_MARKERS)


def any_strong_clip_proxy(texts: Sequence[str]) -> bool:
    return any(strong_clip_proxy(t) for t in texts if t)


def would_ship_v3(
    report: Mapping[str, Any],
    transcript: str,
    *,
    min_evidence_rows: int = 2,
    min_clip_proxies: int = 2,
    min_grounding_ratio: float = 0.25,
) -> Tuple[bool, List[str]]:
    """
    Human-style ship bar: not diagnostic, thesis not generic, enough packaging rows,
    and thesis mostly grounded in transcript tokens.
    """
    reasons: List[str] = []
    mode = str(report.get("output_mode") or "").lower()
    if mode == "diagnostic":
        reasons.append("FAIL: output_mode is diagnostic — not shippable as a full brief.")
        return (False, reasons)

    thesis = extract_thesis_text(report)
    if not thesis.strip():
        reasons.append("FAIL: thesis / primary topic is empty.")
    elif is_generic_creator_text(thesis):
        reasons.append("FAIL: thesis reads as generic or banned filler phrasing.")

    if "unknown" in thesis.lower():
        reasons.append('FAIL: thesis contains "unknown" — reads unfinished.')

    ev = [e for e in (report.get("evidence_mapping") or []) if isinstance(e, dict)]
    if len(ev) < min_evidence_rows:
        reasons.append(
            f"FAIL: expected at least {min_evidence_rows} evidence rows, got {len(ev)}."
        )

    clips = collect_clip_proxy_texts(report)
    if len(clips) < min_clip_proxies:
        reasons.append(
            f"FAIL: expected at least {min_clip_proxies} clip/segment packaging lines, got {len(clips)}."
        )

    if thesis.strip():
        g = thesis_grounding_ratio(thesis, transcript)
        if g < min_grounding_ratio:
            reasons.append(
                f"FAIL: thesis grounding ratio {g:.2f} < {min_grounding_ratio:.2f} "
                "(many thesis words not found in transcript — possible drift)."
            )

    return (not reasons, reasons)


def default_reality_rules_path() -> Path:
    """Default baked-in rules JSON shipped with the backend (``backend/data/v3_reality_expected.json``)."""
    return Path(__file__).resolve().parent / "data" / "v3_reality_expected.json"


def load_reality_rules_from_path(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_default_reality_rules() -> Dict[str, Any]:
    p = default_reality_rules_path()
    if not p.is_file():
        return {}
    return load_reality_rules_from_path(p)


def _rules_without_meta(rules: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in rules.items() if not str(k).startswith("_")}


def validate_reality_golden(
    report: Mapping[str, Any],
    transcript: str,
    rules: Mapping[str, Any],
) -> List[str]:
    """
    Apply golden **expectations** (not full-string equality). Returns a list of failure lines;
    empty list means pass.

    Keys whose names start with ``_`` (e.g. ``_comment``) are ignored.

    Supported keys (all optional except you should pass something meaningful):
      - output_mode_one_of: list[str]
      - signal_mode / signal_mode_one_of: str | list[str]
      - expected_thesis_contains / thesis_must_contain: list[str] — needles in thesis (lower)
      - forbidden_terms / thesis_must_not_contain / banned_substrings_in_thesis: list[str]
      - min_evidence_rows: int
      - min_segments: int — v3 ``segments`` list length
      - min_clip_proxies: int — segment titles + coach clip lines
      - forbid_generic_thesis: bool
      - must_have_tension / has_tension: bool — tension markers in thesis + clip proxies
      - min_thesis_grounding_ratio: float — default 0.0 = skip
    """
    fails: List[str] = []
    rules = _rules_without_meta(rules)
    thesis = extract_thesis_text(report)
    low_thesis = thesis.lower()

    om = rules.get("output_mode_one_of")
    if om:
        cur = str(report.get("output_mode") or "")
        if cur not in om:
            fails.append(f"FAIL: output_mode {cur!r} not in allowed {om!r}")

    sm = rules.get("signal_mode")
    if sm is not None:
        if str(report.get("signal_mode") or "") != str(sm):
            fails.append(
                f"FAIL: signal_mode {report.get('signal_mode')!r} != expected {sm!r}"
            )
    sm_list = rules.get("signal_mode_one_of")
    if sm_list:
        cur = str(report.get("signal_mode") or "")
        if cur not in sm_list:
            fails.append(f"FAIL: signal_mode {cur!r} not in allowed {sm_list!r}")

    for key in ("expected_thesis_contains", "thesis_must_contain"):
        needles = rules.get(key)
        if needles:
            for needle in needles:
                n = str(needle).lower()
                if n not in low_thesis:
                    fails.append(f"FAIL: thesis missing expected phrase {needle!r}")

    for key in ("forbidden_terms", "thesis_must_not_contain", "banned_substrings_in_thesis"):
        banned = rules.get(key)
        if banned:
            for term in banned:
                t = str(term).lower()
                if t in low_thesis:
                    fails.append(f"FAIL: thesis contains forbidden term {term!r}")

    mer = rules.get("min_evidence_rows")
    if mer is not None:
        n = len([e for e in (report.get("evidence_mapping") or []) if isinstance(e, dict)])
        if n < int(mer):
            fails.append(f"FAIL: evidence rows {n} < min_evidence_rows {mer}")

    ms = rules.get("min_segments")
    if ms is not None:
        n = len([s for s in (report.get("segments") or []) if isinstance(s, dict)])
        if n < int(ms):
            fails.append(f"FAIL: segments {n} < min_segments {ms}")

    mc = rules.get("min_clip_proxies")
    if mc is not None:
        n = len(collect_clip_proxy_texts(report))
        if n < int(mc):
            fails.append(f"FAIL: clip proxy lines {n} < min_clip_proxies {mc}")

    if rules.get("forbid_generic_thesis"):
        if is_generic_creator_text(thesis):
            fails.append("FAIL: thesis failed generic / filler detection")

    if rules.get("must_have_tension") or rules.get("has_tension"):
        blob = low_thesis + " " + " ".join(collect_clip_proxy_texts(report)).lower()
        if not any(k in blob for k in _TENSION_MARKERS):
            fails.append("FAIL: no tension / contrast markers in thesis or clip proxies")

    mgr = rules.get("min_thesis_grounding_ratio")
    if mgr is not None and thesis.strip():
        r = thesis_grounding_ratio(thesis, transcript)
        if r < float(mgr):
            fails.append(
                f"FAIL: thesis grounding ratio {r:.2f} < min_thesis_grounding_ratio {mgr}"
            )

    return fails


__all__ = [
    "is_generic_creator_text",
    "extract_thesis_text",
    "collect_clip_proxy_texts",
    "thesis_grounding_ratio",
    "strong_clip_proxy",
    "any_strong_clip_proxy",
    "would_ship_v3",
    "validate_reality_golden",
    "default_reality_rules_path",
    "load_reality_rules_from_path",
    "load_default_reality_rules",
]
