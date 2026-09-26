"""A deployed stack for the #594 tests: one organization, an owner, and a second member.

`build_web_app` over a real stack, so every assertion is about the composition the image serves
rather than a hand-wired sibling of it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import MEMBER_ROLE, OrganizationService
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.persistence import MembershipRow, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_cookie import SESSION_COOKIE as RCA_COOKIE
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.rca.session_service import SessionService as RcaSessionService
from khepri.rca.switching import OrganizationSwitcher
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rra.persistence import Base as RraBase
from khepri.rra.persistence import DatasetProfileRow
from khepri.rra.session_cookie import SESSION_COOKIE as BETA_COOKIE
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME
from khepri.runtime.wiring import RuntimeClients, build_stack, build_web_app
from tests.test_runtime_wiring_upload import InMemoryS3Client, _settings
from tests.w104_support import CREDENTIAL, NOW
from tests.w104b_support import HTTPS


@dataclass
class Deployed:
    """One organization, an owner, a member with a live RCA session, and the deployed app."""

    stack: object
    client: TestClient
    organization_id: str
    owner_account: str
    member_account: str
    scope: str

    def rca_token(self, account_id: str) -> str:
        sessions = RcaSessionService(
            SqlRcaSessionStore(self.stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
        )
        token = sessions.create(account_id, now=NOW)
        OrganizationSwitcher(sessions, SqlOrganizationStore(self.stack.factory)).switch(
            token, self.organization_id, now=NOW
        )
        return token

    def enter_journey(self, token: str) -> None:
        """The shell's journey entry, which is what hands the browser its beta cookie."""
        self.client.cookies.set(RCA_COOKIE, token)
        entered = self.client.post(
            f"/app/en/{self.organization_id}/analyses", follow_redirects=False
        )
        assert entered.status_code == 303, entered.text
        assert self.client.cookies.get(BETA_COOKIE), "the entry route set no beta cookie"

    def revoke_member(self) -> None:
        OrganizationService(SqlOrganizationStore(self.stack.factory)).revoke_membership(
            self.organization_id,
            self.member_account,
            actor_account_id=self.owner_account,
            now=NOW,
        )

    def profiles(self) -> tuple[DatasetProfileRow, ...]:
        with self.stack.factory() as database:
            statement = select(DatasetProfileRow).where(DatasetProfileRow.owner_id == self.scope)
            return tuple(database.scalars(statement))

    def versions(self) -> tuple[object, ...]:
        return tuple(
            SqlWorkspaceRecordStore(self.stack.factory).dataset_versions_for_scope(self.scope)
        )


@pytest.fixture(name="deployed")
def deployed_fixture(tmp_path):
    stack = build_stack(
        _settings(tmp_path), clients=RuntimeClients(s3=InMemoryS3Client()), clock=lambda: NOW
    )
    engine = stack.factory.kw["bind"]
    RcaBase.metadata.create_all(engine)
    RraBase.metadata.create_all(engine)
    accounts = AccountService(SqlAccountStore(stack.factory))
    owner = accounts.create_account("owner@example.test", CREDENTIAL).account_id
    member = accounts.create_account("member@example.test", CREDENTIAL).account_id
    organizations = SqlOrganizationStore(stack.factory)
    organization = OrganizationService(organizations).create_organization("Acme", owner, now=NOW)
    with stack.factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=member,
                role=MEMBER_ROLE,
            )
        )
    scope = organizations.get_scope(organization.organization_id)
    assert scope is not None
    with TestClient(build_web_app(stack), base_url=HTTPS, headers={"Origin": HTTPS}) as client:
        yield Deployed(stack, client, organization.organization_id, owner, member, scope.owner_id)
    engine.dispose()


__all__ = ["BETA_COOKIE", "RCA_COOKIE", "Deployed", "deployed_fixture"]
