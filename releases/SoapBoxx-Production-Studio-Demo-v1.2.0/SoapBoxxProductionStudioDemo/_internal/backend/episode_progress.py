"""
Episode-to-episode progress: lightweight telemetry (no dashboards, no ML).

- Stamps ``export_telemetry`` on successful strategist exports (thesis fingerprint hash, action
  fingerprint, show key, episode id).
- When a prior snapshot exists, sets ``metadata.progress_summary`` to three rule-based strings
  (same lines as the *Progress Since Last Episode* markdown block).
- When ``SOAPBOXX_EPISODE_PROGRESS`` is on (default off), persists one snapshot per show key and
  injects *Progress Since Last Episode* into the next export.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

_STATE_VERSION = 1

# Thesis text similarity (SequenceMatcher on normalized strings). Tuned for short thesis lines.
_THESIS_SIM_STABLE = 0.88
_THESIS_SIM_PARTIAL = 0.52


def default_progress_state_path() -> str:
    custom = (os.getenv("SOAPBOXX_EPISODE_PROGRESS_STATE") or "").strip()
    if custom:
        return custom
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "SoapBoxx", "episode_progress_state.json")
    return os.path.join(os.path.expanduser("~"), ".soapboxx", "episode_progress_state.json")


def episode_progress_persistence_enabled() -> bool:
    """
    File-backed previous snapshot + *Progress Since Last Episode* markdown section.

    Opt-in (default off) so CI and one-off scripts do not write state under ``LOCALAPPDATA`` /
    ``~/.soapboxx``. Set ``SOAPBOXX_EPISODE_PROGRESS=1`` to enable the episode-to-episode loop.
    Metadata :func:`attach_export_telemetry_to_metadata` stamps do **not** require this flag.
    """
    v = (os.getenv("SOAPBOXX_EPISODE_PROGRESS") or "0").strip().lower()
    return v not in ("0", "false", "no", "off")


def _norm_text(s: str) -> str:
    t = (s or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def show_key_from_meta(meta: Dict[str, Any], r3: Dict[str, Any]) -> str:
    explicit = str(
        (meta or {}).get("show_key")
        or (meta or {}).get("series_key")
        or ""
    ).strip()
    if explicit:
        return explicit[:160]
    snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
    creator = str((meta or {}).get("creator") or snap.get("creator") or "").strip().lower()
    title = str((meta or {}).get("title") or snap.get("title") or "").strip().lower()
    raw = f"{creator}|{title}"
    if not raw.strip("|"):
        raw = "unknown_show"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def episode_id_from_meta(meta: Dict[str, Any], r3: Dict[str, Any]) -> str:
    m = meta or {}
    for k in ("episode_id", "youtube_id", "video_id", "source_id"):
        v = str(m.get(k) or "").strip()
        if v:
            return v[:240]
    snap = r3.get("episode_snapshot") if isinstance(r3.get("episode_snapshot"), dict) else {}
    title = str(m.get("title") or snap.get("title") or "untitled").strip()
    gen = str(m.get("generated") or m.get("generated_at") or "").strip()
    h = hashlib.sha256(f"{title}|{gen}".encode("utf-8")).hexdigest()[:14]
    return f"ep_{h}"


def generated_at_from_meta(meta: Dict[str, Any]) -> str:
    m = meta or {}
    g = str(m.get("generated") or m.get("generated_at") or "").strip()
    if g:
        return g
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _fingerprint_bullets(bullets: List[str]) -> str:
    body = "\n".join((b or "").strip() for b in bullets if (b or "").strip())
    if not body:
        return "fp_empty"
    h = hashlib.sha256(body.encode("utf-8")).hexdigest()[:20]
    return f"fp_{h}"


def _fingerprint_thesis(thesis: str) -> str:
    t = _norm_text(thesis)
    if not t:
        return "th_empty"
    h = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
    return f"th_{h}"


def _signal_rank(sm: str) -> int:
    u = (sm or "").upper()
    if "HIGH" in u:
        return 2
    if "MEDIUM" in u:
        return 1
    if "LOW" in u:
        return 0
    return -1


def extract_episode_snapshot(bundle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Serializable snapshot for compare + persist. None if export is not strategist-eligible."""
    try:
        from .episode_report_v3 import (
            _derive_strategist_report_from_bundle,
            bundle_grounded_evidence_counts,
            compressed_action_bullets,
            export_structural_tier,
            strategist_truth_gate_bundle,
        )
    except ImportError:
        from episode_report_v3 import (  # type: ignore
            _derive_strategist_report_from_bundle,
            bundle_grounded_evidence_counts,
            compressed_action_bullets,
            export_structural_tier,
            strategist_truth_gate_bundle,
        )

    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    md = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    if not md:
        md = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
    if md.get("export_status") in ("insufficient_signal", "degraded"):
        return None
    abort, _ = strategist_truth_gate_bundle(bundle)
    if abort:
        return None
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    try:
        sr = _derive_strategist_report_from_bundle(bundle)
    except ValueError:
        return None
    core = sr.get("core_breakdown") if isinstance(sr.get("core_breakdown"), dict) else {}
    thesis = str(core.get("thesis") or "").strip()
    tier = export_structural_tier(bundle)
    if tier == "compressed":
        bullets = compressed_action_bullets(bundle, sr)
    else:
        olf = str(sr.get("one_line_fix") or "").strip()
        cp = str(sr.get("core_problem") or "").strip()
        bullets = [x for x in (cp, olf) if x][:2]
    n_ev, _, _ = bundle_grounded_evidence_counts(bundle)
    n_seg = max(
        len(wf.get("segments") or []),
        len(r3.get("segments") or []),
    )
    sm = str(r3.get("signal_mode") or "").strip()
    meta = md
    eid = episode_id_from_meta(meta, r3)
    gen_at = generated_at_from_meta(meta)
    sk = show_key_from_meta(meta, r3)
    return {
        "version": _STATE_VERSION,
        "episode_id": eid,
        "generated_at": gen_at,
        "show_key": sk,
        "thesis": thesis,
        "thesis_fingerprint": _fingerprint_thesis(thesis),
        "core_problem": str(sr.get("core_problem") or "").strip(),
        "signal_mode": sm,
        "segment_count": int(n_seg),
        "grounded_evidence_count": int(n_ev),
        "export_structural_tier": tier,
        "action_fingerprint": _fingerprint_bullets(bullets),
    }


def build_export_telemetry_dict(bundle: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Metadata stamp for successful strategist exports; None when withheld."""
    snap = extract_episode_snapshot(bundle)
    if not snap:
        return None
    out = {
        "episode_id": snap["episode_id"],
        "generated_at": snap["generated_at"],
        "show_key": snap["show_key"],
        "thesis_fingerprint": snap["thesis_fingerprint"],
        "action_fingerprint": snap["action_fingerprint"],
    }
    prev = bundle.get("previous_episode_snapshot")
    if isinstance(prev, dict) and prev.get("episode_id"):
        out["previous_episode_id"] = str(prev.get("episode_id"))
    return out


def attach_export_telemetry_to_metadata(meta: Dict[str, Any], bundle: Dict[str, Any]) -> None:
    if not isinstance(meta, dict):
        return
    prev = bundle.get("previous_episode_snapshot")
    if isinstance(prev, dict) and prev.get("generated_at"):
        curr = extract_episode_snapshot(bundle)
        if curr:
            meta["progress_summary"] = compute_progress_delta_lines(prev, curr)
        else:
            meta.pop("progress_summary", None)
    else:
        meta.pop("progress_summary", None)

    telem = build_export_telemetry_dict(bundle)
    if telem:
        meta["export_telemetry"] = telem


def compute_progress_delta_lines(prev: Dict[str, Any], curr: Dict[str, Any]) -> List[str]:
    """
    Exactly three rule-based comparison lines (no LLM): thesis framing, evidence density,
    classifier tier. Wording is directional but honest — low thesis similarity yields a neutral
    caveat instead of implying regression.
    """
    tp = _norm_text(str(prev.get("thesis") or ""))
    tc = _norm_text(str(curr.get("thesis") or ""))
    if tp and tc:
        ratio = SequenceMatcher(None, tp, tc).ratio()
        if ratio >= _THESIS_SIM_STABLE:
            thesis_line = (
                "Argument clarity: stable — thesis framing aligns with last episode (clearer positioning)."
            )
        elif ratio >= _THESIS_SIM_PARTIAL:
            thesis_line = (
                "Argument focus: shifted — partial overlap with last episode "
                "(possible improvement or drift; judge against your intent)."
            )
        else:
            thesis_line = (
                "Thesis direction changed — evaluate whether positioning is stronger or weaker "
                "than last episode (low text similarity is not a quality score)."
            )
    else:
        thesis_line = "Argument clarity: comparison limited (missing thesis text on prior or current run)."

    ev_p = int(prev.get("grounded_evidence_count") or 0)
    ev_c = int(curr.get("grounded_evidence_count") or 0)
    if ev_c > ev_p:
        ev_line = "Evidence usage: stronger support (more grounded rows than last episode)."
    elif ev_c < ev_p:
        ev_line = "Evidence usage: weaker grounding (fewer grounded rows than last episode)."
    else:
        ev_line = "Evidence usage: unchanged vs last episode."

    rp = _signal_rank(str(prev.get("signal_mode") or ""))
    rc = _signal_rank(str(curr.get("signal_mode") or ""))
    if rp >= 0 and rc >= 0:
        if rc > rp:
            sig_line = "Overall signal: strengthened (classifier tier up vs last episode)."
        elif rc < rp:
            sig_line = "Overall signal: lower tier than last episode (classifier)."
        else:
            sig_line = "Overall signal: unchanged vs last episode."
    else:
        sig_line = "Overall signal: comparison limited (missing prior or current classifier label)."

    return [thesis_line, ev_line, sig_line]


def format_progress_markdown_lines(bundle: Dict[str, Any]) -> List[str]:
    if not episode_progress_persistence_enabled():
        return []
    prev = bundle.get("previous_episode_snapshot")
    if not isinstance(prev, dict) or not prev.get("generated_at"):
        return []
    curr = extract_episode_snapshot(bundle)
    if not curr:
        return []
    lines = compute_progress_delta_lines(prev, curr)
    if not lines:
        return []
    out = ["", "## Progress Since Last Episode", ""]
    for ln in lines:
        out.append(f"- {ln}")
    return out


def _read_state(path: str) -> Dict[str, Any]:
    if not path or not os.path.isfile(path):
        return {"version": _STATE_VERSION, "shows": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"version": _STATE_VERSION, "shows": {}}
        if not isinstance(data.get("shows"), dict):
            data["shows"] = {}
        return data
    except (OSError, json.JSONDecodeError):
        return {"version": _STATE_VERSION, "shows": {}}


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    dname = os.path.dirname(path)
    if dname:
        os.makedirs(dname, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="sbprog_", suffix=".json", dir=dname or None)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_previous_snapshot(show_key: str) -> Optional[Dict[str, Any]]:
    if not episode_progress_persistence_enabled():
        return None
    path = default_progress_state_path()
    data = _read_state(path)
    shows = data.get("shows") or {}
    prev = shows.get(show_key)
    return prev if isinstance(prev, dict) else None


def save_snapshot_for_show(show_key: str, snapshot: Dict[str, Any]) -> None:
    if not episode_progress_persistence_enabled():
        return
    path = default_progress_state_path()
    data = _read_state(path)
    shows = dict(data.get("shows") or {})
    shows[show_key] = snapshot
    data["shows"] = shows
    data["version"] = _STATE_VERSION
    _atomic_write_json(path, data)


def prepare_bundle_for_export(bundle: Dict[str, Any]) -> None:
    """Attach ``previous_episode_snapshot`` when persistence is enabled and the show has history."""
    bundle.pop("previous_episode_snapshot", None)
    if not episode_progress_persistence_enabled():
        return
    wf = bundle.get("workflow_report") if isinstance(bundle.get("workflow_report"), dict) else {}
    md = wf.get("metadata") if isinstance(wf.get("metadata"), dict) else {}
    r3 = bundle.get("report_v3") if isinstance(bundle.get("report_v3"), dict) else {}
    if md.get("export_status") in ("insufficient_signal", "degraded"):
        return
    if not md:
        md = bundle.get("meta") if isinstance(bundle.get("meta"), dict) else {}
        if md.get("export_status") in ("insufficient_signal", "degraded"):
            return
    meta = md
    sk = show_key_from_meta(meta, r3)
    prev = load_previous_snapshot(sk)
    if prev:
        bundle["previous_episode_snapshot"] = prev


def persist_episode_progress_after_export(bundle: Dict[str, Any]) -> None:
    """Call after markdown export so fingerprints match what the user sees."""
    if not episode_progress_persistence_enabled():
        return
    snap = extract_episode_snapshot(bundle)
    if not snap:
        return
    save_snapshot_for_show(str(snap["show_key"]), snap)


__all__ = [
    "attach_export_telemetry_to_metadata",
    "build_export_telemetry_dict",
    "compute_progress_delta_lines",
    "default_progress_state_path",
    "episode_id_from_meta",
    "episode_progress_persistence_enabled",
    "extract_episode_snapshot",
    "format_progress_markdown_lines",
    "load_previous_snapshot",
    "persist_episode_progress_after_export",
    "prepare_bundle_for_export",
    "save_snapshot_for_show",
    "show_key_from_meta",
]
