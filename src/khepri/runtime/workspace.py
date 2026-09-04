"""The workspace services (`W1-04`; `RCA-005` `FR-110`, `FR-111`, `FR-114`, `FR-125`).

Six actions over the workspace records, each authorized through `IsolationService.resolve_scope`,
each performed against what the existing `RRA` pipeline already produced, each leaving exactly one
content-free audit event.

## Why this module is in `khepri.runtime`

It calls `khepri.rra` -- `ProfilingService` for the admission, `FactPackageService` for the
derivation, the delivery and artifact repositories for the report -- and `khepri.rca.workspace` for
the records. `R7-01` §3 forbids either package importing the other, so the one place that may know
both is the composition layer, beside `bridge.py`, which records the argument in full.

## No second admission, no second derivation

`FR-110`: a dataset version is created only by the existing `RRA-003` admission path. This module
never profiles bytes; it asks `ProfilingService` what the session's admission decided and records
that. `FR-111`: a run is produced only by the existing pipeline; this module never derives a fact
or renders a surface; it asks `FactPackageService` for the package and the report boundary for the
delivery and its artifacts, checks that what it was handed belongs to the run's version, and binds
it by digest. `test_w104_workspace_services.py` asserts the negative on this module's source: no
admission internal is imported.

## What crosses, and what does not

```
account_id + organization_id       <- RCA vocabulary, stops at resolve_scope
        |
     owner_id                      <- the only identity that crosses (FR-032, FR-033)
        |
session_id / job_id                <- RRA object identifiers, confer nothing (FR-023),
                                      read under owner_id, never written to a workspace row
```

A session identifier is bearer-adjacent and `KHEPRI-DEC-015` §7 keeps it out of every log, so no
workspace record and no audit event holds one. The link from a version to its upload is the upload's
digests; from a run to its package, the package digest. `dataset_version_for_upload` reads the
ciphertext digest back for the idempotent retry.

## One event per action

Every public method resolves the scope first -- a caller with no standing gets `ScopeAccessDenied`
and the workspace records nothing, because there is no scope to record it in -- then performs the
action inside `_perform`, which writes exactly one event: `completed` or `already_recorded` on
return, `refused` when the action raises `WorkspaceRefused`. Any other exception is a fault, not an
outcome, and is not recorded as one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from khepri.rca.isolation import IsolationService
from khepri.rca.workspace.audit import (
    ACTION_PROFILE_REMEMBERED,
    ACTION_PROFILE_REUSED,
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    OBJECT_PROFILE,
    OBJECT_RUN,
    OBJECT_VERSION,
    OUTCOME_ALREADY_RECORDED,
    OUTCOME_COMPLETED,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STARTED,
    AdmittedSource,
    AnalysisRun,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
    SourceProfile,
    _identifier,
)
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rca.workspace.profile_store import SqlSourceProfileStore
from khepri.rra.datasets import DatasetProfileRecord, ProfilingService, document_digest
from khepri.rra.datasets import stored_manifest as _stored_manifest
from khepri.rra.intake import UploadMetadata, UploadRepository
from khepri.rra.packages import FactPackageRecord, FactPackageService
from khepri.rra.pipeline import DeliveryRecord
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.rra.sessions import SessionStore

#: The admission outcome code a version records. Only an admitted source becomes a version --
#: `KHEPRI-DEC-033` §2 calls the version "the durable identity of one admitted source" -- so a
#: refused admission is refused here too, and the code has one value this slice can write.
ADMISSION_ADMITTED = "admitted"
#: Rows of the mapping document in this state name the column they were placed on.
_MAPPED = "mapped"

# Content-free, per `rca/errors.py`: each names the constraint, never the caller's input.
NO_SESSION_FAILURE = "No analysis session answers to this request in this scope."
NO_ADMISSION_FAILURE = "No admission is recorded for this analysis."
ADMISSION_REFUSED_FAILURE = "The source was not admitted, so no dataset version can record it."
NO_ATTESTATION_FAILURE = "The admission carries no coverage attestation for a version to keep."
NO_VERSION_FAILURE = "No live dataset version answers to this identifier in this scope."
NO_RUN_FAILURE = (
    "No live analysis run awaiting completion answers to this identifier in this scope."
)
NO_DERIVATION_FAILURE = "No fact package has been derived for this analysis."
PROVENANCE_FAILURE = "The package was not derived from the run's dataset version."
NO_DELIVERY_FAILURE = "No report was delivered for this job in this analysis."
BUNDLE_INCOMPLETE_FAILURE = "The report bundle does not name every required artifact."
PROFILE_MISMATCH_FAILURE = "The admission does not describe this dataset version."
NO_PROFILE_FAILURE = "No source profile answers to this identifier in this scope."


class WorkspaceRefused(ValueError):
    """An action the workspace declines, with a content-free reason. Recorded as `refused`."""


class DeliveryReader(Protocol):
    def find_delivery(self, job_id: str) -> DeliveryRecord | None: ...


class StoredArtifactLike(Protocol):
    sha256_hex: str


class ArtifactReader(Protocol):
    def find_in_session(
        self, *, session_id: str, job_id: str, artifact_kind: str, now: datetime
    ) -> StoredArtifactLike | None: ...


@dataclass(frozen=True, slots=True)
class WorkspacePorts:
    """The `RRA` side: where admission, derivation and the report already happened."""

    sessions: SessionStore
    uploads: UploadRepository
    profiling: ProfilingService
    packages: FactPackageService
    deliveries: DeliveryReader
    artifacts: ArtifactReader


@dataclass(frozen=True, slots=True)
class RecordStores:
    """The `RCA` side: where the workspace records and their audit trail live."""

    workspace: SqlWorkspaceRecordStore
    profiles: SqlSourceProfileStore
    audit: SqlWorkspaceAuditStore


@dataclass(frozen=True, slots=True)
class Performed[T]:
    """What one action produced, how it ended, and which object it was about."""

    result: T
    outcome: str
    subject: AuditSubject


class WorkspaceActions:
    """Create versions and runs, complete runs, remember and offer source profiles."""

    def __init__(
        self, *, isolation: IsolationService, rra: WorkspacePorts, rca: RecordStores
    ) -> None:
        self._isolation = isolation
        self._rra = rra
        self._rca = rca

    # --- FR-110: a version records the admission the session holds ----------------------------

    def create_dataset_version(
        self, *, account_id: str, organization_id: str, session_id: str, now: datetime
    ) -> DatasetVersion:
        """Record the session's `RRA-003` admission as a dataset version, once."""
        actor = self._actor(account_id, organization_id)
        return self._perform(
            actor,
            ACTION_VERSION_CREATED,
            lambda: self._create_version(actor.owner_id, session_id, now),
            now=now,
        )

    def _create_version(
        self, owner_id: str, session_id: str, now: datetime
    ) -> Performed[DatasetVersion]:
        upload, profile = self._admission(owner_id, session_id, now)
        existing = self._rca.workspace.dataset_version_for_upload(
            owner_id, upload.ciphertext_sha256_hex
        )
        if existing is not None:
            return Performed(existing, OUTCOME_ALREADY_RECORDED, _subject_of_version(existing))
        if not profile.admissible:
            raise WorkspaceRefused(ADMISSION_REFUSED_FAILURE)
        manifest = _stored_manifest(profile)
        if manifest is None:
            raise WorkspaceRefused(NO_ATTESTATION_FAILURE)
        version = DatasetVersion.create(
            owner_id=owner_id,
            source=AdmittedSource(
                plaintext_digest=upload.sha256_hex,
                ciphertext_digest=upload.ciphertext_sha256_hex,
                size_bytes=upload.size_bytes,
                media_type=upload.media_type,
                manifest_digest=document_digest(manifest.as_document()),
                mapping_version=profile.mapping_version,
                admission_outcome=ADMISSION_ADMITTED,
            ),
            now=now,
        )
        self._rca.workspace.add_dataset_version(version)
        return Performed(version, OUTCOME_COMPLETED, _subject_of_version(version))

    def _admission(
        self, owner_id: str, session_id: str, now: datetime
    ) -> tuple[UploadMetadata, DatasetProfileRecord]:
        """The session's upload and the profile `RRA-003` admitted it under, both in scope.

        The session is looked up by the `(owner_id, session_id)` pair, so another scope's session
        is `None` here and indistinguishable from no session (`FR-023`, `FR-025`). The profile is
        read through `ProfilingService`, which is the admission entry point -- this module holds no
        other way to a profile, and `test_w104_workspace_services.py` asserts that on its source.
        """
        if self._rra.sessions.get_session_for_owner(owner_id, session_id) is None:
            raise WorkspaceRefused(NO_SESSION_FAILURE)
        upload = self._rra.uploads.get_upload_for_session(session_id)
        try:
            profile = self._rra.profiling.get_session_profile(session_id=session_id, now=now)
        except PermissionError as refused:
            raise WorkspaceRefused(NO_ADMISSION_FAILURE) from refused
        if upload is None or profile is None or profile.source_sha256_hex != upload.sha256_hex:
            raise WorkspaceRefused(NO_ADMISSION_FAILURE)
        return upload, profile

    # --- FR-111: a run is produced by the pipeline and bound to its artifacts by digest ---------

    def start_analysis_run(
        self, *, account_id: str, organization_id: str, version_id: str, now: datetime
    ) -> AnalysisRun:
        """Open a run over a live version. Incomplete by construction; the pipeline fills it."""
        actor = self._actor(account_id, organization_id)
        return self._perform(
            actor,
            ACTION_RUN_STARTED,
            lambda: self._start_run(actor.owner_id, version_id, now),
            now=now,
        )

    def _start_run(self, owner_id: str, version_id: str, now: datetime) -> Performed[AnalysisRun]:
        if self._rca.workspace.get_dataset_version(version_id, owner_id) is None:
            raise WorkspaceRefused(NO_VERSION_FAILURE)
        run = AnalysisRun.create(owner_id=owner_id, version_id=version_id, now=now)
        try:
            self._rca.workspace.add_analysis_run(run)
        except ValueError as refused:
            # The parent was tombstoned between the read and the locked insert.
            raise WorkspaceRefused(NO_VERSION_FAILURE) from refused
        return Performed(run, OUTCOME_COMPLETED, _subject_of_run(run))

    def complete_analysis_run(
        self,
        *,
        account_id: str,
        organization_id: str,
        run_id: str,
        session_id: str,
        job_id: str,
        now: datetime,
    ) -> AnalysisRun:
        """Record what the pipeline produced for a run: its package and every artifact, by digest.

        `session_id` and `job_id` say where to look; they are checked, never trusted. The package
        must derive from the run's own version, the delivery must belong to the session, and every
        required artifact kind must be present -- or the run stays `started` and nothing is bound.
        """
        actor = self._actor(account_id, organization_id)
        return self._perform(
            actor,
            ACTION_RUN_COMPLETED,
            lambda: self._complete_run(actor.owner_id, run_id, (session_id, job_id), now),
            now=now,
        )

    def _complete_run(
        self, owner_id: str, run_id: str, where: tuple[str, str], now: datetime
    ) -> Performed[AnalysisRun]:
        session_id, job_id = where
        run, version = self._awaiting_run(owner_id, run_id)
        package = self._derivation(owner_id, session_id, now)
        if (package.source_sha256_hex, package.mapping_version) != (
            version.upload_plaintext_digest,
            version.mapping_version,
        ):
            raise WorkspaceRefused(PROVENANCE_FAILURE)
        artifacts = self._published_artifacts(session_id, job_id, now)
        outcome = RunOutcome(
            state=RUN_COMPLETED,
            package_digest=package.package_digest,
            package_version=package.package_version,
            formula_version=package.formula_version,
            completed_at=now,
        )
        if not self._rca.workspace.record_completion(
            run.run_id, outcome, artifacts, now=now, owner_id=owner_id
        ):
            raise WorkspaceRefused(NO_RUN_FAILURE)
        return self._reread_run(run.run_id, owner_id)

    def _awaiting_run(self, owner_id: str, run_id: str) -> tuple[AnalysisRun, DatasetVersion]:
        run = self._rca.workspace.get_analysis_run(run_id, owner_id)
        if run is None or run.state != RUN_STARTED:
            raise WorkspaceRefused(NO_RUN_FAILURE)
        version = self._rca.workspace.get_dataset_version(run.version_id, owner_id)
        if version is None:
            raise WorkspaceRefused(NO_VERSION_FAILURE)
        return run, version

    def _derivation(self, owner_id: str, session_id: str, now: datetime) -> FactPackageRecord:
        """The session's `RRA-004` package, read through the service that validates it."""
        if self._rra.sessions.get_session_for_owner(owner_id, session_id) is None:
            raise WorkspaceRefused(NO_SESSION_FAILURE)
        try:
            package = self._rra.packages.get_session_package(session_id=session_id, now=now)
        except PermissionError as refused:
            raise WorkspaceRefused(NO_DERIVATION_FAILURE) from refused
        if package is None:
            raise WorkspaceRefused(NO_DERIVATION_FAILURE)
        return package

    def _published_artifacts(
        self, session_id: str, job_id: str, now: datetime
    ) -> tuple[PublishedArtifact, ...]:
        """Every required artifact kind, each with its own digest, or a refusal (`FR-111`)."""
        delivery = self._rra.deliveries.find_delivery(job_id)
        if delivery is None or delivery.session_id != session_id:
            raise WorkspaceRefused(NO_DELIVERY_FAILURE)
        published = []
        for kind in REQUIRED_ARTIFACT_KINDS:
            stored = self._rra.artifacts.find_in_session(
                session_id=session_id, job_id=job_id, artifact_kind=kind, now=now
            )
            if stored is None:
                raise WorkspaceRefused(BUNDLE_INCOMPLETE_FAILURE)
            published.append(PublishedArtifact(surface=kind, artifact_digest=stored.sha256_hex))
        return tuple(published)

    def fail_analysis_run(
        self, *, account_id: str, organization_id: str, run_id: str, now: datetime
    ) -> AnalysisRun:
        """End a run the pipeline did not deliver, as `failed`: a real state, with no provenance."""
        actor = self._actor(account_id, organization_id)
        return self._perform(
            actor, ACTION_RUN_FAILED, lambda: self._fail_run(actor.owner_id, run_id, now), now=now
        )

    def _fail_run(self, owner_id: str, run_id: str, now: datetime) -> Performed[AnalysisRun]:
        run, _version = self._awaiting_run(owner_id, run_id)
        if not self._rca.workspace.complete_analysis_run(
            run.run_id, RunOutcome(state=RUN_FAILED, completed_at=now), owner_id=owner_id
        ):
            raise WorkspaceRefused(NO_RUN_FAILURE)
        return self._reread_run(run.run_id, owner_id)

    def _reread_run(self, run_id: str, owner_id: str) -> Performed[AnalysisRun]:
        run = self._rca.workspace.get_analysis_run(run_id, owner_id)
        if run is None:  # pragma: no cover -- the row was locked and written one statement ago
            raise WorkspaceRefused(NO_RUN_FAILURE)
        return Performed(run, OUTCOME_COMPLETED, _subject_of_run(run))

    # --- FR-114 / FR-115: the source profile, remembered and offered ----------------------------

    def remember_source_profile(
        self,
        *,
        account_id: str,
        organization_id: str,
        version_id: str,
        session_id: str,
        now: datetime,
    ) -> SourceProfile:
        """Keep the admitted mapping's shape beside its version, as metadata a form can read.

        `FR-115`: descriptive only. What is stored is the profile's *safe* column labels and the
        `(semantic, safe label)` pairs the admitted mapping placed -- what pre-fills a form -- and
        nothing a check could be read from. `SourceProfile`'s field set is `W1-01`'s equality.
        """
        actor = self._actor(account_id, organization_id)
        return self._perform(
            actor,
            ACTION_PROFILE_REMEMBERED,
            lambda: self._remember(actor.owner_id, version_id, session_id, now),
            now=now,
        )

    def _remember(
        self, owner_id: str, version_id: str, session_id: str, now: datetime
    ) -> Performed[SourceProfile]:
        version = self._rca.workspace.get_dataset_version(version_id, owner_id)
        if version is None:
            raise WorkspaceRefused(NO_VERSION_FAILURE)
        _upload, profile = self._admission(owner_id, session_id, now)
        if (profile.source_sha256_hex, profile.mapping_version) != (
            version.upload_plaintext_digest,
            version.mapping_version,
        ):
            raise WorkspaceRefused(PROFILE_MISMATCH_FAILURE)
        remembered = SourceProfile(
            profile_id=_identifier("spf"),
            owner_id=owner_id,
            source_version_id=version.version_id,
            column_labels=_safe_labels(profile),
            proposed_mapping=_placed_mapping(profile),
            created_at=now,
        )
        self._rca.profiles.add(remembered)
        return Performed(remembered, OUTCOME_COMPLETED, _subject_of_profile(remembered))

    def propose_reuse(
        self, *, account_id: str, organization_id: str, profile_id: str, now: datetime
    ) -> SourceProfile:
        """Offer a remembered profile for the customer to see before confirming (`FR-114`).

        Audited although it writes nothing: `FR-125` names profile reuse, and the showing is the
        action. The proposal pre-fills a form; the admission that follows runs on what the customer
        submits, against the new source, and refuses on its own terms.
        """
        actor = self._actor(account_id, organization_id)
        return self._perform(
            actor,
            ACTION_PROFILE_REUSED,
            lambda: self._propose(actor.owner_id, profile_id),
            now=now,
        )

    def _propose(self, owner_id: str, profile_id: str) -> Performed[SourceProfile]:
        profile = self._rca.profiles.get(profile_id, owner_id)
        if profile is None:
            raise WorkspaceRefused(NO_PROFILE_FAILURE)
        return Performed(profile, OUTCOME_COMPLETED, _subject_of_profile(profile))

    # --- authorization and the audit trail -----------------------------------------------------

    def _actor(self, account_id: str, organization_id: str) -> AuditActor:
        """Resolve the scope -- the one authorization door -- and name the actor within it."""
        owner_id = self._isolation.resolve_scope(account_id, organization_id)
        return AuditActor(owner_id=owner_id, actor_account_id=account_id)

    def _perform[T](
        self, actor: AuditActor, action: str, act: Callable[[], Performed[T]], *, now: datetime
    ) -> T:
        """Run one action and record exactly one event for it, whichever way it ends."""
        try:
            performed = act()
        except WorkspaceRefused:
            self._rca.audit.record(WorkspaceAuditEvent.refused(actor, action, None, now=now))
            raise
        door = (
            WorkspaceAuditEvent.already_recorded
            if performed.outcome == OUTCOME_ALREADY_RECORDED
            else WorkspaceAuditEvent.completed
        )
        self._rca.audit.record(door(actor, action, performed.subject, now=now))
        return performed.result


def _subject_of_version(version: DatasetVersion) -> AuditSubject:
    return AuditSubject(OBJECT_VERSION, version.version_id)


def _subject_of_run(run: AnalysisRun) -> AuditSubject:
    return AuditSubject(OBJECT_RUN, run.run_id)


def _subject_of_profile(profile: SourceProfile) -> AuditSubject:
    return AuditSubject(OBJECT_PROFILE, profile.profile_id)


def _safe_labels(profile: DatasetProfileRecord) -> tuple[str, ...]:
    """The profile's sanitized column labels, in column order -- never the source headers."""
    return tuple(str(column["safe_label"]) for column in profile.document["profile"]["columns"])


def _placed_mapping(profile: DatasetProfileRecord) -> tuple[tuple[str, str], ...]:
    """Each mapped semantic and the safe label of the column the admission placed it on."""
    return tuple(
        (str(mapping["semantic"]), str(mapping["candidates"][0]["safe_label"]))
        for mapping in profile.document["mapping"]["mappings"]
        if mapping["state"] == _MAPPED
    )
