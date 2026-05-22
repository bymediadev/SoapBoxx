# backend package — lazy desktop imports so V1 API deploy does not require PortAudio.

from __future__ import annotations

import importlib
from typing import Any

from .error_tracker import error_tracker

__all__ = [
    "SoapBoxxCore",
    "Config",
    "Transcriber",
    "FeedbackEngine",
    "GuestResearch",
    "AudioRecorder",
    "Logger",
    "error_tracker",
]

_LAZY_EXPORTS: dict[str, str] = {
    "SoapBoxxCore": "soapboxx_core",
    "Config": "config",
    "Transcriber": "transcriber",
    "FeedbackEngine": "feedback_engine",
    "GuestResearch": "guest_research",
    "AudioRecorder": "audio_recorder",
    "Logger": "logger",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(f".{_LAZY_EXPORTS[name]}", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
