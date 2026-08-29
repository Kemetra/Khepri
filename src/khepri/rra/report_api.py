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

**The report routes carry no customer content.** Not a figure, a caveat, a safe
label, a filename, a storage location, or a credential. The bundle route in
particular serves a *manifest* of what was published rather than the report: a
download location would be both a storage location and a credential, and RRA-007
excludes both from anything this surface emits.

**The catalog routes are the deliberate exception, and a narrow one.** RRA-011
governs them, and they do serve reason and caveat codes, the bilingual wording
those codes carry, and the evidence path behind one citation -- that is the
point of a catalog. What they still never serve is a figure: no value, no
rendered number, no storage location, and no Internal-tier field. They answer
what a code *means* and what a package reconciled against, never what it
measured. A route here that returned a figure would be an RRA-006 surface
wearing this one's name.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints

from khepri.rra import definitions
from khepri.rra.artifact_publication import ArtifactDocument
from khepri.rra.bundle import ReportBundle
from khepri.rra.datasets import ProfileCorrupted
from khepri.rra.facts import FactPackage
from khepri.rra.jobs import UnknownJobState
from khepri.rra.package_source import SessionPackageReader, rebuild_fact_package
from khepri.rra.packages import PackageCorrupted, PackageRefused
from khepri.rra.rendering.html import build_cells, build_context
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
# A governed code as it appears in a path. Bounded like `JobIdentifier`, and it
# admits `:` because a population code names a family member that way --
# `dimension_complete_sales:category`. The pattern bounds the segment; it never
# decides admissibility, which the catalog's own refusal does.
CatalogCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[a-z0-9_:.]+$",
    ),
]

_NO_JOB = "No report job is available for this session."
_NO_BUNDLE = "No delivered report is available for this session."
_NO_ARTIFACT = "No report artifact is available for this session."
_NO_PACKAGE = "No fact package is available for this session."
_NO_CITATION = "No such citation is published in this report."


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


class MetricDefinitionResponse(BaseModel):
    """What one metric is, in one language, and what it must not be read as.

    `code` is a plain string and never an enumerated type. A `Literal` over the
    governed codes would be a second hand-maintained list of them, which
    `RRA-011`'s single-truth test forbids -- and one the repository's
    hand-listed-set detector could not see, because it scans set literals.
    """

    code: str
    formula_version: str
    description: str
    not_meant: str
    synonyms: list[str]


class PopulationDefinitionResponse(BaseModel):
    """One population, and whether it names a family rather than a member.

    `dimension_complete_sales:<dimension>` is a family whose members are whichever
    dimensions the mapping resolved, so the catalog admits it by its module's own
    prefix rule rather than by membership of a constants set.
    """

    code: str
    is_family: bool


class ReasonDefinitionResponse(BaseModel):
    """One refusal reason, the scopes it is stated at, and what it says.

    `wording` is the accepted prose `RRA-009` owns, surfaced rather than parsed.
    There is deliberately no structured alternative or remedy field: what a reader
    could do instead exists only inside that sentence, and recording it as data
    would be a second machine-shaped account of advice that would drift.
    """

    code: str
    scopes: list[str]
    wording: str


class CaveatDefinitionResponse(BaseModel):
    """One caveat and what it says. Unscoped, as the governed record is."""

    code: str
    wording: str


class SectionOutcome(BaseModel):
    """One analysis and the reason it was refused, or `None` where it answered.

    No `state`: `Section.state` is Internal tier and reaches no customer surface,
    so a refused section is the one carrying a reason. The audit region the
    evidence surface renders from classifies the same way.
    """

    section_id: str
    reason: str | None


class CaveatStatement(BaseModel):
    """One caveat and the analysis it qualified, or `None` for a report-level one."""

    code: str
    section: str | None


class RetainedBasisEvidence(BaseModel):
    """One reconciliation basis, exactly as `RRA-011` enumerates it.

    `population` is here and on no figure. A `Fact` carries no population, and a
    package retains several bases with different ones, so naming a population
    beside a figure would present an inference as a record.
    """

    name: str
    population: str
    event_count: int
    input_digest: str
    precision: int


class AnalysisQualityResponse(BaseModel):
    """Which analyses answered, which were qualified, and which were refused.

    An aggregation of outcomes the package already carries, never a measurement:
    no score, no confidence, no percentage. `caveated_sections` is a subset of
    `answered_sections` -- a qualified answer is still an answer.
    """

    answered: int
    caveated: int
    refused: int
    refusals: list[SectionOutcome]
    refused_results: list[SectionOutcome]
    caveats: list[str]
    answered_sections: list[str]
    caveated_sections: list[str]


class FactEvidenceResponse(BaseModel):
    """The evidence path behind one citation, from the projection the report renders.

    Two keys of that projection are deliberately absent rather than empty.
    `provenance` carries a `bundle_id` derived over the narrative, which is not
    persisted and so cannot be reproduced here -- serving it would publish an
    identifier no delivered surface ever echoed. `passages` is that same narrative.
    Absence and emptiness are different findings, and neither is claimed.

    Coverage, filters and reconciliation are read from the package rather than
    from the audit region, because that is where those records live.
    """

    citation_id: str
    metric: str
    formula_version: str
    definition: str
    figure_ids: list[str]
    sections: list[SectionOutcome]
    caveats: list[CaveatStatement]
    coverage_manifest_identity: str | None
    coverage_signatures: list[str]
    event_kind_filters: list[str]
    status_filters: list[str]
    reconciliation: list[RetainedBasisEvidence]


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
    # A code the catalog does not admit is absent, not forbidden. `UnknownCode`
    # is its fail-closed refusal -- it never degrades to the code string and
    # never returns `None` -- so it belongs in this table rather than in a
    # per-route `except`, for the reason stated above it.
    (definitions.UnknownCode, 404, None),
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


def add_catalog_routes(
    app: FastAPI,
    *,
    services: ReportServices | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the catalog route group, or declare nothing at all.

    Session scoped rather than job scoped, which `RRA-011`'s Scope requires: these
    expose "the registry, the summary, and a fact's evidence" -- a fact's, not a
    report's. The sibling routes above are job scoped because they serve one
    delivered artifact; the catalog answers about the admitted data, and
    `summarize` and `availability` take no job either.

    A report-keyed evidence route is not currently buildable and is filed rather
    than approximated: no governed record ties a delivered report to the package
    it was built from. `DeliveryRecord` carries a `bundle_id` derived over the
    unpersisted narrative and a `package_version` a session's several packages
    share, so neither identifies one package. Supplying that link is an `RRA-004`
    change to what a delivery record carries.

    Declared in two halves because they answer at two scopes. The registry reads
    resolve at import and need no package; the summary and evidence reads resolve
    only against one this caller published.
    """
    if services is None or services.packages is None:
        return

    _add_registry_routes(app)
    _add_package_routes(app, packages=services.packages, clock=clock)


def _add_registry_routes(app: FastAPI) -> None:
    """Catalog-scope reads: what a governed code means, in one language.

    Every one still resolves a session. `RRA-011` scopes *every* read route, and a
    definition is a customer surface even though it reads no store -- so the
    return of `_require_session` is discarded here rather than unused by accident.
    """

    @app.get(
        "/api/v1/beta/catalog/metrics/{code}/{language}",
        response_model=MetricDefinitionResponse,
    )
    def read_metric_definition(
        code: CatalogCode,
        language: ArtifactLanguage,
        session_id: BetaSessionCookie = None,
    ) -> MetricDefinitionResponse:
        _require_session(session_id)
        return _metric_definition_response(code, language)

    @app.get(
        "/api/v1/beta/catalog/populations/{code}",
        response_model=PopulationDefinitionResponse,
    )
    def read_population_definition(
        code: CatalogCode,
        session_id: BetaSessionCookie = None,
    ) -> PopulationDefinitionResponse:
        _require_session(session_id)
        return _population_definition_response(code)

    @app.get(
        "/api/v1/beta/catalog/reasons/{code}/{scope}/{language}",
        response_model=ReasonDefinitionResponse,
    )
    def read_reason_definition(
        code: CatalogCode,
        scope: CatalogCode,
        language: ArtifactLanguage,
        session_id: BetaSessionCookie = None,
    ) -> ReasonDefinitionResponse:
        _require_session(session_id)
        return _reason_definition_response(code, scope, language)

    @app.get(
        "/api/v1/beta/catalog/caveats/{code}/{language}",
        response_model=CaveatDefinitionResponse,
    )
    def read_caveat_definition(
        code: CatalogCode,
        language: ArtifactLanguage,
        session_id: BetaSessionCookie = None,
    ) -> CaveatDefinitionResponse:
        _require_session(session_id)
        return _caveat_definition_response(code, language)


def _add_package_routes(
    app: FastAPI,
    *,
    packages: SessionPackageReader,
    clock: Callable[[], datetime],
) -> None:
    """Package-scope reads: what this caller's own admitted data supports."""

    @app.get(
        "/api/v1/beta/catalog/quality/{language}",
        response_model=AnalysisQualityResponse,
    )
    def read_analysis_quality(
        language: ArtifactLanguage,
        session_id: BetaSessionCookie = None,
    ) -> AnalysisQualityResponse:
        caller = _require_session(session_id)
        bundle, _ = _session_bundle(packages, session_id=caller, now=clock())
        return _quality_response(bundle)

    @app.get(
        "/api/v1/beta/catalog/citations/{citation_id}/evidence/{language}",
        response_model=FactEvidenceResponse,
    )
    def read_citation_evidence(
        citation_id: CatalogCode,
        language: ArtifactLanguage,
        session_id: BetaSessionCookie = None,
    ) -> FactEvidenceResponse:
        caller = _require_session(session_id)
        bundle, package = _session_bundle(packages, session_id=caller, now=clock())
        return _evidence_response(bundle, package, citation_id, language)


def _session_bundle(
    packages: SessionPackageReader,
    *,
    session_id: str,
    now: datetime,
) -> tuple[ReportBundle, FactPackage]:
    """This caller's own package, and the bundle it rebuilds.

    Re-derived rather than read back, because no store holds a bundle. Every
    figure, section, caveat and citation is derived from the package alone, so
    what this returns is the same content the delivered surfaces rendered -- but
    it is deliberately not addressed by `bundle_id`, which hashes the narrative a
    provider composed and nothing persists.

    The digest check is this function's own rather than the caller's: rebuilding
    and comparing proves both that the stored document is intact and that nothing
    was lost or invented in rebuilding it.
    """
    record = _found(
        lambda: packages.get_session_package(session_id=session_id, now=now),
        missing=_NO_PACKAGE,
    )
    package = rebuild_fact_package(record.document)
    if package.digest != record.package_digest:
        raise PackageCorrupted("Rebuilt fact package does not match its digest.")
    return ReportBundle.of(package), package


def _metric_definition_response(code: str, language: str) -> MetricDefinitionResponse:
    definition = _defined(lambda: definitions.define_metric(code))
    return MetricDefinitionResponse(
        code=definition.code,
        formula_version=definition.formula_version,
        description=definitions.describe_metric(code, language),
        not_meant=definitions.not_meant(code, language),
        synonyms=list(definitions.synonyms(code, language)),
    )


def _population_definition_response(code: str) -> PopulationDefinitionResponse:
    definition = _defined(lambda: definitions.define_population(code))
    return PopulationDefinitionResponse(
        code=definition.code,
        is_family=definition.is_family,
    )


def _reason_definition_response(
    code: str,
    scope: str,
    language: str,
) -> ReasonDefinitionResponse:
    definition = _defined(lambda: definitions.define_reason(code))
    wording = _defined(lambda: definitions.explain_reason(code, language, scope))
    return ReasonDefinitionResponse(
        code=definition.code,
        scopes=list(definition.scopes),
        wording=wording,
    )


def _caveat_definition_response(code: str, language: str) -> CaveatDefinitionResponse:
    definition = _defined(lambda: definitions.define_caveat(code))
    return CaveatDefinitionResponse(
        code=definition.code,
        wording=definitions.explain_caveat(code, language),
    )


def _quality_response(bundle: ReportBundle) -> AnalysisQualityResponse:
    summary = definitions.summarize(bundle)
    return AnalysisQualityResponse(
        answered=summary.answered,
        caveated=summary.caveated,
        refused=summary.refused,
        refusals=[
            SectionOutcome(section_id=entry, reason=reason)
            for entry, reason in summary.refusals
        ],
        refused_results=[
            SectionOutcome(section_id=entry, reason=reason)
            for entry, reason in summary.refused_results
        ],
        caveats=list(summary.caveats),
        answered_sections=list(summary.answered_sections),
        caveated_sections=list(summary.caveated_sections),
    )


def _evidence_response(
    bundle: ReportBundle,
    package: FactPackage,
    citation_id: str,
    language: str,
) -> FactEvidenceResponse:
    """One citation's evidence, from the projection the report surfaces render.

    `build_context(...)["audit"]` is bound and no other key of that context is
    read. That is the whole tier defence: `narrative_state` sits beside it at the
    top level and is Internal, so never reaching for it is what keeps it off this
    surface.

    The package-scope half is assembled separately, because it comes from a
    different place for a stated reason: coverage, filters and reconciliation are
    records the package carries and the audit region never held.
    """
    cells = build_cells(bundle, language)
    audit = build_context(bundle, language, cells)["audit"]
    figures = [cell for cell in audit["figures"] if cell.citation_id == citation_id]
    if not figures:
        raise HTTPException(status_code=404, detail=_NO_CITATION)
    metric = figures[0].metric
    return FactEvidenceResponse(
        citation_id=citation_id,
        metric=metric,
        formula_version=definitions.define_metric(metric).formula_version,
        definition=definitions.describe_metric(metric, language),
        figure_ids=[cell.figure_id for cell in figures],
        sections=[SectionOutcome(**entry) for entry in audit["sections"]],
        caveats=[CaveatStatement(**entry) for entry in audit["caveats"]],
        **_package_evidence(package),
    )


def _package_evidence(package: FactPackage) -> dict[str, object]:
    """The attributes `RRA-011` requires that only the package states.

    Coverage, the admitted filters, and one entry per retained basis. Read from
    the package rather than from the audit region because that is where these
    records live -- the single-projection rule binds the *evidence* projection,
    and package scope is separately required to be read from the package.

    `population` appears here, on a basis, and on no figure: a `Fact` carries
    none, and a package retains several bases with different ones.
    """
    return {
        "coverage_manifest_identity": package.coverage_manifest_identity,
        "coverage_signatures": [
            signature.identity for signature in package.coverage_signatures
        ],
        "event_kind_filters": list(package.event_kind_filters),
        "status_filters": list(package.status_filters),
        "reconciliation": [
            RetainedBasisEvidence(
                name=basis.name,
                population=basis.population,
                event_count=basis.event_count,
                input_digest=basis.input_digest,
                precision=basis.precision,
            )
            for basis in package.retained_bases
        ],
    }


def _defined[Definition](read: Callable[[], Definition]) -> Definition:
    """A governed definition, or the status its refusal maps to.

    Routed through `_refusal_for` rather than catching `UnknownCode` here, so the
    catalog's refusal is mapped in the one table this module maps every other
    governed refusal in. A second `except` beside that table is how the two come
    to disagree about a status.

    Distinct from `_found` only in that a definition lookup raises rather than
    returning `None`: the catalog refuses an unadmitted code and never degrades
    it to a `None` a caller might read as "no such thing yet".
    """
    try:
        return read()
    except Exception as error:
        raise _refusal_for(error) from error


__all__ = [
    "JobIdentifier",
    "ArtifactLanguage",
    "AnalysisQualityResponse",
    "CatalogCode",
    "CaveatDefinitionResponse",
    "FactEvidenceResponse",
    "MetricDefinitionResponse",
    "PopulationDefinitionResponse",
    "ReasonDefinitionResponse",
    "ReportBundleResponse",
    "ReportJobResponse",
    "ReportRequestBody",
    "add_catalog_routes",
    "add_report_routes",
]
