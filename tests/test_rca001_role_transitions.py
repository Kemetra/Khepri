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
from khepri.rca.errors import RoleChangeFailed
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    ROLES,
    Membership,
    OrganizationService,
)
from khepri.rca.persistence import Base, MembershipRow, SqlAccountStore, SqlOrganizationStore
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore

NOW = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 14, 13, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"
EMAIL = "owner@example.test"
OTHER_EMAIL = "member@example.test"


@pytest.fixture(name="factory")
def _factory(tmp_path) -> sessionmaker:
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'roles.db').as_posix()}")
    Base.metadata.create_all(engine)
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


def test_the_check_constraint_names_exactly_the_declared_roles(factory: sessionmaker) -> None:
    """The constraint and `ROLES` must not drift apart.

    Two sources describing one rule is the drift Constitution I forbids, so the constraint is
    built *from* `ROLES` rather than restating the two values. This asserts the built artifact
    still mentions both and nothing else.
    """
    checks = inspect(factory.kw["bind"]).get_check_constraints("rca_memberships")
    assert checks, "rca_memberships must carry a role CHECK constraint"

    text_of = " ".join(check["sqltext"] for check in checks)
    for role in ROLES:
        assert f"'{role}'" in text_of, f"{role} missing from {text_of}"
    assert "'admin'" not in text_of
