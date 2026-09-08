"""Production service graph shared by the approved web and worker roles."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.identity import IdentityProvider
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_retention import InvitationRetentionSweeper
from khepri.rca.invitation_service import InvitationService as RcaInvitationService
from khepri.rca.invitations import Invitation, InvitationOffer
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import AccountRetentionSweeper, LifecycleService, MembershipEventSweeper
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.recovery_security import RecoverySecurityEventSweeper, RecoverySecurityService
from khepri.rca.recovery_security_persistence import SqlRecoverySecurityEventStore
from khepri.rca.session_persistence import SqlSessionStore as SqlCommercialSessionStore
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.rca.session_retention import SessionRetentionSweeper
from khepri.rca.session_service import SessionService as RcaSessionService
from khepri.rca.switching import OrganizationSwitcher
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from khepri.rca.workspace.comparisons import ComparisonActions, ComparisonStores
from khepri.rca.workspace.persistence import (
    SqlRunProvenanceStore,
    SqlRunReportStore,
    SqlWorkspaceRecordStore,
)
from khepri.rca.workspace.profile_store import SqlSourceProfileStore
from khepri.rca.workspace.revocation import SqlRevocationLedger
from khepri.rca.workspace.scopes import SqlIsolationScopes
from khepri.rra.api import create_app
from khepri.rra.artifact_persistence import SqlArtifactRepository
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.deterministic_narrative import DeterministicNarrator
from khepri.rra.evidence_retention import DeletionEvidenceSweeper
from khepri.rra.intake import IntakeService
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.journey.routes import JourneyServices
from khepri.rra.journey.state import SqlJourneyReader
from khepri.rra.package_source import SessionFactPackageSource
from khepri.rra.packages import FactPackageService
from khepri.rra.persistence import (
    SqlDeletionRepository,
    SqlFactPackageRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.pipeline import ReportPipeline, ReportPipelinePorts
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PagePrinter, PdfReportRenderer, PrintablePage
from khepri.rra.report_artifacts import MaterializedRenderer
from khepri.rra.report_publication import QueuedReportRequestService
from khepri.rra.report_services import (
    DeliveredBundleAdapter,
    JobReader,
    ReportArtifactAdapter,
    ReportRequestAdapter,
)
from khepri.rra.reports import ReportServices
from khepri.rra.sessions import InvitationService
from khepri.rra.storage import S3EncryptedObjectStore
from khepri.runtime.bridge import CommercialBridge
from khepri.runtime.clerk_identity import ClerkIdentityProvider
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from khepri.runtime.comparison_assembly import ComparisonAssemblyPorts, CrossVersionAssembly
from khepri.runtime.config import RuntimeSettings
from khepri.runtime.external_auth_api import (
    KHEPRI_SESSION_LIFETIME,
    ExternalAuthenticationServices,
    add_external_authentication_routes,
)
from khepri.runtime.job_sessions import SqlJobSessions
from khepri.runtime.landing_api import add_landing_routes
from khepri.runtime.legal_api import add_legal_routes
from khepri.runtime.pipeline_recording import (
    AdmissionPorts,
    PipelineRecorder,
    RecorderReads,
    RecordingProfilingService,
    RecordingReportRequests,
)
from khepri.runtime.retention_sweep import (
    RetentionPasses,
    RetentionSweeper,
    build_retention_sweeper,
)
from khepri.runtime.shell_api import ShellServices, add_shell_routes
from khepri.runtime.shell_provenance import ProvenanceReader, ProvenanceSources
from khepri.runtime.workspace import RecordStores, WorkspaceActions, WorkspacePorts
from khepri.runtime.workspace_deletion import DeletionSources, WorkspaceDeletion
from khepri.runtime.workspace_recording import WorkspaceRecording

# The web role publishes but never claims, so this identity appears in no lease. It
# is required because `ClaimPolicy` refuses an anonymous worker, and a name that is
# obviously not a worker is better here than one that could be mistaken for one.
PUBLISHER_ID = "web-publisher"
PUBLISHER_LEASE_FOR = timedelta(seconds=300)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RuntimeClients:
    s3: Any


@dataclass(frozen=True, slots=True)
class SessionServices:
    invitations: InvitationService
    intake: IntakeService
    profiling: ProfilingService
    packages: FactPackageService
    deletion: DeletionService


@dataclass(frozen=True, slots=True)
class ReportStores:
    jobs: SqlReportJobRepository
    deliveries: SqlDeliveryStore
    artifacts: SqlArtifactRepository
    publisher: ReportArtifactPublisher


@dataclass(frozen=True, slots=True)
class RuntimeStack:
    settings: RuntimeSettings
    clients: RuntimeClients
    services: SessionServices
    reports: ReportStores
    factory: sessionmaker[Session]
    objects: S3EncryptedObjectStore
    clock: Callable[[], datetime]
    identity_provider: IdentityProvider | None


def build_clients(settings: RuntimeSettings) -> RuntimeClients:
    retries = Config(retries={"max_attempts": 3, "mode": "standard"})
    # One client for every S3-compatible target. The endpoint and region come from
    # configuration, so AWS, Spaces, Hetzner, and MinIO differ here only in the
    # strings they supply -- there is no provider branch and must never be one.
    # Credentials are left to the environment rather than read into the process.
    return RuntimeClients(
        s3=boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            region_name=settings.storage_region,
            config=retries,
        ),
    )


def build_stack(
    settings: RuntimeSettings,
    *,
    clients: RuntimeClients | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> RuntimeStack:
    resolved_clients = clients or build_clients(settings)
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    factory = sessionmaker(bind=engine, future=True)
    objects = S3EncryptedObjectStore(
        client=resolved_clients.s3,
        bucket=settings.bucket,
        master_key=settings.master_key,
    )
    sessions = SqlSessionStore(factory)
    uploads = SqlUploadRepository(factory)
    profiles = SqlProfileRepository(factory)
    packages = SqlFactPackageRepository(factory)
    deletions = SqlDeletionRepository(factory)
    report_deliveries = SqlDeliveryStore(factory, now=clock)
    artifact_repository = SqlArtifactRepository(factory)
    artifact_publisher = ReportArtifactPublisher(
        repository=artifact_repository,
        deliveries=report_deliveries,
        objects=objects,
        now=clock,
    )
    return RuntimeStack(
        settings=settings,
        clients=resolved_clients,
        services=SessionServices(
            invitations=InvitationService(sessions),
            intake=IntakeService(sessions=sessions, uploads=uploads, objects=objects),
            profiling=ProfilingService(
                sessions=sessions,
                uploads=uploads,
                objects=objects,
                profiles=profiles,
            ),
            packages=FactPackageService(
                sessions=sessions,
                uploads=uploads,
                objects=objects,
                profiles=profiles,
                packages=packages,
            ),
            deletion=DeletionService(
                sessions=sessions,
                deletions=deletions,
                objects=objects,
            ),
        ),
        reports=ReportStores(
            jobs=SqlReportJobRepository(factory),
            deliveries=report_deliveries,
            artifacts=artifact_repository,
            publisher=artifact_publisher,
        ),
        factory=factory,
        objects=objects,
        clock=clock,
        identity_provider=(
            None if settings.clerk is None else ClerkIdentityProvider(settings.clerk)
        ),
    )


def build_report_services(stack: RuntimeStack) -> ReportServices:
    reader = JobReader(stack.factory)
    requests = ReportRequestAdapter(
        jobs=stack.reports.jobs,
        reader=reader,
        packages=stack.services.packages,
        deliveries=stack.reports.deliveries,
    )
    return ReportServices(
        jobs=QueuedReportRequestService(
            requests=requests,
            publisher=ClaimingReportQueue(
                jobs=stack.reports.jobs,
                factory=stack.factory,
                policy=ClaimPolicy(
                    worker_id=PUBLISHER_ID,
                    lease_for=PUBLISHER_LEASE_FOR,
                ),
            ),
        ),
        bundles=DeliveredBundleAdapter(
            deliveries=stack.reports.deliveries,
            reader=reader,
        ),
        artifacts=ReportArtifactAdapter(stack.reports.publisher),
        packages=stack.services.packages,
    )


def build_commercial_services(stack: RuntimeStack) -> CommercialServices:
    """Build the RCA half of the graph and pair it with the bridge.

    This is the first place `khepri.rca` is constructed in the production composition root.
    `KHEPRI-DEC-021` §3 admits the import here deliberately: a composition root exists to know about
    both sides, and what the boundary forbids is a bridge *inside* either package.

    **Two session stores are in play and they are not interchangeable.** `SqlRcaSessionStore` holds
    authentication sessions and belongs to `ActorResolver`; `SqlSessionStore` (RRA, imported
    unaliased at the top of this module) holds analysis sessions and belongs to the bridge. The
    alias exists so a reader can tell which is which rather than relying on import order.

    The construction mirrors `tests/test_r703_live_authorization_on_resume.py`, which is the shape
    `R7-03` proved the two live gates against.
    """
    accounts = SqlAccountStore(stack.factory)
    organizations = SqlOrganizationStore(stack.factory)
    actors = ActorResolver(
        RcaSessionService(
            SqlRcaSessionStore(stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
        ),
        LifecycleService(accounts, organizations),
    )
    return CommercialServices(
        resolver=AuthorizationResolver(actors, organizations),
        bridge=CommercialBridge(
            isolation=IsolationService(organizations, accounts),
            store=SqlSessionStore(stack.factory),
        ),
        consent=InvitationService(SqlSessionStore(stack.factory)),
    )


def _workspace_ports(stack: RuntimeStack) -> WorkspacePorts:
    """The `RRA` side of the workspace, read from the stack as built -- the same `ProfilingService`
    and `FactPackageService` the beta routes use, and the same delivery and artifact repositories
    the report publisher writes -- so the workspace records what those services decided and never
    a second reading of it."""
    return WorkspacePorts(
        sessions=SqlSessionStore(stack.factory),
        uploads=SqlUploadRepository(stack.factory),
        profiling=stack.services.profiling,
        packages=stack.services.packages,
        deliveries=stack.reports.deliveries,
        artifacts=stack.reports.artifacts,
    )


def _record_stores(stack: RuntimeStack) -> RecordStores:
    """The `RCA` side of the workspace, built here as `build_commercial_services` builds its
    half."""
    return RecordStores(
        workspace=SqlWorkspaceRecordStore(stack.factory),
        profiles=SqlSourceProfileStore(stack.factory),
        audit=SqlWorkspaceAuditStore(stack.factory),
        factory=stack.factory,
        provenance=SqlRunProvenanceStore(stack.factory),
    )


class _OnDemandPrinter:
    """A `PagePrinter` that launches Chromium for one comparison request."""

    def print_to_pdf(self, page: PrintablePage) -> bytes:
        from khepri.rra.rendering.chromium import launch_chromium

        with launch_chromium() as printer:
            return printer.print_to_pdf(page)


def _own_render_directory(path: Path) -> None:
    """Create the comparison render parent as this process's alone (`CWE-377`, review on `#409`).

    The default sits in a shared temporary namespace, as the worker's workbook directory does,
    so a path another local user pre-created -- or a symlink placed there -- would redirect or
    fail every render. The directory is created private to the process user, a symlink is
    refused, and on POSIX a directory owned by someone else is refused rather than used.
    """
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"comparison render directory must not be a symlink: {path}")
    getuid = getattr(os, "getuid", None)
    if getuid is not None and path.stat().st_uid != getuid():
        raise RuntimeError(f"comparison render directory is owned by another user: {path}")


def build_comparison_actions(stack: RuntimeStack, *, workbooks: Path) -> ComparisonActions:
    """The comparison door (`C1-06`): a pair, resolved through `IsolationService`."""
    factory = stack.factory
    _own_render_directory(workbooks)
    return ComparisonActions(
        isolation=IsolationService(SqlOrganizationStore(factory), SqlAccountStore(factory)),
        stores=ComparisonStores(
            workspace=SqlWorkspaceRecordStore(factory),
            audit=SqlWorkspaceAuditStore(factory),
            factory=factory,
        ),
        assembly=CrossVersionAssembly(
            ports=ComparisonAssemblyPorts(
                packages=stack.services.packages,
                profiling=stack.services.profiling,
                jobs=SqlJobSessions(factory),
                reports=SqlRunReportStore(factory),
                provenance=SqlRunProvenanceStore(factory),
                workspace=SqlWorkspaceRecordStore(factory),
            ),
            html=HtmlReportRenderer(),
            pdf=PdfReportRenderer(printer=_OnDemandPrinter()),
            excel=ExcelSurfaceRenderer(directory=workbooks),
        ),
    )


def build_workspace_actions(stack: RuntimeStack) -> WorkspaceActions:
    """The workspace's customer door (`W1-04`): a `Caller`, resolved through `IsolationService`.

    No route mounts these yet. The deployed flow records the workspace through the pipeline door
    instead -- `build_pipeline_recorder` -- and the customer-initiated actions (`FR-114` Run Again
    and reuse) take this door when their surfaces ship.
    """
    accounts = SqlAccountStore(stack.factory)
    organizations = SqlOrganizationStore(stack.factory)
    return WorkspaceActions(
        isolation=IsolationService(organizations, accounts),
        rra=_workspace_ports(stack),
        rca=_record_stores(stack),
    )


def build_pipeline_recorder(stack: RuntimeStack) -> PipelineRecorder:
    """The workspace's pipeline door (`W1-04b`): the deployed admission and report stages record
    what they produced, in the scope the analysis session already carries. Over the same ports and
    stores as the customer door, so there is one recording of each fact."""
    return PipelineRecorder(
        recording=WorkspaceRecording(rra=_workspace_ports(stack), rca=_record_stores(stack)),
        reads=RecorderReads(
            sessions=SqlSessionStore(stack.factory),
            scopes=SqlIsolationScopes(stack.factory),
            reports=SqlRunReportStore(stack.factory),
            jobs=JobReader(stack.factory),
        ),
    )


@dataclass(frozen=True, slots=True)
class ShellInvitations:
    """`shell_api.InvitationGateway`, composed from the two objects that own its verbs.

    **Neither existing object satisfies the gateway alone, and neither should be made to.** The
    listing is the store's -- `invitations_for_organization` was written for this very screen and
    is expiry-aware, destroying the verifier of any stale row it touches (`test_r805_team_surface`
    records that this slice consumes it rather than adding a second listing). The writes are
    `InvitationService`'s, and they are not thin passes to the store: `issue` canonicalizes the
    target address **at rest** (`R4-01` §4) and mints through `Invitation.create`, and `revoke`
    turns the store's `False` into the one uniform refusal `FR-025` requires for all four causes.
    Reaching past the service for either write would drop a governed rule; teaching the service the
    read would put a second listing beside the one already written for this screen.

    So the composition is here, exactly as `R7-01` §3 puts the deletion composition here -- and for
    the same reason `#382` found: a field wired to an object that cannot answer the surface's call
    is absent from the deployed image while every route test passes over a hand-wired
    `ShellServices`. `wiring.py:497` previously passed the service alone, so the Team surface
    raised `AttributeError` on `invitations_for_organization` in the built wheel.
    """

    store: SqlInvitationStore
    service: RcaInvitationService

    def invitations_for_organization(
        self, organization_id: str, *, now: datetime
    ) -> tuple[Invitation, ...]:
        """The organization's invitations, from the store's expiry-aware listing."""
        return self.store.invitations_for_organization(organization_id, now=now)

    def issue(self, offer: InvitationOffer, *, expires_at: datetime, now: datetime) -> str:
        """Mint through the service, so canonicalization and `Invitation.create` still run.

        `offer` stays grouped rather than expanded into its four fields: `InvitationService.issue`
        records that spelling the signature flat cost seven parameters and scored 9.69 on
        CodeScene's Excess Number of Function Arguments.
        """
        return self.service.issue(offer, expires_at=expires_at, now=now)

    def revoke(
        self,
        organization_id: str,
        invitation_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> None:
        """Revoke through the service, which owns `FR-025`'s uniform refusal.

        `actor_account_id` is forwarded rather than dropped even though the service `del`s it:
        `R4-01` §4.1 fixes the signature with it, and a seam that quietly narrowed the call
        contract would be the place a later actor-carrying revocation silently lost its actor.
        """
        self.service.revoke(
            organization_id,
            invitation_id,
            actor_account_id=actor_account_id,
            now=now,
        )


@dataclass(frozen=True, slots=True)
class BetaServices:
    """What `create_app` receives for admission and reporting, once the recorder is around them."""

    recorder: PipelineRecorder
    profiling: RecordingProfilingService
    reports: ReportServices


def build_beta_services(stack: RuntimeStack) -> BetaServices:
    """The beta API's admission and report services, recording the workspace (`W1-04b`).

    `RecordingProfilingService` is a second `ProfilingService` over the same repositories as
    `stack.services.profiling`: the stack's own instance stays the read port every workspace door
    reads admissions through, and this one is what the route admits through. Two instances of a
    stateless service over one set of repositories is one reading; what `W1-04` forbade was a
    second *decision*.
    """
    recorder = build_pipeline_recorder(stack)
    return BetaServices(
        recorder=recorder,
        profiling=RecordingProfilingService(
            AdmissionPorts(
                sessions=SqlSessionStore(stack.factory),
                uploads=SqlUploadRepository(stack.factory),
                objects=stack.objects,
                profiles=SqlProfileRepository(stack.factory),
            ),
            recorder=recorder,
        ),
        reports=_recording_report_services(stack, recorder),
    )


def _recording_report_services(stack: RuntimeStack, recorder: PipelineRecorder) -> ReportServices:
    """`build_report_services`, with the run started for every job the queued service creates."""
    services = build_report_services(stack)
    return ReportServices(
        jobs=RecordingReportRequests(services.jobs, recorder=recorder),
        bundles=services.bundles,
        artifacts=services.artifacts,
        packages=services.packages,
    )


def build_external_authentication_services(
    stack: RuntimeStack,
) -> ExternalAuthenticationServices | None:
    """Compose provider proof with local identity, state, organization, and session stores."""
    if stack.identity_provider is None:
        return None
    accounts = SqlAccountStore(stack.factory)
    organizations = SqlOrganizationStore(stack.factory)
    sessions = RcaSessionService(
        SqlRcaSessionStore(stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
    )
    return ExternalAuthenticationServices(
        identity_provider=stack.identity_provider,
        sessions=sessions,
        lifecycle=LifecycleService(accounts, organizations),
        switcher=OrganizationSwitcher(sessions, organizations),
    )


def build_recovery_security_service(stack: RuntimeStack) -> RecoverySecurityService | None:
    """Compose the Khepri-owned consequence of provider-owned credential recovery.

    **Authorized by `KHEPRI-DEC-025` §4**, which records that this service and its store shipped in
    `#240` with no production caller and requires the composition before a private-beta tester is
    admitted.

    Returns `None` when no provider is configured, mirroring
    `build_external_authentication_services`: the consequence is a consequence *of provider-owned
    recovery*, so a deployment with Clerk disabled has nothing for it to follow. Khepri-credential
    recovery is `R5-02`…`R5-04`, deferred while Clerk owns credentials.

    The collaborators are the same live authorities the authentication route uses -- one
    `SessionService` over the RCA session store and one `LifecycleService` -- rather than new ones,
    so revocation and account state have a single definition. `KHEPRI-DEC-025` §3 keeps credential
    replacement itself with the provider; nothing here writes a verifier.
    """
    if stack.identity_provider is None:
        return None
    accounts = SqlAccountStore(stack.factory)
    organizations = SqlOrganizationStore(stack.factory)
    return RecoverySecurityService(
        sessions=RcaSessionService(
            SqlRcaSessionStore(stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
        ),
        lifecycle=LifecycleService(accounts, organizations),
        events=SqlRecoverySecurityEventStore(stack.factory),
    )


#: Where a comparison's per-request render directories are made. A deployment chooses it by
#: passing another path; it is created in place, so nothing is left behind per process start.
#: Deliberately not the retained-report workbook directory: a comparison is rendered on request
#: and retained nowhere (`RRA-006` §Not stored), and its files never outlive the request.
COMPARISON_DIRECTORY = Path("/tmp/khepri-comparisons")


def build_web_app(stack: RuntimeStack, *, comparisons: Path = COMPARISON_DIRECTORY) -> FastAPI:
    beta = build_beta_services(stack)
    app = create_app(
        service=stack.services.invitations,
        clock=stack.clock,
        intake_service=stack.services.intake,
        deletion_service=stack.services.deletion,
        profiling_service=beta.profiling,
        package_service=stack.services.packages,
        report_services=beta.reports,
        journey_services=JourneyServices(reader=SqlJourneyReader(stack.factory)),
    )
    add_commercial_routes(
        app,
        services=build_commercial_services(stack),
        clock=stack.clock,
    )
    add_external_authentication_routes(
        app,
        services=build_external_authentication_services(stack),
        clock=stack.clock,
    )
    add_legal_routes(app)
    add_landing_routes(app)
    add_shell_routes(
        app, services=build_shell_services(stack, comparisons=comparisons), clock=stack.clock
    )
    return app


def _shell_invitations(stack: RuntimeStack) -> ShellInvitations:
    """The shell's invitation gateway over one store and the service that owns the writes.

    One `SqlInvitationStore` instance, shared by both halves: the service reads and writes through
    the same rows the listing returns, so a revocation the shell performs is absent from the very
    next listing rather than from a second store's view of the table.
    """
    store = SqlInvitationStore(stack.factory)
    return ShellInvitations(store=store, service=RcaInvitationService(store))


def build_shell_services(
    stack: RuntimeStack, *, comparisons: Path = COMPARISON_DIRECTORY
) -> ShellServices | None:
    """The shell over the same resolver the commercial API uses (`RCA-002` `FR-041`).

    Returns `None` when the commercial half is unwired, so the shell exists exactly when the
    authority it renders does. Reusing `build_commercial_services` rather than constructing a
    resolver here keeps one definition of the checkpoint: a second construction site is how the
    shell and the API would come to disagree about who an actor is.
    """
    commercial = build_commercial_services(stack)
    if commercial is None:
        return None
    # One store, bound to a name because two fields share it: the surfaces read through `records`
    # and `W1-09`'s pins write through the same object. See the `pins=` comment below.
    records = SqlWorkspaceRecordStore(stack.factory)
    return ShellServices(
        resolver=commercial.resolver,
        organizations=SqlOrganizationStore(stack.factory),
        # The gateway needs one read and two writes, and they live on two different objects --
        # see `ShellInvitations`. Passing the service alone left the Team surface raising
        # `AttributeError` on `invitations_for_organization` in the built wheel.
        invitations=_shell_invitations(stack),
        bridge=commercial.bridge,
        # `W1-05`: the same record store the workspace actions write through, resolved through
        # the same isolation door they write under, so the shell shows exactly the rows the
        # actions recorded and no second reading of the scope exists.
        records=records,
        isolation=IsolationService(
            SqlOrganizationStore(stack.factory), SqlAccountStore(stack.factory)
        ),
        # `W1-06`: the Passport is read from the provenance the run retained at completion
        # (`KHEPRI-DEC-033` §2); the links and the jobs' sessions serve the artifact handoff, read
        # per scope rather than per run so the spine's cost does not grow with its rows.
        provenance=ProvenanceReader(
            ProvenanceSources(
                provenance=SqlRunProvenanceStore(stack.factory),
                reports=SqlRunReportStore(stack.factory),
                handoffs=SqlJobSessions(stack.factory),
            ),
            clock=stack.clock,
        ),
        # `W1-07a`: the owner-requested ending (`FR-123`). Without this the field keeps its `None`
        # default, `offers_deletion` omits the route, and the capability is absent from the
        # deployed image while every route test passes over a hand-wired `ShellServices` -- which
        # is what review on `#382` found. `R7-01` §3 puts the composition here: the RCA record
        # store and the RRA content path may not import each other.
        #
        # `stack.services.deletion` is reused rather than rebuilt. It is the same
        # `DeletionService` `build_web_app` already hands the beta app, so content deleted from
        # the shell and content deleted through the journey end by one object with one definition
        # of what ending means.
        pins=records,
        deletion=WorkspaceDeletion(
            DeletionSources(
                store=SqlWorkspaceRecordStore(stack.factory),
                audit=SqlWorkspaceAuditStore(stack.factory),
                ledger=SqlRevocationLedger(stack.factory),
                content=stack.services.deletion,
                factory=stack.factory,
            )
        ),
        # `W1-09`: pins (`FR-128`, under active `KHEPRI-DEC-034`). Wired here for the reason the
        # comment above records from `#382` -- without the field, `offers_pins` omits the routes
        # and the capability is absent from the deployed image while every route test passes over
        # a hand-wired `ShellServices`.
        #
        # **The `records` store, not a second one.** `pin` and `pins_for_scope` write and read the
        # same tables the Overview and Data surfaces read, and the cascade that ends a pin lives
        # inside `set_retention_state` on this very class. A second `SqlWorkspaceRecordStore` over
        # the same factory would work and would be a second object holding one definition.
        comparisons=build_comparison_actions(stack, workbooks=comparisons),
    )


def build_retention_sweep(stack: RuntimeStack) -> RetentionSweeper:
    """The sweep `khepri-retention-sweep` runs (`KHEPRI-DEC-033` §5).

    Takes the stack rather than settings so the object store, the session factory and the
    `DeletionService` are the **same ones** the API and the worker use. `DeletionService` needs the
    `S3EncryptedObjectStore` that `build_stack` already constructs; building a second one here
    would be a second wiring of the same collaborators, and `retention_sweep.py` records why that
    is the thing to avoid: *"an expiry route that deleted differently from the on-demand route
    would be a second deletion implementation to keep correct."*

    The collaborators mirror `local/wiring.py`'s composition exactly, so the local sweep and the
    deployed sweep cannot enforce different horizons. No horizon overrides: production runs the
    governed twenty-four months, twelve months and thirty days.
    """
    return build_retention_sweeper(
        jobs=stack.reports.jobs,
        deletion=stack.services.deletion,
        factory=stack.factory,
        retention=RetentionPasses(
            accounts=AccountRetentionSweeper(SqlAccountStore(stack.factory)),
            events=MembershipEventSweeper(SqlOrganizationStore(stack.factory)),
            sessions=SessionRetentionSweeper(SqlCommercialSessionStore(stack.factory)),
            invitations=InvitationRetentionSweeper(SqlInvitationStore(stack.factory)),
            recovery_events=RecoverySecurityEventSweeper(
                SqlRecoverySecurityEventStore(stack.factory)
            ),
            # `W1-07b`'s two `KHEPRI-DEC-033` §2 horizons, which had no implementation at all
            # before that slice -- not merely no caller. Without these the workspace audit events
            # and the deletion evidence `W1-07a` writes accumulate indefinitely under a stated
            # twelve-month rule, which is the shape §5 exists to close.
            workspace_audit=WorkspaceAuditSweeper(SqlWorkspaceAuditStore(stack.factory)),
            evidence=DeletionEvidenceSweeper(SqlDeletionRepository(stack.factory)),
        ),
    )


def build_pipeline(
    stack: RuntimeStack,
    *,
    workbooks: Path,
    printer: PagePrinter,
) -> ReportPipeline:
    workbooks.mkdir(parents=True, exist_ok=True)
    renderers: tuple[MaterializedRenderer, ...] = (
        HtmlReportRenderer(),
        PdfReportRenderer(printer=printer),
        ExcelSurfaceRenderer(directory=workbooks),
    )
    return ReportPipeline(
        ports=ReportPipelinePorts(
            packages=SessionFactPackageSource(
                packages=stack.services.packages,
                now=stack.clock,
            ),
            adapter=DeterministicNarrator(),
            renderers=renderers,
            deliveries=stack.reports.publisher,
        ),
        monotonic_ms=lambda: int(stack.clock().timestamp() * 1000),
    )


__all__ = [
    "ReportStores",
    "RuntimeClients",
    "RuntimeStack",
    "SessionServices",
    "build_clients",
    "build_commercial_services",
    "build_external_authentication_services",
    "build_pipeline",
    "build_recovery_security_service",
    "build_report_services",
    "build_stack",
    "build_web_app",
    "utc_now",
]
