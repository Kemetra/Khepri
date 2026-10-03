"""RRA-017 Verification 17: `RRA-007`'s recovery under `FORCE`, as the worker role (`#595`).

`FR-268`: the candidates come from `FR-267`'s functions, and each is transitioned in its own
transaction scoped to its `owner_id`, which re-reads it `FOR UPDATE SKIP LOCKED` under the same
predicate. The interleaving test hooks that per-candidate re-read, the seam that survives any
refactor of the store, rather than a helper it calls. `reconcile` across scopes is in
`test_rra017_routes_postgres.py`, which has the workspace composition it needs.

Pinned RED at `f1639c1`, before the slice existed; green from `#595`'s implementation.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Engine, event

from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.report_services import JobReader
from khepri.runtime.worker import ClaimWorkerLoop
from tests.rra017_rows import HOUR, NOW, Scope, row
from tests.rra017_support import POSTGRES, RED, WORKER, RlsDatabase, rls_fixture  # noqa: F401

pytestmark = list(POSTGRES)

EARLY = Scope("own_a", "ea")
LATE = Scope("own_b", "lb")
DELETED = {"deletion_requested_at": NOW - 2 * HOUR, "content_deleted_at": NOW - HOUR}


def _job(scope: Scope, session: dict | None = None, **job: Any) -> list:
    return [
        ("rra_beta_sessions", row(scope, "rra_beta_sessions", **(session or {}))),
        ("rra_report_jobs", row(scope, "rra_report_jobs", **job)),
    ]


def _expired(scope: Scope, by: Any) -> list:
    return _job(
        scope,
        state="running",
        lease_owner="worker-dead",
        lease_expires_at=NOW - by,
        attempt_count=1,
    )


def _attempts(rls: RlsDatabase) -> set[tuple[str, str]]:
    rows = rls.as_owner("SELECT job_id, disposition FROM rra_report_job_attempts")
    return {tuple(found) for found in rows}


def test_one_recover_expired_call_reclaims_the_leases_of_both_scopes(rls: RlsDatabase) -> None:
    rls.seed(_expired(EARLY, 2 * HOUR) + _expired(LATE, HOUR))
    recovered = SqlReportJobRepository(rls.factory(WORKER)).recover_expired(now=NOW)
    assert {job.owner_id for job in recovered} == {"own_a", "own_b"}
    assert _attempts(rls) == {(EARLY.job_id, "lease_reclaimed"), (LATE.job_id, "lease_reclaimed")}


def test_one_recover_orphans_call_dead_letters_the_orphans_of_both_scopes(
    rls: RlsDatabase,
) -> None:
    rls.seed(_job(EARLY, DELETED) + _job(LATE, DELETED))
    orphaned = SqlReportJobRepository(rls.factory(WORKER)).recover_orphans(now=NOW)
    assert {(job.owner_id, job.dead_letter_reason) for job in orphaned} == {
        ("own_a", "content_deleted"),
        ("own_b", "content_deleted"),
    }


def _is_candidate_reread(statement: str) -> bool:
    """The per-candidate re-read: a `SKIP LOCKED` read of `rra_report_jobs`."""
    return all(marker in statement for marker in ("SKIP LOCKED", "rra_report_jobs"))


class _LeaseOnReRead:
    """Before the first per-candidate re-read runs, another worker leases that candidate."""

    def __init__(self, rls: RlsDatabase, job_id: str) -> None:
        self._rls = rls
        self._job_id = job_id
        self.fired = False

    def __call__(self, *event_arguments: Any) -> None:
        """`before_cursor_execute(conn, cursor, statement, ...)`: the statement is third."""
        if self.fired or not _is_candidate_reread(event_arguments[2]):
            return
        self.fired = True
        self._rls.as_owner(
            "UPDATE rra_report_jobs SET lease_owner = 'worker-other', lease_expires_at = :until, "
            "attempt_count = attempt_count + 1 WHERE job_id = :job",
            until=NOW + HOUR,
            job=self._job_id,
        )


def test_a_candidate_another_worker_leases_before_its_reread_is_skipped(rls: RlsDatabase) -> None:
    rls.seed(_expired(EARLY, 2 * HOUR) + _expired(LATE, HOUR))
    engine: Engine = rls.engine(WORKER)
    hook = _LeaseOnReRead(rls, EARLY.job_id)
    event.listen(engine, "before_cursor_execute", hook)
    recovered = SqlReportJobRepository(rls.factory(WORKER)).recover_expired(now=NOW)
    assert hook.fired, "the per-candidate re-read never ran"
    assert [job.job_id for job in recovered] == [LATE.job_id]
    assert _attempts(rls) == {(LATE.job_id, "lease_reclaimed")}
    leased = rls.as_owner(
        "SELECT lease_owner FROM rra_report_jobs WHERE job_id = :j", j=EARLY.job_id
    )
    assert leased == [("worker-other",)]


class _Idle:
    """A worker that settles nothing: this test is about what the loop asks first."""

    def execute(self, job: Any, *, heartbeat: Any) -> Any:
        return job


def test_the_worker_loop_recovers_before_it_claims(rls: RlsDatabase) -> None:
    rls.seed(_job(EARLY))
    factory = rls.factory(WORKER)
    jobs = SqlReportJobRepository(factory)
    loop = ClaimWorkerLoop(
        queue=ClaimingReportQueue(
            jobs=jobs,
            factory=factory,
            policy=ClaimPolicy(worker_id="w-595", lease_for=HOUR),
        ),
        worker=_Idle(),
        jobs=JobReader(factory),
        clock=lambda: NOW,
    )
    seen: list[str] = []
    event.listen(rls.engine(WORKER), "before_cursor_execute", lambda *a: seen.append(a[2]))
    assert loop.run_once()
    order = [
        name
        for s in seen
        for name in ("rra_expired_lease_jobs", "rra_next_claimable_job")
        if name in s
    ]
    assert order[:2] == ["rra_expired_lease_jobs", "rra_next_claimable_job"]
