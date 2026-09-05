"""Handing a reader from Analysis detail to one of the run's artifacts (`W1-06`; `RCA-005`
`FR-118`; `R7-03`, `R8-06`).

**Why a handoff and not a link.** The report API reads the beta cookie, and the browser holds at
most one -- the session the journey last opened. A run's artifacts belong to *its* session, so a
plain link would serve another analysis's report or none. The handoff resumes the run's own session
through the bridge (`CommercialBridge.resume`: re-authorized, in scope, `R7-03`'s order), sets that
session's cookie exactly as the entry route sets it (`R8-06`), and redirects to the artifact.

**`POST`, like the entry route.** Setting a cookie is a state change and belongs on no `GET`; a
crawler or a prefetch must not swap the reader's analysis session.

**The targets live here, in Python.** `FR-118` says artifacts are reached from detail and nowhere
else; a template carrying report-API addresses would be a second place to reach them from, and
`test_w106_analysis_detail.py` scans every template for one.

**Every refusal is `unavailable`, with no cookie.** A run that is not this scope's, a run with no
report, a kind the address does not name, a session the bridge will not resume: the same surface,
and no `Set-Cookie`, because a cookie beside a refusal would hand a session to a reader who was
just denied one (the entry route's rule).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse

from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.runtime.shell_frame import offers_analyses
from khepri.runtime.shell_invitations import ShellRendering
from khepri.runtime.shell_journey_entry import hand_off_session
from khepri.runtime.shell_workspace import UnrenderableRecord, report_key

#: Where each kind lives in the report API, by the language the address carries. The kinds are
#: `shell_analysis.ARTIFACT_KINDS`'; a kind absent here is refused.
ARTIFACT_TARGETS: dict[str, str] = {
    "web": "/api/v1/beta/reports/{job}/surfaces/web/{language}",
    "evidence": "/api/v1/beta/reports/{job}/surfaces/evidence/{language}",
    "pdf": "/api/v1/beta/reports/{job}/surfaces/pdf/{language}",
    "excel": "/api/v1/beta/reports/{job}/surfaces/excel",
}


def add_artifact_handoff_route(
    app: FastAPI,
    *,
    services: Any,
    rendering: ShellRendering,
    clock: Callable[[], Any],
) -> None:
    """Declare the handoff, or none at all when detail is not offered (`FR-049`)."""
    if not offers_analyses(services):
        return

    environment = rendering.environment
    language_of = rendering.language_of
    unavailable = rendering.unavailable

    @app.post(f"{rendering.prefix}/{{language}}/{{organization}}/analyses/{{run_id}}/artifacts/{{kind}}")
    def hand_off_artifact(
        language: str,
        organization: str,
        run_id: str,
        kind: str,
        session: CommercialSessionCookie = None,
    ) -> Response:
        rendered = language_of(language)
        target = ARTIFACT_TARGETS.get(kind)
        if session is None or target is None:
            return unavailable(environment, language=rendered)
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=organization, now=now)
            located = _locate(services, context, run_id)
            if located is None:
                return unavailable(environment, language=rendered)
            resumed = services.bridge.resume(
                account_id=context.account_id,
                organization_id=context.organization_id,
                session_id=located.session_id,
                now=now,
            )
        except (PermissionError, UnrenderableRecord):
            return unavailable(environment, language=rendered)
        if resumed is None:
            return unavailable(environment, language=rendered)
        response = RedirectResponse(
            url=target.format(job=located.job_id, language=rendered), status_code=303
        )
        hand_off_session(response, resumed.session_id)
        return response


def _locate(services: Any, context: Any, run_id: str) -> Any:
    """The provenance of a completed, fully bound run in the session's scope, or `None`.

    Resolved through the same door the surfaces read under (`FR-042`): the scope comes from the
    session's organization, and the run must be in it. A run with no report has nothing to hand
    off, whatever the address asks for.
    """
    owner_id = services.isolation.resolve_scope(context.account_id, context.organization_id)
    history = services.records.history_for_scope(owner_id)
    run = next((r for r in history.runs if r.run_id == run_id), None)
    if run is None:
        return None
    bound = frozenset(b.surface for b in history.bindings if b.run_id == run_id)
    if report_key(run, bound) != "report_available":
        return None
    version = next((v for v in history.versions if v.version_id == run.version_id), None)
    if version is None:
        raise UnrenderableRecord("A run names a version the history does not hold.")
    return services.provenance.for_run(owner_id, run, version)


__all__ = ["ARTIFACT_TARGETS", "add_artifact_handoff_route"]
