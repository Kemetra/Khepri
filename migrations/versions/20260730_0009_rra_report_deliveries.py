"""Create durable RRA report deliveries and content-free surface evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0009"
down_revision: str | None = "20260730_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rra_report_deliveries",
        *_delivery_columns(),
        *_delivery_constraints(),
        *_delivery_identity(),
    )
    op.create_index("ix_delivery_expiry", "rra_report_deliveries", ["expires_at"])
    op.create_table(
        "rra_report_delivery_surfaces",
        *_surface_columns(),
        *_surface_constraints(),
    )


def downgrade() -> None:
    op.drop_table("rra_report_delivery_surfaces")
    op.drop_index("ix_delivery_expiry", table_name="rra_report_deliveries")
    op.drop_table("rra_report_deliveries")


def _delivery_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("package_version", sa.String(), nullable=False),
        sa.Column("narrative_state", sa.String(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def _delivery_constraints() -> tuple[sa.CheckConstraint, ...]:
    return (
        sa.CheckConstraint(
            "expires_at > generated_at",
            name="ck_delivery_expiry_after_generation",
        ),
        sa.CheckConstraint(
            "length(bundle_id) = 64",
            name="ck_delivery_bundle_id",
        ),
        sa.CheckConstraint(
            "narrative_state IN ('included', 'refused', 'omitted')",
            name="ck_delivery_narrative_state",
        ),
    )


def _delivery_identity() -> tuple[sa.Constraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["rra_report_jobs.job_id", "rra_report_jobs.session_id"],
            name="fk_delivery_job_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_delivery_session_scope",
            ondelete="RESTRICT",
        ),
        # One delivery per job, in the primary key rather than beside it: a
        # second report for one job is the mixture of versions RRA-006 forbids.
        sa.PrimaryKeyConstraint("job_id"),
        sa.UniqueConstraint("job_id", "bundle_id", name="uq_delivery_job_bundle"),
    )


def _surface_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("surface", sa.String(), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
    )


def _surface_constraints() -> tuple[sa.Constraint, ...]:
    return (
        sa.CheckConstraint(
            "length(content_digest) = 64",
            name="ck_delivery_surface_digest",
        ),
        sa.CheckConstraint(
            "surface IN ('web', 'pdf', 'excel')",
            name="ck_delivery_surface_name",
        ),
        # Composite, so a surface built for another bundle cannot exist beside
        # this delivery at all.
        sa.ForeignKeyConstraint(
            ["job_id", "bundle_id"],
            [
                "rra_report_deliveries.job_id",
                "rra_report_deliveries.bundle_id",
            ],
            name="fk_delivery_surface_bundle",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id", "surface"),
    )
