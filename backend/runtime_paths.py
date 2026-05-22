"""
Resolve filesystem roots for dev runs and PyInstaller bundles.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_root() -> Path:
    """PyInstaller _MEIPASS or source tree root."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


def app_root() -> Path:
    """Writable folder beside the bundle (.exe dir or folder containing .app) or repo root."""
    if is_frozen():
        exe = Path(sys.executable).resolve()
        # PyInstaller macOS: .../SoapBoxxProductionStudioDemo.app/Contents/MacOS/<binary>
        parts = exe.parts
        if sys.platform == "darwin" and len(parts) >= 4 and parts[-3] == "Contents" and parts[-2] == "MacOS":
            return Path(*parts[:-4])
        return exe.parent
    return Path(__file__).resolve().parent.parent


def configure_frozen_runtime() -> Path:
    """
    Set cwd and sys.path so `frontend.*` / `backend.*` imports work in the demo exe.
    Returns app_root.
    """
    root = app_root()
    try:
        os.chdir(root)
    except OSError:
        pass

    bundle = bundle_root()
    for entry in (bundle, bundle / "frontend", bundle / "backend"):
        p = str(entry)
        if entry.is_dir() and p not in sys.path:
            sys.path.insert(0, p)

    # Load .env next to the exe / repo root
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env")
    except Exception:
        pass

    if not (os.getenv("SOAPBOXX_CONFIG_FILE") or "").strip():
        demo_cfg = root / "soapboxx_config.demo.json"
        if demo_cfg.is_file() and (os.getenv("SOAPBOXX_BUCKET") or "").strip().lower() in {
            "demo",
            "dev",
            "development",
            "sandbox",
        }:
            os.environ.setdefault("SOAPBOXX_CONFIG_FILE", str(demo_cfg))

    return root
