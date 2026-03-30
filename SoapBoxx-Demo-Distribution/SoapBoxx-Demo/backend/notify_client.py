#!/usr/bin/env python3
"""
Send admin notifications for beta events (signup, login, etc.).

Priority:
  1. NOTIFY_WEBHOOK_URL — POST JSON to your own server (e.g. FastAPI in server/)
  2. RESEND_API_KEY — Resend HTTP API
  3. SENDGRID_API_KEY — SendGrid v3 API
  4. SMTP_* — Gmail / any SMTP (e.g. Gmail app password)

Load secrets from .env in the SoapBoxx-Demo project root (see .env.example).
"""

from __future__ import annotations

import json
import os
import smtplib
import threading
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        env_path = _PROJECT_ROOT / ".env"
        if env_path.is_file():
            load_dotenv(env_path)
    except Exception:
        pass


def _load_beta_config() -> Dict[str, Any]:
    p = _PROJECT_ROOT / "beta_config.json"
    try:
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _admin_recipient() -> str:
    _load_dotenv()
    cfg = _load_beta_config()
    return (
        (os.environ.get("MAIL_TO") or "").strip()
        or (cfg.get("admin_email") or "").strip()
    )


def _mail_from() -> str:
    _load_dotenv()
    return (os.environ.get("MAIL_FROM") or os.environ.get("SMTP_USER") or "").strip()


def _send_webhook(payload: Dict[str, Any]) -> Tuple[bool, str]:
    url = (os.environ.get("NOTIFY_WEBHOOK_URL") or "").strip()
    if not url:
        return False, "no webhook"
    try:
        import urllib.error
        import urllib.request

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, f"webhook {resp.status}"
    except Exception as e:
        return False, f"webhook error: {e}"


def _send_resend(to: str, subject: str, text: str) -> Tuple[bool, str]:
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key:
        return False, "no resend"
    from_addr = _mail_from() or "onboarding@resend.dev"
    try:
        import urllib.request

        body = json.dumps(
            {
                "from": from_addr,
                "to": [to],
                "subject": subject,
                "text": text,
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=body,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, f"resend {resp.status}"
    except Exception as e:
        return False, f"resend error: {e}"


def _send_sendgrid(to: str, subject: str, text: str) -> Tuple[bool, str]:
    key = (os.environ.get("SENDGRID_API_KEY") or "").strip()
    if not key:
        return False, "no sendgrid"
    from_addr = _mail_from()
    if not from_addr:
        return False, "set MAIL_FROM for SendGrid"
    try:
        import urllib.request

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": from_addr},
            "subject": subject,
            "content": [{"type": "text/plain", "value": text}],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=data,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return True, f"sendgrid {resp.status}"
    except Exception as e:
        return False, f"sendgrid error: {e}"


def _send_smtp(to: str, subject: str, text: str) -> Tuple[bool, str]:
    _load_dotenv()
    host = (os.environ.get("SMTP_HOST") or "").strip()
    port = int(os.environ.get("SMTP_PORT") or "587")
    user = (os.environ.get("SMTP_USER") or "").strip()
    password = (os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or "").strip()
    from_addr = _mail_from() or user
    if not host or not user or not password:
        return False, "no smtp env"
    try:
        msg = MIMEText(text, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to

        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(from_addr, [to], msg.as_string())
        return True, "smtp ok"
    except Exception as e:
        return False, f"smtp error: {e}"


def notify_admin_sync(event: str, user_id: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """
    Send one notification email if configured. Safe to call from a background thread.
    """
    _load_dotenv()
    if (os.environ.get("NOTIFY_DISABLED") or "").strip().lower() in ("1", "true", "yes"):
        return

    to = _admin_recipient()
    if not to:
        return

    subject = f"[SoapBoxx Beta] {event} — {user_id}"
    lines = [
        f"Event: {event}",
        f"User: {user_id}",
        f"Detail: {json.dumps(detail, ensure_ascii=False) if detail else '{}'}",
        "",
        "— Sent by SoapBoxx notify_client",
    ]
    text = "\n".join(lines)

    payload = {"event": event, "user_id": user_id, "detail": detail or {}}

    _load_dotenv()
    smtp_ready = bool(
        (os.environ.get("SMTP_HOST") or "").strip()
        and (os.environ.get("SMTP_USER") or "").strip()
        and (
            (os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS") or "").strip()
        )
    )

    # 1) SMTP first (fastest for most people: Gmail app password only)
    if smtp_ready:
        ok, msg = _send_smtp(to, subject, text)
        print(f"notify smtp: {msg}")
        if ok:
            return

    # 2) Resend
    if (os.environ.get("RESEND_API_KEY") or "").strip():
        ok, msg = _send_resend(to, subject, text)
        print(f"notify resend: {msg}")
        if ok:
            return

    # 3) SendGrid
    if (os.environ.get("SENDGRID_API_KEY") or "").strip():
        ok, msg = _send_sendgrid(to, subject, text)
        print(f"notify sendgrid: {msg}")
        if ok:
            return

    # 4) Optional remote handler
    if (os.environ.get("NOTIFY_WEBHOOK_URL") or "").strip():
        ok, msg = _send_webhook(payload)
        print(f"notify webhook: {msg}")
        if ok:
            return

    if not smtp_ready and not (os.environ.get("RESEND_API_KEY") or "").strip() and not (
        os.environ.get("SENDGRID_API_KEY") or ""
    ).strip() and not (os.environ.get("NOTIFY_WEBHOOK_URL") or "").strip():
        print(
            "notify: skipped (no email configured). Add a .env file — see docs/README_DEMO.md «Email in 1 minute»."
        )


def notify_admin_async(event: str, user_id: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """Non-blocking: runs notify_admin_sync in a daemon thread."""

    def _run():
        try:
            notify_admin_sync(event, user_id, detail)
        except Exception as e:
            print(f"notify_admin_async: {e}")

    threading.Thread(target=_run, daemon=True).start()
