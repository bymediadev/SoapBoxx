#!/usr/bin/env python3
"""
Run before SoapBoxx-Local-Workflow or any long pipeline:

1. ``verify_soapboxx_backend`` — correct ``backend/`` on ``sys.path`` (no stale vendored copy).
2. Fast pytest slice — envelope coercion, claim filters (incl. causal gate), brief normalize, caption strip.
3. Optional ``--ollama-ping`` — confirms Ollama HTTP is reachable (no model inference).

Examples:

  python scripts/preflight_soapboxx.py
  python scripts/preflight_soapboxx.py --repo D:/Work/SoapBoxx --ollama-ping
  python scripts/preflight_soapboxx.py --no-tests

Exit code 0 = ready to run workflows; non-zero = fix paths, deps, or Ollama first.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.error
import urllib.request


def _repo_root(cli_repo: str | None) -> str:
    if cli_repo:
        return os.path.abspath(cli_repo)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, ".."))


def _quality_env_summary() -> str:
    """Effective defaults match backend docs when vars are unset."""
    rows = [
        ("SOAPBOXX_CLAIM_FILTER_V2", "1", "claim_filter_v2 on brief claims"),
        ("SOAPBOXX_CLAIM_REQUIRE_CAUSAL", "1", "require causal/mechanism wording"),
        ("SOAPBOXX_CLAIM_QUALITY_GATE", "on", "substrate check before SGV (off if 0/false)"),
        ("SOAPBOXX_BRIEF_TRANSCRIPT_GUARDRAILS", "1", "brief transcript anchoring"),
    ]
    lines = ["Quality-related env (unset = default shown):"]
    for key, default, note in rows:
        raw = os.environ.get(key)
        if raw is None or str(raw).strip() == "":
            disp = f"{default} (default)"
        else:
            disp = str(raw).strip()
        lines.append(f"  {key}={disp}  # {note}")
    return "\n".join(lines)


def _ollama_ping(host: str) -> tuple[bool, str]:
    base = host.rstrip("/")
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=5) as r:
            body = r.read()
        return True, f"Ollama OK at {base} ({len(body)} bytes /api/tags)"
    except urllib.error.URLError as e:
        return False, f"Ollama not reachable at {base}: {e}"
    except Exception as e:  # pragma: no cover
        return False, f"Ollama ping failed: {e}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--repo",
        default=None,
        help="SoapBoxx repo root (directory containing backend/ and scripts/).",
    )
    p.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip pytest (only verify backend paths).",
    )
    p.add_argument(
        "--ollama-ping",
        action="store_true",
        help="GET /api/tags on OLLAMA_HOST (default http://127.0.0.1:11434).",
    )
    args = p.parse_args()
    root = _repo_root(args.repo)
    os.chdir(root)

    verify = subprocess.run(
        [sys.executable, os.path.join(root, "scripts", "verify_soapboxx_backend.py"), "--repo", root],
        cwd=root,
    )
    if verify.returncode != 0:
        return verify.returncode

    if not args.no_tests:
        tests = [
            "tests/test_verify_soapboxx_backend.py",
            "tests/test_episode_intelligence.py",
            "tests/test_claim_filter_v2.py",
            "tests/test_causal_claim.py",
            "tests/test_transcript_structure_extract.py",
        ]
        pr = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=line", *tests],
            cwd=root,
        )
        if pr.returncode != 0:
            return pr.returncode

    print(_quality_env_summary(), flush=True)

    if args.ollama_ping:
        host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        ok, msg = _ollama_ping(host)
        print(msg)
        if not ok:
            return 1

    print("preflight_soapboxx: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
