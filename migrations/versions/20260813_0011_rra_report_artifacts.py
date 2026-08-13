"""Create encrypted RRA report artifact metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0011"
down_revision: str | None = "20260812_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _create_artifact_table()
    _widen_deletion_evidence()


def _create_artifact_table() -> None:
    op.create_table(
        "rra_report_artifacts",
        *_columns(),
        *_constraints(),
    )
    op.create_index(
        "ix_report_artifact_expiry", "rra_report_artifacts", ["expires_at"]
    )


def _widen_deletion_evidence() -> None:
    op.drop_constraint(
        "ck_evidence_target_kind", "rra_deletion_evidence", type_="check"
    )
    op.drop_constraint(
        "uq_evidence_deletion_attempt", "rra_deletion_evidence", type_="unique"
    )
    op.create_check_constraint(
        "ck_evidence_target_kind",
        "rra_deletion_evidence",
        "target_kind IN ('input', 'report_artifact')",
    )
    op.create_unique_constraint(
        "uq_evidence_deletion_attempt_target",
        "rra_deletion_evidence",
        ["deletion_id", "attempt_number", "target_kind", "target_id"],
    )


def downgrade() -> None:
    _narrow_deletion_evidence()
    _drop_artifact_table()


def _narrow_deletion_evidence() -> None:
    op.drop_constraint(
        "uq_evidence_deletion_attempt_target",
        "rra_deletion_evidence",
        type_="unique",
    )
    op.drop_constraint(
        "ck_evidence_target_kind", "rra_deletion_evidence", type_="check"
    )
    op.create_check_constraint(
        "ck_evidence_target_kind",
        "rra_deletion_evidence",
        "target_kind = 'input'",
    )
    op.create_unique_constraint(
        "uq_evidence_deletion_attempt",
        "rra_deletion_evidence",
        ["deletion_id", "attempt_number"],
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
