"""FR-014: every membership change is attributable, and expires on its own horizon (`#150`).

`Membership` records a current role and cannot express a transition, so attribution lives in an
append-only event table. `KHEPRI-DEC-015` §82 fixes the record's content — opaque actor, opaque
membership identity, prior role, next role, timestamp — and its horizon at twelve months.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.lifecycle import RETENTION_MONTHS
from khepri.rca.organizations import (
    MEMBER_ROLE,
    OWNER_ROLE,
    ROLES,
    MembershipEvent,
    OrganizationService,
)
from khepri.rca.persistence import (
    MembershipEventRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    factory_fixture,
)

ACTOR = "acc_actor"
SUBJECT = "acc_subject"
ORG = "org_example"


# --- the event kind is carried by nullability ---------------------------------------------


def test_a_creation_event_has_no_prior_role() -> None:
    event = MembershipEvent.created(ORG, SUBJECT, OWNER_ROLE, actor_account_id=ACTOR, now=NOW)

    assert event.prior_role is None
    assert event.next_role == OWNER_ROLE


def test_a_revocation_event_has_no_next_role() -> None:
    event = MembershipEvent.revoked(
        ORG, SUBJECT, prior_role=MEMBER_ROLE, actor_account_id=ACTOR, now=NOW
    )

    assert event.prior_role == MEMBER_ROLE
    assert event.next_role is None


def test_a_role_change_carries_both_roles() -> None:
    event = MembershipEvent.role_changed(
        ORG,
        SUBJECT,
        prior_role=MEMBER_ROLE,
        next_role=OWNER_ROLE,
        actor_account_id=ACTOR,
        now=NOW,
    )

    assert (event.prior_role, event.next_role) == (MEMBER_ROLE, OWNER_ROLE)


def test_every_event_kind_is_distinguishable_from_the_role_pair_alone() -> None:
    """The property that makes an `event_type` column unnecessary — and unsafe to add.

    A type column could contradict the roles; these three shapes cannot. If a future kind is not
    distinguishable here, that is the moment to add the column, and this test is where it fails.
    """
    kinds = {
        (event.prior_role is None, event.next_role is None)
        for event in (
            MembershipEvent.created(ORG, SUBJECT, OWNER_ROLE, actor_account_id=ACTOR, now=NOW),
            MembershipEvent.revoked(
                ORG, SUBJECT, prior_role=OWNER_ROLE, actor_account_id=ACTOR, now=NOW
            ),
            MembershipEvent.role_changed(
                ORG,
                SUBJECT,
                prior_role=OWNER_ROLE,
                next_role=MEMBER_ROLE,
                actor_account_id=ACTOR,
                now=NOW,
            ),
        )
    }

    assert len(kinds) == 3, "each event kind must have a distinct nullability signature"


def test_event_identifiers_are_opaque_and_unique() -> None:
    made = [
        MembershipEvent.created(ORG, SUBJECT, OWNER_ROLE, actor_account_id=ACTOR, now=NOW)
        for _ in range(50)
    ]

    assert len({event.event_id for event in made}) == 50
    assert all(event.event_id.startswith("mev_") for event in made)


# --- FR-040: the record is content-free ----------------------------------------------------


def test_the_event_carries_no_field_beyond_the_governed_set() -> None:
    """`KHEPRI-DEC-015` §82 enumerates the content exactly. A new field is a retention change.

    Asserted as an equality rather than a subset: a test that only checked for the *absence* of
    an email would pass while some other identifying field was added.
    """
    assert set(MembershipEvent.__slots__) == {
        "event_id",
        "organization_id",
        "account_id",
        "actor_account_id",
        "prior_role",
        "next_role",
        "occurred_at",
    }


# --- FR-015: exactly two roles -------------------------------------------------------------


def test_exactly_two_roles_exist() -> None:
    assert ROLES == (OWNER_ROLE, MEMBER_ROLE)
    assert len(set(ROLES)) == 2


# --- organization creation emits its event, atomically -------------------------------------


def test_creating_an_organization_emits_one_creation_event(factory: sessionmaker) -> None:
    """FR-014 covers "every change to a membership", and the first one is a change."""
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)

    organization = OrganizationService(store).create_organization(
        "Acme", owner.account_id, now=NOW
    )

    with factory() as database:
        rows = database.scalars(select(MembershipEventRow)).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.organization_id == organization.organization_id
    assert row.account_id == owner.account_id
    assert row.actor_account_id == owner.account_id, "the creator attributes their own membership"
    assert row.prior_role is None, "a creation has no prior role"
    assert row.next_role == OWNER_ROLE


def test_a_refused_creation_writes_no_event(factory: sessionmaker) -> None:
    """The event joins the creation transaction, so a rollback takes it too.

    An event written outside that transaction could describe a creation that never happened,
    which is worse than a missing event: it is a false audit record.
    """
    accounts = SqlAccountStore(factory)
    store = SqlOrganizationStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    OrganizationService(store).create_organization("First", owner.account_id, now=NOW)

    # An account that does not exist violates the membership foreign key.
    with pytest.raises(Exception):  # noqa: B017, PT011 -- any refusal; the assertion is below
        OrganizationService(store).create_organization("Second", "acc_absent", now=NOW)

    with factory() as database:
        surviving = database.execute(
            select(func.count()).select_from(MembershipEventRow)
        ).scalar()
    assert surviving == 1, "only the successful creation left an event"


# --- retention ordering --------------------------------------------------------------------


MEMBERSHIP_EVENT_RETENTION_MONTHS = 12


def test_the_account_horizon_outlasts_the_audit_horizon() -> None:
    """`KHEPRI-DEC-015` justifies 24 months partly as outlasting the 12-month audit horizon,
    "so that audit evidence never outlives the subject it refers to".

    That is a relationship between two independently scheduled sweepers, and nothing else
    enforces it. Shortening the account horizon below the audit horizon would leave events
    pointing at rows that no longer exist, and would do so silently.
    """
    assert RETENTION_MONTHS > MEMBERSHIP_EVENT_RETENTION_MONTHS


def test_an_event_is_purgeable_only_once_its_horizon_elapses() -> None:
    event = MembershipEvent.created(ORG, SUBJECT, OWNER_ROLE, actor_account_id=ACTOR, now=NOW)

    assert not event.is_purgeable_at(NOW.replace(year=NOW.year - 1))
    assert event.is_purgeable_at(NOW), "the horizon instant itself qualifies"
    assert event.is_purgeable_at(NOW.replace(year=NOW.year + 1))


# --- the table carries no foreign key ------------------------------------------------------


def test_the_event_table_has_no_foreign_key(factory: sessionmaker) -> None:
    """Deliberate, and the reason is an ordering one rather than a content one.

    A RESTRICT foreign key onto `rca_accounts` would make the account purge fail while any event
    referenced it — inverting the horizon relationship above, in which the event expires first
    and the tombstone survives until it does. A foreign key onto `rca_memberships` would stop
    revocation removing the membership its own event describes.
    """
    keys = inspect(factory.kw["bind"]).get_foreign_keys("rca_membership_events")

    assert keys == [], f"the event table must carry no foreign key, found: {keys}"
