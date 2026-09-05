from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from khepri.rca.identity import IdentityProvider
from khepri.rca.isolation import IsolationService
from khepri.rca.recovery_security import RecoverySecurityService
from khepri.rca.recovery_security_persistence import SqlRecoverySecurityEventStore
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.envelope import MasterKey
from khepri.rra.report_publication import QueuedReportRequestService
from khepri.rra.report_services import DeliveredBundleAdapter, ReportArtifactAdapter
from khepri.rra.storage import S3EncryptedObjectStore
from khepri.runtime.config import ClerkIdentitySettings, RuntimeSettings
from khepri.runtime.external_auth_api import EXTERNAL_SESSION_PATH
from khepri.runtime.pipeline_recording import (
    PipelineRecorder,
    RecordingProfilingService,
    RecordingReportRequests,
    SettlingJobStore,
)
from khepri.runtime.shell_provenance import ProvenanceReader
from khepri.runtime.wiring import (
    RuntimeClients,
    build_beta_services,
    build_external_authentication_services,
    build_pipeline_recorder,
    build_recovery_security_service,
    build_report_services,
    build_shell_services,
    build_stack,
    build_web_app,
    build_workspace_actions,
)
from khepri.runtime.worker import build_worker_loop

_MASTER_KEY = MasterKey(material=b"k" * 32)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


class AwsClientStub:
    pass


def settings() -> RuntimeSettings:
    return RuntimeSettings.from_environment(
        {
            "KHEPRI_DATABASE_SECRET": json.dumps(
                {
                    "username": "khepri_runtime",
                    "password": "secret",
                    "engine": "postgres",
                    "host": "database.internal",
                    "port": 5432,
                    "dbname": "khepri",
                }
            ),
            "KHEPRI_STORAGE_ENDPOINT": "https://fra1.spaces.example",
            "KHEPRI_STORAGE_REGION": "fra1",
            "KHEPRI_BUCKET": "khepri-beta-content",
            "KHEPRI_STORAGE_MASTER_KEY": base64.b64encode(b"k" * 32).decode("ascii"),
        }
    )


def runtime_stack():
    return build_stack(
        settings(),
        clients=RuntimeClients(s3=AwsClientStub()),
        clock=lambda: NOW,
    )


def test_stack_uses_the_production_encrypted_store() -> None:
    assert isinstance(runtime_stack().objects, S3EncryptedObjectStore)
    assert runtime_stack().identity_provider is None


def test_disabled_provider_configuration_registers_no_external_session_route() -> None:
    paths = {route.path for route in build_web_app(runtime_stack()).routes}

    assert EXTERNAL_SESSION_PATH not in paths


def clerk_enabled_settings() -> RuntimeSettings:
    """The same settings with a configured private-beta provider."""
    configured = settings()
    return RuntimeSettings(
        database_url=configured.database_url,
        storage_endpoint=configured.storage_endpoint,
        storage_region=configured.storage_region,
        bucket=configured.bucket,
        master_key=_MASTER_KEY,
        clerk=ClerkIdentitySettings(
            mode="private_beta",
            issuer="https://private-beta.clerk.accounts.example",
            jwt_key="-----BEGIN PUBLIC KEY-----x-----END PUBLIC KEY-----",
            key_id="ins_private_beta",
            authorized_parties=("https://beta.khepri.example",),
            audience=None,
        ),
    )


def clerk_enabled_stack():
    return build_stack(
        clerk_enabled_settings(),
        clients=RuntimeClients(s3=AwsClientStub()),
        clock=lambda: NOW,
    )


def test_stack_exposes_enabled_clerk_only_through_the_provider_seam() -> None:
    assert isinstance(clerk_enabled_stack().identity_provider, IdentityProvider)


def test_the_recovery_consequence_is_constructible_from_the_production_root() -> None:
    """`KHEPRI-DEC-025` §4: the consequence shipped with no production caller.

    The gap this closes was not a missing behaviour — every clause of `complete()` was implemented
    and tested — but a missing construction. `wiring.py` never built the service, so nothing in the
    deployed wheel could reach it. Asserting the builder returns the real service, over the real
    SQL event store, is what makes the composition evidence rather than a claim.
    """
    service = build_recovery_security_service(clerk_enabled_stack())

    assert isinstance(service, RecoverySecurityService)
    assert isinstance(service._events, SqlRecoverySecurityEventStore)


def test_the_recovery_consequence_is_absent_when_no_provider_is_configured() -> None:
    """It is a consequence *of provider-owned recovery*, so it has nothing to follow without one.

    Mirrors `build_external_authentication_services`. Khepri-credential recovery is `R5-02`…`R5-04`,
    which `KHEPRI-DEC-025` §3 keeps deferred while Clerk owns credentials — so a Clerk-disabled
    deployment having no recovery consequence is the designed state, not a gap.
    """
    assert runtime_stack().identity_provider is None
    assert build_recovery_security_service(runtime_stack()) is None


def test_the_recovery_consequence_shares_one_definition_of_live_authority() -> None:
    """Revocation and account state must not acquire a second definition here.

    The service is given the same `SessionService` shape and lifetime the authentication route
    uses. Two session services with different lifetimes would mean a session the route considers
    live and the consequence considers expired, which is how one revocation rule becomes two.
    """
    stack = clerk_enabled_stack()
    service = build_recovery_security_service(stack)
    external = build_external_authentication_services(stack)

    assert service is not None
    assert external is not None
    assert service._sessions._lifetime == external.sessions._lifetime
    assert type(service._lifecycle) is type(external.lifecycle)


def test_report_routes_use_queued_requests_and_session_scoped_deliveries() -> None:
    services = build_report_services(runtime_stack())

    assert isinstance(services.jobs, QueuedReportRequestService)
    assert isinstance(services.bundles, DeliveredBundleAdapter)
    assert isinstance(services.artifacts, ReportArtifactAdapter)
    assert isinstance(runtime_stack().reports.publisher, ReportArtifactPublisher)


def test_web_app_exposes_the_complete_approved_beta_route_set() -> None:
    app = build_web_app(runtime_stack())
    paths = {route.path for route in app.routes}

    assert {
        "/api/v1/beta/sessions/redeem",
        "/api/v1/beta/consent",
        "/api/v1/beta/uploads",
        "/api/v1/beta/profile",
        "/api/v1/beta/facts",
        "/api/v1/beta/content",
        "/api/v1/beta/reports",
        "/api/v1/beta/reports/{job_id}",
        "/api/v1/beta/reports/{job_id}/bundle",
        "/api/v1/beta/reports/{job_id}/surfaces/web/{language}",
        "/api/v1/beta/reports/{job_id}/surfaces/evidence/{language}",
        "/api/v1/beta/reports/{job_id}/surfaces/pdf/{language}",
        "/api/v1/beta/reports/{job_id}/surfaces/excel",
        "/api/v1/beta/journey",
        "/beta/{language}",
        "/beta/{language}/{step}",
        "/beta/assets/{name}",
    } <= paths


def test_runtime_app_exposes_public_legal_routes_without_commercial_context() -> None:
    """The production composition root must retain the public legal registrar."""
    client = TestClient(build_web_app(runtime_stack()))

    about = client.get("/legal/en/about-us")
    privacy = client.get("/legal/ar/privacy-policy")

    assert about.status_code == 200
    assert privacy.status_code == 503
    assert "organization" not in about.text.lower()
    assert "organization" not in privacy.text.lower()


def test_the_workspace_services_read_the_stacks_own_rra_services() -> None:
    """`W1-04`: the workspace records what the stack's `ProfilingService` and
    `FactPackageService` decided -- the very instances the beta routes use -- and reads deliveries
    and artifacts from the repositories the publisher writes. A second instance of any of them
    would be a second reading of the same decision."""
    stack = runtime_stack()

    services = build_workspace_actions(stack)

    ports = services._rra
    assert ports.profiling is stack.services.profiling
    assert ports.packages is stack.services.packages
    assert ports.deliveries is stack.reports.deliveries
    assert ports.artifacts is stack.reports.artifacts


def test_the_shell_reads_the_record_store_the_workspace_actions_write() -> None:
    """`W1-05`: Overview and Data render the rows `WorkspaceActions` recorded, through the same
    store class over the same factory. A shell without a reader has neither surface and neither
    link (`FR-049`), so the production root must hand it one."""
    stack = runtime_stack()

    shell = build_shell_services(stack)

    assert shell is not None
    assert isinstance(shell.records, SqlWorkspaceRecordStore)
    # The store is keyed by the opaque scope, so the shell must resolve the session's
    # organization through the same door the actions write under (`#373` review).
    assert isinstance(shell.isolation, IsolationService)


def test_the_shell_reads_provenance_from_the_stacks_own_rra_services() -> None:
    """`W1-06`: the Passport and the trust state are read from the admission and the package the
    run binds by digest, through the same `ProfilingService` and `FactPackageService` instances
    the routes and the recorder use -- one reading of each decision, as `W1-04` requires."""
    stack = runtime_stack()

    shell = build_shell_services(stack)

    assert shell is not None
    assert isinstance(shell.provenance, ProvenanceReader)
    assert shell.provenance.profiling is stack.services.profiling
    assert shell.provenance.packages is stack.services.packages
    # The handoff resumes the run's own session through the bridge the entry route opens with.
    assert shell.bridge is not None


def test_the_beta_routes_admit_and_request_through_the_recording_services() -> None:
    """`W1-04b`: the deployed beta API records the workspace as a side effect of the routes a
    customer's browser already drives. Review on `#373` found that nothing in `src/khepri` called
    the workspace actions; this is the composition that does, and `build_web_app` must hand
    `create_app` these two objects and not the plain services beneath them."""
    import inspect as py_inspect

    stack = runtime_stack()

    beta = build_beta_services(stack)

    assert isinstance(beta.profiling, RecordingProfilingService)
    assert beta.profiling.recorder is beta.recorder
    assert isinstance(beta.reports.jobs, RecordingReportRequests)
    assert beta.reports.jobs.recorder is beta.recorder
    # Queue publication stays inside the recording: the job is durable and published before the
    # workspace learns of it, so a recording fault never hides a queued job from the worker.
    assert isinstance(beta.reports.jobs.requests, QueuedReportRequestService)
    source = py_inspect.getsource(build_web_app)
    assert "profiling_service=beta.profiling" in source
    assert "report_services=beta.reports" in source


def test_the_recorder_reads_the_stacks_own_rra_services() -> None:
    """The pipeline door reads admission and derivation from the same instances the routes use --
    `W1-04`'s rule, applied to the second door."""
    stack = runtime_stack()

    recorder = build_pipeline_recorder(stack)

    ports = recorder.recording.ports
    assert ports.profiling is stack.services.profiling
    assert ports.packages is stack.services.packages
    assert ports.deliveries is stack.reports.deliveries
    assert ports.artifacts is stack.reports.artifacts


def test_the_worker_settles_jobs_through_the_recording_store(tmp_path) -> None:
    """The worker role is a second process; its job store is wrapped so that a delivered job
    completes its run and a dead-lettered one fails it. `ReportWorker` holds the wrapped store."""
    stack = runtime_stack()

    loop = build_worker_loop(stack, printer=object(), workbooks=tmp_path)

    jobs = loop._worker._jobs
    assert isinstance(jobs, SettlingJobStore)
    assert jobs.jobs is stack.reports.jobs
    assert isinstance(jobs.recorder, PipelineRecorder)
    # The queue's recovery sweep is where a reclaimed lease reaches the dead letter, so the queue
    # settles through the same store (review on `#375`).
    assert loop._queue._jobs is jobs
