"""#432: the database, not a Python call, refuses a cross-scope package or a phantom organization.

`RRA-001` binds every fact package to its opaque owner *and* session. Before `20260925_0031` a
package's `(owner_id, session_id)` and its `profile_id` were checked by two independent foreign
keys, so a package in scope A could cite scope B's profile with both constraints satisfied -- the
shape `20260904_0021` already closed for the workspace. `20260925_0032` gives
`rca_sessions.active_organization_id` the foreign key it lacked, so a session cannot name an
organization that does not exist.

**Every write goes through the production verb.** A raw `INSERT` would prove the constraint exists
while leaving unproved that the store surfaces it -- `add_package` catches `IntegrityError` to
answer a publication race, and a catch that swallowed a scope fault would turn this refusal into a
silent "already published".

**SQLite enforces nothing unless asked.** RRA's own fixtures do not enable `PRAGMA foreign_keys`,
so this module builds its engine with it on; without that every assertion below would pass for
the wrong reason. The PostgreSQL block proves the migrations' DDL, which no SQLite fixture here
replays, and carries the `concurrency` marker so a skip in CI fails the build.

**Not a `test_rra*` file.** `RCA-001` `FR-037` keeps RRA's existing tests unmodified; this file is
new and edits none of them.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore as RcaSessionStore
from khepri.rca.sessions import Session
from khepri.rra.datasets import DatasetProfileRecord
from khepri.rra.packages import FactPackageRecord
from khepri.rra.persistence import Base as RraBase
from khepri.rra.persistence import (
    SqlFactPackageRepository,
    SqlProfileRepository,
    SqlSessionStore,
)
from khepri.rra.sessions import BetaSession, open_commercial_session
from tests.rca_lifecycle_support import build_factory

NOW = datetime(2026, 9, 25, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64
PACKAGE_SCOPE_FK = "fk_package_profile_scope"
ACTIVE_ORGANIZATION_FK = "fk_rca_session_active_organization"
LEGACY_PACKAGE_FK = "fk_package_profile"
PARENT_REVISION = "20260915_0030"
REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")


def _enforcing_engine() -> Engine:
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

    return engine


@dataclass(frozen=True, slots=True)
class RraStores:
    sessions: SqlSessionStore
    profiles: SqlProfileRepository
    packages: SqlFactPackageRepository

    @classmethod
    def over(cls, factory: sessionmaker) -> RraStores:
        return cls(
            SqlSessionStore(factory),
            SqlProfileRepository(factory),
            SqlFactPackageRepository(factory),
        )

    def open(self, owner_id: str) -> BetaSession:
        return open_commercial_session(self.sessions, owner_id=owner_id, now=NOW)

    def profile(self, session: BetaSession) -> DatasetProfileRecord:
        return self.profiles.add_profile(
            DatasetProfileRecord(
                profile_id=f"prf_{session.session_id}",
                owner_id=session.owner_id,
                session_id=session.session_id,
                upload_id=f"upl_{session.session_id}",
                profile_version="rra003.profile.v1",
                mapping_version="rra003.mapping.v1",
                source_sha256_hex=DIGEST,
                profile_digest=DIGEST,
                row_count=1,
                column_count=1,
                admissible=True,
                created_at=NOW,
                document={},
            )
        )

    def publish(self, session: BetaSession, profile_id: str) -> FactPackageRecord:
        return self.packages.add_package(
            FactPackageRecord(
                package_id=f"pkg_{session.session_id}",
                owner_id=session.owner_id,
                session_id=session.session_id,
                profile_id=profile_id,
                package_version="rra004.package.v1",
                formula_version="rra004.formula.v1",
                mapping_version="rra003.mapping.v1",
                profile_document_digest=DIGEST,
                source_sha256_hex=DIGEST,
                package_digest=DIGEST,
                row_count=1,
                created_at=NOW,
                document={},
            )
        )


@pytest.fixture(name="rra")
def rra_fixture() -> RraStores:
    engine = _enforcing_engine()
    RraBase.metadata.create_all(engine)
    return RraStores.over(sessionmaker(engine, expire_on_commit=False))


class TestAPackageCitesOnlyItsOwnProfile:
    def test_a_package_citing_another_scopes_profile_is_refused(self, rra: RraStores) -> None:
        mine = rra.open("own_scope_a")
        theirs = rra.profile(rra.open("own_scope_b"))

        with pytest.raises(IntegrityError):
            rra.publish(mine, theirs.profile_id)

    def test_a_package_citing_another_sessions_profile_is_refused(self, rra: RraStores) -> None:
        """Same owner, other session: `RRA-001` binds a package to both, not to the owner alone."""
        mine = rra.open("own_scope_a")
        sibling = rra.profile(rra.open("own_scope_a"))

        with pytest.raises(IntegrityError):
            rra.publish(mine, sibling.profile_id)

    def test_a_package_citing_its_own_profile_is_admitted(self, rra: RraStores) -> None:
        mine = rra.open("own_scope_a")
        profile = rra.profile(mine)

        assert rra.publish(mine, profile.profile_id).profile_id == profile.profile_id


@dataclass(frozen=True, slots=True)
class RcaStack:
    sessions: RcaSessionStore
    account_id: str
    organization_id: str

    def issue(self, organization_id: str | None) -> Session:
        issued = Session.issue(self.account_id, now=NOW, lifetime=timedelta(hours=12))
        return issued.session.switched_to(organization_id)


@pytest.fixture(name="rca")
def rca_fixture() -> RcaStack:
    factory = build_factory()
    account_id = (
        AccountService(SqlAccountStore(factory))
        .create_account("owner@example.test", "correct horse battery staple")
        .account_id
    )
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", account_id, now=NOW
    )
    return RcaStack(RcaSessionStore(factory), account_id, organization.organization_id)


class TestASessionNamesOnlyARealOrganization:
    def test_a_session_issued_into_an_absent_organization_is_refused(self, rca: RcaStack) -> None:
        with pytest.raises(IntegrityError):
            rca.sessions.add_session(rca.issue("org_absent"))

    def test_a_session_pointed_at_an_absent_organization_is_refused(self, rca: RcaStack) -> None:
        session = rca.issue(None)
        assert rca.sessions.add_session(session)

        with pytest.raises(IntegrityError):
            rca.sessions.point_session_at_organization(session.session_id_hash, "org_absent")

    @pytest.mark.parametrize("real", [True, False], ids=["real organization", "no organization"])
    def test_a_real_or_absent_active_organization_is_admitted(
        self, rca: RcaStack, real: bool
    ) -> None:
        organization_id = rca.organization_id if real else None

        assert rca.sessions.add_session(rca.issue(organization_id))


requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; this DDL cannot be proved on SQLite",
)


def _alembic_config() -> Config:
    assert DATABASE_URL is not None
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    return config


def _foreign_keys(engine: Engine, table: str) -> set[str]:
    return {key["name"] for key in inspect(engine).get_foreign_keys(table)}


@pytest.fixture(name="postgres")
def postgres_fixture() -> Iterator[tuple[Config, Engine]]:
    """A database at head, left at head -- the range `test_rra_portable_encryption_migration.py`
    documents, because the chain cannot downgrade to base on PostgreSQL."""
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("drop schema public cascade"))
        connection.execute(text("create schema public"))
    config = _alembic_config()
    command.upgrade(config, "head")
    try:
        yield config, engine
    finally:
        command.upgrade(config, "head")
        engine.dispose()


@pytest.mark.concurrency
@requires_postgres
class TestTheMigrationsOnPostgres:
    def test_head_carries_both_named_foreign_keys(self, postgres: tuple[Config, Engine]) -> None:
        _config, engine = postgres

        assert PACKAGE_SCOPE_FK in _foreign_keys(engine, "rra_fact_packages")
        assert LEGACY_PACKAGE_FK not in _foreign_keys(engine, "rra_fact_packages")
        assert ACTIVE_ORGANIZATION_FK in _foreign_keys(engine, "rca_sessions")

    def test_head_refuses_a_cross_scope_package(self, postgres: tuple[Config, Engine]) -> None:
        _config, engine = postgres
        rra = RraStores.over(sessionmaker(engine, expire_on_commit=False))
        theirs = rra.profile(rra.open("own_scope_b"))

        with pytest.raises(IntegrityError):
            rra.publish(rra.open("own_scope_a"), theirs.profile_id)

    def test_downgrade_restores_the_single_column_foreign_key(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        config, engine = postgres

        command.downgrade(config, PARENT_REVISION)

        assert LEGACY_PACKAGE_FK in _foreign_keys(engine, "rra_fact_packages")
        assert PACKAGE_SCOPE_FK not in _foreign_keys(engine, "rra_fact_packages")
        assert ACTIVE_ORGANIZATION_FK not in _foreign_keys(engine, "rca_sessions")
