"""#535: an artifact rewrite and a session deletion cannot interleave, on a real PostgreSQL.

The rewrite holds the session's `FOR UPDATE` lock across the object write. That lock is what makes
a deletion either wait for the rewrite or be seen by it, and SQLite emits no `FOR UPDATE`. So the
SQLite suite proves the sequential cases and cannot prove this one. Marked `concurrency` so that
`.github/scripts/require_concurrency_tests.py` fails CI if it skips. It is repeated because one
green run cannot tell a sound lock from a lucky schedule.
"""

from __future__ import annotations

import os
import threading
from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rra.delivery_persistence import SqlDeliveryStore
from khepri.rra.envelope_migration import ArtifactEnvelopeMigration, EnvelopeMigrationReport
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.persistence import SqlDeletionRepository, SqlSessionStore
from khepri.rra.sessions import InvitationService
from khepri.rra.storage import Resealed, S3EncryptedObjectStore, StoredEnvelope
from tests.rra017_support import migrated_owner_engine
from tests.test_i535_artifact_envelope_migration import _world
from tests.test_rra006_delivery_persistence import NOW, Harness

ATTEMPTS = 10
# Long enough for an unlocked deletion to finish many times over; a locked one never does.
BLOCKED_FOR = 0.5

pytestmark = pytest.mark.concurrency

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; this contract needs a real PostgreSQL",
)


@pytest.fixture(name="postgres_harness")
def postgres_harness_fixture():
    """`harness()`'s world on PostgreSQL: one connection per session, so locks contend, on the
    migrated schema, emptied per test (`#595` D-7)."""
    engine = migrated_owner_engine()
    factory = sessionmaker(engine, expire_on_commit=False)
    invitations = InvitationService(SqlSessionStore(factory))
    session = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)), now=NOW
    )
    try:
        yield Harness(
            factory=factory,
            session=session,
            jobs=SqlReportJobRepository(factory),
            store=SqlDeliveryStore(factory, now=lambda: NOW),
        )
    finally:
        engine.dispose()


class PausingStore:
    """Holds the first rewrite open until released, inside the migration's transaction."""

    def __init__(self, inner: S3EncryptedObjectStore) -> None:
        self._inner = inner
        self.entered = threading.Event()
        self.release = threading.Event()

    def reseal(self, key: str, *, envelope: StoredEnvelope, media_type: str) -> Resealed:
        if not self.entered.is_set():
            self.entered.set()
            assert self.release.wait(timeout=30)
        return self._inner.reseal(key, envelope=envelope, media_type=media_type)


@pytest.mark.parametrize("attempt", range(ATTEMPTS))
@requires_postgres
def test_a_deletion_begun_mid_rewrite_waits_and_the_rest_defer_to_it(
    postgres_harness: Harness, attempt: int
) -> None:
    del attempt
    world = _world(test=postgres_harness)
    store = PausingStore(world.store)
    migration = ArtifactEnvelopeMigration(factory=postgres_harness.factory, objects=store)
    reports: list[EnvelopeMigrationReport] = []
    migrating = threading.Thread(target=lambda: reports.append(migration.migrate()))
    deleting = threading.Thread(
        target=lambda: SqlDeletionRepository(postgres_harness.factory).begin(
            scope=postgres_harness.scope,
            deletion_id="del_race",
            reason="immediate",
            requested_at=NOW,
        )
    )

    migrating.start()
    try:
        assert store.entered.wait(timeout=30)
        deleting.start()
        deleting.join(timeout=BLOCKED_FOR)
        # The mechanism, not a timing: the deletion is parked on the lock the rewrite holds.
        assert deleting.is_alive(), "a deletion began while an object was being rewritten"
    finally:
        # Released and joined on every path, so a failure cannot leave a thread running into
        # the fixture's teardown.
        store.release.set()
        migrating.join(timeout=30)
        if deleting.ident is not None:
            deleting.join(timeout=30)

    # The paused row committed before the deletion took the lock. Whichever rows ran after the
    # deletion committed saw it and left their objects alone, and every one is still counted.
    [report] = reports
    assert report.resealed >= 1
    assert report.resealed + report.deferred == 7
    assert (report.failed, report.artifacts_remaining) == (0, report.deferred)
