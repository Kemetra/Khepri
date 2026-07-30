"""Create durable RRA report-job state, leases, and retry bounds."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rra_report_jobs",
        *_columns(),
        *_state_constraints(),
        *_boundary_constraints(),
        *_identity_constraints(),
    )
    op.create_index(
        "ix_report_job_available",
        "rra_report_jobs",
        ["state", "available_at"],
    )
    op.create_index(
        "ix_report_job_lease_expiry",
        "rra_report_jobs",
        ["lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_report_job_lease_expiry", table_name="rra_report_jobs")
    op.drop_index("ix_report_job_available", table_name="rra_report_jobs")
    op.drop_table("rra_report_jobs")


def _columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def _state_constraints() -> tuple[sa.CheckConstraint, ...]:
    return (
        sa.CheckConstraint(
            "(state IN ('succeeded', 'failed')) = (completed_at IS NOT NULL)",
            name="ck_report_job_completion",
        ),
        sa.CheckConstraint(
            "(state = 'running') = "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_report_job_lease",
        ),
        sa.CheckConstraint(
            "state IN ('queued', 'running', 'retryable', 'succeeded', 'failed')",
            name="ck_report_job_state",
        ),
    )


def _boundary_constraints() -> tuple[sa.CheckConstraint, ...]:
    return (
        sa.CheckConstraint(
            "attempt_count >= 0",
            name="ck_report_job_attempt_count",
        ),
        sa.CheckConstraint(
            "attempt_count <= max_attempts",
            name="ck_report_job_attempt_limit",
        ),
        sa.CheckConstraint(
            "available_at >= queued_at",
            name="ck_report_job_availability",
        ),
        sa.CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_report_job_idempotency_digest",
        ),
        sa.CheckConstraint(
            "max_attempts > 0",
            name="ck_report_job_max_attempts",
        ),
    )


def _identity_constraints() -> tuple[sa.Constraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_report_job_session_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_report_job_session_idempotency",
        ),
    )
