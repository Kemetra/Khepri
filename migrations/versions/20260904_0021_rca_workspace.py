"""Add the three workspace tables (`W1-02`, `RCA-005` `FR-109`--`FR-113`).

`W1-01` wrote the domain contracts and held no persistence. This revision gives them rows:
`rca_workspace_dataset_versions`, `rca_workspace_analysis_runs`, `rca_workspace_artifact_bindings`,
`rca_workspace_source_profiles` and `rca_workspace_tombstones` -- the five the `W1-02` plan assigns
("tables for dataset versions, runs, artifact bindings, source profiles and tombstones").

**The tombstone table is this slice's; the projection that fills it is `W1-03`'s.** The plan splits
them, and the split matters: `KHEPRI-DEC-033` §3 defines a tombstone by what it **may** contain,
never by what was removed, and promises a test asserting each tombstone's field set *equals* its
allowlist. That test belongs with the projection `W1-03` builds. Nothing here projects anything --
these are the columns the allowlist will fill.

One table for both subjects rather than two, because §3's two allowlists differ only in which
optional columns they populate, and a nullable union is smaller to keep correct than two tables that
must not drift. A source profile has no row here at all: §3 says "none -- purged, not tombstoned",
which is also why `SourceProfileRow` is the one workspace table exempt from the delete guard.

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
spellings honest. `state` carries the same treatment: `W1-01` published `RUN_STATES` and
nothing constrained the column, so a row written by any path other than the store could hold
a state the domain does not name -- and the read that rebuilt it would raise, breaking a whole
scoped listing rather than the one row.

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
_RUN_STATE_CHECK = "state IN ('started', 'completed', 'failed')"

#: `FR-111` binds a completed run to the package it produced. Stated in the schema as well as in
#: `RunOutcome.__post_init__`, because enforced only in the dataclass a bad row still reaches the
#: database -- and then raises on *read*, failing `analysis_runs_for_scope` for the whole scope.
#: One malformed row becomes an outage for every run in the organization. Review on `#370` traced
#: it. Conditional rather than `NOT NULL`: `failed` and `started` produced no package.
_RUN_COMPLETION_PROVENANCE_CHECK = (
    "state <> 'completed' OR ("
    "package_digest IS NOT NULL AND package_version IS NOT NULL "
    "AND formula_version IS NOT NULL AND completed_at IS NOT NULL)"
)
_TOMBSTONE_SUBJECT_CHECK = "subject_kind IN ('version', 'run')"

#: `KHEPRI-DEC-033` §3's two allowlists. A version's tombstone must leave every run-only column
#: null and a run's tombstone every version-only column, or the table would admit content §3 says
#: never survives a deletion -- a `subject_kind='version'` row carrying a run's `section_states`.
#: Written as implications because that is what a row-level `CHECK` can evaluate.
#:
#: Literal strings, like every other constraint here, following this file's convention: a migration
#: states the schema it created, and importing the model constants would let a later edit to them
#: silently change what this revision claims to have built. `test_w102_workspace_persistence.py`
#: asserts the constants and these clauses agree.
_TOMBSTONE_VERSION_FIELDS_CHECK = (
    "subject_kind <> 'version' OR ("
    "started_at IS NULL AND completed_at IS NULL AND package_digest IS NULL "
    "AND package_version IS NULL AND formula_version IS NULL AND section_states IS NULL)"
)
# `version_id` is absent from this clause on purpose: `KHEPRI-DEC-033` §3 puts a version id on
# *both* tombstone rows -- the version's own identity, and the run's link to the dataset it derived
# from -- so a run's tombstone is entitled to it. Review on `#370` found the first draft nulling it
# here, which would have made a projected run deletion lose that provenance.
_TOMBSTONE_RUN_FIELDS_CHECK = (
    "subject_kind <> 'run' OR ("
    "created_at IS NULL AND sealed_at IS NULL "
    "AND upload_plaintext_digest IS NULL AND upload_ciphertext_digest IS NULL "
    "AND upload_size_bytes IS NULL AND upload_media_type IS NULL "
    "AND manifest_digest IS NULL AND mapping_version IS NULL "
    "AND admission_outcome IS NULL)"
)


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

    op.create_table("rca_workspace_source_profiles", *_profile_columns(), *_profile_constraints())
    _index("rca_workspace_source_profiles", "owner_id")

    op.create_table("rca_workspace_tombstones", *_tombstone_columns(), *_tombstone_constraints())
    _index("rca_workspace_tombstones", "owner_id")


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
        sa.CheckConstraint(_RUN_STATE_CHECK, name="ck_rca_workspace_run_state"),
        sa.CheckConstraint(
            _RUN_COMPLETION_PROVENANCE_CHECK, name="ck_rca_workspace_run_completion_provenance"
        ),
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


def _profile_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("profile_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("source_version_id", sa.String(), nullable=False),
        # JSON text rather than a column per field: a caller-shaped mapping whose keys are not
        # knowable at migration time, and never read as authority -- `RRA-003` admits the new
        # submission, so it needs no queryable structure.
        sa.Column("column_labels", sa.Text(), nullable=False),
        sa.Column("proposed_mapping", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )


def _profile_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("profile_id"),
        _scope_foreign_key("fk_rca_workspace_profile_scope"),
        # The composite key runs and bindings already carry. `owner_id` alone lets a profile claim
        # one scope while naming a version in another, or none at all.
        sa.ForeignKeyConstraint(
            ["owner_id", "source_version_id"],
            [
                "rca_workspace_dataset_versions.owner_id",
                "rca_workspace_dataset_versions.version_id",
            ],
            name="fk_rca_workspace_profile_version",
            ondelete="RESTRICT",
        ),
    )


def _tombstone_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("tombstone_id", sa.String(), nullable=False),
        sa.Column("subject_kind", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=False),
        # A dataset version's allowlist (`KHEPRI-DEC-033` §3, row one).
        sa.Column("version_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("upload_plaintext_digest", sa.String(), nullable=True),
        sa.Column("upload_ciphertext_digest", sa.String(), nullable=True),
        sa.Column("upload_size_bytes", sa.Integer(), nullable=True),
        sa.Column("upload_media_type", sa.String(), nullable=True),
        sa.Column("manifest_digest", sa.String(), nullable=True),
        sa.Column("mapping_version", sa.String(), nullable=True),
        sa.Column("admission_outcome", sa.String(), nullable=True),
        # An analysis run's allowlist (§3, row two).
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("package_digest", sa.String(), nullable=True),
        sa.Column("package_version", sa.String(), nullable=True),
        sa.Column("formula_version", sa.String(), nullable=True),
        # Bounded rather than free `Text`: `KHEPRI-DEC-033` §3 admits "per-section state codes"
        # and excludes "any figure, series, label, narrative, refusal prose", and a tombstone is
        # immutable once written -- content that gets in cannot be taken out. The store validates
        # the JSON shape (`validate_section_states`); this length is the backstop for a row
        # arriving outside the ORM. 64 entries of two 32-character codes cannot exceed it.
        sa.Column("section_states", sa.String(length=4096), nullable=True),
    )


def _tombstone_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("tombstone_id"),
        _scope_foreign_key("fk_rca_workspace_tombstone_scope"),
        sa.CheckConstraint(_TOMBSTONE_SUBJECT_CHECK, name="ck_rca_workspace_tombstone_subject"),
        sa.CheckConstraint(
            _TOMBSTONE_VERSION_FIELDS_CHECK, name="ck_rca_workspace_tombstone_version_fields"
        ),
        sa.CheckConstraint(
            _TOMBSTONE_RUN_FIELDS_CHECK, name="ck_rca_workspace_tombstone_run_fields"
        ),
    )


def downgrade() -> None:
    """Child-first, because every foreign key here is `RESTRICT`.

    Dropping the versions table before the runs that reference it would fail on the constraint
    rather than cascade -- which is the same property that makes `RESTRICT` the right choice for
    the upgrade, seen from the other direction.
    """
    op.drop_table("rca_workspace_tombstones")
    op.drop_table("rca_workspace_source_profiles")
    op.drop_table("rca_workspace_artifact_bindings")
    op.drop_table("rca_workspace_analysis_runs")
    op.drop_table("rca_workspace_dataset_versions")
