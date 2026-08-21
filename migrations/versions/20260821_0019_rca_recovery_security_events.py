"""Add content-free Khepri recovery security evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0019"
down_revision: str | None = "20260818_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rca_recovery_security_events",
        sa.Column("event_key_hash", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "event_key_hash", name="pk_rca_recovery_security_events"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_recovery_security_event_account",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_rca_recovery_security_events_occurred_at",
        "rca_recovery_security_events",
        ["occurred_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rca_recovery_security_events_occurred_at",
        table_name="rca_recovery_security_events",
    )
    op.drop_table("rca_recovery_security_events")
