"""
V1 structure extraction — rule-based, reproducible, no LLM opinions.

See docs/SYSTEM_DESIGN_V0_V1.md.
"""

from .rule_based import extract_rule_features

__all__ = ["extract_rule_features"]
