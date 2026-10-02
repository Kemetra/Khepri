"""RRA-017 Verification 14 (behavioural), 15 and 16: the four definer functions (`#595`).

`FR-265`'s lookup is called as the application and the worker role with **no** setting, which is
the case it exists for. `FR-267`'s pickers are called as the worker. Parity holds each SQL body
equal to its Python counterpart (`claimable_at`, and the two recovery predicates), the second
statement of the predicate and not a second authority (`#518`): a clause added in Python fails the
seeding count here until the function is replaced in the same slice.

RED at `0c1475f`: `rls_database()` raises `Rra017Absent` before any call.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import Connection, select, text

from khepri.rra.job_persistence import ReportJobRow, claimable_at, next_claimable_statement
from khepri.rra.persistence import SqlSessionStore
from tests.rra017_rows import HOUR, NOW, Scope, row
from tests.rra017_support import (
    APPLICATION,
    INSUFFICIENT_PRIVILEGE,
    POSTGRES,
    RED,
    SCOPED_ROLES,
    SWEEP,
    WORKER,
    RlsDatabase,
    attempt,
    future,
    rls_fixture,  # noqa: F401 -- the `rls` fixture
    scoped,
)

pytestmark = [*POSTGRES, RED]

A = Scope("own_a", "a")
B = Scope("own_b", "b")
PICKERS = ("rra_next_claimable_job", "rra_expired_lease_jobs", "rra_orphaned_jobs")
RECOVERY = ("rra_expired_lease_jobs", "rra_orphaned_jobs")
DELETED = {"deletion_requested_at": NOW - 2 * HOUR, "content_deleted_at": NOW - HOUR}


def _session_and_job(scope: Scope, session: dict | None = None, **job: Any) -> list:
    return [
        ("rra_beta_sessions", row(scope, "rra_beta_sessions", **(session or {}))),
        ("rra_report_jobs", row(scope, "rra_report_jobs", **job)),
    ]


def _running(scope: Scope, lease_expires_at: Any) -> list:
    return _session_and_job(
        scope,
        state="running",
        lease_owner="worker-x",
        lease_expires_at=lease_expires_at,
        attempt_count=1,
    )


def _lookup(connection: Connection, session_id: str | None) -> str | None:
    return connection.scalar(text("SELECT rra_session_owner(:s)"), {"s": session_id})


def _picked(connection: Connection, function: str) -> list[tuple[str, str]]:
    result = connection.execute(text(f"SELECT * FROM {function}(:now)"), {"now": NOW})
    assert list(result.keys()) == ["job_id", "owner_id"]
    return [tuple(found) for found in result]


# -- FR-265 (Verification 15) ------------------------------------------------------------------


@pytest.mark.parametrize("role", SCOPED_ROLES)
def test_the_lookup_answers_each_sessions_owner_and_null_otherwise(
    rls: RlsDatabase, role: str
) -> None:
    rls.seed(_session_and_job(A) + _session_and_job(B))
    with rls.engine(role).begin() as connection:
        answers = [_lookup(connection, sid) for sid in (A.session_id, B.session_id, "ses_x", "")]
        answers.append(_lookup(connection, None))
    assert answers == [A.owner_id, B.owner_id, None, None, None]


def test_the_sweep_role_may_not_call_the_lookup(rls: RlsDatabase) -> None:
    rls.seed(_session_and_job(A))
    refused = attempt(rls.engine(SWEEP), None, lambda c: _lookup(c, A.session_id))
    assert refused == INSUFFICIENT_PRIVILEGE


def test_after_the_lookup_the_scoped_read_sees_that_session_alone(rls: RlsDatabase) -> None:
    rls.seed(_session_and_job(A) + _session_and_job(B))
    with rls.engine(APPLICATION).begin() as connection:
        scoped(connection, _lookup(connection, A.session_id))
        seen = connection.scalars(text("SELECT session_id FROM rra_beta_sessions")).all()
    store = SqlSessionStore(rls.factory(APPLICATION))
    assert (seen, store.get_session(A.session_id).owner_id) == ([A.session_id], A.owner_id)


def test_in_a_unit_scoped_to_a_reading_b_raises_and_the_scope_stays_a(rls: RlsDatabase) -> None:
    acting_for = future("khepri.rra.scope", "acting_for")
    conflict = future("khepri.rra.scope", "ScopeConflict")
    rls.seed(_session_and_job(A) + _session_and_job(B))
    store = SqlSessionStore(rls.factory(APPLICATION))
    with acting_for(A.owner_id):
        with pytest.raises(conflict):
            store.get_session(B.session_id)
        assert store.get_session(A.session_id).owner_id == A.owner_id


# -- FR-267 (Verification 16) ------------------------------------------------------------------


def test_each_picker_names_both_scopes_jobs_while_a_plain_read_sees_none(
    rls: RlsDatabase,
) -> None:
    a, b = Scope("own_a", "ra"), Scope("own_b", "rb")
    oa, ob = Scope("own_a", "oa"), Scope("own_b", "ob")
    rls.seed(_session_and_job(A) + _running(a, NOW - HOUR) + _running(b, NOW - HOUR))
    rls.seed(_session_and_job(oa, DELETED) + _session_and_job(ob, DELETED))
    with rls.engine(WORKER).begin() as connection:
        claimed = _picked(connection, "rra_next_claimable_job")
        expired = _picked(connection, "rra_expired_lease_jobs")
        orphaned = _picked(connection, "rra_orphaned_jobs")
        plain = connection.scalars(text("SELECT job_id FROM rra_report_jobs")).all()
    assert claimed == [(A.job_id, A.owner_id)]
    assert (
        {owner for _job, owner in expired}
        == {owner for _job, owner in orphaned}
        == {
            "own_a",
            "own_b",
        }
    )
    assert plain == []


@pytest.mark.parametrize("function", PICKERS)
def test_the_application_role_may_call_no_picker(rls: RlsDatabase, function: str) -> None:
    refused = attempt(rls.engine(APPLICATION), None, lambda c: _picked(c, function))
    assert refused == INSUFFICIENT_PRIVILEGE


@pytest.mark.parametrize("function", RECOVERY)
def test_the_sweep_role_may_call_the_recovery_pickers(rls: RlsDatabase, function: str) -> None:
    with rls.engine(SWEEP).begin() as connection:
        assert _picked(connection, function) == []


#: One job per clause of `claimable_at(now)`, each failing that clause alone.
CLAIM_FAILURES: dict[str, dict] = {
    "state": {"job": {"state": "succeeded", "completed_at": NOW - HOUR}},
    "available_at": {"job": {"available_at": NOW + HOUR}},
    "attempts": {"job": {"attempt_count": 3, "max_attempts": 3}},
    "live_session": {"session": {"deletion_requested_at": NOW - HOUR}},
}


def _claim_seed() -> list:
    rows = _session_and_job(Scope("own_a", "c0"))
    rows += _session_and_job(Scope("own_b", "c9"), available_at=NOW - HOUR / 2)
    for index, (name, variant) in enumerate(CLAIM_FAILURES.items()):
        scope = Scope("own_a" if index % 2 else "own_b", f"c{index + 1}{name[:2]}")
        rows += _session_and_job(scope, variant.get("session"), **variant.get("job", {}))
    return rows


def _lease_as_owner(rls: RlsDatabase, job_id: str) -> None:
    rls.as_owner(
        "UPDATE rra_report_jobs SET state = 'running', lease_owner = 'w', "
        "lease_expires_at = :until, attempt_count = attempt_count + 1 WHERE job_id = :job",
        until=NOW + HOUR,
        job=job_id,
    )


def test_the_claim_picker_names_what_the_python_predicate_names_at_every_step(
    rls: RlsDatabase,
) -> None:
    assert len(CLAIM_FAILURES) == len(claimable_at(NOW)), "seed one job per claimable_at clause"
    rls.seed(_claim_seed())
    named: list[str] = []
    while True:
        with rls.owner.begin() as connection:
            function = connection.execute(
                text("SELECT job_id FROM rra_next_claimable_job(:now)"), {"now": NOW}
            ).scalar_one_or_none()
            python = connection.execute(next_claimable_statement(NOW)).scalar_one_or_none()
        assert function == python
        if function is None:
            break
        named.append(function)
        _lease_as_owner(rls, function)
    assert named == ["job_c0", "job_c9"]


def _orphan_seed() -> list:
    return (
        _session_and_job(Scope("own_a", "o1"), DELETED)
        + _session_and_job(Scope("own_b", "o2"), DELETED)
        + _session_and_job(Scope("own_a", "o3"))
        + _session_and_job(
            Scope("own_b", "o4"), DELETED, state="succeeded", completed_at=NOW - HOUR
        )
    )


def _expired_seed() -> list:
    return (
        _running(Scope("own_a", "e1"), NOW - HOUR)
        + _running(Scope("own_b", "e2"), NOW - 2 * HOUR)
        + _running(Scope("own_a", "e3"), NOW + HOUR)
        + _session_and_job(Scope("own_b", "e4"), state="retryable")
    )


@dataclass(frozen=True)
class _Recovery:
    """One recovery picker, the Python clauses it mirrors, its order, and its seed."""

    function: str
    clauses: str
    order: str
    seed: Callable[[], list]

    def statement(self) -> Any:
        predicate = future("khepri.rra.job_persistence", self.clauses)
        where = predicate(NOW) if self.clauses == "expired_lease_at" else predicate()
        assert len(where) == 2, "seed one job failing each clause"
        return (
            select(ReportJobRow.job_id, ReportJobRow.owner_id)
            .where(*where)
            .order_by(getattr(ReportJobRow, self.order), ReportJobRow.job_id)
        )


@pytest.mark.parametrize(
    "recovery",
    [
        _Recovery("rra_expired_lease_jobs", "expired_lease_at", "lease_expires_at", _expired_seed),
        _Recovery("rra_orphaned_jobs", "orphaned_at", "queued_at", _orphan_seed),
    ],
    ids=["expired", "orphaned"],
)
def test_each_recovery_picker_names_what_its_python_predicate_names(
    rls: RlsDatabase, recovery: _Recovery
) -> None:
    python = recovery.statement()
    rls.seed(recovery.seed())
    with rls.owner.begin() as connection:
        from_python = [tuple(found) for found in connection.execute(python)]
        from_function = _picked(connection, recovery.function)
    assert from_function == from_python and len(from_python) == 2


# -- FR-264, behaviourally (Verification 14) ---------------------------------------------------

_SHADOWS = (
    "CREATE TEMP TABLE rra_beta_sessions (session_id text, owner_id text, "
    "deletion_requested_at timestamptz, content_deleted_at timestamptz)",
    "INSERT INTO rra_beta_sessions VALUES ('ses_a', 'own_evil', NULL, NULL), "
    "('ses_e', 'own_evil', NULL, NULL)",
    "CREATE TEMP TABLE rra_report_jobs (job_id text, owner_id text, session_id text, state text, "
    "available_at timestamptz, attempt_count int, max_attempts int, "
    "lease_expires_at timestamptz, queued_at timestamptz)",
    "INSERT INTO rra_report_jobs VALUES ('job_evil', 'own_evil', 'ses_e', 'queued', "
    "'2000-01-01', 0, 3, NULL, '2000-01-01')",
    "SET LOCAL search_path = pg_temp, public",
)


def _every_answer(connection: Connection) -> tuple:
    return (_lookup(connection, A.session_id), *(_picked(connection, f) for f in PICKERS))


def test_a_temp_table_of_the_same_name_cannot_redirect_a_definer_function(
    rls: RlsDatabase,
) -> None:
    """The caller holds `EXECUTE` on all four, puts `pg_temp` first, and gets the same answers."""
    rls.seed(_session_and_job(A) + _running(Scope("own_b", "sb"), NOW - HOUR))
    with rls.engine(WORKER).begin() as connection:
        baseline = _every_answer(connection)
        for statement in _SHADOWS:
            connection.execute(text(statement))
        assert connection.scalar(text("SELECT owner_id FROM rra_beta_sessions LIMIT 1"))
        shadowed = _every_answer(connection)
    assert shadowed == baseline
