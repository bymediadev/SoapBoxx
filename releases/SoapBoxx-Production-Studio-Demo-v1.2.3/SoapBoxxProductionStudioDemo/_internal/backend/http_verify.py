"""TLS verification defaults for outbound HTTP (requests).

On some Windows/Python bundles the OS trust store is incomplete, which yields
``SSLCertVerificationError``. Using certifi's Mozilla CA bundle fixes most cases.
"""

from __future__ import annotations

import os
from typing import Union

VerifyArg = Union[bool, str]


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
