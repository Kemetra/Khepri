"""RRA-017 Verification 13: the RRA store suites, rerun as the application role under `FORCE`.

A suite opts in with `pytestmark = STORE_BACKENDS` and builds its engine with `store_engine()`
where it used to build an in-memory SQLite one. Every test in it then runs twice:

- `sqlite`: the in-memory engine the suite always had, with `create_all`. No policy exists, so
  this is Verification 8's half: the stores' own predicates isolate the scopes.
- `app-role`: the guarded application-role engine over RRA-017's migrated schema, from
  `tests/rra017_support.py`. Every policy is forced, the role neither owns the tables nor bypasses
  row security, and the guard refuses a superuser connection, so a store verb that reaches a row
  without setting its scope reads nothing or is refused, and the suite's own assertions fail.

The `app-role` run needs `KHEPRI_TEST_DATABASE_URL`, and is marked `concurrency` so
`require_concurrency_tests.py` fails CI if it skips there.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.scope import acting_for
from tests.rra017_support import APPLICATION, WORKER, RlsDatabase, rls_database
from tests.w110_postgres_support import requires_postgres

SQLITE = "sqlite"
APP_ROLE = "app-role"

_DATABASE: ContextVar[RlsDatabase | None] = ContextVar("rra017_store_database", default=None)
#: The test's one SQLite engine, shared by every role, as one PostgreSQL database is.
_SQLITE: ContextVar[Engine | None] = ContextVar("rra017_store_sqlite", default=None)


@pytest.fixture(
    params=[
        SQLITE,
        pytest.param(APP_ROLE, marks=(pytest.mark.concurrency, requires_postgres)),
    ],
)
def store_backend(request: pytest.FixtureRequest) -> Iterator[str]:
    """The backend `store_engine()` builds on, for the duration of one test."""
    if request.param == SQLITE:
        token = _SQLITE.set(_sqlite_engine())
        try:
            yield SQLITE
        finally:
            _SQLITE.reset(token)
        return
    with rls_database() as database:
        token = _DATABASE.set(database)
        try:
            yield APP_ROLE
        finally:
            _DATABASE.reset(token)


def suite_engine() -> Engine | None:
    """The application role's engine during an `app-role` run, else `None` (the caller's default).

    `w104b_support.journey()` builds on it, so the journey and shell suites that opt in run their
    routes and stores as the application role. Their worker steps run as that role too, which
    holds the worker role's table privileges, except the recovery pickers only the worker may
    call: those run on `suite_worker_factory()`. The deployed worker role is exercised end to end
    by `test_rra017_routes_postgres.py`.
    """
    database = _DATABASE.get()
    return None if database is None else database.engine(APPLICATION)


def suite_worker_factory() -> sessionmaker[Session] | None:
    """The worker role's sessions during an `app-role` run, else `None`."""
    database = _DATABASE.get()
    return None if database is None else database.factory(WORKER)


_JOB_OWNER = text("SELECT owner_id FROM rra_report_jobs WHERE job_id = :job_id")


def owner_of_job(factory: sessionmaker[Session], job_id: str) -> str | None:
    """A job's owner, as the claim picker would hand it to the worker (`FR-267`).

    A test helper's read, outside the policies: through the migration owner during an `app-role`
    run, and through `factory` otherwise, where no policy applies.
    """
    database = _DATABASE.get()
    if database is not None:
        found = database.as_owner(str(_JOB_OWNER), job_id=job_id)
        return found[0][0] if found else None
    with factory() as session:
        return session.scalar(_JOB_OWNER, {"job_id": job_id})


class InUnit:
    """`target`'s verbs, each run as one unit in `owner_id`'s scope (`RRA-017` `FR-233`).

    For a store whose verbs name only a job or a delivery, and so take their scope from the unit:
    in production the worker's job unit or the beta request's unit binds it. A suite calling such a
    store directly binds it here, per call, rather than for the whole test, so its other stores'
    explicit owners keep refusing another scope by returning nothing.
    """

    def __init__(self, target: Any, owner_id: str) -> None:
        self._target = target
        self._owner_id = owner_id

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._target, name)
        if not callable(attribute):
            return attribute

        def in_unit(*args: Any, **kwargs: Any) -> Any:
            with acting_for(self._owner_id):
                return attribute(*args, **kwargs)

        return in_unit


#: Applied as a suite's `pytestmark`: every test runs on both backends.
STORE_BACKENDS = pytest.mark.usefixtures("store_backend")


def store_engine(role: str = APPLICATION) -> Engine:
    """The engine a store suite's harness builds on: SQLite, or `role`'s guarded engine.

    `role` is the runtime role whose process runs the verbs: the worker's for leasing and
    recovery, which only it (and the sweep) may call the pickers for. On SQLite every role shares
    the test's one engine. Outside the fixture, a fresh SQLite engine, as the suite always had.
    """
    database = _DATABASE.get()
    if database is not None:
        return database.engine(role)
    return _SQLITE.get() or _sqlite_engine()


def _sqlite_engine() -> Engine:
    from khepri.rra.persistence import Base  # noqa: PLC0415 -- every RRA table is registered

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine


__all__ = [
    "APP_ROLE",
    "SQLITE",
    "STORE_BACKENDS",
    "WORKER",
    "InUnit",
    "owner_of_job",
    "store_backend",
    "store_engine",
    "suite_engine",
    "suite_worker_factory",
]
