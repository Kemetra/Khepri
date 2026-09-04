"""The world the `W1-04` tests run in: both packages' tables on one engine, the real `RRA-003`
admission and `RRA-004` derivation, and fakes only at the report boundary.

Shared by `test_w104_audit_events.py` and `test_w104_workspace_services.py`, which CodeScene split
from one module for length and cohesion. The fixtures live here so the two files hold assertions
and nothing else.

**Why the fakes stop where they do.** The `G3-04` plan's one named risk for this slice is a second
admission path, so every version these helpers create comes from a session whose upload the real
`ProfilingService` admitted over real bytes, and every run is completed from a package the real
`FactPackageService` derived. The delivery record and the stored artifacts are faked because the
pipeline that produces them needs Chromium and a worker, and `RRA-006`'s own tests prove it; the
service *reads* those products and makes none.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.audit import WorkspaceAuditEvent
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rca.workspace.profile_store import SqlSourceProfileStore
from khepri.rra.coverage_request import CoverageManifestBody
from khepri.rra.datasets import ProfilingService
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
from khepri.runtime.workspace import Caller, RecordStores, WorkspaceActions, WorkspacePorts
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


def attestation(first: date, last: date) -> CoverageManifestBody:
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
    """`test_rra004_packages.py`'s object store: bytes in a dict, a content-derived ciphertext
    digest -- which is what lets one test see two scopes share a digest."""

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
    store: SqlWorkspaceRecordStore
    profiles: SqlSourceProfileStore
    audit: SqlWorkspaceAuditStore
    services: WorkspaceActions


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
    store = SqlWorkspaceRecordStore(factory)
    profile_store = SqlSourceProfileStore(factory)
    audit = SqlWorkspaceAuditStore(factory)
    services = WorkspaceActions(
        isolation=IsolationService(organizations, accounts),
        rra=WorkspacePorts(
            sessions=sessions,
            uploads=uploads,
            profiling=profiling,
            packages=package_service,
            deliveries=deliveries,
            artifacts=artifacts,
        ),
        rca=RecordStores(workspace=store, profiles=profile_store, audit=audit, factory=factory),
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

    @property
    def caller(self) -> Caller:
        return Caller(account_id=self.account_id, organization_id=self.organization_id)


def member(w: World, email: str = "owner@example.test", name: str = "Acme") -> Member:
    """One account owning one organization, through the real services, with its opaque scope."""
    account = w.accounts.create_account(email, CREDENTIAL)
    organization = OrganizationService(w.organizations).create_organization(
        name, account.account_id, now=NOW
    )
    scope = w.organizations.get_scope(organization.organization_id)
    assert scope is not None
    return Member(account.account_id, organization.organization_id, scope.owner_id)


def session_with_upload(w: World, owner_id: str, content: bytes) -> str:
    session = open_commercial_session(w.sessions, owner_id=owner_id, now=NOW)
    InvitationService(w.sessions).record_consent(session.session_id, consent_version="v1", now=NOW)
    pending = w.intake.begin(session_id=session.session_id, declared_size=None, now=NOW)
    pending.append(content)
    pending.complete(now=NOW)
    return session.session_id


def admitted_session(
    w: World, owner_id: str, content: bytes = GOLDEN_CSV, *, attest: bool = True
) -> str:
    """The real `RRA-003` admission: an upload profiled under the shared contract."""
    session_id = session_with_upload(w, owner_id, content)
    days = [
        date.fromisoformat(line.split(b",")[0].decode())
        for line in content.strip().split(b"\n")[1:]
    ]
    w.profiling.profile_session_upload(
        session_id=session_id,
        contract=TEST_CONTRACT,
        now=NOW,
        attestation=attestation(min(days), max(days)) if attest else None,
    )
    return session_id


def derived(w: World, session_id: str, *, job_id: str = JOB) -> FactPackageRecord:
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


def events(w: World, who: Member) -> tuple[WorkspaceAuditEvent, ...]:
    return w.audit.events_for_scope(who.owner_id)
