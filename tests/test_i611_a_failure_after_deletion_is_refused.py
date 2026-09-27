"""Failing a run its version's deletion already ended is refused, not faulted (`#611`).

`complete_analysis_run` re-checked the run under its lock with `_visible_in` -- the scope alone --
where `record_completion` uses `_live_in`, which also reads the tombstone and the revocation ledger.
A run the cascade had tombstoned while still `started` passed that re-check, reached the write, and
the tombstone guard raised `ValueError`. The fault landed in `perform` instead of the refusal the
store states for a run it cannot complete: `False`.

No second transaction is needed: the deletion commits, then the dead-letter door fails the run.
`tests/test_w110_concurrent_runs_postgres.py` drives the same door against the cascade holding the
run's lock.
"""

from __future__ import annotations

from khepri.rca.workspace.contracts import RUN_FAILED, RunOutcome
from tests.w104_support import LATER, member
from tests.w104b_support import journey
from tests.w106_support import started_run
from tests.w107_support import NOW, deletion_service


def test_failing_a_run_its_deletion_ended_is_refused() -> None:
    j = journey()
    who = member(j.w)
    run, _job_id, _session_id = started_run(j, who)
    deletion_service(j).delete_version(
        who.owner_id, run.version_id, actor_account_id=who.account_id, now=NOW
    )

    completed = j.w.store.complete_analysis_run(
        run.run_id, RunOutcome(state=RUN_FAILED, completed_at=LATER), owner_id=who.owner_id
    )

    assert completed is False
    assert j.w.store.get_analysis_run(run.run_id, who.owner_id) is None
