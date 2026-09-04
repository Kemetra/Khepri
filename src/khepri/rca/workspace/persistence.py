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
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from khepri.rca.persistence import Base, _utc
from khepri.rca.records import assert_sealed
from khepri.rca.workspace.contracts import (
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


def _retention_check(states: tuple[str, ...], name: str) -> CheckConstraint:
    """Render the retention CHECK from the declared states, for the named constraint.

    Built from `RETENTION_STATES` rather than spelled out, following `_role_in` in
    `rca/persistence.py` for its reason: adding a third state to the domain without a migration
    then fails against the constraint rather than silently widening it. The migration spells the
    same values literally, because a migration is a historical record and importing a constant into
    one would let a later edit rewrite history -- and a test asserts the two spellings agree.
    """
    assert all(state.isalpha() for state in states), f"states must be plain identifiers: {states}"
    values = ", ".join(f"'{state}'" for state in states)
    return CheckConstraint(f"retention_state IN ({values})", name=name)


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

    def artifact_bindings_for_run(self, run_id: str) -> tuple[ArtifactBinding, ...]:
        """Every surface this run published, which is the set `FR-111` reads for completeness."""
        with self._factory() as database:
            rows = database.execute(
                select(ArtifactBindingRow)
                .where(ArtifactBindingRow.run_id == run_id)
                .order_by(ArtifactBindingRow.surface)
            ).scalars()
            return tuple(_binding_from_row(row) for row in rows)

    # --- retention, the one thing `FR-112` lets a later operation change -----------------

    def retention_state(self, version_id: str) -> str | None:
        with self._factory() as database:
            row = database.get(DatasetVersionRow, version_id)
            return None if row is None else row.retention_state

    def set_retention_state(self, version_id: str, state: str, *, now: datetime) -> None:
        """Move a version's retention state, refusing a state the domain does not name.

        Refused in the store as well as by the `CHECK` constraint, and the duplication is the
        point: the constraint is what holds when a row arrives by another route, and this is what
        gives a caller a content-free refusal rather than a driver error carrying its input.
        """
        if state not in RETENTION_STATES:
            raise ValueError(RETENTION_STATE_FAILURE)
        with self._factory.begin() as database:
            row = database.get(DatasetVersionRow, version_id)
            if row is None:
                return
            row.retention_state = state
            row.retention_changed_at = now

    def tombstone_dataset_version(self, version_id: str, *, now: datetime) -> None:
        self.set_retention_state(version_id, RETENTION_TOMBSTONED, now=now)


__all__ = [
    "RETENTION_ACTIVE",
    "RETENTION_STATES",
    "RETENTION_STATE_FAILURE",
    "RETENTION_TOMBSTONED",
    "AnalysisRunRow",
    "ArtifactBindingRow",
    "DatasetVersionRow",
    "SqlWorkspaceStore",
]
