"""Create RRA invitation and beta session tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rra_invitations",
        sa.Column("invitation_id", sa.String(), nullable=False),
        sa.Column("secret_salt", sa.LargeBinary(), nullable=False),
        sa.Column("secret_digest", sa.LargeBinary(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("invitation_id"),
    )
    op.create_index(
        "ix_rra_invitations_expires_at",
        "rra_invitations",
        ["expires_at"],
    )
    op.create_table(
        "rra_beta_sessions",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_version", sa.String(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(consent_version IS NULL) = (consented_at IS NULL)",
            name="ck_session_consent_complete",
        ),
        sa.CheckConstraint(
            "content_expires_at > created_at",
            name="ck_session_expiry_after_creation",
        ),
        sa.PrimaryKeyConstraint("session_id"),
        sa.UniqueConstraint("owner_id"),
    )
    op.create_index(
        "ix_rra_beta_sessions_content_expires_at",
        "rra_beta_sessions",
        ["content_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rra_beta_sessions_content_expires_at",
        table_name="rra_beta_sessions",
    )
    op.drop_table("rra_beta_sessions")
    op.drop_index("ix_rra_invitations_expires_at", table_name="rra_invitations")
    op.drop_table("rra_invitations")
