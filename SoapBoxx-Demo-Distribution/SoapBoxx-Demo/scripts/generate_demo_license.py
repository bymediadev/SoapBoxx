#!/usr/bin/env python3
"""
Generate a signed SoapBoxx-Demo activation token (default 14 days).

Usage:
  python scripts/generate_demo_license.py --email tester@example.com --days 14
  python scripts/generate_demo_license.py --email tester@example.com --bind-this-machine --write-file
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from backend.demo_license import (  # noqa: E402
    DEFAULT_SIGNING_SECRET,
    _machine_fingerprint,
    issue_demo_token,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--email", default="", help="Tester email (embedded in payload).")
    p.add_argument("--days", type=int, default=14, help="Validity period in days (default: 14).")
    p.add_argument(
        "--device-id",
        default="",
        help="Optional explicit device_id. If set, token only works on that machine id.",
    )
    p.add_argument(
        "--bind-this-machine",
        action="store_true",
        help="Bind token to this machine fingerprint.",
    )
    p.add_argument(
        "--write-file",
        action="store_true",
        help="Write .soapboxx_demo_license.json in current SoapBoxx-Demo folder.",
    )
    args = p.parse_args()

    secret = (
        os.getenv("SOAPBOXX_DEMO_LICENSE_SECRET", "").strip()
        or DEFAULT_SIGNING_SECRET
    )
    did = (args.device_id or "").strip()
    if args.bind_this_machine and not did:
        did = _machine_fingerprint()

    token = issue_demo_token(
        secret=secret,
        email=args.email.strip().lower(),
        days=max(1, int(args.days)),
        device_id=did,
    )

    print("\nSoapBoxx Demo activation token\n")
    print(token)
    print("\nShare this token with tester.")
    if did:
        print(f"Bound device_id: {did}")

    if args.write_file:
        out = PROJECT_ROOT / ".soapboxx_demo_license.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f, indent=2)
        print(f"\nWrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
