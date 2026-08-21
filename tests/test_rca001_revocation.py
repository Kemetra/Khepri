"""`R2-05` -- membership revocation (`FR-012`), guarded by `FR-013`.

**The guard ships with the operation rather than after it.** `R2-04` could split promotion from
demotion because `FR-013` names "remove, downgrade, or disable" and promotion is none of them.
Revocation has no such subset: revoking a member and revoking the final owner are the same
operation on different data, so there is no part of it `FR-013` leaves unconstrained. Shipping the
write first and the guard in `R2-06` would put a callable zero-owner path on `main` for a merge
cycle -- exactly what `R2-04`'s split existed to avoid.

`R2-06` still owns applying the invariant to *demote*, and the three-contender concurrency proof
for both write paths. What it must not do is add a second guard: this routes through the same
lock-count-write seam `R1` built.

`FR-020`'s invitation half belongs to `R4`; invitations do not exist yet.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    OWNER_CHANGE_APPLIED,
    OWNER_CHANGE_FINAL_OWNER,
    OWNER_CHANGE_NOT_APPLICABLE,
    FinalOwnerProtected,
    RoleChangeFailed,
)
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    OrganizationService,
)
from khepri.rca.persistence import (
    Base,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
    organization_owners_for_update,
)
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 14, 13, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"


@pytest.fixture(name="factory")
def _factory(tmp_path) -> sessionmaker:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'revoke.db').as_posix()}")
    Base.metadata.create_all(engine)
    return sessionmaker(engine)


def _org_with(factory: sessionmaker, *members: tuple[str, str]):
    """An organization owned by `owner@`, plus one membership per (email, role) given."""
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    owner = AccountService(accounts).create_account("owner@example.test", CREDENTIAL)
    organization = OrganizationService(store).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    created = {}
    for email, role in members:
        account = AccountService(accounts).create_account(email, CREDENTIAL)
        with factory.begin() as database:
            database.add(
                MembershipRow(
                    organization_id=organization.organization_id,
                    account_id=account.account_id,
                    role=role,
                )
            )
        created[email] = account
    return store, organization, owner, created


# --- FR-012: one membership ends, nothing else moves ------------------------------------------


def test_revocation_removes_only_the_named_membership(factory: sessionmaker) -> None:
    """Scenario 11. The row is gone and no other membership is touched."""
    store, organization, owner, members = _org_with(
        factory, ("member@example.test", MEMBER_ROLE), ("other@example.test", MEMBER_ROLE)
    )
    target = members["member@example.test"]
    bystander = members["other@example.test"]

    service = OrganizationService(store)
    service.revoke_membership(
        organization.organization_id,
        target.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    assert store.get_membership(organization.organization_id, target.account_id) is None
    surviving = store.get_membership(organization.organization_id, bystander.account_id)
    assert surviving is not None, "FR-012: another member of the same organization is unaffected"
    assert surviving.role == MEMBER_ROLE
    assert store.get_membership(organization.organization_id, owner.account_id) is not None


def test_revocation_leaves_the_accounts_other_memberships_intact(factory: sessionmaker) -> None:
    """FR-012's other half: the same account's membership elsewhere survives.

    This is the clause a naive `DELETE FROM rca_memberships WHERE account_id = :id` breaks, and
    it cannot be proven against the memory fake in a way that means anything -- a dict delete
    cannot cascade. It needs the real store and a real DELETE.
    """
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account("owner@example.test", CREDENTIAL)
    joiner = AccountService(accounts).create_account("joiner@example.test", CREDENTIAL)
    first = service.create_organization("First", owner.account_id, now=NOW)
    second = service.create_organization("Second", owner.account_id, now=NOW)
    for organization in (first, second):
        with factory.begin() as database:
            database.add(
                MembershipRow(
                    organization_id=organization.organization_id,
                    account_id=joiner.account_id,
                    role=MEMBER_ROLE,
                )
            )

    service.revoke_membership(
        first.organization_id,
        joiner.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    assert store.get_membership(first.organization_id, joiner.account_id) is None
    still_there = store.get_membership(second.organization_id, joiner.account_id)
    assert still_there is not None, "FR-012: the same account's other membership is unaffected"


def test_revocation_does_not_touch_the_account(factory: sessionmaker) -> None:
    """Revoking a membership is not disabling an account.

    The account keeps authenticating; it simply has one fewer organization. Conflating the two
    would make revocation a far larger operation than FR-012 describes.
    """
    accounts = SqlAccountStore(factory)
    store, organization, owner, members = _org_with(
        factory, ("member@example.test", MEMBER_ROLE)
    )
    target = members["member@example.test"]

    OrganizationService(store).revoke_membership(
        organization.organization_id,
        target.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    account = accounts.get_account(target.account_id)
    assert account is not None
    assert account.can_authenticate(
        has_external_identity=False
    ), "the account survives its revoked membership"


# --- FR-013: the guard, on the same seam R1 built ---------------------------------------------


def test_revoking_the_final_owner_is_refused(factory: sessionmaker) -> None:
    """Scenario 17, through the revoke path.

    FR-013 names "remove" first, so this is the clause the requirement leads with -- and it had
    no operation to guard until now.
    """
    store, organization, owner, _ = _org_with(factory, ("member@example.test", MEMBER_ROLE))

    with pytest.raises(FinalOwnerProtected):
        OrganizationService(store).revoke_membership(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )

    assert store.get_membership(organization.organization_id, owner.account_id) is not None


def test_a_refused_revocation_writes_no_event(factory: sessionmaker) -> None:
    """The event and the deletion travel together in both directions."""
    store, organization, owner, _ = _org_with(factory, ("member@example.test", MEMBER_ROLE))

    with pytest.raises(FinalOwnerProtected):
        OrganizationService(store).revoke_membership(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )

    with factory() as database:
        revocations = database.execute(
            text("SELECT COUNT(*) FROM rca_membership_events WHERE next_role IS NULL")
        ).scalar()
    assert revocations == 0, "a refused revocation leaves no audit record of one"


def test_a_non_final_owner_can_be_revoked(factory: sessionmaker) -> None:
    """Two owners: revoking one leaves the other, so the guard must not refuse."""
    store, organization, owner, members = _org_with(
        factory, ("second@example.test", OWNER_ROLE)
    )
    second = members["second@example.test"]

    OrganizationService(store).revoke_membership(
        organization.organization_id,
        second.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    assert store.get_membership(organization.organization_id, second.account_id) is None
    assert store.get_membership(organization.organization_id, owner.account_id) is not None


def test_a_disabled_co_owner_does_not_rescue_the_final_owner(factory: sessionmaker) -> None:
    """The guard counts *effective* owners, exactly as the disable path does.

    A disabled co-owner keeps their membership row but cannot act, so revoking the one remaining
    live owner would strand the organization. Counting rows rather than effective owners is the
    defect `_effective_owner_conditions` exists to prevent, and this asserts the revoke path
    inherits it rather than re-deriving a weaker rule.
    """
    accounts = SqlAccountStore(factory)
    store, organization, owner, members = _org_with(
        factory, ("second@example.test", OWNER_ROLE)
    )
    second = members["second@example.test"]
    LifecycleService(accounts, store).disable_account(second.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        OrganizationService(store).revoke_membership(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )


# --- FR-014: the event outlives the row it describes ------------------------------------------


def test_revocation_records_an_event_that_survives_the_deleted_row(
    factory: sessionmaker,
) -> None:
    """`KHEPRI-DEC-015` retains the membership "only as the subject of the FR-014 audit event".

    `MembershipEventRow` carries no foreign key precisely so this works: a key onto
    `rca_memberships` would stop revocation removing the row its own event describes.
    """
    store, organization, owner, members = _org_with(
        factory, ("member@example.test", MEMBER_ROLE)
    )
    target = members["member@example.test"]

    OrganizationService(store).revoke_membership(
        organization.organization_id,
        target.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    with factory() as database:
        row = database.execute(
            text(
                "SELECT prior_role, next_role, actor_account_id FROM rca_membership_events "
                "WHERE account_id = :account_id AND next_role IS NULL"
            ),
            {"account_id": target.account_id},
        ).one()

    assert row.prior_role == MEMBER_ROLE, "FR-014: what the prior role was"
    assert row.next_role is None, "a revocation has no resulting role"
    assert row.actor_account_id == owner.account_id, "FR-014: who made the change"


def test_the_event_prior_role_comes_from_the_row_not_the_caller(factory: sessionmaker) -> None:
    """Read inside the transaction, like `promote_membership`.

    A caller-supplied prior role could describe a transition that did not happen, and the event
    has no foreign key to contradict it.
    """
    store, organization, owner, members = _org_with(
        factory, ("second@example.test", OWNER_ROLE)
    )
    second = members["second@example.test"]

    OrganizationService(store).revoke_membership(
        organization.organization_id,
        second.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    with factory() as database:
        prior = database.execute(
            text(
                "SELECT prior_role FROM rca_membership_events "
                "WHERE account_id = :account_id AND next_role IS NULL"
            ),
            {"account_id": second.account_id},
        ).scalar()
    assert prior == OWNER_ROLE, "the owner's revocation records the owner role it actually held"


# --- refusals -------------------------------------------------------------------------------


def test_revoking_a_membership_that_does_not_exist_is_refused(factory: sessionmaker) -> None:
    store, organization, owner, _ = _org_with(factory, ("member@example.test", MEMBER_ROLE))

    with pytest.raises(RoleChangeFailed):
        OrganizationService(store).revoke_membership(
            organization.organization_id,
            "acc_not_a_member",
            actor_account_id=owner.account_id,
            now=LATER,
        )


def test_the_memory_fake_reports_the_same_outcomes() -> None:
    """The fake must refuse what the store refuses, or refusal tests prove nothing.

    A single-threaded dictionary models the *sequential* contract only and is never concurrency
    evidence -- the same caveat `apply_owner_reducing_change`'s fake carries.
    """
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account("owner@example.test", CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)

    assert (
        store.revoke_membership(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )
        == OWNER_CHANGE_FINAL_OWNER
    )
    assert (
        store.revoke_membership(
            organization.organization_id,
            "acc_ghost",
            actor_account_id=owner.account_id,
            now=LATER,
        )
        == OWNER_CHANGE_NOT_APPLICABLE
    )


def test_the_sql_store_reports_the_same_outcome_vocabulary(factory: sessionmaker) -> None:
    store, organization, owner, members = _org_with(
        factory, ("member@example.test", MEMBER_ROLE)
    )
    target = members["member@example.test"]

    assert (
        store.revoke_membership(
            organization.organization_id,
            "acc_ghost",
            actor_account_id=owner.account_id,
            now=LATER,
        )
        == OWNER_CHANGE_NOT_APPLICABLE
    )
    assert (
        store.revoke_membership(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )
        == OWNER_CHANGE_FINAL_OWNER
    )
    outcome = store.revoke_membership(
        organization.organization_id,
        target.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )
    assert outcome == OWNER_CHANGE_APPLIED


def test_the_organization_owner_query_locks_its_rows_on_postgresql() -> None:
    """The revoke path's lock is assertable without a database, like its sibling's.

    SQLite emits no `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so if the
    lock were dropped from `organization_owners_for_update` this whole file would stay green
    while `#155`'s defect class returned through revocation. Compiling against the PostgreSQL
    dialect is the only evidence a SQLite suite can offer.

    It locks by *organization*, unlike `owner_memberships_for_update` which locks by account.
    The disable path reduces ownership across every organization an account owns; revocation
    touches one. Locking the account's rows here would both over-lock and, worse, miss the
    contended set -- two different accounts being revoked from the same organization contend on
    that organization's owner rows, not on each other's.
    """
    statement = organization_owners_for_update("org_example")

    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "rca_memberships.organization_id =" in sql
    assert "rca_memberships.role =" in sql, "only owner rows are locked, not every membership"
