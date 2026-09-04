"""The `W1-02` workspace schema: five row classes, their constraints, and the guards on them.

Split from `persistence.py`, which had grown to 1,147 lines holding two concerns -- what the schema
*is and refuses*, and what the store *does*. CodeScene flagged the module's cohesion on `#370`; the
seam is the one a reader wants.

**The guards live with the rows on purpose.** `_ROW_GUARDS` registers mapper listeners at import,
and a module holding the row classes without that registration would hand any importer unguarded
rows -- the import-side-effect shape `test_rca001_migration.py` documents from `#240`. Keeping
both here means no import path yields a `DatasetVersionRow` that accepts a content update.

Every public name is re-exported from `persistence.py`; import from there.
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
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Mapped, mapped_column

from khepri.rca.persistence import Base
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_PROVENANCE_FAILURE,
    RUN_STARTED,
    RUN_STATES,
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

#: What a source profile *is*, as opposed to what it says. Frozen by `_refuse_identity_change`.
PROFILE_IDENTITY_COLUMNS = frozenset({"profile_id", "owner_id", "source_version_id"})

#: `KHEPRI-DEC-033` §3's two allowlists, as the column names this table gives them. A row must
#: leave every column outside its own subject's allowlist null -- otherwise `subject_kind="version"`
#: could carry a run's section states, and the schema would not enforce the allowlists it claims
#: to represent. Review on `#370` found the `CHECK` validating only the discriminator.
#:
#: **They overlap, and `version_id` is the overlap.** §3 gives it to both rows: a dataset version's
#: tombstone keeps "opaque version id and organization scope", and an analysis run's keeps "opaque
#: run id, **version id** and scope" -- the run's link to the dataset it derived from. A first
#: draft here partitioned them and put `version_id` on the version side alone, which would have
#: made `W1-03` unable to project a run deletion without losing that provenance. Review on `#370`
#: found it, and the test that agreed with the partition was mine too: I had asserted a *stronger*
#: property than §3 states, and it passed because the schema and the assertion were written
#: together from the same misreading.
#:
#: These are also what `W1-03`'s projection must agree with. The drift test asserts the constants
#: and the emitted `CHECK` clauses match, so the two allowlists cannot diverge silently.
VERSION_TOMBSTONE_COLUMNS = (
    "version_id",
    "created_at",
    "sealed_at",
    "upload_plaintext_digest",
    "upload_ciphertext_digest",
    "upload_size_bytes",
    "upload_media_type",
    "manifest_digest",
    "mapping_version",
    "admission_outcome",
)
#: The report sections a run's tombstone records a state for -- `rra/bundle.py`'s
#: `ORDERED_SECTIONS`, restated. `KHEPRI-DEC-033` §3 admits "per-section state codes", and a
#: *section* is one of the five parts of a report, not a metric: the previous draft allowlisted the
#: 22 `GOVERNED_METRICS` names, which would have refused every real section key `W1-03` emits
#: while admitting keys that are not sections. Review on `#370` found it. Finding *a* closed set
#: in the producing module is not the same as finding *the* one the decision names.
#:
#: **One column per section, rather than a JSON document.** The document form had two defects no
#: patch could close: its vocabulary was enforced only by a mapper listener, which Core and raw SQL
#: inserts bypass, and a `CHECK` cannot validate JSON portably across SQLite and PostgreSQL. Five
#: nullable columns make both vocabularies a property of the *schema*: a section that is not a
#: column is unrepresentable, and each column's `CHECK` names the states it may hold. That is the
#: "normalized constrained representation" the review asked for, and it needs no listener.
#:
#: Restated rather than imported because `R7-01` §3 forbids `khepri.rca` importing `khepri.rra`
#: in either direction; `test_w102_workspace_tombstones.py` asserts agreement with
#: `ORDERED_SECTIONS` from the one place that may import both.
TOMBSTONE_SECTIONS = ("overview", "comparison", "concentration", "growth", "basket")
SECTION_COLUMNS = tuple(f"section_{section}" for section in TOMBSTONE_SECTIONS)

#: The state codes a section may carry: `KHEPRI-DEC-033` §3's three, exactly. "Per-section state
#: codes (answered, caveated, refused)" is an exhaustive allowlist, not an example.
#:
#: An earlier draft admitted the union with `rra/bundle.py`'s `GOVERNED_SECTION_STATES`
#: (`present`, `refused`) on the argument that both sets were "real" and `W1-03` could narrow. That
#: was the retention allowlist being widened by a *rendering* vocabulary -- `present` says a surface
#: drew a chart, which is not a retention outcome and not something §3 permits a deletion record to
#: keep. Review on `#370` found it. `W1-03` translates `present` to the retention outcome it means
#: before projecting; this schema does not accept it. `refused` appears in both vocabularies and is
#: admitted because §3 names it, not because `bundle.py` does.
SECTION_STATE_ANSWERED = "answered"
SECTION_STATE_CAVEATED = "caveated"
SECTION_STATE_REFUSED = "refused"
SECTION_STATE_CODES = (
    SECTION_STATE_ANSWERED,
    SECTION_STATE_CAVEATED,
    SECTION_STATE_REFUSED,
)
GOVERNED_SECTION_STATE_CODES: frozenset[str] = frozenset(SECTION_STATE_CODES)

RUN_TOMBSTONE_COLUMNS = (
    # Shared with `VERSION_TOMBSTONE_COLUMNS`: §3 puts a version id on both rows. On a version's
    # tombstone it restates `subject_id`; on a run's it is the dataset the run derived from.
    "version_id",
    "started_at",
    "completed_at",
    "package_digest",
    "package_version",
    "formula_version",
    *SECTION_COLUMNS,
)

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


def _completion_provenance_check(name: str) -> CheckConstraint:
    """A row in `completed` carries the four things `FR-111` says it produced.

    The same rule `RunOutcome.__post_init__` enforces, stated where a writer outside the ORM also
    meets it -- and the duplication has a specific reason. Enforced only in the dataclass, a bad
    row reaches the database, and then `_run_from_row` raises constructing the `RunOutcome` on
    *read*: `analysis_runs_for_scope` fails for the whole scope, so one malformed row becomes an
    outage for every run in the organization. Review on `#370` traced that path.

    Nullable columns with a state-conditional requirement, rather than `NOT NULL`: `failed` and
    `started` carry no package because none was produced.
    """
    return CheckConstraint(
        f"state <> '{RUN_COMPLETED}' OR ("
        "package_digest IS NOT NULL AND package_version IS NOT NULL "
        "AND formula_version IS NOT NULL AND completed_at IS NOT NULL)",
        name=name,
    )


def _version_identity_check() -> CheckConstraint:
    """A version's tombstone names the version it is *for* in both places, identically.

    `subject_id` is the discriminated identity; `version_id` is the allowlist column that, on a
    version's row, restates it (on a run's row it is the parent dataset instead). Nullable and
    independently writable, it let a projection or direct insert persist `subject_id=A` with
    `version_id=B` or `NULL` -- and the row is immutable once written, so history and revocation
    consumers could permanently disagree about which version was deleted. Review on `#370` found
    it.

    `IS NOT NULL` is spelled out because `NULL = subject_id` is `NULL`, and a `CHECK` treats
    unknown as pass: without it the constraint would admit exactly the null it exists to refuse.
    """
    return CheckConstraint(
        f"subject_kind <> '{TOMBSTONE_VERSION}' "
        "OR (version_id IS NOT NULL AND version_id = subject_id)",
        name="ck_rca_workspace_tombstone_version_identity",
    )


def _section_state_checks() -> tuple[CheckConstraint, ...]:
    """One `CHECK` per section column: null, or one of the governed state codes.

    `IS NULL OR` is written out although SQL's three-valued `IN` would admit null on its own,
    because a reader should not need to know that to see the rule. Built from the same constants
    the migration restates as literals, and the drift test compares the two.
    """
    states = ", ".join(f"'{code}'" for code in SECTION_STATE_CODES)
    return tuple(
        CheckConstraint(
            f"{column} IS NULL OR {column} IN ({states})",
            name=f"ck_rca_workspace_tombstone_{column}",
        )
        for column in SECTION_COLUMNS
    )


def _subject_allowlist_check(
    subject: str, own: tuple[str, ...], foreign: tuple[str, ...], name: str
) -> CheckConstraint:
    """One subject's row must leave every column outside its own allowlist null.

    `foreign` minus `own`, because the two allowlists overlap: §3 puts a version id on both rows,
    and a check built from the other list wholesale would forbid the column its own subject is
    entitled to. Taking the difference is what makes the overlap expressible rather than a
    contradiction that no row could satisfy.

    Written as an implication -- `subject_kind <> '<subject>' OR (every foreign column IS NULL)` --
    because that is the form SQL `CHECK` evaluates per row without a subquery. `NULL` cannot appear
    in `subject_kind`, which is `nullable=False`, so the disjunction has no three-valued gap.
    """
    exclusive = tuple(column for column in foreign if column not in own)
    nulls = " AND ".join(f"{column} IS NULL" for column in exclusive)
    return CheckConstraint(f"subject_kind <> '{subject}' OR ({nulls})", name=name)


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
        _completion_provenance_check("ck_rca_workspace_run_completion_provenance"),
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
PROFILE_IDENTITY_FAILURE = "a source profile's identity and isolation scope cannot be reassigned"
TOMBSTONE_IMMUTABLE_FAILURE = "a deletion record cannot be rewritten"
TOMBSTONED_FROZEN_FAILURE = "a tombstoned record accepts no further update"
PARENT_TOMBSTONED_FAILURE = "a derivative cannot be added under a record that has been deleted"
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
    __table_args__ = (
        _scope_foreign_key("fk_rca_workspace_profile_scope"),
        # The same composite key runs and bindings carry. Validating `owner_id` alone lets a row
        # claim scope A while naming a version that does not exist, or one belonging to scope B --
        # a dangling or cross-tenant source association the reuse surface would then read. Review
        # on `#370` found the new table short of the pattern its siblings already followed.
        ForeignKeyConstraint(
            ["owner_id", "source_version_id"],
            [
                "rca_workspace_dataset_versions.owner_id",
                "rca_workspace_dataset_versions.version_id",
            ],
            name="fk_rca_workspace_profile_version",
            ondelete="RESTRICT",
        ),
    )

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
        _subject_allowlist_check(
            TOMBSTONE_VERSION,
            VERSION_TOMBSTONE_COLUMNS,
            RUN_TOMBSTONE_COLUMNS,
            "ck_rca_workspace_tombstone_version_fields",
        ),
        _subject_allowlist_check(
            TOMBSTONE_RUN,
            RUN_TOMBSTONE_COLUMNS,
            VERSION_TOMBSTONE_COLUMNS,
            "ck_rca_workspace_tombstone_run_fields",
        ),
        *_section_state_checks(),
        _version_identity_check(),
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
    # One column per report section (`TOMBSTONE_SECTIONS`), each holding one governed state code
    # or null. The section vocabulary is the column set; the state vocabulary is each column's
    # `CHECK`. Neither depends on a listener, so a Core or raw-SQL insert meets the same rule.
    section_overview: Mapped[str | None] = mapped_column(String, nullable=True)
    section_comparison: Mapped[str | None] = mapped_column(String, nullable=True)
    section_concentration: Mapped[str | None] = mapped_column(String, nullable=True)
    section_growth: Mapped[str | None] = mapped_column(String, nullable=True)
    section_basket: Mapped[str | None] = mapped_column(String, nullable=True)


def _changed_columns(target: object, among: frozenset[str] | None) -> set[str]:
    """Columns this update actually assigns a new value to, optionally narrowed to `among`.

    Assigning a column its existing value is not a change -- SQLAlchemy records no `deleted` history
    for it -- which is the same reason `set_retention_state` needs its own no-op check rather than
    relying on a guard.
    """
    state = sa_inspect(target)
    columns = (
        among
        if among is not None
        else frozenset(column.key for column in state.mapper.column_attrs)
    )
    return {column for column in columns if state.attrs[column].history.has_changes()}


def _leaving_started(target: object, changed: set[str]) -> bool:
    """Whether this update is the completion transition, taken once out of `started`."""
    return "state" in changed and _one_way(target, "state", RUN_STARTED)


def _check_completion_provenance(target: object) -> None:
    """A row leaving `started` for `completed` carries what `FR-111` says it produced.

    The `CHECK` constraint states this at the schema boundary and `RunOutcome` states it at the
    door, and neither covers this path: an ORM writer can load a `started` row and assign *only*
    `state = "completed"`, which satisfies `_check_completion`'s changed-column allowlist while
    every provenance column stays null. The row commits and then raises later on *read*, when
    `_run_from_row` builds the outcome -- failing the whole scope's listing. Review on `#370`
    found it after the `RunOutcome` fix, which is the same rule one layer up.
    """
    if getattr(target, "state", None) != RUN_COMPLETED:
        return
    if any(
        getattr(target, column, None) is None
        for column in ("package_digest", "package_version", "formula_version", "completed_at")
    ):
        raise ValueError(RUN_PROVENANCE_FAILURE)


def _check_completion(changed: set[str]) -> None:
    """A completion writes its own columns and no others.

    A completion permitted to touch `version_id` would rewrite which dataset a run derived from --
    provenance changed through the one write the guard allows.
    """
    if not changed <= COMPLETION_COLUMNS:
        raise ValueError(APPEND_ONLY_FAILURE)


def _check_terminal_state(target: object, changed: set[str]) -> None:
    """A tombstoned row accepts no further update at all.

    The one-way rule refused only a change *away* from `tombstoned`, so the row stayed otherwise
    open: an unsealed tombstoned version could still be sealed -- restarting the seven-day purge
    clock `KHEPRI-DEC-033` §2 starts at sealing, on a version already deleted -- and
    `retention_changed_at` could be rewritten, moving the §5 horizon after the fact. Both verified
    against the guard before fixing. Review on `#370` found it.

    Terminal means terminal: `tombstoned` is the end of the row's life, so the question "which
    columns may still move?" has the answer "none". Checked on the *prior* state rather than the
    new one, so the tombstoning update itself passes.
    """
    state = sa_inspect(target)
    if "retention_state" not in state.attrs:
        # `ArtifactBindingRow` has no retention state -- it is immutable outright, which
        # `_refuse_content_update`'s other rules already enforce. Hoisting this check to run on
        # every path exposed the assumption that all three guarded classes share the column; they
        # do not. Returning here rather than adding the column keeps "which rows have a retention
        # lifecycle" a property of the schema instead of a guard's precondition.
        return
    if _one_way(target, "retention_state", RETENTION_TOMBSTONED):
        return  # this update *is* the reversal; `_check_one_way_transitions` refuses it with a
        # message naming the reversal, which is the more specific answer.
    prior = state.attrs["retention_state"]
    was_tombstoned = (
        prior.history.deleted[0] if prior.history.deleted else target.retention_state
    ) == RETENTION_TOMBSTONED
    if was_tombstoned and changed:
        raise ValueError(TOMBSTONED_FROZEN_FAILURE)


def _check_one_way_transitions(target: object, changed: set[str]) -> None:
    """The two mutable columns that may each move in one direction only.

    Split from `_check_append_only`, which had grown to four rules of two kinds -- *which* columns
    an update may touch, and *which way* the two mutable ones may move. CodeScene put the combined
    function at cyclomatic 11 against a threshold of 9 on `#370`, and the split is the honest one:
    a reader asking "can this column change at all?" and one asking "can it change back?" are
    asking different questions.
    """
    if "sealed_at" in changed and not _one_way(target, "sealed_at", None):
        raise ValueError(RESEAL_FAILURE)
    if "retention_state" in changed and _one_way(target, "retention_state", RETENTION_TOMBSTONED):
        raise ValueError(TOMBSTONE_FAILURE)


def _check_append_only(target: object, changed: set[str]) -> None:
    """Every update that is not a completion: content is frozen and one-way stays one-way."""
    if changed & COMPLETION_COLUMNS:
        raise ValueError(RECOMPLETE_FAILURE)
    if not changed <= MUTABLE_COLUMNS:
        raise ValueError(APPEND_ONLY_FAILURE)
    _check_one_way_transitions(target, changed)


def _refuse_identity_change(_mapper, _connection, target: object) -> None:
    """A profile's document may change; the row it *is* may not.

    `FR-115` makes the profile metadata a surface reads to pre-fill a form, carrying no authority --
    so `column_labels` and `proposed_mapping` are deliberately mutable. But loading a profile from
    scope A and assigning it a valid scope-B `owner_id` committed successfully, because the foreign
    key checks only that B exists: scope B's next read would then return scope A's column labels.
    Review on `#370` found it. The composite foreign key added in the same round makes the pair
    unrepresentable at the schema level; this refuses the reassignment one statement earlier, and
    covers `source_version_id` too, which no constraint can pin to its original value.
    """
    changed = _changed_columns(target, PROFILE_IDENTITY_COLUMNS)
    if changed:
        raise ValueError(PROFILE_IDENTITY_FAILURE)


def _refuse_any_update(_mapper, _connection, target: object) -> None:
    """A tombstone records that something was deleted. Nothing about it may be rewritten.

    It sat outside both registrations, so an ordinary session could rewrite its owner, its subject
    identifiers, the deletion instant, or the digests it preserves -- and `KHEPRI-DEC-033` §5
    anchors a bounded horizon to `deleted_at`. A mutable deletion record is not a deletion record.
    Review on `#370` found it.

    Frozen entirely rather than append-only, because a tombstone has no lifecycle: it is written
    once by the deletion and read thereafter. The later lifecycle purge that removes expired
    tombstones is a *delete*, which `_refuse_delete` still refuses -- `W1-07` owns that operation
    and must take an explicit exemption when it arrives, which is the conversation this guard
    exists to force.
    """
    if _changed_columns(target, None):
        raise ValueError(TOMBSTONE_IMMUTABLE_FAILURE)


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
    # Terminal state first, and unconditionally. It was called from inside `_check_append_only`,
    # which reads as "one more append-only rule" -- but it is a *precondition on every path*, and
    # putting it in a branch made it conditional on not taking the other one. A tombstoned run
    # still reads `started`, so it took the completion branch and returned before the terminal
    # check ever ran: a deleted run could be completed. Confirmed against the guard, then fixed.
    # Review on `#370` found it.
    _check_terminal_state(target, changed)
    if _leaving_started(target, changed):
        _check_completion(changed)
        _check_completion_provenance(target)
        return
    _check_append_only(target, changed)


#: Three guard shapes, side by side, because this table is the only place they are comparable.
#: A single loop over every row class had encoded one shape and left the other two unguarded --
#: review on `#370` found a profile's scope reassignable and a tombstone freely rewritable.
#:
#: ======================  ==========================================  ===================
#: rows                    update                                      delete
#: ======================  ==========================================  ===================
#: versions/runs/bindings  append-only, one-way transitions preserved  refused
#: source profiles         identity frozen, document free (`FR-115`)   **allowed** (§3 purge)
#: tombstones              frozen entirely                             refused
#: ======================  ==========================================  ===================
#:
#: The profile's delete is the one exemption, and `KHEPRI-DEC-033` §3 is why: its row reads
#: "none -- purged, not tombstoned", so a blanket guard would forbid the purge the decision
#: prescribes. That exemption covers deletion only -- it never licensed a scope reassignment.
_ROW_GUARDS = {
    DatasetVersionRow: (_refuse_content_update, _refuse_delete),
    AnalysisRunRow: (_refuse_content_update, _refuse_delete),
    ArtifactBindingRow: (_refuse_content_update, _refuse_delete),
    SourceProfileRow: (_refuse_identity_change, None),
    WorkspaceTombstoneRow: (_refuse_any_update, _refuse_delete),
}

for _row_class, (_on_update, _on_delete) in _ROW_GUARDS.items():
    event.listen(_row_class, "before_update", _on_update)
    if _on_delete is not None:
        event.listen(_row_class, "before_delete", _on_delete)
