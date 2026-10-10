"""`khepri-envelope-migrate` refuses what the catalogue cannot vouch for (`RRA-017` `FR-272`).

Three fail-closed refusals, each before any count, each against the real roles:

- a table the decision reads is missing from `public`: the catalogue cannot say whether the
  policies exist, so the command does not guess "no policies";
- row security enabled on `rra_beta_sessions` alone still counts as "the policies exist", so a
  partial rollback of `20261002_0036` cannot route the listing through a scoped engine that sees
  no session;
- the lister and the scoped engine reach different databases: `FR-273`'s completeness argument
  (every `v1` row keys onto a session the lister returns) holds only within one database.

Each case changes the catalogue as the migration owner and restores it in `finally`: the
harness's head check would not notice the change, and every later test would run under it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.runtime.envelope_migration import REFUSED_UNDER_POLICY
from khepri.runtime.envelope_migration import run as run_envelope_migration
from tests.rra017_rows import NOW, Scope, chain
from tests.rra017_support import (
    APPLICATION,
    POSTGRES,
    SWEEP,
    RlsDatabase,
    guarded_engine,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
    role_url,
)

pytestmark = list(POSTGRES)

A = Scope("own_a", "a")
ELSEWHERE = "khepri_test_elsewhere"


class _NoReseal:
    def reseal(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("a refused migration reseals nothing")


def _refusal(rls: RlsDatabase, sweep: sessionmaker | None) -> tuple[int, list[dict]]:
    stack = SimpleNamespace(
        factory=rls.factory(APPLICATION), objects=_NoReseal(), clock=lambda: NOW
    )
    printed: list[str] = []
    status = run_envelope_migration(
        stack, sweep=None if sweep is None else lambda: sweep, out=printed.append
    )
    return status, [json.loads(line) for line in printed]


def _refused(reason: str) -> tuple[int, list[dict]]:
    return REFUSED_UNDER_POLICY, [{"event": "envelope_migration", "refused": reason}]


@contextmanager
def _altered(rls: RlsDatabase, change: list[str], restore: list[str]) -> Iterator[None]:
    for statement in change:
        rls.as_owner(statement)
    try:
        yield
    finally:
        for statement in restore:
            rls.as_owner(statement)


@pytest.mark.parametrize("table", ["rra_report_artifacts", "rra_uploads", "rra_beta_sessions"])
def test_a_table_missing_from_the_catalogue_refuses_as_unreadable(
    rls: RlsDatabase, table: str
) -> None:
    rename = f"ALTER TABLE public.{table} RENAME TO {table}_away"
    back = f"ALTER TABLE public.{table}_away RENAME TO {table}"
    with _altered(rls, [rename], [back]):
        assert _refusal(rls, rls.factory(SWEEP)) == _refused("catalogue_unreadable")


def _security(table: str, *, on: bool) -> list[str]:
    if on:
        return [
            f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY",
            f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY",
        ]
    return [
        f"ALTER TABLE public.{table} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY",
    ]


def test_row_security_on_the_sessions_alone_counts_as_the_policies(rls: RlsDatabase) -> None:
    """With the content tables' row security rolled back, the listing would still be hidden."""
    legacy = {"rra_report_artifacts": {"envelope_version": 1}}
    rls.seed((table, {**values, **legacy.get(table, {})}) for table, values in chain(A))
    content = ("rra_report_artifacts", "rra_uploads")
    rolled_back = [statement for table in content for statement in _security(table, on=False)]
    restored = [statement for table in content for statement in _security(table, on=True)]
    with _altered(rls, rolled_back, restored):
        assert _refusal(rls, None) == _refused("no_sweep_engine")


@pytest.fixture(name="elsewhere")
def elsewhere_fixture(rls: RlsDatabase) -> Iterator[sessionmaker]:
    """The sweep role, connected to a second database on the same cluster."""
    with rls.owner.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.exec_driver_sql(f"CREATE DATABASE {ELSEWHERE}")
    engine = guarded_engine(role_url(SWEEP).set(database=ELSEWHERE), SWEEP)
    try:
        yield sessionmaker(engine)
    finally:
        engine.dispose()
        with rls.owner.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            connection.exec_driver_sql(f"DROP DATABASE {ELSEWHERE} WITH (FORCE)")


def test_a_lister_on_another_database_refuses_with_no_count(
    rls: RlsDatabase, elsewhere: sessionmaker
) -> None:
    """Fail-closed hardening inside `FR-273`: the walk is complete only within one database."""
    assert _refusal(rls, elsewhere) == _refused("database_mismatch")
