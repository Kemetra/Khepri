"""`W1-06` -- the provenance a run retains, and the read behind its Passport (`RCA-005` `FR-119`;
`KHEPRI-DEC-033` §2).

The Passport is read from the record the run retained at completion -- the attested period and day
boundary, the coverage scope, who attested, the admitted row count, and each section's outcome --
written in the completion's own transaction from the admission and the package the run binds. It
lives with the run: the analysis session's content ends on its own horizon and the Passport does
not end with it (review on `#376`). What is still the session's is the artifact handoff, which the
read reports as `reachable` only while that session can be resumed.

At completion the package is rebuilt and checked against its digest before a section outcome is
recorded; a document that rebuilds to another package, or a digest that names another, is refused
there and no provenance is written. A completed run without its record has no Passport to state
(`None`): runs completed before `20260905_0024` retained none, and the surface must still render
for them (review on `#376` round 2). Only a link to another scope's job is corruption
(`UnrenderableRecord`).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from sqlalchemy import delete

from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_STARTED
from khepri.rca.workspace.persistence import RunProvenanceRow
from khepri.rca.workspace.provenance import SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import RunReport
from khepri.rca.workspace.schema import FAMILY_SECTIONS
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rra.bundle import FAMILY_VERSIONS
from khepri.runtime.job_sessions import SqlJobSessions
from khepri.runtime.run_quality import PackageDoesNotVerify, section_states_of
from khepri.runtime.shell_provenance import Provenance, ProvenanceReader, ProvenanceSources
from khepri.runtime.shell_workspace import UnrenderableRecord
from tests.w104_support import OTHER_CSV, member
from tests.w104b_support import commercial_client, journey, request_report, submit
from tests.w106_support import completed_run, provenance, started_run

#: The run identifiers `_LinkTo` answers a link for; appended by the test that uses it.
_RUNS_ASKED: list[str] = []


def _run_and_version(j, who):
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    return run, version


# --- The record a completed run retains -----------------------------------------------------------


def test_completion_retains_the_period_scale_and_section_outcomes_with_the_run() -> None:
    j = journey()
    who = member(j.w)
    _run, job_id, session_id = completed_run(j, who)
    run, version = _run_and_version(j, who)

    found = provenance(j).for_run(who.owner_id, run, version)

    assert isinstance(found, Provenance)
    assert found.job_id == job_id and found.session_id == session_id and found.reachable
    assert (found.covered_start.isoformat(), found.covered_end.isoformat()) == (
        "2026-01-05",
        "2026-01-07",
    )
    assert found.timezone == "Africa/Cairo" and found.row_count == 4
    # Every governed section has one of the three codes; the record is what the store holds.
    assert isinstance(found.sections, SectionStates)
    retained = SqlRunProvenanceStore(j.w.factory).for_run(run.run_id, who.owner_id)
    assert retained is not None and retained.sections == found.sections
    assert run.state == RUN_COMPLETED


def test_a_started_run_has_no_passport_yet() -> None:
    """Provenance is a fact about a completed derivation; before completion there is nothing to
    state, and the reader says so with `None` rather than a Passport of a run that has not run."""
    j = journey()
    who = member(j.w)
    started_run(j, who)
    run, version = _run_and_version(j, who)

    assert run.state == RUN_STARTED
    assert provenance(j).for_run(who.owner_id, run, version) is None


def test_the_passport_outlives_the_sessions_content_but_the_handoff_does_not() -> None:
    """`KHEPRI-DEC-033` §2: the provenance record lives with the run; the analysis session's
    content ends on its seven-day horizon. After it the Passport is still read, and `reachable`
    says the artifacts cannot be handed off -- `W1-07` reconciles artifact retention."""
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    run, version = _run_and_version(j, who)
    j.clock.advance(timedelta(days=8))

    found = provenance(j).for_run(who.owner_id, run, version)

    assert found is not None
    assert found.row_count == 4 and found.covered_start.isoformat() == "2026-01-05"
    assert found.reachable is False


def test_a_run_completed_through_the_customer_door_retains_provenance_but_has_no_report():
    """The customer door completes a run from the same admission and package, so the record is
    retained; with no job settling it there is no session to resume and nothing to hand off."""
    from tests.w105_support import completed_run as customer_completed

    j = journey()
    who = member(j.w)
    _session, _version, run_id = customer_completed(j.w, who)
    run = j.w.store.get_analysis_run(run_id, who.owner_id)
    version = j.w.store.get_dataset_version(run.version_id, who.owner_id)

    found = provenance(j).for_run(who.owner_id, run, version)

    assert found is not None and found.row_count == 4
    assert found.job_id is None and found.session_id is None and found.reachable is False


def test_a_run_completed_before_provenance_was_retained_has_no_passport_and_is_not_reachable():
    """`20260905_0024` backfills nothing, so a run completed before it has no record. That is an
    absence to state, not corruption to refuse: the reader answers `None` for that run -- and only
    for that run, borrowing no other run's record from the scope's batch -- and the surfaces say
    the Passport is unavailable and the report can no longer be opened."""
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    (older,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    _second_completed_run(j, who)
    runs = j.w.store.analysis_runs_for_scope(who.owner_id)
    (newer,) = [run for run in runs if run.run_id != older.run_id]
    with j.w.factory.begin() as database:
        database.execute(delete(RunProvenanceRow).where(RunProvenanceRow.run_id == older.run_id))

    found = provenance(j).for_runs(who.owner_id, runs)

    assert found[older.run_id] is None
    assert found[newer.run_id] is not None and found[newer.run_id].row_count == 4


def _second_completed_run(j, who) -> None:
    client, _session = commercial_client(j, who)
    submit(client)
    j.run_job(request_report(client))


def test_every_scope_level_read_returns_only_the_scopes_rows() -> None:
    """The batched reads behind the spine are filtered by scope at the store, not by the reader
    indexing them: another organization's records, links and jobs are not read at all."""
    from khepri.rca.workspace.run_reports import SqlRunReportStore

    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    _run, job_id, session_id = completed_run(j, who)
    other_client, _other_session = commercial_client(j, other)
    submit(other_client, OTHER_CSV)
    j.run_job(request_report(other_client))
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)

    records = SqlRunProvenanceStore(j.w.factory).for_scope(who.owner_id)
    links = SqlRunReportStore(j.w.factory).links_for_scope(who.owner_id)
    jobs = SqlJobSessions(j.w.factory).for_scope(who.owner_id)

    assert [record.run_id for record in records] == [run.run_id]
    assert [(link.run_id, link.job_id) for link in links] == [(run.run_id, job_id)]
    assert list(jobs) == [job_id] and jobs[job_id].session_id == session_id
    assert jobs[job_id].owner_id == who.owner_id


class _LinkTo:
    """A link store that answers one job for any run -- the corrupt link the foreign keys forbid."""

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id

    def links_for_scope(self, owner_id: str) -> tuple[RunReport, ...]:
        return tuple(
            RunReport(run_id=run_id, owner_id=owner_id, job_id=self._job_id)
            for run_id in _RUNS_ASKED
        )

    def link(self, report: RunReport, *, now):  # pragma: no cover -- never written here
        raise AssertionError


def test_a_link_to_a_job_of_another_scope_refuses_the_surface() -> None:
    """The link's foreign keys make this unrepresentable in the store; the reader still refuses a
    job whose owner is not the scope asked about, so even a corrupt link cannot cross scopes."""
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    _run, job_id, _session = completed_run(j, who)
    other_client, _other_session = commercial_client(j, other)
    submit(other_client, OTHER_CSV)
    j.run_job(request_report(other_client))
    (other_run,) = j.w.store.analysis_runs_for_scope(other.owner_id)
    (other_version,) = j.w.store.dataset_versions_for_scope(other.owner_id)
    _RUNS_ASKED.append(other_run.run_id)
    reader = ProvenanceReader(
        ProvenanceSources(
            provenance=SqlRunProvenanceStore(j.w.factory),
            reports=_LinkTo(job_id),
            handoffs=SqlJobSessions(j.w.factory),
        ),
        clock=j.clock,
    )

    with pytest.raises(UnrenderableRecord):
        reader.for_run(other.owner_id, other_run, other_version)


def test_another_scopes_run_has_no_record_here() -> None:
    """The provenance store filters by scope, so another scope's completed run reads as a run
    without a record here -- nothing of it is stated under the wrong organization."""
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    completed_run(j, who)
    run, version = _run_and_version(j, who)

    assert provenance(j).for_run(other.owner_id, run, version) is None


# --- The section outcomes are read from a package that verifies -----------------------------------


def test_the_section_outcomes_come_from_a_package_that_matches_its_own_digest() -> None:
    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    record = j.w.packages.get_session_package(session_id=session_id, now=j.clock())

    states = section_states_of(record)

    assert isinstance(states, SectionStates)
    with pytest.raises(PackageDoesNotVerify):
        section_states_of(replace(record, package_digest="sha256:" + "1" * 64))


def test_a_document_that_rebuilds_to_another_package_is_refused_under_the_right_digest() -> None:
    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    other = member(j.w, email="other@example.test", name="Other")
    other_client, other_session = commercial_client(j, other)
    submit(other_client, OTHER_CSV)
    facts = other_client.post("/api/v1/beta/facts")
    assert facts.status_code == 201, facts.text
    genuine = j.w.packages.get_session_package(session_id=session_id, now=j.clock())
    foreign = j.w.packages.get_session_package(session_id=other_session, now=j.clock())

    with pytest.raises(PackageDoesNotVerify):
        section_states_of(replace(genuine, document=foreign.document))


def test_a_run_whose_session_deletion_was_requested_keeps_its_passport_but_is_not_reachable():
    """A requested deletion ends the session's content before its horizon does -- the journey and
    the artifact repository refuse the session from the request, while cleanup is still pending
    -- so the handoff is withdrawn from the request too, and the Passport stays."""
    from khepri.rra.persistence import BetaSessionRow

    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    run, version = _run_and_version(j, who)
    with j.w.factory.begin() as database:
        database.get(BetaSessionRow, session_id).deletion_requested_at = j.clock()

    found = provenance(j).for_run(who.owner_id, run, version)

    assert found is not None and found.row_count == 4
    assert found.reachable is False


def test_completion_refuses_a_profile_that_carries_no_attestation() -> None:
    """A version exists only for an attested source, so a profile without its manifest at
    completion is a record the session no longer vouches for -- refused, nothing recorded."""
    from khepri.runtime.workspace_recording import (
        NO_ATTESTATION_FAILURE,
        WorkspaceRefused,
        _provenance_of,
    )

    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    run, _version = _run_and_version(j, who)
    profile = j.w.profiling.get_session_profile(session_id=session_id, now=j.clock())
    package = j.w.packages.get_session_package(session_id=session_id, now=j.clock())
    stripped = replace(
        profile, document={k: v for k, v in profile.document.items() if k != "coverage_manifest"}
    )

    assert _provenance_of(run, profile, package).row_count == 4
    with pytest.raises(WorkspaceRefused, match=NO_ATTESTATION_FAILURE):
        _provenance_of(run, stripped, package)


def test_each_sections_outcome_is_stated_as_its_own_code(monkeypatch) -> None:
    """The translation to `KHEPRI-DEC-033` §3: a caveated section is `caveated` (it answered, and
    was qualified), a refused one is `refused`, the rest `answered`; a bundle that does not name
    every governed section exactly once is refused rather than recorded with a gap."""
    from khepri.rra.definitions import AnalysisQualitySummary
    from khepri.runtime import run_quality

    def _summary(answered: tuple[str, ...], caveated: tuple[str, ...], refused: tuple[str, ...]):
        return AnalysisQualitySummary(
            answered=len(answered),
            caveated=len(caveated),
            refused=len(refused),
            refusals=tuple((s, "coverage_incomplete") for s in refused),
            refused_results=(),
            caveats=("chart_not_drawn",) if caveated else (),
            answered_sections=answered,
            caveated_sections=caveated,
            caveat_sections=tuple(("chart_not_drawn", s) for s in caveated),
        )

    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    record = j.w.packages.get_session_package(session_id=session_id, now=j.clock())
    monkeypatch.setattr(
        run_quality,
        "summarize",
        lambda bundle: _summary(
            ("overview", "concentration", "growth", "basket"), ("basket",), ("comparison",)
        ),
    )

    assert section_states_of(record) == SectionStates(
        overview="answered",
        comparison="refused",
        concentration="answered",
        growth="answered",
        basket="caveated",
    )

    monkeypatch.setattr(
        run_quality, "summarize", lambda bundle: _summary(("overview", "growth"), (), ())
    )
    with pytest.raises(PackageDoesNotVerify):
        section_states_of(record)


def test_a_completed_run_retains_the_family_version_each_analysis_ran_under() -> None:
    """`W1-08`, `FR-116`. The Notice compares `rra008.*` as well as the mapping, package and core
    formula, and a family version is not derivable from the core formula -- `ADMITTED_FAMILY_PAIRS`
    records which pairings are *authorized*, never which one a run used. So the run must retain
    them, and the real completion path is what proves it: shaping a record directly would leave
    the write deletable with every test still green.

    Every family, answered or refused: a family that refused because its pairing was unadmitted
    still ran under this version and refused because of it.
    """
    j = journey()
    who = member(j.w)
    run, _job_id, _session_id = completed_run(j, who)

    record = SqlRunProvenanceStore(j.w.factory).for_run(run.run_id, who.owner_id)

    assert record is not None
    assert dict(record.family_versions) == dict(FAMILY_VERSIONS)
    assert set(record.family_versions) == set(FAMILY_SECTIONS)


def test_the_scope_predicate_reads_the_relation_whose_index_leads_with_owner() -> None:
    """The spine and the detail page both run this read for every request, and the roadmap leaves
    the jobs table unbounded across organizations. `rra_report_jobs` carries no index whose leading
    column is `owner_id` -- only `(state, available_at)`, `(lease_expires_at)` and
    `(session_id, state)` -- so filtering the scope there scans every tenant's jobs. The sessions
    table carries `uq_session_owner_scope` on `(owner_id, session_id)`, and its own comment records
    that `owner_id` leads it so scope lookups stay index-backed without a second index.

    So the scope is asked of the sessions relation, and the jobs are reached from it by
    `session_id`, which `ix_report_job_session_state` leads with. The composite foreign key
    `fk_report_job_session_scope` ties a job's `owner_id` to its session's, so the two predicates
    select exactly the same rows -- this is the same read down an indexed path, not a narrower one
    (review on `#378`).
    """
    statement = SqlJobSessions(object()).scope_statement("scope-1")  # type: ignore[arg-type]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    condensed = " ".join(sql.split())

    assert "rra_beta_sessions.owner_id = 'scope-1'" in condensed
    assert "rra_report_jobs.owner_id = 'scope-1'" not in condensed


class _JobsOf:
    """A handoff read that answers one scope's jobs for any scope -- the faulty scoped read the
    ownership check exists to catch. `SqlJobSessions` cannot produce this; the point is that the
    reader does not depend on it not producing it."""

    def __init__(self, jobs: dict[str, object]) -> None:
        self._jobs = jobs

    def for_scope(self, owner_id: str) -> dict[str, object]:
        return self._jobs


def test_a_job_whose_owner_is_another_scope_refuses_the_surface() -> None:
    """`W1-06` refused a job whose `owner_id` was not the scope asked about, and the batched read
    must keep refusing it. The scope filter in `for_scope` makes this unreachable today, which is
    exactly why the check has to stay: it is what fails closed if that filter is ever wrong, and
    without it a corrupt or faulty scoped read would mark another scope's handoff `reachable`
    and leave the bridge as the only thing between it and the customer (review on `#378`).

    The link is this scope's own, so the reader reaches the ownership check rather than the
    missing-job branch the sibling test covers.
    """
    from khepri.rca.workspace.run_reports import SqlRunReportStore

    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    run, job_id, _session = completed_run(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    borrowed = SqlJobSessions(j.w.factory).for_scope(who.owner_id)[job_id]
    reader = ProvenanceReader(
        ProvenanceSources(
            provenance=SqlRunProvenanceStore(j.w.factory),
            reports=SqlRunReportStore(j.w.factory),
            handoffs=_JobsOf({job_id: replace(borrowed, owner_id=other.owner_id)}),
        ),
        clock=j.clock,
    )

    with pytest.raises(UnrenderableRecord):
        reader.for_run(who.owner_id, run, version)
