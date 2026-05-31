"""Add measurement version stamps to episode_features (triple immutability lock)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Matches backend/services/measurement_versions.py at migration time.
_FEATURE = "v1"
_EXTRACTION = "1.0.0"
_AGGREGATION = "1.1.0"


def upgrade() -> None:
    op.add_column(
        "episode_features",
        sa.Column(
            "feature_schema_version",
            sa.String(length=32),
            nullable=False,
            server_default=_FEATURE,
        ),
    )
    op.add_column(
        "episode_features",
        sa.Column(
            "extraction_version",
            sa.String(length=32),
            nullable=False,
            server_default=_EXTRACTION,
        ),
    )
    op.add_column(
        "episode_features",
        sa.Column(
            "aggregation_version",
            sa.String(length=32),
            nullable=False,
            server_default=_AGGREGATION,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE episode_features SET "
            "feature_schema_version = :f, "
            "extraction_version = :e, "
            "aggregation_version = :a"
        ).bindparams(f=_FEATURE, e=_EXTRACTION, a=_AGGREGATION)
    )


def downgrade() -> None:
    op.drop_column("episode_features", "aggregation_version")
    op.drop_column("episode_features", "extraction_version")
    op.drop_column("episode_features", "feature_schema_version")
