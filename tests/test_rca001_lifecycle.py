"""The FR-008 session chokepoint and composition with #151's construction rule."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from khepri.rca.accounts import AccountService
from khepri.rca.errors import (
    AccountOperationFailed,
)
from khepri.rca.lifecycle import RETENTION_DAYS, AccountRetentionSweeper, LifecycleService
from tests.rca_fakes import MemoryAccountStore, MemoryOrganizationStore
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
    memory_stack,
)

# --- FR-008 clause 2: the chokepoint the session slice must use -------------------------


def test_assert_account_active_refuses_disabled_purged_and_missing() -> None:
    """The chokepoint FR-008's session clause requires, shipped before its caller exists.

    All three refusals are the same exception with the same message (FR-004): a disabled
    account, a tombstone, and an account that never existed are indistinguishable here.
    """
    accounts = MemoryAccountStore()
    lifecycle = LifecycleService(accounts, MemoryOrganizationStore())
    live = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    doomed = AccountService(accounts).create_account(OTHER_EMAIL, CREDENTIAL)

    assert lifecycle.assert_account_active(live.account_id).account_id == live.account_id

    lifecycle.disable_account(doomed.account_id, now=NOW)
    messages = []
    for account_id in (doomed.account_id, "acc_never_existed"):
        with pytest.raises(AccountOperationFailed) as caught:
            lifecycle.assert_account_active(account_id)
        messages.append(str(caught.value))

    AccountRetentionSweeper(accounts).sweep(now=NOW + timedelta(days=RETENTION_DAYS + 1))
    with pytest.raises(AccountOperationFailed) as caught:
        lifecycle.assert_account_active(doomed.account_id)
    messages.append(str(caught.value))

    assert len(set(messages)) == 1, "disabled, purged, and missing must be indistinguishable"


# --- composition with #151 ---------------------------------------------------------------


def test_lifecycle_state_cannot_be_changed_by_copying() -> None:
    """#149 and #151 compose: re-enabling by field substitution is refused.

    `dataclasses.replace(account, disabled_at=None)` is the obvious way to write a re-enable
    and would bypass every guard in `LifecycleService` — including the FR-013 check. The
    construction rule from #151 blocks it, which is exactly the trap that slice was closed to
    prevent this one from walking into.
    """
    accounts = MemoryAccountStore()
    account = AccountService(accounts).create_account(EMAIL, CREDENTIAL)
    disabled = LifecycleService(accounts, MemoryOrganizationStore()).disable_account(
        account.account_id, now=NOW
    )

    with pytest.raises(TypeError, match="create\\(\\) or _from_storage\\(\\)"):
        dataclasses.replace(disabled, disabled_at=None)
