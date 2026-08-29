"""The HTTP surface for requesting a report, polling it, and fetching it.

**Why these routes are not in `api`.** `create_app` declares every other route
group inline and is already past every complexity threshold the project
measures, so each group added to it makes a tracked file measurably worse. This
module registers its own group instead, which keeps `create_app` exactly as it
was and puts the report surface where it can be read on its own.

**The conditional lives here, not in `create_app`.** `add_report_routes`
returns without declaring anything when no collaborators were supplied, so the
route group is still registered conditionally on an optional keyword-only
parameter -- the same contract every other group has, one function deeper.

**What this module decides and what it does not.** It decides paths, status
codes, and response shapes. Which states, reasons, and deliveries may be
described at all is decided in `reports`, which owns the governed vocabularies
and the fail-closed guards. Nothing here reads a store, builds a pipeline, or
renders a surface.

**Responses carry no customer content.** Not a figure, a caveat, a safe label, a
filename, a storage location, or a credential. The bundle route in particular
serves a *manifest* of what was published rather than the report: a download
location would be both a storage location and a credential, and RRA-007 excludes
both from anything this surface emits.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rra import definitions
from khepri.rra.artifact_publication import ArtifactDocument
from khepri.rra.datasets import ProfileCorrupted
from khepri.rra.jobs import UnknownJobState
from khepri.rra.packages import PackageCorrupted, PackageRefused
from khepri.rra.rendering import wording
from khepri.rra.reports import (
    DeliveredBundle,
    DeliveryWithheld,
    JobEvidenceContradicted,
    ReportJobView,
    ReportPackageMissing,
    ReportServices,
    job_outcome,
    reconcile_delivery,
)
from khepri.rra.session_cookie import SESSION_UNAVAILABLE, BetaSessionCookie
from khepri.rra.sessions import (
    ConsentRequired,
    CrossSessionAccessDenied,
    SessionExpired,
)

# An opaque job identifier, bounded so an unbounded path segment never reaches a
# store as a lookup key.
JobIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
ArtifactLanguage = Annotated[
    str,
    StringConstraints(pattern=r"^(ar|en)$"),
]

_NO_JOB = "No report job is available for this session."
_NO_BUNDLE = "No delivered report is available for this session."
_NO_ARTIFACT = "No report artifact is available for this session."


class ReportRequestBody(BaseModel):
    """A report request carries no request of its own.

    Which figures a report contains was decided when the dataset was profiled
    and fixed when the fact package was published. A field here -- a template, a
    title, a set of semantics -- would be a second decision able to disagree
    with the first, so the model exists to refuse one rather than to carry one.
    """

    model_config = ConfigDict(extra="forbid")


class ReportJobResponse(BaseModel):
    """One job's governed state, and for a finished job what it produced.

    Content-free by construction: an opaque job identifier, a state from the
    governed vocabulary, two timestamps, a bundle content address, and two
    governed reason codes. There is no field a label, a figure, a filename, or a
    provider sentence could occupy.

    Both reasons are here because they answer different questions about an
    abandoned job. `dead_letter_reason` says why the queue stopped retrying it;
    `reason` says what its last attempt failed on. Collapsing them into one field
    would make a job abandoned because its content was deleted indistinguishable
    from one abandoned after exhausting retries on a refused narrative.
    """

    job_id: str
    state: str
    queued_at: datetime
    completed_at: datetime | None
    bundle_id: str | None
    reason: str | None
    dead_letter_reason: str | None


class ReportBundleResponse(BaseModel):
    """The delivered report as a manifest of what was published, not as content.

    Deliberately no figures, no caveats, no narrative, no filenames, and no
    download location or credential of any kind. What a caller is owed here is
    that one whole report exists and what it is bound to: the bundle's content
    address, the fact-package version behind every surface of it, whether
    commentary was included, and which surfaces were delivered.
    """

    job_id: str
    bundle_id: str
    package_version: str
    narrative_state: str
    surfaces: list[str]


def add_report_routes(
    app: FastAPI,
    *,
    services: ReportServices | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the report route group, or declare nothing at all."""
    if services is None:
        return

    @app.post(
        "/api/v1/beta/reports",
        response_model=ReportJobResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def request_retail_report(
        payload: ReportRequestBody,
        response: Response,
        session_id: BetaSessionCookie = None,
    ) -> ReportJobResponse:
        # `payload` is declared and unused on purpose: it is the guard that
        # refuses a caller who invents a field. See `ReportRequestBody`.
        return _requested_report(
            services,
            response=response,
            session_id=_require_session(session_id),
            now=clock(),
        )

    @app.get("/api/v1/beta/catalog/{language}")
    def read_metric_catalog(
        language: ArtifactLanguage,
        session_id: BetaSessionCookie = None,
    ) -> dict[str, object]:
        """Every governed metric, with what it means and what it does not.

        Session-scoped like its siblings even though it carries no customer
        data: `RCA-002` keeps the authenticated surface set closed, and a route
        that answered without a session would be a new public surface rather
        than a new view of an existing one.

        A thin delegator on purpose. `definitions` assembles the answer, and
        inlining that here would put a second projection of the catalog beside
        the one `RRA-011` requires be single.
        """
        _require_session(session_id)
        return _metric_catalog(language)

    @app.get(
        "/api/v1/beta/reports/{job_id}",
        response_model=ReportJobResponse,
    )
    def read_retail_report_job(
        job_id: JobIdentifier,
        session_id: BetaSessionCookie = None,
    ) -> ReportJobResponse:
        caller = _require_session(session_id)
        return _job_response(
            _found(
                lambda: services.jobs.get_session_job(
                    session_id=caller,
                    job_id=job_id,
                    now=clock(),
                ),
                missing=_NO_JOB,
            )
        )

    @app.get(
        "/api/v1/beta/reports/{job_id}/bundle",
        response_model=ReportBundleResponse,
    )
    def read_retail_report_bundle(
        job_id: JobIdentifier,
        session_id: BetaSessionCookie = None,
    ) -> ReportBundleResponse:
        caller = _require_session(session_id)
        return _bundle_response(
            _found(
                lambda: services.bundles.get_session_bundle(
                    session_id=caller,
                    job_id=job_id,
                    now=clock(),
                ),
                missing=_NO_BUNDLE,
            ),
            job_id=job_id,
        )

    if services.artifacts is not None:

        def artifact_response(
            job_id: str,
            artifact_kind: str,
            session_id: str | None,
        ) -> Response:
            caller = _require_session(session_id)
            try:
                document = services.artifacts.get_session_artifact(
                    session_id=caller,
                    job_id=job_id,
                    artifact_kind=artifact_kind,
                    now=clock(),
                )
            except Exception as error:
                raise HTTPException(
                    status_code=503,
                    detail="Report artifact is unavailable.",
                ) from error
            if document is None:
                raise HTTPException(status_code=404, detail=_NO_ARTIFACT)
            return _artifact_response(document)

        @app.get("/api/v1/beta/reports/{job_id}/surfaces/web/{language}")
        def read_business_html(
            job_id: JobIdentifier,
            language: ArtifactLanguage,
            session_id: BetaSessionCookie = None,
        ) -> Response:
            return artifact_response(job_id, f"web_business_{language}", session_id)

        @app.get("/api/v1/beta/reports/{job_id}/surfaces/evidence/{language}")
        def read_evidence_html(
            job_id: JobIdentifier,
            language: ArtifactLanguage,
            session_id: BetaSessionCookie = None,
        ) -> Response:
            return artifact_response(job_id, f"web_evidence_{language}", session_id)

        @app.get("/api/v1/beta/reports/{job_id}/surfaces/pdf/{language}")
        def read_pdf(
            job_id: JobIdentifier,
            language: ArtifactLanguage,
            session_id: BetaSessionCookie = None,
        ) -> Response:
            return artifact_response(job_id, f"pdf_{language}", session_id)

        @app.get("/api/v1/beta/reports/{job_id}/surfaces/excel")
        def read_excel(
            job_id: JobIdentifier,
            session_id: BetaSessionCookie = None,
        ) -> Response:
            return artifact_response(job_id, "excel", session_id)


def _requested_report(
    services: ReportServices,
    *,
    response: Response,
    session_id: str,
    now: datetime,
) -> ReportJobResponse:
    """Ask for this caller's report, and say whether this call is what asked."""
    try:
        view, created = services.jobs.request_session_report(
            session_id=session_id,
            now=now,
        )
    except Exception as error:
        raise _refusal_for(error) from error
    if not created:
        # The same request, so the same job. A second identifier here would be a
        # second report built from one package, and RRA-007 requires the
        # background job be idempotent rather than merely repeatable.
        response.status_code = status.HTTP_200_OK
    return _job_response(view)


def _found[T](read: Callable[[], T | None], *, missing: str) -> T:
    """Whatever this caller's own scope holds, or a plain absence.

    Both reads this surface makes are keyed by the caller's session, so a
    resource belonging to somebody else is absent here rather than forbidden.
    That is why one shared absence is correct: an identifier that names another
    caller's report and one that names nothing at all get the same answer, byte
    for byte, and neither confirms the other caller's report exists.
    """
    try:
        found = read()
    except Exception as error:
        raise _refusal_for(error) from error
    if found is None:
        raise HTTPException(status_code=404, detail=missing)
    return found


def _job_response(view: ReportJobView) -> ReportJobResponse:
    """One job as a caller sees it, or a refusal to describe it at all.

    What may be said is decided in `reports.job_outcome`, which owns the
    governed vocabularies. All that happens here is the mapping onto a status.
    """
    try:
        outcome = job_outcome(view)
    except (JobEvidenceContradicted, UnknownJobState) as error:
        # Deliberately indistinguishable between an ungoverned state, a missing
        # delivery record, a record naming another job, and a dead-letter reason
        # that contradicts the state. Which invariant a store broke is an
        # operator's question, and answering it here would describe stored state
        # to a caller who cannot act on it.
        raise HTTPException(
            status_code=503,
            detail="Report job state is unavailable.",
        ) from error
    return ReportJobResponse(
        job_id=view.job.job_id,
        state=outcome.state,
        queued_at=view.job.queued_at,
        completed_at=view.job.completed_at,
        bundle_id=outcome.bundle_id,
        reason=outcome.reason,
        dead_letter_reason=outcome.dead_letter_reason,
    )


def _bundle_response(bundle: DeliveredBundle, *, job_id: str) -> ReportBundleResponse:
    """The manifest of one whole report, or nothing.

    Every field is taken from the delivery record rather than from the stored
    surfaces, and the record has already refused to name fewer than every
    required surface. The surfaces are what the record is checked against.
    """
    try:
        reconcile_delivery(bundle, job_id=job_id)
    except DeliveryWithheld as withheld:
        # The governed reason stays on the exception. Which invariant a store
        # broke is an operator's question; a caller is told only that no whole
        # report can be served, which is the answer RRA-006 requires.
        raise HTTPException(
            status_code=503,
            detail="Report bundle is unavailable.",
        ) from withheld
    record = bundle.record
    return ReportBundleResponse(
        job_id=record.job_id,
        bundle_id=record.bundle_id,
        package_version=record.package_version,
        narrative_state=record.narrative_state,
        surfaces=list(record.surfaces),
    )


def _artifact_response(document: ArtifactDocument) -> Response:
    return Response(
        content=document.content,
        media_type=document.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{document.file_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# How a governed refusal reaches a caller. A table rather than a chain of
# `except` clauses inside each route: the report routes refuse for the same
# reasons, and three copies of one mapping is three places for them to drift.
# `None` for the detail means the exception's own message is already governed
# text -- every one of those is a fixed sentence written in this package.
_REPORT_REFUSALS: tuple[tuple[type[Exception], int, str | None], ...] = (
    (SessionExpired, 401, SESSION_UNAVAILABLE),
    (CrossSessionAccessDenied, 401, SESSION_UNAVAILABLE),
    (ConsentRequired, 403, None),
    (ReportPackageMissing, 404, None),
    (PackageRefused, 409, None),
    (PackageCorrupted, 503, "Stored fact package is unavailable."),
    (ProfileCorrupted, 503, "Stored fact package is unavailable."),
)


def _refusal_for(error: Exception) -> HTTPException:
    """The status one governed refusal reaches a caller as.

    An error this table does not recognize is re-raised rather than reported as
    a refusal, so an unmapped failure fails closed as a server error instead of
    being described to a caller in words nothing here governs.
    """
    for kind, code, detail in _REPORT_REFUSALS:
        if isinstance(error, kind):
            return HTTPException(status_code=code, detail=detail or str(error))
    raise error


def _require_session(session_id: str | None) -> str:
    if session_id is None:
        raise HTTPException(status_code=401, detail=SESSION_UNAVAILABLE)
    return session_id


def _metric_catalog(language: str) -> dict[str, object]:
    """The catalog as one JSON body, in the asked language.

    Business and Audit tiers only. No precision, no population and no section
    state: the first two are properties of a run rather than of a metric, and
    the third is Internal tier, which `RRA-009` renders on no customer surface.
    """
    return {
        "metrics": [
            {
                "code": code,
                # The governed contract that computes it, read from that
                # contract's own version constant. A family *label* would be a
                # code this catalog coined, which `RRA-011` admits none of.
                "formula_version": definitions.define_metric(code).formula_version,
                # `None` where the metric has no customer-facing name, which is
                # a real distinction rather than a gap: `concentration_curve`
                # names the retained series a chart reads and is deliberately
                # label-free, so inventing a name for it would put a heading on
                # something no reader is ever shown as a figure.
                "name": wording.business_metric_name(code, language),
                "description": definitions.describe_metric(code, language),
                "not_meant": definitions.not_meant(code, language),
            }
            for code in sorted(definitions.METRIC_CODES)
        ],
    }


__all__ = [
    "JobIdentifier",
    "ArtifactLanguage",
    "ReportBundleResponse",
    "ReportJobResponse",
    "ReportRequestBody",
    "add_report_routes",
]
