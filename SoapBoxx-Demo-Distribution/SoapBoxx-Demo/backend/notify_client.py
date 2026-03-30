#!/usr/bin/env python3
"""
Send email for beta events. Signups/logins with a real email address are mailed TO that person.
Tester IDs use MAIL_TO / admin_email. Set NOTIFY_USER_EMAILS=0 to send everything only to MAIL_TO.

Priority:
  1. SMTP_* (Gmail app password) — tried first when set
  2. RESEND_API_KEY / SENDGRID_API_KEY
  3. NOTIFY_WEBHOOK_URL

Loads `.env` from SoapBoxx-Demo, then parent SoapBoxx repo `.env` (see .env.example).
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
    """Load .env: SoapBoxx-Demo/.env overrides SoapBoxx/.env (workspace root)."""
    try:
        from dotenv import load_dotenv

        # e.g. .../SoapBoxx/SoapBoxx-Demo-Distribution/SoapBoxx-Demo
        demo_env = _PROJECT_ROOT / ".env"
        # e.g. .../SoapBoxx/.env (same folder many users keep OPENAI_* etc.)
        workspace_env = _PROJECT_ROOT.parent.parent / ".env"
        if workspace_env.is_file():
            load_dotenv(workspace_env, override=False)
        if demo_env.is_file():
            load_dotenv(demo_env, override=True)
        elif not workspace_env.is_file():
            cwd_env = Path.cwd() / ".env"
            if cwd_env.is_file():
                load_dotenv(cwd_env)
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
    """Fallback inbox: MAIL_TO in .env first, else beta_config admin_email (tester IDs, copies)."""
    _load_dotenv()
    cfg = _load_beta_config()
    return (
        (os.environ.get("MAIL_TO") or "").strip()
        or (cfg.get("admin_email") or "").strip()
    )


def _looks_like_email(user_id: str) -> bool:
    s = (user_id or "").strip().lower()
    if "@" not in s:
        return False
    local, _, domain = s.partition("@")
    return bool(local) and bool(domain) and "." in domain


# Events where we email the person at user_id when that value is an email (signups, logins, etc.)
_USER_FACING_EVENTS = frozenset(
    {
        "signup",
        "login",
        "magic_link_demo",
        "episode_workflow",
        "api_keys_saved_portal",
        "api_keys_saved_app",
    }
)


def _recipient_for_event(event: str, user_id: str) -> str:
    """
    People who sign up with an email get mail at that address.
    Tester IDs (no @) use MAIL_TO / admin_email instead.
    Set NOTIFY_USER_EMAILS=0 to always use admin only.
    """
    _load_dotenv()
    if (os.environ.get("NOTIFY_USER_EMAILS") or "").strip().lower() in ("0", "false", "no"):
        return _admin_recipient()
    if event in _USER_FACING_EVENTS and _looks_like_email(user_id):
        return user_id.strip().lower()
    return _admin_recipient()


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


def _compose_email(event: str, user_id: str, detail: Optional[Dict[str, Any]], to: str) -> Tuple[str, str]:
    """Subject + body. Friendly copy when emailing the user; technical log for admin inbox."""
    detail = detail or {}
    is_user_inbox = _looks_like_email(user_id) and to == user_id.strip().lower()

    if is_user_inbox:
        if event == "signup":
            return (
                "Welcome to SoapBoxx Beta",
                f"Hi,\n\nThanks for signing up. Your account is registered for:\n{user_id}\n\n"
                f"Open the SoapBoxx app and sign in with this email to continue.\n\n"
                f"— SoapBoxx Beta",
            )
        if event == "login":
            return (
                "Signed in to SoapBoxx Beta",
                f"Hi,\n\nYou just signed in to SoapBoxx Beta with:\n{user_id}\n\n"
                f"If this wasn’t you, you can ignore this message.\n\n— SoapBoxx Beta",
            )
        if event == "magic_link_demo":
            return (
                "SoapBoxx Beta — login (demo)",
                f"Hi,\n\nWe recorded a magic-link request for {user_id}.\n"
                f"In the full product, you’d get a real link here. For now, complete sign-in in the app.\n\n"
                f"— SoapBoxx Beta",
            )
        if event == "episode_workflow":
            used = detail.get("episodes_used", "?")
            lim = detail.get("limit", "?")
            return (
                "SoapBoxx Beta — episode recorded",
                f"Hi,\n\nYour episode workflow was recorded ({used}/{lim}) for:\n{user_id}\n\n— SoapBoxx Beta",
            )
        if event in ("api_keys_saved_portal", "api_keys_saved_app"):
            return (
                "SoapBoxx Beta — API keys saved",
                f"Hi,\n\nAPI key settings were saved for your account:\n{user_id}\n\n— SoapBoxx Beta",
            )

    subject = f"[SoapBoxx Beta] {event} — {user_id}"
    lines = [
        f"Event: {event}",
        f"User: {user_id}",
        f"Detail: {json.dumps(detail, ensure_ascii=False) if detail else '{}'}",
        "",
        "— Sent by SoapBoxx notify_client",
    ]
    return subject, "\n".join(lines)


def notify_admin_sync(event: str, user_id: str, detail: Optional[Dict[str, Any]] = None) -> None:
    """
    Send one notification email if configured. Signups/logins go to the user's email when user_id is an email.
    """
    _load_dotenv()
    if (os.environ.get("NOTIFY_DISABLED") or "").strip().lower() in ("1", "true", "yes"):
        return

    to = _recipient_for_event(event, user_id)
    if not to:
        return

    subject, text = _compose_email(event, user_id, detail, to)

    payload = {"event": event, "user_id": user_id, "detail": detail or {}, "recipient": to}

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
