#!/usr/bin/env python3
"""
Fail fast if ``backend.*`` resolves to a stale or shadow copy (common when a wrapper
repo vendors files or prepends a wrong ``sys.path``).

Run from any cwd:

  python scripts/verify_soapboxx_backend.py

Or with an explicit repo root (the directory that contains ``backend/`` and ``scripts/``):

  python path/to/SoapBoxx/scripts/verify_soapboxx_backend.py --repo C:\\path\\to\\SoapBoxx

Exit code 0 = modules under this repo and expected API surface is present; 1 = mismatch.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple


def _repo_root(cli_repo: str | None) -> str:
    if cli_repo:
        return os.path.abspath(cli_repo)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _norm_prefix(path: str) -> str:
    return os.path.normcase(os.path.abspath(path) + os.sep)


def verify(*, repo_root: str) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    backend_dir = os.path.join(repo_root, "backend")
    expected = _norm_prefix(backend_dir)

    if not os.path.isdir(backend_dir):
        errors.append(f"Missing backend directory: {backend_dir}")
        return False, errors

    # Import only after repo is on path (same order as CI / apps should use).
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    try:
        import backend.episode_intelligence as ei  # noqa: E402
        import backend.episode_report_v3 as er3  # noqa: E402
        import backend.soapboxx_v3_workflow as wf  # noqa: E402
        import backend.strict_episode_contract as sec  # noqa: E402
        import backend.transcript_structure_extract as tse  # noqa: E402
    except ImportError as e:
        errors.append(f"Import failed: {e}")
        return False, errors

    for label, mod in (
        ("episode_intelligence", ei),
        ("episode_report_v3", er3),
        ("soapboxx_v3_workflow", wf),
        ("strict_episode_contract", sec),
        ("transcript_structure_extract", tse),
    ):
        fp = getattr(mod, "__file__", None)
        if not fp or not isinstance(fp, str):
            errors.append(f"{label}: missing __file__")
            continue
        if not os.path.normcase(os.path.abspath(fp)).startswith(expected):
            errors.append(
                f"{label}: resolved to {fp!r} — not under this repo's backend/ ({expected}). "
                "Fix PYTHONPATH / sys.path so only one SoapBoxx backend is visible."
            )

    # Expected API markers (catch half-updated vendored copies).
    if not hasattr(ei, "_llm_envelope_text_fallback_enabled"):
        errors.append(
            "episode_intelligence: missing _llm_envelope_text_fallback_enabled — "
            "file is older than this repo; sync backend/episode_intelligence.py."
        )
    if not hasattr(ei, "_coerce_brief_data_shape"):
        errors.append(
            "episode_intelligence: missing _coerce_brief_data_shape — "
            "file is older than this repo; sync backend/episode_intelligence.py (brief envelope coercion)."
        )
    if not hasattr(ei, "_try_lift_stringified_brief_single_key"):
        errors.append(
            "episode_intelligence: missing _try_lift_stringified_brief_single_key — "
            "file is older than this repo; sync backend/episode_intelligence.py (camelCase / stringified brief envelopes)."
        )
    if not hasattr(ei, "_brief_llm_envelope"):
        errors.append(
            "episode_intelligence: missing _brief_llm_envelope — "
            "file is older than this repo; sync backend/episode_intelligence.py (brief Ollama retries)."
        )
    if not hasattr(ei, "_strict_contract_brief_enabled"):
        errors.append(
            "episode_intelligence: missing _strict_contract_brief_enabled — "
            "sync backend/episode_intelligence.py (strict JSON brief path)."
        )
    if not hasattr(ei, "_spine_first_brief_enabled"):
        errors.append(
            "episode_intelligence: missing _spine_first_brief_enabled — "
            "sync backend/episode_intelligence.py (spine-first brief path)."
        )
    if not hasattr(ei, "_spine_refiner_llm_enabled"):
        errors.append(
            "episode_intelligence: missing _spine_refiner_llm_enabled — "
            "sync backend/episode_intelligence.py (spine refiner pass)."
        )
    try:
        import backend.intelligence_ship_gate as isg  # noqa: E402
    except ImportError as e:
        errors.append(
            "intelligence_ship_gate: import failed (sync repo / backend/): "
            f"{e} — if the file is present, also sync backend/soapboxx_intelligence_core.py and "
            "backend/semantic_alignment.py (and config/ship_gate.json when used)."
        )
    else:
        if not hasattr(isg, "assess_brief_intelligence_ship"):
            errors.append("intelligence_ship_gate: missing assess_brief_intelligence_ship.")
    if not hasattr(sec, "validate_strict_episode_contract"):
        errors.append(
            "strict_episode_contract: missing validate_strict_episode_contract — "
            "sync backend/strict_episode_contract.py."
        )
    if not hasattr(wf, "_prune_follow_up_questions_to_evidence_map"):
        errors.append(
            "soapboxx_v3_workflow: missing _prune_follow_up_questions_to_evidence_map — "
            "file is older than this repo; sync backend/soapboxx_v3_workflow.py."
        )
    if not hasattr(tse, "strip_youtube_caption_metadata"):
        errors.append(
            "transcript_structure_extract: missing strip_youtube_caption_metadata — "
            "sync backend/transcript_structure_extract.py (caption junk stripping)."
        )
    if not hasattr(er3, "_merge_strategist_blueprint_with_derived"):
        errors.append(
            "episode_report_v3: missing _merge_strategist_blueprint_with_derived — "
            "sync backend/episode_report_v3.py (strategist + blueprint merge)."
        )

    return not errors, errors


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo",
        default=None,
        help="SoapBoxx repo root (folder containing backend/). Default: parent of scripts/.",
    )
    args = p.parse_args()
    root = _repo_root(args.repo)
    ok, errs = verify(repo_root=root)
    print(f"SOAPBOXX_REPO_ROOT={root}")
    if ok:
        print("verify_soapboxx_backend: OK (backend modules align with this tree).")
        return 0
    print("verify_soapboxx_backend: FAILED", file=sys.stderr)
    for line in errs:
        print(f"  - {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
