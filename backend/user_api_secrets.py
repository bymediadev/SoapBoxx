"""
Optional per-user API keys for demos / BYOK installs.

Keys are stored in a small ``.env``-style file under the OS user profile (not the repo),
then loaded into ``os.environ`` so existing SoapBoxx code paths work unchanged.

Override order: repo ``.env`` loads first, then ``load_user_api_secrets(override=True)``
so user keys win over bundled demo defaults.
"""

from __future__ import annotations

import os
from pathlib import Path


def classify_api_key_secret(secret: str) -> str | None:
    """
    Map a pasted secret to the ``os.environ`` name SoapBoxx already reads.

    Recognizes common prefixes for OpenAI, Anthropic, Groq, and Google API keys.
    Returns ``None`` if the string does not match a known pattern (caller may ask
    the user to pick a provider manually).
    """
    s = (secret or "").strip()
    if not s:
        return None
    low = s.lower()
    if low.startswith("sk-ant"):
        return "ANTHROPIC_API_KEY"
    if s.startswith("gsk_"):
        return "GROQ_API_KEY"
    if s.startswith("AIza"):
        return "GOOGLE_API_KEY"
    if low.startswith("sk-"):
        return "OPENAI_API_KEY"
    return None


def user_api_secrets_path() -> Path:
    """Path to the user-owned secrets file (``.env`` format)."""
    raw = (os.getenv("SOAPBOXX_USER_SECRETS_FILE") or "").strip()
    if raw:
        return Path(raw)
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "SoapBoxx"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "soapboxx"
    root.mkdir(parents=True, exist_ok=True)
    return root / "api_keys.env"


def load_user_api_secrets(*, override: bool = True) -> None:
    """Load ``user_api_secrets_path()`` into the process environment."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    p = user_api_secrets_path()
    if p.is_file():
        load_dotenv(p, override=override)


def persist_user_api_secret(key: str, value: str) -> None:
    """Write one key to the user secrets file and update ``os.environ`` (or remove if empty)."""
    from dotenv.main import set_key, unset_key

    p = user_api_secrets_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(
            "# SoapBoxx — your API keys (optional). This file stays on your machine only.\n",
            encoding="utf-8",
        )
    val = (value or "").strip()
    if not val:
        try:
            unset_key(p, key, encoding="utf-8")
        except Exception:
            pass
        os.environ.pop(key, None)
        if key == "GROQ_API_KEY":
            try:
                unset_key(p, "SOAPBOXX_GROQ_API_KEY", encoding="utf-8")
            except Exception:
                pass
            os.environ.pop("SOAPBOXX_GROQ_API_KEY", None)
        return

    set_key(p, key, val, quote_mode="always", encoding="utf-8")
    os.environ[key] = val
    if key == "GROQ_API_KEY":
        set_key(p, "SOAPBOXX_GROQ_API_KEY", val, quote_mode="always", encoding="utf-8")
        os.environ["SOAPBOXX_GROQ_API_KEY"] = val


def clear_user_api_secrets_file() -> None:
    """Delete the user secrets file if it exists."""
    p = user_api_secrets_path()
    if p.is_file():
        p.unlink()
