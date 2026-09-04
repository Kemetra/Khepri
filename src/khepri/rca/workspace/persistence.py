"""Workspace persistence (`RCA-005` `FR-109`--`FR-113`).

Three tables and one store. `W1-01` wrote the domain contracts and held no persistence; this slice
gives them rows, and nothing else -- no service, no authorization, no computation. `W1-04` takes the
authorized operations.

**Every table is keyed by the opaque isolation scope, with a foreign key that says so.** `FR-109`
and `RCA-001` `FR-033` require the key to carry no commercial meaning and no organization
identifier. A bare `owner_id` column would let a caller write any string; the constraint onto
`rca_isolation_scopes.owner_id` is what makes it a key rather than a label. That target is a
`UNIQUE` column rather than that table's primary key -- `organization_id` is -- which a foreign key
may reference and which is deliberately the column that carries no commercial identifier.

**Retention state lives here and not on the record.** `DatasetVersion`'s docstring in `contracts.py`
commits to this: a version is "immutable once sealed; after that only its retention state changes,
which `W1-02` holds in the store rather than on this record". `FR-112` says the same from the other
side -- append-only, and "only retention state and tombstoning may change a row". So the column is
on the table, the transition is a store operation, and the sealed record read back is unchanged by
it. A retention field on the record would make retention look like content.

**The vocabulary is enforced twice, and neither is decoration.** `RETENTION_STATES` is checked in
the store, which is where a caller gets a content-free refusal rather than a driver error, and again
by a `CHECK` constraint, which is what holds when a row arrives by any other route. `W1-01` closed
exactly this defect in its `RUN_STATES` form: a tuple that only *documents* its values leaves the
constraint with prose and no code path.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from khepri.rca.persistence import Base, _utc
from khepri.rca.records import assert_sealed
from khepri.rca.workspace.contracts import (
    RUN_STARTED,
    RUN_STATES,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
    RunSubject,
    VersionLifecycle,
    _identifier,
)

# The retention states a stored object may be in. `KHEPRI-DEC-033` governs the transitions; this
# slice holds only the vocabulary and the column, because a transition is an operation and `W1-07`
# is where the lifecycle that drives it is written.
RETENTION_ACTIVE = "active"
RETENTION_TOMBSTONED = "tombstoned"
RETENTION_STATES = (RETENTION_ACTIVE, RETENTION_TOMBSTONED)

# What a tombstone row may be about. `KHEPRI-DEC-033` §3 gives two allowlists and states that a
# source profile is purged rather than tombstoned, so there is deliberately no third value.
TOMBSTONE_VERSION = "version"
TOMBSTONE_RUN = "run"
TOMBSTONE_SUBJECTS = (TOMBSTONE_VERSION, TOMBSTONE_RUN)

# Content-free, per the refusal discipline in `rca/errors.py`: it names the constraint, never the
# rejected value, so a refusal cannot echo a caller's input back into a log.
RETENTION_STATE_FAILURE = "Retention state is not one of the retention states this domain defines."


def _scope_foreign_key(name: str) -> ForeignKeyConstraint:
    """A fresh constraint binding `owner_id` to the isolation scope, for the named table.

    A function rather than a shared module constant, because a SQLAlchemy `ForeignKeyConstraint`
    is a stateful schema object that binds to exactly one table -- reusing one instance across the
    three tables raises `This ForeignKey already has a parent`. Each constraint also needs its own
    name, or PostgreSQL rejects the second `CREATE TABLE` for a duplicate identifier.

    `ondelete="RESTRICT"` throughout: `FR-112` makes these rows append-only, and a cascade would
    delete workspace history as a side effect of a delete elsewhere. `KHEPRI-DEC-033`'s deletion
    records evidence, which `W1-07` writes -- it is not something a constraint performs silently.
    """
    return ForeignKeyConstraint(
        ["owner_id"],
        ["rca_isolation_scopes.owner_id"],
        name=name,
        ondelete="RESTRICT",
    )


def _states_check(column: str, states: tuple[str, ...], name: str) -> CheckConstraint:
    """Render a vocabulary CHECK from the declared states, for the named column.

    Built from the domain's own tuple rather than spelled out, following `_role_in` in
    `rca/persistence.py`: adding a state without a migration then fails against the constraint
    rather than silently widening it. The migration spells the same values literally, because a
    migration is a historical record and importing a constant into one would let a later edit
    rewrite history.

    `column` exists because two vocabularies need this -- `retention_state`, which this slice
    introduces, and `state`, which `W1-01` published as `RUN_STATES`. The second had no schema
    constraint until review on `#370` asked for one, and the asymmetry was the defect: a row
    written by any path other than this store could hold a state the domain does not name, and the
    read that rebuilt it would raise, breaking a whole scoped listing rather than the one row.
    """
    assert all(state.isalpha() for state in states), f"states must be plain identifiers: {states}"
    assert column.replace("_", "").isalpha(), f"column must be an identifier: {column!r}"
    values = ", ".join(f"'{state}'" for state in states)
    return CheckConstraint(f"{column} IN ({values})", name=name)


def _retention_check(states: tuple[str, ...], name: str) -> CheckConstraint:
    """Render the retention CHECK from the declared states, for the named constraint.

    Built from `RETENTION_STATES` rather than spelled out, following `_role_in` in
    `rca/persistence.py` for its reason: adding a third state to the domain without a migration
    then fails against the constraint rather than silently widening it. The migration spells the
    same values literally, because a migration is a historical record and importing a constant into
    one would let a later edit rewrite history -- and a test asserts the two spellings agree.
    """
    return _states_check("retention_state", states, name)


class DatasetVersionRow(Base):
    """One admitted source, with the retention state the record deliberately does not carry."""

    __tablename__ = "rca_workspace_dataset_versions"
    __table_args__ = (
        _scope_foreign_key("fk_rca_workspace_version_scope"),
        _retention_check(RETENTION_STATES, "ck_rca_workspace_version_retention"),
        # The target a child's composite foreign key needs. Not a cardinality claim: `version_id`
        # is already unique alone as the primary key, so this constrains nothing new -- it exists
        # so `(owner_id, version_id)` is referenceable, which is what makes a cross-scope child
        # unrepresentable rather than merely untested.
        UniqueConstraint("owner_id", "version_id", name="uq_rca_workspace_version_scope"),
    )

    version_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    upload_plaintext_digest: Mapped[str] = mapped_column(String, nullable=False)
    upload_ciphertext_digest: Mapped[str] = mapped_column(String, nullable=False)
    upload_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    upload_media_type: Mapped[str] = mapped_column(String, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String, nullable=False)
    mapping_version: Mapped[str] = mapped_column(String, nullable=False)
    admission_outcome: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_state: Mapped[str] = mapped_column(String, nullable=False, default=RETENTION_ACTIVE)
    retention_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AnalysisRunRow(Base):
    """One derivation over one dataset version, `RESTRICT`-bound to it for `_scope_foreign_key`'s
    reason: a cascade would delete append-only history as a side effect of a delete elsewhere."""

    __tablename__ = "rca_workspace_analysis_runs"
    __table_args__ = (
        _scope_foreign_key("fk_rca_workspace_run_scope"),
        ForeignKeyConstraint(
            ["owner_id", "version_id"],
            [
                "rca_workspace_dataset_versions.owner_id",
                "rca_workspace_dataset_versions.version_id",
            ],
            name="fk_rca_workspace_run_version",
            ondelete="RESTRICT",
        ),
        _retention_check(RETENTION_STATES, "ck_rca_workspace_run_retention"),
        _states_check("state", RUN_STATES, "ck_rca_workspace_run_state"),
        UniqueConstraint("owner_id", "run_id", name="uq_rca_workspace_run_scope"),
    )

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    version_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    package_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    package_version: Mapped[str | None] = mapped_column(String, nullable=True)
    formula_version: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_state: Mapped[str] = mapped_column(String, nullable=False, default=RETENTION_ACTIVE)
    retention_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ArtifactBindingRow(Base):
    """One published surface of one run's bundle, bound by digest.

    **No `UNIQUE (run_id, surface)`, and that is the decision rather than an omission.** It would
    read as the right constraint -- one web artifact per run -- but `RRA-006` publishes a bundle
    together or not at all, and `FR-111` reads a run naming fewer than every required surface as
    incomplete. Completeness is therefore a property of the *set* a run names, which a per-row
    uniqueness constraint cannot express and would only appear to. Encoding a cardinality nobody
    requires is the defect `R7-02` spent a slice unwinding; the check belongs where `W1-04` reads
    the set.
    """

    __tablename__ = "rca_workspace_artifact_bindings"
    __table_args__ = (
        _scope_foreign_key("fk_rca_workspace_binding_scope"),
        ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["rca_workspace_analysis_runs.owner_id", "rca_workspace_analysis_runs.run_id"],
            name="fk_rca_workspace_binding_run",
            ondelete="RESTRICT",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    surface: Mapped[str] = mapped_column(String, nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


# The only columns an `UPDATE` may touch after a row is written. `FR-112`: dataset versions and
# runs are append-only, and "only retention state and tombstoning may change a row".
MUTABLE_COLUMNS = frozenset({"retention_state", "retention_changed_at", "sealed_at"})

# What `complete_analysis_run` writes, and nothing else may. `FR-112` makes content immutable
# "after sealing or completion" -- not after writing -- and `W1-01` creates a run *incomplete* by
# design, because `FR-111` puts the digest and the governed versions on the real pipeline. So the
# transition from `started` to a terminal state is required rather than a violation, and these are
# the only columns it may touch.
COMPLETION_COLUMNS = frozenset(
    {"state", "package_digest", "package_version", "formula_version", "completed_at"}
)

APPEND_ONLY_FAILURE = "A workspace record's content cannot change after it is written."
RESEAL_FAILURE = "A sealed version cannot be sealed again."
RECOMPLETE_FAILURE = "A run that has left the started state cannot be completed again."
DELETE_FAILURE = "A workspace record is removed through its retention lifecycle, not deleted."
TOMBSTONE_FAILURE = "A tombstoned record cannot return to an earlier retention state."


def _refuse_delete(_mapper, _connection, _target: object) -> None:
    """Refuse an ordinary `DELETE`, which `RESTRICT` does not cover.

    `ondelete="RESTRICT"` protects a row that something *references*. A dataset version with no
    runs, or any binding, has no referent and deletes cleanly -- so the append-only guarantee held
    only for rows that happened to have children. Review on `#370` found it.

    `FR-112` makes these rows append-only and `KHEPRI-DEC-033` moves them out of use by
    tombstoning rather than erasure, because deletion has to leave evidence. A row erased by an
    ordinary `DELETE` leaves none, and the retention state this slice added would have nothing to
    describe.

    `W1-07` writes the lifecycle that legitimately removes rows -- the retention sweep and the
    backup-aware purge. It will need an exemption from this listener, which is the right shape: an
    operation that deletes should have to say so, rather than every session being able to.

    Like `_refuse_content_update`, this is a mapper event: it binds ORM deletes, not bulk DML or
    raw SQL, and database-boundary enforcement belongs with `W1-07`.
    """
    raise ValueError(DELETE_FAILURE)


def _one_way(target: object, column: str, forbidden_prior: object) -> bool:
    """Whether a change to `column` moves it away from a value it may only leave once.

    The listener sees both sides of the change, so a one-way transition is expressible here rather
    than by writing around the guard. `sealed_at` may go from `None` to an instant and never move
    again -- `KHEPRI-DEC-033` starts the seven-day raw-upload purge clock at the first sealing, and
    re-sealing would push a deletion deadline outward. `retention_state` may not leave
    `tombstoned`, or a tombstone is an undoable soft delete and a later read presents a row the
    decision says is gone.
    """
    history = sa_inspect(target).attrs[column].history
    return history.deleted == [forbidden_prior]


class SourceProfileRow(Base):
    """Descriptive metadata from a prior version, offered for re-attestation (`FR-115`).

    **Mutable, and not append-only.** Every other table here holds a record the domain acts on;
    a profile is metadata a surface reads to pre-fill a form. `FR-115` says the check runs on what
    is submitted, so a profile carries no authority and freezing it would protect nothing.

    **Purged rather than tombstoned**, which is `KHEPRI-DEC-033` §3 stating it outright: the
    tombstone table has rows for dataset versions and runs and the profile row reads
    "none -- purged, not tombstoned". §3 gives the reason -- the live profile holds sanitized
    customer column headers and min/max values, and none of it may survive a deletion. So this is
    the one workspace table exempt from `_refuse_delete`; a blanket guard would have made the purge
    the decision prescribes impossible.

    `proposed_mapping` is stored as JSON text rather than as a column per field, because it is a
    caller-shaped mapping whose keys are not knowable at migration time. It is never read as
    authority -- `RRA-003` admits the new submission -- so it needs no queryable structure.
    """

    __tablename__ = "rca_workspace_source_profiles"
    __table_args__ = (_scope_foreign_key("fk_rca_workspace_profile_scope"),)

    profile_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_version_id: Mapped[str] = mapped_column(String, nullable=False)
    column_labels: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_mapping: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkspaceTombstoneRow(Base):
    """What remains after a deletion: `KHEPRI-DEC-033` §3's allowlist, and nothing else.

    **Defined by what it may contain, never by what was removed.** §3 is explicit about why -- the
    live records hold sanitized column headers, free text and figures, and a tombstone built by
    *removing* fields would let a new field on the live record arrive here by default.

    One table for both subjects rather than two, because §3's two allowlists differ only in which
    optional columns they populate, and the nullable union is the smaller thing to keep correct
    than two tables that must not drift. `subject_kind` says which allowlist a row belongs to, and
    `W1-03` builds the projection that fills it.

    **`W1-03` owns the allowlist, this slice owns the table.** The plan splits them deliberately:
    the equality test that `KHEPRI-DEC-033` §3 promises -- each tombstone's field set equals its
    allowlist exactly -- is `W1-03`'s to write against the projection it builds. Nothing here
    projects anything.

    A source profile has no row here at all. §3: "none -- purged, not tombstoned".
    """

    __tablename__ = "rca_workspace_tombstones"
    __table_args__ = (
        _scope_foreign_key("fk_rca_workspace_tombstone_scope"),
        _states_check("subject_kind", TOMBSTONE_SUBJECTS, "ck_rca_workspace_tombstone_subject"),
    )

    tombstone_id: Mapped[str] = mapped_column(String, primary_key=True)
    subject_kind: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # A dataset version's allowlist (§3, row one). Null on a run's tombstone.
    version_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    upload_plaintext_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    upload_ciphertext_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    upload_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    upload_media_type: Mapped[str | None] = mapped_column(String, nullable=True)
    manifest_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    mapping_version: Mapped[str | None] = mapped_column(String, nullable=True)
    admission_outcome: Mapped[str | None] = mapped_column(String, nullable=True)

    # An analysis run's allowlist (§3, row two). Null on a version's tombstone.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    package_digest: Mapped[str | None] = mapped_column(String, nullable=True)
    package_version: Mapped[str | None] = mapped_column(String, nullable=True)
    formula_version: Mapped[str | None] = mapped_column(String, nullable=True)
    section_states: Mapped[str | None] = mapped_column(Text, nullable=True)


def _leaving_started(target: object, changed: set[str]) -> bool:
    """Whether this update is the completion transition, taken once out of `started`."""
    return "state" in changed and _one_way(target, "state", RUN_STARTED)


def _check_completion(changed: set[str]) -> None:
    """A completion writes its own columns and no others.

    A completion permitted to touch `version_id` would rewrite which dataset a run derived from --
    provenance changed through the one write the guard allows.
    """
    if not changed <= COMPLETION_COLUMNS:
        raise ValueError(APPEND_ONLY_FAILURE)


def _check_append_only(target: object, changed: set[str]) -> None:
    """Every update that is not a completion: content is frozen and one-way stays one-way."""
    if changed & COMPLETION_COLUMNS:
        raise ValueError(RECOMPLETE_FAILURE)
    if not changed <= MUTABLE_COLUMNS:
        raise ValueError(APPEND_ONLY_FAILURE)
    if "sealed_at" in changed and not _one_way(target, "sealed_at", None):
        raise ValueError(RESEAL_FAILURE)
    if "retention_state" in changed and _one_way(target, "retention_state", RETENTION_TOMBSTONED):
        raise ValueError(TOMBSTONE_FAILURE)


def _refuse_content_update(_mapper, _connection, target: object) -> None:
    """Refuse an `UPDATE` that changes content, or that reverses a one-way transition.

    **Why a guard exists at all.** Nothing else refuses one. The primary key stops a *second
    insert* under the same identifier, which is what `test_writing_the_same_version_twice_is_
    refused` asserts -- but a session that loads a row and commits a changed
    `upload_plaintext_digest` rewrites provenance through a perfectly ordinary `UPDATE`. Review on
    `#370` named this: duplicate-key testing does not satisfy `FR-112`, whose text is "a change to
    any content field after sealing or completion is refused".

    This is the lesson `W1-01` already paid for, one layer down: sealing proves a record was
    constructed through a door, never that anything refuses a later write.

    **What this covers, stated exactly.** It is a mapper event, so it fires for changes made to a
    *loaded object*. It does **not** fire for bulk DML (`session.execute(update(...))`) or for raw
    SQL, and a claim that it binds every write would be false -- review on `#370` caught an earlier
    version of this docstring making it, while `seal_dataset_version` itself used bulk DML to get
    around the guard. That bypass is gone: sealing now mutates the object like any other write, and
    the one-way rule lives here where the reversal is visible.

    Enforcement at the database boundary -- a trigger, or column privileges -- would bind every
    path, and belongs with `W1-07`'s lifecycle work where the deletion operations that must be
    exempt from it are written. This binds the ORM, which is every path in this repository today.

    Registered on the two row classes rather than on `Base`, so no other RCA table is affected.
    """
    changed = {
        attribute.key for attribute in sa_inspect(target).attrs if attribute.history.has_changes()
    }
    if _leaving_started(target, changed):
        _check_completion(changed)
        return
    _check_append_only(target, changed)


def _visible_in(row: object | None, owner_id: str | None) -> bool:
    """Whether a read may return this row: it exists, and it is not another scope's.

    Extracted from the two `get_*` methods rather than inlined, because
    `row is None or (owner_id is not None and row.owner_id != owner_id)` fuses two unrelated
    questions -- does it exist, and is it mine -- into one three-clause predicate that a reader has
    to disentangle before seeing the isolation rule inside it. `FR-109` isolation is the load-
    bearing half, so it gets a name and one place to be wrong.

    A `None` `owner_id` means the caller is not narrowing by scope: `W1-04` performs its own
    authorization before reading, and an internal read that has already established the scope
    should not have to restate it. Narrowing here is a filter, never a grant.
    """
    if row is None:
        return False
    return owner_id is None or row.owner_id == owner_id


# Every workspace row is append-only, so every one carries both guards. `ArtifactBindingRow` was
# missing from the update listener until review on `#370` asked why: a binding is immutable under
# `RCA-005`, and a caller changing `artifact_digest` would silently repoint a retained result at
# different content, which is exactly the provenance `FR-111` binds by digest to prevent.
#
# Registered per class rather than on `Base`, so no other RCA table is affected.
# `SourceProfileRow` is deliberately absent from both: `FR-115` makes a profile descriptive
# metadata a surface reads rather than a record the domain acts on, and `KHEPRI-DEC-033` §3 says it
# is "purged, not tombstoned" -- so a blanket delete guard would forbid the very operation the
# decision prescribes. `WorkspaceTombstoneRow` is absent for the opposite reason: it is what
# *survives* a deletion, and `W1-07`'s retention sweep must be able to purge it at its horizon.
for _row_class in (DatasetVersionRow, AnalysisRunRow, ArtifactBindingRow):
    event.listen(_row_class, "before_update", _refuse_content_update)
    event.listen(_row_class, "before_delete", _refuse_delete)


def _version_from_row(row: DatasetVersionRow) -> DatasetVersion:
    return DatasetVersion._from_storage(
        version_id=row.version_id,
        owner_id=row.owner_id,
        source=AdmittedSource(
            plaintext_digest=row.upload_plaintext_digest,
            ciphertext_digest=row.upload_ciphertext_digest,
            size_bytes=row.upload_size_bytes,
            media_type=row.upload_media_type,
            manifest_digest=row.manifest_digest,
            mapping_version=row.mapping_version,
            admission_outcome=row.admission_outcome,
        ),
        lifecycle=VersionLifecycle(
            created_at=_utc(row.created_at),
            sealed_at=_utc(row.sealed_at),
        ),
    )


def _run_from_row(row: AnalysisRunRow) -> AnalysisRun:
    return AnalysisRun._from_storage(
        subject=RunSubject(run_id=row.run_id, owner_id=row.owner_id, version_id=row.version_id),
        outcome=RunOutcome(
            state=row.state,
            package_digest=row.package_digest,
            package_version=row.package_version,
            formula_version=row.formula_version,
            completed_at=_utc(row.completed_at),
        ),
        started_at=_utc(row.started_at),
    )


def _binding_from_row(row: ArtifactBindingRow) -> ArtifactBinding:
    return ArtifactBinding._from_storage(
        run_id=row.run_id,
        owner_id=row.owner_id,
        artifact=PublishedArtifact(surface=row.surface, artifact_digest=row.artifact_digest),
        published_at=_utc(row.published_at),
    )


def run_for_update(run_id: str):
    """Lock one run row for the duration of the caller's transaction.

    A **module-level named statement** rather than an inline `.with_for_update()`, following
    `account_for_update` in `rca/persistence.py` and for the reason stated there: SQLite emits no
    `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so an inline lock someone later
    removed would leave the whole suite green. Being named, a test compiles it against the
    PostgreSQL dialect and asserts `FOR UPDATE` is present without needing a database.

    `complete_analysis_run` needs it because read-then-write is not atomic: two workers can both
    read `started`, both pass the check, and the second overwrite the first's package digest and
    version provenance while both report success. Review on `#370` found that; `FR-111` binds a run
    to the versions it actually derived under, so a lost write there is lost provenance.
    """
    return select(AnalysisRunRow).where(AnalysisRunRow.run_id == run_id).with_for_update()


def version_for_update(version_id: str):
    """Lock one dataset version row. See `run_for_update`.

    `seal_dataset_version` needs it for the reason `run_for_update` states: it reports whether
    *this* call sealed the version, and two callers must not both be told they did.
    `set_retention_state` deliberately does **not** take it -- see the comment there.
    """
    return (
        select(DatasetVersionRow)
        .where(DatasetVersionRow.version_id == version_id)
        .with_for_update()
    )


class SqlWorkspaceStore:
    """Rows for the workspace records, and the one transition `FR-112` permits.

    Nothing here authorizes. A caller reaching this store has already been authorized by `W1-04`,
    and the `owner_id` arguments below narrow a query rather than grant a right -- which is why
    they default to `None` for the internal reads `W1-04` will make after its own check, and are
    supplied wherever a request carries a scope.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    # --- dataset versions ---------------------------------------------------------------

    def add_dataset_version(self, version: DatasetVersion) -> DatasetVersion:
        """Append one version. A second write under the same identifier raises."""
        assert_sealed(version)
        with self._factory.begin() as database:
            database.add(
                DatasetVersionRow(
                    version_id=version.version_id,
                    owner_id=version.owner_id,
                    upload_plaintext_digest=version.upload_plaintext_digest,
                    upload_ciphertext_digest=version.upload_ciphertext_digest,
                    upload_size_bytes=version.upload_size_bytes,
                    upload_media_type=version.upload_media_type,
                    manifest_digest=version.manifest_digest,
                    mapping_version=version.mapping_version,
                    admission_outcome=version.admission_outcome,
                    created_at=version.created_at,
                    sealed_at=version.sealed_at,
                    retention_state=RETENTION_ACTIVE,
                )
            )
        return version

    def get_dataset_version(
        self, version_id: str, owner_id: str | None = None
    ) -> DatasetVersion | None:
        with self._factory() as database:
            row = database.get(DatasetVersionRow, version_id)
            if not _visible_in(row, owner_id):
                return None
            return _version_from_row(row)

    def dataset_versions_for_scope(self, owner_id: str) -> tuple[DatasetVersion, ...]:
        """Newest first, within one scope only."""
        with self._factory() as database:
            rows = database.execute(
                select(DatasetVersionRow)
                .where(DatasetVersionRow.owner_id == owner_id)
                .order_by(DatasetVersionRow.created_at.desc(), DatasetVersionRow.version_id.desc())
            ).scalars()
            return tuple(_version_from_row(row) for row in rows)

    # --- analysis runs ------------------------------------------------------------------

    def add_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        assert_sealed(run)
        with self._factory.begin() as database:
            database.add(
                AnalysisRunRow(
                    run_id=run.run_id,
                    version_id=run.version_id,
                    owner_id=run.owner_id,
                    package_digest=run.package_digest,
                    package_version=run.package_version,
                    formula_version=run.formula_version,
                    state=run.state,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    retention_state=RETENTION_ACTIVE,
                )
            )
        return run

    def complete_analysis_run(
        self, run_id: str, outcome: RunOutcome, *, owner_id: str | None = None
    ) -> bool:
        """Record what a run produced, once, moving it out of `started`.

        `W1-01` creates a run incomplete on purpose -- `FR-111` puts the digest and the governed
        versions on the real pipeline rather than on whoever starts the run -- so the pipeline
        needs a way to record its result. Review on `#370` found that the append-only guard had
        made this impossible: a run written through this store could never reach a terminal state,
        and `FR-112`'s "after sealing or completion" had been implemented as "after writing".

        One way, like sealing. `RunOutcome.__post_init__` already refuses a state the domain does
        not name, so this refuses only the *second* completion: the guard treats every column this
        writes as immutable once the run has left `started`.

        Returns whether this call completed it, on the same reasoning as `seal_dataset_version`:
        a run that does not exist, belongs to another scope, or has already finished are the same
        answer from the caller's side.
        """
        if outcome.state == RUN_STARTED:
            raise ValueError(RECOMPLETE_FAILURE)
        with self._factory.begin() as database:
            row = database.scalars(run_for_update(run_id)).one_or_none()
            if not _visible_in(row, owner_id) or row.state != RUN_STARTED:
                return False
            row.state = outcome.state
            row.package_digest = outcome.package_digest
            row.package_version = outcome.package_version
            row.formula_version = outcome.formula_version
            row.completed_at = outcome.completed_at
        return True

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> AnalysisRun | None:
        with self._factory() as database:
            row = database.get(AnalysisRunRow, run_id)
            if not _visible_in(row, owner_id):
                return None
            return _run_from_row(row)

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[AnalysisRun, ...]:
        with self._factory() as database:
            rows = database.execute(
                select(AnalysisRunRow)
                .where(AnalysisRunRow.owner_id == owner_id)
                .order_by(AnalysisRunRow.started_at.desc(), AnalysisRunRow.run_id.desc())
            ).scalars()
            return tuple(_run_from_row(row) for row in rows)

    # --- artifact bindings --------------------------------------------------------------

    def add_artifact_binding(self, binding: ArtifactBinding) -> ArtifactBinding:
        assert_sealed(binding)
        with self._factory.begin() as database:
            database.add(
                ArtifactBindingRow(
                    binding_id=_identifier("abn"),
                    run_id=binding.run_id,
                    owner_id=binding.owner_id,
                    surface=binding.surface,
                    artifact_digest=binding.artifact_digest,
                    published_at=binding.published_at,
                )
            )
        return binding

    def artifact_bindings_for_run(
        self, run_id: str, owner_id: str | None = None
    ) -> tuple[ArtifactBinding, ...]:
        """Every surface this run published, which is the set `FR-111` reads for completeness.

        Narrowed by scope for the same reason as the `get_*` reads: an identifier that leaks
        should not become data that leaks. Review on `#370` found this method, `retention_state`
        and `set_retention_state` taking no `owner_id` while the two `get_*` methods did -- the
        module stating one rule and implementing it in half its reads.
        """
        with self._factory() as database:
            query = select(ArtifactBindingRow).where(ArtifactBindingRow.run_id == run_id)
            if owner_id is not None:
                query = query.where(ArtifactBindingRow.owner_id == owner_id)
            rows = database.execute(query.order_by(ArtifactBindingRow.surface)).scalars()
            return tuple(_binding_from_row(row) for row in rows)

    # --- retention, the one thing `FR-112` lets a later operation change -----------------

    def retention_state(self, version_id: str, owner_id: str | None = None) -> str | None:
        with self._factory() as database:
            row = database.get(DatasetVersionRow, version_id)
            return row.retention_state if _visible_in(row, owner_id) else None

    def set_retention_state(
        self, version_id: str, state: str, *, now: datetime, owner_id: str | None = None
    ) -> None:
        """Move a version's retention state, refusing a state the domain does not name.

        Refused in the store as well as by the `CHECK` constraint, and the duplication is the
        point: the constraint is what holds when a row arrives by another route, and this is what
        gives a caller a content-free refusal rather than a driver error carrying its input.
        """
        if state not in RETENTION_STATES:
            raise ValueError(RETENTION_STATE_FAILURE)
        with self._factory.begin() as database:
            # No row lock, unlike `seal_dataset_version` and `complete_analysis_run`, which share
            # this read-then-write shape. Those two return *whether this call* performed the
            # transition, and two concurrent callers must not both be told `True`. This returns
            # nothing, and `tombstoned` is terminal over a two-state domain -- so a row makes at
            # most one real transition, concurrent tombstones agree on the state they want, and
            # `_one_way` refuses the reverse from either order. `R1-05` forbids a lock with no
            # guard behind it: it would imply a decision boundary here that does not exist.
            row = database.get(DatasetVersionRow, version_id)
            if not _visible_in(row, owner_id) or row.retention_state == state:
                # A repeat of the state the row already holds is `FR-123`'s idempotent retry, and
                # it must not move the clock. `KHEPRI-DEC-033` §5 anchors a deletion horizon to
                # `retention_changed_at`, so overwriting it on every retry would let repeated
                # requests extend a deadline outward -- the same defect re-sealing was guarded
                # against, arriving through the timestamp instead of the state. Review on `#370`
                # found it, and the guard could not: assigning an equal value is not a change, so
                # `_one_way` sees nothing to refuse.
                return
            row.retention_state = state
            row.retention_changed_at = now

    def seal_dataset_version(
        self, version_id: str, *, now: datetime, owner_id: str | None = None
    ) -> bool:
        """Record that a version is sealed. One way, and never twice.

        `DatasetVersion.create` cannot take a `sealed_at` -- `W1-01` made sealing an event rather
        than a creation argument, and two of its tests assert that against the signature. But no
        operation ever *performed* the event, so every stored version stayed unsealed and
        `KHEPRI-DEC-033`'s seven-day raw-upload purge clock could never start. Review on `#370`
        found the missing half.

        Returns whether this call sealed it. A second call is refused rather than silently moving
        the instant, because the purge clock starts at the first: re-sealing would extend a
        deletion deadline, which is the one direction `KHEPRI-DEC-033` cannot tolerate. A version
        that does not exist, or belongs to another scope, returns `False` for the reason
        `set_retention_state` returns silently -- those are the same answer from the caller's side.

        It mutates the loaded row like any other write. An earlier version used bulk DML to get
        around `_refuse_content_update`, which review on `#370` correctly read as a hole rather
        than a design: a mapper listener does not fire for bulk DML, so the bypass proved the
        guard's own coverage claim false. The one-way rule now lives in the guard, where the
        reversal is visible, and this method needs no exemption.
        """
        with self._factory.begin() as database:
            row = database.scalars(version_for_update(version_id)).one_or_none()
            if not _visible_in(row, owner_id) or row.sealed_at is not None:
                return False
            row.sealed_at = now
        return True

    def tombstone_dataset_version(
        self, version_id: str, *, now: datetime, owner_id: str | None = None
    ) -> None:
        self.set_retention_state(version_id, RETENTION_TOMBSTONED, now=now, owner_id=owner_id)


__all__ = [
    "APPEND_ONLY_FAILURE",
    "run_for_update",
    "version_for_update",
    "TOMBSTONE_SUBJECTS",
    "SourceProfileRow",
    "WorkspaceTombstoneRow",
    "DELETE_FAILURE",
    "COMPLETION_COLUMNS",
    "RECOMPLETE_FAILURE",
    "RESEAL_FAILURE",
    "TOMBSTONE_FAILURE",
    "MUTABLE_COLUMNS",
    "RETENTION_ACTIVE",
    "RETENTION_STATES",
    "RETENTION_STATE_FAILURE",
    "RETENTION_TOMBSTONED",
    "AnalysisRunRow",
    "ArtifactBindingRow",
    "DatasetVersionRow",
    "SqlWorkspaceStore",
]
