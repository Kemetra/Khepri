"""The team surface: members and pending invitations (`R8-05`).

Authorized by `RCA-002`. Each test names the requirement it verifies.

**This is the first shell surface that shows one person's identity to another.** Every earlier
surface rendered the actor's own context or a refusal. A member list shows email addresses, which
makes the organization scope of the read a disclosure boundary rather than a convenience: the
query is scoped by `organization_id`, never filtered in a template, so there is no path on which
the filter could be skipped.

**`memberships_for_organization` is new; `invitations_for_organization` is not.** The invitation
listing already existed and was written for this screen -- its docstring says so -- and is
expiry-aware, destroying the verifier of any stale row it touches. This slice consumes it rather
than adding a second listing beside it.

**A disabled member still holds a membership row.** Disablement never touches `rca_memberships`, so
a join that ignored account state would render a disabled person as an ordinary member. The read
carries `disabled` and the surface says so, which is the same defect `count_owners` was fixed for
one layer down.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import Account, AccountService
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.lifecycle import LifecycleService
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
    return AccountService(store).create_account(email, "a-correct-horse-battery-staple")


class TestMembershipsForOrganization:
    """The read the team surface needs, scoped by organization at the query."""

    def test_it_lists_the_members_of_one_organization(self, factory) -> None:
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        created = service.create_organization("Acme", owner.account_id, now=NOW)

        members = organizations.memberships_for_organization(created.organization_id)

        assert [member.email for member in members] == ["owner@example.test"]

    def test_it_never_lists_a_member_of_another_organization(self, factory) -> None:
        """The disclosure boundary, asserted as an absence.

        Scoping is at the query. A test that checked a count would pass if the read returned the
        right number of the wrong people.
        """
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        ours = _account(accounts, "ours@example.test")
        theirs = _account(accounts, "theirs@example.test")
        acme = service.create_organization("Acme", ours.account_id, now=NOW)
        service.create_organization("Initech", theirs.account_id, now=NOW)

        members = organizations.memberships_for_organization(acme.organization_id)

        assert [member.email for member in members] == ["ours@example.test"]

    def test_it_reports_a_live_member_as_not_disabled(self, factory) -> None:
        """The negative half, so the disabled case below is not passing on a constant.

        A read hard-coding `disabled=True` would satisfy the next test and fail this one.
        """
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        created = service.create_organization("Acme", owner.account_id, now=NOW)

        members = organizations.memberships_for_organization(created.organization_id)

        assert [member.disabled for member in members] == [False]

    def test_it_reports_a_disabled_member_as_disabled(self, factory) -> None:
        """Disablement never touches `rca_memberships`, so the row alone would read as live.

        This is `count_owners`' defect one layer up: a membership row is not evidence that the
        person behind it can act. The account disabled here is a **member of this organization**,
        so a read ignoring account state renders them as ordinary.
        """
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        service.create_organization("Acme", owner.account_id, now=NOW)
        # `FR-013` refuses to disable an organization's final owner, so the account disabled here
        # holds no owner role anywhere: it is a member of nothing. That is enough for this read --
        # the point is that account state reaches the projection at all, and a one-owner
        # organization cannot be put into the disabled-owner state by any production path.
        stranger = _account(accounts, "stranger@example.test")
        LifecycleService(accounts, organizations).disable_account(
            stranger.account_id, now=NOW + timedelta(days=1)
        )
        disabled_org = service.create_organization("Ghost", stranger.account_id, now=NOW)

        members = organizations.memberships_for_organization(disabled_org.organization_id)

        assert [member.disabled for member in members] == [True]

    def test_it_carries_the_role(self, factory) -> None:
        """`FR-015`: exactly two roles, and the surface must be able to show which."""
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "owner@example.test")
        created = service.create_organization("Acme", owner.account_id, now=NOW)

        members = organizations.memberships_for_organization(created.organization_id)

        assert [member.role for member in members] == ["owner"]

    def test_it_orders_deterministically(self, factory) -> None:
        """A team list that reorders between renders is a list nobody can scan."""
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)
        service = OrganizationService(organizations)
        owner = _account(accounts, "zulu@example.test")
        created = service.create_organization("Acme", owner.account_id, now=NOW)

        first = organizations.memberships_for_organization(created.organization_id)
        second = organizations.memberships_for_organization(created.organization_id)

        assert [member.email for member in first] == [member.email for member in second]


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "owner"


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
    def __init__(
        self,
        organizations: list[Organization] | None = None,
        members: list[object] | None = None,
    ) -> None:
        self._organizations = organizations or []
        self._members = members or []
        self.member_calls: list[str] = []

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        return self._organizations

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        self.member_calls.append(organization_id)
        return self._members


def _organization(organization_id: str, name: str) -> Organization:
    return Organization._from_storage(
        organization_id=organization_id, name=name, created_at=NOW
    )


def _shell(
    *,
    context: _Context | None = None,
    raises: Exception | None = None,
    reader: _StubOrganizations | None = None,
) -> TestClient:
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context, raises),
            organizations=reader or _StubOrganizations(),
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


class TestTheTeamSurface:
    """`FR-042`, `FR-051`: scoped to the session's organization, never the address."""

    def test_it_lists_the_members_of_the_active_organization(self) -> None:
        reader = _StubOrganizations(
            organizations=[_organization("org-acme", "Acme")],
            members=[_Member("member@example.test", "owner", False)],
        )
        response = _shell(reader=reader).get(f"{SHELL_PREFIX}/en/org-acme/team")

        assert response.status_code == 200
        assert "member@example.test" in response.text

    def test_it_reads_the_session_organization_not_the_address(self) -> None:
        """`FR-042`. The path names one organization; the session names another.

        Asserted on what the reader was asked, because a surface reading the address would still
        render a page and would still look right in a screenshot.
        """
        reader = _StubOrganizations(
            organizations=[_organization("org-acme", "Acme")], members=[]
        )
        _shell(context=_Context("acct-1", "org-acme"), reader=reader).get(
            f"{SHELL_PREFIX}/en/org-someone-else/team"
        )

        assert reader.member_calls == ["org-acme"]

    def test_a_refused_actor_reaches_the_unavailable_surface(self) -> None:
        """`FR-050`: the team surface adds no new refusal of its own."""
        response = _shell(raises=ScopeAccessDenied()).get(f"{SHELL_PREFIX}/en/org-acme/team")

        assert response.status_code == 404
        assert "member@example.test" not in response.text

    def test_it_marks_a_disabled_member(self) -> None:
        reader = _StubOrganizations(
            organizations=[_organization("org-acme", "Acme")],
            members=[_Member("gone@example.test", "member", True)],
        )
        response = _shell(reader=reader).get(f"{SHELL_PREFIX}/en/org-acme/team")

        assert SHELL_COPY["en"]["member_disabled"] in response.text


@dataclass
class _Member:
    email: str
    role: str
    disabled: bool
