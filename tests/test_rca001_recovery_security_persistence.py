"""SQL persistence evidence for content-free recovery security events."""

from __future__ import annotations

from sqlalchemy import inspect as sqla_inspect

from khepri.rca.accounts import AccountService
from khepri.rca.persistence import SqlAccountStore
from tests.rca_lifecycle_support import CREDENTIAL, NOW, build_factory


def test_the_row_has_exactly_the_content_free_event_columns() -> None:
    from khepri.rca.recovery_security_persistence import RecoverySecurityEventRow

    assert {column.key for column in sqla_inspect(RecoverySecurityEventRow).columns} == {
        "event_key_hash",
        "account_id",
        "occurred_at",
    }


def test_append_once_refuses_a_key_bound_to_another_account() -> None:
    from khepri.rca.recovery_security import RecoverySecurityEvent
    from khepri.rca.recovery_security_persistence import SqlRecoverySecurityEventStore

    factory = build_factory()
    store = SqlRecoverySecurityEventStore(factory)
    accounts = AccountService(SqlAccountStore(factory))
    first_account = accounts.create_account("first@example.test", CREDENTIAL)
    second_account = accounts.create_account("second@example.test", CREDENTIAL)
    first = RecoverySecurityEvent.record(first_account.account_id, "attempt-1", now=NOW)
    foreign = RecoverySecurityEvent.record(second_account.account_id, "attempt-1", now=NOW)

    assert store.append_once(first) == first
    assert store.append_once(first) == first
    assert store.append_once(foreign) is None
    assert store.get_event_count() == 1
