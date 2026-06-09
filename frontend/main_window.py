#!/usr/bin/env python3
"""SoapBoxx — Insights Library desktop entry."""

from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

try:
    from dotenv import load_dotenv

    load_dotenv(_repo_root / ".env")
except ImportError:
    pass


def main() -> None:
    from frontend.library_window import run_library_offline_app

    print("Starting SoapBoxx Insights Library...")
    run_library_offline_app()


if __name__ == "__main__":
    main()
