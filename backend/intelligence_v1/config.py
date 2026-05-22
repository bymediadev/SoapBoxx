"""Paths and env for intelligence_v1 (Phase 1 measurement loop)."""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_root() -> Path:
    return _REPO_ROOT


def default_db_path() -> Path:
    raw = (os.getenv("SOAPBOXX_INTELLIGENCE_DB") or "").strip()
    if raw:
        return Path(raw)
    data_dir = _REPO_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "soapboxx.db"


def metric_prompt_path() -> Path:
    return _REPO_ROOT / "prompts" / "metric_extraction_prompt.txt"


def coaching_prompt_path() -> Path:
    return _REPO_ROOT / "prompts" / "coaching_prompt.txt"


def metrics_schema_path() -> Path:
    return _REPO_ROOT / "schemas" / "episode_metrics_schema.json"
