"""V1 core tables — Day 1 schema (SOAPBOXX_V1_7DAY_EXECUTION.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Podcast(Base):
    __tablename__ = "podcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rss_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    episodes: Mapped[list["Episode"]] = relationship(back_populates="podcast")
    taxonomy_links: Mapped[list["PodcastTaxonomyMap"]] = relationship(
        back_populates="podcast"
    )


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    podcast_id: Mapped[int] = mapped_column(
        ForeignKey("podcasts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    raw_rss_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    full_transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guid: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, index=True)
    pipeline_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="new", server_default="new"
    )
    pipeline_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("podcast_id", "guid", name="uq_episode_podcast_guid"),
    )

    podcast: Mapped["Podcast"] = relationship(back_populates="episodes")
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        back_populates="episode", cascade="all, delete-orphan"
    )
    features: Mapped[Optional["EpisodeFeatures"]] = relationship(
        back_populates="episode", uselist=False, cascade="all, delete-orphan"
    )
    translation: Mapped[Optional["EpisodeTranslation"]] = relationship(
        back_populates="episode", uselist=False, cascade="all, delete-orphan"
    )


class SystemEvent(Base):
    """Append-only activity feed for system visibility (Lovable / ops)."""

    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    podcast_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("podcasts.id", ondelete="SET NULL"), nullable=True
    )
    episode_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True
    )
    meta_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[int] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    end_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    episode: Mapped["Episode"] = relationship(back_populates="segments")


class EpisodeFeatures(Base):
    """Exactly 7 V1 metrics (Day 5); table created Day 1."""

    __tablename__ = "episode_features"

    episode_id: Mapped[int] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), primary_key=True
    )
    hook_length_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intro_length_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    question_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    speaking_turns: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    host_guest_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    topic_shift_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cta_present: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    episode: Mapped["Episode"] = relationship(back_populates="features")


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    node_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # domain | category | subcategory

    parent: Mapped[Optional["TaxonomyNode"]] = relationship(
        remote_side="TaxonomyNode.id", back_populates="children"
    )
    children: Mapped[list["TaxonomyNode"]] = relationship(back_populates="parent")
    podcast_links: Mapped[list["PodcastTaxonomyMap"]] = relationship(
        back_populates="taxonomy_node"
    )


class EpisodeTranslation(Base):
    __tablename__ = "episode_translations"

    episode_id: Mapped[int] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), primary_key=True
    )
    template_id: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    insight_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    episode: Mapped["Episode"] = relationship(back_populates="translation")


class PodcastTaxonomyMap(Base):
    __tablename__ = "podcast_taxonomy_map"
    __table_args__ = (
        UniqueConstraint("podcast_id", "taxonomy_node_id", name="uq_podcast_taxonomy"),
    )

    podcast_id: Mapped[int] = mapped_column(
        ForeignKey("podcasts.id", ondelete="CASCADE"), primary_key=True
    )
    taxonomy_node_id: Mapped[int] = mapped_column(
        ForeignKey("taxonomy_nodes.id", ondelete="CASCADE"), primary_key=True
    )

    podcast: Mapped["Podcast"] = relationship(back_populates="taxonomy_links")
    taxonomy_node: Mapped["TaxonomyNode"] = relationship(back_populates="podcast_links")
