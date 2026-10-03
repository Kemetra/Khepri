"""The two guards every runtime engine carries on PostgreSQL (`RRA-017` `FR-233`, `FR-270`; `#595`).

`khepri.runtime.db_roles.engine_for` is the only place an engine is built. It attaches:

- **the connect-time role check** (plan D-5): a connection that is not its role's own login, or is
  a superuser or bypasses row security, is refused before its first statement. Handed the
  migration owner's credential, a runtime process would otherwise run with every policy silently
  bypassed;
- **the scope tripwire** (plan D-4), on the application and worker engines only: a statement that
  reaches a covered table in a transaction that set no scope raises `ScopeRequired` before it is
  sent, where the policy alone would answer with a silent empty result.

Each guard is shown refusing and shown admitting, so neither passes by refusing everything.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from khepri.rra.persistence import BetaSessionRow, InvitationRow
from khepri.rra.scope import ScopeRequired, scoped_read
from khepri.runtime.db_roles import DatabaseRole, RoleMismatch, engine_for
from tests.rra017_support import (  # noqa: F401 -- rls_fixture is the fixture
    DATABASE_URL,
    POSTGRES,
    RlsDatabase,
    rls_fixture,
    role_url,
)

pytestmark = list(POSTGRES)

SCOPED_ROLES = (DatabaseRole.APPLICATION, DatabaseRole.WORKER)


@contextmanager
def _engine(url: object, role: DatabaseRole) -> Iterator[Engine]:
    engine = engine_for(url, role)  # type: ignore[arg-type]
    try:
        yield engine
    finally:
        engine.dispose()


def _as(role: DatabaseRole) -> object:
    """`role`'s own login, with the harness's test-only password."""
    return role_url(role.value)


# -- the connect-time role check -----------------------------------------------------------------


@pytest.mark.parametrize(
    "login",
    [pytest.param(None, id="migration-owner"), pytest.param(DatabaseRole.WORKER, id="worker")],
)
def test_an_application_engine_logged_in_as_anything_else_refuses_to_connect(
    rls: RlsDatabase, login: DatabaseRole | None
) -> None:
    url = make_url(DATABASE_URL) if login is None else _as(login)
    with _engine(url, DatabaseRole.APPLICATION) as engine, pytest.raises(RoleMismatch):
        engine.connect()


@pytest.mark.parametrize("role", list(DatabaseRole), ids=lambda role: role.value)
def test_each_role_connects_as_its_own_login(rls: RlsDatabase, role: DatabaseRole) -> None:
    with _engine(_as(role), role) as engine, engine.connect() as connection:
        assert connection.exec_driver_sql("SELECT current_user").scalar() == role.value


# -- the scope tripwire ----------------------------------------------------------------------------


@pytest.mark.parametrize("role", SCOPED_ROLES, ids=lambda role: role.value)
def test_an_unscoped_statement_on_a_covered_table_raises_before_it_is_sent(
    rls: RlsDatabase, role: DatabaseRole
) -> None:
    with (
        _engine(_as(role), role) as engine,
        engine.connect() as connection,
        pytest.raises(ScopeRequired),
    ):
        connection.execute(select(BetaSessionRow.session_id))


@pytest.mark.parametrize("role", SCOPED_ROLES, ids=lambda role: role.value)
def test_a_scoped_transaction_and_an_uncovered_table_pass_and_the_next_is_unscoped(
    rls: RlsDatabase, role: DatabaseRole
) -> None:
    with _engine(_as(role), role) as engine:
        with scoped_read(sessionmaker(engine), "own_tripwire") as database:
            assert database.scalars(select(BetaSessionRow.session_id)).all() == []
        with engine.connect() as connection:
            connection.execute(select(InvitationRow.invitation_id))
        with engine.connect() as connection, pytest.raises(ScopeRequired):
            connection.execute(select(BetaSessionRow.session_id))


def test_the_sweep_engine_reads_across_scopes_without_a_tripwire(rls: RlsDatabase) -> None:
    """`FR-271`: the sweep's four components read across scopes by design, unscoped."""
    sweep = DatabaseRole.SWEEP
    with _engine(_as(sweep), sweep) as engine, engine.connect() as connection:
        assert connection.execute(select(BetaSessionRow.session_id)).all() == []
