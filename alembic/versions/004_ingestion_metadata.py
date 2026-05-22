"""Ingestion metadata: descriptions + raw_rss_json

Revision ID: 004
Revises: 003
Create Date: 2026-05-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("podcasts", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("episodes", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("episodes", sa.Column("raw_rss_json", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("episodes", "raw_rss_json")
    op.drop_column("episodes", "description")
    op.drop_column("podcasts", "description")
