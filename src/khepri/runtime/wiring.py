"""Production service graph shared by the approved web and worker roles."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.api import create_app
from khepri.rra.bundle import SurfaceRenderer
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.deterministic_narrative import DeterministicNarrator
from khepri.rra.intake import IntakeService
from khepri.rra.job_persistence import SqlReportJobRepository
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
from khepri.rra.report_publication import QueuedReportRequestService
from khepri.rra.report_services import (
    DeliveredBundleAdapter,
    JobReader,
    ReportRequestAdapter,
)
from khepri.rra.reports import ReportServices
from khepri.rra.sessions import InvitationService
from khepri.rra.sqs_queue import SqsReportPublisher
from khepri.rra.storage import S3EncryptedObjectStore
from khepri.runtime.config import RuntimeSettings


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class RuntimeClients:
    s3: Any
    sqs: Any


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
        sqs=boto3.client("sqs", region_name=settings.region, config=retries),
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
            deliveries=SqlDeliveryStore(factory, now=clock),
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
            publisher=SqsReportPublisher(
                client=stack.clients.sqs,
                queue_url=stack.settings.queue_url,
            ),
        ),
        bundles=DeliveredBundleAdapter(
            deliveries=stack.reports.deliveries,
            reader=reader,
        ),
    )


def build_web_app(stack: RuntimeStack) -> FastAPI:
    return create_app(
        service=stack.services.invitations,
        clock=stack.clock,
        intake_service=stack.services.intake,
        deletion_service=stack.services.deletion,
        profiling_service=stack.services.profiling,
        package_service=stack.services.packages,
        report_services=build_report_services(stack),
    )


def build_pipeline(
    stack: RuntimeStack,
    *,
    workbooks: Path,
    printer: PagePrinter,
) -> ReportPipeline:
    workbooks.mkdir(parents=True, exist_ok=True)
    renderers: tuple[SurfaceRenderer, ...] = (
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
            deliveries=stack.reports.deliveries,
        ),
        monotonic_ms=lambda: int(stack.clock().timestamp() * 1000),
    )


__all__ = [
    "ReportStores",
    "RuntimeClients",
    "RuntimeStack",
    "SessionServices",
    "build_clients",
    "build_pipeline",
    "build_report_services",
    "build_stack",
    "build_web_app",
    "utc_now",
]
