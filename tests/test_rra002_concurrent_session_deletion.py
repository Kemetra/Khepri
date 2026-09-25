"""Two requests inside `delete_session_content` settle on one deletion (`#560` item 6; `RRA-002`).

**Forced here on SQLite, without threads.** The second request is caught in one window -- see
`tests.rra002_deletion_race_support` -- and the whole first request runs to completion inside it,
the interleaving the race needs, reproduced every run. What SQLite cannot show is the lock:
`StaticPool` shares one connection and SQLAlchemy emits no `FOR UPDATE` for this dialect.
`test_concurrency_postgres.py` runs the genuine two-connection race against PostgreSQL.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.deletion import DeletionRetryRequired
from khepri.rra.persistence import Base, SqlSessionStore, SqlUploadRepository
from tests.rra002_deletion_race_support import (
    WINDOW_AFTER_TARGETS,
    WINDOWS,
    ObjectStore,
    assert_one_deletion,
    delete,
    hooked_service,
    settled,
)
from tests.test_rra002_deletion_persistence import NOW, session_and_upload


def _factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.mark.parametrize("window", WINDOWS)
def test_a_request_overtaken_inside_the_window_answers_the_one_deletion(window: str) -> None:
    factory = _factory()
    scope = session_and_upload(SqlSessionStore(factory), SqlUploadRepository(factory))
    objects = ObjectStore()
    first = hooked_service(factory, window=window, hook=lambda: None, objects=objects)
    results = []

    def overtaken() -> None:
        results.append(delete(first, scope, NOW))

    second = hooked_service(factory, window=window, hook=overtaken, objects=objects)
    results.append(delete(second, scope, NOW))

    assert_one_deletion(results, settled(factory, scope), "upl_alpha")


class _FailingObjectStore(ObjectStore):
    def delete(self, key: str) -> None:
        raise RuntimeError("object store unavailable")


@pytest.mark.xfail(
    strict=True,
    raises=ValueError,
    reason="#560 item 6 residual: a stale attempt number after a racing fail() raises ValueError",
)
def test_a_request_overtaken_by_a_failed_attempt_is_not_a_server_error() -> None:
    """A second request whose objects are gone, after the first recorded a failed attempt.

    Both hold the pending job at attempt 0. The first request's object delete fails and `fail()`
    moves the job to attempt 1; the second then completes with attempt-1 evidence, which
    `_validate_attempt` refuses with `ValueError` -- a 500 from the route, which maps only
    `SessionExpired` and `DeletionRetryRequired`. Fail-closed (no duplicate evidence, the job
    stays `retryable`), but not an answer. Pinned, not fixed: the expected outcome is a later
    slice's call.
    """
    factory = _factory()
    scope = session_and_upload(SqlSessionStore(factory), SqlUploadRepository(factory))
    failing = hooked_service(
        factory, window=WINDOW_AFTER_TARGETS, hook=lambda: None, objects=_FailingObjectStore()
    )

    def overtaken() -> None:
        with pytest.raises(DeletionRetryRequired):
            delete(failing, scope, NOW)

    second = hooked_service(
        factory, window=WINDOW_AFTER_TARGETS, hook=overtaken, objects=ObjectStore()
    )
    delete(second, scope, NOW)
