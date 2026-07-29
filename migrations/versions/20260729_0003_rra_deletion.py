"""Create RRA deletion jobs and content-free evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0003"
down_revision: str | None = "20260729_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rra_beta_sessions",
        sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "rra_beta_sessions",
        sa.Column("content_deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_session_deletion_order",
        "rra_beta_sessions",
        "content_deleted_at IS NULL OR deletion_requested_at IS NOT NULL",
    )
    op.create_table(
        "rra_deletion_jobs",
        sa.Column("deletion_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_count >= 0", name="ck_deletion_attempt_count"),
        sa.CheckConstraint(
            "(state = 'complete') = (completed_at IS NOT NULL)",
            name="ck_deletion_completion",
        ),
        sa.CheckConstraint(
            "reason IN ('immediate', 'expiry')",
            name="ck_deletion_reason",
        ),
        sa.CheckConstraint(
            "(state = 'retryable') = (next_retry_at IS NOT NULL)",
            name="ck_deletion_retry_schedule",
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'retryable', 'complete')",
            name="ck_deletion_state",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_deletion_session_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("deletion_id"),
        sa.UniqueConstraint("session_id", name="uq_deletion_session"),
    )
    op.create_index(
        "ix_rra_deletion_jobs_next_retry_at",
        "rra_deletion_jobs",
        ["next_retry_at"],
    )
    op.create_table(
        "rra_deletion_evidence",
        sa.Column("evidence_id", sa.String(), nullable=False),
        sa.Column("deletion_id", sa.String(), nullable=False),
        sa.Column("target_kind", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("location_digest", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_evidence_attempt_number",
        ),
        sa.CheckConstraint(
            "length(content_digest) = 64",
            name="ck_evidence_content_digest",
        ),
        sa.CheckConstraint(
            "(outcome = 'failed') = (error_code IS NOT NULL)",
            name="ck_evidence_error_outcome",
        ),
        sa.CheckConstraint(
            "length(location_digest) = 64",
            name="ck_evidence_location_digest",
        ),
        sa.CheckConstraint(
            "outcome IN ('deleted', 'failed')",
            name="ck_evidence_outcome",
        ),
        sa.CheckConstraint(
            "target_kind = 'input'",
            name="ck_evidence_target_kind",
        ),
        sa.ForeignKeyConstraint(
            ["deletion_id"],
            ["rra_deletion_jobs.deletion_id"],
            name="fk_evidence_deletion",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evidence_id"),
        sa.UniqueConstraint(
            "deletion_id",
            "attempt_number",
            name="uq_evidence_deletion_attempt",
        ),
    )
    op.create_index(
        "ix_rra_deletion_evidence_deletion_id",
        "rra_deletion_evidence",
        ["deletion_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rra_deletion_evidence_deletion_id",
        table_name="rra_deletion_evidence",
    )
    op.drop_table("rra_deletion_evidence")
    op.drop_index(
        "ix_rra_deletion_jobs_next_retry_at",
        table_name="rra_deletion_jobs",
    )
    op.drop_table("rra_deletion_jobs")
    op.drop_constraint(
        "ck_session_deletion_order",
        "rra_beta_sessions",
        type_="check",
    )
    op.drop_column("rra_beta_sessions", "content_deleted_at")
    op.drop_column("rra_beta_sessions", "deletion_requested_at")
