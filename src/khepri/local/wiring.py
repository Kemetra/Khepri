"""Every collaborator the local stack builds, assembled once.

**This is the composition root the Dockerfile names.** Its comment says the entry
point "arrives with the slice that gives each container its command", and no such
slice has landed — `create_app` is called by tests only, and `ReportWorker` is
constructed by nothing. This module builds both halves so a developer can run
them, without claiming to be that slice: it is local wiring, not a container
command, and `khepri.infra.compute` still passes no command of its own.

**One engine, one set of repositories, two consumers.** The web app and the worker
read the same PostgreSQL database and the same object store, because they do in
the deployed design too. Building them from one `LocalStack` object rather than
twice over is the same reason `khepri.infra.app` hands one `EnvironmentProps` to
both stacks: shared construction makes agreement structural.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from khepri.local.config import LocalSettings
from khepri.local.packages import build_package_source
from khepri.local.storage import build_local_object_store
from khepri.local.sweeper import LocalSweeper, build_local_sweeper
from khepri.local.worker import LocalReportWorker, LocalWorkerPorts, build_local_worker
from khepri.rca.lifecycle import AccountRetentionSweeper
from khepri.rca.persistence import SqlAccountStore
from khepri.rra.api import create_app
from khepri.rra.artifact_persistence import SqlArtifactRepository
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.deterministic_narrative import DeterministicNarrator
from khepri.rra.intake import IntakeService
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.journey.routes import JourneyServices
from khepri.rra.journey.state import SqlJourneyReader
from khepri.rra.packages import FactPackageService
from khepri.rra.persistence import (
    SqlDeletionRepository,
    SqlFactPackageRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.pipeline import ReportPipeline, ReportPipelinePorts
from khepri.rra.rendering.chromium import launch_chromium
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PagePrinter, PdfReportRenderer
from khepri.rra.report_artifacts import MaterializedRenderer
from khepri.rra.report_services import (
    DeliveredBundleAdapter,
    JobReader,
    ReportArtifactAdapter,
    ReportRequestAdapter,
)
from khepri.rra.reports import ReportServices
from khepri.rra.sessions import InvitationService


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SessionServices:
    """What a beta participant's own journey runs through, up to the report."""

    invitations: InvitationService
    intake: IntakeService
    profiling: ProfilingService
    packages: FactPackageService
    deletion: DeletionService


@dataclass(frozen=True, slots=True)
class ReportStores:
    """Where report jobs and delivered bundles are kept."""

    jobs: SqlReportJobRepository
    deliveries: SqlDeliveryStore
    artifacts: SqlArtifactRepository
    publisher: ReportArtifactPublisher


@dataclass(frozen=True, slots=True)
class LocalStack:
    """Everything the local journey runs against, built once and shared.

    Grouped rather than flat. A stack listing eleven collaborators side by side
    reads as one bag of things, and every consumer would take the whole bag to
    reach two of them; `ReportPipelinePorts` groups for the same reason.
    """

    settings: LocalSettings
    services: SessionServices
    reports: ReportStores
    factory: sessionmaker[Session]
    clock: Callable[[], datetime]

    @property
    def invitations(self) -> InvitationService:
        """Reached often enough by name that a hop through `services` obscures it."""
        return self.services.invitations


@dataclass(frozen=True, slots=True)
class WorkerStack:
    """The two background drivers, built over one already-constructed stack."""

    worker: LocalReportWorker
    sweeper: LocalSweeper


def build_engine(settings: LocalSettings):
    """One pooled engine. `pool_pre_ping` because a local container may restart."""
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def build_stack(
    settings: LocalSettings | None = None,
    *,
    clock: Callable[[], datetime] = utc_now,
) -> LocalStack:
    """Construct every service the web app and the worker share."""
    resolved = settings or LocalSettings.from_environment()
    factory = sessionmaker(bind=build_engine(resolved), future=True)
    objects = build_local_object_store(resolved)

    store = SqlSessionStore(factory)
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
    return LocalStack(
        settings=resolved,
        services=SessionServices(
            invitations=InvitationService(store),
            intake=IntakeService(sessions=store, uploads=uploads, objects=objects),
            profiling=ProfilingService(
                sessions=store,
                uploads=uploads,
                objects=objects,
                profiles=profiles,
            ),
            packages=FactPackageService(
                sessions=store,
                uploads=uploads,
                objects=objects,
                profiles=profiles,
                packages=packages,
            ),
            deletion=DeletionService(
                sessions=store,
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
        clock=clock,
    )


def build_pipeline(
    stack: LocalStack,
    *,
    workbooks: Path,
    printer: PagePrinter | None = None,
) -> ReportPipeline:
    """The report stages, wired to the deterministic narrator.

    **The PDF surface needs a live browser, so the caller owns it.**
    `PdfReportRenderer` takes a `PagePrinter` backed by a running Chromium, and
    that browser has to outlive every render rather than one of them — which is
    why it arrives as an argument instead of being constructed here.

    Without a printer the renderer set is incomplete and `BundleAssembler` refuses
    the bundle as `missing_surface`. That is the correct governed answer, not a
    defect: RRA-006 treats a partial export as an incomplete bundle, and a local
    run substituting some other PDF writer would be delivering a report whose
    surfaces were not produced the way the approved ones are.
    """
    renderers: list[MaterializedRenderer] = [
        HtmlReportRenderer(),
        ExcelSurfaceRenderer(directory=workbooks),
    ]
    if printer is not None:
        renderers.append(PdfReportRenderer(printer=printer))
    return ReportPipeline(
        ports=ReportPipelinePorts(
            packages=build_package_source(
                packages=stack.services.packages,
                now=stack.clock,
            ),
            adapter=DeterministicNarrator(),
            renderers=tuple(renderers),
            deliveries=stack.reports.publisher,
        ),
        monotonic_ms=lambda: int(stack.clock().timestamp() * 1000),
    )


def local_page_printer() -> AbstractContextManager[PagePrinter]:
    """A pinned-Chromium printer for the duration of a block.

    `launch_chromium` already yields a `ChromiumPagePrinter` and already applies
    the `--disable-dev-shm-usage` flag `KHEPRI-DEC-007` requires, so this is an
    alias rather than a wrapper. Wrapping it once produced a printer constructed
    around another printer, which type-checks under structural typing and fails
    three frames later inside `print_to_pdf`.
    """
    return launch_chromium()


def build_report_services(stack: LocalStack) -> ReportServices:
    """The two session-scoped adapters the report routes require.

    Neither store satisfies those Protocols on its own -- see
    `khepri.rra.report_services` for why that gap is real rather than local.
    """
    reader = JobReader(stack.factory)
    deliveries = stack.reports.deliveries
    return ReportServices(
        jobs=ReportRequestAdapter(
            jobs=stack.reports.jobs,
            reader=reader,
            packages=stack.services.packages,
            deliveries=deliveries,
        ),
        bundles=DeliveredBundleAdapter(deliveries=deliveries, reader=reader),
        artifacts=ReportArtifactAdapter(stack.reports.publisher),
    )


def build_web_app(stack: LocalStack) -> FastAPI:
    """The FastAPI application with every route group supplied."""
    return create_app(
        service=stack.invitations,
        clock=stack.clock,
        intake_service=stack.services.intake,
        deletion_service=stack.services.deletion,
        profiling_service=stack.services.profiling,
        package_service=stack.services.packages,
        report_services=build_report_services(stack),
        journey_services=JourneyServices(reader=SqlJourneyReader(stack.factory)),
    )


def build_worker_stack(
    stack: LocalStack,
    *,
    workbooks: Path,
    printer: PagePrinter | None = None,
) -> WorkerStack:
    """The worker loop and the sweeper, over one already-built stack."""
    workbooks.mkdir(parents=True, exist_ok=True)
    return WorkerStack(
        worker=build_local_worker(
            LocalWorkerPorts(
                jobs=stack.reports.jobs,
                factory=stack.factory,
                handler=build_pipeline(stack, workbooks=workbooks, printer=printer),
            ),
            clock=stack.clock,
        ),
        sweeper=build_local_sweeper(
            jobs=stack.reports.jobs,
            deletion=stack.services.deletion,
            factory=stack.factory,
            # KHEPRI-DEC-015 §2b's retention pass. Without this the horizon is enforced by
            # nothing: the class existed but no operational entry point called it, so disabled
            # accounts would have kept their email identities indefinitely.
            accounts=AccountRetentionSweeper(SqlAccountStore(stack.factory)),
        ),
    )


__all__ = [
    "LocalStack",
    "ReportStores",
    "SessionServices",
    "WorkerStack",
    "build_engine",
    "build_pipeline",
    "build_report_services",
    "build_stack",
    "build_web_app",
    "build_worker_stack",
    "local_page_printer",
    "utc_now",
]
