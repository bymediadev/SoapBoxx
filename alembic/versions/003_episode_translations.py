"""episode_translations — Day 7

Revision ID: 003
Revises: 002
Create Date: 2026-05-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episode_translations",
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=8), nullable=False),
        sa.Column("insight_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("episode_id"),
    )


def downgrade() -> None:
    op.drop_table("episode_translations")
