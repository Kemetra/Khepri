"""The PostgreSQL-backed `journey()` and the instruments `FR-127`'s concurrent class needs (`#388`).

`tests/w104_support.py` builds its engine on `StaticPool`, so every thread shares one connection:
two requests cannot overlap on it, and a barrier-synchronised pair raises `InterfaceError` rather
than racing. This module supplies the same composition over a real pooled PostgreSQL engine, where
each request gets its own connection and a `FOR UPDATE` either blocks the other or does not.

**An overlap is forced, never hoped for.** Two threads started together usually serialise by
accident, and a test that passes on a lucky schedule proves nothing about the lock. So each case
here pauses the first request at a named point -- `LockPause` holds it just after its locking
statement returns, `PausedCall` just before a collaborator is called -- starts the second, and,
where a lock is the claim, reads `pg_stat_activity` to prove the second is *waiting on the first's
lock* before letting the first go.

**Three ways a test here can fail, kept apart**, so a strict `xfail` pinning a known defect cannot
absorb the others:

- `HarnessError` when the instrument did not do its job: a pause never reached, a request that
  never finished, a database not named as a test database.
- A plain `AssertionError` when a property fails, the lock-wait proof included.
- `DefectStillPresent` only where a test pins a filed defect. It is the only failure that test's
  `xfail(raises=...)` names.

Gated on `KHEPRI_TEST_DATABASE_URL` like `test_concurrency_postgres.py`, and every test using it
carries the `concurrency` marker, so `require_concurrency_tests.py` fails CI if one ever skips.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event, text

from tests.w104b_support import Journey, journey

DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; FR-127's concurrent cases need a real PostgreSQL",
)

#: Long enough for a loaded CI runner, short enough that a lock that never contends fails fast.
WAIT_SECONDS = 10.0

#: A database whose name lacks `test` as a whole `_`-separated token is never emptied. CI's is
#: `khepri_test`; `contest` or `testimony` do not match.
TEST_DATABASE_NAME = re.compile(r"(^|_)test($|_)")


class HarnessError(RuntimeError):
    """The instrument failed, not the code under test.

    Never an `AssertionError`, so no strict `xfail` pinning a defect can mistake a broken harness
    for the defect still being present.
    """


class DefectStillPresent(AssertionError):
    """A filed defect's own assertion: the only failure a pinning `xfail` names in `raises=`."""


def await_reached(reached: threading.Event, what: str) -> None:
    """Wait for a pause point, or fail as the harness: the interleaving was never set up."""
    if not reached.wait(WAIT_SECONDS):
        raise HarnessError(f"{what} never reached its pause point")


def postgres_engine() -> Engine:
    """A pooled engine over an emptied `public` schema.

    Not `StaticPool`: each session gets its own connection, so two transactions genuinely overlap.
    The schema is dropped with `CASCADE` rather than through either `metadata.drop_all`, because
    the workspace and `RRA` tables are two metadata trees keyed onto one another.
    """
    engine = create_engine(DATABASE_URL)
    _empty_public_schema(engine)
    return engine


def _empty_public_schema(engine: Engine) -> None:
    """Drop and recreate `public`, refused unless the database is named as a test database, so a
    mis-pointed `KHEPRI_TEST_DATABASE_URL` cannot empty a real one."""
    name = engine.url.database or ""
    if not TEST_DATABASE_NAME.search(name):
        raise HarnessError(f"refusing to empty database {name!r}: its name does not mark a test")
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


@contextmanager
def postgres_journey() -> Iterator[Journey]:
    """`journey()` over PostgreSQL: the same stores, routes and deletion path, real connections.

    The schema is emptied again on the way out. Other `concurrency` tests share this database and
    drop only their own metadata tree, which a workspace table keyed onto an `RRA` one would block.
    """
    engine = postgres_engine()
    try:
        yield journey(engine)
    finally:
        engine.dispose()
        _empty_public_schema(engine)
        engine.dispose()


class LockPause:
    """Holds the first request that runs a locking statement on `table`, lock held, until released.

    Hooked on the engine's `after_cursor_execute`, which is the seam that survives any refactor of
    the store: the statement has returned, so PostgreSQL has granted whatever lock it took, and the
    transaction stays open while this waits. Only the first matching statement after `arm` pauses;
    every later one, including the second request's, passes straight through. The held backend's
    pid is recorded, so the lock-wait proof can ask who is blocked by *it*.
    """

    def __init__(self, engine: Engine, table: str) -> None:
        self._engine = engine
        self._table = table
        self._armed = False
        self._guard = threading.Lock()
        self.reached = threading.Event()
        self.release = threading.Event()
        self.backend_pid: int | None = None

    def arm(self) -> None:
        self._armed = True
        event.listen(self._engine, "after_cursor_execute", self._after)

    def disarm(self) -> None:
        """Let the held request go, and pause nothing more.

        The listener is left attached, inert: removing it here would mutate the engine's listener
        list while another thread iterates it. It goes with the engine, which is per test.
        """
        with self._guard:
            self._armed = False
        self.release.set()

    def _after(self, conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        if self._table not in statement or "FOR UPDATE" not in statement:
            return
        with self._guard:
            if not self._armed:
                return
            self._armed = False
        self.backend_pid = conn.connection.dbapi_connection.info.backend_pid
        self.reached.set()
        self.release.wait(WAIT_SECONDS * 3)


class PausedCall:
    """Wraps one collaborator so its first call waits until released, then delegates unchanged.

    For an interleaving that is not about a lock: the request has done every read it makes, and is
    held at the point where it acts on them.
    """

    def __init__(self, inner: Any, method: str) -> None:
        self._inner = inner
        self._method = method
        self._paused = False
        self.reached = threading.Event()
        self.release = threading.Event()

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._inner, name)
        if name != self._method:
            return attribute
        return self._pausing(attribute)

    def _pausing(self, call: Callable[..., Any]) -> Callable[..., Any]:
        def paused(*args: Any, **kwargs: Any) -> Any:
            if not self._paused:
                self._paused = True
                self.reached.set()
                self.release.wait(WAIT_SECONDS * 3)
            return call(*args, **kwargs)

        return paused


def backends_blocked_by(engine: Engine, blocker_pid: int, table: str) -> int:
    """How many backends are waiting, right now, on a lock `blocker_pid` holds **while running a
    `FOR UPDATE` on `table`**.

    The statement filter is the point. A child-row insert waits on its parent's `FOR KEY SHARE`, so
    a request whose own lock was removed can still be seen blocked by the holder -- on the foreign
    key -- and an unfiltered count would read that as the lock working.
    `test_w102_workspace_lock_contention.py` records the same trap for its `NOWAIT` probe.
    """
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE :blocker = ANY(pg_blocking_pids(pid)) "
                "AND query ILIKE '%FOR UPDATE%' AND query LIKE '%' || :table || '%'"
            ),
            {"blocker": blocker_pid, "table": table},
        ).scalar_one()


def blocked_by(engine: Engine, blocker_pid: int | None, table: str) -> bool:
    """Whether some backend comes to wait on `blocker_pid`'s lock, in a `FOR UPDATE` on `table`,
    within `WAIT_SECONDS`.

    Filtered by the blocker and by the waiting statement, so neither an unrelated wait nor a
    foreign-key wait can satisfy it. Polled rather than slept.
    """
    if blocker_pid is None:
        raise HarnessError("the held request's backend was never recorded")
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if backends_blocked_by(engine, blocker_pid, table) > 0:
            return True
        time.sleep(0.05)
    return False


class Background:
    """One call on its own thread, whose result or exception is read back after `join`."""

    def __init__(self, call: Callable[[], Any]) -> None:
        self._call = call
        self._outcome: list[Any] = []
        self._failure: list[BaseException] = []
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            self._outcome.append(self._call())
        except BaseException as failure:  # noqa: BLE001 -- re-raised on the test's thread
            self._failure.append(failure)

    @property
    def finished(self) -> bool:
        return not self._thread.is_alive()

    def failure(self) -> BaseException | None:
        """What the call raised, once it has finished, or `None` if it returned."""
        self._thread.join(WAIT_SECONDS * 3)
        if self._thread.is_alive():
            raise HarnessError("the request never finished")
        return self._failure[0] if self._failure else None

    def result(self) -> Any:
        failure = self.failure()
        if failure is not None:
            raise failure
        return self._outcome[0]


@dataclass(frozen=True, slots=True)
class Overlap:
    """Two calls that genuinely overlapped: the first held on its lock, the second shown waiting."""

    first: Background
    second: Background


def overlap_on_lock(
    j: Journey, table: str, first: Callable[[], Any], second: Callable[[], Any]
) -> Overlap:
    """Run `first` until it holds its `FOR UPDATE` on `table`, start `second`, prove `second` waits
    on *that* lock, then let `first` go.

    The proof is a plain assertion, because it is the property and not the instrument. It is made
    before the first request is released, so an outcome that comes out right on a serial schedule
    cannot pass for it.
    """
    engine = engine_of(j)
    pause = LockPause(engine, table)
    pause.arm()
    try:
        held = Background(first)
        await_reached(pause.reached, "the first request")
        waiting = Background(second)
        assert blocked_by(engine, pause.backend_pid, table), (
            f"the second request never waited on the first's lock in a FOR UPDATE on {table}"
        )
        assert not waiting.finished, "the second request finished while the first held the lock"
    finally:
        pause.disarm()
    return Overlap(held, waiting)


def engine_of(j: Journey) -> Engine:
    """The engine a journey's stores write through, and the one a `LockPause` hooks."""
    return j.w.factory.kw["bind"]


def outcomes_of(j: Journey, owner_id: str, action: str) -> list[str]:
    """Every audit outcome this scope recorded for one action, sorted."""
    return sorted(e.outcome for e in j.w.audit.events_for_scope(owner_id) if e.action == action)


def tombstones_of(j: Journey, owner_id: str, kind: type, subject_id: str) -> list[Any]:
    """This scope's tombstones of one kind for one subject: a version's, or a run's."""
    from khepri.rca.workspace.tombstones import RunTombstone

    subject = "run_id" if kind is RunTombstone else "version_id"
    return [
        stone
        for stone in j.w.store.tombstones_for_scope(owner_id)
        if isinstance(stone, kind) and getattr(stone, subject) == subject_id
    ]


def shell_with_bridge(j: Journey, who: Any, bridge: Any) -> Any:
    """`services_over`'s shell with its session bridge replaced -- by a `PausedCall` around the
    real one, so the handoff is held after its reads and before it resumes the session."""
    from dataclasses import replace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from khepri.rca.session_cookie import SESSION_COOKIE
    from khepri.runtime.shell_api import add_shell_routes
    from tests.w106_support import HTTPS, services_over

    app = FastAPI()
    add_shell_routes(app, services=replace(services_over(j, who), bridge=bridge), clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def delivered_unsettled(j: Journey, job_id: str) -> None:
    """Deliver the job through the real pipeline, *without* the settling store around the jobs.

    The state a crash between delivery and recording leaves: the job succeeded, its run is still
    `started`. From here the worker's settlement and the reconcile sweep are two real doors that
    can both reach `record_completion` for one run.
    """
    from khepri.rra.worker import ReportJobMessage, ReportWorker, WorkerPolicy
    from tests.w104b_support import LEASE_FOR, RETRY_DELAY, WORKER_ID

    ReportWorker(
        jobs=j.jobs,
        handler=j.pipeline(),
        clock=j.clock,
        policy=WorkerPolicy(worker_id=WORKER_ID, lease_for=LEASE_FOR, retry_delay=RETRY_DELAY),
    ).process(ReportJobMessage(job_id=job_id))


__all__ = [
    "Background",
    "DefectStillPresent",
    "HarnessError",
    "LockPause",
    "Overlap",
    "PausedCall",
    "await_reached",
    "backends_blocked_by",
    "blocked_by",
    "delivered_unsettled",
    "engine_of",
    "outcomes_of",
    "overlap_on_lock",
    "postgres_engine",
    "tombstones_of",
    "postgres_journey",
    "requires_postgres",
    "shell_with_bridge",
]
