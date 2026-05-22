"""Add episode guid for RSS deduplication — Day 3

Revision ID: 002
Revises: 001
Create Date: 2026-05-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("episodes", sa.Column("guid", sa.String(length=512), nullable=True))
    op.create_index("ix_episodes_guid", "episodes", ["guid"], unique=False)
    op.create_unique_constraint(
        "uq_episode_podcast_guid", "episodes", ["podcast_id", "guid"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_episode_podcast_guid", "episodes", type_="unique")
    op.drop_index("ix_episodes_guid", table_name="episodes")
    op.drop_column("episodes", "guid")
