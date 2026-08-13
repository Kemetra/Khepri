"""Contracts that only a real database can exhibit (`R1-03` level 3).

Every test here needs two genuine connections to PostgreSQL. The rest of the suite runs
in-memory SQLite through a `StaticPool`, which shares one connection across every
session, so two concurrent transactions cannot exist in it. SQLite also has no
``SELECT ... FOR UPDATE`` and SQLAlchemy emits none for that dialect, which means a
locking test written against the default fixture passes while proving nothing.

These are marked `concurrency`. CI attaches a PostgreSQL service and then fails if any of
them skipped -- see `.github/scripts/require_concurrency_tests.py`. Locally they skip
when `KHEPRI_TEST_DATABASE_URL` is unset, so the ordinary suite still runs offline.

**Why this file starts with an RRA test rather than an RCA one.** `redeem_invitation`
already performs the guard-and-write shape `#155` needs, and has shipped since the RRA
sessions slice, but nothing has ever proved it under real concurrency: its existing test
runs on SQLite, where the lock is a no-op, so it demonstrates sequential replay rejection
only. Proving the harness against a lock that already works means that when `R1-04` adds
the RCA path, a failure points at the new code rather than at untested infrastructure.
"""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.sessions import BetaSession, InvitationService

NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.concurrency

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; these contracts need a real PostgreSQL",
)


@pytest.fixture(name="factory")
def factory_fixture():
    """A PostgreSQL session factory on a schema created and dropped per test.

    Not `StaticPool`: the whole point is that each session gets its own connection, so
    two transactions can genuinely overlap. The default `QueuePool` does that.
    """
    engine = create_engine(DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@requires_postgres
def test_the_fixture_really_gives_two_independent_connections(factory) -> None:
    """The harness check. If this fails, every other verdict in this file is worthless.

    A test that silently ran both halves on one connection would report success for a
    lock that never contended. Asserting distinct backend PIDs is the cheapest way to
    know the fixture delivers what the other tests assume.
    """
    with factory() as first, factory() as second:
        first_pid = first.execute(text("SELECT pg_backend_pid()")).scalar()
        second_pid = second.execute(text("SELECT pg_backend_pid()")).scalar()

    assert first_pid != second_pid


@requires_postgres
def test_concurrent_redemption_of_one_invitation_yields_exactly_one_session(
    factory,
) -> None:
    """`FOR UPDATE` serializes two redemptions of the same invitation (`RRA-001`).

    Both threads read the invitation as unredeemed on SQLite, because the lock is a
    no-op there and neither blocks. On PostgreSQL the second must wait for the first to
    commit, then observe `redeemed_at` set and refuse.

    Asserting on the *store* return values rather than a row count is deliberate: a row
    count of one would also be satisfied by both calls failing.
    """
    store = SqlSessionStore(factory)
    service = InvitationService(store)
    token = service.issue_invitation(expires_at=NOW + timedelta(hours=1))
    invitation_id, _ = service.parse_token(token)

    def redeem(index: int) -> bool:
        return store.redeem_invitation(
            invitation_id,
            NOW,
            BetaSession(
                owner_id=f"own_concurrent_{index}",
                session_id=f"ses_concurrent_{index}",
                created_at=NOW,
                content_expires_at=NOW + timedelta(days=7),
                consent_version="beta-privacy-v1",
                consented_at=NOW,
            ),
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(redeem, range(2)))

    assert sorted(outcomes) == [False, True]
