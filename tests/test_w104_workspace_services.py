"""`W1-04` -- the workspace services (`RCA-005` `FR-110`, `FR-111`, `FR-114`, `FR-125`).

Written before `khepri.runtime.workspace` and `khepri.rca.workspace.audit` exist.

**Driven through the real admission.** The `G3-04` plan names this slice's one risk: a second
admission path. "If this slice can create a dataset version without calling `RRA-003`, `FR-110` is
violated however the code reads." So every version here is created from a session whose upload was
admitted by the real `ProfilingService` over real bytes, and every run is completed from a package
the real `FactPackageService` derived. The only fakes are at the report boundary -- the delivery
record and the stored artifacts -- because the pipeline that produces them needs Chromium and a
worker, and `RRA-006`'s own tests prove it. The service *reads* those products; it makes none.

**Why the services live in `khepri.runtime`.** They call `khepri.rra` for admission and the pipeline
and `khepri.rca` for the workspace records, and `R7-01` §3 forbids either package importing the
other. `runtime/bridge.py` records why the composition layer is the one place that may know both.

**One audit event per action, by count.** `FR-125` says every workspace action emits one
content-free event. Each test here counts the events in the scope after the call -- one more than
before, whether the action completed or was refused -- rather than asserting that some event exists.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.audit import (
    ACTION_PROFILE_REMEMBERED,
    ACTION_PROFILE_REUSED,
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    AUDIT_ACTIONS,
    AUDIT_OBJECTS,
    AUDIT_OUTCOMES,
    OBJECT_PROFILE,
    OBJECT_RUN,
    OBJECT_VERSION,
    OUTCOME_ALREADY_RECORDED,
    OUTCOME_COMPLETED,
    OUTCOME_REFUSED,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import (
    SqlWorkspaceAuditStore,
    WorkspaceAuditEventRow,
)
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_STARTED,
    SourceProfile,
)
from khepri.rca.workspace.persistence import SqlWorkspaceStore
from khepri.rca.workspace.profile_store import SqlSourceProfileStore
from khepri.rra.coverage_request import CoverageManifestBody
from khepri.rra.datasets import ProfilingService, document_digest, stored_manifest
from khepri.rra.intake import IntakeService, StoredObject
from khepri.rra.packages import FactPackageRecord, FactPackageService
from khepri.rra.persistence import Base as RraBase
from khepri.rra.persistence import (
    SqlFactPackageRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.pipeline import DeliveryRecord
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.rra.sessions import InvitationService, open_commercial_session
from khepri.runtime.workspace import (
    ADMISSION_ADMITTED,
    WorkspacePorts,
    WorkspaceRefused,
    WorkspaceServices,
    WorkspaceStores,
)
from tests.rra003_contract_fixtures import TEST_CONTRACT

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 5, 13, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"

# The same extract `test_rra004_packages.py` admits, and the one it refuses: a file with no
# measure column is inadmissible under `RRA-003`, which is the refusal `FR-114` needs a test for.
GOLDEN_CSV = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)
OTHER_CSV = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-02-02,10.00,1,INV-9,Snacks,Cairo\n"
    b"2026-02-03,20.00,2,INV-10,Snacks,Cairo\n"
)
NO_MEASURE_CSV = b"date,branch\n2026-01-05,Cairo\n2026-01-06,Giza\n"
JOB = "job_w104_1"


def _attestation(first: date, last: date) -> CoverageManifestBody:
    days = [date.fromordinal(day) for day in range(first.toordinal(), last.toordinal() + 1)]
    return CoverageManifestBody(
        timezone="Africa/Cairo",
        attested_by="Test fixture: operator attestation.",
        covered_start=first,
        covered_end=last,
        aggregate_scope="all-stores",
        covered_days=days,
        event_kinds=["sale"],
        statuses=["posted"],
    )


class MemoryObjectStore:
    """`test_rra004_packages.py`'s object store: bytes in a dict, a fixed ciphertext digest."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, *, key: str, content: bytes, media_type: str, sha256_hex: str) -> StoredObject:
        self.objects[key] = content
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="AES-256-GCM",
            envelope_version=1,
            ciphertext_sha256_hex=hashlib.sha256(b"ciphertext:" + content).hexdigest(),
        )

    def get(self, key: str, **_: object) -> bytes:
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class FakeDeliveries:
    """The report boundary, as the service sees it: one delivery record per job, or none."""

    def __init__(self) -> None:
        self.records: dict[str, DeliveryRecord] = {}

    def find_delivery(self, job_id: str) -> DeliveryRecord | None:
        return self.records.get(job_id)


@dataclass(frozen=True)
class FakeStoredArtifact:
    job_id: str
    artifact_kind: str
    session_id: str
    sha256_hex: str


class FakeArtifacts:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str, str], FakeStoredArtifact] = {}

    def find_in_session(
        self, *, session_id: str, job_id: str, artifact_kind: str, now: datetime
    ) -> FakeStoredArtifact | None:
        return self.items.get((session_id, job_id, artifact_kind))


@dataclass
class World:
    factory: sessionmaker
    accounts: AccountService
    organizations: SqlOrganizationStore
    sessions: SqlSessionStore
    uploads: SqlUploadRepository
    objects: MemoryObjectStore
    intake: IntakeService
    profiling: ProfilingService
    packages: FactPackageService
    deliveries: FakeDeliveries
    artifacts: FakeArtifacts
    store: SqlWorkspaceStore
    profiles: SqlSourceProfileStore
    audit: SqlWorkspaceAuditStore
    services: WorkspaceServices


def world() -> World:
    """Both packages' tables on one engine, with foreign keys enforced.

    The workspace tables key onto `rca_isolation_scopes`; the RRA content tables key onto
    `rra_beta_sessions`. One engine carrying both is what the production database is, and it is
    the only shape in which a service that reads one side and writes the other can be exercised.
    """
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    RcaBase.metadata.create_all(engine)
    RraBase.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    sessions = SqlSessionStore(factory)
    uploads = SqlUploadRepository(factory)
    profiles = SqlProfileRepository(factory)
    packages = SqlFactPackageRepository(factory)
    objects = MemoryObjectStore()
    profiling = ProfilingService(
        sessions=sessions, uploads=uploads, objects=objects, profiles=profiles
    )
    package_service = FactPackageService(
        sessions=sessions, uploads=uploads, objects=objects, profiles=profiles, packages=packages
    )
    deliveries = FakeDeliveries()
    artifacts = FakeArtifacts()
    store = SqlWorkspaceStore(factory)
    profile_store = SqlSourceProfileStore(factory)
    audit = SqlWorkspaceAuditStore(factory)
    services = WorkspaceServices(
        isolation=IsolationService(organizations, accounts),
        rra=WorkspacePorts(
            sessions=sessions,
            uploads=uploads,
            profiling=profiling,
            packages=package_service,
            deliveries=deliveries,
            artifacts=artifacts,
        ),
        rca=WorkspaceStores(workspace=store, profiles=profile_store, audit=audit),
    )
    return World(
        factory=factory,
        accounts=AccountService(accounts),
        organizations=organizations,
        sessions=sessions,
        uploads=uploads,
        objects=objects,
        intake=IntakeService(sessions=sessions, uploads=uploads, objects=objects),
        profiling=profiling,
        packages=package_service,
        deliveries=deliveries,
        artifacts=artifacts,
        store=store,
        profiles=profile_store,
        audit=audit,
        services=services,
    )


@dataclass(frozen=True)
class Member:
    account_id: str
    organization_id: str
    owner_id: str


def _member(w: World, email: str = "owner@example.test", name: str = "Acme") -> Member:
    account = w.accounts.create_account(email, CREDENTIAL)
    organization = OrganizationService(w.organizations).create_organization(
        name, account.account_id, now=NOW
    )
    scope = w.organizations.get_scope(organization.organization_id)
    assert scope is not None
    return Member(account.account_id, organization.organization_id, scope.owner_id)


def _session_with_upload(w: World, owner_id: str, content: bytes) -> str:
    session = open_commercial_session(w.sessions, owner_id=owner_id, now=NOW)
    InvitationService(w.sessions).record_consent(session.session_id, consent_version="v1", now=NOW)
    pending = w.intake.begin(session_id=session.session_id, declared_size=None, now=NOW)
    pending.append(content)
    pending.complete(now=NOW)
    return session.session_id


def _admitted_session(
    w: World, owner_id: str, content: bytes = GOLDEN_CSV, *, attest: bool = True
) -> str:
    """The real `RRA-003` admission: an upload profiled under the shared contract."""
    session_id = _session_with_upload(w, owner_id, content)
    days = [
        date.fromisoformat(line.split(b",")[0].decode())
        for line in content.strip().split(b"\n")[1:]
    ]
    w.profiling.profile_session_upload(
        session_id=session_id,
        contract=TEST_CONTRACT,
        now=NOW,
        attestation=_attestation(min(days), max(days)) if attest else None,
    )
    return session_id


def _derived(w: World, session_id: str, *, job_id: str = JOB) -> FactPackageRecord:
    """The real `RRA-004` package, plus the report boundary's products for one job."""
    package, _created = w.packages.build_session_package(session_id=session_id, now=NOW)
    w.deliveries.records[job_id] = DeliveryRecord(
        job_id=job_id,
        session_id=session_id,
        bundle_id="bdl_" + job_id,
        package_version=package.package_version,
        narrative_state="included",
        surfaces=("web", "pdf", "excel"),
    )
    for kind in REQUIRED_ARTIFACT_KINDS:
        w.artifacts.items[(session_id, job_id, kind)] = FakeStoredArtifact(
            job_id=job_id,
            artifact_kind=kind,
            session_id=session_id,
            sha256_hex=hashlib.sha256(f"{job_id}:{kind}".encode()).hexdigest(),
        )
    return package


def _events(w: World, member: Member) -> tuple[WorkspaceAuditEvent, ...]:
    return w.audit.events_for_scope(member.owner_id)


def _field_names(record_type: type) -> set[str]:
    return {f.name for f in fields(record_type)}


# --- FR-125: the audit event ---------------------------------------------------------------------


def test_audit_event_fields_are_exactly_fr125s() -> None:
    """Opaque actor, opaque organization, object identifiers, action, outcome, timestamp -- and
    nothing else. Equality, so a field that could carry content fails until named here."""
    assert _field_names(WorkspaceAuditEvent) == {
        "event_id",
        "owner_id",
        "actor_account_id",
        "action",
        "outcome",
        "object_kind",
        "object_id",
        "occurred_at",
    }


def test_the_audit_vocabularies_are_closed() -> None:
    assert set(AUDIT_ACTIONS) == {
        ACTION_VERSION_CREATED,
        ACTION_RUN_STARTED,
        ACTION_RUN_COMPLETED,
        ACTION_RUN_FAILED,
        ACTION_PROFILE_REMEMBERED,
        ACTION_PROFILE_REUSED,
    }
    assert set(AUDIT_OUTCOMES) == {OUTCOME_COMPLETED, OUTCOME_REFUSED, OUTCOME_ALREADY_RECORDED}
    assert set(AUDIT_OBJECTS) == {OBJECT_VERSION, OBJECT_RUN, OBJECT_PROFILE}


@pytest.mark.parametrize(
    ("action", "kind"),
    [("deleted_everything", OBJECT_VERSION), (ACTION_RUN_STARTED, "session")],
)
def test_an_audit_event_refuses_a_word_outside_its_vocabulary(action: str, kind: str) -> None:
    """Fail closed (Constitution V): an unrecognized action or object kind is refused, not stored.
    A `session` object kind is refused in particular -- `KHEPRI-DEC-015` §7 forbids the session
    identifier from any log, and an event that could name one would be that log."""
    actor = AuditActor(owner_id="own_abc", actor_account_id="acc_abc")
    with pytest.raises(ValueError):
        WorkspaceAuditEvent.completed(actor, action, AuditSubject(kind, "x_1"), now=NOW)


def test_the_audit_table_holds_exactly_the_events_columns() -> None:
    """Read off the emitted schema, not the model's fields (`W1-02`'s reasoning): a column added
    to the table without touching the dataclass would pass a field-set test."""
    columns = {column.name for column in WorkspaceAuditEventRow.__table__.columns}
    assert columns == _field_names(WorkspaceAuditEvent)


def test_the_migration_states_the_same_audit_vocabularies_the_model_does() -> None:
    """The migration keeps literal strings by this repo's convention, so the two can drift."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1]
    source = (
        root / "migrations" / "versions" / "20260905_0022_rca_workspace_audit_events.py"
    ).read_text(encoding="utf-8")

    def literal(constant: str) -> set[str]:
        body = source.split(f"{constant} = ", 1)[1].split("\n", 1)[0]
        return set(re.findall(r"'([a-z_]+)'", body))

    assert literal("_ACTIONS") == set(AUDIT_ACTIONS)
    assert literal("_OUTCOMES") == set(AUDIT_OUTCOMES)
    assert literal("_OBJECTS") == set(AUDIT_OBJECTS)


def test_audit_events_are_read_by_scope_and_cannot_be_rewritten() -> None:
    w = world()
    ours, theirs = _member(w), _member(w, "other@example.test", "Other")
    for member in (ours, theirs):
        actor = AuditActor(owner_id=member.owner_id, actor_account_id=member.account_id)
        w.audit.record(
            WorkspaceAuditEvent.completed(
                actor, ACTION_RUN_STARTED, AuditSubject(OBJECT_RUN, "run_x"), now=NOW
            )
        )

    assert [e.owner_id for e in w.audit.events_for_scope(ours.owner_id)] == [ours.owner_id]
    with w.factory.begin() as database:
        row = database.get(WorkspaceAuditEventRow, _events(w, ours)[0].event_id)
        row.outcome = OUTCOME_REFUSED
        with pytest.raises(ValueError, match="audit event"):
            database.flush()


# --- FR-110: a version records the admission the session holds, and nothing admits twice ---------


def test_creating_a_version_records_the_real_admission() -> None:
    w = world()
    member = _member(w)
    session_id = _admitted_session(w, member.owner_id)
    upload = w.uploads.get_upload_for_session(session_id)
    profile = w.profiling.get_session_profile(session_id=session_id, now=NOW)
    assert upload is not None and profile is not None and profile.admissible

    version = w.services.create_dataset_version(
        account_id=member.account_id,
        organization_id=member.organization_id,
        session_id=session_id,
        now=LATER,
    )

    assert version.owner_id == member.owner_id
    assert version.upload_plaintext_digest == upload.sha256_hex
    assert version.upload_ciphertext_digest == upload.ciphertext_sha256_hex
    assert version.upload_size_bytes == upload.size_bytes == len(GOLDEN_CSV)
    assert version.upload_media_type == upload.media_type
    manifest = stored_manifest(profile)
    assert manifest is not None
    assert version.manifest_digest == document_digest(manifest.as_document())
    assert version.mapping_version == profile.mapping_version
    assert version.admission_outcome == ADMISSION_ADMITTED
    assert version.created_at == LATER
    assert version.sealed_at is None, "sealing is the derivation's event, not the admission's"
    assert w.store.dataset_versions_for_scope(member.owner_id) == (version,)
    (recorded,) = _events(w, member)
    assert (recorded.action, recorded.outcome) == (ACTION_VERSION_CREATED, OUTCOME_COMPLETED)
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_VERSION, version.version_id)
    assert (recorded.owner_id, recorded.actor_account_id) == (
        member.owner_id,
        member.account_id,
    )


def test_a_version_needs_an_admission_the_session_actually_holds() -> None:
    """An upload alone is not an admission. The service asks `ProfilingService` for the profile
    and refuses when there is none -- it never profiles the bytes itself."""
    w = world()
    member = _member(w)
    session_id = _session_with_upload(w, member.owner_id, GOLDEN_CSV)

    with pytest.raises(WorkspaceRefused):
        w.services.create_dataset_version(
            account_id=member.account_id,
            organization_id=member.organization_id,
            session_id=session_id,
            now=LATER,
        )

    assert w.store.dataset_versions_for_scope(member.owner_id) == ()
    (recorded,) = _events(w, member)
    assert (recorded.action, recorded.outcome) == (ACTION_VERSION_CREATED, OUTCOME_REFUSED)
    assert recorded.object_id is None


def test_a_refused_admission_creates_no_version_and_no_run() -> None:
    """`FR-114`'s Run Again refusal, at the service: the new source fails `RRA-003` admission, so
    reuse is refused, nothing is copied from the prior run, and the history gains no run."""
    w = world()
    member = _member(w)
    prior = w.services.create_dataset_version(
        account_id=member.account_id,
        organization_id=member.organization_id,
        session_id=_admitted_session(w, member.owner_id),
        now=NOW,
    )
    w.services.start_analysis_run(
        account_id=member.account_id,
        organization_id=member.organization_id,
        version_id=prior.version_id,
        now=NOW,
    )
    runs_before = w.store.analysis_runs_for_scope(member.owner_id)
    again = _admitted_session(w, member.owner_id, NO_MEASURE_CSV, attest=False)

    with pytest.raises(WorkspaceRefused):
        w.services.create_dataset_version(
            account_id=member.account_id,
            organization_id=member.organization_id,
            session_id=again,
            now=LATER,
        )

    assert w.store.dataset_versions_for_scope(member.owner_id) == (prior,)
    assert w.store.analysis_runs_for_scope(member.owner_id) == runs_before
    assert _events(w, member)[-1].outcome == OUTCOME_REFUSED


def test_an_admission_without_a_coverage_attestation_creates_no_version() -> None:
    """`W1-01` made the manifest digest a required field of a version, and `KHEPRI-DEC-033` §2
    keeps the manifest with the version it describes. A profile with no attestation has none to
    keep, so the version is refused rather than written with a digest of nothing."""
    w = world()
    member = _member(w)
    session_id = _admitted_session(w, member.owner_id, attest=False)

    with pytest.raises(WorkspaceRefused):
        w.services.create_dataset_version(
            account_id=member.account_id,
            organization_id=member.organization_id,
            session_id=session_id,
            now=LATER,
        )

    assert w.store.dataset_versions_for_scope(member.owner_id) == ()
    assert len(_events(w, member)) == 1


def test_creating_a_version_twice_for_one_session_returns_the_first() -> None:
    """A retry is not a second version. The upload's ciphertext digest is unique per stored copy,
    so it identifies the session's upload without the workspace holding a session identifier."""
    w = world()
    member = _member(w)
    session_id = _admitted_session(w, member.owner_id)
    kwargs = dict(
        account_id=member.account_id, organization_id=member.organization_id, session_id=session_id
    )

    first = w.services.create_dataset_version(**kwargs, now=NOW)
    second = w.services.create_dataset_version(**kwargs, now=LATER)

    assert second == first
    assert w.store.dataset_versions_for_scope(member.owner_id) == (first,)
    outcomes = [e.outcome for e in _events(w, member)]
    assert outcomes == [OUTCOME_COMPLETED, OUTCOME_ALREADY_RECORDED]


def test_a_version_cannot_be_created_from_another_scopes_session() -> None:
    """The session identifier is an object identifier, never authority (`FR-023`): a member of
    one organization naming another organization's session is refused, indistinguishably from
    naming no session at all."""
    w = world()
    ours, theirs = _member(w), _member(w, "other@example.test", "Other")
    their_session = _admitted_session(w, theirs.owner_id)

    with pytest.raises(WorkspaceRefused):
        w.services.create_dataset_version(
            account_id=ours.account_id,
            organization_id=ours.organization_id,
            session_id=their_session,
            now=LATER,
        )

    assert w.store.dataset_versions_for_scope(ours.owner_id) == ()
    assert w.store.dataset_versions_for_scope(theirs.owner_id) == ()
    assert len(_events(w, ours)) == 1 and _events(w, theirs) == ()


def test_a_non_member_is_refused_before_any_event_is_written() -> None:
    """Authorization is `resolve_scope`'s, one door (`R6-01` §5), and it comes first: an actor
    with no standing in the organization gets the uniform refusal and the workspace records
    nothing about the attempt, because there is no scope to record it in."""
    w = world()
    member = _member(w)
    outsider = _member(w, "other@example.test", "Other")
    session_id = _admitted_session(w, member.owner_id)

    with pytest.raises(ScopeAccessDenied):
        w.services.create_dataset_version(
            account_id=outsider.account_id,
            organization_id=member.organization_id,
            session_id=session_id,
            now=LATER,
        )

    assert _events(w, member) == () and _events(w, outsider) == ()


def test_the_service_reaches_admission_only_through_the_profiling_service() -> None:
    """The plan's named risk, asserted on the source: no admission internal is imported. The one
    way to a profile is `ProfilingService`, which is the `RRA-003` entry point."""
    import inspect as py_inspect

    from khepri.runtime import workspace

    source = py_inspect.getsource(workspace)
    for forbidden in (
        "khepri.rra.admission",
        "khepri.rra.profiling",
        "khepri.rra.mapping",
        "khepri.rra.facts",
        "build_document",
        "build_profile",
        "build_mapping",
        "build_fact_package",
    ):
        assert forbidden not in source, forbidden
    assert "ProfilingService" in source
    assert "FactPackageService" in source


# --- FR-111: a run is produced by the pipeline, and bound to its artifacts by digest -------------


def _version_and_run(w: World, member: Member) -> tuple[str, str, str]:
    session_id = _admitted_session(w, member.owner_id)
    version = w.services.create_dataset_version(
        account_id=member.account_id,
        organization_id=member.organization_id,
        session_id=session_id,
        now=NOW,
    )
    run = w.services.start_analysis_run(
        account_id=member.account_id,
        organization_id=member.organization_id,
        version_id=version.version_id,
        now=NOW,
    )
    return session_id, version.version_id, run.run_id


def test_starting_a_run_needs_a_live_version_in_scope() -> None:
    w = world()
    member = _member(w)
    session_id, version_id, run_id = _version_and_run(w, member)
    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED and run.version_id == version_id
    assert [e.action for e in _events(w, member)] == [ACTION_VERSION_CREATED, ACTION_RUN_STARTED]

    w.store.tombstone_dataset_version(version_id, now=LATER)
    with pytest.raises(WorkspaceRefused):
        w.services.start_analysis_run(
            account_id=member.account_id,
            organization_id=member.organization_id,
            version_id=version_id,
            now=LATER,
        )
    assert _events(w, member)[-1].outcome == OUTCOME_REFUSED
    assert len(_events(w, member)) == 3


def test_completing_a_run_binds_every_required_artifact_and_seals_the_version() -> None:
    """The run's provenance is the real package's -- digest and the two governed versions -- and
    one binding per required artifact kind carries that artifact's own digest. The first
    completion over a version seals it: `KHEPRI-DEC-033` starts the raw upload's purge clock at
    "facts derived and reconciled", which is this event."""
    w = world()
    member = _member(w)
    session_id, version_id, run_id = _version_and_run(w, member)
    package = _derived(w, session_id)

    completed = w.services.complete_analysis_run(
        account_id=member.account_id,
        organization_id=member.organization_id,
        run_id=run_id,
        session_id=session_id,
        job_id=JOB,
        now=LATER,
    )

    assert completed.state == RUN_COMPLETED
    assert completed.package_digest == package.package_digest
    assert completed.package_version == package.package_version
    assert completed.formula_version == package.formula_version
    assert completed.completed_at == LATER
    assert w.store.get_analysis_run(run_id) == completed
    bindings = w.store.artifact_bindings_for_run(run_id)
    assert {(b.surface, b.artifact_digest) for b in bindings} == {
        (kind, w.artifacts.items[(session_id, JOB, kind)].sha256_hex)
        for kind in REQUIRED_ARTIFACT_KINDS
    }
    assert {b.published_at for b in bindings} == {LATER}
    version = w.store.get_dataset_version(version_id)
    assert version is not None and version.sealed_at == LATER
    recorded = _events(w, member)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_RUN_COMPLETED, OUTCOME_COMPLETED)
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_RUN, run_id)
    assert len(_events(w, member)) == 3


@pytest.mark.parametrize("missing", REQUIRED_ARTIFACT_KINDS)
def test_a_run_missing_any_required_artifact_is_not_presented_as_completed(missing: str) -> None:
    """`FR-111`: fewer than every required surface is incomplete. Per kind, because a check that
    loops over some of them passes for the ones it names. The run stays `started`, gains no
    binding, and the version stays unsealed."""
    w = world()
    member = _member(w)
    session_id, version_id, run_id = _version_and_run(w, member)
    _derived(w, session_id)
    del w.artifacts.items[(session_id, JOB, missing)]

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            account_id=member.account_id,
            organization_id=member.organization_id,
            run_id=run_id,
            session_id=session_id,
            job_id=JOB,
            now=LATER,
        )

    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED and run.package_digest is None
    assert w.store.artifact_bindings_for_run(run_id) == ()
    version = w.store.get_dataset_version(version_id)
    assert version is not None and version.sealed_at is None
    assert _events(w, member)[-1].outcome == OUTCOME_REFUSED


def test_a_run_cannot_be_completed_without_a_delivery_for_its_job() -> None:
    w = world()
    member = _member(w)
    session_id, _version_id, run_id = _version_and_run(w, member)
    _derived(w, session_id)
    del w.deliveries.records[JOB]

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            account_id=member.account_id,
            organization_id=member.organization_id,
            run_id=run_id,
            session_id=session_id,
            job_id=JOB,
            now=LATER,
        )
    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED


def test_a_package_derived_from_another_source_cannot_complete_a_run() -> None:
    """Provenance is checked, not assumed: the package's source digest and mapping version must
    be the run's version's. A run over version A completed from a session that admitted file B
    would bind A's history to B's figures."""
    w = world()
    member = _member(w)
    _session_a, _version_a, run_id = _version_and_run(w, member)
    session_b = _admitted_session(w, member.owner_id, OTHER_CSV)
    _derived(w, session_b, job_id="job_b")

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            account_id=member.account_id,
            organization_id=member.organization_id,
            run_id=run_id,
            session_id=session_b,
            job_id="job_b",
            now=LATER,
        )

    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED
    assert w.store.artifact_bindings_for_run(run_id) == ()


def test_a_delivery_from_another_session_cannot_complete_a_run() -> None:
    """The delivery names its session; a job identifier alone is not enough. A delivery recorded
    under another session -- even another session of the same scope -- is refused."""
    w = world()
    member = _member(w)
    session_id, _version_id, run_id = _version_and_run(w, member)
    _derived(w, session_id)
    other = _admitted_session(w, member.owner_id, OTHER_CSV)
    w.deliveries.records[JOB] = DeliveryRecord(
        job_id=JOB,
        session_id=other,
        bundle_id="bdl_other",
        package_version=w.deliveries.records[JOB].package_version,
        narrative_state="included",
        surfaces=("web", "pdf", "excel"),
    )

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(
            account_id=member.account_id,
            organization_id=member.organization_id,
            run_id=run_id,
            session_id=session_id,
            job_id=JOB,
            now=LATER,
        )
    run = w.store.get_analysis_run(run_id)
    assert run is not None and run.state == RUN_STARTED


def test_a_second_completion_is_refused_and_binds_nothing_twice() -> None:
    w = world()
    member = _member(w)
    session_id, _version_id, run_id = _version_and_run(w, member)
    _derived(w, session_id)
    kwargs = dict(
        account_id=member.account_id,
        organization_id=member.organization_id,
        run_id=run_id,
        session_id=session_id,
        job_id=JOB,
    )
    w.services.complete_analysis_run(**kwargs, now=LATER)

    with pytest.raises(WorkspaceRefused):
        w.services.complete_analysis_run(**kwargs, now=LATER)

    assert len(w.store.artifact_bindings_for_run(run_id)) == len(REQUIRED_ARTIFACT_KINDS)
    assert [e.outcome for e in _events(w, member)[-2:]] == [OUTCOME_COMPLETED, OUTCOME_REFUSED]


def test_failing_a_run_records_the_real_state_and_no_provenance() -> None:
    """A pipeline that did not deliver ends the run as `failed`: a real runtime state the history
    spine can show, never a run that looks unfinished forever or a completion with nothing behind
    it."""
    w = world()
    member = _member(w)
    _session_id, version_id, run_id = _version_and_run(w, member)

    failed = w.services.fail_analysis_run(
        account_id=member.account_id,
        organization_id=member.organization_id,
        run_id=run_id,
        now=LATER,
    )

    assert failed.state == RUN_FAILED
    assert failed.package_digest is None and failed.completed_at == LATER
    assert w.store.get_analysis_run(run_id) == failed
    version = w.store.get_dataset_version(version_id)
    assert version is not None and version.sealed_at is None, "nothing was derived"
    recorded = _events(w, member)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_RUN_FAILED, OUTCOME_COMPLETED)


# --- FR-114 / FR-115: the source profile is remembered as metadata and offered as a proposal ------


def _remembered(w: World, member: Member) -> tuple[str, SourceProfile]:
    session_id = _admitted_session(w, member.owner_id)
    version = w.services.create_dataset_version(
        account_id=member.account_id,
        organization_id=member.organization_id,
        session_id=session_id,
        now=NOW,
    )
    profile = w.services.remember_source_profile(
        account_id=member.account_id,
        organization_id=member.organization_id,
        version_id=version.version_id,
        session_id=session_id,
        now=LATER,
    )
    return session_id, profile


def test_remembering_a_source_profile_stores_descriptive_metadata_only() -> None:
    """The column labels are the profile's *safe* labels and the proposal is the admitted
    mapping's (semantic, safe label) pairs -- what pre-fills a form. No outcome, no check result:
    `SourceProfile`'s field set is `W1-01`'s equality, and this fills only those fields."""
    w = world()
    member = _member(w)
    session_id, profile = _remembered(w, member)
    admitted = w.profiling.get_session_profile(session_id=session_id, now=NOW)
    assert admitted is not None
    safe_labels = tuple(column["safe_label"] for column in admitted.document["profile"]["columns"])
    mapped = tuple(
        (mapping["semantic"], mapping["candidates"][0]["safe_label"])
        for mapping in admitted.document["mapping"]["mappings"]
        if mapping["state"] == "mapped"
    )

    assert profile.owner_id == member.owner_id
    assert profile.column_labels == safe_labels
    assert profile.proposed_mapping == mapped
    assert mapped, "the golden extract maps at least one semantic"
    assert profile.created_at == LATER
    assert w.profiles.get(profile.profile_id, member.owner_id) == profile
    assert w.profiles.for_scope(member.owner_id) == (profile,)
    recorded = _events(w, member)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_PROFILE_REMEMBERED, OUTCOME_COMPLETED)
    assert (recorded.object_kind, recorded.object_id) == (OBJECT_PROFILE, profile.profile_id)


def test_a_profile_must_describe_the_version_it_is_remembered_for() -> None:
    """A session that admitted a different file cannot be remembered as this version's profile:
    the source digest and mapping version are compared, so the labels offered for reuse are the
    ones the version was actually admitted under."""
    w = world()
    member = _member(w)
    version = w.services.create_dataset_version(
        account_id=member.account_id,
        organization_id=member.organization_id,
        session_id=_admitted_session(w, member.owner_id),
        now=NOW,
    )
    other = _admitted_session(w, member.owner_id, OTHER_CSV)

    with pytest.raises(WorkspaceRefused):
        w.services.remember_source_profile(
            account_id=member.account_id,
            organization_id=member.organization_id,
            version_id=version.version_id,
            session_id=other,
            now=LATER,
        )

    assert w.profiles.for_scope(member.owner_id) == ()
    assert _events(w, member)[-1].outcome == OUTCOME_REFUSED


def test_proposing_reuse_returns_the_profile_and_emits_one_event() -> None:
    """`FR-125` names profile reuse as an audited action even though it writes nothing: the
    proposal is what the customer sees before confirming (`FR-114`), and that showing is the
    action."""
    w = world()
    member = _member(w)
    _session_id, profile = _remembered(w, member)
    before = len(_events(w, member))

    proposed = w.services.propose_reuse(
        account_id=member.account_id,
        organization_id=member.organization_id,
        profile_id=profile.profile_id,
        now=LATER,
    )

    assert proposed == profile
    recorded = _events(w, member)[-1]
    assert (recorded.action, recorded.outcome) == (ACTION_PROFILE_REUSED, OUTCOME_COMPLETED)
    assert len(_events(w, member)) == before + 1


def test_a_profile_of_a_deleted_version_is_not_offered() -> None:
    """`KHEPRI-DEC-033` §1: derived content never outlives its input's right to exist. The
    profile describes a version the customer withdrew, so it is not proposed."""
    w = world()
    member = _member(w)
    _session_id, profile = _remembered(w, member)
    w.store.tombstone_dataset_version(profile.source_version_id, now=LATER)

    assert w.profiles.get(profile.profile_id, member.owner_id) is None
    assert w.profiles.for_scope(member.owner_id) == ()
    with pytest.raises(WorkspaceRefused):
        w.services.propose_reuse(
            account_id=member.account_id,
            organization_id=member.organization_id,
            profile_id=profile.profile_id,
            now=LATER,
        )
    assert _events(w, member)[-1].outcome == OUTCOME_REFUSED


def test_a_profile_is_read_by_scope() -> None:
    w = world()
    ours, theirs = _member(w), _member(w, "other@example.test", "Other")
    _session_id, profile = _remembered(w, ours)

    assert w.profiles.get(profile.profile_id, theirs.owner_id) is None
    assert w.profiles.for_scope(theirs.owner_id) == ()
    with pytest.raises(WorkspaceRefused):
        w.services.propose_reuse(
            account_id=theirs.account_id,
            organization_id=theirs.organization_id,
            profile_id=profile.profile_id,
            now=LATER,
        )


# --- The schema and the audit table -------------------------------------------------------------


def test_the_audit_table_is_a_workspace_table_keyed_by_scope() -> None:
    """Every workspace table is keyed by the opaque scope (`FR-109`). The audit table carries no
    foreign key onto it, for the reason `rca_membership_events` carries none: the event must
    outlive the organization it describes until its own twelve-month horizon, and a `RESTRICT`
    key would enforce the opposite ordering."""
    table = WorkspaceAuditEventRow.__table__
    assert table.name == "rca_workspace_audit_events"
    assert not table.foreign_keys
    indexed = {tuple(column.name for column in index.columns) for index in table.indexes}
    assert ("owner_id",) in indexed and ("occurred_at",) in indexed


def test_no_workspace_column_can_hold_a_session_identifier() -> None:
    """`KHEPRI-DEC-015` §7: the session identifier never reaches a log, and `RCA-005`'s workspace
    holds no `RRA` identifier at all -- the link between a version and its upload is the digest,
    between a run and its package the package digest."""
    w = world()
    inspector = inspect(w.factory().get_bind())
    for table in inspector.get_table_names():
        if not table.startswith("rca_workspace_"):
            continue
        names = {column["name"] for column in inspector.get_columns(table)}
        assert not {name for name in names if "session" in name or "job" in name}, table
