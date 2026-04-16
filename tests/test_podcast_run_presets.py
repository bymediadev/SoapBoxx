"""Tests for scripts/podcast_run_presets.py (env overlays for long podcast runs)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from podcast_run_presets import PRESETS, apply_preset, describe_preset, list_preset_names  # noqa: E402


def test_list_presets_nonempty():
    assert "full" in list_preset_names()
    assert "smoke" in list_preset_names()


def test_apply_full_overrides_base():
    base = {"SOAPBOXX_OLLAMA_HTTP_TIMEOUT": "60", "OTHER": "x"}
    out = apply_preset(base, "full")
    assert out["OTHER"] == "x"
    assert out["SOAPBOXX_OLLAMA_HTTP_TIMEOUT"] == PRESETS["full"]["SOAPBOXX_OLLAMA_HTTP_TIMEOUT"]
    assert out["SOAPBOXX_OLLAMA_HEARTBEAT"] == "1"


def test_apply_none_is_noop():
    assert apply_preset({"A": "1"}, "none") == {"A": "1"}
    assert apply_preset({"A": "1"}, "") == {"A": "1"}


def test_apply_unknown_raises():
    with pytest.raises(ValueError, match="Unknown preset"):
        apply_preset({}, "nope")


def test_describe_includes_keys():
    text = describe_preset("smoke")
    assert "SOAPBOXX_OLLAMA_HEARTBEAT" in text
