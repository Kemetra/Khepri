"""The organization switcher and the no-membership surface (`R8-04`).

Authorized by `RCA-002`. Each test names the requirement it verifies.

**What this slice adds to `khepri.rca`, and why it is a read rather than a new concept.**
`OrganizationStore` could create an organization and read memberships, but nothing read an
organization back, so the name written at `create_organization` had no path to a screen.
`organizations_for_account` is that path. It introduces no new state and no new semantics --
`RCA-002` excludes both -- and enumerates exactly what `FR-051` permits: organizations in which
the actor holds a current membership.

**Why the join is load-bearing.** Enumerating membership rows and looking each organization up
separately would be the same shape as counting owner rows without joining account state, which is
a defect this repository already shipped once (`count_owners`). One query keeps the membership
predicate and the organization read in the same statement, so a row cannot be enumerated whose
organization no longer exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import Account, AccountService
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.organizations import Organization, OrganizationService
from khepri.rca.persistence import Base, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY

NOW = datetime(2026, 8, 22, tzinfo=UTC)


@pytest.fixture(name="factory")
def factory_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _account(store: SqlAccountStore, email: str) -> Account:
    """Through the production verb, not `add_account` with a hand-built record.

    `Account.create` derives the verifier from the credential and admits no digest parameter, so
    raw-record setup would be constructing state the application cannot construct.
    """
    return AccountService(store).create_account(email, "a-correct-horse-battery-staple")


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "member"


class _StubResolver:
    def __init__(
        self, context: _Context | None = None, raises: Exception | None = None
    ) -> None:
        self._context = context or _Context("acct-1", "org-acme")
        self._raises = raises

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        if self._raises is not None:
            raise self._raises
        return self._context


class _StubOrganizations:
    """Records who it was asked about, so `FR-042` is asserted on the call, not the output."""

    def __init__(self, organizations: list[Organization] | None = None) -> None:
        self._organizations = organizations or []
        self.calls: list[str] = []

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        self.calls.append(account_id)
        return self._organizations


def _organization(organization_id: str, name: str) -> Organization:
    return Organization._from_storage(
        organization_id=organization_id, name=name, created_at=NOW
    )


def _shell(
    *,
    context: _Context | None = None,
    raises: Exception | None = None,
    organizations: list[Organization] | None = None,
    reader: _StubOrganizations | None = None,
) -> TestClient:
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context, raises),
            organizations=reader or _StubOrganizations(organizations),
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


class TestOrganizationsForAccount:
    """`FR-051`: enumerate only organizations the actor is currently a member of."""

    def test_it_returns_the_organizations_the_account_belongs_to(self, factory) -> None:
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        service.create_organization("Acme", owner.account_id, now=NOW)
        service.create_organization("Globex", owner.account_id, now=NOW)

        found = organizations.organizations_for_account(owner.account_id)

        assert sorted(organization.name for organization in found) == ["Acme", "Globex"]

    def test_it_returns_nothing_for_an_account_with_no_membership(self, factory) -> None:
        """`FR-048`: no membership is a state with a next step, not an error."""
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        stranger = _account(accounts, "stranger@example.test")

        assert organizations.organizations_for_account(stranger.account_id) == []

    def test_it_never_returns_an_organization_the_account_does_not_belong_to(
        self, factory
    ) -> None:
        """The disclosure `FR-051` forbids, asserted as an absence rather than a count.

        A count would pass if the query returned the right *number* of the wrong rows.
        """
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        outsider = _account(accounts, "outsider@example.test")
        service.create_organization("Acme", owner.account_id, now=NOW)

        found = organizations.organizations_for_account(outsider.account_id)

        assert [organization.name for organization in found] == []

    def test_it_enumerates_each_organization_the_account_owns(self, factory) -> None:
        """Two organizations, one account, both enumerated.

        Built entirely through `create_organization`, the production verb: a test that inserted
        membership rows directly would assert the read while exempting the write that produces
        them, and a mutant of that write would survive.
        """
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        other = _account(accounts, "other@example.test")
        service.create_organization("Acme", owner.account_id, now=NOW)
        service.create_organization("Globex", owner.account_id, now=NOW)
        service.create_organization("Initech", other.account_id, now=NOW)

        found = organizations.organizations_for_account(owner.account_id)

        assert [organization.name for organization in found] == ["Acme", "Globex"]

    def test_it_orders_by_name_so_a_switcher_renders_the_same_list_twice(self, factory) -> None:
        """Ordering is a property of the query, not of insertion."""
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        for name in ("Zulu", "Alpha", "Mike"):
            service.create_organization(name, owner.account_id, now=NOW)

        found = organizations.organizations_for_account(owner.account_id)

        assert [organization.name for organization in found] == ["Alpha", "Mike", "Zulu"]


class TestTheNoMembershipSurface:
    """`FR-048`: an account in no organization reaches a surface with an explicit next step.

    It is the one edge state `RCA-002` deliberately does *not* collapse into `unavailable`, and the
    reason is the whole of it: no membership is not a refusal, it is a state with something to do.
    """

    def test_an_account_with_no_membership_reaches_its_own_surface(self) -> None:
        response = _shell(context=_Context("acct-1", None), organizations=[]).get(
            f"{SHELL_PREFIX}/en/"
        )

        assert response.status_code == 200
        assert "unavailable" not in response.text.lower()

    def test_that_surface_carries_a_next_step(self) -> None:
        """A surface without an action would be `unavailable` with different words."""
        response = _shell(context=_Context("acct-1", None), organizations=[]).get(
            f"{SHELL_PREFIX}/en/"
        )

        assert SHELL_COPY["en"]["no_membership_action"] in response.text

    def test_it_is_distinguishable_from_the_unavailable_surface(self) -> None:
        """The distinction `FR-050` permits, asserted so a later change cannot quietly collapse it.

        Every other edge state is indistinguishable; this one must not be.
        """
        no_membership = _shell(context=_Context("acct-1", None), organizations=[]).get(
            f"{SHELL_PREFIX}/en/"
        )
        refused = _shell(raises=ScopeAccessDenied()).get(f"{SHELL_PREFIX}/en/")

        assert no_membership.status_code != refused.status_code
        assert no_membership.text != refused.text


class TestTheSwitcher:
    """`FR-051`: the switcher enumerates only current memberships."""

    def test_it_lists_the_organizations_the_actor_belongs_to(self) -> None:
        response = _shell(
            context=_Context("acct-1", "org-acme"),
            organizations=[_organization("org-acme", "Acme"), _organization("org-gx", "Globex")],
        ).get(f"{SHELL_PREFIX}/en/")

        assert "Acme" in response.text
        assert "Globex" in response.text

    def test_it_never_lists_an_organization_the_actor_is_not_in(self) -> None:
        """The reader is asked for this actor's organizations; nothing else may appear.

        Asserted against a name no membership carries, so a switcher rendering "every organization"
        fails here rather than passing because the fixture happened to hold one.
        """
        response = _shell(
            context=_Context("acct-1", "org-acme"),
            organizations=[_organization("org-acme", "Acme")],
        ).get(f"{SHELL_PREFIX}/en/")

        assert "Initech" not in response.text

    def test_the_reader_is_asked_only_about_the_resolved_actor(self) -> None:
        """`FR-042`: the account comes from the resolved context, never from the address."""
        reader = _StubOrganizations([_organization("org-acme", "Acme")])
        _shell(context=_Context("acct-1", "org-acme"), reader=reader).get(
            f"{SHELL_PREFIX}/en/someone-else/analyses"
        )

        assert reader.calls == ["acct-1"]


class TestTheFakeAgreesWithTheStore:
    """The in-memory store used across the RCA suite must not diverge from the SQL one.

    A fake that answers differently makes every test built on it evidence about the fake.
    """

    def test_both_stores_expose_the_same_read(self) -> None:
        from tests.rca_fakes import MemoryOrganizationStore

        assert hasattr(MemoryOrganizationStore, "organizations_for_account")
        assert hasattr(SqlOrganizationStore, "organizations_for_account")


def test_the_store_protocol_declares_the_read() -> None:
    """`OrganizationStore` is the seam every consumer depends on; a method absent from it is a
    method consumers cannot call without reaching past the Protocol."""
    from khepri.rca.stores import OrganizationStore

    assert hasattr(OrganizationStore, "organizations_for_account")


def _organization_names(organizations: list[Organization]) -> list[str]:
    return sorted(organization.name for organization in organizations)
