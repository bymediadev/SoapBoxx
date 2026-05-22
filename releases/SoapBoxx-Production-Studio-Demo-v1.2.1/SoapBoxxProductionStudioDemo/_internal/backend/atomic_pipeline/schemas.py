# backend/atomic_pipeline/schemas.py
"""Strict JSON contracts for the atomic intelligence pipeline (v3 extension pack)."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


ClaimCategory = Literal["historical_fact", "interpretation", "rhetorical", "unclear"]
ClaimConfidence = Literal["high", "medium", "low"]
EvidenceBasis = Literal["explicit_transcript", "inferred", "unknown"]

VerificationStatus = Literal["supported", "disputed", "unverified", "likely_incorrect"]
RecommendedAction = Literal["keep", "reframe", "remove", "fact_check_needed"]

TopicCategory = Literal[
    "history",
    "psychology",
    "politics",
    "economics",
    "behavior",
    "ethics",
    "other",
]

TopicRelationship = Literal["causes", "influences", "conflicts_with", "contextualizes"]

InsightType = Literal["psychological", "historical", "political", "behavioral"]

ClipWhy = Literal["clarity", "tension", "novelty", "emotional_weight"]
ClipRisk = Literal["safe", "contextual", "misleading_if_isolated"]

GuestType = Literal["historian", "practitioner", "contrarian", "academic", "storyteller"]


class Claim(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    timestamp: float = 0.0
    raw_statement: str
    category: ClaimCategory
    confidence: ClaimConfidence
    evidence_basis: EvidenceBasis


class Verification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim_id: str
    status: VerificationStatus
    notes: str = ""
    recommended_action: RecommendedAction


class TopicNode(BaseModel):
    model_config = ConfigDict(extra="ignore")

    topic_id: str
    label: str
    weight: float = Field(ge=0.0, le=1.0)
    category: TopicCategory
    evidence_claim_ids: List[str] = Field(default_factory=list)


class TopicEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")

    from_topic_id: str
    to_topic_id: str
    relationship: TopicRelationship


class TopicGraph(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nodes: List[TopicNode] = Field(default_factory=list)
    edges: List[TopicEdge] = Field(default_factory=list)


class Insight(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    derived_from_claim_ids: List[str] = Field(default_factory=list)
    insight_type: InsightType
    insight_statement: str
    applicability: str = ""


class Clip(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clip_id: str
    source_claim_id: str
    hook_line: str
    why_it_works: ClipWhy
    risk_level: ClipRisk


class GuestRecommendationReason(BaseModel):
    model_config = ConfigDict(extra="ignore")

    primary_angle: str = ""
    what_they_would_challenge: str = ""


class GuestRecommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    guest_type: GuestType
    target_topic_id: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    recommendation_reason: GuestRecommendationReason
    ideal_questions: List[str] = Field(default_factory=list)


class AudienceAction(BaseModel):
    """7-day testable behavior tied to an insight (Module 7)."""

    model_config = ConfigDict(extra="ignore")

    id: str
    insight_id: str
    behavior: str
    timeframe_days: int = Field(default=7, ge=1, le=7)


class AtomicPipelineEnvelope(BaseModel):
    """Exact export shape for Module 8."""

    model_config = ConfigDict(extra="ignore")

    claims: List[Claim] = Field(default_factory=list)
    verification: List[Verification] = Field(default_factory=list)
    topic_graph: TopicGraph = Field(default_factory=TopicGraph)
    insights: List[Insight] = Field(default_factory=list)
    clips: List[Clip] = Field(default_factory=list)
    guest_recommendations: List[GuestRecommendation] = Field(default_factory=list)
    actions: List[AudienceAction] = Field(default_factory=list)
    diagnostics: Optional[dict] = None
