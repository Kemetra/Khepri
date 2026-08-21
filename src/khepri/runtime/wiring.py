"""Production service graph shared by the approved web and worker roles."""

from __future__ import annotations

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
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.rra.api import create_app
from khepri.rra.artifact_persistence import SqlArtifactRepository
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.deterministic_narrative import DeterministicNarrator
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
from khepri.rra.rendering.pdf import PagePrinter, PdfReportRenderer
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
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from khepri.runtime.config import RuntimeSettings

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


def build_clients(settings: RuntimeSettings) -> RuntimeClients:
    retries = Config(retries={"max_attempts": 3, "mode": "standard"})
    return RuntimeClients(
        s3=boto3.client("s3", region_name=settings.region, config=retries),
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
        kms_key_arn=settings.kms_key_arn,
        expected_bucket_owner=settings.expected_bucket_owner,
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
        SqlRcaSessionStore(stack.factory),
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


def build_web_app(stack: RuntimeStack) -> FastAPI:
    app = create_app(
        service=stack.services.invitations,
        clock=stack.clock,
        intake_service=stack.services.intake,
        deletion_service=stack.services.deletion,
        profiling_service=stack.services.profiling,
        package_service=stack.services.packages,
        report_services=build_report_services(stack),
        journey_services=JourneyServices(reader=SqlJourneyReader(stack.factory)),
    )
    add_commercial_routes(
        app,
        services=build_commercial_services(stack),
        clock=stack.clock,
    )
    return app


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
    "build_pipeline",
    "build_report_services",
    "build_stack",
    "build_web_app",
    "utc_now",
]
