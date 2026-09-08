"""Analyses comparison routes (`C1-06`; `RCA-005` `FR-132`, `FR-042`, `FR-050`).

Reachability for a comparison derived at read time: `POST` supplies the ordered
pair, `GET` renders both versions each linking to its Analysis Passport. Scope
comes from the session, never from the address (`FR-042`). An isolation miss is
the one uniform unavailable surface (`FR-050`); an `RRA-008` refusal shows the
C1-04 wording and no figure.
"""

from __future__ import annotations

import asyncio
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
from khepri.rra.report_artifacts import HTML_MEDIA_TYPE, PDF_MEDIA_TYPE, XLSX_MEDIA_TYPE
from khepri.runtime.shell_invitations import ShellRendering, _form
from khepri.runtime.shell_workspace import Moment, moment

__all__ = ["add_comparison_routes", "offers_comparisons"]


def offers_comparisons(services: Any) -> bool:
    return getattr(services, "comparisons", None) is not None


@dataclass(frozen=True, slots=True)
class _OperandView:
    """One source version, named as the Data surface and the Passport name it (`FR-119`):
    the submission instant linking to its Data entry, with the identifier in the anchor
    rather than leading. The Passport link needs a run, which a refusal never bound."""

    version_id: str
    submitted: Moment
    run_id: str | None


@dataclass(frozen=True, slots=True)
class _CompareView:
    subject: _OperandView | None
    baseline: _OperandView | None
    html_href: str
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
        # The body is read on the loop; the render is not. It launches Chromium through
        # Playwright's synchronous API, which refuses to start on a running event loop, and
        # the assembler would turn that refusal into the uniform unavailable page for a pair
        # the GET address -- a plain `def`, run in the threadpool -- renders. Same thread
        # model on both paths.
        return await asyncio.to_thread(_respond, call)


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
    surfaces = outcome.surfaces
    subject = _operand_view(outcome, "subject", surfaces)
    baseline = _operand_view(outcome, "baseline", surfaces)
    if outcome.refused and outcome.refusal is not None:
        return _CompareView(subject, baseline, "", "", "", outcome.refusal.wording[language])
    assert surfaces is not None
    return _filled_view(subject, baseline, surfaces, language)


def _operand_view(
    outcome: ComparisonOutcome, side: str, surfaces: ComparisonSurfaces | None
) -> _OperandView | None:
    if outcome.operands is None:
        return None
    version = getattr(outcome.operands, side)
    run_id = None if surfaces is None else getattr(surfaces, f"{side}_run_id")
    return _OperandView(
        version_id=version.version_id, submitted=moment(version.created_at), run_id=run_id
    )


def _filled_view(
    subject: _OperandView | None,
    baseline: _OperandView | None,
    surfaces: ComparisonSurfaces,
    language: str,
) -> _CompareView:
    return _CompareView(
        subject=subject,
        baseline=baseline,
        # The three surfaces travel in this response as `data:` downloads. The redirect
        # handoff other Analyses artifacts use points at a stored run's artifact, and a
        # comparison has none: `RRA-006` §Two-population bundle renders it on request and
        # stores it nowhere. Nothing is framed or inlined, since the shell's policy is
        # `default-src 'none'` with no frame directive. The response is therefore the sum
        # of the three payloads plus base64 overhead, assembled in memory per request.
        html_href=_data_href(HTML_MEDIA_TYPE, surfaces.html[language].encode("utf-8")),
        pdf_href=_data_href(PDF_MEDIA_TYPE, surfaces.pdf[language]),
        excel_href=_data_href(XLSX_MEDIA_TYPE, surfaces.excel),
        refusal=None,
    )


def _data_href(media_type: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{media_type};base64,{encoded}"
