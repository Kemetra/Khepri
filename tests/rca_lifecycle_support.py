"""Shared fixtures for the account lifecycle test modules (`RCA-001` #149)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import Membership
from khepri.rca.persistence import Base, MembershipRow
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


def add_membership(
    organizations: MemoryOrganizationStore,
    organization_id: str,
    account_id: str,
    role: str,
    *,
    changed_by: str,
) -> None:
    """Give an account a membership in the fake store.

    The FR-013 tests each need an organization with a second member at a chosen role, and
    writing that inline six times is duplication CodeScene flags — fairly, since the shape is
    identical every time and only the role and holder vary.
    """
    organizations.memberships[(organization_id, account_id)] = Membership.create(
        organization_id, account_id, role, changed_by=changed_by, now=NOW
    )


def add_membership_row(
    factory: sessionmaker,
    organization_id: str,
    account_id: str,
    role: str,
    *,
    changed_by: str,
) -> None:
    """The same, against the real store.

    The SQL-backed FR-013 tests need a second owner row that `OrganizationService` will not
    create for them, since it only ever makes the creator an owner.
    """
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization_id,
                account_id=account_id,
                role=role,
                changed_by=changed_by,
                changed_at=NOW,
            )
        )
