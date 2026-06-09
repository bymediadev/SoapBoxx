# backend package — V1 API + transcription utilities.

from __future__ import annotations

import importlib
from typing import Any

from .error_tracker import error_tracker

__all__ = [
    "Transcriber",
    "error_tracker",
]

_LAZY_EXPORTS: dict[str, str] = {
    "Transcriber": "transcriber",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(f".{_LAZY_EXPORTS[name]}", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
