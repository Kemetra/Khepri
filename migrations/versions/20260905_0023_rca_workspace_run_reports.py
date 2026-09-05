"""Add the run-to-report link and the one-version-per-upload index (`W1-04b`, `RCA-005` `FR-110`,
`FR-111`).

A run is started in the web process when its report job is queued and completed in the worker
process when that job delivers. The worker holds a job and needs the run; this table answers it:
one row per run, naming the job that settles it, unique per job.

**Why a job identifier is stored where a session identifier is not.** `runtime/workspace.py`
keeps `session_id` out of every workspace row because a session identifier is bearer-adjacent
(`KHEPRI-DEC-015` §7). A job identifier confers nothing (`FR-023`), is derived from the scope,
session and package digest, and is already served in the report API's own addresses to the
session's owner. It is an opaque object identifier and appears on no surface, tombstone or log.

**`RESTRICT` throughout**, as `20260904_0021` records for the sibling tables: deletion is `W1-07`'s
evidenced operation, and a run that is deleted takes its link with it explicitly rather than by
cascade. The scope key follows the same reasoning as the other workspace tables.

**`down_revision` is `20260905_0022`**, `W1-04`'s audit event table, the head this slice inherits.
The pin in `tests/test_rca001_session_persistence.py` and the head stated in
`specs/001-rca-001-commercial-identity/STATUS.md` move in this same commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0023"
down_revision: str | None = "20260905_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rca_workspace_run_reports",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_rca_workspace_run_reports"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["rca_isolation_scopes.owner_id"],
            name="fk_rca_workspace_run_report_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["rca_workspace_analysis_runs.owner_id", "rca_workspace_analysis_runs.run_id"],
            name="fk_rca_workspace_run_report_run",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("job_id", name="uq_rca_workspace_run_report_job"),
    )
    op.create_index(
        "ix_rca_workspace_run_reports_owner_id", "rca_workspace_run_reports", ["owner_id"]
    )
    # One version per admitted upload in a scope, arbitrated by the database: two overlapping
    # profile requests both pass a read-then-insert, and only a constraint refuses the second
    # (review on `#375`). An index rather than a table constraint so SQLite can add it in place.
    op.create_index(
        "uq_rca_workspace_version_upload",
        "rca_workspace_dataset_versions",
        ["owner_id", "upload_ciphertext_digest"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_rca_workspace_version_upload", table_name="rca_workspace_dataset_versions")
    op.drop_index("ix_rca_workspace_run_reports_owner_id", table_name="rca_workspace_run_reports")
    op.drop_table("rca_workspace_run_reports")
