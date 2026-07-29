"""Create RRA dataset profiles with mapping and admissibility provenance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0004"
down_revision: str | None = "20260729_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rra_dataset_profiles",
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("upload_id", sa.String(), nullable=False),
        sa.Column("profile_version", sa.String(), nullable=False),
        sa.Column("mapping_version", sa.String(), nullable=False),
        sa.Column("source_sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("profile_digest", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("admissible", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.CheckConstraint("column_count > 0", name="ck_profile_column_count"),
        sa.CheckConstraint("length(profile_digest) = 64", name="ck_profile_digest"),
        sa.CheckConstraint("row_count >= 0", name="ck_profile_row_count"),
        sa.CheckConstraint(
            "length(source_sha256_hex) = 64",
            name="ck_profile_source_digest",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_profile_session_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("profile_id"),
        sa.UniqueConstraint("session_id", name="uq_profile_session"),
        sa.UniqueConstraint("upload_id", name="uq_profile_upload"),
    )


def downgrade() -> None:
    op.drop_table("rra_dataset_profiles")
