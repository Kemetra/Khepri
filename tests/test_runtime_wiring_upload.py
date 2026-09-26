"""The deployed composition root, driven through an upload (`#529` T-06; `RCA-005` `FR-110`).

`test_runtime_wiring.py::test_the_beta_routes_admit_and_request_through_the_recording_services`
guards `build_web_app`'s wiring by substring, and every behavioural `W1-04b` test drives
`w104b_support._beta_app` -- a hand-copied sibling of `build_web_app` that already omits
`deletion_service` and `journey_services`. A composition root that stopped handing `create_app`
the recording profiler would keep both green. This test drives `build_web_app(stack)` itself,
over SQLite, through the journey's own upload and profile routes, and reads the dataset-version
row back.

The object store is the production `S3EncryptedObjectStore`; only its network client is a dict,
so every seal, checksum and verification runs exactly as deployed.
"""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from sqlalchemy import URL

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_cookie import SESSION_COOKIE as RCA_SESSION_COOKIE
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.rca.session_service import SessionService as RcaSessionService
from khepri.rca.switching import OrganizationSwitcher
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rra.envelope import MasterKey
from khepri.rra.persistence import Base as RraBase
from khepri.runtime.config import RuntimeSettings
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME
from khepri.runtime.wiring import RuntimeClients, build_stack, build_web_app
from tests.w104_support import CREDENTIAL, NOW
from tests.w104b_support import HTTPS, submit


class InMemoryS3Client:
    """The S3 calls `S3EncryptedObjectStore` makes on this path, over a dict."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, *, Key: str, Body: bytes, ChecksumSHA256: str, **_: object) -> dict:
        self.objects[Key] = bytes(Body)
        return {"ChecksumSHA256": ChecksumSHA256}

    def get_object(self, *, Key: str, **_: object) -> dict:
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Key: str, **_: object) -> dict:
        self.objects.pop(Key, None)
        return {}


def _settings(tmp_path) -> RuntimeSettings:
    return RuntimeSettings(
        database_url=URL.create("sqlite+pysqlite", database=str(tmp_path / "wiring.db")),
        storage_endpoint="https://fra1.spaces.example",
        storage_region="fra1",
        bucket="khepri-beta-content",
        master_key=MasterKey(material=b"k" * 32),
        clerk=None,
    )


def test_the_deployed_app_records_a_dataset_version_for_an_upload(tmp_path) -> None:
    stack = build_stack(
        _settings(tmp_path), clients=RuntimeClients(s3=InMemoryS3Client()), clock=lambda: NOW
    )
    engine = stack.factory.kw["bind"]
    try:
        RcaBase.metadata.create_all(engine)
        RraBase.metadata.create_all(engine)
        owner = AccountService(SqlAccountStore(stack.factory)).create_account(
            "owner@example.test", CREDENTIAL
        )
        organizations = SqlOrganizationStore(stack.factory)
        organization = OrganizationService(organizations).create_organization(
            "Acme", owner.account_id, now=NOW
        )
        scope = organizations.get_scope(organization.organization_id)
        assert scope is not None
        # A browser reaches the analysis the way the deployed shell hands it over: a live RCA
        # session enters the journey, which sets the beta cookie. A bare workspace cookie is
        # refused since `#594`, because the beta routes re-check membership.
        sessions = RcaSessionService(
            SqlRcaSessionStore(stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
        )
        token = sessions.create(owner.account_id, now=NOW)
        OrganizationSwitcher(sessions, organizations).switch(
            token, organization.organization_id, now=NOW
        )
        app = build_web_app(stack)
        # `Origin` as a browser sends it (`require_same_origin`, `#434` §2).
        with TestClient(app, base_url=HTTPS, headers={"Origin": HTTPS}) as client:
            client.cookies.set(RCA_SESSION_COOKIE, token)
            entered = client.post(
                f"/app/en/{organization.organization_id}/analyses", follow_redirects=False
            )
            assert entered.status_code == 303, entered.text
            consented = client.post("/api/v1/beta/consent", json={"consent_version": "v1"})
            assert consented.status_code == 204, consented.text

            submit(client)

        versions = SqlWorkspaceRecordStore(stack.factory).dataset_versions_for_scope(scope.owner_id)
        assert len(versions) == 1
    finally:
        engine.dispose()
