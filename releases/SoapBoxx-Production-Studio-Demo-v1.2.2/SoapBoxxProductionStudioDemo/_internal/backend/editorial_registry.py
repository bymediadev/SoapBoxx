"""
Per-show editorial profile registry (presentation-only).

Merges built-in slug → profile keys with an optional JSON overlay. Does not import
evaluation or decision logic.

Overlay path (first match):

1. ``SOAPBOXX_EDITORIAL_REGISTRY`` env (absolute or relative path)
2. ``<repo_root>/config/editorial_profiles.json`` if present

JSON may be a flat ``{"show-key": "interview", ...}`` or ``{"shows": {...}}``.
Keys are normalized to lower case; values must be valid profile names.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# Built-in defaults (single source of truth for code + merge base).
DEFAULT_EDITORIAL_PROFILES: Dict[str, str] = {
    "interview": "interview",
    "case_fire": "narrative",
    "daily": "balanced",
}

_META_KEYS_IN_ORDER: List[str] = [
    "podcast_id",
    "podcast_slug",
    "show_id",
    "show_slug",
    "editorial_show_key",
    "show_format",
    "episode_format",
]

_overlay_path_mtime: Optional[tuple] = None
_overlay_flat: Dict[str, str] = {}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _candidate_paths() -> List[Path]:
    out: List[Path] = []
    env = os.environ.get("SOAPBOXX_EDITORIAL_REGISTRY") or os.environ.get(
        "SOAPBOXX_EDITORIAL_REGISTRY_PATH"
    )
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = _repo_root() / p
        out.append(p)
    out.append(_repo_root() / "config" / "editorial_profiles.json")
    return out


def _load_overlay_flat() -> Dict[str, str]:
    global _overlay_path_mtime, _overlay_flat
    for path in _candidate_paths():
        try:
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
            sig = (str(path.resolve()), mtime)
            if _overlay_path_mtime == sig:
                return _overlay_flat
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "shows" in data and isinstance(data["shows"], dict):
                raw = data["shows"]
            elif isinstance(data, dict):
                raw = data
            else:
                raw = {}
            out: Dict[str, str] = {}
            for k, v in raw.items():
                kk = str(k).strip().lower()
                vv = str(v).strip().lower()
                if kk and vv:
                    out[kk] = vv
            _overlay_path_mtime = sig
            _overlay_flat = out
            return _overlay_flat
        except (OSError, json.JSONDecodeError):
            continue
    _overlay_path_mtime = None
    _overlay_flat = {}
    return {}


def clear_editorial_registry_cache() -> None:
    """Tests: reset overlay cache after swapping files or env."""
    global _overlay_path_mtime, _overlay_flat
    _overlay_path_mtime = None
    _overlay_flat = {}


def get_merged_registry() -> Dict[str, str]:
    """Built-in profiles plus JSON overlay (overlay wins on key collision)."""
    merged = dict(DEFAULT_EDITORIAL_PROFILES)
    merged.update(_load_overlay_flat())
    return merged


def registry_profile_for_meta(meta: Dict[str, Any], merged: Optional[Dict[str, str]] = None) -> Optional[str]:
    """
    First registry hit wins. Tries ``podcast_id``, ``podcast_slug``, ``show_id``,
    ``show_slug``, ``editorial_show_key``, ``show_format``, ``episode_format``.
    """
    m = merged if merged is not None else get_merged_registry()
    for field in _META_KEYS_IN_ORDER:
        raw = meta.get(field)
        if raw is None or raw == "":
            continue
        k = str(raw).strip().lower()
        hit = m.get(k)
        if hit:
            return hit
    return None
