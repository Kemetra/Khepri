"""Shared fixtures for the account lifecycle test modules (`RCA-001` #149)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.lifecycle import LifecycleService
from khepri.rca.persistence import Base
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
