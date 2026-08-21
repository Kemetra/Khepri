from __future__ import annotations

import json
from datetime import UTC, datetime

from khepri.rca.identity import IdentityProvider
from khepri.rra.artifact_publication import ReportArtifactPublisher
from khepri.rra.report_publication import QueuedReportRequestService
from khepri.rra.report_services import DeliveredBundleAdapter, ReportArtifactAdapter
from khepri.rra.storage import S3EncryptedObjectStore
from khepri.runtime.config import ClerkIdentitySettings, RuntimeSettings
from khepri.runtime.external_auth_api import EXTERNAL_SESSION_PATH
from khepri.runtime.wiring import RuntimeClients, build_report_services, build_stack, build_web_app

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
            "KHEPRI_AWS_REGION": "me-central-1",
            "KHEPRI_BUCKET": "khepri-beta-content",
            "KHEPRI_KMS_KEY_ARN": (
                "arn:aws:kms:me-central-1:123456789012:"
                "key/12345678-1234-1234-1234-123456789abc"
            ),
            "KHEPRI_EXPECTED_BUCKET_OWNER": "123456789012",
            "KHEPRI_QUEUE_URL": "https://sqs.example/report-jobs",
            "KHEPRI_DLQ_URL": "https://sqs.example/report-jobs-dlq",
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


def test_stack_exposes_enabled_clerk_only_through_the_provider_seam() -> None:
    configured = settings()
    configured = RuntimeSettings(
        database_url=configured.database_url,
        region=configured.region,
        bucket=configured.bucket,
        kms_key_arn=configured.kms_key_arn,
        expected_bucket_owner=configured.expected_bucket_owner,
        queue_url=configured.queue_url,
        dead_letter_queue_url=configured.dead_letter_queue_url,
        clerk=ClerkIdentitySettings(
            mode="private_beta",
            issuer="https://private-beta.clerk.accounts.example",
            jwt_key="-----BEGIN PUBLIC KEY-----x-----END PUBLIC KEY-----",
            key_id="ins_private_beta",
            authorized_parties=("https://beta.khepri.example",),
            audience=None,
        ),
    )

    stack = build_stack(
        configured,
        clients=RuntimeClients(s3=AwsClientStub()),
        clock=lambda: NOW,
    )

    assert isinstance(stack.identity_provider, IdentityProvider)


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
