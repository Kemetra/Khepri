"""Move existing workspace-bound RRA content off the beta expiry timer.

DEC-033 retains facts and report artifacts with their workspace run.  Rows
created before issue #429 was fixed still carry the invitation beta's seven-day
deadline, so deploying only the new write path would leave those runs exposed.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0030"
down_revision: str | None = "20260906_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONTENT_END = datetime(9999, 12, 31, tzinfo=UTC)


def _promote_sessions() -> None:
    op.execute(
        sa.text(
            """
            UPDATE rra_beta_sessions AS session
            SET content_expires_at = :content_end
            WHERE session.deletion_requested_at IS NULL
              AND session.content_deleted_at IS NULL
              AND (
                EXISTS (
                    SELECT 1
                    FROM rra_uploads AS upload
                    JOIN rca_workspace_dataset_versions AS version
                      ON version.owner_id = upload.owner_id
                     AND version.upload_ciphertext_digest = upload.ciphertext_sha256_hex
                    WHERE upload.owner_id = session.owner_id
                      AND upload.session_id = session.session_id
                )
                OR EXISTS (
                    SELECT 1
                    FROM rra_report_jobs AS job
                    JOIN rca_workspace_run_reports AS report
                      ON report.job_id = job.job_id
                     AND report.owner_id = job.owner_id
                    JOIN rca_workspace_analysis_runs AS run
                      ON run.run_id = report.run_id
                     AND run.owner_id = report.owner_id
                    WHERE job.owner_id = session.owner_id
                      AND job.session_id = session.session_id
                )
              )
            """
        ).bindparams(content_end=_CONTENT_END)
    )


def _promote_dependants(table: str) -> None:
    statement = sa.text(
        f"""
        UPDATE {table} AS content
        SET expires_at = :content_end
        WHERE EXISTS (
            SELECT 1
            FROM rra_beta_sessions AS session
            WHERE session.owner_id = content.owner_id
              AND session.session_id = content.session_id
              AND session.content_expires_at = :content_end
        )
        """
    ).bindparams(content_end=_CONTENT_END)
    op.execute(statement)


def upgrade() -> None:
    _promote_sessions()
    for table in ("rra_uploads", "rra_report_deliveries", "rra_report_artifacts"):
        _promote_dependants(table)


def downgrade() -> None:
    """No-op: an old beta deadline cannot be reconstructed without shortening live content."""
