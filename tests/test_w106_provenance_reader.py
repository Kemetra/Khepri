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
there and no provenance is written. A completed run without its record is a corrupt record and
refuses the whole surface (`UnrenderableRecord`).
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
from khepri.rca.workspace.tombstones import SectionStates
from khepri.runtime.run_quality import PackageDoesNotVerify, section_states_of
from khepri.runtime.shell_provenance import Provenance, ProvenanceReader, ProvenanceSources
from khepri.runtime.shell_workspace import UnrenderableRecord
from tests.w104_support import OTHER_CSV, member
from tests.w104b_support import commercial_client, journey, request_report, submit
from tests.w106_support import completed_run, provenance, started_run


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


def test_a_completed_run_without_its_record_refuses_the_surface() -> None:
    """A completed run always retains its provenance (the same transaction writes both), so a
    completed run without one is a corrupt record, not an absence to render around."""
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    run, version = _run_and_version(j, who)
    with j.w.factory.begin() as database:
        database.execute(delete(RunProvenanceRow).where(RunProvenanceRow.run_id == run.run_id))

    with pytest.raises(UnrenderableRecord):
        provenance(j).for_run(who.owner_id, run, version)


class _LinkTo:
    """A link store that answers one job for any run -- the corrupt link the foreign keys forbid."""

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id

    def job_id_for_run(self, run_id: str, owner_id: str) -> str | None:
        return self._job_id

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
    reader = ProvenanceReader(
        ProvenanceSources(
            provenance=SqlRunProvenanceStore(j.w.factory),
            reports=_LinkTo(job_id),
            jobs=j.reader,
            sessions=j.w.sessions,
        ),
        clock=j.clock,
    )

    with pytest.raises(UnrenderableRecord):
        reader.for_run(other.owner_id, other_run, other_version)


def test_another_scopes_run_has_no_record_here() -> None:
    """The provenance store filters by scope, so another scope's completed run reads as a
    completed run without a record -- refused, never rendered under the wrong organization."""
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    completed_run(j, who)
    run, version = _run_and_version(j, who)

    with pytest.raises(UnrenderableRecord):
        provenance(j).for_run(other.owner_id, run, version)


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


def test_a_run_whose_session_content_was_deleted_keeps_its_passport_but_is_not_reachable() -> None:
    """Deletion ends the session's content before its horizon does; the Passport stays and the
    handoff is withdrawn, exactly as after expiry."""
    from khepri.rra.persistence import BetaSessionRow

    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    run, version = _run_and_version(j, who)
    with j.w.factory.begin() as database:
        row = database.get(BetaSessionRow, session_id)
        row.deletion_requested_at = j.clock()
        row.content_deleted_at = j.clock()

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
