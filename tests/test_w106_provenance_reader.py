"""`W1-06` -- the provenance read, one collaborator at a time (`RCA-005` `FR-119`).

The Passport is read from what the version and run already bind by digest: the coverage manifest
the admission recorded (`manifest_digest`) and the package the run was completed from
(`package_digest`). Each read is checked against the record before a word of it is presented; a
mismatch is a corrupt or substituted record and refuses the whole surface (`UnrenderableRecord`),
never a Passport with one field quietly wrong. Absence -- the journey's content deleted -- is not
corruption and reads as "unavailable".
"""

from __future__ import annotations

import pytest
from khepri.runtime.shell_provenance import Provenance, ProvenanceReader

from khepri.rca.workspace.contracts import RUN_COMPLETED, RUN_STARTED
from khepri.rra.rendering.wording import SECTION_HEADINGS
from khepri.runtime.shell_workspace import UnrenderableRecord
from tests.w104_support import member
from tests.w104b_support import journey
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


def test_deleted_journey_content_reads_as_unavailable_not_as_corruption() -> None:
    j = journey()
    who = member(j.w)
    from tests.w104b_support import commercial_client, request_report, submit

    client, _session = commercial_client(j, who)
    submit(client)
    j.run_job(request_report(client))
    run, version = _run_and_version(j, who)
    assert client.delete("/api/v1/beta/content").status_code in (200, 204)

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


def test_a_link_to_a_job_of_another_scope_refuses_the_surface() -> None:
    """The link's foreign keys make this unrepresentable in the store; the reader still refuses
    a job whose owner is not the scope asked about, so a corrupt link cannot cross scopes."""
    j = journey()
    who = member(j.w)
    other = member(j.w, email="other@example.test", name="Other")
    completed_run(j, who)
    run, version = _run_and_version(j, who)

    with pytest.raises(UnrenderableRecord):
        provenance(j).for_run(other.owner_id, run, version)
