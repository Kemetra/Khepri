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
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import Account, AccountService
from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, Organization, OrganizationService
from khepri.rca.persistence import Base, SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY
from tests.rca_lifecycle_support import (
    CREDENTIAL,
    EMAIL,
    OTHER_EMAIL,
    grant_membership,
    two_owner_organization,
)

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


def _team_with_a_purged_member_and_an_orphan(factory):
    """Two live owners, one purged member (email `NULL`), and one membership with no account.

    `factory=None` builds it over the fakes. The r805 fixture enforces no foreign keys, so the
    orphan row can exist on SQLite too, and the inner join is what must leave it out.
    """
    stack = two_owner_organization(factory)
    organization_id = stack.organization.organization_id
    purged = AccountService(stack.accounts).create_account("aaa@example.test", CREDENTIAL)
    grant_membership(stack, purged.account_id, MEMBER_ROLE, factory=factory)
    stack.lifecycle.disable_account(purged.account_id, now=NOW)
    assert stack.accounts.purge_if_still_eligible(purged.account_id, NOW + timedelta(days=1))
    grant_membership(stack, "acc_orphan", MEMBER_ROLE, factory=factory)
    return stack.organizations.memberships_for_organization(organization_id)


class TestTheFakeListsMembersLikeTheStore:
    """`#529` `T-11`: the fake and the SQL store must list one team identically.

    PostgreSQL sorts `NULL` last in ascending order and SQLite sorts it first, so an implicit
    `ORDER BY email` put a purged member at opposite ends on the two engines, and the fake sorted
    `NULL` as `""` -- first -- while also listing memberships with no account, which the SQL inner
    join never returns. The order is now explicit (`nulls_last()`), and the fake mirrors both.
    """

    @pytest.mark.parametrize("backend", ["sql", "memory"])
    def test_a_purged_member_sorts_last_and_an_orphan_is_absent(self, factory, backend) -> None:
        members = _team_with_a_purged_member_and_an_orphan(
            factory if backend == "sql" else None
        )

        assert [member.email for member in members] == [OTHER_EMAIL, EMAIL, None]
        assert "acc_orphan" not in {member.account_id for member in members}


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
    invitations: object | None = None,
) -> TestClient:
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context, raises),
            organizations=reader or _StubOrganizations(),
            invitations=invitations,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


class _ListingInvitations:
    """An invitation gateway that answers the expiry question the real store asks.

    `SqlInvitationStore.invitations_for_organization` is expiry-aware (`#217`):
    it evaluates `_expired(row, now)` -- `stored <= now` -- for every row it
    returns. A gateway that ignores `now` cannot fail the way production does,
    so this one asserts it received a usable instant, which is the whole point
    of the case below.
    """

    def __init__(self, invitations: tuple[object, ...]) -> None:
        self.invitations = invitations
        self.asked_at: object = None

    def invitations_for_organization(
        self, organization_id: str, *, now: object
    ) -> tuple[object, ...]:
        if not isinstance(now, datetime):
            raise TypeError(
                f"the listing needs an instant to compare against, got {now!r}"
            )
        self.asked_at = now
        return self.invitations


class TestTheTeamSurfaceListsInvitations:
    """The path no other case in this file reaches: an organization holding one."""

    def test_it_lists_an_organization_that_holds_an_invitation(self) -> None:
        """Found in review on `#508`, and no existing test could see it.

        `_team_response` passed `now=None` to a listing whose signature requires
        a `datetime` and which compares `stored <= now` on every row it returns.
        Every Team test lists an *empty* organization, so the loop never ran and
        the surface answered `200` while any organization with a single
        invitation row raised `TypeError`.

        This is the same shape `#382` recorded for the `AttributeError` the
        adapter fixed: a field wired to something that cannot answer the
        surface's call, invisible while nothing calls it.
        """
        invitations = _ListingInvitations(
            (
                SimpleNamespace(
                    invitation_id="inv-1",
                    target_identity="invitee@example.test",
                    intended_role="member",
                ),
            )
        )
        reader = _StubOrganizations(
            organizations=[_organization("org-acme", "Acme")],
            members=[_Member("member@example.test", "owner", False)],
        )

        response = _shell(reader=reader, invitations=invitations).get(
            f"{SHELL_PREFIX}/en/org-acme/team"
        )

        assert response.status_code == 200
        assert invitations.asked_at == NOW


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

    def test_an_address_naming_another_organization_is_refused_before_any_read(self) -> None:
        """`FR-042` scenario 3. The path names one organization; the session names another.

        This case once asserted that the surface rendered the *session's* team under the other
        organization's address. `FR-042`'s text requires the two to be compared and the request
        to fail closed on disagreement, which review on `#373` read correctly; the pin is replaced.
        Asserted on what the reader was asked as well as on the status, because a surface that
        refused after reading would still have consulted the membership list for a page it did
        not show.
        """
        reader = _StubOrganizations(
            organizations=[_organization("org-acme", "Acme")], members=[]
        )
        response = _shell(context=_Context("acct-1", "org-acme"), reader=reader).get(
            f"{SHELL_PREFIX}/en/org-someone-else/team"
        )

        assert response.status_code == 404
        assert reader.member_calls == []

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
