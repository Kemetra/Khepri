"""RRA-017 Verification 13, and `reconcile` from Verification 17, through `#388`'s harness (`#595`).

`FR-239`: route-level tests reuse `tests/w110_postgres_support.py`, whose `postgres_journeys`
builds one deployed-shaped journey per runtime role over the migrated schema under `FORCE`. The
routes run as the application role and the report worker as the worker role, through the
deployed claim loop (`ClaimWorkerLoop` over `ClaimingReportQueue` and the settling store), so the
wall is shown not to break the paths it sits beneath. The rerun of the existing RRA route and
store suites under the application role is the plan's Verification 13 mechanism; these cases are
its end-to-end floor.

Pinned RED at `f1639c1`, before the slice existed; green from `#595`'s implementation.
"""

from __future__ import annotations

from datetime import datetime

from khepri.rra.claim_queue import ClaimingReportQueue, ClaimPolicy
from khepri.rra.worker import ReportWorker, WorkerPolicy
from khepri.runtime.pipeline_recording import SettlingJobStore
from khepri.runtime.worker import ClaimWorkerLoop
from tests.rra017_support import APPLICATION, POSTGRES, WORKER
from tests.w104_support import member
from tests.w104b_support import (
    LEASE_FOR,
    RETRY_DELAY,
    WORKER_ID,
    Journey,
    invited_client,
    request_report,
    submit,
)
from tests.w106_support import detail_address, shell_over, submitted
from tests.w110_postgres_support import postgres_journeys

pytestmark = list(POSTGRES)


def _claim_loop(worker: Journey, *, settling: bool = True) -> ClaimWorkerLoop:
    """The deployed worker loop over the worker role's journey, as `build_worker_loop` builds it."""
    jobs = (
        SettlingJobStore(worker.jobs, reader=worker.reader, recorder=worker.recorder)
        if settling
        else worker.jobs
    )
    return ClaimWorkerLoop(
        queue=ClaimingReportQueue(
            jobs=jobs,
            factory=worker.w.factory,
            policy=ClaimPolicy(worker_id=WORKER_ID, lease_for=LEASE_FOR),
        ),
        worker=ReportWorker(
            jobs=jobs,
            handler=worker.pipeline(),
            clock=worker.clock,
            policy=WorkerPolicy(worker_id=WORKER_ID, lease_for=LEASE_FOR, retry_delay=RETRY_DELAY),
        ),
        jobs=worker.reader,
        clock=worker.clock,
    )


def _state(client: object, job_id: str) -> str:
    response = client.get(f"/api/v1/beta/reports/{job_id}")
    assert response.status_code == 200, response.text
    return response.json()["state"]


def test_an_invited_report_is_requested_delivered_and_read_across_the_two_roles() -> None:
    with postgres_journeys(APPLICATION, WORKER) as (web, worker):
        client = invited_client(web)
        submit(client)
        job_id = request_report(client)
        assert _claim_loop(worker).run_once()
        assert _state(client, job_id) == "succeeded"


def test_a_members_delivered_run_reads_back_through_the_shell() -> None:
    with postgres_journeys(APPLICATION, WORKER) as (web, worker):
        who = member(web.w)
        client, _session_id = submitted(web, who)
        request_report(client)
        assert _claim_loop(worker).run_once()
        (run,) = web.w.store.analysis_runs_for_scope(who.owner_id)
        detail = shell_over(web, who).get(detail_address(who, run.run_id))
        assert detail.status_code == 200, detail.text


def test_reconcile_settles_the_started_runs_of_both_scopes() -> None:
    """Verification 17. Delivered without the settling store, as a crash between delivery and
    recording leaves them, then walked by `reconcile` as the worker role."""
    with postgres_journeys(APPLICATION, WORKER) as (web, worker):
        members = (member(web.w, "a@example.test", "A"), member(web.w, "b@example.test", "B"))
        for who in members:
            client, _session_id = submitted(web, who)
            request_report(client)
        loop = _claim_loop(worker, settling=False)
        assert loop.run_once() and loop.run_once()
        now: datetime = worker.clock()
        assert worker.recorder.reconcile(now=now) == 2
        for who in members:
            (run,) = web.w.store.analysis_runs_for_scope(who.owner_id)
            assert run.state == "completed", who
