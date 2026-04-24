# report_control_workflow/constants.py
"""Thresholds, prompts, regex patterns — shared by pipeline, intelligence, and logging (no layer imports)."""

from __future__ import annotations

import re
from typing import List, Tuple

RULES: List[str] = [
    "No raw transcript allowed in final packaged claims (only cleaned + bounded excerpts).",
    "No duplicate content in shipped claim rows.",
    "Every claim must be testable (complete sentence, non-filler).",
    "Every claim must have **supporting** evidence (relationship == supports), not mere similarity.",
    "Every claim must relate to the thesis (support or contradict) — binary gate.",
    "Audience actions must be concrete and external (no vague internal 'confirm thesis' lines).",
    "Ship only when score_report >= threshold or caller explicitly overrides.",
    "Claims must meet minimum strength (specificity / assertiveness), not only grammar.",
    "Evidence must meet minimum proving strength, not only 'supports' relationship.",
]

MIN_CLAIMS = 3
DEFAULT_EVIDENCE_SCORE_MIN = 0.6
DEFAULT_THESIS_MIN_WORDS = 8
DEFAULT_CLAIM_STRENGTH_MIN = 0.6
DEFAULT_EVIDENCE_STRENGTH_MIN = 0.5
DEFAULT_SEMANTIC_DEDUP = 0.88
DEFAULT_CLAIM_DIVERSITY_CLUSTER = 0.82
HYBRID_RELATIONSHIP_SIM_HIGH = 0.75
DEFAULT_DENSITY_MIN = 0.38
DENSITY_PENALTY_MAX = 0.12
DEFAULT_INSIGHT_NOVELTY_MIN = 0.5
DEFAULT_CONTRARIAN_SCORE_PENALTY = 0.12
DEFAULT_RELEVANCE_MIN = 0.12
DEFAULT_OUTPUT_COMPRESS_THRESHOLD = 0.85
DEFAULT_CLIP_SELECT_K = 3
MIN_CLIPS_CONTRACT = 2
CORE_INSIGHT_MAX_WORDS = 20
DEFAULT_CLIP_DIVERSITY_THRESHOLD = 0.85
DEFAULT_CORE_SYNTHESIS_NOVELTY_TRIGGER = 0.6
MAX_WARNINGS_IN_OUTPUT = 5
RELATION_TYPES: Tuple[str, ...] = ("supports", "contradicts", "soft_contradiction", "irrelevant")
DEFAULT_SHIP_SCORE_STRONG = 0.85
DEFAULT_SHIP_SCORE_OK = 0.70
DUPLICATE_CLAIM_SIMILARITY = 0.97

PIPELINE_ERROR_LOG_MAX = 500
REPORT_SCORE_HISTORY_MAX = 5000

CLEAN_PROMPT = """You are a transcript cleaner.

Rules:
- Remove filler words (like, you know, I mean) where they add no meaning
- Remove repeated words and obvious ASR stutters
- Fix broken grammar only when meaning is preserved
- Break long sentences into readable ones without changing facts
- Keep original meaning EXACT — do not summarize the episode

Return clean text only. No markdown fences."""

REPAIR_PROMPT = """You are repairing a structured podcast report JSON.

## Current JSON
{report_json}

## Validation errors (fix all)
{errors}

Rules:
- Return ONLY valid JSON matching the same shape: title, thesis, claims[], highlights[], clips[], actions[].
- Optional keys (may be omitted): core_insight (one sentence), contrarian (one sentence or empty string).
- Each claim: text (one testable sentence), evidence (verbatim excerpt), score (0-1).
- Remove or rewrite rows that caused errors; do not invent unrelated themes.

No markdown fences. No commentary outside JSON."""

RELATIONSHIP_CLASSIFY_PROMPT = """You classify whether PASSAGE supports, contradicts, or is irrelevant to HYPOTHESIS.

HYPOTHESIS: {hypothesis}

PASSAGE: {passage}

Reply with exactly one word: supports | contradicts | irrelevant
"""

_STOP = frozenset(
    "the a an to of and or for in on at by as is it if we you they he she "
    "was were are be been being this that these those with from than then "
    "into over out up down about".split()
)

_FILLER_PHRASES = re.compile(
    r"\b(?:like|you know|i mean|sort of|kind of)\b[, ]*",
    re.I,
)
_MULTI_SPACE = re.compile(r" {2,}")
_REPEAT_WORD = re.compile(r"\b(\w+)\s+\1\b", re.I)
_YEAR_STUTTER = re.compile(r"\b((?:19|20)\d{2})\s+\1\b")
_COMMA_STUTTER = re.compile(r"(?:\s*,){2,}")
_VERB_LIKE = re.compile(
    r"\b(?:is|are|was|were|been|being|have|has|had|do|does|did|would|could|should|may|might|must|"
    r"shows?|argues?|demonstrates?|proves?|means|shaped|built|funded|remains?|became|makes?|"
    r"went|goes|came|says|states|claims|requires?|drives?|forces?)\b",
    re.I,
)
_PAST_PART = re.compile(r"\b\w{4,}ed\b")
_WEAK_OPENERS = re.compile(
    r"^(Then|So|And|But|Like|Well|Okay|Yeah|Oh)\b",
    re.I,
)
_INTERNAL_ACTION_BANNED = re.compile(
    r"\b(?:confirm|verify|re-?read|revisit|double-?check)\s+(?:the\s+)?thesis\b",
    re.I,
)
_VAGUE_WORDS = re.compile(
    r"\b(?:various|many|some|several|often|generally|typically|sometimes|maybe|perhaps|"
    r"things?\s+like|sort\s+of|kind\s+of|in\s+many\s+ways|different\s+ways|over\s+time|"
    r"changed\s+over\s+time|in\s+various\s+ways)\b",
    re.I,
)
_STRONG_VERBS = re.compile(
    r"\b(?:causes?|caused|leads?\s+to|led\s+to|results?\s+in|resulted|demonstrates?|proved?|"
    r"forced?|drove|shaped|influenced|banned|doubled|tripled|measured|shows?\s+that|argues?\s+that|"
    r"funded|blocked|required|mandated|outlawed|correlates?)\b",
    re.I,
)
_DIRECTIONAL = re.compile(
    r"\b(?:causes?|leads?\s+to|results?\s+in|shaped|influenc(?:ed|es)|drove|forced?|proved?|demonstrates?|"
    r"shows?\s+that|argues?\s+that|because|therefore|thus|funded|blocked|mandated)\b",
    re.I,
)
_EVIDENCE_CONCRETE = re.compile(
    r"\b(?:19|20)\d{2}\b|\b\d+(?:\.\d+)?%|\$\d|\b(?:study|studies|trial|dataset|record|minutes?|bill|law|act)\b",
    re.I,
)
_EVIDENCE_VAGUE = re.compile(
    r"\b(?:historically|involved|generally|philosophy|philosophical|often\s+been|has\s+been|"
    r"in\s+many\s+cases|tends\s+to|might\s+have|could\s+have)\b",
    re.I,
)
_INSIGHT_GENERIC = re.compile(
    r"\b(?:has changed over time|is important because|in many ways|various factors|has evolved|"
    r"matters because|plays a role|significant impact|broadly speaking)\b",
    re.I,
)
_PROGRESSION = re.compile(
    r"\b(?:therefore|because|which leads to|as a result|consequently|nonetheless|however|yet|but|"
    r"even so|on the other hand)\b",
    re.I,
)
_CLIP_STRONG = re.compile(
    r"\b(?:kills?|destroys?|drives?|controls?|exposes?|betrays?|lies?|truth|crisis|broken|"
    r"rigged|corrupt)\b",
    re.I,
)
_SOFT_TENSION_RE = re.compile(
    r"\b(?:however|but|although|nonetheless|even so|yet)\b|"
    r"\b(?:depends|not always|in some cases|with exceptions|may not|does not always)\b",
    re.I,
)
