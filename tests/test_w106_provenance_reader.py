"""`W1-06` -- the provenance read, one collaborator at a time (`RCA-005` `FR-119`).

The Passport is read from what the version and run already bind by digest: the coverage manifest
the admission recorded (`manifest_digest`) and the package the run was completed from
(`package_digest`). Each read is checked against the record before a word of it is presented; a
mismatch is a corrupt or substituted record and refuses the whole surface (`UnrenderableRecord`),
never a Passport with one field quietly wrong. Absence -- the journey's content deleted -- is not
corruption and reads as "unavailable".
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_STARTED
from khepri.rca.workspace.run_reports import RunReport, SqlRunReportStore
from khepri.rra.rendering.wording import SECTION_HEADINGS
from khepri.runtime.shell_provenance import Provenance, ProvenanceReader, ProvenanceSources
from khepri.runtime.shell_workspace import UnrenderableRecord
from tests.w104_support import OTHER_CSV, member
from tests.w104b_support import commercial_client, journey, submit
from tests.w106_support import completed_run, provenance, started_run


def _run_and_version(j, who):
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    return run, version


def test_a_completed_run_reads_its_period_scale_and_quality_from_what_it_binds() -> None:
    j = journey()
    who = member(j.w)
    _run, job_id, session_id = completed_run(j, who)
    run, version = _run_and_version(j, who)

    found = provenance(j).for_run(who.owner_id, run, version)

    assert isinstance(found, Provenance)
    assert found.job_id == job_id and found.session_id == session_id
    assert (found.covered_start.isoformat(), found.covered_end.isoformat()) == (
        "2026-01-05",
        "2026-01-07",
    )
    assert found.timezone == "Africa/Cairo" and found.row_count == 4
    assert found.quality is not None
    # The summary is the report's own grouping: every section is answered or refused, none both.
    sections = set(found.quality.answered_sections) | {s for s, _ in found.quality.refusals}
    assert sections == set(SECTION_HEADINGS["en"])
    assert run.state == RUN_COMPLETED


def test_a_started_run_has_its_period_but_no_quality_yet() -> None:
    j = journey()
    who = member(j.w)
    started_run(j, who)
    run, version = _run_and_version(j, who)

    found = provenance(j).for_run(who.owner_id, run, version)

    assert run.state == RUN_STARTED
    assert found is not None and found.quality is None
    assert found.row_count == 4


def test_a_run_no_job_settles_has_no_provenance() -> None:
    """A run started through the customer door (`W1-04`) and never queued has no job, no session
    to read an admission from, and so no Passport: `None`, not a guess."""
    from tests.w105_support import admitted_version

    j = journey()
    who = member(j.w)
    _session, version_id = admitted_version(j.w, who)
    run = j.w.services.start_analysis_run(who.caller, version_id=version_id, now=j.clock())
    version = j.w.store.get_dataset_version(version_id, who.owner_id)

    assert provenance(j).for_run(who.owner_id, run, version) is None


def test_expired_journey_content_reads_as_unavailable_not_as_corruption() -> None:
    """Seven days after the analysis session opened its content is no longer served (`R7-07`);
    the run keeps its record, and the reader answers absence, not a refusal."""
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    run, version = _run_and_version(j, who)
    j.clock.advance(timedelta(days=8))

    assert provenance(j).for_run(who.owner_id, run, version) is None


class _Corrupt:
    """A version or run whose recorded digest disagrees with what the session holds."""

    def __init__(self, record, **fields) -> None:
        self._record = record
        self._fields = fields

    def __getattr__(self, name):
        if name in self._fields:
            return self._fields[name]
        return getattr(self._record, name)


def test_a_manifest_that_does_not_match_the_versions_digest_refuses_the_surface() -> None:
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    run, version = _run_and_version(j, who)

    with pytest.raises(UnrenderableRecord):
        provenance(j).for_run(
            who.owner_id, run, _Corrupt(version, manifest_digest="sha256:" + "0" * 64)
        )


def test_a_package_that_does_not_match_the_runs_digest_refuses_the_surface() -> None:
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    run, version = _run_and_version(j, who)

    with pytest.raises(UnrenderableRecord):
        provenance(j).for_run(
            who.owner_id, _Corrupt(run, package_digest="sha256:" + "0" * 64), version
        )


def test_another_scopes_run_has_no_provenance_here() -> None:
    """The link store filters by scope, so another scope's run has no job *here*: an absence,
    which the surface turns into `unavailable` because the run is not in its history either."""
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    completed_run(j, who)
    run, version = _run_and_version(j, who)

    assert provenance(j).for_run(other.owner_id, run, version) is None


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
    run, version = _run_and_version(j, who)
    reader = ProvenanceReader(
        ProvenanceSources(
            reports=_LinkTo(job_id),
            jobs=j.reader,
            profiling=j.w.profiling,
            packages=j.w.packages,
        ),
        clock=j.clock,
    )

    with pytest.raises(UnrenderableRecord):
        reader.for_run(other.owner_id, run, version)


class _PackagesAnswering:
    """A package reader that answers one record for any session -- the doubles the two digest
    checks need, because each guards a corruption the other cannot see."""

    def __init__(self, record) -> None:
        self._record = record

    def get_session_package(self, *, session_id: str, now):
        return self._record


def _reader_with_packages(j, packages) -> ProvenanceReader:
    return ProvenanceReader(
        ProvenanceSources(
            reports=SqlRunReportStore(j.w.factory),
            jobs=j.reader,
            profiling=j.w.profiling,
            packages=packages,
        ),
        clock=j.clock,
    )


def test_a_stored_digest_that_does_not_name_the_runs_package_refuses_before_any_rebuild() -> None:
    """The record's own digest is the first check: a stored package whose digest is not the one
    the run binds is refused without rebuilding it, as the catalog refuses it."""
    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    run, version = _run_and_version(j, who)
    genuine = j.w.packages.get_session_package(session_id=session_id, now=j.clock())
    tampered = replace(genuine, package_digest="sha256:" + "1" * 64)

    with pytest.raises(UnrenderableRecord):
        _reader_with_packages(j, _PackagesAnswering(tampered)).for_run(who.owner_id, run, version)


def test_a_document_that_rebuilds_to_another_package_refuses_even_when_its_digest_agrees() -> None:
    """The second check is the rebuild: a record whose stored digest matches the run but whose
    document is another package's is a substitution the first check cannot see."""
    j = journey()
    who = member(j.w)
    _run, _job, session_id = completed_run(j, who)
    run, version = _run_and_version(j, who)
    other = member(j.w, email="other@example.test", name="Other")
    other_client, other_session = commercial_client(j, other)
    submit(other_client, OTHER_CSV)
    facts = other_client.post("/api/v1/beta/facts")
    assert facts.status_code == 201, facts.text
    genuine = j.w.packages.get_session_package(session_id=session_id, now=j.clock())
    foreign = j.w.packages.get_session_package(session_id=other_session, now=j.clock())
    substituted = replace(genuine, document=foreign.document)

    with pytest.raises(UnrenderableRecord):
        _reader_with_packages(j, _PackagesAnswering(substituted)).for_run(
            who.owner_id, run, version
        )
