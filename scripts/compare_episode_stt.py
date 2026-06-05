#!/usr/bin/env python3
"""Snapshot episode metrics before/after STT re-run on live API."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = "https://soapboxx-production.up.railway.app"


def request(base: str, method: str, path: str, body: dict | None = None, timeout: int = 120):
    url = f"{base.rstrip('/')}{path}"
    data = None
    headers = {"Accept": "application/json", "User-Agent": "SoapBoxx-STT-Compare/1.0"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def snapshot(base: str, episode_id: int) -> dict:
    return {
        "state": request(base, "GET", f"/episodes/{episode_id}/state"),
        "features": request(base, "GET", f"/episodes/{episode_id}/features"),
        "producer": request(base, "GET", f"/episodes/{episode_id}/report/producer"),
        "actions": request(base, "GET", f"/episodes/{episode_id}/report/actions"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--episode-id", type=int, default=1)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--max-polls", type=int, default=60)
    parser.add_argument("--skip-process", action="store_true")
    args = parser.parse_args()

    report_path = ROOT / "reports" / f"stt_compare_ep{args.episode_id}.json"

    print(f"API: {args.api}")
    print(f"Episode: {args.episode_id}")
    before = snapshot(args.api, args.episode_id)
    print("\n=== BEFORE ===")
    print(json.dumps(before, indent=2)[:4000])

    if not args.skip_process:
        print("\nDispatching POST /episodes/{id}/process force_retranscribe=true ...")
        try:
            proc = request(
                args.api,
                "POST",
                f"/episodes/{args.episode_id}/process",
                {"force_retranscribe": True},
                timeout=180,
            )
            print(json.dumps(proc, indent=2))
        except HTTPError as exc:
            print(f"Process failed: HTTP {exc.code} {exc.read().decode()[:500]}")
            return 1

        for i in range(args.max_polls):
            state = request(args.api, "GET", f"/episodes/{args.episode_id}/state")
            status = state.get("status")
            err = state.get("pipeline_error")
            print(f"poll {i + 1}: status={status!r} pipeline_error={err!r}")
            if status in ("ready", "failed") and status != "transcribing":
                break
            if status not in ("queued", "transcribing", "ingesting", "ingested"):
                break
            time.sleep(args.poll_seconds)

    after = snapshot(args.api, args.episode_id)
    print("\n=== AFTER ===")
    print(json.dumps(after, indent=2)[:4000])

    out = {
        "api": args.api,
        "episode_id": args.episode_id,
        "before": before,
        "after": after,
        "diff": {
            "transcript_warning_before": (before.get("producer") or {}).get("transcript_warning"),
            "transcript_warning_after": (after.get("producer") or {}).get("transcript_warning"),
            "speaking_turns_before": (before.get("features") or {}).get("speaking_turns"),
            "speaking_turns_after": (after.get("features") or {}).get("speaking_turns"),
            "host_guest_ratio_before": (before.get("features") or {}).get("host_guest_ratio"),
            "host_guest_ratio_after": (after.get("features") or {}).get("host_guest_ratio"),
            "status_before": (before.get("state") or {}).get("status"),
            "status_after": (after.get("state") or {}).get("status"),
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nWrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
