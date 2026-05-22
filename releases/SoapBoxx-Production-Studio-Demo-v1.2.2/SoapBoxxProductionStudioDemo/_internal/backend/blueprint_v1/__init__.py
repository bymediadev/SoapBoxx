# backend/blueprint_v1/__init__.py
"""
SoapBoxx Master Blueprint v1: SSOT input → classify → control injection →
parallel narrative + analytical engines → thesis → clips → synthesis →
validated final report.

Run: ``from backend.blueprint_v1.pipeline import run_blueprint_v1`` (adjust import path).
"""

from .pipeline import run_blueprint_v1
from .schemas import EpisodicInput, FinalReport

__all__ = ["run_blueprint_v1", "EpisodicInput", "FinalReport"]
