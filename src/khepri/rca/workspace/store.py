"""The `W1-02` workspace store: reads narrowed by scope and liveness, transitions, and their locks.

Split from `persistence.py` alongside `schema.py`. This module holds the operations -- `_visible_in`
and `_live_in`, the row-to-record projections, the two named `FOR UPDATE` statements, and
`SqlWorkspaceStore` -- and imports the rows and vocabularies it operates on from `schema`.

Every public name is re-exported from `persistence.py`; import from there.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy import (
    select,
)
from sqlalchemy.orm import sessionmaker

from khepri.rca.persistence import _utc
from khepri.rca.records import assert_sealed
from khepri.rca.workspace.contracts import (
    RUN_STARTED,
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
from khepri.rca.workspace.schema import (
    PARENT_TOMBSTONED_FAILURE,
    RECOMPLETE_FAILURE,
    RETENTION_ACTIVE,
    RETENTION_STATE_FAILURE,
    RETENTION_STATES,
    RETENTION_TOMBSTONED,
    AnalysisRunRow,
    ArtifactBindingRow,
    DatasetVersionRow,
    WorkspaceTombstoneRow,
)
from khepri.rca.workspace.tombstone_rows import tombstone_from_row, tombstone_row
from khepri.rca.workspace.tombstones import RunTombstone, SectionStates, VersionTombstone

#: How a deleting caller tells the cascade each run's section states. The live run record carries
#: none and the bundle that does is `khepri.rra`'s (see `tombstones.py`), so the store asks rather
#: than reads. Called once per live run, inside the deletion's transaction, with the run as stored.
SectionsOf = Callable[[AnalysisRun], SectionStates | None]


def _no_sections(_run: AnalysisRun) -> SectionStates | None:
    """The default: no caller supplied section states, so none are recorded (§3: *may* contain)."""
    return None


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


def _live_in(row: object | None, owner_id: str | None) -> bool:
    """Whether a *read* may return this row as a live record: visible, and not tombstoned.

    Separate from `_visible_in` because the transitions need the weaker predicate -- an idempotent
    tombstone must reach its own row to return early, and the terminal-state guard must see the row
    it refuses. A read is different: `DatasetVersion` and `AnalysisRun` carry no retention state by
    `W1-01`'s design, so a tombstoned row read back is indistinguishable from a live one, and a
    caller could keep presenting or reusing a record the customer deleted. Review on `#370` found
    the four read paths filtering by scope alone. `retention_state()` is the store's answer for the
    row's state; these return `None` or omit it.
    """
    return _visible_in(row, owner_id) and row.retention_state == RETENTION_ACTIVE


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


def run_for_update(run_id: str, owner_id: str | None = None):
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
    statement = select(AnalysisRunRow).where(AnalysisRunRow.run_id == run_id)
    if owner_id is not None:
        # Scoped when the caller knows the scope, so a cross-tenant identifier locks *nothing*:
        # `FOR UPDATE` over an empty result acquires no lock, and the insert that follows meets the
        # composite foreign key exactly as it would have without this call. Without the predicate a
        # caller naming another tenant's row would hold that row for the transaction -- contention
        # across the isolation boundary, which `FR-109` forbids in spirit if not in letter.
        statement = statement.where(AnalysisRunRow.owner_id == owner_id)
    return statement.with_for_update()


def version_for_update(version_id: str, owner_id: str | None = None):
    """Lock one dataset version row. See `run_for_update`.

    `seal_dataset_version` needs it for the reason `run_for_update` states: it reports whether
    *this* call sealed the version, and two callers must not both be told they did.
    `set_retention_state` deliberately does **not** take it -- see the comment there.
    """
    statement = select(DatasetVersionRow).where(DatasetVersionRow.version_id == version_id)
    if owner_id is not None:
        statement = statement.where(DatasetVersionRow.owner_id == owner_id)  # see `run_for_update`
    return statement.with_for_update()


def _refuse_tombstoned_parent(parent: object | None) -> None:
    """Refuse a derivative whose parent exists, is in scope, and has been deleted.

    Deliberately *not* `_live_in`: a parent that is missing or belongs to another scope is left to
    the composite foreign key, which refuses the insert with `IntegrityError` as it always did. Two
    reasons. The schema tests for those constraints must keep exercising them -- a store check that
    intercepted first would let a dropped foreign key pass unnoticed. And the lock statement is
    scoped by `owner_id`, so a foreign parent was never locked and is `None` here by construction.
    What this adds is the one case the foreign key cannot see: the row is real and ours, and the
    customer deleted it.
    """
    if parent is not None and parent.retention_state != RETENTION_ACTIVE:
        raise ValueError(PARENT_TOMBSTONED_FAILURE)


def _tombstone_version(
    database, version: DatasetVersionRow, now: datetime, sections_of: SectionsOf
) -> None:
    """Write the version's tombstone, then cascade to its live runs, each with its own.

    `W1-02` flipped the retention state and wrote nothing into `rca_workspace_tombstones`; this is
    the projection its `WorkspaceTombstoneRow` docstring left to `W1-03`. The projection reads the
    row through `_version_from_row`, so it sees the same record a reader would have, and the row it
    writes is added to the same session as the state change: one transaction ends the version and
    records what may survive it, or neither happens.

    Called only from `set_retention_state`, *after* its idempotency return -- a repeated deletion
    reaches neither this nor the cascade, which is `FR-123`'s "no new deletion evidence".
    """
    tombstone = VersionTombstone.project(_version_from_row(version), deleted_at=now)
    database.add(tombstone_row(tombstone))
    _cascade_tombstone_to_runs(database, version, now, sections_of)


def _cascade_tombstone_to_runs(
    database, version: DatasetVersionRow, now: datetime, sections_of: SectionsOf
) -> None:
    """Tombstone every live run of a version being tombstoned, in the same transaction.

    `KHEPRI-DEC-033` §3: a dataset version's deletion is "immediate, cascading to every derivative
    below". Without this a run that existed *before* the deletion kept `retention_state = active` --
    readable through both run reads, completable, and able to receive bindings -- while its source
    version was no longer readable. `add_analysis_run`'s parent check covers only runs created
    *after*. Review on `#370` found the pre-existing case.

    Bindings need nothing here: they have no retention state and are read through their run, which
    `artifact_bindings_for_run` joins to and requires live.

    **Only live runs**, and not as an optimisation: `_check_terminal_state` refuses *every*
    update to a tombstoned row, so a run already tombstoned on its own would make the whole
    cascade raise and roll back the version's deletion with it. The filter is what keeps the
    cascade able to run.

    Row by row through the ORM rather than bulk `UPDATE`, so the guards see each transition -- the
    same reason `seal_dataset_version` stopped using bulk DML. The version row is already locked by
    the caller, which is what serialises this against `add_analysis_run` and a concurrent cascade.

    Each run's clock is set to the deletion instant. §3 gives a run's tombstone its own clock
    "anchored to that class's own trigger", and a cascaded deletion *is* the run's trigger.

    Each run also gets its tombstone (`W1-03`), projected from the run as stored and with the
    section states `sections_of` supplies for it. Only the runs this deletion ends get one: a run
    the liveness filter skips was ended by its own trigger, and its record is that trigger's.
    """
    live_runs = database.scalars(
        select(AnalysisRunRow)
        .where(AnalysisRunRow.version_id == version.version_id)
        .where(AnalysisRunRow.owner_id == version.owner_id)
        .where(AnalysisRunRow.retention_state == RETENTION_ACTIVE)
    ).all()
    for run in live_runs:
        record = _run_from_row(run)
        tombstone = RunTombstone.project(record, sections=sections_of(record), deleted_at=now)
        database.add(tombstone_row(tombstone))
        run.retention_state = RETENTION_TOMBSTONED
        run.retention_changed_at = now


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
            if not _live_in(row, owner_id):
                return None
            return _version_from_row(row)

    def dataset_versions_for_scope(self, owner_id: str) -> tuple[DatasetVersion, ...]:
        """Newest first, within one scope only."""
        with self._factory() as database:
            rows = database.execute(
                select(DatasetVersionRow)
                .where(DatasetVersionRow.owner_id == owner_id)
                .where(DatasetVersionRow.retention_state == RETENTION_ACTIVE)
                .order_by(DatasetVersionRow.created_at.desc(), DatasetVersionRow.version_id.desc())
            ).scalars()
            return tuple(_version_from_row(row) for row in rows)

    # --- analysis runs ------------------------------------------------------------------

    def add_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        """Store a run under a version that is still live, or refuse.

        The composite foreign key proves the version exists in this scope and nothing more. A
        pipeline racing a deletion could therefore create a new *live* derivative of an input the
        customer had just withdrawn -- inserted after the tombstone, returned by
        `analysis_runs_for_scope`, and `KHEPRI-DEC-033` §3's cascade would never reach it because
        it did not exist when the cascade ran. Review on `#370` found it.

        The parent is locked for the transaction, not merely read: `tombstone_dataset_version`
        takes the same `version_for_update`, so the two serialize and a run is added either before
        the deletion -- and cascades with it -- or refused after. A read without the lock leaves
        the window this exists to close. `test_rca001_lock_scope.py` names this method for that
        reason.
        """
        assert_sealed(run)
        with self._factory.begin() as database:
            parent = database.scalars(
                version_for_update(run.version_id, run.owner_id)
            ).one_or_none()
            _refuse_tombstoned_parent(parent)
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
            row = database.scalars(run_for_update(run_id, owner_id)).one_or_none()
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
            if not _live_in(row, owner_id):
                return None
            return _run_from_row(row)

    def analysis_runs_for_scope(self, owner_id: str) -> tuple[AnalysisRun, ...]:
        with self._factory() as database:
            rows = database.execute(
                select(AnalysisRunRow)
                .where(AnalysisRunRow.owner_id == owner_id)
                .where(AnalysisRunRow.retention_state == RETENTION_ACTIVE)
                .order_by(AnalysisRunRow.started_at.desc(), AnalysisRunRow.run_id.desc())
            ).scalars()
            return tuple(_run_from_row(row) for row in rows)

    # --- artifact bindings --------------------------------------------------------------

    def add_artifact_binding(self, binding: ArtifactBinding) -> ArtifactBinding:
        """Bind an artifact to a run that is still live, or refuse. See `add_analysis_run`.

        The same shape one level down. The review named runs under versions; a binding under a
        tombstoned run is the identical window, and a rule that covers one parent and not the other
        is the kind of asymmetry this module has already been caught on once.
        """
        assert_sealed(binding)
        with self._factory.begin() as database:
            parent = database.scalars(
                run_for_update(binding.run_id, binding.owner_id)
            ).one_or_none()
            _refuse_tombstoned_parent(parent)
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
            # Joined to the parent run and narrowed to a live one. A binding has no retention state
            # of its own; it is read *through* its run, so a run tombstoned while its bindings
            # remain -- a partial, restored or concurrent deletion -- would otherwise hand back the
            # withdrawn artifacts' digests here while `get_analysis_run` hid the run itself. The
            # fifth read path; the earlier count of four missed the one that reads by parent.
            # Review on `#370` found it.
            query = (
                select(ArtifactBindingRow)
                .join(AnalysisRunRow, AnalysisRunRow.run_id == ArtifactBindingRow.run_id)
                .where(ArtifactBindingRow.run_id == run_id)
                .where(AnalysisRunRow.retention_state == RETENTION_ACTIVE)
            )
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
        self,
        version_id: str,
        state: str,
        *,
        now: datetime,
        owner_id: str | None = None,
        sections_of: SectionsOf = _no_sections,
    ) -> None:
        """Move a version's retention state, refusing a state the domain does not name.

        Refused in the store as well as by the `CHECK` constraint, and the duplication is the
        point: the constraint is what holds when a row arrives by another route, and this is what
        gives a caller a content-free refusal rather than a driver error carrying its input.
        """
        if state not in RETENTION_STATES:
            raise ValueError(RETENTION_STATE_FAILURE)
        with self._factory.begin() as database:
            # Locked, and the argument for *not* locking is worth recording because I made it on
            # this PR and it was wrong. I reasoned that concurrent tombstones agree on the state
            # they want, so last-write-wins is harmless. They do not agree on
            # `retention_changed_at`: both read `active`, both find the equality check false, and
            # the second overwrites the first deletion instant -- moving the horizon
            # `KHEPRI-DEC-033` §5 anchors to it, which is the defect the early return was added to
            # close. The early return only ever protected a *sequential* retry.
            #
            # No test here could have caught it. SQLite serializes writes, so the two calls run in
            # sequence and the second genuinely does read `tombstoned` -- the environment supplies
            # the property the assertion checks. Two reviewers found it independently on `#370`.
            row = database.scalars(version_for_update(version_id, owner_id)).one_or_none()
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
            if state == RETENTION_TOMBSTONED:
                _tombstone_version(database, row, now, sections_of)

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
            row = database.scalars(version_for_update(version_id, owner_id)).one_or_none()
            if not _visible_in(row, owner_id) or row.sealed_at is not None:
                return False
            row.sealed_at = now
        return True

    def tombstone_dataset_version(
        self,
        version_id: str,
        *,
        now: datetime,
        owner_id: str | None = None,
        sections_of: SectionsOf = _no_sections,
    ) -> None:
        """Delete a version as `KHEPRI-DEC-033` §1-§3 describe: one way, cascading, recorded.

        `sections_of` is how the caller supplies each cascaded run's section states -- see
        `SectionsOf`. Left at its default, every run is recorded with no section states, which is
        what a `started` or `failed` run has and what a caller without the bundle can say.
        """
        self.set_retention_state(
            version_id, RETENTION_TOMBSTONED, now=now, owner_id=owner_id, sections_of=sections_of
        )

    def tombstones_for_scope(self, owner_id: str) -> tuple[VersionTombstone | RunTombstone, ...]:
        """Every deletion record in one scope, oldest deletion first, a version before its runs.

        Keyed by the scope and nothing else: a tombstone is what the history spine shows in place
        of the record that ended (`FR-117`), so it is read the way live records are -- by scope --
        and never by a filter a caller could widen. Ordered so a listing is stable across reads.
        """
        with self._factory() as database:
            rows = database.scalars(
                select(WorkspaceTombstoneRow)
                .where(WorkspaceTombstoneRow.owner_id == owner_id)
                .order_by(
                    WorkspaceTombstoneRow.deleted_at,
                    WorkspaceTombstoneRow.subject_kind.desc(),
                    WorkspaceTombstoneRow.subject_id,
                )
            )
            return tuple(tombstone_from_row(row) for row in rows)
