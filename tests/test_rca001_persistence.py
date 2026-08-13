from __future__ import annotations

import inspect
import secrets
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rca.accounts import Account, AccountService
from khepri.rca.credentials import DEFAULT_KDF, Verifier, hash_credential
from khepri.rca.errors import AuthenticationFailed, OrganizationCreationFailed
from khepri.rca.isolation import IsolationService
from khepri.rca.organizations import (
    IsolationScope,
    Membership,
    Organization,
    OrganizationService,
)
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


def test_an_account_round_trips_through_a_new_store_instance(factory: sessionmaker) -> None:
    """Reads must come from the database, not session-local state.

    A brand-new store instance cannot see an uncommitted write — for example if `add_account`
    used `self._factory()` instead of `self._factory.begin()`, which closes without
    committing — so this is what proves the row actually landed.
    """
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)

    restored = SqlAccountStore(factory).get_account(account.account_id)
    assert restored is not None
    assert restored.email == EMAIL
    assert restored.verifier == account.verifier
    # A record rebuilt through the reconstruction door equals the one the creation door made:
    # the sentinel is excluded from equality, so round-tripping is not door-dependent.
    assert restored == account


@pytest.mark.parametrize(
    "destroyed",
    [
        pytest.param(("credential_digest",), id="digest_only"),
        pytest.param(("credential_salt",), id="salt_only"),
        pytest.param(("kdf_n", "kdf_r", "kdf_p"), id="work_factor_only"),
        pytest.param(("kdf_n",), id="one_work_factor_column"),
    ],
)
def test_a_partially_destroyed_verifier_reads_as_no_verifier(
    factory: sessionmaker, destroyed: tuple[str, ...]
) -> None:
    """`KHEPRI-DEC-015` destruction must not be expressible by halves.

    The verifier occupies five columns, so a destruction that fails partway — or a future
    write path that clears some of them — leaves a row that is neither live nor destroyed.
    Reading such a row as a *usable* verifier would let a disabled account authenticate
    against whatever material survived. So any missing part makes the whole thing absent.

    This is #149's load-bearing assumption: that slice destroys verifiers on disablement, and
    it inherits this reader. Without this test the guard is deletable in a refactor without a
    single test going red — verified by mutation (`any` to `all` leaves the suite green).
    """
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)

    with factory.begin() as database:
        row = database.get(AccountRow, account.account_id)
        assert row is not None
        for column in destroyed:
            setattr(row, column, None)

    restored = SqlAccountStore(factory).get_account(account.account_id)
    assert restored is not None, "the account itself survives; only its verifier is gone"
    assert restored.verifier is None
    assert restored.has_verifier is False

    # And it must not authenticate, even with the credential that produced the row.
    with pytest.raises(AuthenticationFailed):
        AccountService(SqlAccountStore(factory)).authenticate(EMAIL, CREDENTIAL)


def test_a_canonicalized_duplicate_is_refused_through_the_service(
    factory: sessionmaker,
) -> None:
    service = AccountService(SqlAccountStore(factory))
    service.create_account(EMAIL, CREDENTIAL)

    with pytest.raises(AuthenticationFailed):
        service.create_account("Owner@EXAMPLE.Test", "another credential")

    with factory() as database:
        assert database.execute(select(func.count()).select_from(AccountRow)).scalar() == 1


def test_the_store_canonicalizes_without_the_service(factory: sessionmaker) -> None:
    """A-1 must hold for callers that bypass `AccountService` entirely.

    An importer, a backfill, or any other internal caller reaching `add_account` directly
    would otherwise persist a mixed-case address verbatim beside its canonical twin — two
    durable identities for one mailbox, with the mixed-case row unreachable through
    canonicalized service lookups. This calls the store directly, which is what an earlier
    version of this test only appeared to do: it routed both inserts through the service, so
    the store's own behaviour was never exercised.

    Note the two bypasses are different and only one is closed. Skipping `AccountService` is
    still permitted and still exercised here; skipping a *construction door* is not, so the
    records are built through `_from_storage` — the door for values that already exist — with
    a deliberately non-canonical address, which is precisely the input a backfill would carry.
    """
    store = SqlAccountStore(factory)
    salt = secrets.token_bytes(16)
    verifier = Verifier.from_storage(
        salt=salt, digest=hash_credential(CREDENTIAL, salt, DEFAULT_KDF), kdf=DEFAULT_KDF
    )

    assert store.add_account(
        Account._from_storage(account_id="acc_canonical", email=EMAIL, verifier=verifier)
    )
    # Same mailbox, different casing, straight into the store.
    assert not store.add_account(
        Account._from_storage(
            account_id="acc_variant", email="Owner@EXAMPLE.Test", verifier=verifier
        )
    )

    with factory() as database:
        assert database.execute(select(func.count()).select_from(AccountRow)).scalar() == 1

    # And the stored row is reachable by any casing, because lookup canonicalizes too.
    for variant in (EMAIL, "OWNER@example.test", "  Owner@Example.Test  "):
        found = store.get_account_by_email(variant)
        assert found is not None, variant
        assert found.account_id == "acc_canonical"


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

    doomed = Organization._from_storage(
        organization_id="org_doomed", name="Doomed", created_at=NOW
    )
    orphan = Membership._from_storage(
        organization_id="org_doomed",
        account_id="acc_does_not_exist",
        role="owner",
        changed_by="acc_does_not_exist",
        changed_at=NOW,
    )
    scope = IsolationScope.create("org_doomed")

    assert store.create_organization(doomed, orphan, scope) is False

    with factory() as database:
        assert database.execute(select(func.count()).select_from(OrganizationRow)).scalar() == 1
        assert database.execute(select(func.count()).select_from(MembershipRow)).scalar() == 1
        assert database.execute(select(func.count()).select_from(IsolationScopeRow)).scalar() == 1
        assert database.get(IsolationScopeRow, "org_doomed") is None
        assert database.get(OrganizationRow, "org_doomed") is None


def test_a_mismatched_aggregate_is_refused_without_writing(factory: sessionmaker) -> None:
    """The three records form one aggregate; foreign keys alone do not enforce that.

    A membership naming a different EXISTING organization satisfies every constraint, so the
    new organization would commit with no owner — an orphan, which FR-013 forbids from the
    moment of creation. Note the account must differ from the existing owner: with the same
    account the composite primary key collides and the write fails for an unrelated reason,
    which is what made an earlier version of this check pass by accident.
    """
    accounts = AccountService(SqlAccountStore(factory))
    owner = accounts.create_account(EMAIL, CREDENTIAL)
    other = accounts.create_account("other@example.test", CREDENTIAL)
    store = SqlOrganizationStore(factory)
    existing = OrganizationService(store).create_organization("First", owner.account_id, now=NOW)

    for membership_org, scope_org in (
        (existing.organization_id, "org_new"),  # membership points elsewhere
        ("org_new", existing.organization_id),  # scope points elsewhere
    ):
        assert not store.create_organization(
            Organization._from_storage(organization_id="org_new", name="New", created_at=NOW),
            Membership._from_storage(
                organization_id=membership_org,
                account_id=other.account_id,
                role="owner",
                changed_by=other.account_id,
                changed_at=NOW,
            ),
            IsolationScope.create(scope_org),
        )

    with factory() as database:
        assert database.execute(select(func.count()).select_from(OrganizationRow)).scalar() == 1
        assert database.get(OrganizationRow, "org_new") is None


def test_the_creation_door_has_no_parameter_for_an_isolation_key() -> None:
    """FR-032/FR-033 by construction: `create` cannot express an untrusted key.

    Two weaker versions were tried and both left a hole. Validating in
    `OrganizationService` missed every caller reaching the store directly — verified: such a
    caller persisted `owner@example.test`, and `resolve_scope` handed that email back as the
    analytical boundary. Validating the key's *shape* then missed
    `own_AcmePharmacy000000000000`, which is 24 characters of the accepted alphabet and still
    copied straight from an organization name.

    Shape cannot establish provenance, so the creation door owns the key instead of checking
    it. This asserts the **signature**, not an exception type: an earlier version asserted
    `pytest.raises(TypeError)` on a direct call, which after #151 sealed the constructor would
    have kept passing for an entirely unrelated reason (a missing sentinel), leaving the
    property it was written to defend untested.
    """
    assert "owner_id" not in inspect.signature(IsolationScope.create).parameters


def test_a_created_scope_never_carries_caller_data() -> None:
    """The complement of the signature check: what `create` actually mints is opaque."""
    for untrusted in (
        "owner@example.test",
        "acme-pharmacy",
        "own_AcmePharmacy000000000000",
    ):
        scope = IsolationScope.create(untrusted)
        assert untrusted not in scope.owner_id
        assert scope.owner_id.startswith("own_")


def test_records_reject_construction_outside_a_door() -> None:
    """Every sealed record refuses a direct call, so a bypass cannot happen by accident."""
    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        IsolationScope(organization_id="org_1", owner_id="own_whatever")
    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        Organization(organization_id="org_1", name="Acme", created_at=NOW)
    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        Membership(
            organization_id="org_1",
            account_id="acc_1",
            role="owner",
            changed_by="acc_1",
            changed_at=NOW,
        )
    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        Account(account_id="acc_1", email=EMAIL, verifier=None)


def test_a_store_refuses_a_record_that_did_not_come_through_a_door(
    factory: sessionmaker,
) -> None:
    """The persistence boundary checks provenance, not field contents.

    Checking contents is what #148's round 2 already proved insufficient: a value's shape
    cannot establish where it came from. `object.__setattr__` is the deliberate, conspicuous
    bypass the sealed form permits — this asserts the store still refuses its output.
    """
    smuggled = Account.create(EMAIL, CREDENTIAL)
    object.__setattr__(smuggled, "_token", None)
    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        SqlAccountStore(factory).add_account(smuggled)


def test_every_scope_allocates_a_distinct_opaque_key() -> None:
    keys = {IsolationScope.create(f"org_{index}").owner_id for index in range(200)}
    assert len(keys) == 200
    assert all(key.startswith("own_") for key in keys)


def test_reconstruction_preserves_the_key_that_was_allocated_originally() -> None:
    """FR-035: one organization resolves to a stable scope for its lifetime.

    The persistence read path must return the stored key, not mint a new one.
    """
    stored = IsolationScope.create("org_1").owner_id
    assert IsolationScope._from_storage("org_1", stored).owner_id == stored


def test_service_converts_a_failed_write_into_a_uniform_refusal(factory: sessionmaker) -> None:
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    with pytest.raises(OrganizationCreationFailed):
        service.create_organization("Acme", "acc_does_not_exist", now=NOW)


def test_authentication_against_a_stored_row_with_no_verifier_is_refused(
    factory: sessionmaker,
) -> None:
    """A verifier-less row must refuse, not crash, and must pay the same cost.

    Account disablement is a later slice, but the state it produces — a row whose verifier
    was destroyed per KHEPRI-DEC-015 — is already representable, so authentication has to
    handle it now rather than raising on a None digest.
    """
    service = AccountService(SqlAccountStore(factory))
    account = service.create_account(EMAIL, CREDENTIAL)

    with factory.begin() as database:
        row = database.get(AccountRow, account.account_id)
        assert row is not None
        row.credential_salt = None
        row.credential_digest = None
        row.kdf_n = row.kdf_r = row.kdf_p = None

    with pytest.raises(AuthenticationFailed):
        service.authenticate(EMAIL, CREDENTIAL)

    restored = SqlAccountStore(factory).get_account(account.account_id)
    assert restored is not None
    assert restored.has_verifier is False


def test_the_schema_permits_an_account_with_no_verifier() -> None:
    """The columns must be nullable, or DEC-015's required end state is unrepresentable.

    Asserted here rather than left to the disablement slice so that slice inherits a schema
    it can satisfy without a migration.
    """
    columns = {column.name: column for column in AccountRow.__table__.columns}
    for name in ("credential_salt", "credential_digest", "kdf_n", "kdf_r", "kdf_p"):
        assert columns[name].nullable, f"{name} must be nullable to allow verifier destruction"
    assert "disabled" not in columns, "account lifecycle is deferred to its own slice"


def test_no_rca_table_references_an_rra_table() -> None:
    for table in Base.metadata.tables.values():
        assert table.name.startswith("rca_")
        for constraint in table.foreign_key_constraints:
            for element in constraint.elements:
                assert not element.target_fullname.startswith("rra_")
