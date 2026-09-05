"""Add the provenance record a completed run retains (`W1-06`, `RCA-005` `FR-119`,
`KHEPRI-DEC-033` §2).

The decision's matrix gives the provenance record its own row, living with the run. The Passport's
customer tier -- the attested period and its day boundary, coverage scope, who attested, the
admitted row count -- and one governed state code per report section are written at completion, in
the completion's transaction, so they outlive the analysis session's content horizon. Review on
`#376` found the surface reading them through session-gated services instead.

**Section columns as `20260904_0021` declares them for tombstones**: one column per section, each
`CHECK`ed against `KHEPRI-DEC-033` §3's three codes, spelled literally here and built from the
model's tuples in `schema.py`; the drift test compares the two. Here they are `NOT NULL`: a
provenance record exists only for a completed run, whose every section has an outcome.

**`RESTRICT` throughout**, as the sibling workspace tables: the record is deleted with its run by
`W1-07`, explicitly and evidenced, never as a constraint's side effect.

**`down_revision` is `20260905_0023`**, `W1-04b`'s run-to-report link, the head this slice inherits.
The pin in `tests/test_rca001_session_persistence.py` and the head stated in
`specs/001-rca-001-commercial-identity/STATUS.md` move in this same commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_0024"
down_revision: str | None = "20260905_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SECTION_COLUMNS = (
    "section_overview",
    "section_comparison",
    "section_concentration",
    "section_growth",
    "section_basket",
)
_SECTION_STATES = "('answered', 'caveated', 'refused')"


def upgrade() -> None:
    op.create_table(
        "rca_workspace_run_provenance",
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("covered_start", sa.Date(), nullable=False),
        sa.Column("covered_end", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("aggregate_scope", sa.String(), nullable=True),
        sa.Column("attested_by", sa.String(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        *(sa.Column(column, sa.String(), nullable=False) for column in _SECTION_COLUMNS),
        sa.PrimaryKeyConstraint("run_id", name="pk_rca_workspace_run_provenance"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["rca_isolation_scopes.owner_id"],
            name="fk_rca_workspace_provenance_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["rca_workspace_analysis_runs.owner_id", "rca_workspace_analysis_runs.run_id"],
            name="fk_rca_workspace_provenance_run",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "covered_end >= covered_start", name="ck_rca_workspace_provenance_period"
        ),
        sa.CheckConstraint("row_count >= 0", name="ck_rca_workspace_provenance_rows"),
        *(
            sa.CheckConstraint(
                f"{column} IN {_SECTION_STATES}", name=f"ck_rca_workspace_provenance_{column}"
            )
            for column in _SECTION_COLUMNS
        ),
    )
    op.create_index(
        "ix_rca_workspace_run_provenance_owner_id", "rca_workspace_run_provenance", ["owner_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rca_workspace_run_provenance_owner_id", table_name="rca_workspace_run_provenance"
    )
    op.drop_table("rca_workspace_run_provenance")
