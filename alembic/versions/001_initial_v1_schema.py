"""Initial V1 schema — Day 1

Revision ID: 001
Revises:
Create Date: 2026-05-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "podcasts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("rss_url", sa.String(length=2048), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "taxonomy_nodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("node_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["taxonomy_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_taxonomy_nodes_parent_id", "taxonomy_nodes", ["parent_id"])

    op.create_table(
        "episodes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("podcast_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("audio_url", sa.String(length=2048), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("full_transcript", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["podcast_id"], ["podcasts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_episodes_podcast_id", "episodes", ["podcast_id"])

    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transcript_segments_episode_id", "transcript_segments", ["episode_id"]
    )

    op.create_table(
        "episode_features",
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("hook_length_seconds", sa.Float(), nullable=True),
        sa.Column("intro_length_seconds", sa.Float(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=True),
        sa.Column("speaking_turns", sa.Integer(), nullable=True),
        sa.Column("host_guest_ratio", sa.Float(), nullable=True),
        sa.Column("topic_shift_count", sa.Integer(), nullable=True),
        sa.Column("cta_present", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("episode_id"),
    )

    op.create_table(
        "podcast_taxonomy_map",
        sa.Column("podcast_id", sa.Integer(), nullable=False),
        sa.Column("taxonomy_node_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["podcast_id"], ["podcasts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["taxonomy_node_id"], ["taxonomy_nodes.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("podcast_id", "taxonomy_node_id"),
        sa.UniqueConstraint(
            "podcast_id", "taxonomy_node_id", name="uq_podcast_taxonomy"
        ),
    )


def downgrade() -> None:
    op.drop_table("podcast_taxonomy_map")
    op.drop_table("episode_features")
    op.drop_index("ix_transcript_segments_episode_id", table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_index("ix_episodes_podcast_id", table_name="episodes")
    op.drop_table("episodes")
    op.drop_index("ix_taxonomy_nodes_parent_id", table_name="taxonomy_nodes")
    op.drop_table("taxonomy_nodes")
    op.drop_table("podcasts")
