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

## How it reads

In scope-level batches: three reads for however many runs are asked about -- the scope's provenance
records, its run-to-job links, and its jobs joined to their sessions' liveness
(`runtime/job_sessions.py`). The spine asks about every completed run at once; detail asks about
one; both go through `for_runs`, so there is one rule and one cost shape. Review on `#376` (round 3)
found the first draft reading each run separately: four round trips per completed run on a spine
the roadmap leaves unbounded.

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
- **`UnrenderableRecord`** -- a link to a job this scope does not hold: a corrupt record, which
  refuses the whole surface (`FR-050`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime

from khepri.rca.workspace.provenance import RunProvenance, SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rca.workspace.tombstones import SectionStates
from khepri.runtime.job_sessions import JobSession, JobSessionsPort
from khepri.runtime.shell_workspace import UNRENDERABLE_FAILURE, UnrenderableRecord


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
    """Where a scope's provenance is read from: its retained records, its links from run to job,
    and its jobs with their sessions' liveness -- the last two for the handoff only."""

    provenance: SqlRunProvenanceStore
    reports: SqlRunReportStore
    handoffs: JobSessionsPort


@dataclass(frozen=True, slots=True)
class _ScopeReads:
    """One scope's three reads, indexed for the runs asked about."""

    records: dict[str, RunProvenance]
    links: dict[str, str]
    jobs: dict[str, JobSession]


class ProvenanceReader:
    """Reads runs' Passports from the records they retained at completion."""

    def __init__(self, sources: ProvenanceSources, *, clock: Callable[[], datetime]) -> None:
        self._sources = sources
        self._clock = clock

    @property
    def sources(self) -> ProvenanceSources:
        return self._sources

    def for_run(self, owner_id: str, run: object, version: object) -> Provenance | None:
        """The Passport for `run`, in `owner_id`'s scope -- or `None` where no record is retained:
        before completion, or for a run completed before provenance was retained."""
        return self.for_runs(owner_id, (run,))[run.run_id]

    def for_runs(self, owner_id: str, runs: Iterable[object]) -> dict[str, Provenance | None]:
        """The Passport of each of `runs`, by run, from three scope-level reads -- and no read at
        all when there is nothing to ask about."""
        asked = tuple(runs)
        if not asked:
            return {}
        reads = self._read_scope(owner_id)
        return {run.run_id: self._of(run, reads) for run in asked}

    def _read_scope(self, owner_id: str) -> _ScopeReads:
        sources = self._sources
        return _ScopeReads(
            records={p.run_id: p for p in sources.provenance.for_scope(owner_id)},
            links={link.run_id: link.job_id for link in sources.reports.links_for_scope(owner_id)},
            jobs=sources.handoffs.for_scope(owner_id),
        )

    def _of(self, run: object, reads: _ScopeReads) -> Provenance | None:
        record = reads.records.get(run.run_id)
        if record is None:
            return None
        job = _settling_job(run.run_id, reads)
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
            reachable=job is not None and self._resumable(job),
        )

    def _resumable(self, job: JobSession) -> bool:
        """Whether the analysis session's content is still live: no deletion requested, not past
        `content_expires_at` -- the facts the journey and the artifact repository read. A requested
        deletion is already refused there while its cleanup is pending or retrying, so it is
        unreachable here from the request, not from the completion."""
        if job.deletion_requested_at is not None:
            return False
        return self._clock() < job.content_expires_at


def _settling_job(run_id: str, reads: _ScopeReads) -> JobSession | None:
    """The job the run is settled by, in this scope. A link to a job the scope does not hold is a
    corrupt record, not an absence."""
    job_id = reads.links.get(run_id)
    if job_id is None:
        return None
    job = reads.jobs.get(job_id)
    if job is None:
        raise UnrenderableRecord(UNRENDERABLE_FAILURE)
    return job


__all__ = ["Provenance", "ProvenanceReader", "ProvenanceSources"]
