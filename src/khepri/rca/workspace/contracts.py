"""Workspace domain contracts (`RCA-005` `FR-109`, `FR-110`, `FR-112`, `FR-115`).

Four types, split across a line worth stating explicitly because a later slice
will be tempted to move something across it.

**Sealed — records the domain acts on.** `DatasetVersion`, `AnalysisRun` and
`ArtifactBinding` follow `records.py`'s two-door rule: `create` allocates,
`_from_storage` preserves, and they never meet. Persistence accepts only the
exact types registered by `@register_sealed`, so a forged instance is not
merely rejected at a boundary — it cannot reach one.

**Unsealed — metadata a surface reads.** `SourceProfile` is descriptive only.
Sealing it would imply a door exists to construct profiles through, and that
shape is what invites a later slice to treat a profile as authority for an
admission it never performed. `FR-115` says a profile pre-fills the *form* and
the check runs on what is submitted; the type carries no field a check could be
read from, and `test_w101_workspace_contracts.py` asserts that as an equality
over its field set rather than as an absence. The same reasoning keeps
`OrganizationMember` unsealed in `rca/organizations.py`.

**Why `owner_id` and not an organization identifier.** `RCA-001` `FR-031`–
`FR-035` map an organization to one opaque isolation scope, and `FR-033`
forbids a commercial identifier appearing in or being derivable from it. Every
record here is keyed by that opaque scope. A `organization_id` field would be
the commercial identifier arriving by another name.

**Sealing is an event, not an argument.** `DatasetVersion.create` has no
`sealed_at` parameter. `KHEPRI-DEC-033` starts the raw upload's seven-day purge
clock at sealing — "facts derived and reconciled" — so a version that could
arrive already sealed would start that clock before its facts exist. The
transition is `W1-02`'s to write as an operation against the store.

No persistence, no service, and no computation live here.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime

from khepri.rca.records import Sealed, register_sealed, through_door


def _identifier(prefix: str) -> str:
    """An opaque identifier carrying no commercial meaning (`FR-109`).

    `secrets` rather than a counter or a hash of anything the customer supplied:
    a derived identifier would make the source recoverable from the key, which
    is what `RCA-001` `FR-033` forbids.
    """
    return f"{prefix}_{secrets.token_urlsafe(18)}"


@dataclass(frozen=True, slots=True)
class AdmittedSource:
    """What admission established about one file, as one value.

    Grouped rather than passed as seven parameters. These fields always travel
    together -- `RRA-003` produces all of them in one admission and no caller
    holds a subset -- so a flat signature would spread one fact across seven
    arguments and let a caller pair a digest with another file's size. It is
    unsealed because it is an argument to a door, not a record that survives
    one: `DatasetVersion` is what persists.
    """

    plaintext_digest: str
    ciphertext_digest: str
    size_bytes: int
    media_type: str
    manifest_digest: str
    mapping_version: str
    admission_outcome: str


@register_sealed
@dataclass(frozen=True, slots=True)
class DatasetVersion(Sealed):
    """One admitted source, as `RCA-005` defines it.

    Immutable once sealed; after that only its retention state changes, which
    `W1-02` holds in the store rather than on this record. A new file is a new
    version — never an edit to this one.
    """

    version_id: str
    owner_id: str
    upload_plaintext_digest: str
    upload_ciphertext_digest: str
    upload_size_bytes: int
    upload_media_type: str
    manifest_digest: str
    mapping_version: str
    admission_outcome: str
    created_at: datetime
    sealed_at: datetime | None

    @staticmethod
    def _build(
        version_id: str,
        owner_id: str,
        source: AdmittedSource,
        created_at: datetime,
        sealed_at: datetime | None,
    ) -> DatasetVersion:
        """The constructor call both doors share.

        Extracted because the two bodies were byte-identical apart from
        `version_id` and `sealed_at`, which CodeScene reads as duplication and
        which is also how the two doors would drift: a field added to one and
        forgotten in the other produces a record that differs by which door it
        came through.

        **This does not weaken the two-door rule.** The doors keep their own
        distinct signatures -- `create` still has no `version_id` or `sealed_at`
        parameter, so a stored-only value stays unexpressible there -- and this
        helper is called *inside* an already-open door. It reads only its own
        arguments and runs no caller code, so the window `records.py` requires
        stays a single constructor call.
        """
        return DatasetVersion(
            version_id=version_id,
            owner_id=owner_id,
            upload_plaintext_digest=source.plaintext_digest,
            upload_ciphertext_digest=source.ciphertext_digest,
            upload_size_bytes=source.size_bytes,
            upload_media_type=source.media_type,
            manifest_digest=source.manifest_digest,
            mapping_version=source.mapping_version,
            admission_outcome=source.admission_outcome,
            created_at=created_at,
            sealed_at=sealed_at,
        )

    @classmethod
    def create(cls, *, owner_id: str, source: AdmittedSource, now: datetime) -> DatasetVersion:
        with through_door():
            return cls._build(_identifier("dsv"), owner_id, source, now, None)

    @classmethod
    def _from_storage(
        cls,
        *,
        version_id: str,
        owner_id: str,
        source: AdmittedSource,
        created_at: datetime,
        sealed_at: datetime | None,
    ) -> DatasetVersion:
        with through_door():
            return cls._build(version_id, owner_id, source, created_at, sealed_at)


@register_sealed
@dataclass(frozen=True, slots=True)
class AnalysisRun(Sealed):
    """One derivation over one dataset version at one instant.

    Created incomplete: a run that could arrive with a package digest would be
    a run whose result preceded its execution. `FR-111` requires the digest and
    the artifact bindings to come from the real pipeline, so completion is an
    operation `W1-04` performs, not a value a caller supplies here.
    """

    run_id: str
    version_id: str
    owner_id: str
    package_digest: str | None
    package_version: str | None
    formula_version: str | None
    state: str
    started_at: datetime
    completed_at: datetime | None

    @staticmethod
    def _build(
        run_id: str,
        owner_id: str,
        version_id: str,
        outcome: RunOutcome,
        started_at: datetime,
    ) -> AnalysisRun:
        """The constructor call both doors share. See `DatasetVersion._build`."""
        return AnalysisRun(
            run_id=run_id,
            version_id=version_id,
            owner_id=owner_id,
            package_digest=outcome.package_digest,
            package_version=outcome.package_version,
            formula_version=outcome.formula_version,
            state=outcome.state,
            started_at=started_at,
            completed_at=outcome.completed_at,
        )

    @classmethod
    def create(cls, *, owner_id: str, version_id: str, now: datetime) -> AnalysisRun:
        with through_door():
            return cls._build(
                _identifier("run"), owner_id, version_id, RunOutcome(state=RUN_STARTED), now
            )

    @classmethod
    def _from_storage(
        cls,
        *,
        run_id: str,
        owner_id: str,
        version_id: str,
        outcome: RunOutcome,
        started_at: datetime,
    ) -> AnalysisRun:
        with through_door():
            return cls._build(run_id, owner_id, version_id, outcome, started_at)


# The operational states of a run. Named as a tuple so the domain, the store and the schema
# constrain the same values rather than each spelling them out -- the pattern `ROLES` follows
# in `rca/organizations.py`.
RUN_STARTED = "started"
RUN_COMPLETED = "completed"
RUN_FAILED = "failed"
RUN_STATES = (RUN_STARTED, RUN_COMPLETED, RUN_FAILED)

# Content-free, per the refusal discipline in `rca/errors.py`: it names the constraint, never
# the rejected value, so a refusal cannot echo a caller's input back into a log.
RUN_STATE_FAILURE = "Run state is not one of the states this domain defines."


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """What a run's execution produced, as one value.

    Grouped for the same reason as `AdmittedSource`: these five fields are one
    fact about one completed derivation, and a caller holding three of them has
    a half-finished run rather than three independent values. Only
    `_from_storage` takes it -- `create` cannot, because `FR-111` puts the
    digest and versions on the real pipeline rather than on whoever starts the
    run.
    """

    state: str
    package_digest: str | None = None
    package_version: str | None = None
    formula_version: str | None = None
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        """Refuse a state `RUN_STATES` does not name.

        `RUN_STATES` published the vocabulary and nothing read it, so
        `RunOutcome(state="cancelled")` reached `AnalysisRun._from_storage`
        and was copied into a sealed record. A tuple that only *documents* its
        values is the *defined but never attached* defect: the constraint has
        prose and no code path.

        The check lives here rather than on `AnalysisRun` because `Sealed`
        rejects a subclass defining `__post_init__` at class-definition time
        (`records.py`), and because this is the type a caller actually fills
        in. Validating the argument is a different property from sealing the
        record: sealing proves a record came through a door, never that the
        door checked what it was handed.

        Fail-closed per Constitution V — an unrecognized state is refused, not
        coerced to a default.
        """
        if self.state not in RUN_STATES:
            raise ValueError(RUN_STATE_FAILURE)


@register_sealed
@dataclass(frozen=True, slots=True)
class ArtifactBinding(Sealed):
    """One published surface of one run's bundle, bound by digest.

    Bound rather than stored: the bytes live in the object store under
    `RRA-002`'s encryption, and this record says which digest belongs to which
    run. `RRA-006` publishes a bundle together or not at all, so `FR-111` reads
    a run naming fewer than every required surface as incomplete.
    """

    run_id: str
    owner_id: str
    surface: str
    artifact_digest: str
    published_at: datetime

    @staticmethod
    def _build(
        run_id: str,
        owner_id: str,
        surface: str,
        artifact_digest: str,
        published_at: datetime,
    ) -> ArtifactBinding:
        """The constructor call both doors share. See `DatasetVersion._build`."""
        return ArtifactBinding(
            run_id=run_id,
            owner_id=owner_id,
            surface=surface,
            artifact_digest=artifact_digest,
            published_at=published_at,
        )

    @classmethod
    def create(
        cls,
        *,
        owner_id: str,
        run_id: str,
        surface: str,
        artifact_digest: str,
        now: datetime,
    ) -> ArtifactBinding:
        with through_door():
            return cls._build(run_id, owner_id, surface, artifact_digest, now)

    @classmethod
    def _from_storage(
        cls,
        *,
        run_id: str,
        owner_id: str,
        surface: str,
        artifact_digest: str,
        published_at: datetime,
    ) -> ArtifactBinding:
        with through_door():
            return cls._build(run_id, owner_id, surface, artifact_digest, published_at)


@dataclass(frozen=True, slots=True)
class SourceProfile:
    """Descriptive metadata from a prior dataset version, offered for re-attestation.

    **Not `Sealed`, and the omission is the point.** A profile is read by a
    surface to pre-fill a mapping form; it is never authority for anything. If
    it carried an admission outcome, a later slice would read that field and
    skip the `RRA-003` check `FR-115` says must always run against the new
    source. The field set is asserted as an equality in
    `test_w101_workspace_contracts.py`, so such a field fails a test before it
    can be consumed.

    `proposed_mapping` is a tuple of pairs rather than a dict so the record
    stays hashable and immutable alongside the sealed records above, and so the
    word *proposed* survives into the type: what is stored is a suggestion, and
    what is admitted is whatever `RRA-003` accepts from the new submission.
    """

    profile_id: str
    owner_id: str
    source_version_id: str
    column_labels: tuple[str, ...]
    proposed_mapping: tuple[tuple[str, str], ...] = field(default=())
    created_at: datetime | None = None
