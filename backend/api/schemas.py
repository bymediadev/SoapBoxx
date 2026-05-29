"""Pydantic schemas for V1 API (source layer only)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PodcastCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=512)
    rss_url: Optional[str] = Field(None, max_length=2048)


class PodcastRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    rss_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EpisodeCreate(BaseModel):
    podcast_id: int
    title: str = Field(..., min_length=1, max_length=1024)
    audio_url: Optional[str] = Field(None, max_length=2048)
    duration_seconds: Optional[float] = None
    published_at: Optional[datetime] = None


class EpisodeRead(BaseModel):
    id: int
    podcast_id: int
    title: str
    description: Optional[str] = None
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    published_at: Optional[datetime] = None
    full_transcript: Optional[str] = None
    guid: Optional[str] = None
    pipeline_status: str = "new"
    pipeline_error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RssIngestRequest(BaseModel):
    rss_url: str = Field(..., min_length=8, max_length=2048)
    podcast_id: Optional[int] = None


class RssIngestResponse(BaseModel):
    podcast_id: int
    episodes_created: int
    episodes_skipped: int = 0
    episodes_dispatched: int = 0
    episode_ids: list[int] = Field(default_factory=list)


class TranscribeRequest(BaseModel):
    transcript: Optional[str] = Field(
        None,
        description="Optional paste path; skips STT when provided",
    )


class TranscribeResponse(BaseModel):
    episode_id: int
    transcript_length: int
    segment_count: int


class EpisodeFeaturesRead(BaseModel):
    episode_id: int
    hook_length_seconds: Optional[float] = None
    intro_length_seconds: Optional[float] = None
    question_count: Optional[int] = None
    speaking_turns: Optional[int] = None
    host_guest_ratio: Optional[float] = None
    topic_shift_count: Optional[int] = None
    cta_present: Optional[bool] = None

    model_config = {"from_attributes": True}


class TaxonomyNodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    node_type: str = Field(..., pattern="^(domain|category|subcategory)$")
    parent_id: Optional[int] = None


class TaxonomyNodeRead(BaseModel):
    id: int
    name: str
    node_type: str
    parent_id: Optional[int] = None

    model_config = {"from_attributes": True}


class PodcastTaxonomyMapRequest(BaseModel):
    podcast_id: int
    taxonomy_node_id: int


class CoachingMetricRow(BaseModel):
    metric: str
    value: str
    benchmark: Optional[str] = None
    coaching: Optional[str] = None


class CoachingReportRead(BaseModel):
    episode_structure: List[CoachingMetricRow] = []
    conversation_dynamics: List[CoachingMetricRow] = []
    what_this_means: List[str] = []
    similar_to: Optional[str] = None
    topic_shift_note: Optional[str] = None


class TranslationRead(BaseModel):
    episode_id: int
    template_id: str
    insight_text: str
    report: Optional[CoachingReportRead] = None

    model_config = {"from_attributes": True}


class ProcessEpisodeRequest(BaseModel):
    transcript: Optional[str] = Field(
        None,
        description="Optional pasted transcript; skips audio STT when set",
    )
    force_retranscribe: bool = Field(
        False,
        description=(
            "When true, re-run STT from audio_url even if a transcript exists. "
            "Slow on Railway (may timeout on long episodes). Default false skips STT "
            "when full_transcript is already stored."
        ),
    )


class ProcessEpisodeResponse(BaseModel):
    episode_id: int
    status: str
    steps: list[dict] = Field(
        description=(
            "Per-step results. Transcribe step includes reason "
            "(existing_transcript | force_retranscribe | no_transcript | pasted_transcript) "
            "and reused (true when transcript was not re-generated)."
        ),
    )
    transcript_length: int
    segment_count: int
    template_id: Optional[str] = None
    insight_preview: Optional[str] = None
    transcript_source: Optional[str] = Field(
        None,
        description="existing | stt | pasted — how the transcript used for metrics was obtained",
    )


class ProcessBatchResponse(BaseModel):
    requested: int
    attempted: int
    succeeded: int
    failed: int
    results: list[dict]
