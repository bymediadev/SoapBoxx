"""Start the local FastAPI server for the offline Insights Library UI."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Optional, Tuple

_server_thread: Optional[threading.Thread] = None
_server_instance = None

DEFAULT_REMOTE_API = "https://soapboxx-production.up.railway.app"


def configured_library_api_base() -> Optional[str]:
    """Explicit API host for library data (``SOAPBOXX_LIBRARY_API_URL``)."""
    raw = (os.getenv("SOAPBOXX_LIBRARY_API_URL") or "").strip().rstrip("/")
    return raw or None


def api_base_url() -> str:
    host = (os.getenv("SOAPBOXX_API_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("SOAPBOXX_API_PORT") or os.getenv("PORT") or "8000")
    return f"http://{host}:{port}"


def library_ui_url(*, remote_base: Optional[str] = None) -> str:
    base = (remote_base or configured_library_api_base() or api_base_url()).rstrip("/")
    return f"{base}/ui/"


def should_start_local_api() -> bool:
    return configured_library_api_base() is None


def remote_fallback_enabled() -> bool:
    raw = (os.getenv("SOAPBOXX_LIBRARY_FALLBACK_REMOTE") or "1").strip().lower()
    return raw in ("1", "true", "yes", "on")


def remote_fallback_ui_url() -> str:
    return library_ui_url(remote_base=DEFAULT_REMOTE_API)


def _health_urls(base: str) -> Tuple[str, ...]:
    root = base.rstrip("/")
    return (f"{root}/health/live", f"{root}/health")


def wait_for_api(base: Optional[str] = None, *, timeout: float = 90.0) -> bool:
    root = (base or api_base_url()).rstrip("/")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for url in _health_urls(root):
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, TimeoutError, OSError):
                pass
        time.sleep(0.4)
    return False


def is_api_running(base: Optional[str] = None) -> bool:
    root = (base or api_base_url()).rstrip("/")
    for url in _health_urls(root):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return False


def local_library_ready(base: Optional[str] = None) -> bool:
    """True when API is live and Postgres is connected (library endpoints usable)."""
    root = (base or api_base_url()).rstrip("/")
    if not is_api_running(root):
        return False
    try:
        with urllib.request.urlopen(f"{root}/health", timeout=3) as resp:
            if resp.status != 200:
                return False
            payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("status") == "ok"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return False


def start_local_api(*, wait: bool = True, timeout: float = 90.0) -> bool:
    """
    Start uvicorn in a daemon thread unless the API is already reachable.
    Returns True when ``/health/live`` or ``/health`` responds.
    """
    if not should_start_local_api():
        base = configured_library_api_base() or ""
        return bool(base) and wait_for_api(base, timeout=min(timeout, 15.0))

    global _server_thread, _server_instance

    base = api_base_url()
    if is_api_running(base):
        return True

    if _server_thread is not None and _server_thread.is_alive():
        return wait_for_api(base, timeout=timeout) if wait else True

    host = (os.getenv("SOAPBOXX_API_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("SOAPBOXX_API_PORT") or os.getenv("PORT") or "8000")

    def _run() -> None:
        global _server_instance
        import uvicorn

        config = uvicorn.Config(
            "main:app",
            host=host,
            port=port,
            log_level=(os.getenv("SOAPBOXX_API_LOG_LEVEL") or "warning").strip(),
            access_log=False,
        )
        _server_instance = uvicorn.Server(config)
        _server_instance.run()

    _server_thread = threading.Thread(target=_run, name="soapboxx-local-api", daemon=True)
    _server_thread.start()

    if not wait:
        return True
    return wait_for_api(base, timeout=timeout)
