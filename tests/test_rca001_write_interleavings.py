"""Two RCA store writes that a concurrent change could break (`#526` D-03, D-05).

**D-03, `promote_membership` (`RCA-001` `FR-014`).** The store read the membership row and then
wrote the new role through the ORM. A revocation committed between the two left the ORM's `UPDATE`
matching no row, which SQLAlchemy raises as `StaleDataError` -- escaping the documented `False`. A
second promotion committed between the two left the row already `owner`, and this call still wrote
a second `member -> owner` event describing a transition that did not happen.

**D-05, `add_session` (`RCA-001` `FR-003`, `FR-004`).** The store checked for the identifier and
then inserted. Its sibling `link_external_identity` catches the constraint that arbitrates a clash;
this did not, so a clash reached the caller as a driver error rather than the documented `False`
that `SessionService.create` turns into its uniform refusal.

**How the interleaving is forced on SQLite.** A `before_cursor_execute` listener runs the
"concurrent" statement on the same connection immediately before the store's own write reaches the
driver -- after every read the store made. The race is then reproduced every run rather than
hoped for. The genuine two-connection race for D-03 runs against PostgreSQL in CI
(`test_concurrent_persistence_postgres.py`).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import AuthenticationFailed, RoleChangeFailed
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import (
    MembershipEventRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    factory_fixture,
)

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 23, 13, 0, tzinfo=UTC)
MEMBER_EMAIL = "member@example.test"


def _just_before(factory: sessionmaker, table_prefix: str, interleave) -> None:
    """Run `interleave(cursor, statement, parameters)` once, immediately before the first write
    whose SQL starts with `table_prefix`."""
    engine = factory.kw["bind"]
    fired: list[bool] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _concurrently(_conn, cursor, statement, parameters, _context, _many) -> None:
        if fired or not statement.lstrip().upper().startswith(table_prefix):
            return
        fired.append(True)
        interleave(cursor, statement, parameters)


def _organization_with_member(factory: sessionmaker) -> tuple[str, str, str]:
    accounts = SqlAccountStore(factory)
    owner = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    member = AccountService(accounts).create_account(MEMBER_EMAIL, CREDENTIAL)
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=member.account_id,
                role=MEMBER_ROLE,
            )
        )
    return organization.organization_id, owner.account_id, member.account_id


def _role_change_events(factory: sessionmaker, account_id: str) -> int:
    with factory() as database:
        return database.scalar(
            select(func.count())
            .select_from(MembershipEventRow)
            .where(MembershipEventRow.account_id == account_id)
        )


def _promote(factory: sessionmaker, organization_id: str, owner_id: str, member_id: str) -> None:
    OrganizationService(SqlOrganizationStore(factory)).promote_to_owner(
        organization_id, member_id, actor_account_id=owner_id, now=LATER
    )


# --- D-03 ------------------------------------------------------------------------------------


def test_a_promotion_overtaken_by_a_revocation_is_an_ordinary_refusal(factory) -> None:
    organization_id, owner_id, member_id = _organization_with_member(factory)
    events_before = _role_change_events(factory, member_id)

    def revoke(cursor, _statement, _parameters) -> None:
        cursor.execute(
            "DELETE FROM rca_memberships WHERE organization_id = ? AND account_id = ?",
            (organization_id, member_id),
        )

    _just_before(factory, "UPDATE RCA_MEMBERSHIPS", revoke)

    with pytest.raises(RoleChangeFailed):
        _promote(factory, organization_id, owner_id, member_id)

    assert _role_change_events(factory, member_id) == events_before


def test_a_promotion_overtaken_by_another_writes_no_second_event(factory) -> None:
    organization_id, owner_id, member_id = _organization_with_member(factory)
    events_before = _role_change_events(factory, member_id)

    def promoted_elsewhere(cursor, _statement, _parameters) -> None:
        cursor.execute(
            "UPDATE rca_memberships SET role = ? WHERE organization_id = ? AND account_id = ?",
            (OWNER_ROLE, organization_id, member_id),
        )

    _just_before(factory, "UPDATE RCA_MEMBERSHIPS", promoted_elsewhere)

    with pytest.raises(RoleChangeFailed):
        _promote(factory, organization_id, owner_id, member_id)

    assert _role_change_events(factory, member_id) == events_before, (
        "an event recorded a member -> owner transition this call did not make"
    )


def test_an_uncontended_promotion_still_writes_its_row_and_one_event(factory) -> None:
    organization_id, owner_id, member_id = _organization_with_member(factory)
    events_before = _role_change_events(factory, member_id)

    _promote(factory, organization_id, owner_id, member_id)

    membership = SqlOrganizationStore(factory).get_membership(organization_id, member_id)
    assert membership is not None and membership.role == OWNER_ROLE
    assert _role_change_events(factory, member_id) == events_before + 1


# --- D-05 ------------------------------------------------------------------------------------


def _replay(cursor, statement, parameters) -> None:
    """The same session row, committed first by a concurrent writer."""
    cursor.execute(statement, parameters)


def test_a_session_insert_that_loses_a_clash_returns_false(factory) -> None:
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)
    from khepri.rca.sessions import Session

    issued = Session.issue(account.account_id, now=NOW, lifetime=LATER - NOW)
    _just_before(factory, "INSERT INTO RCA_SESSIONS", _replay)

    assert SqlSessionStore(factory).add_session(issued.session) is False


def test_the_clash_reaches_the_caller_as_the_uniform_refusal(factory) -> None:
    account = AccountService(SqlAccountStore(factory)).create_account(EMAIL, CREDENTIAL)
    _just_before(factory, "INSERT INTO RCA_SESSIONS", _replay)

    with pytest.raises(AuthenticationFailed):
        SessionService(SqlSessionStore(factory), lifetime=LATER - NOW).create(
            account.account_id, now=NOW
        )
