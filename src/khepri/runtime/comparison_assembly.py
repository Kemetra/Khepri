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
from datetime import datetime
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
from khepri.rca.workspace.provenance import SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.rca.workspace.store import SqlWorkspaceRecordStore
from khepri.rra.analysis.comparison_narrative import refusal_wording
from khepri.rra.analysis.dataset_period import CAUSE_INCOMPLETE, CAUSE_UNORDERED_PAIR
from khepri.rra.bundle import BundleAssembler, SurfaceContent
from khepri.rra.datasets import ProfilingService
from khepri.rra.packages import FactPackageService
from khepri.rra.rendering.excel import ExcelSurfaceRenderer
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PdfReportRenderer
from khepri.runtime.comparison_operands import (
    ComparisonOperand,
    OperandLoad,
    OperandRequest,
    admit_pair,
    derive_operand,
)
from khepri.runtime.job_sessions import SqlJobSessions

__all__ = ["ComparisonAssemblyPorts", "CrossVersionAssembly"]


@dataclass(frozen=True, slots=True)
class ComparisonAssemblyPorts:
    """Where a completed run's package and coverage manifest are read."""

    packages: FactPackageService
    profiling: ProfilingService
    jobs: SqlJobSessions
    reports: SqlRunReportStore
    provenance: SqlRunProvenanceStore
    workspace: SqlWorkspaceRecordStore


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
        self, owner_id: str, subject: ComparisonOperand, baseline: ComparisonOperand
    ) -> ComparisonOutcome | None:
        admission = admit_pair(owner_id, subject, baseline)
        if admission.bundle is None:
            return ComparisonOutcome(
                kind=KIND_REFUSED,
                refusal=ComparisonRefusal(admission.cause, admission.wording),
            )
        surfaces = self._render(admission.bundle, subject.run_id, baseline.run_id)
        if surfaces is None:
            return None
        return ComparisonOutcome(kind=KIND_ADMITTED, surfaces=surfaces, bundle=admission.bundle)

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


def _load_missing(subject: OperandLoad, baseline: OperandLoad) -> bool:
    if subject.operand is None and not subject.incomplete:
        return True
    return baseline.operand is None and not baseline.incomplete


def _load_incomplete(subject: OperandLoad, baseline: OperandLoad) -> bool:
    if subject.incomplete:
        return True
    return baseline.incomplete


def _load_operand(
    ports: ComparisonAssemblyPorts, owner_id: str, version_id: str, now: datetime
) -> OperandLoad:
    run = _latest_completed(ports.workspace, owner_id, version_id)
    if run is None:
        return OperandLoad(None, False)
    return derive_operand(OperandRequest(ports=ports, owner_id=owner_id, run=run, now=now))


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
    # A completed run always carries its instant: `RunOutcome._has_provenance` refuses one
    # without it at the only doors that build an `AnalysisRun`, and the schema CHECK
    # `ck_rca_workspace_run_completion_provenance` refuses the row. `_completed_for` admits
    # only completed runs, so there is no absent instant left to rank.
    assert completed is not None
    return (completed, run.run_id)
