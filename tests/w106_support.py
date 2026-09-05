"""Shared fixtures for `W1-06`: the shell with Analysis detail over `tests/w104b_support.py`'s
journey, so every run the detail describes was admitted, derived, queued and delivered by the real
pipeline and recorded by the real seam.

The shell is composed as `build_shell_services` composes it -- the record store, the isolation
door, the provenance reader over the stack's own `RRA` services, and the real `CommercialBridge`
for the artifact handoff -- with only the session checkpoint stubbed to the member's identifiers.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import AnalysisRun
from khepri.rca.workspace.run_reports import SqlRunReportStore
from khepri.runtime.bridge import CommercialBridge
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_provenance import ProvenanceReader, ProvenanceSources
from tests.w104_support import Member
from tests.w104b_support import Journey, commercial_client, request_report, submit
from tests.w105_support import Context, StubResolver

HTTPS = "https://testserver"


def isolation(j: Journey) -> IsolationService:
    return IsolationService(j.w.organizations, SqlAccountStore(j.w.factory))


def provenance(j: Journey) -> ProvenanceReader:
    """The composition-root read the detail surface is given, over the journey's own services."""
    return ProvenanceReader(
        ProvenanceSources(
            reports=SqlRunReportStore(j.w.factory),
            jobs=j.reader,
            profiling=j.w.profiling,
            packages=j.w.packages,
        ),
        clock=j.clock,
    )


def services_over(
    j: Journey, who: Member, *, with_provenance: bool = True, with_bridge: bool = True
) -> ShellServices:
    return ShellServices(
        resolver=StubResolver(Context(who.account_id, who.organization_id)),
        organizations=j.w.organizations,
        records=j.w.store,
        isolation=isolation(j),
        bridge=(
            CommercialBridge(isolation=isolation(j), store=j.w.sessions) if with_bridge else None
        ),
        provenance=provenance(j) if with_provenance else None,
    )


def shell_over(j: Journey, who: Member, **wiring: bool) -> TestClient:
    app = FastAPI()
    add_shell_routes(app, services=services_over(j, who, **wiring), clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def page(j: Journey, who: Member, tail: str, **options: Any) -> str:
    """One surface as the member sees it; `language` and the wiring flags travel in `options`."""
    language = options.pop("language", "en")
    address = f"{SHELL_PREFIX}/{language}/{who.organization_id}/{tail}"
    return shell_over(j, who, **options).get(address).text


def analyses_address(who: Member, language: str = "en") -> str:
    return f"{SHELL_PREFIX}/{language}/{who.organization_id}/analyses"


def detail_address(who: Member, run_id: str, language: str = "en") -> str:
    return f"{analyses_address(who, language)}/{run_id}"


def handoff_address(who: Member, run_id: str, kind: str, language: str = "en") -> str:
    return f"{detail_address(who, run_id, language)}/artifacts/{kind}"


def submitted(j: Journey, who: Member) -> tuple[TestClient, str]:
    """A commercial session with an admitted, attested upload -- a version, no run yet."""
    client, session_id = commercial_client(j, who)
    submit(client)
    return client, session_id


def started_run(j: Journey, who: Member) -> tuple[AnalysisRun, str, str]:
    """A run the report request started and the worker has not yet settled."""
    client, session_id = submitted(j, who)
    job_id = request_report(client)
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    return run, job_id, session_id


def completed_run(j: Journey, who: Member) -> tuple[AnalysisRun, str, str]:
    """A run the worker delivered: completed, seven artifacts bound, version sealed."""
    _run, job_id, session_id = started_run(j, who)
    j.run_job(job_id)
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    return run, job_id, session_id


__all__ = [
    "HTTPS",
    "analyses_address",
    "completed_run",
    "detail_address",
    "handoff_address",
    "isolation",
    "page",
    "provenance",
    "services_over",
    "shell_over",
    "started_run",
    "submitted",
]
