"""#594: after a revocation the reader selects another organization, inside the same session.

The owner's 2026-09-26 decision: the session may remain alive, and "the user must select or resolve
to another organization for which they still have valid membership before organization-scoped work
continues". Before this slice no route switched the active organization inside a session. The
chooser's rows linked to `/{language}/{organization}/{entry}`, which only compares the address with
the *active* organization, so once that one was revoked every row landed on `unavailable`, and its
exit led back to the chooser. The reader looped until they signed in again.

**The switch is a POST** (`RCA-002` FR-051a), made through `OrganizationSwitcher.switch`, which
admits only a current membership (`RCA-001` FR-029). A GET that changed the active organization is
a GET a browser may prefetch.

**Driven through `build_web_app`**, with the membership revoked through the real service.
"""

from __future__ import annotations

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.rca.session_service import SessionService as RcaSessionService
from khepri.runtime.external_auth_api import KHEPRI_SESSION_LIFETIME
from tests.i594_support import RCA_COOKIE, Deployed, deployed_fixture  # noqa: F401
from tests.w104_support import CREDENTIAL, NOW


def _second_organization(deployed: Deployed) -> str:
    """An organization the member owns outright, so revocation elsewhere leaves them one."""
    return (
        OrganizationService(SqlOrganizationStore(deployed.stack.factory))
        .create_organization("Globex", deployed.member_account, now=NOW)
        .organization_id
    )


def _revoked_with_another(deployed: Deployed) -> str:
    other = _second_organization(deployed)
    deployed.client.cookies.set(RCA_COOKIE, deployed.rca_token(deployed.member_account))
    deployed.revoke_member()
    return other


class TestTheChooserSwitches:
    def test_a_revoked_reader_switches_to_an_organization_they_still_belong_to(
        self, deployed: Deployed
    ) -> None:
        other = _revoked_with_another(deployed)

        switched = deployed.client.post(f"/app/en/{other}/switch", follow_redirects=False)

        assert switched.status_code == 303
        assert switched.headers["location"] == f"/app/en/{other}/overview"
        assert deployed.client.get(f"/app/en/{other}/overview").status_code == 200

    def test_the_chooser_offers_the_switch_for_every_organization_but_the_active_one(
        self, deployed: Deployed
    ) -> None:
        other = _revoked_with_another(deployed)

        chooser = deployed.client.get("/app/en/").text

        assert f'action="/app/en/{other}/switch"' in chooser
        assert f'action="/app/en/{deployed.organization_id}/switch"' not in chooser, (
            "the revoked organization is not listed at all (FR-051)"
        )


def _active_organization(deployed: Deployed, token: str) -> str | None:
    """What the stored session names, read back through the session service."""
    sessions = RcaSessionService(
        SqlRcaSessionStore(deployed.stack.factory), lifetime=KHEPRI_SESSION_LIFETIME
    )
    return sessions.resolve(token, now=NOW).active_organization_id


def _strangers_organization(deployed: Deployed) -> str:
    stranger = AccountService(SqlAccountStore(deployed.stack.factory)).create_account(
        "stranger@example.test", CREDENTIAL
    )
    return (
        OrganizationService(SqlOrganizationStore(deployed.stack.factory))
        .create_organization("Initech", stranger.account_id, now=NOW)
        .organization_id
    )


class TestTheSwitchAdmitsOnlyACurrentMembership:
    def test_switching_back_into_the_revoked_organization_is_refused(
        self, deployed: Deployed
    ) -> None:
        _revoked_with_another(deployed)

        refused = deployed.client.post(
            f"/app/en/{deployed.organization_id}/switch", follow_redirects=False
        )

        assert refused.status_code == 404
        assert "location" not in refused.headers

    def test_a_refused_switch_leaves_the_active_organization_unchanged(
        self, deployed: Deployed
    ) -> None:
        """`FR-051a`: read back from the stored session, not inferred from a page."""
        token = deployed.rca_token(deployed.member_account)
        deployed.client.cookies.set(RCA_COOKIE, token)

        refused = deployed.client.post(
            f"/app/en/{_strangers_organization(deployed)}/switch", follow_redirects=False
        )

        assert refused.status_code == 404
        assert _active_organization(deployed, token) == deployed.organization_id

    def test_every_refusal_is_the_same_page(self, deployed: Deployed) -> None:
        """No session, a non-member, and an unknown organization are indistinguishable."""
        anonymous = deployed.client.post(
            f"/app/en/{deployed.organization_id}/switch", follow_redirects=False
        )
        deployed.client.cookies.set(RCA_COOKIE, deployed.rca_token(deployed.member_account))
        stranger = deployed.client.post(
            f"/app/en/{_strangers_organization(deployed)}/switch", follow_redirects=False
        )
        unknown = deployed.client.post("/app/en/org_no_such/switch", follow_redirects=False)

        assert anonymous.status_code == stranger.status_code == unknown.status_code == 404
        assert anonymous.content == stranger.content == unknown.content

    def test_a_cross_site_switch_is_refused(self, deployed: Deployed) -> None:
        token = deployed.rca_token(deployed.member_account)
        deployed.client.cookies.set(RCA_COOKIE, token)
        other = _second_organization(deployed)

        forged = deployed.client.post(
            f"/app/en/{other}/switch",
            headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
            follow_redirects=False,
        )

        assert forged.status_code == 403
        assert _active_organization(deployed, token) == deployed.organization_id
