"""Locked category list + default benchmarks when library is thin."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from .config import repo_root

_MIN_LIVE_DEFAULT = 2


@lru_cache(maxsize=1)
def _load_registry() -> Dict[str, Any]:
    path = repo_root() / "schemas" / "categories.json"
    if not path.is_file():
        return {"categories": [], "min_episodes_for_live_benchmarks": _MIN_LIVE_DEFAULT}
    return json.loads(path.read_text(encoding="utf-8"))


def category_ids() -> List[str]:
    reg = _load_registry()
    return [str(c["id"]) for c in reg.get("categories") or [] if c.get("id")]


def category_labels() -> List[Tuple[str, str]]:
    """(id, display label) for UI combos."""
    reg = _load_registry()
    out: List[Tuple[str, str]] = []
    for c in reg.get("categories") or []:
        cid = str(c.get("id") or "").strip()
        if not cid:
            continue
        label = str(c.get("label") or cid).strip()
        out.append((cid, label))
    return out or [("general", "General / mixed")]


def normalize_category(raw: str) -> str:
    """Map free text to a known category id; fallback ``general``."""
    s = (raw or "").strip().lower()
    if not s:
        return "general"
    ids = {x.lower(): x for x in category_ids()}
    if s in ids:
        return ids[s]
    slug = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if slug in ids:
        return ids[slug]
    for cid, label in category_labels():
        if s == label.lower() or s in label.lower():
            return cid
    return "general"


def default_benchmarks(category: str) -> Dict[str, Dict[str, float]]:
    cid = normalize_category(category)
    reg = _load_registry()
    for c in reg.get("categories") or []:
        if str(c.get("id")) == cid:
            defaults = c.get("defaults") or {}
            return {
                str(k): {
                    "avg": float(v.get("avg", 0)),
                    "p90": float(v.get("p90", 0)),
                    "p10": float(v.get("p10", 0)),
                }
                for k, v in defaults.items()
                if isinstance(v, dict)
            }
    return default_benchmarks("general")


def min_episodes_for_live_benchmarks() -> int:
    reg = _load_registry()
    try:
        return max(1, int(reg.get("min_episodes_for_live_benchmarks", _MIN_LIVE_DEFAULT)))
    except (TypeError, ValueError):
        return _MIN_LIVE_DEFAULT


def resolve_benchmarks(
    category: str,
    computed: Dict[str, Dict[str, float]],
    *,
    sample_size: int,
) -> Tuple[Dict[str, Dict[str, float]], str]:
    """
    Merge computed category stats with defaults when the library is thin.

    Returns ``(benchmarks, source_note)`` where source_note is for the report.
    """
    defaults = default_benchmarks(category)
    min_n = min_episodes_for_live_benchmarks()
    if sample_size >= min_n and computed:
        has_signal = any((v.get("avg") or 0) != 0 for v in computed.values())
        if has_signal:
            merged = dict(defaults)
            merged.update(computed)
            return merged, f"Category library: {sample_size} episode(s) in «{normalize_category(category)}»."
    merged = dict(defaults)
    for k, v in (computed or {}).items():
        if k not in merged and v:
            merged[k] = v
    return (
        merged,
        f"Using «{normalize_category(category)}» default benchmarks "
        f"({sample_size} episode(s) in library; need {min_n}+ for live averages).",
    )
