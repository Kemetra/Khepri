"""`R4-07` -- the invitation races, against real PostgreSQL.

`test_rca001_invitation_failure_matrix.py` proves the sequential contract. This file proves the
parts SQLite structurally cannot: the identity advisory lock (`R4-01` §8.2) serializes issuance
against an identity purge, and revocation cannot race redemption into two terminal states.

**Why these live apart.** They need two genuine connections. The rest of the RCA suite runs
in-memory SQLite through a `StaticPool`, which shares one connection across every session, so two
transactions cannot overlap in it -- and SQLite has no `pg_advisory_xact_lock` at all, so
`take_identity_lock` declines there by dialect. A lock test written against that fixture passes
while proving nothing, which the roadmap names as a stop condition. Marked `concurrency`, so CI
fails if they skip (`.github/scripts/require_concurrency_tests.py`); locally they skip when
`KHEPRI_TEST_DATABASE_URL` is unset.

## The issuance-first case asserts blocking, not the outcome

§7.1, made rigorous in `#220` after review on `#210` found the defect. "No invitation open
afterwards" is what an implementation with **no lock at all** produces whenever issuance happens to
commit before the purge's delete begins -- which is most of the time on an unloaded test database.
So a conforming-looking test would pass against the exact defect the lock exists to prevent, and
would do so reliably enough to look trustworthy.

**Blocking is the only observable that distinguishes a held lock from an absent one**, so that is
what `test_the_purge_blocks_on_a_held_issuance_lock` asserts, via `pg_locks`. And because "B
blocked" alone could be any lock, `test_a_different_address_does_not_block` is its control: the same
sequence at a *different* address, where the keys differ and B must **not** block. The pair is what
identifies the key as identity-derived rather than incidental.

## These were not run locally, and that is stated rather than implied

The Windows-to-WSL PostgreSQL path on the development machine stalls inside psycopg's connection
handshake (`psycopg.waiting.wait_conn`) even though the TCP socket opens, so the container that is
reachable for a single query is not reachable for the repeated connections these tests need.
Investigated to root cause with `faulthandler` rather than guessed at, and it is environmental: no
DDL ever reaches the server, and `pg_stat_activity` shows zero sessions during the stall.

The consequence for the reader: **CI is the first place these execute.** Two things compensate, and
neither is "trust the timing". Each blocking assertion carries a **control** that must behave
differently -- see `test_a_different_address_does_not_block` -- so a green run tells a real
identity-keyed lock from any lock at all. And every assertion message states what its failure
means, because whoever reads a CI failure will not have the local reproduction that explains it.

## The purge-first case is a positive assertion of accepted behaviour

§8.2 records the owner accepting that residual on 2026-08-18: an `issue` beginning after the purge
commits finds no address on the tombstone, takes no lock, and inserts an open invitation after the
cascade has run. §7.1's table requires this asserted as the *documented* outcome rather than
`xfail`ed, "so if it ever **stops** holding, something changed and the suite says so".

The closability claim is the `xfail(strict=True)` in `test_rca001_identity_advisory_lock.py`. This
file asserts the behaviour; that one records that it is not closed.
"""

from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.errors import InvitationOperationFailed
from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_service import InvitationService
from khepri.rca.invitations import InvitationOffer, parse_token
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.organizations import MEMBER_ROLE, OrganizationService
from khepri.rca.persistence import (
    Base,
    SqlAccountStore,
    SqlOrganizationStore,
    identity_lock_key,
)
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_service import SessionService

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=7)
LIFETIME = timedelta(hours=12)
CREDENTIAL = "correct horse battery staple"
PURGE_HORIZON = NOW + timedelta(days=800)

#: How long to let the blocked purge sit before concluding it is genuinely waiting.
#:
#: `pg_locks` is the primary evidence -- it names the key and the waiting process -- and this bounds
#: how long the test waits for that row to appear. Generous rather than tight: a slow CI runner
#: making this flake would be a test failing for a reason unrelated to the contract.
BLOCK_TIMEOUT_SECONDS = 10.0

pytestmark = pytest.mark.concurrency

# Fewer repeats than `test_rca001_concurrent_final_owner.py`'s ten, deliberately. That file repeats
# because its contract depends on *interleaving*, and a lucky schedule can hide a defect -- `R1`
# measured one passing two runs in three. These tests assert the lock directly: the blocking test
# reads `pg_locks` for a waiting backend, which is a state rather than a race outcome, so repetition
# adds runtime without adding evidence. Three keeps a flake visible while staying inside the job's
# ten-minute budget, which a first version exceeded.
ATTEMPTS = 3

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason=(
        "KHEPRI_TEST_DATABASE_URL is unset; the identity advisory lock is inert on SQLite "
        "(`take_identity_lock` declines by dialect), so these contracts need real PostgreSQL"
    ),
)


@pytest.fixture(name="factory")
def factory_fixture():
    """A PostgreSQL session factory whose sessions get independent connections.

    Deliberately not `StaticPool`, following the sibling concurrency file: the default `QueuePool`
    hands each session its own connection, which is the property every test here depends on.
    """
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _account(factory, label: str) -> tuple[str, str]:
    email = f"r407c-{label}@example.test"
    account = AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL)
    return account.account_id, email


def _organization(factory, label: str) -> tuple[str, str]:
    owner_id, _ = _account(factory, f"owner-{label}")
    organization = OrganizationService(SqlOrganizationStore(factory)).create_organization(
        f"Acme {label}", owner_id, now=NOW
    )
    return organization.organization_id, owner_id


def _offer(organization_id: str, issued_by: str, target: str) -> InvitationOffer:
    return InvitationOffer(
        organization_id=organization_id,
        intended_role=MEMBER_ROLE,
        target_identity=target,
        issued_by=issued_by,
    )


def _disable(factory, account_id: str) -> None:
    accounts = SqlAccountStore(factory)
    live = accounts.get_account(account_id)
    assert live is not None
    assert accounts.save_account(live.disabled(now=NOW))


class _Gate(NamedTuple):
    """The two events that sequence a holder thread against its observer."""

    holding: threading.Event
    release: threading.Event


class _Row(NamedTuple):
    """What `_insert_invitation_row` needs, grouped so the helper stays under five parameters."""

    invitation_id: str
    organization_id: str
    issued_by: str
    address: str


def _insert_invitation_row(
    database,
    *,
    invitation_id: str,
    organization_id: str,
    issued_by: str,
    address: str,
) -> None:
    """Write an open invitation row on the caller's connection, bypassing `issue`.

    **Raw SQL on a supplied connection, deliberately.** `InvitationService.issue` opens its own
    transaction and takes the identity advisory lock, so calling it from inside a transaction that
    already holds that key deadlocks the caller against itself -- which cost two CI runs before it
    was found. This writes the same row the service would, on the connection that holds the lock, so
    the row commits with it.

    The verifier columns are filler: nothing in the blocking test verifies a secret, and
    `ck_rca_invitation_verifier_whole` only requires the five to be present or absent together.
    """
    database.execute(
        text(
            "INSERT INTO rca_invitations (invitation_id, organization_id, intended_role, "
            "target_identity, secret_salt, secret_digest, kdf_n, kdf_r, kdf_p, "
            "expires_at, issued_by, issued_at) "
            "VALUES (:iid, :org, :role, :target, :salt, :digest, :n, :r, :p, "
            ":expires, :issued_by, :issued_at)"
        ),
        {
            "iid": invitation_id,
            "org": organization_id,
            "role": MEMBER_ROLE,
            "target": address,
            "salt": b"0" * 16,
            "digest": b"0" * 32,
            "n": 2**14,
            "r": 8,
            "p": 1,
            "expires": LATER,
            "issued_by": issued_by,
            "issued_at": NOW,
        },
    )


def _hold_lock_and_write(
    factory,
    gate: _Gate,
    key: int,
    row: _Row,
) -> None:
    """Hold the identity lock, then write an invitation row on the *same* connection.

    **`InvitationService.issue` cannot be called from in here, and the first version's attempt to
    deadlocked the whole run.** `issue` writes through `add_invitation`, which opens its own
    transaction on its own connection and takes this same advisory key -- so calling it while this
    transaction holds the key means waiting on a lock this thread already holds, forever, with no
    SQL error and no output. Two rounds of CI cancellation traced to this.

    What that gives up is exercising `issue`'s own acquisition, and that is the right division
    rather than a gap: this file proves the lock **serializes**, and
    `test_rca001_identity_advisory_lock.py`'s source assertion proves **both paths take it**.

    Module-level rather than a closure inside the test, so the test body stays small enough for
    CodeScene's Large Method rule -- a nested function counts toward the enclosing method's size.
    """
    with factory.begin() as database:
        database.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        gate.holding.set()
        gate.release.wait(timeout=BLOCK_TIMEOUT_SECONDS * 2)
        _insert_invitation_row(
            database,
            invitation_id=row.invitation_id,
            organization_id=row.organization_id,
            issued_by=row.issued_by,
            address=row.address,
        )


def _advisory_rows(factory, key: int) -> list[tuple[bool, int]]:
    """Every `pg_locks` row for the advisory `key`, as `(granted, pid)`.

    Read from `pg_locks` rather than inferred from a timeout, because a timeout alone cannot
    distinguish "blocked on this key" from "slow for another reason".

    **The two halves are computed in Python, and the SQL casts nothing.** PostgreSQL splits a bigint
    advisory key across `classid` (high 32 bits) and `objid` (low 32 bits). The first version
    reassembled them in SQL with `:key::bigint`, which is a **syntax error**: SQLAlchemy
    substitutes `:key` and PostgreSQL is then left with a stray `::`. It failed as
    `syntax error at or near ":"`, and because the failure raised inside the polling loop the thread
    holding the advisory lock never reached its release -- so the whole CI job deadlocked and was
    cancelled at ten minutes. Found in the PostgreSQL server log, which is the only place the error
    surfaced.

    Two lessons kept in the code rather than in a commit message: a `text()` parameter and a
    PostgreSQL cast cannot share a token, and a polling helper that can raise must not be the only
    thing that releases a lock -- see the `try/finally` in the test below.
    """
    high = (key >> 32) & 0xFFFFFFFF
    low = key & 0xFFFFFFFF
    with factory() as database:
        return [
            (granted, pid)
            for granted, pid in database.execute(
                text(
                    "SELECT granted, pid FROM pg_locks "
                    "WHERE locktype = 'advisory' AND classid = :high AND objid = :low"
                ),
                {"high": high, "low": low},
            ).all()
        ]


def _holds(factory, key: int) -> bool:
    """Whether the lock for `key` is held by someone (granted)."""
    return any(granted for granted, _ in _advisory_rows(factory, key))


def _waiting_on(factory, key: int) -> bool:
    """Whether some backend is *waiting* on the advisory lock for `key`."""
    return any(not granted for granted, _ in _advisory_rows(factory, key))


def _wait_until_blocked(factory, key: int) -> bool:
    """Poll `pg_locks` until a backend is waiting on `key`, or the budget runs out.

    Condition-based rather than a fixed sleep: a sleep long enough for a slow runner is dead time on
    a fast one, and a sleep short enough to be quick is a flake.
    """
    tick = threading.Event()
    for _ in range(int(BLOCK_TIMEOUT_SECONDS * 10)):
        if _waiting_on(factory, key):
            return True
        tick.wait(0.1)
    return False


def _open_invitations(factory, organization_id: str) -> int:
    return len(
        SqlInvitationStore(factory).invitations_for_organization(organization_id, now=NOW)
    )


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_the_purge_blocks_on_a_held_issuance_lock(factory, attempt: int) -> None:
    """§7.1 step 2 -- the assertion that fails when the lock is missing.

    Sequence, made deterministic rather than hoped for:

    1. Connection A opens `issue`'s transaction, takes the advisory lock, and **holds it**
       uncommitted. Done by taking the lock directly on A's session, which is what `add_invitation`
       does inside its own transaction -- the invitation row is then inserted on the same
       connection, so both are held together.
    2. Connection B starts the purge and must **block**, evidenced by `pg_locks` showing a
       backend waiting on the same key.
    3. A commits; B proceeds, and its cascade catches the row: no invitation open afterwards.

    Step 2 is the one that fails without the lock -- the purge would complete immediately and the
    test's own timing, not the implementation, would decide the result.
    """
    organization_id, owner_id = _organization(factory, f"block{attempt}")
    addressee_id, address = _account(factory, f"blocked{attempt}")
    _disable(factory, addressee_id)
    key = identity_lock_key(address)

    gate = _Gate(threading.Event(), threading.Event())
    holding, release = gate.holding, gate.release

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(
            _hold_lock_and_write,
            factory,
            gate,
            key,
            _Row(f"inv_held{attempt}", organization_id, owner_id, address),
        )
        try:
            assert holding.wait(timeout=BLOCK_TIMEOUT_SECONDS), "the holder never took the lock"

            # Before asserting anything about *waiting*, prove the query can see the lock at all.
            # A `pg_locks` predicate that matches nothing would otherwise report "not blocked" for
            # every implementation, sound or broken -- the unfalsifiable direction.
            assert _holds(factory, key), (
                "the held lock is not visible in `pg_locks` for this key, so the blocking "
                "assertion below would be vacuous: either the holder did not acquire it, or "
                "the key reconstruction in `_advisory_rows` is wrong"
            )

            purge = pool.submit(
                lambda: SqlAccountStore(factory).purge_if_still_eligible(
                    addressee_id, PURGE_HORIZON
                )
            )

            blocked = _wait_until_blocked(factory, key)

            assert blocked, (
                "the purge did not block on the advisory lock. Either the lock is absent from "
                "one of the two paths, or the two derive different keys -- both are the defect "
                "§8.2's key derivation and named statement exist to prevent, and both leave "
                "this test's timing rather than the implementation deciding the result"
            )

        finally:
            # **Always release the holder**, even when an assertion above fails or a helper raises.
            # Without this the holding thread waits on `release` forever, the pool's `__exit__`
            # waits on the thread, and the whole run deadlocks rather than reporting the failure --
            # which is exactly how the `:key::bigint` syntax error turned into a cancelled job.
            release.set()
        holder.result(timeout=BLOCK_TIMEOUT_SECONDS * 2)
        assert purge.result(timeout=BLOCK_TIMEOUT_SECONDS * 2) is True

    assert _open_invitations(factory, organization_id) == 0, (
        "the purge's cascade must catch the invitation issued under the lock it waited for"
    )


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_a_different_address_does_not_block(factory, attempt: int) -> None:
    """The control for the test above, and the reason it identifies the *identity* key.

    "The purge blocked" on its own is consistent with any lock anywhere in the purge path -- a row
    lock on the account, an unrelated table lock, even a coincidence of timing. Holding the advisory
    lock for a **different** address and observing that the purge does *not* block is what
    establishes that the key is derived from the identity being purged.

    Without this control the sibling test would pass against an implementation that locked a
    constant, which would serialize every purge against every issuance and still look correct.
    """
    _, _ = _organization(factory, f"control{attempt}")
    addressee_id, _ = _account(factory, f"controlled{attempt}")
    _disable(factory, addressee_id)
    unrelated_key = identity_lock_key(f"someone-else-{attempt}@example.test")

    holding = threading.Event()
    release = threading.Event()

    def hold_unrelated() -> None:
        with factory.begin() as database:
            database.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": unrelated_key}
            )
            holding.set()
            release.wait(timeout=BLOCK_TIMEOUT_SECONDS * 2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder = pool.submit(hold_unrelated)
        try:
            assert holding.wait(timeout=BLOCK_TIMEOUT_SECONDS)

            purge = pool.submit(
                lambda: SqlAccountStore(factory).purge_if_still_eligible(
                    addressee_id, PURGE_HORIZON
                )
            )

            assert purge.result(timeout=BLOCK_TIMEOUT_SECONDS) is True, (
                "a lock held for a different address must not block this purge; if it does, the "
                "key is not derived from the identity and the lock serializes unrelated work"
            )
        finally:
            release.set()
        holder.result(timeout=BLOCK_TIMEOUT_SECONDS * 2)


@requires_postgres
def test_the_purge_first_ordering_leaves_an_invitation_open(factory) -> None:
    """§8.2's accepted residual, asserted as documented behaviour rather than `xfail`ed.

    The purge commits first, so `issue` looks the addressee up by canonical address, finds the
    tombstone has none, takes no lock -- correctly, since a post-purge miss is indistinguishable
    from `FR-019`'s ordinary no-account case -- and inserts an open invitation **after** the cascade
    has run. §7.1 retracted a row-lock fix for exactly this: "a row lock cannot serialize two
    operations when the discriminating fact is that the row stops being *discoverable* by the key
    one of them uses."

    The owner accepted this on 2026-08-18 rather than amend `KHEPRI-DEC-015` §2b to retain an
    address-derived marker. §7.1 requires it asserted positively so that if it ever stops holding,
    the suite says so -- a silent improvement is still a change to a governed decision's premises.

    **This is not a test that the hazard is harmless.** It is inert only while nothing can redeem at
    the released address, and `TestTheReplacementAccountCannotRedeem` in the sequential file is what
    covers the case that matters: a replacement account is refused because the addressee check
    compares against `target_identity`, not because the invitation is gone.
    """
    organization_id, owner_id = _organization(factory, "purgefirst")
    addressee_id, address = _account(factory, "purgedfirst")
    _disable(factory, addressee_id)

    assert SqlAccountStore(factory).purge_if_still_eligible(addressee_id, PURGE_HORIZON) is True

    InvitationService(SqlInvitationStore(factory)).issue(
        _offer(organization_id, owner_id, address), expires_at=LATER, now=NOW
    )

    assert _open_invitations(factory, organization_id) == 1, (
        "the purge-first ordering leaves an invitation open: this is the residual §8.2 accepts, "
        "not a defect. If this assertion starts failing, something closed the race and this test "
        "and §8.2 both need revisiting"
    )


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_revocation_and_redemption_cannot_both_win(factory, attempt: int) -> None:
    """§4.1's second `R4-07` obligation: exactly one terminal state, no integrity error.

    Run concurrently, both read the invitation as open. §4.1's hazard: redemption's conditional
    update sets `redeemed_at`, and revocation -- on a stale snapshot -- writes `revoked_at` over
    a row that is already redeemed. Either the write lands and the row claims two terminal states,
    which `ck_rca_invitation_terminal_state` refuses **after** the membership has committed (so the
    failure surfaces as an integrity error rather than a refusal), or terminal state is silently
    overwritten.

    Both verbs are single conditional statements, so the database serializes them: exactly one
    affects a row and the other sees zero. The assertion is the *pair* -- one winner, and no
    integrity error on either path.
    """
    organization_id, owner_id = _organization(factory, f"race{attempt}")
    invitee_id, invitee_email = _account(factory, f"racer{attempt}")
    service = InvitationService(SqlInvitationStore(factory))
    token = service.issue(
        _offer(organization_id, owner_id, invitee_email), expires_at=LATER, now=NOW
    )
    invitation_id, _ = parse_token(token)

    sessions = SessionService(SqlSessionStore(factory), lifetime=LIFETIME)
    session_token = sessions.create(invitee_id, now=NOW)
    actor = ActorResolver(
        sessions, LifecycleService(SqlAccountStore(factory), SqlOrganizationStore(factory))
    ).resolve_actor(session_token, now=NOW)

    barrier = threading.Barrier(2)

    def redeem() -> str:
        barrier.wait(timeout=BLOCK_TIMEOUT_SECONDS)
        try:
            InvitationService(SqlInvitationStore(factory)).redeem(token, actor, now=NOW)
            return "redeemed"
        except InvitationOperationFailed:
            return "refused"

    def revoke() -> str:
        barrier.wait(timeout=BLOCK_TIMEOUT_SECONDS)
        try:
            InvitationService(SqlInvitationStore(factory)).revoke(
                organization_id, invitation_id, actor_account_id=owner_id, now=NOW
            )
            return "revoked"
        except InvitationOperationFailed:
            return "refused"

    # **Both submitted before either is awaited.** Calling `.result()` inside the list literal
    # blocks on the first future before the second is even submitted, so the barrier never reaches
    # two participants and the test deadlocks -- the same shape as the self-deadlock above, found
    # by auditing for it rather than by another CI cancellation.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(redeem), pool.submit(revoke)]
        outcomes = [future.result(timeout=BLOCK_TIMEOUT_SECONDS * 2) for future in futures]

    # One winner. Which one is timing, and asserting a fixed winner would be asserting the
    # scheduler -- §6.1's own instruction about this shape of test.
    assert outcomes.count("refused") == 1, (
        f"exactly one of redemption and revocation must win; got {outcomes}"
    )

    membership = SqlOrganizationStore(factory).get_membership(organization_id, invitee_id)
    stored = SqlInvitationStore(factory).get_invitation(invitation_id, now=NOW)

    if outcomes[0] == "redeemed":
        assert membership is not None and membership.role == MEMBER_ROLE
        assert stored is not None and stored.redeemed_at is not None
        assert stored.revoked_at is None, "a redeemed row must not also be revoked"
    else:
        assert membership is None, "a revoked invitation must create no membership"
        assert stored is None, "revocation deletes the row (§4.1)"
