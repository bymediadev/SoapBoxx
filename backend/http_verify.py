"""TLS verification defaults for outbound HTTP (requests / httpx).

On some Windows/Python bundles the bundled CA store rejects valid chains
(corporate TLS interception, stale certifi). Preference order:
OS trust store via ``truststore`` → certifi bundle → system default.
"""

from __future__ import annotations

import os
from typing import Optional, Union

VerifyArg = Union[bool, str]

_TRUSTSTORE_INJECTED: Optional[bool] = None


def maybe_inject_truststore() -> bool:
    """
    Route Python TLS through the OS trust store (Windows/macOS) when the
    optional ``truststore`` package is installed. Idempotent.
    Disable with ``SOAPBOXX_SSL_TRUSTSTORE=0``.
    """
    global _TRUSTSTORE_INJECTED
    if _TRUSTSTORE_INJECTED is not None:
        return _TRUSTSTORE_INJECTED
    raw = (os.getenv("SOAPBOXX_SSL_TRUSTSTORE") or "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        _TRUSTSTORE_INJECTED = False
        return False
    try:
        import truststore

        truststore.inject_into_ssl()
        _TRUSTSTORE_INJECTED = True
    except ImportError:
        _TRUSTSTORE_INJECTED = False
    return _TRUSTSTORE_INJECTED


def httpx_verify_arg() -> VerifyArg:
    """``verify=`` value for httpx clients."""
    raw = (os.getenv("SOAPBOXX_SSL_VERIFY") or "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if maybe_inject_truststore():
        # Default SSL context is now backed by the OS trust store.
        return True
    try:
        import certifi

        return certifi.where()
    except ImportError:
        return True


def requests_verify_arg() -> VerifyArg:
    """Return the ``verify=`` value for ``requests`` / ``urllib3``.

    - If ``SOAPBOXX_SSL_VERIFY`` is ``0`` / ``false`` / ``no`` / ``off``, verification is disabled
      (insecure; debugging or broken corporate TLS interception only).
    - Otherwise, if **certifi** is installed, use ``certifi.where()`` so TLS uses a known-good bundle.
    - If **certifi** is missing, fall back to ``True`` (system default).
    """
    raw = (os.getenv("SOAPBOXX_SSL_VERIFY") or "1").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    try:
        import certifi

        return certifi.where()
    except ImportError:
        return True
