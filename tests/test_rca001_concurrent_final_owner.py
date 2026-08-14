"""FR-013 under concurrency: the guard and its write must be one decision (`#155`, `R1-03`).

`test_rca001_final_owner.py` proves the *sequential* contract, and proves it well. This file
proves the part SQLite structurally cannot: that two overlapping owner-reducing operations
cannot both pass the guard.

**Why these live apart from the sequential tests.** They need two genuine PostgreSQL
connections. The rest of the RCA suite runs in-memory SQLite through a `StaticPool`, which
shares one connection across every session, so two transactions cannot overlap in it; SQLite
also has no ``SELECT ... FOR UPDATE`` and SQLAlchemy emits none for that dialect. A locking
test written against that fixture passes while proving nothing, which the roadmap names as a
stop condition ("a SQLite-only proof for a PostgreSQL concurrency contract").

They are marked `concurrency`, so CI fails if they skip -- see
`.github/scripts/require_concurrency_tests.py`. Locally they skip when
`KHEPRI_TEST_DATABASE_URL` is unset.

**Determinism is the whole design here.** A test that merely starts two threads and hopes they
interleave is flaky: it would pass against the broken code whenever the timing happened to be
kind, and a concurrency test that is green half the time against a known defect is worse than
no test. Every test below uses a barrier to force both callers past the guard *before* either
writes, which makes the failure reproduce every run rather than occasionally.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.errors import FinalOwnerProtected
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import OWNER_ROLE, OrganizationService
from khepri.rca.persistence import Base, MembershipRow, SqlAccountStore, SqlOrganizationStore

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
CREDENTIAL = "correct horse battery staple"

pytestmark = pytest.mark.concurrency

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; FR-013 concurrency needs a real PostgreSQL",
)


@pytest.fixture(name="factory")
def factory_fixture():
    """A PostgreSQL session factory whose sessions get independent connections.

    Deliberately not `StaticPool`: the default `QueuePool` hands each session its own
    connection, which is the property every test in this file depends on.
    """
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _two_owner_organization(factory):
    """One organization, two owner-role members, on the supplied PostgreSQL factory.

    A local build rather than `rca_lifecycle_support.two_owner_organization`, because that
    helper returns the fixture's own stores and these tests need to construct a *separate*
    `LifecycleService` per thread -- two services sharing one store instance would be a
    weaker arrangement than two concurrent requests, which is what this file models.
    """
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    first = AccountService(accounts).create_account("first@example.test", CREDENTIAL)
    second = AccountService(accounts).create_account("second@example.test", CREDENTIAL)
    organization = OrganizationService(organizations).create_organization(
        "Acme", first.account_id, now=NOW
    )
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=second.account_id,
                role=OWNER_ROLE,
            )
        )
    return organization, first, second


def _surviving_owners(factory, organization_id: str) -> int:
    return SqlOrganizationStore(factory).count_owners(
        organization_id, excluding_account_id=""
    )


@requires_postgres
def test_concurrent_disablement_of_both_owners_leaves_one(factory) -> None:
    """The `#155` defect, made deterministic.

    Two owners, disabled at the same moment. The barrier forces both callers to finish
    reading account state and counting owners before either writes, which is exactly the
    interleaving the issue describes:

        T1 counts owners excluding A -> 1 (sees B, still enabled)
        T2 counts owners excluding B -> 1 (sees A, still enabled)
        T1 writes A disabled
        T2 writes B disabled          -> zero effective owners

    Against the current non-transactional path both calls succeed and the organization is
    stranded. Against an atomic guard-and-write exactly one succeeds and the other is refused.

    The assertion is on the surviving owner count rather than on which call won: FR-013 does
    not care *which* owner remains, only that one does. Asserting a particular winner would
    make the test fail for a correct implementation that serialized the other way.
    """
    organization, first, second = _two_owner_organization(factory)
    barrier = threading.Barrier(2, timeout=10)

    def disable(account_id: str) -> str:
        # Two independent services over two independent stores: one per simulated request.
        lifecycle = LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
        barrier.wait()
        try:
            lifecycle.disable_account(account_id, now=NOW)
        except FinalOwnerProtected:
            return "refused"
        return "disabled"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(
            pool.map(disable, [first.account_id, second.account_id])
        )

    assert _surviving_owners(factory, organization.organization_id) >= 1, (
        "FR-013: an organization must never reach zero owner-role members"
    )
    assert outcomes == ["disabled", "refused"], (
        "exactly one owner-reducing operation may succeed"
    )


@requires_postgres
def test_concurrent_disablement_of_three_owners_leaves_one(factory) -> None:
    """Three-way contention, because a two-way lock can be right by accident.

    A mechanism that merely serialized *pairs* -- or that happened to make the second caller
    re-read -- could satisfy the two-owner test and still strand an organization when three
    operations contend. Two of the three must be refused.
    """
    organization, first, second = _two_owner_organization(factory)
    accounts = SqlAccountStore(factory)
    third = AccountService(accounts).create_account("third@example.test", CREDENTIAL)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=third.account_id,
                role=OWNER_ROLE,
            )
        )

    barrier = threading.Barrier(3, timeout=10)

    def disable(account_id: str) -> str:
        lifecycle = LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
        barrier.wait()
        try:
            lifecycle.disable_account(account_id, now=NOW)
        except FinalOwnerProtected:
            return "refused"
        return "disabled"

    ids = [first.account_id, second.account_id, third.account_id]
    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = sorted(pool.map(disable, ids))

    assert _surviving_owners(factory, organization.organization_id) >= 1
    assert outcomes == ["disabled", "disabled", "refused"], (
        "two of three may succeed; the last owner must be refused"
    )


@requires_postgres
def test_concurrent_disablement_in_separate_organizations_does_not_serialize(
    factory,
) -> None:
    """Unrelated organizations stay independent (`R1-01` design requirement 3).

    A mechanism that took a table-wide lock would pass every test above and quietly serialize
    every disablement in the system. Two sole owners of two different organizations must both
    be refused on their own merits, and neither refusal may be caused by the other.

    This is the test that fails if someone reaches for `LOCK TABLE` to make the others pass.
    """
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    owner_a = AccountService(accounts).create_account("a@example.test", CREDENTIAL)
    owner_b = AccountService(accounts).create_account("b@example.test", CREDENTIAL)
    OrganizationService(organizations).create_organization("A", owner_a.account_id, now=NOW)
    OrganizationService(organizations).create_organization("B", owner_b.account_id, now=NOW)

    barrier = threading.Barrier(2, timeout=10)

    def disable(account_id: str) -> str:
        lifecycle = LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
        barrier.wait()
        try:
            lifecycle.disable_account(account_id, now=NOW)
        except FinalOwnerProtected:
            return "refused"
        return "disabled"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = sorted(pool.map(disable, [owner_a.account_id, owner_b.account_id]))

    assert outcomes == ["refused", "refused"], (
        "each is the final owner of its own organization; both refusals are independent"
    )


# --- R2-06: the membership write paths, which R1 did not cover -------------------------------


@requires_postgres
def test_concurrent_revocation_of_three_owners_leaves_one(factory) -> None:
    """Three contenders on the revoke path.

    `R1` established that two threads are not a reliable proof of this defect class -- its
    two-owner test passed against the broken code, and only three contenders exposed the race.
    So the revoke path gets three from the start rather than earning the same lesson twice.
    """
    organization, first, second = _two_owner_organization(factory)
    accounts = SqlAccountStore(factory)
    third = AccountService(accounts).create_account("third@example.test", CREDENTIAL)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=third.account_id,
                role=OWNER_ROLE,
            )
        )

    barrier = threading.Barrier(3, timeout=10)

    def revoke(account_id: str) -> str:
        organizations = SqlOrganizationStore(factory)
        barrier.wait()
        try:
            OrganizationService(organizations).revoke_membership(
                organization.organization_id,
                account_id,
                actor_account_id=account_id,
                now=NOW,
            )
        except FinalOwnerProtected:
            return "refused"
        return "revoked"

    ids = [first.account_id, second.account_id, third.account_id]
    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = sorted(pool.map(revoke, ids))

    assert _surviving_owners(factory, organization.organization_id) >= 1
    assert outcomes == ["refused", "revoked", "revoked"], (
        "two of three may succeed; the last owner must be refused"
    )


@requires_postgres
def test_concurrent_demotion_of_three_owners_leaves_one(factory) -> None:
    """Three contenders on the demote path -- `FR-013`'s "downgrade" clause under contention."""
    organization, first, second = _two_owner_organization(factory)
    accounts = SqlAccountStore(factory)
    third = AccountService(accounts).create_account("third@example.test", CREDENTIAL)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=third.account_id,
                role=OWNER_ROLE,
            )
        )

    barrier = threading.Barrier(3, timeout=10)

    def demote(account_id: str) -> str:
        organizations = SqlOrganizationStore(factory)
        barrier.wait()
        try:
            OrganizationService(organizations).demote_to_member(
                organization.organization_id,
                account_id,
                actor_account_id=account_id,
                now=NOW,
            )
        except FinalOwnerProtected:
            return "refused"
        return "demoted"

    ids = [first.account_id, second.account_id, third.account_id]
    with ThreadPoolExecutor(max_workers=3) as pool:
        outcomes = sorted(pool.map(demote, ids))

    assert _surviving_owners(factory, organization.organization_id) >= 1
    assert outcomes == ["demoted", "demoted", "refused"], (
        "two of three may succeed; the last owner must be refused"
    )


@requires_postgres
def test_one_caller_revoking_while_another_demotes_cannot_strand_the_organization(
    factory,
) -> None:
    """The mixed case `R1` did not have, and the reason `R2-06` exists as its own task.

    `R2-01` §5 names this explicitly: revoke and demote are *two different write paths* reducing
    the same count. A guard that serialized each path against itself -- two locks, one per
    operation -- would pass both three-contender tests above and still strand an organization
    here, because neither caller would observe the other.

    Three owners, three different operations: one revoked, one demoted, one disabled. At most
    two may succeed, and whichever is last must be refused. This is the test that fails if the
    three paths ever stop sharing a guard.
    """
    organization, first, second = _two_owner_organization(factory)
    accounts = SqlAccountStore(factory)
    third = AccountService(accounts).create_account("third@example.test", CREDENTIAL)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=organization.organization_id,
                account_id=third.account_id,
                role=OWNER_ROLE,
            )
        )

    barrier = threading.Barrier(3, timeout=10)

    def revoke() -> str:
        organizations = SqlOrganizationStore(factory)
        barrier.wait()
        try:
            OrganizationService(organizations).revoke_membership(
                organization.organization_id,
                first.account_id,
                actor_account_id=first.account_id,
                now=NOW,
            )
        except FinalOwnerProtected:
            return "refused"
        return "applied"

    def demote() -> str:
        organizations = SqlOrganizationStore(factory)
        barrier.wait()
        try:
            OrganizationService(organizations).demote_to_member(
                organization.organization_id,
                second.account_id,
                actor_account_id=second.account_id,
                now=NOW,
            )
        except FinalOwnerProtected:
            return "refused"
        return "applied"

    def disable() -> str:
        lifecycle = LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
        barrier.wait()
        try:
            lifecycle.disable_account(third.account_id, now=NOW)
        except FinalOwnerProtected:
            return "refused"
        return "applied"

    with ThreadPoolExecutor(max_workers=3) as pool:
        running = [pool.submit(revoke), pool.submit(demote), pool.submit(disable)]
        outcomes = sorted(future.result() for future in running)

    assert _surviving_owners(factory, organization.organization_id) >= 1, (
        "three different owner-reducing operations must not between them reach zero owners"
    )
    assert outcomes.count("refused") >= 1, (
        "three operations on three owners: at least one must be refused"
    )


@requires_postgres
def test_the_two_lock_predicates_intersect_on_every_contended_organization(factory) -> None:
    """Why an account-scoped lock and an organization-scoped lock serialize at all.

    The three owner-reducing paths do not lock the same way. `apply_owner_reducing_change` locks
    `WHERE account_id = A AND role = 'owner'`, because disabling one account reduces ownership in
    every organization it owns. `_apply_membership_change` locks
    `WHERE organization_id = O AND role = 'owner'`, because revoking or demoting touches one.

    Those row sets intersect on exactly `{(O, A)}`, and only when `A` holds an owner row in `O`.
    That is not a lucky coincidence, it is the definition of contention here: two owner-reducing
    operations can affect the same organization's owner count **only if** the disabled account is
    itself an owner of that organization -- in which case its row is in both sets and the two
    serialize. When the sets are disjoint the operations cannot affect each other's count, so
    serializing them would be pure contention with no invariant behind it.

    This test pins the load-bearing half: an account owning a *different* organization from the
    one being revoked from does not block, and neither operation corrupts the other's count. If a
    later change made the locks intersect only sometimes, the mixed-race test above would catch
    the dangerous direction and this one catches the wasteful direction.

    Account A owns X. Account B and C own Y. Disable A while revoking B from Y: disjoint locks,
    both must succeed, and Y must still have C.
    """
    accounts = SqlAccountStore(factory)
    organizations = SqlOrganizationStore(factory)
    a = AccountService(accounts).create_account("a@example.test", CREDENTIAL)
    b = AccountService(accounts).create_account("b@example.test", CREDENTIAL)
    c = AccountService(accounts).create_account("c@example.test", CREDENTIAL)
    x = OrganizationService(organizations).create_organization("X", a.account_id, now=NOW)
    y = OrganizationService(organizations).create_organization("Y", b.account_id, now=NOW)
    with factory.begin() as database:
        database.add(
            MembershipRow(
                organization_id=y.organization_id,
                account_id=c.account_id,
                role=OWNER_ROLE,
            )
        )

    barrier = threading.Barrier(2, timeout=10)

    def disable_a() -> str:
        lifecycle = LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
        barrier.wait()
        try:
            lifecycle.disable_account(a.account_id, now=NOW)
        except FinalOwnerProtected:
            return "refused"
        return "applied"

    def revoke_b() -> str:
        barrier.wait()
        try:
            OrganizationService(SqlOrganizationStore(factory)).revoke_membership(
                y.organization_id,
                b.account_id,
                actor_account_id=c.account_id,
                now=NOW,
            )
        except FinalOwnerProtected:
            return "refused"
        return "applied"

    with ThreadPoolExecutor(max_workers=2) as pool:
        running = [pool.submit(disable_a), pool.submit(revoke_b)]
        outcomes = sorted(future.result() for future in running)

    # A is X's only owner, so disabling A must be refused on its own merits -- by X's count, not
    # by anything the revocation did.
    assert outcomes == ["applied", "refused"], (
        "the revocation succeeds (Y keeps C) and the disablement is refused (A is X's last owner)"
    )
    assert _surviving_owners(factory, x.organization_id) >= 1, "X keeps A"
    assert _surviving_owners(factory, y.organization_id) >= 1, "Y keeps C"
