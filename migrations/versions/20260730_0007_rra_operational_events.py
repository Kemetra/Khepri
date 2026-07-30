"""Create content-free RRA operational telemetry evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0007"
down_revision: str | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_report_job_session_scope",
        "rra_report_jobs",
        ["job_id", "session_id"],
    )
    op.create_table(
        "rra_operational_events",
        *_columns(),
        *_vocabulary_constraints(),
        *_measurement_constraints(),
        *_identity_constraints(),
    )
    op.create_index(
        "ix_operational_event_job_time",
        "rra_operational_events",
        ["job_id", "recorded_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_operational_event_job_time",
        table_name="rra_operational_events",
    )
    op.drop_table("rra_operational_events")
    op.drop_constraint(
        "uq_report_job_session_scope",
        "rra_report_jobs",
        type_="unique",
    )


def _columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("fact_package_id", sa.String(), nullable=True),
        sa.Column("report_bundle_id", sa.String(), nullable=True),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("transition", sa.String(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=True),
        sa.Column("queue_time_ms", sa.BigInteger(), nullable=True),
        sa.Column("provider_latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("dataset_size_band", sa.String(), nullable=True),
        sa.Column("output_size_bytes", sa.BigInteger(), nullable=True),
    )


def _vocabulary_constraints() -> tuple[sa.CheckConstraint, ...]:
    return (
        sa.CheckConstraint(
            "stage IN ("
            "'upload_validation', 'materialization', 'profiling', 'mapping', "
            "'fact_calculation', 'narrative_generation', 'chart_rendering', "
            "'pdf_generation', 'excel_generation', 'storage', 'delivery'"
            ")",
            name="ck_operational_event_stage",
        ),
        sa.CheckConstraint(
            "transition IN ('started', 'succeeded', 'failed', 'refused')",
            name="ck_operational_event_transition",
        ),
        sa.CheckConstraint(
            "dataset_size_band IS NULL OR dataset_size_band IN "
            "('le_1_mib', 'le_10_mib', 'le_25_mib', 'le_50_mib')",
            name="ck_operational_event_dataset_band",
        ),
    )


def _measurement_constraints() -> tuple[sa.CheckConstraint, ...]:
    return (
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_operational_event_attempt",
        ),
        sa.CheckConstraint(
            "(transition = 'started') = (duration_ms IS NULL)",
            name="ck_operational_event_duration",
        ),
        sa.CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_operational_event_duration_nonnegative",
        ),
        sa.CheckConstraint(
            "queue_time_ms IS NULL OR queue_time_ms >= 0",
            name="ck_operational_event_queue_nonnegative",
        ),
        sa.CheckConstraint(
            "provider_latency_ms IS NULL OR provider_latency_ms >= 0",
            name="ck_operational_event_provider_nonnegative",
        ),
        sa.CheckConstraint(
            "output_size_bytes IS NULL OR output_size_bytes >= 0",
            name="ck_operational_event_output_nonnegative",
        ),
        sa.CheckConstraint(
            "provider_latency_ms IS NULL OR stage = 'narrative_generation'",
            name="ck_operational_event_provider_stage",
        ),
    )


def _identity_constraints() -> tuple[sa.Constraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["rra_report_jobs.job_id", "rra_report_jobs.session_id"],
            name="fk_operational_event_job_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint(
            "job_id",
            "attempt_number",
            "stage",
            "transition",
            name="uq_operational_event_transition",
        ),
    )
