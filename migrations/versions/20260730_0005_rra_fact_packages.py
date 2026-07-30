"""Create RRA fact packages bound to their profile and source digest."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0005"
down_revision: str | None = "20260729_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rra_fact_packages",
        sa.Column("package_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("formula_version", sa.String(), nullable=False),
        sa.Column("mapping_version", sa.String(), nullable=False),
        sa.Column("profile_digest", sa.String(length=64), nullable=False),
        sa.Column("source_sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("package_digest", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.CheckConstraint("length(package_digest) = 64", name="ck_package_digest"),
        sa.CheckConstraint(
            "length(profile_digest) = 64",
            name="ck_package_profile_digest",
        ),
        sa.CheckConstraint("row_count >= 0", name="ck_package_row_count"),
        sa.CheckConstraint(
            "length(source_sha256_hex) = 64",
            name="ck_package_source_digest",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["rra_dataset_profiles.profile_id"],
            name="fk_package_profile",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_package_session_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("package_id"),
        sa.UniqueConstraint(
            "profile_id",
            "package_version",
            "formula_version",
            "mapping_version",
            name="uq_package_profile_versions",
        ),
    )
    op.create_index("ix_package_session", "rra_fact_packages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_package_session", table_name="rra_fact_packages")
    op.drop_table("rra_fact_packages")
