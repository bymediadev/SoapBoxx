"""Layer 2 — optional episode_audio_motion table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "episode_audio_motion",
        sa.Column("episode_id", sa.Integer(), nullable=False),
        sa.Column(
            "extractor_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column("events_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("episode_id"),
    )


def downgrade() -> None:
    op.drop_table("episode_audio_motion")
