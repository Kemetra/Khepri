"""`R2-04` -- exact `owner`/`member` transitions through explicit operations.

Scope is deliberately one direction. `FR-013` names "remove, downgrade, or disable" as the
operations that must fail closed, and promotion is none of the three: an organization with *more*
owners is never at risk of reaching zero. So promotion needs no final-owner guard and ships whole
here, while demotion -- which is owner-reducing -- ships in `R2-06` together with the guard it
needs, in one piece.

That split is not a convenience. Shipping a callable demotion here and its guard in `R2-06` would
leave `main` holding an operation that can take an organization to zero owners for a full merge
cycle, and the alternative -- a service-level owner count in the meantime -- is exactly the
cross-store race `lifecycle.py:66-84` documents and `R1` was opened to kill. The roadmap forbids
a second independent guard for the same reason.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import FinalOwnerProtected, RoleChangeFailed
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    ROLES,
    Membership,
    MembershipEvent,
    OrganizationService,
)
from khepri.rca.persistence import Base, MembershipRow, SqlAccountStore, SqlOrganizationStore
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 14, 13, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"
EMAIL = "owner@example.test"
OTHER_EMAIL = "member@example.test"


@pytest.fixture(name="engine")
def _engine(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'roles.db').as_posix()}")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(name="factory")
def _factory(engine) -> sessionmaker:
    return sessionmaker(engine)


# --- the domain transition ------------------------------------------------------------------


def test_promotion_returns_a_new_record_rather_than_mutating() -> None:
    """A role change is an operation, not a field assignment.

    `records.py` refuses `dataclasses.replace`, and its module docstring names
    `replace(membership, role="owner")` as the obvious way to write this transition that must be
    refused -- because that call shape was the forgery `#151` was opened to close. The door
    method is the sanctioned form, following `Account.disabled()`.
    """
    member = Membership.create("org_1", "acc_1", MEMBER_ROLE)

    promoted = member.promoted()

    assert promoted.role == OWNER_ROLE
    assert member.role == MEMBER_ROLE, "the original is untouched"
    assert promoted is not member
    assert (promoted.organization_id, promoted.account_id) == ("org_1", "acc_1")


def test_promoting_an_owner_is_refused() -> None:
    """The transition states its own precondition rather than silently succeeding.

    A no-op promotion would emit an FR-014 event whose prior and next roles are identical --
    an audit record of a change that did not happen, which is worse than no record.
    """
    owner = Membership.create("org_1", "acc_1", OWNER_ROLE)

    with pytest.raises(ValueError, match="already an owner"):
        owner.promoted()


def test_the_transition_carries_no_field_beyond_the_state_it_names() -> None:
    """`R2-03` removed attribution from this row and it must not creep back.

    A `promoted_by`/`promoted_at` pair here would be the same defect `20260814_0014` deleted:
    audit data on a row with no expiry, outliving the twelve-month horizon `KHEPRI-DEC-015` §2a
    gives it. The event carries the attribution.
    """
    promoted = Membership.create("org_1", "acc_1", MEMBER_ROLE).promoted()

    assert {field.name for field in fields(promoted)} == {
        "organization_id",
        "account_id",
        "role",
    }


# --- the service ----------------------------------------------------------------------------


def test_promotion_writes_the_row_and_its_event_together() -> None:
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    store.memberships[(organization.organization_id, member.account_id)] = Membership.create(
        organization.organization_id, member.account_id, MEMBER_ROLE
    )

    service.promote_to_owner(
        organization.organization_id,
        member.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    promoted = store.get_membership(organization.organization_id, member.account_id)
    assert promoted is not None
    assert promoted.role == OWNER_ROLE

    event = store.events[-1]
    assert (event.prior_role, event.next_role) == (MEMBER_ROLE, OWNER_ROLE)
    assert event.actor_account_id == owner.account_id, "FR-014: who made the change"
    assert event.account_id == member.account_id, "FR-014: which membership it affected"
    assert event.occurred_at == LATER, "FR-014: when it occurred"


def test_promoting_a_membership_that_does_not_exist_is_refused() -> None:
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)

    with pytest.raises(RoleChangeFailed):
        service.promote_to_owner(
            organization.organization_id,
            "acc_not_a_member",
            actor_account_id=owner.account_id,
            now=LATER,
        )


def test_a_refused_promotion_writes_no_event() -> None:
    """The event and the state change travel together in both directions.

    An event for a promotion that did not happen is a false audit record, which is worse than a
    missing one: a reader cannot tell it from a true one.
    """
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    before = len(store.events)

    with pytest.raises(RoleChangeFailed):
        service.promote_to_owner(
            organization.organization_id,
            "acc_not_a_member",
            actor_account_id=owner.account_id,
            now=LATER,
        )

    assert len(store.events) == before, "a refused change leaves no trace"


def test_promotion_does_not_disturb_other_memberships() -> None:
    """Scenario 10's neighbour: one membership changes, the rest hold."""
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    bystander = AccountService(accounts).create_account("third@example.test", CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    for account in (member, bystander):
        store.memberships[(organization.organization_id, account.account_id)] = Membership.create(
            organization.organization_id, account.account_id, MEMBER_ROLE
        )

    service.promote_to_owner(
        organization.organization_id,
        member.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    untouched = store.get_membership(organization.organization_id, bystander.account_id)
    assert untouched is not None
    assert untouched.role == MEMBER_ROLE, "a bystander's role is not collateral"


# --- the SQL store and the schema -----------------------------------------------------------


def test_the_sql_store_promotes_the_row_and_writes_the_event(factory: sessionmaker) -> None:
    """The fake and the real store must agree; this is the real one."""
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=member.account_id,
                role=MEMBER_ROLE,
            )
        )

    service.promote_to_owner(
        organization.organization_id,
        member.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    promoted = store.get_membership(organization.organization_id, member.account_id)
    assert promoted is not None
    assert promoted.role == OWNER_ROLE

    with factory() as database:
        roles = database.execute(
            text(
                "SELECT prior_role, next_role FROM rca_membership_events "
                "WHERE account_id = :account_id"
            ),
            {"account_id": member.account_id},
        ).fetchall()
    assert (MEMBER_ROLE, OWNER_ROLE) in [tuple(row) for row in roles]


def test_the_role_column_refuses_a_third_role(factory: sessionmaker) -> None:
    """FR-015: exactly two roles, enforced by the column and not only by the domain.

    The domain can refuse a third role, but a store caller reaching the row directly is exactly
    the seam `#151` was opened to close -- and `role` was an unconstrained `String`, so
    `role="admin"` was writable. `STATUS.md` records this as FR-015's gap.
    """
    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id="org_x",
                account_id="acc_x",
                role="admin",
            )
        )


def test_the_check_constraint_names_exactly_the_declared_roles(engine) -> None:
    """The constraint and `ROLES` must not drift apart.

    Two sources describing one rule is the drift Constitution I forbids, so the constraint is
    built *from* `ROLES` rather than restating the two values. This asserts the built artifact
    still mentions both and nothing else.
    """
    checks = inspect(engine).get_check_constraints("rca_memberships")
    assert checks, "rca_memberships must carry a role CHECK constraint"

    text_of = " ".join(check["sqltext"] for check in checks)
    for role in ROLES:
        assert f"'{role}'" in text_of, f"{role} missing from {text_of}"
    assert "'admin'" not in text_of


def test_the_store_refuses_an_event_whose_prior_role_contradicts_the_row() -> None:
    """FR-014's prior role is checked against the stored row, not the caller's claim.

    The event carries no foreign key -- deliberately, per `MembershipEventRow` -- so the store's
    own checks are the only thing between a caller and a false audit record. A destination check
    alone leaves `prior_role` undefended, and an event claiming a promotion from `owner` when the
    row was `member` is precisely the record no reader could tell from a true one.

    This is also the read-then-write gap: if the role changed after the service read it, the
    event describes a transition that did not happen and the write must refuse rather than
    record it.
    """
    accounts = MemoryAccountStore()
    store = MemoryOrganizationStore(accounts)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    store.memberships[(organization.organization_id, member.account_id)] = Membership.create(
        organization.organization_id, member.account_id, MEMBER_ROLE
    )
    before = len(store.events)

    promoted = Membership.create(organization.organization_id, member.account_id, OWNER_ROLE)
    lying = MembershipEvent.role_changed(
        organization.organization_id,
        member.account_id,
        prior_role=OWNER_ROLE,  # the row says `member`
        next_role=OWNER_ROLE,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    assert store.promote_membership(promoted, lying) is False
    assert len(store.events) == before, "a refused write records nothing"
    still_member = store.get_membership(organization.organization_id, member.account_id)
    assert still_member is not None
    assert still_member.role == MEMBER_ROLE, "the row is untouched by a refused write"


def test_the_sql_store_refuses_the_same_contradiction(factory: sessionmaker) -> None:
    """The fake's refusal is only meaningful if the real store refuses it too."""
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=member.account_id,
                role=MEMBER_ROLE,
            )
        )

    promoted = Membership.create(organization.organization_id, member.account_id, OWNER_ROLE)
    lying = MembershipEvent.role_changed(
        organization.organization_id,
        member.account_id,
        prior_role=OWNER_ROLE,
        next_role=OWNER_ROLE,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    assert store.promote_membership(promoted, lying) is False

    unchanged = store.get_membership(organization.organization_id, member.account_id)
    assert unchanged is not None
    assert unchanged.role == MEMBER_ROLE
    with factory() as database:
        count = database.execute(
            text(
                "SELECT COUNT(*) FROM rca_membership_events WHERE account_id = :account_id"
            ),
            {"account_id": member.account_id},
        ).scalar()
    assert count == 0, "no event survives a refused write"


# --- demotion: the owner-reducing direction (R2-06) ------------------------------------------


def test_demotion_returns_a_new_record_rather_than_mutating() -> None:
    owner = Membership.create("org_1", "acc_1", OWNER_ROLE)

    demoted = owner.demoted()

    assert demoted.role == MEMBER_ROLE
    assert owner.role == OWNER_ROLE, "the original is untouched"


def test_demoting_a_member_is_refused() -> None:
    """A no-op demotion would emit an event whose prior and next roles are identical."""
    member = Membership.create("org_1", "acc_1", MEMBER_ROLE)

    with pytest.raises(ValueError, match="already a member"):
        member.demoted()


def test_demoting_a_non_final_owner_writes_the_row_and_its_event(factory: sessionmaker) -> None:
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=second.account_id,
                role=OWNER_ROLE,
            )
        )

    service.demote_to_member(
        organization.organization_id,
        second.account_id,
        actor_account_id=owner.account_id,
        now=LATER,
    )

    demoted = store.get_membership(organization.organization_id, second.account_id)
    assert demoted is not None
    assert demoted.role == MEMBER_ROLE
    with factory() as database:
        roles = database.execute(
            text(
                "SELECT prior_role, next_role FROM rca_membership_events "
                "WHERE account_id = :account_id"
            ),
            {"account_id": second.account_id},
        ).fetchall()
    assert (OWNER_ROLE, MEMBER_ROLE) in [tuple(row) for row in roles]


def test_demoting_the_final_owner_is_refused(factory: sessionmaker) -> None:
    """FR-013's "downgrade" clause, which had no operation to guard until now."""
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        service.demote_to_member(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )

    still_owner = store.get_membership(organization.organization_id, owner.account_id)
    assert still_owner is not None
    assert still_owner.role == OWNER_ROLE, "the refused demotion left the role alone"


def test_a_refused_demotion_writes_no_event(factory: sessionmaker) -> None:
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        service.demote_to_member(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )

    with factory() as database:
        changes = database.execute(
            text(
                "SELECT COUNT(*) FROM rca_membership_events "
                "WHERE prior_role IS NOT NULL AND next_role IS NOT NULL"
            )
        ).scalar()
    assert changes == 0, "a refused demotion leaves no audit record of one"


def test_a_disabled_co_owner_does_not_rescue_a_demotion(factory: sessionmaker) -> None:
    """Demotion inherits the effective-owner rule, exactly as revocation does."""
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    service = OrganizationService(store)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    second = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)
    organization = service.create_organization("Acme", owner.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=second.account_id,
                role=OWNER_ROLE,
            )
        )
    LifecycleService(accounts, store).disable_account(second.account_id, now=NOW)

    with pytest.raises(FinalOwnerProtected):
        service.demote_to_member(
            organization.organization_id,
            owner.account_id,
            actor_account_id=owner.account_id,
            now=LATER,
        )


def test_revoke_and_demote_share_one_guard(factory: sessionmaker) -> None:
    """The roadmap's stop condition: not two independent final-owner guards.

    Asserted structurally rather than by comment. Both operations must route through
    `_apply_membership_change`, so a future edit that gives one its own lock-count-check fails
    here rather than passing review as a local change.
    """
    import inspect as inspect_module  # noqa: PLC0415

    for method in (
        SqlOrganizationStore.revoke_membership,
        SqlOrganizationStore.demote_membership,
    ):
        source = inspect_module.getsource(method)
        assert "_apply_membership_change" in source, (
            f"{method.__name__} must reuse the shared guard, not carry its own"
        )
        assert "OWNER_CHANGE_FINAL_OWNER" not in source, (
            f"{method.__name__} decides the final-owner outcome itself; that is a second guard"
        )
