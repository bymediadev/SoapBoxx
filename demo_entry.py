"""
PyInstaller entry point for the Production Studio Demo build.

Using a small launcher keeps `frontend.*` / `backend.*` imports working when frozen.
"""

from __future__ import annotations

import sys


def _bootstrap() -> None:
    try:
        from backend.runtime_paths import configure_frozen_runtime

        configure_frozen_runtime()
    except Exception as exc:
        print(f"SoapBoxx demo bootstrap warning: {exc}", file=sys.stderr)


if __name__ == "__main__":
    _bootstrap()
    from frontend.main_window import main

    main()
