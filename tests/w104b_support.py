"""The world `W1-04b` runs in: the deployed beta API and the worker, composed the way
`khepri.runtime.wiring` composes them, over `tests/w104_support.py`'s engine.

`W1-04` proved the workspace actions work when a test calls them. `W1-05` proved the surfaces
render what the actions wrote. Neither proved that anything in the deployed application *reaches*
the actions -- review on `#373` found that nothing did. These fixtures drive the real HTTP routes a
customer's browser drives (`consent`, `uploads`, `profile`, `facts`, `reports`) and the real worker,
and the only doubles are the renderers' bytes, because rendering is `RRA-006`'s and needs Chromium.
Every store between the route and the surface is the production class over one engine.
"""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rca.workspace.scopes import SqlIsolationScopes
from khepri.rra.api import create_app
from khepri.rra.artifact_persistence import SqlArtifactRepository
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.deterministic_narrative import DeterministicNarrator
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.package_source import SessionFactPackageSource
from khepri.rra.persistence import SqlProfileRepository
from khepri.rra.pipeline import ReportPipeline, ReportPipelinePorts
from khepri.rra.report_services import (
    DeliveredBundleAdapter,
    JobReader,
    ReportArtifactAdapter,
    ReportRequestAdapter,
)
from khepri.rra.reports import ReportServices
from khepri.rra.session_cookie import SESSION_COOKIE
from khepri.rra.sessions import InvitationService, open_commercial_session
from khepri.rra.storage import ObjectWrite, PutResult
from khepri.rra.worker import (
    ReportExecutionFailed,
    ReportJobMessage,
    ReportWorker,
    WorkerExecution,
    WorkerPolicy,
)
from khepri.runtime.pipeline_recording import (
    AdmissionPorts,
    PipelineRecorder,
    RecorderReads,
    RecordingProfilingService,
    RecordingReportRequests,
    SettlingJobStore,
)
from khepri.runtime.workspace import RecordStores, WorkspacePorts
from khepri.runtime.workspace_recording import WorkspaceRecording
from tests.rra003_contract_fixtures import profile_payload
from tests.test_rra006_pipeline import ArtifactRenderer
from tests.w104_support import GOLDEN_CSV, NOW, Member, MemoryObjectStore, World, attestation
from tests.w104_support import world as base_world

#: The worker's retry delay here. Short, because a test that abandons a job advances the clock
#: past it three times; the value itself is not under test.
RETRY_DELAY = timedelta(seconds=60)
LEASE_FOR = timedelta(minutes=5)
WORKER_ID = "w104b-worker"
#: The beta cookie is `secure`, so a plain-http client would never send it back and every step
#: after redemption would read as unauthenticated -- `test_local_journey.py` records the same.
HTTPS = "https://testserver"


class Clock:
    """A clock a test can move, so a retry can become due without sleeping."""

    def __init__(self, now: datetime = NOW) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, by: timedelta) -> datetime:
        self.now = self.now + by
        return self.now


class ArtifactObjects(MemoryObjectStore):
    """The upload store, also able to keep the report's artifacts (`put_or_verify`)."""

    def put_or_verify(self, request: ObjectWrite) -> PutResult:
        created = request.key not in self.objects
        stored = self.put(
            key=request.key,
            content=request.content,
            media_type=request.media_type,
            sha256_hex=request.sha256_hex,
        )
        return PutResult(stored=stored, created=created)


@dataclass
class Journey:
    """One deployed-shaped composition: the beta app, its worker, and every store beneath."""

    w: World
    clock: Clock
    recorder: PipelineRecorder
    reports: SqlRunReportStore
    jobs: SqlReportJobRepository
    reader: JobReader
    deliveries: SqlDeliveryStore
    artifacts: SqlArtifactRepository
    publisher: ReportArtifactPublisher
    app: FastAPI

    def worker(self, handler: object | None = None) -> ReportWorker:
        """The worker as `build_worker_loop` composes it: the settling store around the jobs."""
        return ReportWorker(
            jobs=SettlingJobStore(self.jobs, reader=self.reader, recorder=self.recorder),
            handler=handler or self.pipeline(),
            clock=self.clock,
            policy=WorkerPolicy(worker_id=WORKER_ID, lease_for=LEASE_FOR, retry_delay=RETRY_DELAY),
        )

    def pipeline(self) -> ReportPipeline:
        """The real pipeline over the real publisher; only the rendered bytes are stand-ins."""
        return ReportPipeline(
            ports=ReportPipelinePorts(
                packages=SessionFactPackageSource(packages=self.w.packages, now=self.clock),
                adapter=DeterministicNarrator(),
                renderers=(
                    ArtifactRenderer("web"),
                    ArtifactRenderer("pdf"),
                    ArtifactRenderer("excel"),
                ),
                deliveries=self.publisher,
            ),
            monotonic_ms=lambda: 0,
        )

    def run_job(self, job_id: str, handler: object | None = None) -> None:
        """One worker attempt over the job, exactly as the claim loop would drive it -- including
        swallowing the failure the loop swallows (`ClaimWorkerLoop.run_once`), because the job
        store has already recorded the attempt by the time it is raised."""
        with suppress(ReportExecutionFailed):
            self.worker(handler).process(ReportJobMessage(job_id=job_id))


def journey() -> Journey:
    w = base_world()
    clock = Clock()
    objects = ArtifactObjects()
    jobs = SqlReportJobRepository(w.factory)
    reader = JobReader(w.factory)
    deliveries = SqlDeliveryStore(w.factory, now=clock)
    artifacts = SqlArtifactRepository(w.factory)
    publisher = ReportArtifactPublisher(
        repository=artifacts, deliveries=deliveries, objects=objects, now=clock
    )
    recorder = PipelineRecorder(
        recording=WorkspaceRecording(
            rra=WorkspacePorts(
                sessions=w.sessions,
                uploads=w.uploads,
                profiling=w.profiling,
                packages=w.packages,
                deliveries=deliveries,
                artifacts=artifacts,
            ),
            rca=RecordStores(
                workspace=w.store, profiles=w.profiles, audit=w.audit, factory=w.factory
            ),
        ),
        reads=RecorderReads(
            sessions=w.sessions,
            scopes=SqlIsolationScopes(w.factory),
            reports=SqlRunReportStore(w.factory),
            jobs=reader,
        ),
    )
    profiling = RecordingProfilingService(
        AdmissionPorts(
            sessions=w.sessions,
            uploads=w.uploads,
            objects=w.objects,
            profiles=SqlProfileRepository(w.factory),
        ),
        recorder=recorder,
    )
    requests = RecordingReportRequests(
        ReportRequestAdapter(jobs=jobs, reader=reader, packages=w.packages, deliveries=deliveries),
        recorder=recorder,
    )
    app = create_app(
        service=InvitationService(w.sessions),
        clock=clock,
        intake_service=w.intake,
        profiling_service=profiling,
        package_service=w.packages,
        report_services=ReportServices(
            jobs=requests,
            bundles=DeliveredBundleAdapter(deliveries=deliveries, reader=reader),
            artifacts=ReportArtifactAdapter(publisher),
            packages=w.packages,
        ),
    )
    return Journey(
        w=w,
        clock=clock,
        recorder=recorder,
        reports=SqlRunReportStore(w.factory),
        jobs=jobs,
        reader=reader,
        deliveries=deliveries,
        artifacts=artifacts,
        publisher=publisher,
        app=app,
    )


def commercial_client(j: Journey, who: Member) -> tuple[TestClient, str]:
    """A browser holding the beta cookie the shell's entry route sets (`R8-06`), consented."""
    session = open_commercial_session(j.w.sessions, owner_id=who.owner_id, now=j.clock())
    client = TestClient(j.app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, session.session_id)
    consented = client.post("/api/v1/beta/consent", json={"consent_version": "v1"})
    assert consented.status_code == 204, consented.text
    return client, session.session_id


def invited_client(j: Journey) -> TestClient:
    """A design-partner session from an invitation: a scope no organization owns."""
    token = InvitationService(j.w.sessions).issue_invitation(
        expires_at=j.clock() + timedelta(days=7)
    )
    client = TestClient(j.app, base_url=HTTPS)
    redeemed = client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    assert redeemed.status_code == 201, redeemed.text
    consented = client.post("/api/v1/beta/consent", json={"consent_version": "v1"})
    assert consented.status_code == 204, consented.text
    return client


def submit(client: TestClient, content: bytes = GOLDEN_CSV, *, attest: bool = True) -> dict:
    """Upload and profile, as the journey's upload step does. Returns the profile response."""
    uploaded = client.post(
        "/api/v1/beta/uploads", content=content, headers={"content-type": "text/csv"}
    )
    assert uploaded.status_code == 201, uploaded.text
    profiled = client.post("/api/v1/beta/profile", json=profile_body(content, attest=attest))
    assert profiled.status_code in (200, 201), profiled.text
    return profiled.json()


def profile_body(content: bytes, *, attest: bool) -> dict:
    """The profile request the journey posts, attesting coverage over the file's own days."""
    body = profile_payload()
    if attest:
        days = [
            date.fromisoformat(line.split(b",")[0].decode())
            for line in content.strip().split(b"\n")[1:]
        ]
        body["coverage_manifest"] = attestation(min(days), max(days)).model_dump(mode="json")
    return body


def request_report(client: TestClient) -> str:
    """Derive the facts and ask for the report, as the journey's facts and report steps do."""
    facts = client.post("/api/v1/beta/facts")
    assert facts.status_code in (200, 201), facts.text
    requested = client.post("/api/v1/beta/reports", json={})
    assert requested.status_code in (200, 201), requested.text
    return requested.json()["job_id"]


class BrokenHandler:
    """A pipeline that never delivers, so the job walks its retries to the dead letter."""

    def __init__(self) -> None:
        self.attempts = 0

    def __call__(self, execution: WorkerExecution) -> None:
        self.attempts += 1
        raise RuntimeError("the renderer is down")


__all__ = [
    "LEASE_FOR",
    "RETRY_DELAY",
    "WORKER_ID",
    "ArtifactObjects",
    "BrokenHandler",
    "Clock",
    "Journey",
    "commercial_client",
    "invited_client",
    "journey",
    "profile_body",
    "request_report",
    "submit",
]
