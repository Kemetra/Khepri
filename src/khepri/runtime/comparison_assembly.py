"""RRA half of C1-06 comparison orchestration.

`RCA-005` `FR-130`--`FR-133` and §Comparison retention live in
`khepri.rca.workspace.comparisons`; this module loads retained packages and
coverage manifests, calls `assemble_crossversion`, and renders the three
surfaces in-request. `R7-01` §3 forbids `khepri.rca` from importing
`khepri.rra`, so the composition sits here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
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
from khepri.rra.analysis.dataset_period import CAUSE_INCOMPLETE, CAUSE_UNORDERED_PAIR, DatasetPeriod
from khepri.rra.bundle import BundleAssembler
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
            return _incomplete_outcome()
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
        surfaces = self._render(built, subject.run_id, baseline.run_id)
        if surfaces is None:
            return None
        return ComparisonOutcome(kind=KIND_ADMITTED, surfaces=surfaces, bundle=built)

    def _render(
        self, bundle: Any, subject_run_id: str, baseline_run_id: str
    ) -> ComparisonSurfaces | None:
        result = BundleAssembler(renderers=(self._html, self._pdf, self._excel)).assemble(bundle)
        if result.incomplete or result.surfaces is None:
            return None
        html = self._html.render_html(bundle)
        pdf = self._pdf.render_pdf(bundle)
        excel = self._excel.render_materialized(bundle)
        # The workbook renderer writes a file to reach its bytes. `RRA-006` §Not stored:
        # a two-population bundle is rendered on request and retained nowhere, so the
        # file goes as soon as its bytes are in hand; the directory holds nothing between
        # requests, and a process that ran for a year has kept no comparison on disk.
        self._excel.path_for(bundle).unlink(missing_ok=True)
        return ComparisonSurfaces(
            claims={content.surface: content for content in result.surfaces},
            html=html.documents,
            pdf=pdf.documents,
            excel=excel.artifacts[0].content,
            subject_run_id=subject_run_id,
            baseline_run_id=baseline_run_id,
        )


def _incomplete_outcome() -> ComparisonOutcome:
    return ComparisonOutcome(
        kind=KIND_REFUSED,
        refusal=ComparisonRefusal(CAUSE_INCOMPLETE, refusal_wording(CAUSE_INCOMPLETE)),
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
    manifest = stored_manifest(profile)
    if manifest is None:
        return _Load(None, True)
    period = _dataset_period(ask.version_id, provenance, manifest)
    operand = _Operand(bound.package, period, manifest.aggregate_scope, bound.run.run_id)
    return _Load(operand, False)


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
