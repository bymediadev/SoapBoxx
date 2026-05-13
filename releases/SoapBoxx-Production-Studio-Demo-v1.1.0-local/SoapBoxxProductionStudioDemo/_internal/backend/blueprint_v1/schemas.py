# backend/blueprint_v1/schemas.py
"""Pydantic models — Master Blueprint v1 final envelope + SSOT."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EpisodicInput(BaseModel):
    """Single Source of Truth for all blueprint stages."""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    description: str = ""
    transcript: str = ""
    duration: float = 0.0
    entities: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    structure_signals: List[str] = Field(default_factory=list)
    tone_signals: List[str] = Field(default_factory=list)

    @classmethod
    def from_metadata_transcript(
        cls,
        transcript: str,
        *,
        title: str = "",
        description: str = "",
        duration: float = 0.0,
        creator: str = "",
        genre: str = "",
    ) -> "EpisodicInput":
        topics: List[str] = []
        if genre.strip():
            topics.append(genre.strip())
        return cls(
            title=title or "",
            description=description or "",
            transcript=transcript or "",
            duration=duration,
            entities=[creator.strip()] if creator.strip() else [],
            topics=topics,
            structure_signals=[],
            tone_signals=[],
        )


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: Literal["ANALYTICAL", "NARRATIVE", "HYBRID"]
    confidence: int = Field(ge=0, le=100)
    reasoning: str = ""

    @field_validator("type", mode="before")
    @classmethod
    def upper_type(cls, v: Any) -> str:
        s = str(v or "HYBRID").strip().upper()
        if s not in ("ANALYTICAL", "NARRATIVE", "HYBRID"):
            return "HYBRID"
        return s


class NarrativeBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    core_story: str = ""
    key_moments: List[str] = Field(default_factory=list)
    hidden_dynamics: List[str] = Field(default_factory=list)
    memory_vs_reality: str = ""
    tension: str = ""


class AnalyticalBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    core_ideas: List[str] = Field(default_factory=list)
    claims: List[str] = Field(default_factory=list)
    reasoning_quality: str = ""
    missing_pieces: List[str] = Field(default_factory=list)
    counterpoints: List[str] = Field(default_factory=list)


class ThesisBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    thesis: str = ""


class ClipItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = ""
    reason: str = ""


class ClipsBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    clips: List[ClipItem] = Field(default_factory=list)


class SynthesisBlock(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key_insight: str = ""
    friction_point: str = ""
    strength: str = ""
    gap: str = ""


class FinalReport(BaseModel):
    """Top-level validated output — blueprint §7."""

    model_config = ConfigDict(extra="allow")

    classification: ClassificationResult
    thesis: str = Field(min_length=12)
    narrative: Dict[str, Any]
    analytical: Dict[str, Any]
    synthesis: Dict[str, Any]
    clips: List[Dict[str, Any]]
    actions: List[str] = Field(default_factory=list)
    strategist_report: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_blocks(
        cls,
        *,
        classification: ClassificationResult,
        thesis: str,
        narrative: NarrativeBlock,
        analytical: AnalyticalBlock,
        synthesis: SynthesisBlock,
        clips: List[ClipItem],
        actions: Optional[List[str]] = None,
        strategist_report: Optional[Dict[str, Any]] = None,
    ) -> "FinalReport":
        return cls(
            classification=classification,
            thesis=thesis.strip(),
            narrative=narrative.model_dump(),
            analytical=analytical.model_dump(),
            synthesis=synthesis.model_dump(),
            clips=[c.model_dump() for c in clips],
            actions=list(actions or []),
            strategist_report=dict(strategist_report or {}),
        )

    def public_payload(self) -> Dict[str, Any]:
        """User-facing payload that excludes internal extraction internals."""
        return {
            "strategist_report": dict(self.strategist_report or {}),
            "product_positioning": "A podcast performance and growth intelligence layer",
        }
