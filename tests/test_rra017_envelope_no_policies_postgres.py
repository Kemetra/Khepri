"""`khepri-envelope-migrate` where PostgreSQL has no RRA policies (`RRA-017` `FR-272`).

There the command lists sessions through the stack's own engine. That engine is the one
`build_stack` builds, `engine_for(..., DatabaseRole.APPLICATION)`, and it carries the scope
tripwire, which the harness's guarded engines do not. A listing with no scope bound reaches
`rra_beta_sessions` unscoped, so the tripwire raises `ScopeRequired` and the run prints nothing.
The listing is bound deliberately unscoped instead, as the backstop counts are.

Row security is switched off on the three tables the decision reads, as the migration owner, and
switched back on in `finally`: the harness's head check would not notice, and every later test
would run without it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.envelope_migration import ArtifactEnvelopeMigration
from khepri.rra.scope import ScopeRequired
from khepri.rra.storage import S3EncryptedObjectStore
from khepri.runtime.db_roles import DatabaseRole, engine_for
from khepri.runtime.envelope_migration import GUARDED_TABLES
from khepri.runtime.envelope_migration import run as run_envelope_migration
from tests.rra017_rows import NOW, Scope
from tests.rra017_support import (
    APPLICATION,
    POSTGRES,
    RlsDatabase,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
    role_url,
)
from tests.test_i535_artifact_envelope_migration import BUCKET, MASTER, DictS3
from tests.test_rra017_envelope_postgres import _legacy

pytestmark = list(POSTGRES)

A = Scope("own_a", "a")


def _never_built() -> sessionmaker[Session]:
    raise AssertionError("no sweep engine is built where no policy exists")


@pytest.fixture(name="unpoliced")
def unpoliced_fixture(rls: RlsDatabase) -> Iterator[RlsDatabase]:
    for table in GUARDED_TABLES:
        rls.as_owner(f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY")
        rls.as_owner(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
    try:
        yield rls
    finally:
        for table in GUARDED_TABLES:
            rls.as_owner(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            rls.as_owner(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")


@pytest.fixture(name="stack_engine")
def stack_engine_fixture() -> Iterator[sessionmaker[Session]]:
    """The application role's engine exactly as `build_stack` builds it: tripwired."""
    engine = engine_for(role_url(APPLICATION), DatabaseRole.APPLICATION)
    try:
        yield sessionmaker(bind=engine, future=True)
    finally:
        engine.dispose()


def test_with_no_policies_the_run_lists_through_the_tripwired_stack_and_verifies(
    unpoliced: RlsDatabase, stack_engine: sessionmaker[Session]
) -> None:
    client = DictS3()
    unpoliced.seed(_legacy(A, client))
    stack = SimpleNamespace(
        factory=stack_engine,
        objects=S3EncryptedObjectStore(client=client, bucket=BUCKET, master_key=MASTER),
        clock=lambda: NOW,
    )
    printed: list[str] = []

    status = run_envelope_migration(stack, sweep=_never_built, out=printed.append)

    line = json.loads(printed.pop())
    assert (status, printed) == (0, [])
    assert (line["resealed"], line["artifacts_remaining"]) == (1, 0)
    backstop = (line["backstop_artifacts_remaining"], line["backstop_uploads_remaining"])
    assert backstop == (0, 0)


def test_under_the_policies_a_listing_on_the_stack_engine_stays_loud(
    rls: RlsDatabase, stack_engine: sessionmaker[Session]
) -> None:
    """Only the no-policies composition binds the listing unscoped. Under the policies the same
    listing would read no session and report "verified", so the tripwire must still raise."""
    rls.seed(_legacy(A, DictS3()))
    objects = S3EncryptedObjectStore(client=DictS3(), bucket=BUCKET, master_key=MASTER)
    migration = ArtifactEnvelopeMigration(factory=stack_engine, objects=objects)

    with pytest.raises(ScopeRequired):
        migration.migrate()
