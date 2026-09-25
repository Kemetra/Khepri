"""`#526`'s two genuine races, against PostgreSQL (`RCA-005` `FR-123`; `RCA-001` `FR-014`).

`test_w107_deletion_race.py` and `test_rca001_write_interleavings.py` force each interleaving
deterministically on SQLite. What they cannot show is the engine doing the arbitration: the rest of
the suite runs in-memory SQLite through a `StaticPool`, one connection shared by every session, so
two transactions never overlap, and SQLAlchemy emits no `FOR UPDATE` for that dialect. Here two
threads hold two real connections.

Marked `concurrency`: they skip locally when `KHEPRI_TEST_DATABASE_URL` is unset, and CI fails if
they skip there (`.github/scripts/require_concurrency_tests.py`).

**The barrier is placed after each request's own unlocked read and before its write**, so both
requests pass the read every run -- the interleaving each defect needs, not a hoped-for one. Each
contention test repeats `ATTEMPTS` times for the reason `test_rca001_concurrent_final_owner.py`
records: one green run cannot tell a sound lock from a lucky schedule.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import khepri.rca.workspace.persistence  # noqa: F401 -- registers the workspace tables
from khepri.rca import persistence
from khepri.rca.accounts import AccountService
from khepri.rca.errors import AccountOperationFailed, RoleChangeFailed
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, OWNER_ROLE, OrganizationService
from khepri.rca.persistence import (
    AccountRow,
    Base,
    MembershipEventRow,
    MembershipRow,
    SqlAccountStore,
    SqlOrganizationStore,
)
from khepri.rca.workspace.audit import (
    ACTION_VERSION_DELETED,
    OBJECT_VERSION,
    OUTCOME_ALREADY_DELETED,
    OUTCOME_COMPLETED,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.contracts import AdmittedSource, DatasetVersion
from khepri.rca.workspace.persistence import SqlWorkspaceRecordStore
from khepri.rca.workspace.revocation import SqlRevocationLedger
from khepri.runtime.workspace_deletion import DeletionSources, WorkspaceDeletion

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"
ATTEMPTS = 10

SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)

pytestmark = pytest.mark.concurrency

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; these races need a real PostgreSQL",
)


@pytest.fixture(name="factory")
def factory_fixture():
    """A PostgreSQL session factory whose sessions get independent connections (`QueuePool`)."""
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _organization(factory) -> tuple[str, str, str]:
    """One organization and its owner, returning `(organization_id, owner_id, scope)`."""
    owner = AccountService(SqlAccountStore(factory)).create_account(
        "owner@example.test", CREDENTIAL
    )
    organizations = SqlOrganizationStore(factory)
    organization = OrganizationService(organizations).create_organization(
        "Acme", owner.account_id, now=NOW
    )
    scope = organizations.get_scope(organization.organization_id)
    assert scope is not None
    return organization.organization_id, owner.account_id, scope.owner_id


# --- A-14: two overlapping deletions of one version ------------------------------------------


def _deletion(factory, barrier: threading.Barrier) -> WorkspaceDeletion:
    """One request's deletion service, over its own stores.

    The content step is replaced by the barrier: it sits after `delete_version`'s unlocked read and
    before its unit of work, which is exactly the window the defect needs. Replacing it also keeps
    the `RRA` content path -- which has its own tests -- out of this race.
    """
    service = WorkspaceDeletion(
        DeletionSources(
            store=SqlWorkspaceRecordStore(factory),
            audit=SqlWorkspaceAuditStore(factory),
            ledger=SqlRevocationLedger(factory),
            content=None,
            factory=factory,
        )
    )
    service._end_derived_content = lambda _version, _now: barrier.wait()  # type: ignore[method-assign]
    return service


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_overlapping_deletions_end_the_version_once(factory, attempt: int) -> None:
    """`FR-123`: one `completed`, one `already_deleted` -- never two endings."""
    _organization_id, owner_id, scope = _organization(factory)
    version = SqlWorkspaceRecordStore(factory).add_dataset_version(
        DatasetVersion.create(owner_id=scope, source=SOURCE, now=NOW)
    )
    barrier = threading.Barrier(2, timeout=10)

    def delete(_: int) -> bool:
        outcome = _deletion(factory, barrier).delete_version(
            scope, version.version_id, actor_account_id=owner_id, now=NOW
        )
        return outcome.deleted

    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = sorted(pool.map(delete, range(2)))

    assert answers == [False, True], "both overlapping deletions answered deleted=True"
    outcomes = sorted(
        event.outcome
        for event in SqlWorkspaceAuditStore(factory).events_for_scope(scope)
        if event.action == ACTION_VERSION_DELETED
    )
    assert outcomes == sorted([OUTCOME_ALREADY_DELETED, OUTCOME_COMPLETED])
    assert SqlRevocationLedger(factory).is_revoked(OBJECT_VERSION, version.version_id, scope)


# --- D-03: promotion against a concurrent promotion or revocation ----------------------------


class _PromotesAfterBarrier(SqlOrganizationStore):
    """The real store, whose promotion write waits until the other request has read too."""

    def __init__(self, factory, barrier: threading.Barrier) -> None:
        super().__init__(factory)
        self._barrier = barrier

    def promote_membership(self, membership, event) -> bool:
        self._barrier.wait()
        return super().promote_membership(membership, event)


def _organization_with_member(factory) -> tuple[str, str, str]:
    organization_id, owner_id, _scope = _organization(factory)
    member = AccountService(SqlAccountStore(factory)).create_account(
        "member@example.test", CREDENTIAL
    )
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization_id, account_id=member.account_id, role=MEMBER_ROLE
            )
        )
    return organization_id, owner_id, member.account_id


def _promotion_events(factory, account_id: str) -> int:
    with factory() as database:
        return database.scalar(
            select(func.count())
            .select_from(MembershipEventRow)
            .where(
                MembershipEventRow.account_id == account_id,
                MembershipEventRow.prior_role == MEMBER_ROLE,
                MembershipEventRow.next_role == OWNER_ROLE,
            )
        )


def _promote(store, organization_id: str, owner_id: str, member_id: str) -> str:
    try:
        OrganizationService(store).promote_to_owner(
            organization_id, member_id, actor_account_id=owner_id, now=NOW
        )
    except RoleChangeFailed:
        return "refused"
    return "promoted"


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_two_concurrent_promotions_record_one_transition(factory, attempt: int) -> None:
    """`FR-014`: one role change, one event. Both requests read `member`; one promotes."""
    organization_id, owner_id, member_id = _organization_with_member(factory)
    barrier = threading.Barrier(2, timeout=10)

    def promote(_: int) -> str:
        return _promote(
            _PromotesAfterBarrier(factory, barrier), organization_id, owner_id, member_id
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(promote, range(2)))

    assert outcomes == ["promoted", "refused"]
    assert _promotion_events(factory, member_id) == 1


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_a_promotion_racing_a_revocation_refuses_rather_than_raising(factory, attempt: int) -> None:
    """Before `#526` a revocation committed under the promotion's feet raised `StaleDataError`.
    Whichever wins, the promotion answers `promoted` or `refused`, and an event exists only for a
    promotion that happened."""
    organization_id, owner_id, member_id = _organization_with_member(factory)
    barrier = threading.Barrier(2, timeout=10)

    def revoke() -> str:
        barrier.wait()
        OrganizationService(SqlOrganizationStore(factory)).revoke_membership(
            organization_id, member_id, actor_account_id=owner_id, now=NOW
        )
        return "revoked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        promoting = pool.submit(
            _promote, _PromotesAfterBarrier(factory, barrier), organization_id, owner_id, member_id
        )
        revoking = pool.submit(revoke)
        promoted = promoting.result()
        assert revoking.result() == "revoked"

    assert promoted in {"promoted", "refused"}
    assert _promotion_events(factory, member_id) == (1 if promoted == "promoted" else 0)
    assert SqlOrganizationStore(factory).get_membership(organization_id, member_id) is None


# --- #434 §6: an enable landing inside the purge's eligibility window ------------------------

#: How long the purge holds its window open for the enable. Under the row lock the enable cannot
#: finish inside it, so the wait always runs out; without the lock it finishes almost at once.
ENABLE_WINDOW_SECONDS = 0.5
PURGE_HORIZON = NOW + timedelta(days=1)


def _disabled_account(factory) -> str:
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account("purge@example.test", CREDENTIAL)
    LifecycleService(accounts, SqlOrganizationStore(factory)).disable_account(
        account.account_id, now=NOW
    )
    return account.account_id


def _enable(factory, account_id: str, checked: threading.Event, done: threading.Event) -> str:
    checked.wait(timeout=10)
    try:
        LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory)).enable_account(
            account_id
        )
    except AccountOperationFailed:
        return "refused"
    finally:
        done.set()
    return "enabled"


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_an_enable_inside_the_purge_window_never_leaves_an_enabled_tombstone(
    factory, attempt: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`KHEPRI-DEC-015` §2b: the purge is irreversible, so it must not land on an enabled row.

    The purge checks eligibility, then holds its transaction open while `enable_account` runs.
    With `account_for_update` the enable's `UPDATE` waits on the row lock, and once the purge
    commits `_apply_account`'s `email IS NOT NULL` predicate refuses it. Without the lock the
    enable commits inside the window and the purge then nulls the identity of an enabled account
    -- the tombstone `#434` §6 describes, which SQLite's shared connection cannot produce.
    """
    account_id = _disabled_account(factory)
    checked, done = threading.Event(), threading.Event()
    real_lock = persistence.take_identity_lock

    def lock_then_hold_the_window(database, canonical_address: str) -> bool:
        taken = real_lock(database, canonical_address)
        checked.set()
        done.wait(timeout=ENABLE_WINDOW_SECONDS)
        return taken

    monkeypatch.setattr(persistence, "take_identity_lock", lock_then_hold_the_window)

    with ThreadPoolExecutor(max_workers=2) as pool:
        purging = pool.submit(
            SqlAccountStore(factory).purge_if_still_eligible, account_id, PURGE_HORIZON
        )
        enabling = pool.submit(_enable, factory, account_id, checked, done)
        answers = (purging.result(), enabling.result())

    with factory() as database:
        row = database.get(AccountRow, account_id)
    assert answers == (True, "refused"), "the enable must wait for the purge, then be refused"
    assert row is not None and row.email is None and row.disabled_at is not None
