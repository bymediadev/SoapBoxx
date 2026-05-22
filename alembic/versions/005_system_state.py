"""System state: episode pipeline_status + system_events

Revision ID: 005
Revises: 004
Create Date: 2026-05-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "episodes",
        sa.Column("pipeline_status", sa.String(length=32), nullable=False, server_default="new"),
    )
    op.add_column("episodes", sa.Column("pipeline_error", sa.Text(), nullable=True))
    op.add_column(
        "episodes",
        sa.Column(
            "pipeline_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_episodes_pipeline_status", "episodes", ["pipeline_status"])

    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("podcast_id", sa.Integer(), nullable=True),
        sa.Column("episode_id", sa.Integer(), nullable=True),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["podcast_id"], ["podcasts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_created_at", "system_events", ["created_at"])
    op.create_index("ix_system_events_event_type", "system_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_system_events_event_type", table_name="system_events")
    op.drop_index("ix_system_events_created_at", table_name="system_events")
    op.drop_table("system_events")
    op.drop_index("ix_episodes_pipeline_status", table_name="episodes")
    op.drop_column("episodes", "pipeline_updated_at")
    op.drop_column("episodes", "pipeline_error")
    op.drop_column("episodes", "pipeline_status")
