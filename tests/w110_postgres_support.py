"""The PostgreSQL-backed `journey()` and the instruments `FR-127`'s concurrent class needs (`#388`).

`tests/w104_support.py` builds its engine on `StaticPool`, so every thread shares one connection:
two requests cannot overlap on it, and a barrier-synchronised pair raises `InterfaceError` rather
than racing. This module supplies the same composition over a real pooled PostgreSQL engine, where
each request gets its own connection and a `FOR UPDATE` either blocks the other or does not.

**An overlap is forced, never hoped for.** Two threads started together usually serialise by
accident, and a test that passes on a lucky schedule proves nothing about the lock. So each case
here pauses the first request at a named point -- `LockPause` holds it just after its locking
statement returns, `PausedCall` just before a collaborator is called -- starts the second, and,
where a lock is the claim, reads `pg_stat_activity` to prove the second is *waiting on a lock*
before letting the first go. Removing the lock turns that proof red, not merely the outcome.

Gated on `KHEPRI_TEST_DATABASE_URL` like `test_concurrency_postgres.py`, and every test using it
carries the `concurrency` marker, so `require_concurrency_tests.py` fails CI if one ever skips.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
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
    every later one, including the second request's, passes straight through.
    """

    def __init__(self, engine: Engine, table: str) -> None:
        self._engine = engine
        self._table = table
        self._armed = False
        self._guard = threading.Lock()
        self.reached = threading.Event()
        self.release = threading.Event()

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

    def _after(self, _conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        if self._table not in statement or "FOR UPDATE" not in statement:
            return
        with self._guard:
            if not self._armed:
                return
            self._armed = False
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


def backends_waiting_on_a_lock(engine: Engine) -> int:
    """How many other backends in this database are waiting to acquire a lock right now."""
    with engine.connect() as connection:
        return connection.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' "
                "AND pid <> pg_backend_pid()"
            )
        ).scalar_one()


def blocked_on_a_lock(engine: Engine) -> bool:
    """Whether some backend comes to wait on a lock within `WAIT_SECONDS`.

    Polled rather than slept: the second request needs a moment to reach its locking statement,
    and a fixed sleep either wastes time or, on a slow runner, reads before it arrives.
    """
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if backends_waiting_on_a_lock(engine) > 0:
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
        assert not self._thread.is_alive(), "the request never finished"
        return self._failure[0] if self._failure else None

    def result(self) -> Any:
        failure = self.failure()
        if failure is not None:
            raise failure
        return self._outcome[0]


def engine_of(j: Journey) -> Engine:
    """The engine a journey's stores write through -- the one a `LockPause` hooks."""
    return j.w.factory.kw["bind"]


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
    "delivered_unsettled",
    "engine_of",
    "shell_with_bridge",
    "LockPause",
    "PausedCall",
    "backends_waiting_on_a_lock",
    "blocked_on_a_lock",
    "postgres_engine",
    "postgres_journey",
    "requires_postgres",
]
