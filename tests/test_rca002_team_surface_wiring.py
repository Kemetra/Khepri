"""The Team surface, driven through the **real** production builder (`RCA-002`).

**Why this module exists rather than another case in `test_r805_team_surface.py`.** That module
tests the surface, and it does so over a hand-wired `ShellServices` whose invitation double
implements `invitations_for_organization`. Every one of its cases passed while the deployed image
raised `AttributeError` on that very call, because `wiring.py` composed the field from
`InvitationService` alone -- which owns `issue`, `revoke` and `redeem` and no listing. A fixture
that supplies the method under test cannot see a deployment that does not.

So these cases build the app the way the image builds it: `build_stack` -> `build_shell_services`
-> `add_shell_routes`, with only the S3 client stubbed and SQLite standing in for Postgres. That
is `test_clerk_private_beta_e2e.py`'s method, used here for the same reason.

This is the second instance of one defect shape in one module. `#382` found `deletion=` unwired and
added the field; this is `invitations=` wired to an object that cannot answer the surface's read.
The guard against a third is `test_the_gateway_answers_every_verb_the_shell_calls`, which asserts
the composed object over the Protocol's whole surface rather than over the one verb that broke.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import URL

from khepri.rca.accounts import AccountService
from khepri.rca.invitations import InvitationOffer
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import Base as RcaBase
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from khepri.rca.switching import OrganizationSwitcher
from khepri.rra.persistence import Base as RraBase
from khepri.runtime.config import MasterKey, RuntimeSettings
from khepri.runtime.shell_api import SHELL_PREFIX, add_shell_routes
from khepri.runtime.wiring import (
    RuntimeClients,
    build_shell_services,
    build_stack,
)

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"
MASTER_KEY = MasterKey(material=b"k" * 32)


class AwsClientStub:
    """The one boundary stubbed. The Team surface reaches no object storage."""


@pytest.fixture
def deployment(tmp_path):
    """The real builders over SQLite, and one organization with an owner and a live session."""
    settings = RuntimeSettings(
        database_url=URL.create("sqlite+pysqlite", database=str(tmp_path / "team.db")),
        storage_endpoint="https://fra1.spaces.example",
        storage_region="fra1",
        bucket="khepri-content",
        master_key=MASTER_KEY,
        # No Clerk instance. The Team surface authenticates by the local commercial session
        # cookie, and a deployment without external identity still serves it -- so `None` is the
        # honest setting here rather than a stub that implies a trust relationship this test
        # never exercises.
        clerk=None,
    )
    stack = build_stack(settings, clients=RuntimeClients(s3=AwsClientStub()), clock=lambda: NOW)
    engine = stack.factory.kw["bind"]
    RcaBase.metadata.create_all(engine)
    RraBase.metadata.create_all(engine)

    owner = AccountService(SqlAccountStore(stack.factory)).create_account(
        "owner@example.test", CREDENTIAL
    )
    organization = OrganizationService(SqlOrganizationStore(stack.factory)).create_organization(
        "Team Wiring", owner.account_id, now=NOW
    )
    sessions = SessionService(SqlSessionStore(stack.factory), lifetime=timedelta(hours=12))
    token = sessions.create(owner.account_id, now=NOW)
    OrganizationSwitcher(sessions, SqlOrganizationStore(stack.factory)).switch(
        token, organization.organization_id, now=NOW
    )

    services = build_shell_services(stack)
    assert services is not None, "the commercial half is wired, so the shell exists"
    app = FastAPI()
    add_shell_routes(app, services=services, clock=lambda: NOW)
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, token)
    try:
        yield _Deployment(
            client=client,
            services=services,
            organization_id=organization.organization_id,
            account_id=owner.account_id,
            stack=stack,
        )
    finally:
        client.close()
        engine.dispose()


@dataclass(frozen=True)
class _Deployment:
    """What one built deployment offers these cases.

    A dataclass rather than a hand-written `__init__`, following `RuntimeStack` and every other
    grouped value in `wiring.py`: five fields spelled out as parameters scored `Excess Number of
    Function Arguments` on CodeScene's pre-flight, which is the same finding
    `InvitationService.issue`'s docstring records for the same shape.
    """

    client: TestClient
    services: Any
    organization_id: str
    account_id: str
    stack: Any

    def team(self, language: str = "en"):
        return self.client.get(f"{SHELL_PREFIX}/{language}/{self.organization_id}/team")


def test_the_team_surface_renders_from_the_production_wiring(deployment) -> None:
    """`RCA-002`: the Team destination answers on the app the real builders produce.

    This is the case that failed on `08d269f` with

        AttributeError: 'InvitationService' object has no attribute
        'invitations_for_organization'

    raised from `shell_api.py:_team_response`. It is a `500` on a shipped customer surface, and no
    existing test saw it because every one of them hand-wired the gateway.
    """
    response = deployment.team()

    assert response.status_code == 200, response.text
    assert "text/html" in response.headers["content-type"]


def test_the_team_surface_renders_in_both_languages(deployment) -> None:
    """The defect was language-independent, and so is the guard (`FR-043`)."""
    for language in ("en", "ar"):
        response = deployment.team(language)
        assert response.status_code == 200, f"{language}: {response.text}"


def test_the_gateway_answers_every_verb_the_shell_calls(deployment) -> None:
    """The whole `InvitationGateway` surface, on the object the builder actually composed.

    **Asserted by calling, not by `hasattr`.** A name check passes the moment anything carrying the
    attribute is attached, including an object whose method raises or reads another scope -- and it
    is exactly the assertion that would have let the original defect through had the wrong object
    happened to define the name. Each verb is driven for its effect instead.

    Redemption is deliberately absent: `InvitationGateway` does not declare it, because the shell
    may invite and un-invite and may not redeem. Asserting it here would widen the seam this test
    exists to pin.
    """
    gateway = deployment.services.invitations
    organization_id = deployment.organization_id

    assert gateway.invitations_for_organization(organization_id, now=NOW) == ()

    token = gateway.issue(
        InvitationOffer(
            organization_id=organization_id,
            intended_role="member",
            target_identity="Invitee@Example.test",
            issued_by=deployment.account_id,
        ),
        expires_at=NOW + timedelta(days=3),
        now=NOW,
    )
    assert token, "issuing returns the one-time token"

    held = gateway.invitations_for_organization(organization_id, now=NOW)
    assert len(held) == 1
    # The service canonicalizes the address at rest (`R4-01` §4). Reaching past it to the store
    # would have stored it as typed, and every later predicate would miss the row.
    assert held[0].target_identity == "invitee@example.test"

    gateway.revoke(
        organization_id,
        held[0].invitation_id,
        actor_account_id=deployment.account_id,
        now=NOW,
    )
    assert gateway.invitations_for_organization(organization_id, now=NOW) == ()


def test_revoking_an_invitation_another_organization_holds_refuses_uniformly(
    deployment,
) -> None:
    """`FR-025`: the composed gateway keeps the service's refusal rather than the store's `False`.

    The seam could have been built by calling `SqlInvitationStore.delete_open_invitation`
    directly -- it is one line shorter and it would pass the three tests above. It would also
    return `False` for an unreachable invitation where `FR-025` requires a refusal that cannot
    distinguish "does not exist" from "belongs to another organization". This case is what makes
    that shortcut fail, so the composition cannot be simplified into a defect.
    """
    from khepri.rca.errors import InvitationOperationFailed

    other = OrganizationService(SqlOrganizationStore(deployment.stack.factory)).create_organization(
        "Another", deployment.account_id, now=NOW
    )
    gateway = deployment.services.invitations
    gateway.issue(
        InvitationOffer(
            organization_id=other.organization_id,
            intended_role="member",
            target_identity="elsewhere@example.test",
            issued_by=deployment.account_id,
        ),
        expires_at=NOW + timedelta(days=3),
        now=NOW,
    )
    held = gateway.invitations_for_organization(other.organization_id, now=NOW)
    assert len(held) == 1

    with pytest.raises(InvitationOperationFailed):
        gateway.revoke(
            deployment.organization_id,
            held[0].invitation_id,
            actor_account_id=deployment.account_id,
            now=NOW,
        )

    # Still held by the organization that owns it: the refusal changed nothing.
    assert len(gateway.invitations_for_organization(other.organization_id, now=NOW)) == 1


def test_the_listing_never_crosses_organizations(deployment) -> None:
    """`FR-023`: the listing is scoped by `organization_id`, so it is no enumeration oracle."""
    other = OrganizationService(SqlOrganizationStore(deployment.stack.factory)).create_organization(
        "Another", deployment.account_id, now=NOW
    )
    gateway = deployment.services.invitations
    gateway.issue(
        InvitationOffer(
            organization_id=other.organization_id,
            intended_role="member",
            target_identity="elsewhere@example.test",
            issued_by=deployment.account_id,
        ),
        expires_at=NOW + timedelta(days=3),
        now=NOW,
    )

    assert gateway.invitations_for_organization(deployment.organization_id, now=NOW) == ()
    assert len(gateway.invitations_for_organization(other.organization_id, now=NOW)) == 1
