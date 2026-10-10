"""RRA-017 Verification 18: the sweep role (`FR-270`, `FR-271`) and the envelope refusal (`FR-272`).

The sweep role crosses the policies only through permissive policies granted to it alone, backed
by column grants: it reads exactly `FR-271`'s columns, across both scopes, and is refused
everything else. The three production reads run as the sweep role through their own components,
so a column grant left stale by a later change to a statement fails here. That includes `#535`'s
planned re-keying of `RawUploadRetentionSweeper._due` onto `upload_id`: whichever of the two slices
lands second updates the sweep role's column grants, and the `_due` case below catches the one
that does not.

Pinned RED at `f1639c1`, before the slice existed; green from `#595`'s implementation.
"""

from __future__ import annotations

import inspect
import json
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from khepri.rra.deletion import DeletionService
from khepri.rra.evidence_retention import DeletionEvidenceSweeper
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.persistence import SqlDeletionRepository, SqlSessionStore
from khepri.runtime.envelope_migration import REFUSED_UNDER_POLICY
from khepri.runtime.envelope_migration import run as run_envelope_migration
from tests.rra017_rows import BUILDERS, HOUR, NOW, Scope, chain, row
from tests.rra017_support import (
    APPLICATION,
    INSUFFICIENT_PRIVILEGE,
    POSTGRES,
    SWEEP,
    RlsDatabase,
    Rra017Absent,
    attempt,
    future,
    insert,
    remove,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
    rra_tables,
    scope_set_by,
    touch,
)
from tests.w104_support import MemoryObjectStore

pytestmark = list(POSTGRES)

A = Scope("own_a", "a")
B = Scope("own_b", "b")
#: `FR-271`'s column grants on RRA tables.
SWEEP_READS = {
    "rra_beta_sessions": ("session_id", "owner_id", "content_expires_at", "content_deleted_at"),
    "rra_uploads": ("upload_id", "owner_id", "session_id", "object_key", "ciphertext_sha256_hex"),
    "rra_deletion_evidence": ("attempted_at",),
}
ALL_RRA = (*BUILDERS, "rra_invitations")


def _refused_reads() -> list[tuple[str, str]]:
    """Every other column of a listed table, and the first column of every other RRA table."""
    tables = rra_tables()
    other = [
        (name, column.name)
        for name, columns in SWEEP_READS.items()
        for column in tables[name].columns
        if column.name not in columns
    ]
    unlisted = [name for name in ALL_RRA if name not in SWEEP_READS]
    return other + [(name, next(iter(tables[name].columns)).name) for name in unlisted]


def test_the_sweep_reads_exactly_its_columns_across_both_scopes(rls: RlsDatabase) -> None:
    rls.seed(chain(A) + chain(B))
    with rls.engine(SWEEP).begin() as connection:
        for table, columns in SWEEP_READS.items():
            found = connection.execute(text(f"SELECT {', '.join(columns)} FROM {table}")).all()
            assert len(found) == 2, table


@pytest.mark.parametrize(("table", "column"), _refused_reads())
def test_every_other_column_and_table_is_refused_to_the_sweep(
    rls: RlsDatabase, table: str, column: str
) -> None:
    refused = attempt(
        rls.engine(SWEEP), None, lambda c: c.execute(text(f"SELECT {column} FROM {table}"))
    )
    assert refused == INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize("table", list(BUILDERS))
def test_the_sweep_may_neither_insert_nor_update_an_rra_table(rls: RlsDatabase, table: str) -> None:
    rls.seed(chain(A))
    engine = rls.engine(SWEEP)
    fresh = Scope(A.owner_id, "a2")
    assert attempt(engine, None, insert(table, row(fresh, table))) == INSUFFICIENT_PRIVILEGE
    assert attempt(engine, None, lambda c: touch(c, table)) == INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize("table", [name for name in BUILDERS if name != "rra_deletion_evidence"])
def test_the_sweep_may_delete_from_no_rra_table_but_the_evidence(
    rls: RlsDatabase, table: str
) -> None:
    rls.seed(chain(A))
    assert attempt(rls.engine(SWEEP), None, lambda c: remove(c, table)) == INSUFFICIENT_PRIVILEGE


def _old_evidence(scope: Scope) -> list:
    rows = chain(scope)
    rows[-1] = (
        "rra_deletion_evidence",
        row(scope, "rra_deletion_evidence", attempted_at=NOW - timedelta(days=400)),
    )
    return rows


def test_the_evidence_purge_removes_both_scopes_rows_past_the_horizon(rls: RlsDatabase) -> None:
    rls.seed(_old_evidence(A) + _old_evidence(B))
    sweeper = DeletionEvidenceSweeper(SqlDeletionRepository(rls.factory(SWEEP)))
    assert sweeper.sweep(now=NOW).purged_evidence == 2
    assert rls.as_owner("SELECT count(*) FROM rra_deletion_evidence") == [(0,)]


def _expired_session(scope: Scope) -> list:
    expired = {"created_at": NOW - 2 * HOUR, "content_expires_at": NOW - HOUR}
    return [("rra_beta_sessions", row(scope, "rra_beta_sessions", **expired))]


def _sweeper(rls: RlsDatabase) -> Any:
    build = future("khepri.runtime.retention_sweep", "build_retention_sweeper")
    if "sweep_factory" not in inspect.signature(build).parameters:
        raise Rra017Absent("build_retention_sweeper takes no sweep engine yet (FR-271)")
    scoped = rls.factory(APPLICATION)
    deletion = DeletionService(
        sessions=SqlSessionStore(scoped),
        deletions=SqlDeletionRepository(scoped),
        objects=MemoryObjectStore(),
    )
    return build(
        jobs=SqlReportJobRepository(scoped),
        deletion=deletion,
        factory=scoped,
        sweep_factory=rls.factory(SWEEP),
    )


def test_one_sweep_deletes_both_scopes_expired_sessions_each_under_its_own_owner(
    rls: RlsDatabase,
) -> None:
    rls.seed(_expired_session(A) + _expired_session(B))
    sweeper = _sweeper(rls)
    owners: list[str] = []

    def _record(*event_arguments: Any) -> None:
        owner = scope_set_by(event_arguments[2], event_arguments[3])
        if owner is not None:
            owners.append(owner)

    event.listen(rls.engine(APPLICATION), "before_cursor_execute", _record)
    assert sweeper.sweep(now=NOW).expired_sessions == 2
    assert {"own_a", "own_b"} <= set(owners)
    deleted = rls.as_owner(
        "SELECT count(*) FROM rra_beta_sessions WHERE content_deleted_at IS NOT NULL"
    )
    assert deleted == [(2,)]


def _sealed_version(scope: Scope) -> list[tuple[str, dict]]:
    upload = row(scope, "rra_uploads")
    return [
        (
            "rca_organizations",
            {
                "organization_id": f"org_{scope.tag}",
                "name": scope.tag,
                "created_at": NOW - 30 * 24 * HOUR,
            },
        ),
        (
            "rca_isolation_scopes",
            {"organization_id": f"org_{scope.tag}", "owner_id": scope.owner_id},
        ),
        (
            "rca_workspace_dataset_versions",
            {
                "version_id": f"ver_{scope.tag}",
                "owner_id": scope.owner_id,
                "upload_id": upload["upload_id"],
                "upload_plaintext_digest": upload["sha256_hex"],
                "upload_ciphertext_digest": upload["ciphertext_sha256_hex"],
                "upload_size_bytes": upload["size_bytes"],
                "upload_media_type": "text/csv",
                "manifest_digest": "m" * 64,
                "mapping_version": "v1",
                "admission_outcome": "admitted",
                "created_at": NOW - 10 * 24 * HOUR,
                "sealed_at": NOW - 8 * 24 * HOUR,
                "retention_state": "active",
                "retention_changed_at": None,
            },
        ),
    ]


def _seed_rca(rls: RlsDatabase, rows: list[tuple[str, dict]]) -> None:
    from khepri.rca.persistence import Base as RcaBase  # noqa: PLC0415

    with rls.owner.begin() as connection:
        for table, values in rows:
            connection.execute(RcaBase.metadata.tables[table].insert().values(**values))


def test_the_due_upload_read_runs_as_the_sweep_role_across_both_scopes(rls: RlsDatabase) -> None:
    lister = future("khepri.runtime.workspace_retention", "DueUploadLister")
    rls.seed(chain(A)[:2] + chain(B)[:2])
    _seed_rca(rls, _sealed_version(A) + _sealed_version(B))
    due = lister(rls.factory(SWEEP)).due(now=NOW)
    assert {upload.owner_id for upload in due} == {"own_a", "own_b"}


class _NoReseal:
    def reseal(self, *_: Any, **__: Any) -> Any:
        raise AssertionError("a refused migration reseals nothing")


#: The harness's migration owner: it owns the tables and, on CI's and the throwaway cluster, is
#: also the superuser, so one role stands for both of `FR-272`'s bypassing connections.
OWNER = "owner"
#: `FR-272`'s refused compositions: (the lister's role, the scoped engine's role, the reason).
REFUSED_COMPOSITIONS = {
    "no_sweep_engine": (None, APPLICATION, "no_sweep_engine"),
    "lister_on_the_application_role": (APPLICATION, APPLICATION, "lister_role"),
    "lister_on_the_owner": (OWNER, APPLICATION, "lister_role"),
    "scoped_on_the_owner": (SWEEP, OWNER, "scoped_role"),
    "both_on_the_owner": (OWNER, OWNER, "lister_role"),
}


def _factory_for(rls: RlsDatabase, role: str | None) -> Any:
    if role is None:
        return None
    return sessionmaker(rls.owner) if role == OWNER else rls.factory(role)


@pytest.mark.parametrize("composition", list(REFUSED_COMPOSITIONS))
def test_the_envelope_migration_refuses_any_other_composition_and_reports_no_count(
    rls: RlsDatabase, composition: str
) -> None:
    """`FR-272`: under the policies it runs only with its listing on the sweep role and its scoped
    work on the application role. Through a scoped role both reads are empty, and through a
    bypassing one the policies are not what the run proved; either would read as "verified"."""
    lister, scoped, reason = REFUSED_COMPOSITIONS[composition]
    legacy = []
    for scope in (A, B):
        rows = chain(scope)
        index = [name for name, _ in rows].index("rra_report_artifacts")
        rows[index] = (
            "rra_report_artifacts",
            row(scope, "rra_report_artifacts", envelope_version=1),
        )
        legacy += rows
    rls.seed(legacy)
    stack = SimpleNamespace(
        factory=_factory_for(rls, scoped), objects=_NoReseal(), clock=lambda: NOW
    )
    printed: list[str] = []
    status = run_envelope_migration(
        stack, sweep_factory=_factory_for(rls, lister), out=printed.append
    )
    assert status == REFUSED_UNDER_POLICY
    assert [json.loads(line) for line in printed] == [
        {"event": "envelope_migration", "refused": reason}
    ]
