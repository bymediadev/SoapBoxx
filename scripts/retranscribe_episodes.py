#!/usr/bin/env python3
"""Re-transcribe episodes on live API (sync force_retranscribe path)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = "https://soapboxx-production.up.railway.app"


def api_post(base: str, path: str, body: dict, *, timeout: int) -> dict:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "SoapBoxx-Retranscribe/1.0",
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def api_get(base: str, path: str, *, timeout: int = 90) -> dict:
    url = f"{base.rstrip('/')}{path}"
    req = Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "SoapBoxx-Retranscribe/1.0"},
        method="GET",
    )
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--episode-ids", default="1,2")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds per episode")
    args = parser.parse_args()

    episode_ids = [int(x.strip()) for x in args.episode_ids.split(",") if x.strip()]
    results = []

    for eid in episode_ids:
        print(f"\n=== Episode {eid}: force_retranscribe ===")
        before = api_get(args.api, f"/episodes/{eid}/features")
        print(
            f"Before: turns={before.get('speaking_turns')} "
            f"hook={before.get('hook_length_seconds')} "
            f"questions={before.get('question_count')}"
        )
        t0 = time.time()
        try:
            out = api_post(
                args.api,
                f"/episodes/{eid}/process",
                {"force_retranscribe": True},
                timeout=args.timeout,
            )
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            print(f"FAILED HTTP {exc.code}: {detail}")
            return 1
        elapsed = round(time.time() - t0, 1)
        print(f"Done in {elapsed}s")
        print(json.dumps(out, indent=2)[:3000])

        after = api_get(args.api, f"/episodes/{eid}/features")
        prod = api_get(args.api, f"/episodes/{eid}/report/producer")
        results.append(
            {
                "episode_id": eid,
                "elapsed_seconds": elapsed,
                "before": before,
                "after": after,
                "transcript_warning": prod.get("transcript_warning"),
                "template_id": prod.get("template_id"),
                "structure_label": prod.get("structure_label"),
                "limitations": prod.get("transcript_limitations"),
            }
        )
        print(
            f"After: turns={after.get('speaking_turns')} "
            f"hook={after.get('hook_length_seconds')} "
            f"template={prod.get('template_id')} "
            f"warning={(prod.get('transcript_warning') or {}).get('code')}"
        )

    out_path = ROOT / "reports" / "retranscribe_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
