"""The provenance read behind Analysis detail (`W1-06`; `RCA-005` `FR-119`).

## What the Passport is read from

A run and its version already bind, by digest, everything the Passport states: the version carries
the coverage manifest's digest (`FR-109`, `KHEPRI-DEC-033` §3) and the run its package's
(`FR-111`). This module reads the manifest and the package back from the session the run's job
belongs to -- through `ProfilingService` and `FactPackageService`, the same instances the routes
and the recorder use -- and **checks each against the digest the record holds before presenting a
word of it**. A record is therefore provenance without a second copy of it: nothing is stored
twice, and nothing is presented that the record does not vouch for.

## Why this module is in `khepri.runtime`

It reads `khepri.rca.workspace` (the run-to-report link) and `khepri.rra` (the job, the admission,
the package). `R7-01` §3 forbids either package importing the other, so the composition layer is
the one place that may hold both, beside `workspace_recording.py`, which records the argument.

## The rebuild is admissible

`ReportBundle.of(package)` is rebuilt from the stored package exactly as the catalog's
package-scoped routes rebuild it (`report_api._session_bundle`), which `KHEPRI-DEC-032` reads as
admissible because it publishes no figure. This module publishes none either: it asks the bundle
which sections answered, which carried a caveat and which refused (`definitions.summarize`), and the
surface words that through the report's own component chrome.

## Three answers

- **`Provenance`** -- the run's job settles it, its session's admission and package are present
  and agree with the record.
- **`None`** -- nothing to present, honestly: no job settles this run (a run the customer door
  started and never queued), or the session's content is gone (the journey's own deletion, or
  expiry). Detail says the provenance is unavailable and offers no artifact.
- **`UnrenderableRecord`** -- the record and the session disagree: a manifest or package whose
  digest is not the one the record binds, or a link to a job another scope owns. That is a corrupt
  or substituted record, and the whole surface refuses (`FR-050`) rather than presenting a Passport
  with one field quietly wrong.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from khepri.rca.workspace.contracts import RUN_COMPLETED
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rra.bundle import ReportBundle
from khepri.rra.datasets import DatasetProfileRecord, ProfilingService, document_digest
from khepri.rra.datasets import stored_manifest as _stored_manifest
from khepri.rra.definitions import AnalysisQualitySummary, summarize
from khepri.rra.jobs import ReportJob
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import FactPackageService
from khepri.runtime.shell_workspace import UNRENDERABLE_FAILURE, UnrenderableRecord


class JobReaderPort(Protocol):
    def find(self, job_id: str) -> ReportJob | None: ...


@dataclass(frozen=True, slots=True)
class Provenance:
    """What Analysis detail presents for one run, read from what the run binds.

    `session_id` and `job_id` are the handoff's address (`ReportLocator`'s two identifiers) and
    reach no template: the handoff route builds the report API's address from them in Python.
    `quality` is `None` for a run that has no package yet -- a started run -- and never for a
    completed one, whose package is checked against the run's digest before it is summarized.
    """

    session_id: str
    job_id: str
    covered_start: date
    covered_end: date
    timezone: str
    aggregate_scope: str | None
    attested_by: str
    row_count: int
    quality: AnalysisQualitySummary | None


@dataclass(frozen=True, slots=True)
class ProvenanceSources:
    """Where a run's provenance is read from: the link to its job, the job, the admission, the
    package -- the same `RRA` service instances the routes and the recorder use."""

    reports: SqlRunReportStore
    jobs: JobReaderPort
    profiling: ProfilingService
    packages: FactPackageService


class ProvenanceReader:
    """Reads one run's Passport from the admission and package its record binds by digest."""

    def __init__(self, sources: ProvenanceSources, *, clock: Callable[[], datetime]) -> None:
        self._reports = sources.reports
        self._jobs = sources.jobs
        self._profiling = sources.profiling
        self._packages = sources.packages
        self._clock = clock

    @property
    def profiling(self) -> ProfilingService:
        return self._profiling

    @property
    def packages(self) -> FactPackageService:
        return self._packages

    def for_run(self, owner_id: str, run: object, version: object) -> Provenance | None:
        """The Passport for `run` over `version`, in `owner_id`'s scope -- or `None`, or a refusal.

        `run` and `version` are the records the history read returned; they are trusted for their
        digests and nothing read here is trusted until it matches one of them.
        """
        job = self._settling_job(owner_id, run)
        if job is None:
            return None
        now = self._clock()
        profile = self._admission(job.session_id, now)
        if profile is None:
            return None
        manifest = _stored_manifest(profile)
        if manifest is None or document_digest(manifest.as_document()) != version.manifest_digest:
            raise UnrenderableRecord(UNRENDERABLE_FAILURE)
        return Provenance(
            session_id=job.session_id,
            job_id=job.job_id,
            covered_start=manifest.covered_start,
            covered_end=manifest.covered_end,
            timezone=manifest.timezone,
            aggregate_scope=manifest.aggregate_scope,
            attested_by=manifest.attested_by,
            row_count=profile.row_count,
            quality=self._quality(job.session_id, run, now),
        )

    def _settling_job(self, owner_id: str, run: object) -> ReportJob | None:
        """The job the run is settled by, in this scope. A link to another scope's job is a corrupt
        record, not an absence."""
        job_id = self._reports.job_id_for_run(run.run_id, owner_id)
        if job_id is None:
            return None
        job = self._jobs.find(job_id)
        if job is None or job.owner_id != owner_id:
            raise UnrenderableRecord(UNRENDERABLE_FAILURE)
        return job

    def _admission(self, session_id: str, now: datetime) -> DatasetProfileRecord | None:
        """The admission the session holds, or `None` once its content is gone."""
        try:
            return self._profiling.get_session_profile(session_id=session_id, now=now)
        except PermissionError:
            return None

    def _quality(
        self, session_id: str, run: object, now: datetime
    ) -> AnalysisQualitySummary | None:
        """The report's own grouping of what it answered and refused, for a completed run.

        The package is rebuilt and checked against the run's digest first: a completed run whose
        session holds a different package -- or none -- is a record that no longer vouches for what
        it binds, and the surface refuses rather than summarizing another package.
        """
        if run.state != RUN_COMPLETED:
            return None
        try:
            record = self._packages.get_session_package(session_id=session_id, now=now)
        except PermissionError:
            record = None
        if record is None or record.package_digest != run.package_digest:
            raise UnrenderableRecord(UNRENDERABLE_FAILURE)
        package = rebuild_fact_package(record.document)
        if package.digest != run.package_digest:
            raise UnrenderableRecord(UNRENDERABLE_FAILURE)
        return summarize(ReportBundle.of(package))


__all__ = ["JobReaderPort", "Provenance", "ProvenanceReader", "ProvenanceSources"]
