"""Dead-letter exhausted RRA report jobs and record content-free attempt history."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0008"
down_revision: str | None = "20260730_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "rra_report_jobs",
        sa.Column("dead_letter_reason", sa.String(), nullable=True),
    )
    for name in ("ck_report_job_state", "ck_report_job_completion"):
        op.drop_constraint(name, "rra_report_jobs", type_="check")
    for name, condition in _job_constraints():
        op.create_check_constraint(name, "rra_report_jobs", condition)
    op.create_index(
        "ix_report_job_session_state",
        "rra_report_jobs",
        ["session_id", "state"],
    )
    op.create_table(
        "rra_report_job_attempts",
        *_columns(),
        *_outcome_constraints(),
        *_identity_constraints(),
    )


def downgrade() -> None:
    op.drop_table("rra_report_job_attempts")
    op.drop_index("ix_report_job_session_state", table_name="rra_report_jobs")
    for name, _ in _job_constraints():
        op.drop_constraint(name, "rra_report_jobs", type_="check")
    for name, condition in _superseded_job_constraints():
        op.create_check_constraint(name, "rra_report_jobs", condition)
    op.drop_column("rra_report_jobs", "dead_letter_reason")


def _job_constraints() -> tuple[tuple[str, str], ...]:
    return (
        (
            "ck_report_job_state",
            "state IN ("
            "'queued', 'running', 'retryable', 'succeeded', 'dead_lettered'"
            ")",
        ),
        (
            "ck_report_job_completion",
            "(state IN ('succeeded', 'dead_lettered')) = (completed_at IS NOT NULL)",
        ),
        (
            "ck_report_job_dead_letter",
            "(state = 'dead_lettered') = (dead_letter_reason IS NOT NULL)",
        ),
        (
            "ck_report_job_dead_letter_reason",
            "dead_letter_reason IS NULL OR dead_letter_reason IN ("
            "'retries_exhausted', 'content_deleted'"
            ")",
        ),
    )


def _superseded_job_constraints() -> tuple[tuple[str, str], ...]:
    return (
        (
            "ck_report_job_state",
            "state IN ('queued', 'running', 'retryable', 'succeeded', 'failed')",
        ),
        (
            "ck_report_job_completion",
            "(state IN ('succeeded', 'failed')) = (completed_at IS NOT NULL)",
        ),
    )


def _columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disposition", sa.String(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )


def _outcome_constraints() -> tuple[sa.CheckConstraint, ...]:
    return (
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_job_attempt_number",
        ),
        sa.CheckConstraint(
            "(disposition = 'retries_exhausted') = (available_at IS NULL)",
            name="ck_job_attempt_availability",
        ),
        sa.CheckConstraint(
            "disposition IN ("
            "'retry_scheduled', 'lease_reclaimed', 'retries_exhausted'"
            ")",
            name="ck_job_attempt_disposition",
        ),
    )


def _identity_constraints() -> tuple[sa.Constraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["rra_report_jobs.job_id", "rra_report_jobs.session_id"],
            name="fk_job_attempt_job_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id", "attempt_number"),
    )
