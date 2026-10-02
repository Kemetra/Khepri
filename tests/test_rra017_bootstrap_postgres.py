"""RRA-017 Verification 5, 12 and the PostgreSQL half of 8: how a unit of work learns its scope.

- **Verification 5 (`FR-238`, `FR-266`).** The membership guard refuses a beta cookie the lookup
  cannot resolve, including an existing session the lookup is made to miss, so the refusal does
  not rely on the lookup. `_workspace_of`, reached through the recorder's public `admitted`, raises
  rather than returning "not a workspace" when the lookup or the scoped read is empty.
- **Verification 12 (`FR-233`).** Every transaction that touches a covered table sets the scope
  first, and the setting is gone in the next transaction on the same physical connection.
- **Verification 8, PostgreSQL path.** `SqlSessionStore.get_session` reaches `rra_session_owner` on
  PostgreSQL. The SQLite fallback is gated by dialect, so this proves the PostgreSQL path does not
  take it.

RED at `0c1475f`: `rls_database()` raises `Rra017Absent` before any request.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import fields, replace
from datetime import timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import sessionmaker

from khepri.rca.workspace.persistence import SqlRunReportStore
from khepri.rca.workspace.scopes import SqlIsolationScopes
from khepri.rra.persistence import SqlSessionStore
from khepri.rra.session_cookie import SESSION_COOKIE, SESSION_UNAVAILABLE
from khepri.rra.sessions import InvitationService
from khepri.runtime.beta_membership_guard import BetaMembershipGuard, add_beta_membership_guard
from khepri.runtime.pipeline_recording import PipelineRecorder, RecorderReads
from tests.rra017_rows import NOW
from tests.rra017_support import (
    APPLICATION,
    COVERED_TABLES,
    OWNER_SETTING,
    POSTGRES,
    RED,
    RlsDatabase,
    Rra017Absent,
    future,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
)
from tests.w104b_support import HTTPS, Journey, invited_client, submit
from tests.w110_postgres_support import postgres_journeys

pytestmark = [*POSTGRES, RED]

PROBE = "/api/v1/beta/probe"
_COVERED = re.compile(r"\b(" + "|".join(COVERED_TABLES) + r")\b")
_SETS_SCOPE = re.compile(r"set_config\(", re.IGNORECASE)


class _NoResolver:
    """The commercial resolver is never reached on these paths: no organization owns the scope."""

    def for_request(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("the resolver must not be consulted")


class _MissingOwners:
    """A lookup made to miss, for a session that does exist."""

    def owner_of(self, _session_id: str) -> None:
        return None


def _guarded_probe(guard: BetaMembershipGuard) -> TestClient:
    app = FastAPI()

    @app.get(PROBE)
    def _probe() -> dict[str, str]:
        return {"reached": "route"}

    add_beta_membership_guard(app, guard)
    return TestClient(app, base_url=HTTPS)


def _guard(rls: RlsDatabase) -> BetaMembershipGuard:
    return BetaMembershipGuard.over(
        rls.factory(APPLICATION), resolver=_NoResolver(), clock=lambda: NOW
    )


def _invited_session(rls: RlsDatabase) -> str:
    service = InvitationService(SqlSessionStore(rls.factory(APPLICATION)))
    token = service.issue_invitation(expires_at=NOW + timedelta(days=1))
    return service.redeem(token, now=NOW).session_id


def _probe_with(client: TestClient, session_id: str | None) -> tuple[int, Any]:
    if session_id is not None:
        client.cookies.set(SESSION_COOKIE, session_id)
    response = client.get(PROBE)
    return response.status_code, response.json()


# -- Verification 5 -----------------------------------------------------------------------------


def test_the_guard_refuses_a_cookie_the_lookup_cannot_resolve(rls: RlsDatabase) -> None:
    client = _guarded_probe(_guard(rls))
    assert _probe_with(client, "ses_unknown") == (401, {"detail": SESSION_UNAVAILABLE})


def test_the_guard_refuses_an_existing_session_the_lookup_is_made_to_miss(
    rls: RlsDatabase,
) -> None:
    session_id = _invited_session(rls)
    guard = _guard(rls)
    if "owners" not in {field.name for field in fields(guard)}:
        raise Rra017Absent("BetaMembershipGuard has no `owners` lookup yet (FR-266)")
    client = _guarded_probe(replace(guard, owners=_MissingOwners()))
    assert _probe_with(client, session_id) == (401, {"detail": SESSION_UNAVAILABLE})


def test_without_a_cookie_and_for_an_unowned_scope_the_route_decides(rls: RlsDatabase) -> None:
    session_id = _invited_session(rls)
    reached = (200, {"reached": "route"})
    assert _probe_with(_guarded_probe(_guard(rls)), None) == reached
    assert _probe_with(_guarded_probe(_guard(rls)), session_id) == reached


def _with_empty_scoped_read(web: Journey) -> PipelineRecorder:
    """The journey's recorder, its lookup real and the scoped session read after it empty."""
    owners = future("khepri.rra.scope", "SqlSessionOwners")(web.w.factory)
    reads = RecorderReads(
        sessions=_EmptySessions(),
        owners=owners,
        scopes=SqlIsolationScopes(web.w.factory),
        reports=SqlRunReportStore(web.w.factory),
        jobs=web.reader,
    )
    return PipelineRecorder(recording=web.recorder.recording, reads=reads)


def test_the_recorder_raises_when_the_lookup_or_the_scoped_read_is_empty() -> None:
    unresolved = future("khepri.runtime.pipeline_recording", "SessionScopeUnresolved")
    with postgres_journeys(APPLICATION) as (web,):
        client = invited_client(web)
        submit(client)
        cases = (
            (web.recorder, "ses_unknown"),
            (_with_empty_scoped_read(web), client.cookies.get(SESSION_COOKIE)),
        )
        for recorder, session_id in cases:
            try:
                recorder.admitted(session_id, now=web.clock())
            except unresolved:
                continue
            raise AssertionError(f"{session_id!r}: an empty bootstrap read as not-a-workspace")


def test_the_recorder_answers_none_only_for_a_resolved_scope_no_organization_owns() -> None:
    with postgres_journeys(APPLICATION) as (web,):
        client = invited_client(web)
        submit(client)
        assert web.recorder.admitted(client.cookies.get(SESSION_COOKIE), now=web.clock()) is None


class _EmptySessions:
    """The scoped session read after a lookup that resolved, made empty."""

    def get_session(self, _session_id: str) -> None:
        return None

    def get_session_for_owner(self, _owner_id: str, _session_id: str) -> None:
        return None


# -- Verification 12 ----------------------------------------------------------------------------


@contextmanager
def _transactions(engine: Engine) -> Iterator[list[list[str]]]:
    """Every transaction's statements on `engine`, in order, while the block runs."""
    log: list[list[str]] = []

    def _begin(_connection: Any) -> None:
        log.append([])

    def _statement(_conn: Any, _cursor: Any, statement: str, *_: Any) -> None:
        if not log:
            log.append([])
        log[-1].append(statement)

    event.listen(engine, "begin", _begin)
    event.listen(engine, "before_cursor_execute", _statement)
    try:
        yield log
    finally:
        event.remove(engine, "before_cursor_execute", _statement)
        event.remove(engine, "begin", _begin)


def test_every_transaction_that_touches_a_covered_table_sets_the_scope_first() -> None:
    with postgres_journeys(APPLICATION) as (web,):
        engine = web.w.factory.kw["bind"]
        with _transactions(engine) as log:
            client = invited_client(web)
            submit(client)
        touching = [statements for statements in log if any(map(_COVERED.search, statements))]
        # A `begin` hook that never fired would log one transaction and pass vacuously.
        assert len(touching) >= 5, f"only {len(touching)} transactions touched a covered table"
        unscoped = [s for s in touching if not _scope_precedes_covered(s)]
        assert unscoped == []


def _scope_precedes_covered(statements: list[str]) -> bool:
    first = next(index for index, statement in enumerate(statements) if _COVERED.search(statement))
    return any(_SETS_SCOPE.search(statement) for statement in statements[:first])


def test_the_setting_is_gone_in_the_next_transaction_on_the_same_connection(
    rls: RlsDatabase,
) -> None:
    """A `NULL` here would mean no scope was ever set on the connection; `''` is the reset value
    PostgreSQL reads back after a transaction-local setting ends."""
    owner_id = "own_a"
    engine = rls.engine(APPLICATION, pool_size=1, max_overflow=0)
    store = SqlSessionStore(sessionmaker(engine, expire_on_commit=False))
    with engine.connect() as connection:
        before = connection.scalar(text("SELECT pg_backend_pid()"))
    assert store.get_session_for_owner(owner_id, "ses_a") is None
    with engine.connect() as connection:
        after = connection.execute(
            text(f"SELECT pg_backend_pid(), current_setting('{OWNER_SETTING}', true)")
        ).one()
    assert tuple(after) == (before, "")


# -- Verification 8, the PostgreSQL path -----------------------------------------------------------


def test_the_postgres_session_read_calls_the_lookup_and_not_the_fallback(rls: RlsDatabase) -> None:
    session_id = _invited_session(rls)
    engine = rls.engine(APPLICATION)
    store = SqlSessionStore(rls.factory(APPLICATION))
    with _transactions(engine) as log:
        assert store.get_session(session_id) is not None
    statements = [statement for transaction in log for statement in transaction]
    assert any("rra_session_owner(" in statement for statement in statements)
