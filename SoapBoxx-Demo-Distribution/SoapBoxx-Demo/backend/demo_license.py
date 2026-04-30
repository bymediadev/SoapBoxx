#!/usr/bin/env python3
"""
Simple demo license gate for SoapBoxx-Demo.

Token format:
    sbx1.<base64url(payload_json)><.><hex_hmac_sha256>

Payload fields:
    - product: "soapboxx-demo"
    - iat: unix seconds
    - exp: unix seconds
    - email: optional
    - device_id: optional (if set, token is bound to one machine)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import platform
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

DEMO_PRODUCT = "soapboxx-demo"
DEMO_TOKEN_PREFIX = "sbx1"
# Keep this overridable for internal builds; do not ship private production keys.
DEFAULT_SIGNING_SECRET = "soapboxx-demo-license-v1-change-me"


def _utc_now_ts() -> int:
    return int(time.time())


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _canonical_json(data: Dict[str, Any]) -> bytes:
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _machine_fingerprint() -> str:
    blob = "|".join(
        [
            socket.gethostname(),
            platform.system(),
            platform.machine(),
            os.environ.get("USERNAME", "") or os.environ.get("USER", ""),
        ]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _sign_payload(payload_b64: str, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256)
    return mac.hexdigest()


def issue_demo_token(
    *,
    secret: str,
    email: str = "",
    days: int = 14,
    device_id: str = "",
    now_ts: Optional[int] = None,
) -> str:
    ts = int(now_ts or _utc_now_ts())
    payload = {
        "product": DEMO_PRODUCT,
        "iat": ts,
        "exp": ts + max(1, int(days)) * 86400,
        "email": (email or "").strip().lower(),
        "device_id": (device_id or "").strip(),
    }
    payload_b64 = _b64u_encode(_canonical_json(payload))
    sig = _sign_payload(payload_b64, secret)
    return f"{DEMO_TOKEN_PREFIX}.{payload_b64}.{sig}"


@dataclass
class LicenseCheck:
    ok: bool
    status: str
    message: str
    payload: Optional[Dict[str, Any]] = None
    days_left: int = 0


class DemoLicenseGate:
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.license_file = self.project_root / ".soapboxx_demo_license.json"
        self.runtime_file = self.project_root / ".soapboxx_demo_runtime.json"
        self.secret = (
            os.getenv("SOAPBOXX_DEMO_LICENSE_SECRET", "").strip()
            or DEFAULT_SIGNING_SECRET
        )

    def _load_license_token(self) -> str:
        try:
            if self.license_file.is_file():
                with open(self.license_file, "r", encoding="utf-8") as f:
                    blob = json.load(f)
                if isinstance(blob, dict):
                    return str(blob.get("token") or "").strip()
        except Exception:
            pass
        return ""

    def _save_license_token(self, token: str) -> None:
        obj = {"token": token.strip()}
        with open(self.license_file, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)

    def _load_runtime_state(self) -> Dict[str, Any]:
        try:
            if self.runtime_file.is_file():
                with open(self.runtime_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, dict):
                    return d
        except Exception:
            pass
        return {}

    def _save_runtime_state(self, state: Dict[str, Any]) -> None:
        with open(self.runtime_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    def activate_token(self, token: str) -> LicenseCheck:
        check = self.validate_token(token)
        if check.ok:
            self._save_license_token(token.strip())
        return check

    def validate_current(self) -> LicenseCheck:
        if (os.getenv("SOAPBOXX_DEV_PLAYGROUND", "").strip().lower()) in (
            "1",
            "true",
            "yes",
        ):
            return LicenseCheck(True, "dev_bypass", "Developer playground mode is enabled.")
        token = self._load_license_token()
        if not token:
            return LicenseCheck(
                False,
                "missing",
                "No demo license found. Enter an activation token to start your 14-day demo.",
            )
        return self.validate_token(token)

    def validate_token(self, token: str) -> LicenseCheck:
        token = (token or "").strip()
        try:
            pfx, payload_b64, sig = token.split(".", 2)
        except ValueError:
            return LicenseCheck(False, "invalid", "License token format is invalid.")
        if pfx != DEMO_TOKEN_PREFIX:
            return LicenseCheck(False, "invalid", "Unsupported license token prefix.")
        expected_sig = _sign_payload(payload_b64, self.secret)
        if not hmac.compare_digest(expected_sig, sig):
            return LicenseCheck(False, "invalid", "License signature is invalid.")
        try:
            payload = json.loads(_b64u_decode(payload_b64).decode("utf-8"))
        except Exception:
            return LicenseCheck(False, "invalid", "License payload could not be decoded.")
        if not isinstance(payload, dict):
            return LicenseCheck(False, "invalid", "License payload is invalid.")
        if str(payload.get("product") or "").strip() != DEMO_PRODUCT:
            return LicenseCheck(False, "invalid", "License product does not match this demo.")
        now_ts = _utc_now_ts()
        exp = int(payload.get("exp") or 0)
        iat = int(payload.get("iat") or 0)
        if exp <= 0 or iat <= 0 or exp <= iat:
            return LicenseCheck(False, "invalid", "License timestamps are invalid.")
        if now_ts > exp:
            return LicenseCheck(False, "expired", "Your 14-day demo license has expired.", payload=payload)
        did = str(payload.get("device_id") or "").strip()
        if did and did != _machine_fingerprint():
            return LicenseCheck(
                False,
                "invalid",
                "This license is bound to a different machine.",
                payload=payload,
            )
        # Simple clock rollback guard.
        st = self._load_runtime_state()
        last_seen = int(st.get("last_seen_ts") or 0)
        if last_seen and now_ts < (last_seen - 12 * 3600):
            return LicenseCheck(
                False,
                "clock_rollback",
                "System clock appears to have moved backwards. Please restore correct time.",
                payload=payload,
            )
        st["last_seen_ts"] = now_ts
        self._save_runtime_state(st)
        days_left = max(0, int((exp - now_ts + 86399) // 86400))
        return LicenseCheck(
            True,
            "ok",
            f"Demo license valid. {days_left} day(s) remaining.",
            payload=payload,
            days_left=days_left,
        )
