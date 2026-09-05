"""The provenance read behind Analysis detail (`W1-06`; `RCA-005` `FR-119`; `KHEPRI-DEC-033` §2).

## What the Passport is read from

The run's **retained provenance record** (`rca/workspace/provenance.py`), written at completion in
the completion's own transaction from the admission and the package the run binds: the attested
period and its day boundary, the coverage scope, who attested, the admitted row count, and one
governed state code per report section. It lives with the run, as `KHEPRI-DEC-033` gives the
provenance record its own row -- so a Passport does not vanish when the analysis session's content
ends on its seven-day horizon. An earlier draft read the admission and the package back through the
session-gated services at render time; review on `#376` found that every otherwise-retained analysis
would have lost its Passport on that timer.

## What is still the session's

The artifacts. `KHEPRI-DEC-033` retains them with the run, but today they are served by the report
API under the analysis session's cookie, and the handoff resumes that session. So this read also
answers whether the run's session can still be resumed (`reachable`), and detail offers an artifact
only while it can. Reconciling artifact retention with the session's horizon is `W1-07`'s lifecycle
work; this surface states the state it finds and offers nothing it cannot honour.

## Why this module is in `khepri.runtime`

It reads `khepri.rca.workspace` (the provenance record, the run-to-report link) and `khepri.rra`
(the job, the session). `R7-01` §3 forbids either package importing the other, so the composition
layer is the one place that may hold both.

## Three answers

- **`Provenance`** -- the run is completed and its record is retained.
- **`None`** -- there is no provenance to state: the run is not completed yet, or it completed
  before provenance was retained (`20260905_0024` backfills nothing: the admission and the package
  a record is written from may already have ended on their own horizons). Detail states the
  Passport as unavailable and offers no artifact; the run itself stays on the spine. Review on
  `#376` round 2: an earlier draft read the absence as corruption and refused the whole Analyses
  surface, which every organization with a run completed before the upgrade would have met.
- **`UnrenderableRecord`** -- a link to a job another scope owns: a corrupt record, which refuses
  the whole surface (`FR-050`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Protocol

from khepri.rca.workspace.provenance import SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rca.workspace.tombstones import SectionStates
from khepri.rra.jobs import ReportJob
from khepri.rra.sessions import BetaSession
from khepri.runtime.shell_workspace import UNRENDERABLE_FAILURE, UnrenderableRecord


class JobReaderPort(Protocol):
    def find(self, job_id: str) -> ReportJob | None: ...


class SessionReaderPort(Protocol):
    def get_session(self, session_id: str) -> BetaSession | None: ...


@dataclass(frozen=True, slots=True)
class Provenance:
    """What Analysis detail presents for one completed run.

    `session_id` and `job_id` are the handoff's address and reach no template; both are `None` for
    a run no job settled (one the customer door started and never queued). `reachable` says whether
    that session can still be resumed, which is what an artifact handoff needs.
    """

    session_id: str | None
    job_id: str | None
    covered_start: date
    covered_end: date
    timezone: str
    aggregate_scope: str | None
    attested_by: str
    row_count: int
    sections: SectionStates
    reachable: bool
    #: Each `RRA-008` family's version as this run ran under it, by section. Empty for a run
    #: completed before `20260905_0025`; the Notice reads that absence as "not recorded".
    family_versions: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProvenanceSources:
    """Where a run's provenance is read from: its retained record, its link to its job, the job,
    and the job's session -- the last two for the handoff only."""

    provenance: SqlRunProvenanceStore
    reports: SqlRunReportStore
    jobs: JobReaderPort
    sessions: SessionReaderPort


class ProvenanceReader:
    """Reads one run's Passport from the record it retained at completion."""

    def __init__(self, sources: ProvenanceSources, *, clock: Callable[[], datetime]) -> None:
        self._sources = sources
        self._clock = clock

    @property
    def sources(self) -> ProvenanceSources:
        return self._sources

    def for_run(self, owner_id: str, run: object, version: object) -> Provenance | None:
        """The Passport for `run`, in `owner_id`'s scope -- or `None` where no record is retained:
        before completion, or for a run completed before provenance was retained."""
        record = self._sources.provenance.for_run(run.run_id, owner_id)
        if record is None:
            return None
        job = self._settling_job(owner_id, run)
        return Provenance(
            session_id=None if job is None else job.session_id,
            job_id=None if job is None else job.job_id,
            covered_start=record.covered_start,
            covered_end=record.covered_end,
            timezone=record.timezone,
            aggregate_scope=record.aggregate_scope,
            attested_by=record.attested_by,
            row_count=record.row_count,
            sections=record.sections,
            family_versions=record.family_versions,
            reachable=job is not None and self._resumable(job.session_id),
        )

    def _settling_job(self, owner_id: str, run: object) -> ReportJob | None:
        """The job the run is settled by, in this scope. A link to another scope's job is a corrupt
        record, not an absence."""
        job_id = self._sources.reports.job_id_for_run(run.run_id, owner_id)
        if job_id is None:
            return None
        job = self._sources.jobs.find(job_id)
        if job is None or job.owner_id != owner_id:
            raise UnrenderableRecord(UNRENDERABLE_FAILURE)
        return job

    def _resumable(self, session_id: str) -> bool:
        """Whether the analysis session's content is still live: present, no deletion requested,
        not past `content_expires_at` -- the facts the journey and the artifact repository read.
        A requested deletion is already refused there while its cleanup is pending or retrying, so
        it is unreachable here from the request, not from the completion."""
        session = self._sources.sessions.get_session(session_id)
        if session is None or session.deletion_requested_at is not None:
            return False
        return self._clock() < session.content_expires_at


__all__ = [
    "JobReaderPort",
    "Provenance",
    "ProvenanceReader",
    "ProvenanceSources",
    "SessionReaderPort",
]
