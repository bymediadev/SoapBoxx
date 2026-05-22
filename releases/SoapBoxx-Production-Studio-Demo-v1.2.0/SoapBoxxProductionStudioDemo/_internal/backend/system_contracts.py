"""
Global version and schema identifiers — attach-only; no scoring or policy logic.

Used by :mod:`evaluation_pipeline`, :mod:`decision_engine`, and :mod:`report_renderer`.
"""

from __future__ import annotations

# Product-facing bundle version (metadata only).
SYSTEM_VERSION = "reporting_v1"

# Evaluation artifact version (snapshot + evaluator output).
EVALUATION_VERSION = "v1"

# Immutable contract name for ``input_quality_components`` shape (see evaluation_pipeline).
EVALUATION_OUTPUT_SCHEMA = "input_quality_components_v1"

# Human report dict from :func:`report_renderer.render_report`.
REPORT_OUTPUT_SCHEMA_VERSION = "report_output_schema_v1"

# Keys allowed in ``input_quality_components`` for schema v1 (no dynamic fields).
INPUT_QUALITY_COMPONENTS_V1_KEYS = (
    "input_quality_score",
    "transcript_length_score",
    "extraction_success_score",
    "grounding_density_score",
)
