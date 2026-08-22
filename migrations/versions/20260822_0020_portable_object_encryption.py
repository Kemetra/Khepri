"""Provider-neutral object encryption metadata.

`KHEPRI-DEC-008` replaces the five AWS provider-header proofs with application-side
envelope encryption. Two durable consequences follow, and this migration is both.

**`encryption_algorithm` may no longer be an AWS product name.** Both tables
carried `CHECK (encryption_algorithm = 'aws:kms')`, which is a portability
violation written into the database: no S3-compatible store outside AWS can
produce a row satisfying it. The constraint is replaced rather than dropped,
because the column still has exactly one governed value -- now the algorithm the
application performs.

**`kms_key_id` is removed rather than renamed.** It recorded which external
customer managed key encrypted the object, which is a fact only SSE-KMS has. Under
envelope encryption the wrapped per-object data key travels inside the object
itself, so there is no external key identifier to record and a renamed column
would name nothing. `ciphertext_sha256_hex` and `envelope_version` take its place
and both carry real meaning: the first is the read-back proof `KHEPRI-DEC-008`
requires, and the second lets a future format change be detected rather than
guessed.

**Why the new columns are NOT NULL with no server default.** No deployment
definition exists, so no environment exists, so there are no rows -- the decision
states this directly, and `governance/` holds no descriptor. A server default
would be a value invented for rows that cannot exist, and it would let a future
insert omit the read-back proof and still succeed.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# Annotated in the style every other revision uses. The head-consistency guard parses
# `down_revision` with a regex that expects either an annotation or no space before the
# `=`; an unannotated `down_revision = "..."` is unparseable to it, which silently leaves
# the parent unrecorded and `20260821_0019` still looking like a head.
revision: str = "20260822_0020"
down_revision: str | None = "20260821_0019"
branch_labels: str | None = None
depends_on: str | None = None

_ALGORITHM = "AES-256-GCM"

_UPLOADS = "rra_uploads"
_ARTIFACTS = "rra_report_artifacts"


def upgrade() -> None:
    _forward(_UPLOADS, "ck_upload_kms_encryption", "ck_upload_envelope_encryption", "upload")
    op.drop_constraint("ck_report_artifact_storage_identity", _ARTIFACTS, type_="check")
    op.create_check_constraint(
        "ck_report_artifact_storage_identity",
        _ARTIFACTS,
        "length(object_key) > 0",
    )
    _forward(
        _ARTIFACTS,
        "ck_report_artifact_encryption",
        "ck_report_artifact_encryption",
        "report_artifact",
    )


def downgrade() -> None:
    _back(_ARTIFACTS, "ck_report_artifact_encryption", "ck_report_artifact_encryption")
    op.drop_constraint("ck_report_artifact_storage_identity", _ARTIFACTS, type_="check")
    op.create_check_constraint(
        "ck_report_artifact_storage_identity",
        _ARTIFACTS,
        "length(object_key) > 0 AND length(kms_key_id) > 0",
    )
    _back(_UPLOADS, "ck_upload_envelope_encryption", "ck_upload_kms_encryption")


def _forward(table: str, old_check: str, new_check: str, prefix: str) -> None:
    """Retire the AWS key column and admit the envelope columns."""
    op.drop_constraint(old_check, table, type_="check")
    op.drop_column(table, "kms_key_id")
    op.add_column(table, sa.Column("envelope_version", sa.Integer(), nullable=False))
    op.add_column(
        table,
        sa.Column("ciphertext_sha256_hex", sa.String(length=64), nullable=False),
    )
    op.create_check_constraint(new_check, table, f"encryption_algorithm = '{_ALGORITHM}'")
    op.create_check_constraint(
        f"ck_{prefix}_ciphertext_sha256_length",
        table,
        "length(ciphertext_sha256_hex) = 64",
    )
    op.create_check_constraint(
        f"ck_{prefix}_envelope_version",
        table,
        "envelope_version > 0",
    )


def _back(table: str, new_check: str, old_check: str) -> None:
    prefix = "upload" if table == _UPLOADS else "report_artifact"
    op.drop_constraint(f"ck_{prefix}_envelope_version", table, type_="check")
    op.drop_constraint(f"ck_{prefix}_ciphertext_sha256_length", table, type_="check")
    op.drop_constraint(new_check, table, type_="check")
    op.drop_column(table, "ciphertext_sha256_hex")
    op.drop_column(table, "envelope_version")
    op.add_column(table, sa.Column("kms_key_id", sa.String(), nullable=False))
    op.create_check_constraint(old_check, table, "encryption_algorithm = 'aws:kms'")
