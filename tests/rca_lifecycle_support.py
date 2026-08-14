"""Shared fixtures for the account lifecycle test modules (`RCA-001` #149)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import OWNER_ROLE, Membership, OrganizationService
from khepri.rca.persistence import Base, MembershipRow, SqlAccountStore, SqlOrganizationStore
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
EMAIL = "owner@example.test"
OTHER_EMAIL = "other@example.test"
CREDENTIAL = "correct horse battery staple"


def build_factory() -> sessionmaker:
    """An in-memory engine with foreign keys actually enforced.

    `StaticPool` plus `check_same_thread=False` because every new connection to
    `sqlite+pysqlite://` otherwise gets a fresh empty database; and an explicit
    `PRAGMA foreign_keys=ON` per connection, because SQLite defaults it to OFF and every
    ForeignKeyConstraint would be inert.
    """
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture(name="factory")
def factory_fixture() -> sessionmaker:
    return build_factory()


def memory_stack() -> tuple[MemoryAccountStore, MemoryOrganizationStore, LifecycleService]:
    """Both fakes plus the service, wired so the fake counts owners the way the store does.

    Without passing `accounts` to the organization store, the fake would count membership rows
    and disagree with `SqlOrganizationStore` on exactly the case FR-013 turns on.
    """
    accounts = MemoryAccountStore()
    organizations = MemoryOrganizationStore(accounts)
    return accounts, organizations, LifecycleService(accounts, organizations)


@dataclass(frozen=True, slots=True)
class TwoOwners:
    """An organization with two owner-role members, and the stores holding it."""

    accounts: object
    organizations: object
    lifecycle: LifecycleService
    organization: object
    first: object
    second: object


def two_owner_organization(factory: sessionmaker | None = None) -> TwoOwners:
    """Build the fixture every FR-013 test needs: one organization, two owners.

    `OrganizationService` only ever makes the creator an owner, so the second has to be added
    directly. Extracted as one unit because that is what the duplication actually was — four
    near-identical setup statements repeated across the FR-013 tests in two variants. An earlier
    attempt pulled out only the membership line, which left the block intact and added an
    argument-heavy helper in its place.

    Pass `factory` for the SQL-backed variant; omit it for the in-memory one.
    """
    if factory is None:
        accounts = MemoryAccountStore()
        organizations = MemoryOrganizationStore(accounts)
    else:
        accounts = SqlAccountStore(factory)
        organizations = SqlOrganizationStore(factory)

    first = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    _grant(
        (organizations, factory, organization.organization_id),
        second.account_id,
        OWNER_ROLE,
    )
    return TwoOwners(
        accounts, organizations, LifecycleService(accounts, organizations),
        organization, first, second,
    )


def _grant(stack_parts, account_id: str, role: str) -> None:
    """Add a membership to whichever store backs this fixture.

    Takes the fixture's own (organizations, factory, organization_id) rather than three separate
    parameters: the caller already has them together, and threading them individually is the
    excess-argument smell that replaced the duplication on the first attempt.

    The granter used to travel with them, for the membership row's `changed_by`. `20260814_0014`
    dropped that column, and a fixture helper is the wrong place to keep synthesizing attribution
    the schema no longer has -- a test needing an attributed change builds a `MembershipEvent`.
    """
    organizations, factory, organization_id = stack_parts
    if factory is None:
        organizations.memberships[(organization_id, account_id)] = Membership.create(
            organization_id, account_id, role
        )
        return
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
            )
        )


def grant_membership(stack: TwoOwners, account_id: str, role: str, *, factory=None) -> None:
    """Add one more membership to an existing fixture, for the multi-organization cases."""
    _grant(
        (stack.organizations, factory, stack.organization.organization_id),
        account_id,
        role,
    )
