"""RRA-017 Verification 19: `FR-273`, as the sweep and application roles (`#535`).

`khepri-envelope-migrate` lists sessions on the sweep engine and does everything else on the
scoped engine, one session at a time, with that session's `owner_id` set. Two hooks watch the
engines for the whole run:

- on the sweep engine, every statement's columns are collected from the compiled construct, and
  any statement whose text names `rra_report_artifacts` or `rra_uploads` fails the test. The
  database would not refuse the second: `FR-271` grants the sweep role columns of `rra_uploads`;
- on the scoped engine, every statement that reaches either content table is recorded with the
  scope its transaction set.

The sight cases drop `rra_sweep_read` or revoke a column grant, and restore it in `finally` with
migration `20261002_0036`'s own statements: the harness's head check would not notice either
loss, and every later test would run without it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import Column, event
from sqlalchemy.sql import visitors

from khepri.rra.scope import SCOPE_MARK
from khepri.rra.storage import S3EncryptedObjectStore
from khepri.runtime.envelope_migration import run as run_envelope_migration
from tests.rra017_rows import NOW, Scope, chain, row
from tests.rra017_support import (
    APPLICATION,
    POSTGRES,
    SWEEP,
    RlsDatabase,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
)
from tests.test_i535_artifact_envelope_migration import BUCKET, MASTER, DictS3, forge_v1

pytestmark = list(POSTGRES)

A = Scope("own_a", "a")
B = Scope("own_b", "b")
#: A session whose `owner_id` is `''`: `FR-232` hides it from every scoped read (Open item 6).
UNOWNED = Scope("", "e")
CONTENT = re.compile(r"\b(rra_report_artifacts|rra_uploads)\b")
LISTED_COLUMNS = {("rra_beta_sessions", "session_id"), ("rra_beta_sessions", "owner_id")}
REFUSED = 2


def _artifact_key(scope: Scope) -> str:
    return row(scope, "rra_report_artifacts")["object_key"]


def _legacy(scope: Scope, client: DictS3, *, upload_version: int = 2) -> list[tuple[str, dict]]:
    """`scope`'s chain with a `v1` artifact whose object is in `client`."""
    plaintext = f"report of {scope.tag}".encode()
    body = forge_v1(plaintext)
    client.objects[_artifact_key(scope)] = body
    overrides = {
        "rra_report_artifacts": {
            "envelope_version": 1,
            "sha256_hex": hashlib.sha256(plaintext).hexdigest(),
            "ciphertext_sha256_hex": hashlib.sha256(body).hexdigest(),
        },
        "rra_uploads": {"envelope_version": upload_version},
    }
    return [(table, {**values, **overrides.get(table, {})}) for table, values in chain(scope)]


@dataclass
class Watch:
    """What each engine ran, recorded by `before_cursor_execute` hooks."""

    swept_columns: set[tuple[str, str]] = field(default_factory=set)
    swept_content: list[str] = field(default_factory=list)
    scoped_content: list[tuple[Any, str, Any]] = field(default_factory=list)

    def on_sweep(self, _conn: Any, *event: Any) -> None:
        """`before_cursor_execute`; `event` is cursor, statement, parameters, context, many."""
        statement = event[1]
        if CONTENT.search(statement):
            self.swept_content.append(statement)
        compiled = getattr(event[3], "compiled", None)
        construct = getattr(compiled, "statement", None)
        if construct is not None:
            self.swept_columns |= {
                (element.table.name, element.name)
                for element in visitors.iterate(construct)
                if isinstance(element, Column) and element.table is not None
            }

    def on_scoped(self, conn: Any, *event: Any) -> None:
        """`before_cursor_execute`, recording the scope each content statement ran under."""
        statement, parameters = event[1], event[2]
        if CONTENT.search(statement):
            self.scoped_content.append((conn.info.get(SCOPE_MARK), statement, parameters))

    def owners_of_content_reads(self) -> set[Any]:
        return {mark for mark, _statement, _parameters in self.scoped_content}


@dataclass
class World:
    rls: RlsDatabase
    client: DictS3 = field(default_factory=DictS3)
    watch: Watch = field(default_factory=Watch)

    def __post_init__(self) -> None:
        event.listen(self.rls.engine(SWEEP), "before_cursor_execute", self.watch.on_sweep)
        event.listen(self.rls.engine(APPLICATION), "before_cursor_execute", self.watch.on_scoped)

    def run(self) -> tuple[int, dict]:
        stack = SimpleNamespace(
            factory=self.rls.factory(APPLICATION),
            objects=S3EncryptedObjectStore(client=self.client, bucket=BUCKET, master_key=MASTER),
            clock=lambda: NOW,
        )
        printed: list[str] = []
        status = run_envelope_migration(
            stack, sweep_factory=self.rls.factory(SWEEP), out=printed.append
        )
        assert len(printed) == 1
        assert not self.watch.swept_content, "a content table was reached on the sweep engine"
        return status, json.loads(printed[0])

    def versions(self) -> list[tuple[str, int]]:
        return self.rls.as_owner(
            "SELECT owner_id, envelope_version FROM rra_report_artifacts ORDER BY owner_id"
        )


@pytest.fixture(name="world")
def world_fixture(rls: RlsDatabase) -> World:
    return World(rls)


def test_v1_artifacts_in_both_scopes_are_resealed_and_the_run_is_verified(world: World) -> None:
    world.rls.seed(_legacy(A, world.client) + _legacy(B, world.client))

    status, line = world.run()

    assert status == 0
    counts = (line["resealed"], line["artifacts_remaining"], line["uploads_not_migrated"])
    assert counts == (2, 0, 0)
    assert world.versions() == [("own_a", 2), ("own_b", 2)]
    assert world.client.objects[_artifact_key(A)][0] == 2


def test_the_lister_reads_only_session_id_and_owner_id_on_the_sweep_engine(world: World) -> None:
    world.rls.seed(_legacy(A, world.client) + _legacy(B, world.client))

    world.run()

    assert world.watch.swept_columns == LISTED_COLUMNS


def test_every_content_statement_runs_scoped_to_its_own_sessions_owner(world: World) -> None:
    world.rls.seed(_legacy(A, world.client) + _legacy(B, world.client))

    world.run()

    assert world.watch.owners_of_content_reads() == {"own_a", "own_b"}
    reads = [entry for entry in world.watch.scoped_content if entry[1].startswith("SELECT")]
    assert reads
    for mark, statement, parameters in reads:
        bound = parameters.values() if isinstance(parameters, dict) else parameters
        assert mark in set(bound), statement


def test_a_v1_upload_is_counted_in_its_scope_never_resealed_and_blocks_verified(
    world: World,
) -> None:
    world.rls.seed(_legacy(A, world.client) + _legacy(B, world.client, upload_version=1))

    status, line = world.run()

    assert status == 1
    assert (line["resealed"], line["uploads_not_migrated"]) == (2, 1)
    assert set(world.client.puts) == {_artifact_key(A), _artifact_key(B)}
    upload_counts = [
        mark for mark, statement, _ in world.watch.scoped_content if "rra_uploads" in statement
    ]
    assert "own_b" in upload_counts


def _defer(world: World) -> None:
    world.rls.as_owner(
        "UPDATE rra_beta_sessions SET deletion_requested_at = :now WHERE owner_id = 'own_b'",
        now=NOW,
    )


def _fault(world: World) -> None:
    world.client.failing.add(_artifact_key(B))


@pytest.mark.parametrize("leave", [_defer, _fault], ids=["deferred", "faulted"])
def test_one_v1_artifact_left_in_b_blocks_verified(world: World, leave: Any) -> None:
    world.rls.seed(_legacy(A, world.client) + _legacy(B, world.client))
    leave(world)

    status, line = world.run()

    assert status == 1
    assert line["artifacts_remaining"] == 1
    assert world.versions() == [("own_a", 2), ("own_b", 1)]


def test_an_unowned_session_blocks_verified_and_is_never_counted_as_zero(world: World) -> None:
    world.rls.seed(_legacy(A, world.client) + _legacy(UNOWNED, world.client))

    status, line = world.run()

    assert status == 1
    assert line["sessions_unscoped"] == 1
    assert world.watch.owners_of_content_reads() == {"own_a"}
    assert ("", 1) in world.versions()


#: Each loss of the lister's sight, and migration `20261002_0036`'s statement restoring it.
SIGHT_LOSSES = {
    "policy_dropped": (
        "DROP POLICY rra_sweep_read ON public.rra_beta_sessions",
        "CREATE POLICY rra_sweep_read ON public.rra_beta_sessions AS PERMISSIVE FOR SELECT "
        f"TO {SWEEP} USING (true)",
    ),
    "session_id_revoked": (
        f"REVOKE SELECT (session_id) ON public.rra_beta_sessions FROM {SWEEP}",
        f"GRANT SELECT (session_id) ON public.rra_beta_sessions TO {SWEEP}",
    ),
    "owner_id_revoked": (
        f"REVOKE SELECT (owner_id) ON public.rra_beta_sessions FROM {SWEEP}",
        f"GRANT SELECT (owner_id) ON public.rra_beta_sessions TO {SWEEP}",
    ),
}


@pytest.fixture(name="blinded", params=list(SIGHT_LOSSES))
def blinded_fixture(world: World, request: pytest.FixtureRequest) -> Iterator[World]:
    lose, restore = SIGHT_LOSSES[request.param]
    world.rls.as_owner(lose)
    try:
        yield world
    finally:
        world.rls.as_owner(restore)


def test_a_lister_that_cannot_see_every_session_refuses_with_no_count(blinded: World) -> None:
    blinded.rls.seed(_legacy(A, blinded.client) + _legacy(B, blinded.client))

    status, line = blinded.run()

    assert status == REFUSED
    assert line == {"event": "envelope_migration", "refused": "lister_sight"}
    assert blinded.client.puts == []


_SESSION_KEYS = """
SELECT c.conname, c.confdeltype, c.confrelid::regclass::text,
       ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY AS k(n, i)
             JOIN pg_attribute AS a ON a.attrelid = c.conrelid AND a.attnum = k.n ORDER BY k.i),
       ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY AS k(n, i)
             JOIN pg_attribute AS a ON a.attrelid = c.confrelid AND a.attnum = k.n ORDER BY k.i)
FROM pg_constraint AS c
WHERE c.contype = 'f'
  AND c.conname IN ('fk_report_artifact_session_scope', 'fk_upload_session_scope')
"""


def test_both_content_tables_key_onto_their_session_with_restrict(rls: RlsDatabase) -> None:
    """The walk is complete only because every `v1` row sits in a session the lister returns."""
    keys = {name: tuple(rest) for name, *rest in rls.as_owner(_SESSION_KEYS)}
    scope = ["owner_id", "session_id"]
    expected = ("r", "rra_beta_sessions", scope, scope)
    assert keys == {
        "fk_report_artifact_session_scope": expected,
        "fk_upload_session_scope": expected,
    }
