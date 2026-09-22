"""A governed refusal raised *after* a shell gate reaches the uniform surface, not a 500 (#520).

Two routes checked their actor at a gate and then called a service that can refuse again with no
`except` around it:

- **A-06.** `issue_invitation` passes `require_owner`, then `InvitationService.issue` raises
  `InvitationOperationFailed` whenever the store refuses the write. The sibling
  `revoke_invitation` answers that same exception with the one unavailable surface (`RCA-001`
  `FR-025`); issuing answered it with a bare 500.
- **A-08.** The decision surface passes `_member_or_none`, then every view read re-resolves the
  scope through `IsolationService.resolve_scope`. A membership revoked between the two raised
  `ScopeAccessDenied` into a 500. The actor is by then not a member, which `RCA-002` `FR-050`
  puts on the same indistinguishable surface the gate itself renders.

Both are asserted against the **sibling's own response** -- status *and* body -- rather than a
status code alone, because "the uniform refusal" means indistinguishable from the other causes,
and a 404 carrying different copy would pass a status check while disclosing the cause.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import SCOPE_FAILURE, ScopeAccessDenied
from khepri.rca.invitation_service import InvitationService
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.persistence import SqlFactPackageRepository
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from tests.test_r805b_invitation_management import NOW, _StubOrganizations, _StubResolver
from tests.w104_support import Member
from tests.w104b_support import Journey, journey
from tests.w106_support import HTTPS, completed_run, isolation, services_over
from tests.w110_support import ScopedResolver, two_members

# --- A-06: issuing an invitation the store refuses -------------------------------------------


class _RefusingInvitationStore:
    """An invitation store that refuses every write, as a CHECK or FK violation does.

    Driven through the real `InvitationService`, so the exception reaching the route is the one
    production raises rather than one a stub chose.
    """

    def __init__(self) -> None:
        self.offered = 0

    def add_invitation(self, invitation: object) -> bool:
        self.offered += 1
        return False

    def delete_open_invitation(
        self, organization_id: str, invitation_id: str, *, now: object
    ) -> bool:
        return False


def _owner_shell() -> tuple[TestClient, _RefusingInvitationStore]:
    store = _RefusingInvitationStore()
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(),
            organizations=_StubOrganizations(),
            invitations=InvitationService(store),
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app, raise_server_exceptions=False)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client, store


class TestIssuingARefusedInvitation:
    def test_a_refused_write_is_the_revoke_routes_refusal_not_a_500(self) -> None:
        client, store = _owner_shell()

        issued = client.post(
            f"{SHELL_PREFIX}/en/org-acme/team/invitations",
            data={"email": "invitee@example.test", "role": "member"},
        )
        revoked = client.post(f"{SHELL_PREFIX}/en/org-acme/team/invitations/inv-1/revoke")

        assert store.offered == 1, "the write must actually have been attempted and refused"
        assert issued.status_code == 404
        assert (issued.status_code, issued.text) == (revoked.status_code, revoked.text)
        assert "inv_" not in issued.text, "a refused issuance shows no token"


# --- A-08: a membership revoked between the gate and the view reads --------------------------


class _RevokedAfter:
    """The real scope door, until the membership is revoked after `allowed` resolutions.

    Shared by the selector's read and every view read, so the order of calls is the production
    order: call one is `_sources_for`'s, call two is the first view read's.
    """

    def __init__(self, inner: Any, *, allowed: int) -> None:
        self._inner = inner
        self._allowed = allowed
        self.calls = 0

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        self.calls += 1
        if self.calls > self._allowed:
            raise ScopeAccessDenied(SCOPE_FAILURE)
        return self._inner.resolve_scope(account_id, organization_id)


def _decision_shell(j: Journey, who: Member, door: _RevokedAfter) -> TestClient:
    base = services_over(j, who)
    context = base.resolver.for_request("", organization_id=None, now=None)
    services = ShellServices(
        resolver=ScopedResolver(context, organization_id=who.organization_id),
        organizations=base.organizations,
        records=base.records,
        isolation=door,
        provenance=base.provenance,
        decisions=SemanticQueryActions(
            isolation=door,
            sources=j.w.store,
            port=SemanticViewAdapter(SqlFactPackageRepository(j.w.factory)),
        ),
    )
    app = FastAPI()
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS, raise_server_exceptions=False)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


class TestAMembershipRevokedMidRequest:
    def test_the_page_is_the_gates_own_unavailable_surface(self) -> None:
        world = journey()
        who, other = two_members(world)
        run, _job, _session = completed_run(world, who)
        door = _RevokedAfter(isolation(world), allowed=1)
        client = _decision_shell(world, who, door)

        revoked = client.get(f"{SHELL_PREFIX}/en/{who.organization_id}/decisions/{run.run_id}")
        # The gate's own refusal: an address naming an organization that is not the session's.
        gate = client.get(f"{SHELL_PREFIX}/en/{other.organization_id}/decisions/{run.run_id}")

        assert door.calls >= 2, "the selector's resolution must succeed and a view read refuse"
        assert revoked.status_code == 404
        assert (revoked.status_code, revoked.text) == (gate.status_code, gate.text)
        assert "decision-card" not in revoked.text
        assert who.organization_id not in revoked.text

    def test_an_unrevoked_member_still_reads_the_page(self) -> None:
        """The control: the same wiring with no revocation renders the surface."""
        world = journey()
        who, _other = two_members(world)
        run, _job, _session = completed_run(world, who)
        door = _RevokedAfter(isolation(world), allowed=10_000)

        page = _decision_shell(world, who, door).get(
            f"{SHELL_PREFIX}/en/{who.organization_id}/decisions/{run.run_id}"
        )

        assert page.status_code == 200
        assert "decision-card" in page.text
