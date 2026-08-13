"""Create encrypted RRA report artifact metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Renumbered from 20260813_0011 when this slice met `20260813_0011_rca_account_lifecycle` on
# `main`. Both slices were cut from 20260812_0010 in parallel and both claimed 0011, which
# Alembic reports as a `UserWarning` rather than an error -- the chain then carries two heads
# with the same id and one revision silently shadows the other. AGENTS.md gives the rule: the
# second slice to merge re-points. The two migrations touch disjoint tables (`rca_accounts`
# there, `rra_*` here), so ordering them is safe.
revision: str = "20260813_0012"
down_revision: str | None = "20260813_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_artifact_table()
    _requeue_deliveries_without_artifacts()
    _replace_deletion_evidence_constraints(
        current_unique="uq_evidence_deletion_attempt",
        replacement_unique="uq_evidence_deletion_attempt_target",
        target_check="target_kind IN ('input', 'report_artifact')",
        unique_columns=(
            "deletion_id",
            "attempt_number",
            "target_kind",
            "target_id",
        ),
    )


def downgrade() -> None:
    _discard_report_artifact_evidence()
    _replace_deletion_evidence_constraints(
        current_unique="uq_evidence_deletion_attempt_target",
        replacement_unique="uq_evidence_deletion_attempt",
        target_check="target_kind = 'input'",
        unique_columns=("deletion_id", "attempt_number"),
    )
    _drop_artifact_table()


def _requeue_deliveries_without_artifacts() -> None:
    op.execute(
        sa.text(
            """
            UPDATE rra_report_jobs
            SET state = 'queued',
                available_at = CURRENT_TIMESTAMP,
                max_attempts = max_attempts + attempt_count,
                lease_owner = NULL,
                lease_expires_at = NULL,
                completed_at = NULL,
                dead_letter_reason = NULL
            WHERE state = 'succeeded'
              AND EXISTS (
                  SELECT 1 FROM rra_report_deliveries delivery
                  WHERE delivery.job_id = rra_report_jobs.job_id
              )
              AND EXISTS (
                  SELECT 1 FROM rra_beta_sessions session
                  WHERE session.session_id = rra_report_jobs.session_id
                    AND session.content_expires_at > CURRENT_TIMESTAMP
                    AND session.deletion_requested_at IS NULL
                    AND session.content_deleted_at IS NULL
              )
            """
        )
    )


def _discard_report_artifact_evidence() -> None:
    op.execute(
        sa.text(
            "DELETE FROM rra_deletion_evidence "
            "WHERE target_kind = 'report_artifact'"
        )
    )


def _replace_deletion_evidence_constraints(
    *,
    current_unique: str,
    replacement_unique: str,
    target_check: str,
    unique_columns: tuple[str, ...],
) -> None:
    table = "rra_deletion_evidence"
    check = "ck_evidence_target_kind"
    op.drop_constraint(current_unique, table, type_="unique")
    op.drop_constraint(check, table, type_="check")
    op.create_check_constraint(check, table, target_check)
    op.create_unique_constraint(replacement_unique, table, list(unique_columns))


def _create_artifact_table() -> None:
    op.create_table(
        "rra_report_artifacts",
        *_columns(),
        *_constraints(),
    )
    op.create_index(
        "ix_report_artifact_expiry", "rra_report_artifacts", ["expires_at"]
    )


def _drop_artifact_table() -> None:
    op.drop_index("ix_report_artifact_expiry", table_name="rra_report_artifacts")
    op.drop_table("rra_report_artifacts")


def _columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("artifact_kind", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("bundle_id", sa.String(length=64), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("encryption_algorithm", sa.String(), nullable=False),
        sa.Column("kms_key_id", sa.String(), nullable=False),
    )


def _constraints() -> tuple[sa.Constraint, ...]:
    return (
        sa.CheckConstraint(
            "artifact_kind IN ("
            "'web_business_ar','web_business_en','web_evidence_ar','web_evidence_en',"
            "'pdf_ar','pdf_en','excel')",
            name="ck_report_artifact_kind",
        ),
        sa.CheckConstraint(
            "((artifact_kind IN ('web_business_ar','web_business_en') "
            "AND media_type = 'text/html; charset=utf-8' "
            "AND file_name = 'khepri-report.html') OR "
            "(artifact_kind IN ('web_evidence_ar','web_evidence_en') "
            "AND media_type = 'text/html; charset=utf-8' "
            "AND file_name = 'khepri-evidence.html') OR "
            "(artifact_kind IN ('pdf_ar','pdf_en') "
            "AND media_type = 'application/pdf' "
            "AND file_name = 'khepri-report.pdf') OR "
            "(artifact_kind = 'excel' "
            "AND media_type = 'application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet' AND file_name = 'khepri-report.xlsx'))",
            name="ck_report_artifact_metadata",
        ),
        sa.CheckConstraint("length(bundle_id) = 64", name="ck_report_artifact_bundle"),
        sa.CheckConstraint("size_bytes > 0", name="ck_report_artifact_size"),
        sa.CheckConstraint("length(sha256_hex) = 64", name="ck_report_artifact_digest"),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_report_artifact_expiry"
        ),
        sa.CheckConstraint(
            "encryption_algorithm = 'aws:kms'",
            name="ck_report_artifact_encryption",
        ),
        sa.CheckConstraint(
            "length(object_key) > 0 AND length(kms_key_id) > 0",
            name="ck_report_artifact_storage_identity",
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "bundle_id"],
            ["rra_report_deliveries.job_id", "rra_report_deliveries.bundle_id"],
            name="fk_report_artifact_delivery",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_report_artifact_session_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("job_id", "artifact_kind"),
        sa.UniqueConstraint("object_key", name="uq_report_artifact_object_key"),
    )
