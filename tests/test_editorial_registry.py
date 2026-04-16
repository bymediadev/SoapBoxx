"""Per-show editorial registry merge and meta lookup."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from editorial_registry import (  # noqa: E402
    clear_editorial_registry_cache,
    get_merged_registry,
    registry_profile_for_meta,
)


def test_registry_profile_prefers_podcast_id_over_show_format():
    merged = {
        "pod-xyz": "solo",
        "daily": "balanced",
    }
    meta = {
        "podcast_id": "pod-xyz",
        "show_format": "daily",
    }
    assert registry_profile_for_meta(meta, merged) == "solo"


def test_json_overlay_merges_and_overrides_builtin(tmp_path, monkeypatch):
    clear_editorial_registry_cache()
    p = tmp_path / "reg.json"
    p.write_text(
        json.dumps({"shows": {"daily": "interview", "extra-show": "news"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SOAPBOXX_EDITORIAL_REGISTRY", str(p))
    clear_editorial_registry_cache()
    m = get_merged_registry()
    assert m["daily"] == "interview"
    assert m["extra-show"] == "news"
    assert m["case_fire"] == "narrative"
    monkeypatch.delenv("SOAPBOXX_EDITORIAL_REGISTRY", raising=False)
    clear_editorial_registry_cache()
