# backend/episode_reference_shelf.py
"""
Curated **works cited / verification shelf** for episode exports.

SoapBoxx matches your claims and thesis text against *known-good* anchors (real books, major reports,
.gov hubs). This is **not** automated fact-checking: it is a starting shelf so producers can pull
primary material instead of leaning on model paraphrase alone.

No invented ISBNs or page numbers — only strings we ship in-repo. Optional ``find_at`` may be a
search hint or canonical URL.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple

ShelfRow = Tuple[str, Tuple[str, ...], str, str]  # id, triggers, mla_line, find_at


# Order = priority when multiple rows match (put broad education rows after more specific ones).
_SHELF: List[ShelfRow] = [
    (
        "cdc_yrbss",
        ("cdc", "yrbss", "youth risk behavior", "behavior survey", "suicide", "killing themselves"),
        (
            'Centers for Disease Control and Prevention. *Youth Risk Behavior Surveillance System (YRBSS): '
            "Data Summary & Trends.* CDC, ongoing reports."
        ),
        "https://www.cdc.gov/healthyyouth/data/yrbs/index.htm",
    ),
    (
        "nces",
        ("department of education", "national center for education", "nces", "ipeds", "school statistics"),
        (
            "National Center for Education Statistics. *Digest of Education Statistics.* "
            "Institute of Education Sciences, U.S. Department of Education, annual."
        ),
        "https://nces.ed.gov/programs/digest/",
    ),
    (
        "ravitch_reign",
        (
            "privatization",
            "charter",
            "school choice",
            "standardized test",
            "corporate reform",
            "education reform",
        ),
        (
            'Ravitch, Diane. *Reign of Error: The Hoax of the Privatization Movement and the Danger to '
            "America's Public Schools.* Alfred A. Knopf, 2013."
        ),
        "WorldCat or your library catalog; search title + author for the edition you cite on mic.",
    ),
    (
        "tyack_one_best",
        (
            "centralization",
            "centralized",
            "urban school",
            "public school system",
            "school board",
            "bureaucracy",
            "one best system",
        ),
        (
            "Tyack, David B. *The One Best System: A History of American Urban Education.* "
            "Harvard University Press, 1974."
        ),
        "Harvard University Press catalog or academic library stacks (LA 215 / history of education).",
    ),
    (
        "bowles_gintis",
        ("credential", "workforce", "inequality", "classroom", "social reproduction", "capitalism"),
        (
            "Bowles, Samuel, and Herbert Gintis. *Schooling in Capitalist America: Educational Reform and the "
            "Contradictions of Economic Life.* Basic Books, 1976."
        ),
        "Academic library; often shelved under economics of education / sociology of education.",
    ),
    (
        "cremin_transformation",
        ("common school", "horace mann", "progressive education", "american education", "school reform history"),
        (
            "Cremin, Lawrence A. *The Transformation of the School: Progressivism in American Education, 1876-1957.* "
            "Vintage Books, 1961."
        ),
        "Standard U.S. education-history survey text; verify edition for your citation style.",
    ),
    (
        "foundation_990",
        ("foundation", "philanthrop", "grant", "990", "endowment", "donor"),
        (
            "Internal Revenue Service. *Return of Organization Exempt from Income Tax (Form 990).* "
            "IRS / Candid (Foundation Directory), filings by tax year."
        ),
        "https://www.irs.gov/charities-non-profits/form-990-resources-for-tax-exempt-organizations",
    ),
    (
        "rockefeller_archive",
        ("rockefeller", "rockfeller", "general education board", "g.e.b.", "flexner"),
        (
            "Rockefeller Archive Center. *Guide to the General Education Board Collection* and related "
            "finding aids. Sleepy Hollow, NY, archival holdings."
        ),
        "https://rockarch.org/ — use finding aids for primary documents before inferring intent.",
    ),
    (
        "nepc_policy",
        ("think tank", "policy brief", "school closure", "education policy", "research synthesis"),
        (
            "Baker, Bruce D., et al. *Reports and policy briefs.* National Education Policy Center, "
            "University of Colorado Boulder, ongoing."
        ),
        "https://nepc.colorado.edu/ — filter by topic; read methodology sections before citing statistics.",
    ),
]


def _haystack_from_report(report: Dict[str, Any]) -> str:
    parts: List[str] = []
    for c in report.get("claims") or []:
        if isinstance(c, dict):
            parts.append(str(c.get("text") or ""))
    for row in report.get("evidence_mapping") or []:
        if isinstance(row, dict):
            parts.append(str(row.get("claim") or ""))
            parts.append(str(row.get("evidence") or ""))
    cr = report.get("coach_report") if isinstance(report.get("coach_report"), dict) else {}
    parts.append(str(cr.get("episode_thesis") or ""))
    snap = report.get("episode_snapshot") if isinstance(report.get("episode_snapshot"), dict) else {}
    parts.append(str(snap.get("title") or ""))
    parts.append(str(snap.get("primary_topic") or ""))
    return " \n ".join(parts).lower()


def collect_reference_shelf(report: Dict[str, Any], *, max_entries: int = 8) -> List[Dict[str, str]]:
    """
    Return a list of dicts: id, mla, find_at — curated only, keyword-triggered.
    """
    hay = _haystack_from_report(report)
    out: List[Dict[str, str]] = []
    seen: set[str] = set()
    for sid, triggers, mla, find_at in _SHELF:
        if not triggers or not mla:
            continue
        if any(t in hay for t in triggers):
            if sid in seen:
                continue
            seen.add(sid)
            out.append({"id": sid, "mla": mla.strip(), "find_at": (find_at or "").strip()})
        if len(out) >= max_entries:
            break
    return out


def format_reference_shelf_markdown(entries: Sequence[Dict[str, Any]]) -> List[str]:
    """Markdown block for v3 coach export (appendix B)."""
    if not entries:
        return []
    lines: List[str] = [
        "",
        "---",
        "## Appendix B — Works cited (verification shelf)",
        "",
        "*Curated anchors matched to language in this run — **not** verified citations for your specific "
        "quotes. Pull the primary document (book chapter, 990, archival file, or agency table) before "
        "repeating numbers in marketing.*",
        "",
    ]
    for i, e in enumerate(entries, start=1):
        mla = str(e.get("mla") or "").strip()
        find_at = str(e.get("find_at") or "").strip()
        if not mla:
            continue
        lines.append(f"{i}. {mla}")
        if find_at:
            lines.append(f"   *Locate:* {find_at}")
        lines.append("")
    lines.append(
        "*Style note: Italics follow common handbook practice for long works; adjust to MLA 9 / Chicago / "
        "AP as your network requires.*"
    )
    lines.append("")
    return lines


def proper_nouns_from_claims(report: Dict[str, Any], *, max_names: int = 14) -> List[str]:
    """
    Surface capitalized phrases from claim text so producers see **names already on the tape**
    (strings only — no biography, no fact claims).
    """
    blob = " ".join(
        str(c.get("text") or "")
        for c in (report.get("claims") or [])[:40]
        if isinstance(c, dict)
    )
    # Sequences of Title-Case tokens (2–4 words) or single capitalized token >= 5 chars.
    # Single-word matches are noisy in transcripts ("Because", "Which", "Actually"), so we only
    # keep them when they recur or are in a small explicit allowlist.
    stop_single = {
        "because",
        "which",
        "actually",
        "there",
        "everyone",
        "companies",
        "host",
        "guest",
        "that",
        "this",
        "when",
        "what",
        "just",
        "like",
    }
    single_allow = {"daniel", "babylon", "israel", "judah", "joseph", "revelation", "alexa"}
    single_counts: Dict[str, int] = {}
    for m in re.finditer(r"\b[A-Z][a-z]{4,}\b", blob):
        k = m.group(0).strip().lower()
        single_counts[k] = single_counts.get(k, 0) + 1

    found: List[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}|[A-Z][a-z]{4,})\b", blob):
        w = m.group(0).strip()
        low = w.lower()
        if low in ("the", "and", "but", "host", "guest", "like", "just", "that", "this", "what", "when"):
            continue
        if " " not in w:
            if low in stop_single:
                continue
            if low not in single_allow and single_counts.get(low, 0) < 2:
                continue
        if w not in seen and len(w) >= 4:
            seen.add(w)
            found.append(w)
        if len(found) >= max_names:
            break
    return found


def format_named_strings_markdown(names: Sequence[str]) -> List[str]:
    if not names:
        return []
    return [
        "",
        "### Proper nouns surfacing in extracted claims (strings only)",
        "",
        "*Not verified identities or roles — cross-check the transcript before attributing motive or biography.*",
        "",
        ", ".join(names) + ".",
        "",
    ]


__all__ = [
    "collect_reference_shelf",
    "format_reference_shelf_markdown",
    "proper_nouns_from_claims",
    "format_named_strings_markdown",
]
