"""Issuing and revoking invitations from the team surface (`R8-05b`).

Authorized by `RCA-002`. These are the shell's first **mutating** actions; every earlier surface
only read.

**The route is the only thing enforcing owner-only.** `InvitationService.issue` and `.revoke` take
`actor_account_id` for attribution and check no authority of their own -- both docstrings say so --
so a member reaching the verb directly succeeds. `R6-04` put the check in the gate deliberately,
which means a shell route calling `for_request` instead of `require_owner` would hand every member
the ability to invite.

**The DENY cases assert an effect, not an exception.** `TestTheInvitationRows` in the authorization
matrix records why: a `pytest.raises` on the gate alone would hold even if the verb ran
unconditionally afterwards. So a refused issuance asserts that no invitation exists, and a refused
revocation asserts the target is still open.

**The token is shown once and never again.** `issue` returns it and only a salted hash persists, so
the surface renders it immediately and the pending list cannot show it. That is a domain constraint
the UI obeys, not a design preference.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.runtime.shell_api import (
    INVITATION_LIFETIME,
    SHELL_PREFIX,
    ShellServices,
    add_shell_routes,
)

NOW = datetime(2026, 8, 22, tzinfo=UTC)


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    """Records which gate was used, because that is the property under test.

    Both methods exist so a `require_owner`->`for_request` mutant dies on an assertion rather than
    an `AttributeError`. A mutant killed for the wrong reason proves nothing.
    """

    def __init__(
        self,
        context: _Context | None = None,
        raises: Exception | None = None,
        owner_raises: Exception | None = None,
    ) -> None:
        self._context = context or _Context("acct-1", "org-acme")
        self._raises = raises
        self._owner_raises = owner_raises
        self.calls: list[tuple[str, str | None]] = []

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        self.calls.append(("for_request", organization_id))
        if self._raises is not None:
            raise self._raises
        return self._context

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:
        self.calls.append(("require_owner", organization_id))
        if self._owner_raises is not None:
            raise self._owner_raises
        if self._raises is not None:
            raise self._raises
        return self._context


@dataclass
class _Invitation:
    invitation_id: str
    target_identity: str
    intended_role: str


class _StubInvitations:
    """Records every call, so scope is asserted on what was asked, not on what came back."""

    def __init__(self, pending: list[_Invitation] | None = None) -> None:
        self.pending = pending or []
        self.issued: list[tuple[str, str, str]] = []
        self.revoked: list[tuple[str, str]] = []
        self.listed: list[str] = []

    def invitations_for_organization(
        self, organization_id: str, *, now: object = None
    ) -> tuple[_Invitation, ...]:
        self.listed.append(organization_id)
        return tuple(self.pending)

    def issue(self, offer: object, *, expires_at: datetime, now: datetime) -> str:
        self.issued.append(
            (offer.organization_id, offer.target_identity, offer.intended_role)
        )
        self.expires_at = expires_at
        return "inv_a-one-time-token"

    def revoke(
        self,
        organization_id: str,
        invitation_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> None:
        self.revoked.append((organization_id, invitation_id))


class _StubOrganizations:
    def __init__(self, members: list[object] | None = None) -> None:
        self._members = members or []

    def organizations_for_account(self, account_id: str) -> list[object]:
        return [object()]

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return self._members


def _shell(
    *,
    context: _Context | None = None,
    raises: Exception | None = None,
    owner_raises: Exception | None = None,
    invitations: _StubInvitations | None = None,
    resolver: _StubResolver | None = None,
) -> tuple[TestClient, _StubInvitations, _StubResolver]:
    resolver = resolver or _StubResolver(context, raises, owner_raises)
    invitations = invitations or _StubInvitations()
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=resolver,
            organizations=_StubOrganizations(),
            invitations=invitations,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client, invitations, resolver


class TestTheOwnerGate:
    """The route enforces owner-only, because neither verb does."""

    def test_issuing_goes_through_require_owner(self) -> None:
        client, _, resolver = _shell()

        client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert ("require_owner", "org-acme") in resolver.calls
        assert not any(call == "for_request" for call, _ in resolver.calls)

    def test_revoking_goes_through_require_owner(self) -> None:
        client, _, resolver = _shell()

        client.post(f"{SHELL_PREFIX}/en/org-acme/team/invitations/inv-1/revoke")

        assert ("require_owner", "org-acme") in resolver.calls

    def test_a_member_cannot_issue_and_no_invitation_results(self) -> None:
        """The DENY effect, not merely the exception.

        Asserting `raises` alone would hold even if the verb ran unconditionally afterwards.
        """
        client, invitations, _ = _shell(owner_raises=ScopeAccessDenied())

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert response.status_code == 404
        assert invitations.issued == []

    def test_a_member_cannot_revoke_and_the_invitation_survives(self) -> None:
        client, invitations, _ = _shell(owner_raises=ScopeAccessDenied())

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations/inv-1/revoke"
        )

        assert response.status_code == 404
        assert invitations.revoked == []


class TestScopeIsNamedAtTheGate:
    """`FR-024`: the target organization is named to `require_owner`, which resolves the actor's
    live role in *that* organization before permitting anything.

    This is deliberately not "the path is ignored". `require_owner` requires a target precisely so
    the caller must name one -- "the organization that was authorized is the one in the caller's
    hand" -- and a path naming an organization the actor does not own is refused at the gate.
    """

    def test_the_gate_is_given_the_organization_the_request_names(self) -> None:
        client, _, resolver = _shell(context=_Context("acct-1", "org-acme"))

        client.post(
            f"{SHELL_PREFIX}/en/org-somewhere-else/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert ("require_owner", "org-somewhere-else") in resolver.calls

    def test_a_foreign_organization_is_refused_and_nothing_is_issued(self) -> None:
        """The effect of that gate refusing, not merely that it was called."""
        client, invitations, _ = _shell(owner_raises=ScopeAccessDenied())

        response = client.post(
            f"{SHELL_PREFIX}/en/org-somewhere-else/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert response.status_code == 404
        assert invitations.issued == []

    def test_revocation_writes_to_the_organization_the_gate_authorized(self) -> None:
        client, invitations, _ = _shell(context=_Context("acct-1", "org-acme"))

        client.post(f"{SHELL_PREFIX}/en/org-acme/team/invitations/inv-1/revoke")

        assert invitations.revoked == [("org-acme", "inv-1")]


class TestTheToken:
    """`issue` returns the secret once; only a salted hash persists."""

    def test_the_token_is_rendered_after_issuing(self) -> None:
        client, _, _ = _shell()

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert response.status_code == 200
        assert "inv_a-one-time-token" in response.text

    def test_the_pending_list_carries_no_token(self) -> None:
        """It could not, and the surface must not imply otherwise."""
        client, _, _ = _shell(
            invitations=_StubInvitations(
                pending=[_Invitation("inv-1", "invitee@example.test", "member")]
            )
        )

        response = client.get(f"{SHELL_PREFIX}/en/org-acme/team")

        assert "invitee@example.test" in response.text
        assert "inv_a-one-time-token" not in response.text


class TestTheExpiry:
    """The domain refuses a default lifetime; the shell supplies one."""

    def test_it_sends_a_seven_day_expiry(self) -> None:
        client, invitations, _ = _shell()

        client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )

        assert invitations.expires_at == NOW + INVITATION_LIFETIME
        assert timedelta(days=7) == INVITATION_LIFETIME


class TestTheRole:
    """`FR-015`: exactly two roles, and a request cannot name a third."""

    def test_an_unknown_role_is_refused_and_nothing_is_issued(self) -> None:
        client, invitations, _ = _shell()

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "superuser"},
        )

        assert response.status_code == 404
        assert invitations.issued == []
