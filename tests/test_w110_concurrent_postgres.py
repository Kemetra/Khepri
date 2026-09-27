"""`FR-127`'s concurrent case class, over PostgreSQL and the real routes (`#388`, `W1-10`): deletion
overlapping deletion, and deletion overlapping the artifact handoff.

`test_w110_lifecycle_isolation.py`'s `TestConcurrent` drives the sequential halves -- a retry, and
a handoff after an ending -- because its SQLite fixture cannot hold two transactions open at once.
These are the overlapping cases that class records it could not drive, run on
`w110_postgres_support`'s PostgreSQL `journey()`. The run-level cases -- two runs over one version,
and a run failing while it is deleted or settled -- are `test_w110_concurrent_runs_postgres.py`'s.

Each forces its interleaving rather than hoping for one: the first request is held at a named
point, the second is started, and where a lock is the claim `pg_stat_activity` must show the
second *waiting on the first's lock* before the first is let go. A lock that is present in the
compiled SQL but not held -- all `test_w102_workspace_locks.py` can assert -- fails that proof.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from khepri.rca.workspace.audit import (
    ACTION_VERSION_DELETED,
    OUTCOME_ALREADY_DELETED,
    OUTCOME_COMPLETED,
)
from khepri.rca.workspace.tombstones import RunTombstone, VersionTombstone
from khepri.rra.session_cookie import SESSION_COOKIE
from tests.w104_support import Member, member
from tests.w104b_support import Journey
from tests.w106_support import HTTPS, completed_run, handoff_address, services_over
from tests.w107_support import (
    NOW,
    delete_address,
    deletion_jobs_for,
    deletion_service,
    sealed_version,
    shell_with_deletion,
)
from tests.w110_postgres_support import (
    Background,
    DefectStillPresent,
    LockPause,
    PausedCall,
    await_reached,
    engine_of,
    outcomes_of,
    overlap_on_lock,
    postgres_journey,
    requires_postgres,
    shell_with_bridge,
    tombstones_of,
)
from tests.w110_support import Denials, assert_uniform_denial

pytestmark = [pytest.mark.concurrency, requires_postgres]

VERSIONS = "rca_workspace_dataset_versions"
#: What the report API answers for a session whose artifacts are gone.
NO_ARTIFACT = "No report artifact is available for this session."


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

        both = overlap_on_lock(
            j,
            VERSIONS,
            lambda: first_shell.post(address, follow_redirects=False),
            lambda: second_shell.post(address, follow_redirects=False),
        )
        answers = (both.first.result(), both.second.result())

        assert_uniform_denial(Denials(answers, ("first delete", "overlapping delete")), status=303)
        assert len(tombstones_of(j, who.owner_id, VersionTombstone, version.version_id)) == 1
        assert len(tombstones_of(j, who.owner_id, RunTombstone, run.run_id)) == 1, (
            "the cascade ran twice"
        )
        assert outcomes_of(j, who.owner_id, ACTION_VERSION_DELETED) == sorted(
            [OUTCOME_COMPLETED, OUTCOME_ALREADY_DELETED]
        )
        assert len(deletion_jobs_for(j, who.owner_id)) == 1


def _paused_handoff(j: Journey, who: Member, *, delete: bool):
    """A handoff that has read the run as live and reachable, held before it resumes the session,
    optionally while the deletion completes, then let go. Returns its answer.

    The ordering the issue names: an artifact cookie issued *after* the ending is recorded hands
    out exactly what the deletion was for. The handoff takes no lock, so what must stop it is a
    check at or after the point it acts -- held here with a `PausedCall` on the bridge's `resume`.
    """
    run, _job, _session = completed_run(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    bridge = PausedCall(services_over(j, who).bridge, "resume")
    shell = shell_with_bridge(j, who, bridge)
    handoff = Background(
        lambda: shell.post(handoff_address(who, run.run_id, "web"), follow_redirects=False)
    )
    await_reached(bridge.reached, "the handoff")
    if delete:
        ended = deletion_service(j).delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )
        assert ended.deleted, "the deletion did not end the version, so nothing is proven"
    bridge.release.set()
    return handoff.result()


def _follow(j: Journey, answer):
    """The artifact the handoff redirected to, fetched with the cookie it set, as a browser does."""
    cookie = answer.cookies.get(SESSION_COOKIE)
    assert cookie, "the handoff answered 303 without the session cookie it exists to set"
    beta = TestClient(j.app, base_url=HTTPS)
    beta.cookies.set(SESSION_COOKIE, cookie)
    return beta.get(answer.headers["location"])


def test_a_held_handoff_with_no_deletion_hands_over_the_artifact() -> None:
    """The positive control for the two below: the same pause, no deletion, and the artifact is
    served. Without it a refusal below could be the harness breaking the handoff, not the ending."""
    with postgres_journey() as j:
        answer = _paused_handoff(j, member(j.w), delete=False)

        assert answer.status_code == 303
        assert _follow(j, answer).status_code == 200


def test_a_late_handoff_does_not_hand_over_ended_content() -> None:
    """Whatever the handoff answers, the artifact it points at is not served for the ended session.

    This is the property that holds today, one step later than it should: the handoff itself still
    answers `303` with a cookie (`#605`, below). Followed with that cookie, the report API refuses
    with its no-artifact answer -- so what the deletion was for is not handed over.
    """
    with postgres_journey() as j:
        answer = _paused_handoff(j, member(j.w), delete=True)

        if answer.status_code == 404:
            assert "set-cookie" not in answer.headers
            return
        artifact = _follow(j, answer)
        assert artifact.status_code == 404, "the late handoff's cookie served the ended artifact"
        assert artifact.json() == {"detail": NO_ARTIFACT}


@pytest.mark.xfail(
    raises=DefectStillPresent,
    strict=True,
    reason="#605: the handoff re-checks nothing after `_locate`, so it issues a cookie for a "
    "session whose ending was recorded while it was in flight",
)
def test_a_late_handoff_issues_no_cookie_for_an_ended_session() -> None:
    """`FR-127`'s uniform denial, at the handoff itself: no `303`, and no cookie beside it.

    Strict and pinned to `DefectStillPresent`, so fixing `#605` fails the marker and a broken
    harness errors rather than reading as the defect still being there.
    """
    with postgres_journey() as j:
        answer = _paused_handoff(j, member(j.w), delete=True)

        if answer.status_code != 404 or "set-cookie" in answer.headers:
            raise DefectStillPresent("handed off an artifact after its ending was recorded (#605)")


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
            await_reached(pause.reached, "the deletion")
            answer = shell_with_bridge(j, who, services_over(j, who).bridge).post(
                handoff_address(who, run.run_id, "web"), follow_redirects=False
            )
        finally:
            pause.disarm()

        assert deleting.result().deleted
        assert answer.status_code == 404, "handed off content whose ending was in progress"
        assert "set-cookie" not in answer.headers
