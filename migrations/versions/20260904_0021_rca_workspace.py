"""Add the three workspace tables (`W1-02`, `RCA-005` `FR-109`--`FR-113`).

`W1-01` wrote the domain contracts and held no persistence. This revision gives them rows:
`rca_workspace_dataset_versions`, `rca_workspace_analysis_runs` and
`rca_workspace_artifact_bindings`.

**`down_revision` is `20260822_0020`**, the `KHEPRI-DEC-008` portability revision, which is the head
this slice inherits. `FR-113` requires one Alembic head and
`tests/test_rca001_session_persistence.py` pins the identifier deliberately rather than counting
heads generically -- a count alone would pass for a revision chained onto the wrong parent. That pin
and the head stated in `specs/001-rca-001-commercial-identity/STATUS.md` are updated in this same
commit, because both are assertions about what the head *is* and a stale one sends the next slice to
the wrong parent.

**Values are spelled literally here and built from `RETENTION_STATES` in the model, deliberately.**
The same split as `20260814_0015` and `20260818_0018`: a migration is a historical record of what
the schema became on a given day, and importing a module constant into one would let a later edit to
that constant silently rewrite history. The model does the opposite, rendering the constraint from
`RETENTION_STATES` so the domain and the column cannot drift.
`test_the_retention_check_agrees_between_the_migration_and_the_model` is what keeps the two
spellings honest.

**The scope foreign key targets `rca_isolation_scopes.owner_id`, a `UNIQUE` column rather than that
table's primary key.** `organization_id` is the primary key there, and `RCA-001` `FR-033` forbids a
commercial identifier appearing in or being derivable from a workspace key -- an `organization_id`
column on these tables would be that identifier arriving by another name. PostgreSQL admits a
foreign key onto any uniquely-constrained column, and `uq_rca_scope_owner` is that constraint.

**A child's parent key is composite, so a cross-scope row is unrepresentable.** `owner_id` and
`version_id` as two independent foreign keys are checked independently, which lets a run claim one
scope while pointing at another scope's dataset version -- both constraints satisfied, the row
appearing in the child's scope and referencing a foreign tenant. `FR-109` isolation cannot rest on
callers pairing them correctly, so the run references `(owner_id, version_id)` and the binding
references `(owner_id, run_id)`. The two `UNIQUE (owner_id, <id>)` constraints exist only to give
those composite references a target: each `<id>` is already unique alone as a primary key, so
neither constrains anything new.

**Constraints considered and refused, per `KHEPRI-DEC-020` §4:**

*No `UNIQUE (run_id, surface)` on the bindings table.* It reads as the obvious constraint --
one web artifact per run -- but `RRA-006` publishes a bundle together or not at all, and
`FR-111` reads a run naming fewer than every required surface as incomplete. Completeness is
a property of the *set* a run names, which per-row uniqueness cannot express and would only
appear to. Encoding a cardinality nobody requires is the defect `R7-02` spent a slice
unwinding; `W1-04` reads the set.

*No `UNIQUE (owner_id, ...)` anywhere.* One scope holds many dataset versions and many runs by
design -- that is what a history spine is (`FR-117`) -- and `20260817_0017` exists precisely because
an earlier `UNIQUE (owner_id)` had to be dropped so one commercial scope could hold more than one
analysis. Restating that mistake in a new table would be a regression with a migration number.

*`ON DELETE RESTRICT`, never `CASCADE`, on all five foreign keys.* `FR-112` makes these rows
append-only. A cascade would delete workspace history as a silent side effect of a delete elsewhere,
where `KHEPRI-DEC-033` requires deletion to be an operation that records evidence -- which `W1-07`
writes. `RESTRICT` turns an unconsidered delete into a failure rather than a silent loss.

**Nothing to backfill.** None of the three tables has existed before and no earlier column holds
workspace state, so the upgrade creates and the downgrade drops. No data is at risk in either
direction. The drops are ordered child-first, because the foreign keys are `RESTRICT`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0021"
down_revision: str | None = "20260822_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled literally rather than imported -- see the module docstring.
_RETENTION_CHECK = "retention_state IN ('active', 'tombstoned')"


def upgrade() -> None:
    """Three tables and their indexes.

    Delegating to per-table helpers rather than spelling the DDL inline, following
    `20260812_0010`, which creates four tables the same way. The shape is not cosmetic: it keeps
    each table's columns and constraints readable as one unit, which is what a reader auditing a
    schema change is looking for.
    """
    op.create_table("rca_workspace_dataset_versions", *_version_columns(), *_version_constraints())
    _index("rca_workspace_dataset_versions", "owner_id")

    op.create_table("rca_workspace_analysis_runs", *_run_columns(), *_run_constraints())
    _index("rca_workspace_analysis_runs", "owner_id")
    _index("rca_workspace_analysis_runs", "version_id")

    op.create_table("rca_workspace_artifact_bindings", *_binding_columns(), *_binding_constraints())
    _index("rca_workspace_artifact_bindings", "owner_id")
    _index("rca_workspace_artifact_bindings", "run_id")


def _index(table: str, column: str) -> None:
    op.create_index(f"ix_{table}_{column}", table, [column])


def _scope_foreign_key(name: str) -> sa.ForeignKeyConstraint:
    """`owner_id` onto the isolation scope. `RESTRICT` -- see the module docstring."""
    return sa.ForeignKeyConstraint(
        ["owner_id"],
        ["rca_isolation_scopes.owner_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _retention_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("retention_state", sa.String(), nullable=False),
        sa.Column("retention_changed_at", sa.DateTime(timezone=True), nullable=True),
    )


def _version_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("upload_plaintext_digest", sa.String(), nullable=False),
        sa.Column("upload_ciphertext_digest", sa.String(), nullable=False),
        sa.Column("upload_size_bytes", sa.Integer(), nullable=False),
        sa.Column("upload_media_type", sa.String(), nullable=False),
        sa.Column("manifest_digest", sa.String(), nullable=False),
        sa.Column("mapping_version", sa.String(), nullable=False),
        sa.Column("admission_outcome", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        # Nullable because sealing is an event, not a creation argument: `KHEPRI-DEC-033` starts
        # the raw upload's seven-day purge clock at sealing, so a version sealed at creation would
        # start a deletion clock for content whose facts do not exist yet.
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        *_retention_columns(),
    )


def _version_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("version_id"),
        _scope_foreign_key("fk_rca_workspace_version_scope"),
        sa.CheckConstraint(_RETENTION_CHECK, name="ck_rca_workspace_version_retention"),
        sa.UniqueConstraint("owner_id", "version_id", name="uq_rca_workspace_version_scope"),
    )


def _run_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("version_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        # Nullable together: a run is created incomplete, because `FR-111` puts the digest and the
        # governed versions on the real pipeline rather than on whoever starts the run.
        sa.Column("package_digest", sa.String(), nullable=True),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("formula_version", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_retention_columns(),
    )


def _run_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("run_id"),
        _scope_foreign_key("fk_rca_workspace_run_scope"),
        sa.ForeignKeyConstraint(
            ["owner_id", "version_id"],
            [
                "rca_workspace_dataset_versions.owner_id",
                "rca_workspace_dataset_versions.version_id",
            ],
            name="fk_rca_workspace_run_version",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(_RETENTION_CHECK, name="ck_rca_workspace_run_retention"),
        sa.UniqueConstraint("owner_id", "run_id", name="uq_rca_workspace_run_scope"),
    )


def _binding_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("binding_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("surface", sa.String(), nullable=False),
        sa.Column("artifact_digest", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
    )


def _binding_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("binding_id"),
        _scope_foreign_key("fk_rca_workspace_binding_scope"),
        sa.ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["rca_workspace_analysis_runs.owner_id", "rca_workspace_analysis_runs.run_id"],
            name="fk_rca_workspace_binding_run",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    """Child-first, because every foreign key here is `RESTRICT`.

    Dropping the versions table before the runs that reference it would fail on the constraint
    rather than cascade -- which is the same property that makes `RESTRICT` the right choice for
    the upgrade, seen from the other direction.
    """
    op.drop_table("rca_workspace_artifact_bindings")
    op.drop_table("rca_workspace_analysis_runs")
    op.drop_table("rca_workspace_dataset_versions")
