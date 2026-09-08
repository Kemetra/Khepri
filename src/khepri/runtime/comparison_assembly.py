"""RRA half of C1-06 comparison orchestration.

`RCA-005` `FR-130`--`FR-133` and §Comparison retention live in
`khepri.rca.workspace.comparisons`; this module loads retained packages and
coverage manifests, calls `assemble_crossversion`, and renders the three
surfaces in-request. `R7-01` §3 forbids `khepri.rca` from importing
`khepri.rra`, so the composition sits here.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from khepri.rca.workspace.comparisons import (
    KIND_ADMITTED,
    KIND_REFUSED,
    ComparisonOutcome,
    ComparisonRefusal,
    ComparisonSurfaces,
    OrderedVersionIds,
)
from khepri.rca.workspace.contracts import RUN_COMPLETED, AnalysisRun
from khepri.rca.workspace.provenance import RunProvenance, SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rca.workspace.store import SqlWorkspaceRecordStore
from khepri.rra.aggregates import granularity_for
from khepri.rra.analysis.comparison_narrative import refusal_wording
from khepri.rra.analysis.dataset_period import (
    CAUSE_INCOMPLETE,
    CAUSE_RETAIL_DAY,
    CAUSE_UNORDERED_PAIR,
    DatasetPeriod,
)
from khepri.rra.bundle import BundleAssembler, SurfaceContent
from khepri.rra.coverage import CompletenessQuery, CoverageManifest, admits_completeness
from khepri.rra.crossversion_assembly import assemble_crossversion
from khepri.rra.crossversion_bundle import CrossVersionRefusal, CrossVersionRequest
from khepri.rra.datasets import DatasetProfileRecord, ProfilingService, stored_manifest
from khepri.rra.facts import FactPackage
from khepri.rra.package_source import rebuild_fact_package
from khepri.rra.packages import (
    FactPackageRecord,
    FactPackageService,
    PackageCorrupted,
    PackageRefused,
)
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PdfReportRenderer
from khepri.runtime.job_sessions import JobSession, SqlJobSessions
from khepri.runtime.run_quality import PACKAGE_MISMATCH_FAILURE, PackageDoesNotVerify

__all__ = ["ComparisonAssemblyPorts", "CrossVersionAssembly"]

#: Coverage manifests attest calendar ``date`` values, not datetimes. The
#: attested retail day therefore starts at hour 0 of the manifest timezone.
#: Derived from the retained type, not supplied as a comparison default.
_CALENDAR_DAY_HOUR = 0

_PACKAGE_FAULTS = (PermissionError, PackageCorrupted, PackageRefused, PackageDoesNotVerify)


@dataclass(frozen=True, slots=True)
class ComparisonAssemblyPorts:
    """Where a completed run's package and coverage manifest are read."""

    packages: FactPackageService
    profiling: ProfilingService
    jobs: SqlJobSessions
    reports: SqlRunReportStore
    provenance: SqlRunProvenanceStore
    workspace: SqlWorkspaceRecordStore


@dataclass(frozen=True, slots=True)
class _Operand:
    package: FactPackage
    period: DatasetPeriod
    aggregate_scope: str | None
    run_id: str
    #: The manifest's timezone: the retail day boundary every attested day is stated in.
    timezone: str


@dataclass(frozen=True, slots=True)
class _Load:
    operand: _Operand | None
    incomplete: bool


@dataclass(frozen=True, slots=True)
class _RunPackage:
    run: AnalysisRun
    session: JobSession
    package: FactPackage


@dataclass(frozen=True, slots=True)
class _OperandAsk:
    ports: ComparisonAssemblyPorts
    owner_id: str
    version_id: str
    now: datetime
    bound: _RunPackage


@dataclass(slots=True)
class _Captured:
    """A `SurfaceRenderer` over one full render, keeping the document it produced.

    `BundleAssembler.assemble` is what turns a renderer fault into an incomplete
    bundle, and so into the uniform unavailable outcome with its audit event. It
    asks each renderer only for its claim, so reaching the documents needed a
    second render pass -- one nothing guarded, so a fault there escaped the
    request before the audit write, and one whose bytes the recorded claims did
    not describe. Rendering once inside the assembler and keeping the document
    leaves one pass, governed, whose claim is about the bytes delivered.
    """

    produce: Callable[[Any], Any]
    document: Any = None

    def render(self, bundle: Any) -> SurfaceContent:
        self.document = self.produce(bundle)
        return self.document.content


class CrossVersionAssembly:
    """Load two retained packages and assemble the in-request bundle."""

    def __init__(
        self,
        ports: ComparisonAssemblyPorts,
        html: HtmlReportRenderer,
        pdf: PdfReportRenderer,
        excel: ExcelSurfaceRenderer,
    ) -> None:
        self._ports = ports
        self._html = html
        self._pdf = pdf
        self._excel = excel

    def unordered_refusal(self) -> ComparisonRefusal:
        return ComparisonRefusal(CAUSE_UNORDERED_PAIR, refusal_wording(CAUSE_UNORDERED_PAIR))

    def assemble_pair(
        self, owner_id: str, pair: OrderedVersionIds, *, now: datetime
    ) -> ComparisonOutcome | None:
        subject = _load_operand(self._ports, owner_id, pair.subject_version_id, now)
        baseline = _load_operand(self._ports, owner_id, pair.baseline_version_id, now)
        if _load_missing(subject, baseline):
            return None
        if _load_incomplete(subject, baseline):
            return _refused_outcome(CAUSE_INCOMPLETE)
        return self._assemble(owner_id, subject.operand, baseline.operand)

    def _assemble(
        self, owner_id: str, subject: _Operand, baseline: _Operand
    ) -> ComparisonOutcome | None:
        built = assemble_crossversion(_cross_request(owner_id, subject, baseline))
        if isinstance(built, CrossVersionRefusal):
            return ComparisonOutcome(
                kind=KIND_REFUSED,
                refusal=ComparisonRefusal(built.cause, dict(built.wording)),
            )
        if subject.timezone != baseline.timezone:
            # `RRA-008` §Period rule refuses a pair whose periods differ in retail-day boundary,
            # and the coverage manifest's timezone is that boundary. The frozen period type
            # carries an hour, not a zone, so the family's predicate cannot see this; the
            # comparison is made here, once every frozen predicate has admitted the pair, under
            # the cause the family already froze. Its proper home is the predicate itself, which
            # is an owner amendment recorded in the roadmap row (owner's reading, 2026-09-08).
            return _refused_outcome(CAUSE_RETAIL_DAY)
        surfaces = self._render(built, subject.run_id, baseline.run_id)
        if surfaces is None:
            return None
        return ComparisonOutcome(kind=KIND_ADMITTED, surfaces=surfaces, bundle=built)

    def _render(
        self, bundle: Any, subject_run_id: str, baseline_run_id: str
    ) -> ComparisonSurfaces | None:
        # The workbook renderer writes a file to reach its bytes, named by `bundle_id`
        # alone -- so two requests for one pair would share a path, and one request's
        # cleanup or replace would fail the other's read. Each request therefore renders
        # into a directory of its own. `RRA-006` §Not stored: a two-population bundle is
        # rendered on request and retained nowhere, so that directory goes as soon as the
        # bytes are in hand -- and just the same when the bundle comes back incomplete or
        # a later renderer faults, since the assembler has already written the file by
        # then. A process that ran for a year has kept no comparison on disk.
        scratch = _scratch_under(self._excel.directory)
        if scratch is None:
            return None
        excel = replace(self._excel, directory=scratch)
        try:
            return self._surfaces(bundle, excel, subject_run_id, baseline_run_id)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def _surfaces(
        self,
        bundle: Any,
        excel: ExcelSurfaceRenderer,
        subject_run_id: str,
        baseline_run_id: str,
    ) -> ComparisonSurfaces | None:
        html = _Captured(self._html.render_html)
        pdf = _Captured(self._pdf.render_pdf)
        workbook = _Captured(excel.render_materialized)
        result = BundleAssembler(renderers=(html, pdf, workbook)).assemble(bundle)
        if result.incomplete or result.surfaces is None:
            return None
        return ComparisonSurfaces(
            claims={content.surface: content for content in result.surfaces},
            html=html.document.documents,
            pdf=pdf.document.documents,
            excel=workbook.document.artifacts[0].content,
            subject_run_id=subject_run_id,
            baseline_run_id=baseline_run_id,
        )


def _scratch_under(directory: Path) -> Path | None:
    """A request's own render directory, or None when none can be made.

    The configured directory can be gone or unwritable by the time a request
    arrives. That is a failure to render, and it owes the caller the same
    `None` a renderer fault does, so the action still returns the uniform
    unavailable outcome and writes its one audit event.
    """
    try:
        return Path(tempfile.mkdtemp(dir=directory))
    except OSError:
        return None


def _refused_outcome(cause: str) -> ComparisonOutcome:
    return ComparisonOutcome(
        kind=KIND_REFUSED, refusal=ComparisonRefusal(cause, refusal_wording(cause))
    )


def _load_missing(subject: _Load, baseline: _Load) -> bool:
    if subject.operand is None and not subject.incomplete:
        return True
    return baseline.operand is None and not baseline.incomplete


def _load_incomplete(subject: _Load, baseline: _Load) -> bool:
    if subject.incomplete:
        return True
    return baseline.incomplete


def _cross_request(owner_id: str, subject: _Operand, baseline: _Operand) -> CrossVersionRequest:
    return CrossVersionRequest(
        subject=subject.package,
        baseline=baseline.package,
        subject_organization_scope=owner_id,
        baseline_organization_scope=owner_id,
        subject_period=subject.period,
        baseline_period=baseline.period,
        subject_aggregate_scope=subject.aggregate_scope,
        baseline_aggregate_scope=baseline.aggregate_scope,
    )


def _load_operand(
    ports: ComparisonAssemblyPorts, owner_id: str, version_id: str, now: datetime
) -> _Load:
    run = _latest_completed(ports.workspace, owner_id, version_id)
    if run is None or run.package_digest is None:
        return _Load(None, False)
    session = _session_of(ports, run.run_id, owner_id)
    if session is None:
        return _Load(None, False)
    record = _package_record(ports.packages, session.session_id, now)
    if record is None:
        return _Load(None, False)
    try:
        package = _verified_package(record)
    except PackageDoesNotVerify:
        return _Load(None, False)
    if package is None:
        return _Load(None, False)
    if run.package_digest != package.digest:
        return _Load(None, False)
    bound = _RunPackage(run=run, session=session, package=package)
    ask = _OperandAsk(ports, owner_id, version_id, now, bound)
    return _operand_from(ask)


def _operand_from(ask: _OperandAsk) -> _Load:
    bound = ask.bound
    provenance = ask.ports.provenance.for_run(bound.run.run_id, ask.owner_id)
    if provenance is None:
        return _Load(None, True)
    profile = _profile_record(ask.ports.profiling, bound.session.session_id, ask.now)
    if profile is None:
        return _Load(None, True)
    manifest = _manifest_of(profile)
    if manifest is None:
        return _Load(None, True)
    period = _dataset_period(ask.version_id, provenance, manifest)
    operand = _Operand(
        package=bound.package,
        period=period,
        aggregate_scope=manifest.aggregate_scope,
        run_id=bound.run.run_id,
        timezone=manifest.timezone,
    )
    return _Load(operand, False)


def _manifest_of(profile: DatasetProfileRecord) -> CoverageManifest | None:
    """The stored manifest, or None when the profile carries none or it no longer reads.

    `stored_manifest` is a read that is not re-admitted: bare subscripts and date parsing
    raise on a document whose manifest section has drifted, and `ManifestRefused` is a
    `ValueError`. A corrupted package already loads as `None` here; a corrupted manifest
    gets the same treatment, so the pair refuses as incomplete with its one audit event.
    """
    try:
        return stored_manifest(profile)
    except (KeyError, ValueError):
        return None


def _latest_completed(
    workspace: SqlWorkspaceRecordStore, owner_id: str, version_id: str
) -> AnalysisRun | None:
    completed = tuple(
        run
        for run in workspace.analysis_runs_for_scope(owner_id)
        if _completed_for(run, version_id)
    )
    if not completed:
        return None
    return max(completed, key=_completion_key)


def _completed_for(run: AnalysisRun, version_id: str) -> bool:
    if run.version_id != version_id:
        return False
    return run.state == RUN_COMPLETED


def _completion_key(run: AnalysisRun) -> tuple[datetime, str]:
    completed = run.completed_at
    if completed is None:
        return (datetime.min, run.run_id)
    return (completed, run.run_id)


def _session_of(ports: ComparisonAssemblyPorts, run_id: str, owner_id: str) -> JobSession | None:
    job_id = ports.reports.job_id_for_run(run_id, owner_id)
    if job_id is None:
        return None
    return ports.jobs.job(job_id, owner_id)


def _package_record(
    packages: FactPackageService, session_id: str, now: datetime
) -> FactPackageRecord | None:
    try:
        return packages.get_session_package(session_id=session_id, now=now)
    except _PACKAGE_FAULTS:
        return None


def _profile_record(
    profiling: ProfilingService, session_id: str, now: datetime
) -> DatasetProfileRecord | None:
    try:
        return profiling.get_session_profile(session_id=session_id, now=now)
    except PermissionError:
        return None


def _verified_package(record: FactPackageRecord) -> FactPackage | None:
    try:
        package = rebuild_fact_package(record.document)
    except (KeyError, TypeError, ValueError):
        return None
    if package.digest != record.package_digest:
        raise PackageDoesNotVerify(PACKAGE_MISMATCH_FAILURE)
    return package


def _dataset_period(
    version_id: str, provenance: RunProvenance, manifest: CoverageManifest
) -> DatasetPeriod:
    start, end = provenance.covered_start, provenance.covered_end
    return DatasetPeriod(
        dataset_version_id=version_id,
        start=start,
        end=end,
        granularity=_granularity(manifest),
        retail_day_start_hour=_CALENDAR_DAY_HOUR,
        complete=_complete(manifest, start, end),
    )


def _granularity(manifest: CoverageManifest) -> str:
    days = [day for _scope, day in manifest.covered_pairs]
    return granularity_for(days)


def _complete(manifest: CoverageManifest, start: date, end: date) -> bool:
    scopes = tuple(sorted(manifest.scopes))
    if not scopes:
        return False
    return all(_scope_complete(manifest, scope, start, end) for scope in scopes)


def _scope_complete(manifest: CoverageManifest, scope: str, start: date, end: date) -> bool:
    query = CompletenessQuery(
        input_digest=manifest.input_digest,
        source_contract_digest=manifest.source_contract_digest,
        scope=scope,
        start=start,
        end=end,
    )
    return admits_completeness(manifest, query)
