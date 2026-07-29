"""Create RRA governed upload metadata table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0002"
down_revision: str | None = "20260729_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_session_owner_scope",
        "rra_beta_sessions",
        ["owner_id", "session_id"],
    )
    op.create_table(
        "rra_uploads",
        sa.Column("upload_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("encryption_algorithm", sa.String(), nullable=False),
        sa.Column("kms_key_id", sa.String(), nullable=False),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_upload_expiry_after_creation",
        ),
        sa.CheckConstraint(
            "encryption_algorithm = 'aws:kms'",
            name="ck_upload_kms_encryption",
        ),
        sa.CheckConstraint(
            "length(sha256_hex) = 64",
            name="ck_upload_sha256_length",
        ),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 52428800",
            name="ck_upload_size_range",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_upload_session_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("upload_id"),
        sa.UniqueConstraint("object_key"),
        sa.UniqueConstraint("session_id", name="uq_upload_session"),
    )
    op.create_index(
        "ix_rra_uploads_expires_at",
        "rra_uploads",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_rra_uploads_expires_at", table_name="rra_uploads")
    op.drop_table("rra_uploads")
    op.drop_constraint(
        "uq_session_owner_scope",
        "rra_beta_sessions",
        type_="unique",
    )
