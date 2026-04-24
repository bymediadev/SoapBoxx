# report_control_workflow/__init__.py
"""
Standalone report control pipeline: transcript hygiene, claim gates, scoring, packaging.

Intentionally **outside** ``backend/`` so it stays a separable concern from core SoapBoxx.
"""

from __future__ import annotations

from report_control_workflow.constants import (
    CLEAN_PROMPT,
    CORE_INSIGHT_MAX_WORDS,
    DEFAULT_CLAIM_STRENGTH_MIN,
    DEFAULT_CLIP_DIVERSITY_THRESHOLD,
    DEFAULT_CLIP_SELECT_K,
    DEFAULT_CONTRARIAN_SCORE_PENALTY,
    DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER,
    DEFAULT_DENSITY_MIN,
    DEFAULT_EVIDENCE_SCORE_MIN,
    DEFAULT_EVIDENCE_STRENGTH_MIN,
    DEFAULT_INSIGHT_NOVELTY_MIN,
    DEFAULT_OUTPUT_COMPRESS_THRESHOLD,
    DEFAULT_SHIP_SCORE_OK,
    DEFAULT_SHIP_SCORE_STRONG,
    DEFAULT_THESIS_MIN_WORDS,
    HYBRID_RELATIONSHIP_SIM_HIGH,
    MAX_WARNINGS_IN_OUTPUT,
    MIN_CLAIMS,
    MIN_CLIPS_CONTRACT,
    RELATION_TYPES,
    REPAIR_PROMPT,
    RULES,
)
from report_control_workflow.core.models import ClaimRow, ControlReport
from report_control_workflow.core.utils import report_token_density
from report_control_workflow.intelligence.clips import (
    score_clip_potential,
    select_top_clips,
    validate_clip_diversity,
)
from report_control_workflow.intelligence.contrarian import (
    detect_soft_contradiction,
    extract_contrarian_line,
    has_contrarian_claim,
    has_thesis_tension,
)
from report_control_workflow.intelligence.insight import (
    extract_core_insight,
    resolve_core_insight,
    synthesize_core_insight,
)
from report_control_workflow.intelligence.relationships import (
    classify_relationship,
    classify_relationship_hybrid,
    classify_relationship_llm,
    is_relevant,
)
from report_control_workflow.logging.error_log import (
    clear_pipeline_error_log,
    get_pipeline_error_log,
    log_errors,
    summarize_errors,
)
from report_control_workflow.logging.metrics import (
    REPORT_SCORE_HISTORY,
    clear_report_score_history,
    normalize_score,
    percentile_rank,
    store_report_score,
)
from report_control_workflow.pipeline.assembly import assemble_report
from report_control_workflow.pipeline.control_pipeline import run_control_pipeline
from report_control_workflow.pipeline.extract import (
    chunk_transcript,
    clean_transcript,
    deduplicate,
    extract_claims,
    filter_relevance,
    map_evidence,
)
from report_control_workflow.pipeline.repair import (
    auto_repair,
    compress_claim_rows,
    deduplicate_claim_rows,
    enforce_claim_diversity,
    repair_report_with_llm,
)
from report_control_workflow.pipeline.scoring import (
    information_quality_score,
    score_argument_cohesion,
    score_claim_strength,
    score_evidence_strength,
    score_insight_novelty,
    score_report,
)
from report_control_workflow.pipeline.validation import (
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
from report_control_workflow.runtime.decisions import decide_report_action, decide_report_action_v2

__all__ = [
    "RULES",
    "MIN_CLAIMS",
    "CLEAN_PROMPT",
    "REPAIR_PROMPT",
    "ClaimRow",
    "ControlReport",
    "DEFAULT_EVIDENCE_SCORE_MIN",
    "DEFAULT_EVIDENCE_STRENGTH_MIN",
    "DEFAULT_CLAIM_STRENGTH_MIN",
    "DEFAULT_THESIS_MIN_WORDS",
    "DEFAULT_SHIP_SCORE_STRONG",
    "DEFAULT_SHIP_SCORE_OK",
    "DEFAULT_DENSITY_MIN",
    "DEFAULT_INSIGHT_NOVELTY_MIN",
    "DEFAULT_CONTRARIAN_SCORE_PENALTY",
    "HYBRID_RELATIONSHIP_SIM_HIGH",
    "classify_relationship",
    "classify_relationship_llm",
    "classify_relationship_hybrid",
    "has_subject_verb_structure",
    "contains_directional_claim",
    "is_valid_thesis",
    "is_valid_claim",
    "is_relevant",
    "is_valid_action",
    "score_claim_strength",
    "score_evidence_strength",
    "score_insight_novelty",
    "score_argument_cohesion",
    "has_contrarian_claim",
    "score_clip_potential",
    "information_quality_score",
    "summarize_errors",
    "get_pipeline_error_log",
    "decide_report_action",
    "decide_report_action_v2",
    "REPORT_SCORE_HISTORY",
    "store_report_score",
    "percentile_rank",
    "clear_report_score_history",
    "DEFAULT_OUTPUT_COMPRESS_THRESHOLD",
    "DEFAULT_CLIP_SELECT_K",
    "MIN_CLIPS_CONTRACT",
    "CORE_INSIGHT_MAX_WORDS",
    "DEFAULT_CLIP_DIVERSITY_THRESHOLD",
    "DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER",
    "MAX_WARNINGS_IN_OUTPUT",
    "RELATION_TYPES",
    "compress_claim_rows",
    "select_top_clips",
    "extract_core_insight",
    "resolve_core_insight",
    "synthesize_core_insight",
    "normalize_score",
    "validate_clip_diversity",
    "detect_soft_contradiction",
    "has_thesis_tension",
    "extract_contrarian_line",
    "validate_output_contract",
    "enforce_output_contract",
    "report_token_density",
    "enforce_claim_diversity",
    "log_errors",
    "clear_pipeline_error_log",
    "clean_transcript",
    "chunk_transcript",
    "extract_claims",
    "validate_claims",
    "map_evidence",
    "filter_relevance",
    "deduplicate",
    "deduplicate_claim_rows",
    "validate_report",
    "auto_repair",
    "score_report",
    "repair_report_with_llm",
    "assemble_report",
    "run_control_pipeline",
]
