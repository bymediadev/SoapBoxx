# report_control_workflow/pipeline/__init__.py
"""Pipeline stages: extract → validate → score → repair → assemble; orchestration in ``control_pipeline``."""

from __future__ import annotations

from . import config  # noqa: F401 — ``from report_control_workflow.pipeline import config``
from .assembly import assemble_report
from .control_pipeline import run_control_pipeline
from .extract import (
    chunk_transcript,
    clean_transcript,
    deduplicate,
    extract_claims,
    filter_relevance,
    map_evidence,
)
from .repair import (
    auto_repair,
    compress_claim_rows,
    deduplicate_claim_rows,
    enforce_claim_diversity,
    repair_report_with_llm,
)
from .scoring import (
    information_quality_score,
    score_argument_cohesion,
    score_claim_strength,
    score_evidence_strength,
    score_insight_novelty,
    score_report,
)
from .validation import (
    contains_directional_claim,
    enforce_output_contract,
    has_subject_verb_structure,
    is_valid_action,
    is_valid_claim,
    is_valid_thesis,
    validate_claims,
    validate_output_contract,
    validate_report,
)

__all__ = [
    "config",
    "assemble_report",
    "run_control_pipeline",
    "chunk_transcript",
    "clean_transcript",
    "deduplicate",
    "extract_claims",
    "filter_relevance",
    "map_evidence",
    "auto_repair",
    "compress_claim_rows",
    "deduplicate_claim_rows",
    "enforce_claim_diversity",
    "repair_report_with_llm",
    "information_quality_score",
    "score_argument_cohesion",
    "score_claim_strength",
    "score_evidence_strength",
    "score_insight_novelty",
    "score_report",
    "contains_directional_claim",
    "enforce_output_contract",
    "has_subject_verb_structure",
    "is_valid_action",
    "is_valid_claim",
    "is_valid_thesis",
    "validate_claims",
    "validate_output_contract",
    "validate_report",
]
