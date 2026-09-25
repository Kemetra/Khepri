"""Two requests inside `delete_session_content` settle on one deletion (`#560` item 6; `RRA-002`).

**Forced here on SQLite, without threads.** The second request is caught in one window -- see
`tests.rra002_deletion_race_support` -- and the whole first request runs to completion inside it,
the interleaving the race needs, reproduced every run. What SQLite cannot show is the lock:
`StaticPool` shares one connection and SQLAlchemy emits no `FOR UPDATE` for this dialect.
`test_concurrency_postgres.py` runs the genuine two-connection race against PostgreSQL.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.deletion import DeletionRetryRequired, DeletionService
from khepri.rra.persistence import Base, SqlSessionStore, SqlUploadRepository
from khepri.rra.session_cookie import SESSION_COOKIE
from khepri.rra.sessions import InvitationService, SessionScope
from tests.rra002_deletion_race_support import (
    WINDOW_AFTER_TARGETS,
    WINDOWS,
    ObjectStore,
    Settled,
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


def _route_client(
    service: DeletionService, factory: sessionmaker, scope: SessionScope
) -> TestClient:
    app = create_app(
        service=InvitationService(SqlSessionStore(factory)),
        deletion_service=service,
        clock=lambda: NOW,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, scope.session_id)
    return client


@pytest.mark.parametrize(
    "outer_objects", [ObjectStore, _FailingObjectStore], ids=["outer_deletes", "outer_fails"]
)
def test_a_request_overtaken_by_a_failed_attempt_answers_retry(outer_objects: type) -> None:
    """A request overtaken by a failed attempt answers the retry, not a 500 (`#576`; `RRA-002`).

    Both requests hold the pending job at attempt 0. The inner request's object delete fails and
    its `fail()` commits attempt 1. The outer request -- whether its own deletes succeed or fail --
    then settles against a job its snapshot no longer describes. `RRA-002` §Requirements names
    "immediate idempotent deletion" and "retry state": the route answers the governed 503 retry,
    keeps the session cookie, and the store holds only the inner attempt's evidence.
    """
    factory = _factory()
    scope = session_and_upload(SqlSessionStore(factory), SqlUploadRepository(factory))
    failing = hooked_service(
        factory, window=WINDOW_AFTER_TARGETS, hook=lambda: None, objects=_FailingObjectStore()
    )

    def overtaken() -> None:
        with pytest.raises(DeletionRetryRequired):
            delete(failing, scope, NOW)

    outer = hooked_service(
        factory, window=WINDOW_AFTER_TARGETS, hook=overtaken, objects=outer_objects()
    )
    response = _route_client(outer, factory, scope).delete("/api/v1/beta/content")

    assert response.status_code == 503
    assert response.json() == {"detail": "Content deletion is pending retry."}
    assert "set-cookie" not in response.headers
    assert settled(factory, scope) == Settled(
        jobs=1,
        attempt_count=1,
        evidence=((1, "upl_alpha", "failed"),),
        content_deleted=False,
    )
