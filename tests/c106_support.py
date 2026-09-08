"""Shared fixtures for C1-06 comparison orchestration.

Built on the W1-04b journey so every version and run is admitted, derived and
settled through the real pipeline and isolation door. A stub store would answer
any key and miss the point of `RCA-005` `FR-130`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import RUN_COMPLETED, AnalysisRun, DatasetVersion
from khepri.rca.workspace.provenance import SqlRunProvenanceStore
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.runtime.job_sessions import SqlJobSessions
from khepri.runtime.shell_api import SHELL_PREFIX, add_shell_routes
from tests.c105_support import _Printer
from tests.w104_support import GOLDEN_CSV, OTHER_CSV, Member
from tests.w104b_support import Journey, commercial_client, request_report, submit
from tests.w106_support import HTTPS, services_over

__all__ = [
    "CompletedPair",
    "compare_address",
    "compare_form_address",
    "completed_pair",
    "comparison_actions",
    "shell_with_comparisons",
]


@dataclass(frozen=True, slots=True)
class CompletedPair:
    """Two live versions in one scope, each with a completed run and a package."""

    subject: DatasetVersion
    baseline: DatasetVersion
    subject_run: AnalysisRun
    baseline_run: AnalysisRun


def completed_pair(j: Journey, who: Member) -> CompletedPair:
    """Two attested, derived, settled versions in `who`'s organization."""
    client, _session = commercial_client(j, who)
    submit(client, GOLDEN_CSV)
    j.run_job(request_report(client))
    j.clock.advance(timedelta(hours=1))
    other, _session = commercial_client(j, who)
    submit(other, OTHER_CSV)
    j.run_job(request_report(other))
    runs = {
        run.version_id: run
        for run in j.w.store.analysis_runs_for_scope(who.owner_id)
        if run.state == RUN_COMPLETED
    }
    versions = j.w.store.dataset_versions_for_scope(who.owner_id)
    newer, older = versions[0], versions[1]
    return CompletedPair(
        subject=older,
        baseline=newer,
        subject_run=runs[older.version_id],
        baseline_run=runs[newer.version_id],
    )


def comparison_actions(j: Journey, workbooks: Path, printer: Any = None) -> Any:
    """ComparisonActions over the journey's live stores and a fake printer (or the given one)."""
    from khepri.rca.workspace.comparisons import ComparisonActions, ComparisonStores
    from khepri.rra.rendering import ExcelSurfaceRenderer, HtmlReportRenderer, PdfReportRenderer
    from khepri.runtime.comparison_assembly import ComparisonAssemblyPorts, CrossVersionAssembly

    return ComparisonActions(
        isolation=IsolationService(j.w.organizations, SqlAccountStore(j.w.factory)),
        stores=ComparisonStores(
            workspace=j.w.store,
            audit=j.w.audit,
            factory=j.w.factory,
        ),
        assembly=CrossVersionAssembly(
            ports=ComparisonAssemblyPorts(
                packages=j.w.packages,
                profiling=j.w.profiling,
                jobs=SqlJobSessions(j.w.factory),
                reports=SqlRunReportStore(j.w.factory),
                provenance=SqlRunProvenanceStore(j.w.factory),
                workspace=j.w.store,
            ),
            html=HtmlReportRenderer(),
            pdf=PdfReportRenderer(printer=printer or _Printer()),
            excel=ExcelSurfaceRenderer(directory=workbooks),
        ),
    )


def compare_form_address(who: Member, language: str = "en") -> str:
    return f"{SHELL_PREFIX}/{language}/{who.organization_id}/analyses/compare"


def compare_address(who: Member, subject_id: str, baseline_id: str, language: str = "en") -> str:
    return f"{compare_form_address(who, language)}/{subject_id}/{baseline_id}"


def shell_with_comparisons(
    j: Journey, who: Member, workbooks: Path, printer: Any = None
) -> TestClient:
    """A shell whose comparison action is wired, over the journey's isolation door."""
    app = FastAPI()
    actions = comparison_actions(j, workbooks, printer)
    services = replace(services_over(j, who), comparisons=actions)
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client
