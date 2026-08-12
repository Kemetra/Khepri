from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed, OrganizationCreationFailed
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import Membership, Organization, OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    Base,
    IsolationScopeRow,
    MembershipRow,
    OrganizationRow,
    SqlAccountStore,
    SqlOrganizationStore,
)

NOW = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)
EMAIL = "owner@example.test"
CREDENTIAL = "correct horse battery staple"


def _factory() -> sessionmaker:
    """Build an in-memory engine with foreign keys actually enforced.

    Two non-obvious requirements, both matching `tests/test_rra001_persistence.py`:
    `StaticPool` plus `check_same_thread=False`, because every new connection to
    `sqlite+pysqlite://` otherwise gets a fresh empty database and `create_all` would be
    invisible; and an explicit `PRAGMA foreign_keys=ON` per connection, because SQLite
    defaults it to OFF and every ForeignKeyConstraint would be inert.
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
def _factory_fixture() -> sessionmaker:
    return _factory()


def test_foreign_keys_are_enforced(factory: sessionmaker) -> None:
    """Guards the fixture itself. Without the pragma the atomicity test below is vacuous."""
    with factory() as database:
        enforced = database.execute(select(func.count()).select_from(MembershipRow)).scalar()
        assert enforced == 0
        assert database.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_account_round_trips(factory: sessionmaker) -> None:
    service = AccountService(SqlAccountStore(factory))
    created = service.create_account(EMAIL, CREDENTIAL)
    assert service.authenticate(EMAIL, CREDENTIAL).account_id == created.account_id


def test_duplicate_email_is_rejected_by_the_database(factory: sessionmaker) -> None:
    service = AccountService(SqlAccountStore(factory))
    service.create_account(EMAIL, CREDENTIAL)
    with pytest.raises(AuthenticationFailed):
        service.create_account(EMAIL, "another credential")


def test_disabling_an_account_persists_and_blocks_authentication(factory: sessionmaker) -> None:
    service = AccountService(SqlAccountStore(factory))
    account = service.create_account(EMAIL, CREDENTIAL)
    assert service.authenticate(EMAIL, CREDENTIAL).account_id == account.account_id

    service.disable_account(account.account_id)

    with pytest.raises(AuthenticationFailed):
        service.authenticate(EMAIL, CREDENTIAL)

    # Read through a brand-new store instance so a silently-uncommitted write (e.g. if
    # `update_account` used `self._factory()` instead of `self._factory.begin()`) cannot
    # hide behind session-local state and must actually be visible in the database.
    fresh_store = SqlAccountStore(factory)
    assert fresh_store.get_account(account.account_id).disabled is True


def test_update_account_on_a_missing_account_is_a_no_op(factory: sessionmaker) -> None:
    service = AccountService(SqlAccountStore(factory))
    account = service.create_account(EMAIL, CREDENTIAL)

    store = SqlAccountStore(factory)
    store.update_account(replace(account, account_id="acc_does_not_exist", disabled=True))

    with factory() as database:
        assert database.execute(select(func.count()).select_from(AccountRow)).scalar() == 1
    assert store.get_account(account.account_id).disabled is False


def test_organization_creation_round_trips(factory: sessionmaker) -> None:
    store = SqlOrganizationStore(factory)
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)

    organization = OrganizationService(store).create_organization(
        "Acme", account.account_id, now=NOW
    )
    owner_id = IsolationService(store).resolve_scope(
        account.account_id, organization.organization_id
    )
    assert owner_id.startswith("own_")


def test_scope_survives_a_new_store_instance(factory: sessionmaker) -> None:
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", account.account_id, now=NOW
    )

    first = IsolationService(SqlOrganizationStore(factory)).resolve_scope(
        account.account_id, organization.organization_id
    )
    second = IsolationService(SqlOrganizationStore(factory)).resolve_scope(
        account.account_id, organization.organization_id
    )
    assert first == second


def test_creation_is_atomic_when_a_row_violates_a_constraint(factory: sessionmaker) -> None:
    """Drive the real store path: a membership naming a nonexistent account trips the FK."""
    store = SqlOrganizationStore(factory)
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)
    OrganizationService(store).create_organization("Acme", account.account_id, now=NOW)

    doomed = Organization(organization_id="org_doomed", name="Doomed", created_at=NOW)
    orphan = Membership(
        organization_id="org_doomed",
        account_id="acc_does_not_exist",
        role="owner",
        changed_by="acc_does_not_exist",
        changed_at=NOW,
    )
    from khepri.rca.organizations import IsolationScope

    scope = IsolationScope(organization_id="org_doomed", owner_id="own_doomed")

    assert store.create_organization(doomed, orphan, scope) is False

    with factory() as database:
        assert database.execute(select(func.count()).select_from(OrganizationRow)).scalar() == 1
        assert database.execute(select(func.count()).select_from(MembershipRow)).scalar() == 1
        assert database.execute(select(func.count()).select_from(IsolationScopeRow)).scalar() == 1
        assert database.get(IsolationScopeRow, "org_doomed") is None
        assert database.get(OrganizationRow, "org_doomed") is None


def test_service_converts_a_failed_write_into_a_uniform_refusal(factory: sessionmaker) -> None:
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    with pytest.raises(OrganizationCreationFailed):
        service.create_organization("Acme", "acc_does_not_exist", now=NOW)


def test_disabling_destroys_the_credential_verifier_in_the_database(
    factory: sessionmaker,
) -> None:
    """KHEPRI-DEC-015 retains the verifier only while the account is enabled.

    Its retention matrix requires destruction to be immediate and non-recoverable at
    disablement. Asserting on the row rather than the dataclass is the point: destruction
    only counts if it reaches storage, where backups and offline guessing would find it.
    """
    service = AccountService(SqlAccountStore(factory))
    account = service.create_account(EMAIL, CREDENTIAL)

    with factory() as database:
        row = database.get(AccountRow, account.account_id)
        assert row is not None
        assert row.credential_digest is not None

    service.disable_account(account.account_id)

    with factory() as database:
        row = database.get(AccountRow, account.account_id)
        assert row is not None
        assert row.disabled is True
        assert row.credential_salt is None
        assert row.credential_digest is None
        assert (row.kdf_n, row.kdf_r, row.kdf_p) == (None, None, None)


def test_authentication_against_a_destroyed_verifier_is_refused(factory: sessionmaker) -> None:
    service = AccountService(SqlAccountStore(factory))
    account = service.create_account(EMAIL, CREDENTIAL)
    service.disable_account(account.account_id)

    with pytest.raises(AuthenticationFailed):
        service.authenticate(EMAIL, CREDENTIAL)


def test_the_schema_permits_an_account_with_no_verifier(factory: sessionmaker) -> None:
    """The columns must be nullable, or DEC-015's required end state is unrepresentable."""
    columns = {column.name: column for column in AccountRow.__table__.columns}
    for name in ("credential_salt", "credential_digest", "kdf_n", "kdf_r", "kdf_p"):
        assert columns[name].nullable, f"{name} must be nullable to allow verifier destruction"


def test_no_rca_table_references_an_rra_table() -> None:
    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
        for constraint in table.foreign_key_constraints:
            for element in constraint.elements:
                assert not element.target_fullname.startswith("rra_")
