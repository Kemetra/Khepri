"""`FR-127`'s concurrent case class, over PostgreSQL and the real routes (`#388`, `W1-10`).

`test_w110_lifecycle_isolation.py`'s `TestConcurrent` drives the sequential halves -- a retry, and
a handoff after an ending -- because its SQLite fixture cannot hold two transactions open at once.
These are the overlapping cases that class records it could not drive, run on
`w110_postgres_support`'s PostgreSQL `journey()`.

Each forces its interleaving rather than hoping for one: the first request is held at a named
point, the second is started, and where a lock is the claim `pg_stat_activity` must show the
second *waiting on a lock* before the first is let go. A lock that is present in the compiled SQL
but not held -- the only thing `test_w102_workspace_locks.py` can assert -- fails that proof.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_VERSION_DELETED,
    OUTCOME_ALREADY_DELETED,
    OUTCOME_COMPLETED,
)
from khepri.rca.workspace.tombstones import RunTombstone, VersionTombstone
from khepri.rra.session_cookie import SESSION_COOKIE
from khepri.runtime.workspace_recording import WorkspaceRefused
from tests.w104_support import LATER, Member, member
from tests.w104b_support import Journey
from tests.w106_support import HTTPS, completed_run, handoff_address, started_run
from tests.w107_support import (
    NOW,
    delete_address,
    deletion_jobs_for,
    deletion_service,
    sealed_version,
    shell_with_deletion,
)
from tests.w110_postgres_support import (
    WAIT_SECONDS,
    Background,
    LockPause,
    PausedCall,
    blocked_on_a_lock,
    delivered_unsettled,
    engine_of,
    postgres_journey,
    requires_postgres,
    shell_with_bridge,
)
from tests.w110_support import Denials, assert_uniform_denial

pytestmark = [pytest.mark.concurrency, requires_postgres]

VERSIONS = "rca_workspace_dataset_versions"


def _outcomes(j: Journey, who: Member, action: str) -> list[str]:
    return sorted(e.outcome for e in j.w.audit.events_for_scope(who.owner_id) if e.action == action)


def _tombstones_of(j: Journey, who: Member, kind: type, subject_id: str) -> list[object]:
    subject = "run_id" if kind is RunTombstone else "version_id"
    return [
        stone
        for stone in j.w.store.tombstones_for_scope(who.owner_id)
        if isinstance(stone, kind) and getattr(stone, subject) == subject_id
    ]


def test_two_overlapping_deletions_end_the_version_once() -> None:
    """Two deletions of one version, the second arriving while the first holds the version lock.

    Both pass the unlocked fast path in `delete_version` -- the first has not committed -- so only
    the lock inside `set_retention_state` stands between them and a second ending. Asserted: the
    second really waited on that lock; both callers get byte-identical answers; one version
    tombstone and one run tombstone, so the cascade ran once; one `completed` and one
    `already_deleted` event (`FR-123`); and one content-deletion job.
    """
    with postgres_journey() as j:
        who = member(j.w)
        version, run = sealed_version(j, who, with_run=True)
        address = delete_address(who, version.version_id)
        first_shell, second_shell = shell_with_deletion(j, who), shell_with_deletion(j, who)
        pause = LockPause(engine_of(j), VERSIONS)
        pause.arm()
        try:
            first = Background(lambda: first_shell.post(address, follow_redirects=False))
            assert pause.reached.wait(WAIT_SECONDS), "the first deletion never took the lock"
            second = Background(lambda: second_shell.post(address, follow_redirects=False))
            assert blocked_on_a_lock(engine_of(j)), (
                "the second deletion never waited on the version lock; FOR UPDATE is not held"
            )
            assert not second.finished, "the second deletion finished while the first held the lock"
        finally:
            pause.disarm()

        answers = (first.result(), second.result())

        assert_uniform_denial(Denials(answers, ("first delete", "overlapping delete")), status=303)
        assert len(_tombstones_of(j, who, VersionTombstone, version.version_id)) == 1
        assert len(_tombstones_of(j, who, RunTombstone, run.run_id)) == 1, "the cascade ran twice"
        assert _outcomes(j, who, ACTION_VERSION_DELETED) == sorted(
            [OUTCOME_COMPLETED, OUTCOME_ALREADY_DELETED]
        )
        assert len(deletion_jobs_for(j, who.owner_id)) == 1


def _late_handoff(j: Journey, who: Member):
    """A handoff that has read the run as live and reachable, held while the deletion completes,
    then let go. Returns its answer.

    The ordering the issue names: an artifact cookie issued *after* the ending is recorded hands
    out exactly what the deletion was for. The handoff takes no lock, so what must stop it is a
    check at or after the point it acts -- held here with a `PausedCall` on the bridge's `resume`.
    """
    run, _job, _session = completed_run(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    bridge = PausedCall(_real_bridge(j, who), "resume")
    shell = shell_with_bridge(j, who, bridge)
    handoff = Background(
        lambda: shell.post(handoff_address(who, run.run_id, "web"), follow_redirects=False)
    )
    assert bridge.reached.wait(WAIT_SECONDS), "the handoff never reached the bridge"
    ended = deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    bridge.release.set()
    assert ended.deleted, "the deletion did not end the version, so nothing is proven"
    return handoff.result()


def test_a_late_handoff_does_not_hand_over_ended_content() -> None:
    """Whatever the handoff answers, the artifact it points at is not served for the ended session.

    This is the property that holds today, and it holds one step later than it should: the handoff
    itself still answers `303` with a cookie (`#605`, below). Followed with that cookie, the report
    API refuses -- so what the deletion was for is not handed over.
    """
    with postgres_journey() as j:
        who = member(j.w)
        answer = _late_handoff(j, who)

        if answer.status_code == 404:
            assert "set-cookie" not in answer.headers
            return
        beta = TestClient(j.app, base_url=HTTPS)
        beta.cookies.set(SESSION_COOKIE, answer.cookies.get(SESSION_COOKIE) or "")
        artifact = beta.get(answer.headers["location"])
        assert artifact.status_code == 404, "the late handoff's cookie served the ended artifact"


@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason="#605: the handoff re-checks nothing after `_locate`, so it issues a cookie for a "
    "session whose ending was recorded while it was in flight",
)
def test_a_late_handoff_issues_no_cookie_for_an_ended_session() -> None:
    """`FR-127`'s uniform denial, at the handoff itself: no `303`, and no cookie beside it.

    Strict, so fixing `#605` fails this marker and forces it to be removed rather than left to
    describe a defect that no longer exists.
    """
    with postgres_journey() as j:
        who = member(j.w)
        answer = _late_handoff(j, who)

        assert answer.status_code == 404, "handed off an artifact after its ending was recorded"
        assert "set-cookie" not in answer.headers


def test_a_handoff_during_the_ending_does_not_hand_over_ended_content() -> None:
    """The deletion holds the version lock, its tombstone not yet committed, when the handoff runs.

    The content ending commits before the records do (`workspace_deletion.py` states why), so the
    window here is real: the run still reads as live. The handoff must refuse on the session's
    recorded deletion rather than succeed on the uncommitted tombstone's absence.
    """
    with postgres_journey() as j:
        who = member(j.w)
        run, _job, _session = completed_run(j, who)
        (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
        pause = LockPause(engine_of(j), VERSIONS)
        pause.arm()
        try:
            deleting = Background(
                lambda: deletion_service(j).delete_version(
                    who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
                )
            )
            assert pause.reached.wait(WAIT_SECONDS), "the deletion never took the version lock"
            answer = shell_with_bridge(j, who, _real_bridge(j, who)).post(
                handoff_address(who, run.run_id, "web"), follow_redirects=False
            )
        finally:
            pause.disarm()

        assert deleting.result().deleted
        assert answer.status_code == 404, "handed off content whose ending was in progress"
        assert "set-cookie" not in answer.headers


def _overlapping_settlements(j: Journey, who: Member) -> tuple[str, Background]:
    """The worker's settlement and the reconcile sweep, both reaching `record_completion` for one
    run, the sweep started while the settlement holds the version lock. Returns the run and the
    sweep, whose outcome the callers read differently.

    Both read the run as `started` -- the first has not committed -- so the version and run locks
    are all that serialise them. The sweep must be seen waiting on a lock before the first goes.
    """
    run, job_id, _session = started_run(j, who)
    delivered_unsettled(j, job_id)
    job = j.reader.find(job_id)
    pause = LockPause(engine_of(j), VERSIONS)
    pause.arm()
    try:
        settling = Background(lambda: j.recorder.settled(job, now=NOW))
        assert pause.reached.wait(WAIT_SECONDS), "the settlement never took the version lock"
        sweeping = Background(lambda: j.recorder.reconcile_job(job_id, now=LATER))
        assert blocked_on_a_lock(engine_of(j)), (
            "the sweep never waited on a lock; the completion is not serialised"
        )
        assert not sweeping.finished, "the sweep settled the run while the first held the lock"
    finally:
        pause.disarm()
    settling.result()
    sweeping.failure()
    return run.run_id, sweeping


def test_two_settlements_of_one_run_complete_it_once() -> None:
    """What survives the overlap: the first settlement's completion, each surface bound once, one
    `completed` event.

    The sweep's own outcome is deliberately not read here. Today it ends in a fault that only the
    provenance row's primary key produces (`#606`, below), and the durable state is what this test
    claims -- a claim that would still be true, and still worth pinning, once `#606` is fixed.
    """
    with postgres_journey() as j:
        who = member(j.w)
        run_id, _sweep = _overlapping_settlements(j, who)

        completed = j.w.store.get_analysis_run(run_id, who.owner_id)
        bindings = j.w.store.artifact_bindings_for_scope(who.owner_id)
        assert completed is not None and completed.completed_at == NOW
        assert bindings, "nothing was bound, so nothing is proven"
        assert len(bindings) == len({binding.surface for binding in bindings}), (
            "a surface was bound twice: both settlements completed the run"
        )
        assert _outcomes(j, who, ACTION_RUN_COMPLETED).count(OUTCOME_COMPLETED) == 1


@pytest.mark.xfail(
    raises=AssertionError,
    strict=True,
    reason="#606: the locked re-check in `record_completion` reads the run from the session's "
    "identity map, so the loser passes it and faults on the provenance key",
)
def test_the_losing_settlement_is_refused_not_faulted() -> None:
    """The loser's answer: the refusal `perform` records, or nothing -- never a database fault.

    A fault here means the guard under the lock let the second completion through and something
    after it happened to stop it. Strict, so fixing `#606` forces the marker off.
    """
    with postgres_journey() as j:
        who = member(j.w)
        _run_id, sweep = _overlapping_settlements(j, who)

        failure = sweep.failure()
        assert failure is None or isinstance(failure, WorkspaceRefused), repr(failure)


def _real_bridge(j: Journey, who: Member):
    from tests.w106_support import services_over

    return services_over(j, who).bridge
