"""Analyses comparison routes (`C1-06`; `RCA-005` `FR-132`, `FR-042`, `FR-050`).

Reachability for a comparison derived at read time: `POST` supplies the ordered
pair, `GET` renders both versions each linking to its Analysis Passport. Scope
comes from the session, never from the address (`FR-042`). An isolation miss is
the one uniform unavailable surface (`FR-050`); an `RRA-008` refusal shows the
C1-04 wording and no figure.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request, Response

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.rca.workspace.comparisons import (
    ComparisonActor,
    ComparisonOutcome,
    ComparisonRequest,
    ComparisonSurfaces,
)
from khepri.rra.report_artifacts import PDF_MEDIA_TYPE, XLSX_MEDIA_TYPE
from khepri.runtime.shell_invitations import ShellRendering, _form

__all__ = ["add_comparison_routes", "offers_comparisons"]


def offers_comparisons(services: Any) -> bool:
    return getattr(services, "comparisons", None) is not None


@dataclass(frozen=True, slots=True)
class _CompareView:
    subject_run_id: str
    baseline_run_id: str
    html: str
    pdf_href: str
    excel_href: str
    refusal: str | None


@dataclass(frozen=True, slots=True)
class _RouteCall:
    services: Any
    rendering: ShellRendering
    clock: Callable[[], datetime]
    language: str
    organization: str
    session: str | None
    asked: ComparisonRequest


def add_comparison_routes(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], datetime],
) -> None:
    """Declare the comparison routes where this deployment offers them."""
    if not offers_comparisons(services):
        return
    _declare_post(app, services, rendering, clock)
    _declare_get(app, services, rendering, clock)


def _declare_post(
    app: FastAPI, services: Any, rendering: ShellRendering, clock: Callable[[], datetime]
) -> None:
    @app.post(f"{rendering.prefix}/{{language}}/{{organization}}/analyses/compare")
    async def compare_post(
        request: Request,
        language: str,
        organization: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        submitted = _form(await request.body())
        asked = ComparisonRequest(
            actor=ComparisonActor(account_id=""),
            organization_id=organization,
            subject_version_id=submitted.get("subject", ""),
            baseline_version_id=submitted.get("baseline", ""),
        )
        call = _RouteCall(services, rendering, clock, language, organization, session, asked)
        return _respond(call)


def _declare_get(
    app: FastAPI, services: Any, rendering: ShellRendering, clock: Callable[[], datetime]
) -> None:
    prefix = rendering.prefix
    path = f"{prefix}/{{language}}/{{organization}}/analyses/compare/{{subject}}/{{baseline}}"

    @app.get(path)
    def compare_get(
        language: str,
        organization: str,
        subject: str,
        baseline: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        asked = ComparisonRequest(
            actor=ComparisonActor(account_id=""),
            organization_id=organization,
            subject_version_id=subject,
            baseline_version_id=baseline,
        )
        call = _RouteCall(services, rendering, clock, language, organization, session, asked)
        return _respond(call)


def _respond(call: _RouteCall) -> Response:
    rendered = call.rendering.language_of(call.language)
    context = _member_or_none(call.services, call.session, call.clock, call.organization)
    if context is None:
        return call.rendering.unavailable(call.rendering.environment, language=rendered)
    request = ComparisonRequest(
        actor=ComparisonActor(account_id=context.account_id),
        organization_id=context.organization_id,
        subject_version_id=call.asked.subject_version_id,
        baseline_version_id=call.asked.baseline_version_id,
        extra_version_ids=call.asked.extra_version_ids,
    )
    try:
        outcome = call.services.comparisons.request(request, now=call.clock())
    except PermissionError:
        return call.rendering.unavailable(call.rendering.environment, language=rendered)
    if outcome.unavailable:
        return call.rendering.unavailable(call.rendering.environment, language=rendered)
    return _page(_PageCall(call, context, rendered, request, outcome))


def _member_or_none(
    services: Any, session: str | None, clock: Callable[[], datetime], organization: str
) -> Any:
    if session is None:
        return None
    try:
        context = services.resolver.for_request(session, organization_id=None, now=clock())
    except PermissionError:
        return None
    if context.organization_id is None:
        return None
    if context.organization_id != organization:
        return None
    return context


@dataclass(frozen=True, slots=True)
class _PageCall:
    route: _RouteCall
    context: Any
    language: str
    request: ComparisonRequest
    outcome: ComparisonOutcome


def _page(page: _PageCall) -> Response:
    from khepri.runtime.shell_frame import offers_of, organization_frame

    context = page.context
    rendering = page.route.rendering
    frame = organization_frame(
        page.route.services.organizations.organizations_for_account(context.account_id),
        context.organization_id,
        surface="analyses",
        offers=offers_of(page.route.services),
    )
    tail = (
        f"/{context.organization_id}/analyses/compare/"
        f"{page.request.subject_version_id}/{page.request.baseline_version_id}"
    )
    return rendering.render(
        rendering.environment,
        "compare.html.j2",
        language=page.language,
        status_code=200,
        view=_view(page.outcome, page.language),
        organization_id=context.organization_id,
        **{**frame, "surface_path": tail},
    )


def _view(outcome: ComparisonOutcome, language: str) -> _CompareView:
    if outcome.refused and outcome.refusal is not None:
        return _CompareView("", "", "", "", "", outcome.refusal.wording[language])
    surfaces = outcome.surfaces
    assert surfaces is not None
    return _filled_view(surfaces, language)


def _filled_view(surfaces: ComparisonSurfaces, language: str) -> _CompareView:
    return _CompareView(
        subject_run_id=surfaces.subject_run_id,
        baseline_run_id=surfaces.baseline_run_id,
        html=surfaces.html[language],
        pdf_href=_data_href(PDF_MEDIA_TYPE, surfaces.pdf[language]),
        excel_href=_data_href(XLSX_MEDIA_TYPE, surfaces.excel),
        refusal=None,
    )


def _data_href(media_type: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{media_type};base64,{encoded}"
