"""#594: a revoked member's beta cookie stops authorizing in the revoked organization.

The shell's journey entry (`R8-06`) and artifact handoff (`W1-06`) issue `khepri_beta_session`
after a membership check. Every `/api/v1/beta/*` route then authorized on that cookie alone, so a
member whose membership was revoked kept uploading, publishing, downloading and deleting in the
organization's analysis scope. `RCA-001` `FR-030` requires the opposite: "A session whose active
organization membership has been revoked MUST cease to authorize actions in that organization",
and the owner's 2026-09-26 decision on #594 says no protected operation may proceed using the
revoked membership.

**Driven through the deployed composition.** `build_web_app` over a real stack, the beta cookie
obtained from the real journey-entry POST, and the membership revoked through
`OrganizationService.revoke_membership`. A hand-wired app would prove a guard that the deployed
image might not register.

**The effect, not only the status.** A refused profile POST must leave no profile row and no
dataset version, because a 401 that still wrote would be a refusal in name only.

**Invitation sessions are untouched.** A design-partner scope has no organization, so there is no
membership to revoke; `KHEPRI-DEC-023` keeps that path unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

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
from khepri.rra.persistence import DatasetProfileRow, SqlSessionStore
from khepri.rra.session_cookie import SESSION_COOKIE as BETA_COOKIE
from khepri.rra.sessions import InvitationService, open_commercial_session
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME
from khepri.runtime.wiring import RuntimeClients, build_stack, build_web_app
from tests.test_runtime_wiring_upload import InMemoryS3Client, _settings
from tests.w104_support import CREDENTIAL, GOLDEN_CSV, NOW
from tests.w104b_support import HTTPS, profile_body, submit


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


def _consent(client: TestClient) -> int:
    return client.post("/api/v1/beta/consent", json={"consent_version": "v1"}).status_code


class TestAMemberKeepsAccess:
    def test_a_current_member_submits_through_the_beta_cookie(self, deployed: Deployed) -> None:
        deployed.enter_journey(deployed.rca_token(deployed.member_account))

        assert _consent(deployed.client) == 204
        submit(deployed.client)

        assert len(deployed.profiles()) == 1
        assert len(deployed.versions()) == 1


class TestRevocationEndsBetaAccess:
    def test_a_revoked_members_beta_cookie_writes_nothing(self, deployed: Deployed) -> None:
        deployed.enter_journey(deployed.rca_token(deployed.member_account))
        assert _consent(deployed.client) == 204
        uploaded = deployed.client.post(
            "/api/v1/beta/uploads", content=GOLDEN_CSV, headers={"content-type": "text/csv"}
        )
        assert uploaded.status_code == 201, uploaded.text

        deployed.revoke_member()
        # The journey's own, complete profile request: absent the guard it is admitted, writes
        # the profile and records a version (`TestAMemberKeepsAccess` shows that it does).
        profiled = deployed.client.post(
            "/api/v1/beta/profile", json=profile_body(GOLDEN_CSV, attest=True)
        )

        assert profiled.status_code == 401
        assert deployed.profiles() == ()
        assert deployed.versions() == ()

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/v1/beta/journey"),
            ("GET", "/api/v1/beta/profile"),
            ("POST", "/api/v1/beta/reports"),
            ("DELETE", "/api/v1/beta/content"),
        ],
    )
    def test_every_beta_route_refuses_after_revocation(
        self, deployed: Deployed, method: str, path: str
    ) -> None:
        deployed.enter_journey(deployed.rca_token(deployed.member_account))
        deployed.revoke_member()

        assert deployed.client.request(method, path).status_code == 401

    def test_a_member_of_another_organization_cannot_carry_this_analysis(
        self, deployed: Deployed
    ) -> None:
        """A live session whose account belongs only to another organization is refused.

        The session is live and the account active, so `AuthorizationResolver.resolve` succeeds;
        what refuses is `resolve_scope`, because the account holds no membership in the
        organization owning this analysis. A revoked member is refused the same way.
        """
        deployed.enter_journey(deployed.rca_token(deployed.member_account))
        outsider = AccountService(SqlAccountStore(deployed.stack.factory)).create_account(
            "outsider@example.test", CREDENTIAL
        )
        elsewhere = OrganizationService(
            SqlOrganizationStore(deployed.stack.factory)
        ).create_organization("Elsewhere", outsider.account_id, now=NOW)
        sessions = RcaSessionService(
            SqlRcaSessionStore(deployed.stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
        )
        token = sessions.create(outsider.account_id, now=NOW)
        OrganizationSwitcher(sessions, SqlOrganizationStore(deployed.stack.factory)).switch(
            token, elsewhere.organization_id, now=NOW
        )
        deployed.client.cookies.set(RCA_COOKIE, token)

        assert _consent(deployed.client) == 401

    def test_a_workspace_beta_cookie_without_an_rca_session_is_refused(
        self, deployed: Deployed
    ) -> None:
        """The cookie alone never authorized a workspace scope's analysis again."""
        session = open_commercial_session(
            SqlSessionStore(deployed.stack.factory), owner_id=deployed.scope, now=NOW
        )
        deployed.client.cookies.set(BETA_COOKIE, session.session_id)

        assert _consent(deployed.client) == 401


class TestAStillMemberKeepsTheirAnalysisAcrossASwitch:
    def test_switching_organization_does_not_end_an_open_analysis(
        self, deployed: Deployed
    ) -> None:
        """Owner decision, 2026-09-26: the guard checks the analysis's own organization.

        `FR-030` refuses a *revoked* member. A member who is still in the organization and has
        merely made another one active keeps the analysis open in their other tab.
        """
        token = deployed.rca_token(deployed.member_account)
        deployed.enter_journey(token)
        elsewhere = OrganizationService(
            SqlOrganizationStore(deployed.stack.factory)
        ).create_organization("Globex", deployed.member_account, now=NOW)
        sessions = RcaSessionService(
            SqlRcaSessionStore(deployed.stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
        )
        OrganizationSwitcher(sessions, SqlOrganizationStore(deployed.stack.factory)).switch(
            token, elsewhere.organization_id, now=NOW
        )

        assert _consent(deployed.client) == 204


class TestInvitationSessionsAreUntouched:
    def test_an_invitation_session_needs_no_rca_session(self, deployed: Deployed) -> None:
        token = InvitationService(SqlSessionStore(deployed.stack.factory)).issue_invitation(
            expires_at=NOW + timedelta(days=7)
        )
        redeemed = deployed.client.post("/api/v1/beta/sessions/redeem", json={"token": token})
        assert redeemed.status_code == 201, redeemed.text

        assert _consent(deployed.client) == 204

    def test_redemption_is_not_refused_by_a_stale_workspace_cookie(
        self, deployed: Deployed
    ) -> None:
        """Redeeming mints a new design-partner session and acts in no workspace scope.

        A browser can still hold an earlier workspace cookie (seven-day `max_age`) after its RCA
        session ended or its membership was revoked. That cookie must not block an invitation.
        """
        workspace = open_commercial_session(
            SqlSessionStore(deployed.stack.factory), owner_id=deployed.scope, now=NOW
        )
        deployed.client.cookies.set(BETA_COOKIE, workspace.session_id)
        token = InvitationService(SqlSessionStore(deployed.stack.factory)).issue_invitation(
            expires_at=NOW + timedelta(days=7)
        )

        redeemed = deployed.client.post("/api/v1/beta/sessions/redeem", json={"token": token})

        assert redeemed.status_code == 201, redeemed.text
