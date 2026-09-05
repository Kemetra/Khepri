"""`W1-04b` -- the deployed pipeline records the workspace (`RCA-005` `FR-110`, `FR-111`,
`FR-125`; `RCA-002` `FR-049`).

Review on `#373` found that nothing in `src/khepri` called `WorkspaceActions`: the shell's entry
route opened a journey session and recorded nothing, so a customer who ran analyses through the
deployed journey would open Overview and read that nothing had been submitted. These cases drive
the journey's own HTTP routes and the real worker over one engine, then read the shell surfaces
the way `W1-05` renders them. Nothing here calls a workspace action directly -- that is the point.

Three seams, each recorded by the pipeline stage that produced the fact (`FR-110`: the version is
what admission decided; `FR-111`: the run is what the pipeline delivered):

- `POST /profile` admits a source -> a dataset version exists;
- `POST /reports` queues the job -> an analysis run is started and bound to that job;
- the worker settles the job -> the run completes with every artifact by digest, or fails when the
  job is dead-lettered.
"""

from __future__ import annotations

from datetime import timedelta

from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    ACTOR_PIPELINE,
    OUTCOME_ALREADY_RECORDED,
    OUTCOME_COMPLETED,
)
from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_FAILED, RUN_STARTED
from khepri.rra.jobs import JOB_DEAD_LETTERED, JOB_RETRYABLE, JOB_SUCCEEDED
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_copy import SHELL_COPY
from tests.w104_support import GOLDEN_CSV, OTHER_CSV, events, member
from tests.w104b_support import (
    RETRY_DELAY,
    BrokenHandler,
    commercial_client,
    invited_client,
    journey,
    profile_body,
    request_report,
    submit,
)
from tests.w105_support import page, staged_analyses_page

EN = SHELL_COPY["en"]
#: Between an action and its repeat, so the two events carry distinct instants and the audit
#: store's `occurred_at` order is the order they happened in.
A_MOMENT = timedelta(seconds=1)


def _outcomes(j, who, action: str) -> list[str]:
    return [event.outcome for event in events(j.w, who) if event.action == action]


# --- FR-110: admission through the deployed route records the version ---------------------------


def test_the_deployed_journeys_admission_puts_the_data_on_the_data_surface() -> None:
    """The lie `#373` found, stated as the assertion that would have caught it: after the
    journey's own upload and profile routes, Data lists the submission and says it was admitted."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)

    submit(client)

    versions = j.w.store.dataset_versions_for_scope(who.owner_id)
    assert len(versions) == 1
    html = page(j.w, who, "data")
    assert html.count('class="data-item"') == 1
    assert EN["data_admitted"] in html
    assert EN["data_empty"] not in html


def test_the_version_is_recorded_as_the_pipelines_own_action() -> None:
    """`FR-125`: one event, and the actor is the pipeline -- the beta cookie names a session, not
    an account, so the event cannot name the member and does not pretend to."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)

    submit(client)

    recorded = [event for event in events(j.w, who) if event.action == ACTION_VERSION_CREATED]
    assert [event.outcome for event in recorded] == [OUTCOME_COMPLETED]
    assert recorded[0].actor_account_id == ACTOR_PIPELINE
    assert recorded[0].owner_id == who.owner_id


def test_re_posting_the_profile_records_one_version_and_says_so() -> None:
    """`profile_session_upload` is idempotent and so is the recording: a retried request finds the
    version by its upload digest and leaves one row and an `already_recorded` event."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    j.clock.advance(A_MOMENT)

    again = client.post("/api/v1/beta/profile", json=profile_body(GOLDEN_CSV, attest=True))

    assert again.status_code == 200, again.text
    assert len(j.w.store.dataset_versions_for_scope(who.owner_id)) == 1
    assert _outcomes(j, who, ACTION_VERSION_CREATED) == [
        OUTCOME_COMPLETED,
        OUTCOME_ALREADY_RECORDED,
    ]


def test_a_second_organization_on_the_same_engine_sees_none_of_it() -> None:
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    client, _session_id = commercial_client(j, who)
    submit(client, OTHER_CSV)

    assert j.w.store.dataset_versions_for_scope(other.owner_id) == ()
    assert EN["data_empty"] in page(j.w, other, "data")


# --- FR-111: the report job starts the run; the worker completes or fails it -------------------


def test_requesting_the_report_starts_the_run_and_overview_shows_it_processing() -> None:
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)

    job_id = request_report(client)

    runs = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert [run.state for run in runs] == [RUN_STARTED]
    assert j.reports.run_id_for_job(who.owner_id, job_id) == runs[0].run_id
    html = page(j.w, who, "overview")
    assert EN["run_state_started"] in html
    assert EN["overview_no_work"] not in html


def test_the_worker_completes_the_run_with_every_delivered_artifact_by_digest() -> None:
    """The completion is what the publisher wrote: seven bindings, each digest the stored
    artifact's own, the version sealed, and Overview no longer processing."""
    j = journey()
    who = member(j.w)
    client, session_id = commercial_client(j, who)
    submit(client)
    job_id = request_report(client)

    j.run_job(job_id)

    job = j.reader.find(job_id)
    assert job is not None and job.state == JOB_SUCCEEDED
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert run.state == RUN_COMPLETED
    assert run.package_digest and run.package_version and run.formula_version
    bound = {
        binding.surface: binding.artifact_digest
        for binding in j.w.store.artifact_bindings_for_run(run.run_id, who.owner_id)
    }
    assert set(bound) == set(REQUIRED_ARTIFACT_KINDS)
    for kind in REQUIRED_ARTIFACT_KINDS:
        stored = j.artifacts.find_in_session(
            session_id=session_id, job_id=job_id, artifact_kind=kind, now=j.clock()
        )
        assert stored is not None and bound[kind] == stored.sha256_hex
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    assert version.sealed_at is not None
    html = page(j.w, who, "overview")
    assert EN["run_state_completed"] in html
    assert EN["run_state_started"] not in html


def test_the_analyses_spine_reads_the_completed_run_with_its_report_available() -> None:
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    j.run_job(request_report(client))

    html = staged_analyses_page(j.w, who)

    assert EN["run_state_completed"] in html
    assert EN["report_available"] in html
    assert EN["report_not_yet"] not in html


def test_completion_is_one_event_and_a_second_worker_pass_records_it_as_already_done() -> None:
    """A redelivered job costs the pipeline a lookup (`ReportPipeline.run`) and costs the
    workspace one `already_recorded` event, never a second completion."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    job_id = request_report(client)
    j.run_job(job_id)
    j.clock.advance(A_MOMENT)

    j.recorder.settled(j.reader.find(job_id), now=j.clock())

    assert _outcomes(j, who, ACTION_RUN_COMPLETED) == [
        OUTCOME_COMPLETED,
        OUTCOME_ALREADY_RECORDED,
    ]
    assert len(j.w.store.artifact_bindings_for_scope(who.owner_id)) == len(
        REQUIRED_ARTIFACT_KINDS
    )


def test_a_failed_attempt_that_will_retry_leaves_the_run_processing() -> None:
    """A retryable failure is not an outcome the customer can act on yet; the run stays
    `started`, which Overview shows as processing, and no failure event is written."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    job_id = request_report(client)

    j.run_job(job_id, handler=BrokenHandler())

    job = j.reader.find(job_id)
    assert job is not None and job.state == JOB_RETRYABLE
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert run.state == RUN_STARTED
    assert _outcomes(j, who, ACTION_RUN_FAILED) == []


def test_a_dead_lettered_job_fails_the_run_and_overview_asks_for_attention() -> None:
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    job_id = request_report(client)
    broken = BrokenHandler()

    for _attempt in range(3):
        j.run_job(job_id, handler=broken)
        j.clock.advance(RETRY_DELAY * 2)

    job = j.reader.find(job_id)
    assert job is not None and job.state == JOB_DEAD_LETTERED
    assert broken.attempts == 3
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert run.state == RUN_FAILED
    assert _outcomes(j, who, ACTION_RUN_FAILED) == [OUTCOME_COMPLETED]
    html = page(j.w, who, "overview")
    assert EN["run_state_failed"] in html
    assert 'class="attention-list"' in html


def test_a_dead_letter_reported_twice_fails_the_run_once() -> None:
    """The symmetry of the completion case: a second report of the same abandonment is one
    `already_recorded` event, never a refusal and never a second failure."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    job_id = request_report(client)
    for _attempt in range(3):
        j.run_job(job_id, handler=BrokenHandler())
        j.clock.advance(RETRY_DELAY * 2)

    j.recorder.abandoned(j.reader.find(job_id), now=j.clock())

    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert run.state == RUN_FAILED
    assert _outcomes(j, who, ACTION_RUN_FAILED) == [OUTCOME_COMPLETED, OUTCOME_ALREADY_RECORDED]


def test_re_requesting_the_report_is_the_same_run() -> None:
    """`ReportRequestAdapter` returns the same job for the same session and package; the
    workspace returns the same run for the same job, and says `already_recorded`."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client)
    first = request_report(client)
    j.clock.advance(A_MOMENT)

    second = request_report(client)

    assert second == first
    assert len(j.w.store.analysis_runs_for_scope(who.owner_id)) == 1
    assert _outcomes(j, who, ACTION_RUN_STARTED) == [
        OUTCOME_COMPLETED,
        OUTCOME_ALREADY_RECORDED,
    ]


def test_the_same_file_submitted_twice_is_one_version_with_two_runs() -> None:
    """Run Again's shape (`FR-114`), reached through the deployed routes: a second session over
    the same bytes finds the existing version by digest and starts its own run over it."""
    j = journey()
    who = member(j.w)
    first, _s1 = commercial_client(j, who)
    submit(first)
    j.run_job(request_report(first))
    second, _s2 = commercial_client(j, who)
    submit(second)

    j.run_job(request_report(second))

    versions = j.w.store.dataset_versions_for_scope(who.owner_id)
    runs = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert len(versions) == 1
    assert [run.state for run in runs] == [RUN_COMPLETED, RUN_COMPLETED]
    assert {run.version_id for run in runs} == {versions[0].version_id}


# --- What is deliberately not recorded ----------------------------------------------------------


def test_a_session_no_organization_owns_records_nothing_and_still_gets_its_report() -> None:
    """An invitation-redeemed design-partner session has no isolation scope and so no
    workspace. The pipeline records nothing for it and does not refuse it either."""
    j = journey()
    client = invited_client(j)
    submit(client)
    job_id = request_report(client)

    j.run_job(job_id)

    job = j.reader.find(job_id)
    assert job is not None and job.state == JOB_SUCCEEDED
    assert j.reports.run_id_for_job(job.owner_id, job_id) is None
    assert j.w.store.dataset_versions_for_scope(job.owner_id) == ()
    assert j.w.audit.events_for_scope(job.owner_id) == ()


def test_an_unattested_source_is_not_a_dataset_version_and_its_run_is_not_recorded() -> None:
    """`W1-01` made the coverage manifest part of a version (`KHEPRI-DEC-033` §3 keeps its
    digest), and the journey's attestation is optional. A profile without one is not a version,
    so nothing is recorded and no event is written -- a gap this slice states rather than fills."""
    j = journey()
    who = member(j.w)
    client, _session_id = commercial_client(j, who)
    submit(client, attest=False)
    job_id = request_report(client)

    j.run_job(job_id)

    job = j.reader.find(job_id)
    assert job is not None and job.state == JOB_SUCCEEDED
    assert j.w.store.dataset_versions_for_scope(who.owner_id) == ()
    assert j.w.store.analysis_runs_for_scope(who.owner_id) == ()
    assert events(j.w, who) == ()
