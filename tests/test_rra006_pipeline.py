from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    LANGUAGE_DIRECTION,
    NARRATIVE_INCLUDED,
    REASON_BUNDLE_MISMATCH,
    REASON_FIGURE_NOT_RECONCILED,
    REASON_MISSING_SURFACE,
    REASON_SURFACE_FAILED,
    REQUIRED_SURFACES,
    SURFACE_EXCEL,
    SURFACE_PDF,
    SURFACE_WEB,
    ReportBundle,
    StatedFigure,
    SurfaceContent,
    SurfaceLanguage,
    SurfaceUnavailable,
)
from khepri.rra.facts import FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.jobs import (
    JOB_RUNNING,
    FailureRequest,
    LeaseAction,
    LeaseLost,
    LeaseRequest,
    ReportJob,
)
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    REASON_PROVIDER_REFUSED,
    REASON_PROVIDER_TIMEOUT,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeRequest,
    NarrativeSection,
    ProviderRefused,
)
from khepri.rra.pipeline import (
    GOVERNED_REASONS,
    REASON_PACKAGE_MISSING,
    DeliveryRecord,
    ReportDelivery,
    ReportPipeline,
    ReportPipelineFailed,
    ReportPipelinePorts,
    ReportPublication,
)
from khepri.rra.profiling import build_profile
from khepri.rra.report_artifacts import (
    HTML_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    REQUIRED_ARTIFACT_KINDS,
    SURFACE_ARTIFACT_KINDS,
    XLSX_MEDIA_TYPE,
    ArtifactPayload,
    MaterializedSurface,
)
from khepri.rra.worker import ReportExecutionFailed, ReportJobMessage, ReportWorker, WorkerPolicy

NOW = datetime(2026, 7, 30, 16, 0, tzinfo=UTC)
ADAPTER_VERSION = "test.adapter.v1"

# The size a stand-in renderer reports for a payload it never produced. Nothing
# here writes a file, so the number only has to be one a renderer could have
# measured; tests that care which surface it came from choose their own.
SURFACE_SIZE = 1024

GOLDEN = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)


def package(content: bytes = GOLDEN) -> FactPackage:
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )


def job(job_id: str = "job_alpha") -> ReportJob:
    return ReportJob(
        job_id=job_id,
        owner_id="own_alpha",
        session_id="ses_alpha",
        idempotency_key="a" * 64,
        state=JOB_RUNNING,
        queued_at=NOW,
        available_at=NOW,
        attempt_count=1,
        max_attempts=3,
        lease_owner="worker_alpha",
        lease_expires_at=NOW + timedelta(minutes=5),
        completed_at=None,
        dead_letter_reason=None,
    )


# --- fakes ----------------------------------------------------------------


class Packages:
    """A fact package source. Hands back one package, or none at all."""

    def __init__(self, supplied: FactPackage | None) -> None:
        self._supplied = supplied
        self.asked: list[str] = []

    def load(self, leased: ReportJob) -> FactPackage | None:
        self.asked.append(leased.job_id)
        return self._supplied


class Adapter:
    """A provider that cites the revenue fact it was actually given."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error
        self.calls = 0

    @property
    def adapter_version(self) -> str:
        return ADAPTER_VERSION

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft:
        self.calls += 1
        if self._error is not None:
            raise self._error
        fact_id = next(
            str(entry["fact_id"])
            for entry in request.document["facts"]
            if entry["metric"] == "revenue"
        )
        return NarrativeDraft(
            adapter_version=ADAPTER_VERSION,
            request_digest=request.digest,
            languages=(
                LanguageNarrative(
                    language=LANGUAGE_ARABIC,
                    sections=(
                        NarrativeSection(
                            section_id="summary",
                            text="بلغت الإيرادات ٥٠٠٫٠٠.",
                            cited_fact_ids=(fact_id,),
                            caveats=(),
                        ),
                    ),
                ),
                LanguageNarrative(
                    language=LANGUAGE_ENGLISH,
                    sections=(
                        NarrativeSection(
                            section_id="summary",
                            text="Revenue was 500.00.",
                            cited_fact_ids=(fact_id,),
                            caveats=(),
                        ),
                    ),
                ),
            ),
        )


def surface_of(
    bundle: ReportBundle,
    surface: str,
    *,
    bundle_id: str | None = None,
    output_size_bytes: int = SURFACE_SIZE,
) -> SurfaceContent:
    return SurfaceContent(
        surface=surface,
        bundle_id=bundle.bundle_id if bundle_id is None else bundle_id,
        output_size_bytes=output_size_bytes,
        languages=tuple(
            SurfaceLanguage(
                language=language,
                direction=LANGUAGE_DIRECTION[language],
                sections=bundle.section_ids,
                stated=tuple(
                    StatedFigure(
                        figure_id=entry.figure_id,
                        text=entry.renderings[language],
                        section=entry.section,
                    )
                    for entry in bundle.figures
                ),
                caveats=bundle.caveats,
                disclosure=bundle.disclosure(language),
            )
            for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
        ),
    )


class Renderer:
    """A faithful renderer, which counts how often it was asked to work.

    The size it reports is chosen by whoever builds it, so a test can tell one
    surface's payload from another's.
    """

    def __init__(self, surface: str, *, output_size_bytes: int = SURFACE_SIZE) -> None:
        self._surface = surface
        self._size = output_size_bytes
        self.calls = 0

    @property
    def surface(self) -> str:
        return self._surface

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        self.calls += 1
        return surface_of(bundle, self._surface, output_size_bytes=self._size)

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface:
        content = self.render(bundle)
        kinds = SURFACE_ARTIFACT_KINDS[self.surface]
        remaining = self._size - len(kinds) + 1
        artifacts = tuple(
            _payload(kind, content=b"x" if index < len(kinds) - 1 else b"x" * remaining)
            for index, kind in enumerate(kinds)
        )
        return MaterializedSurface(content=content, artifacts=artifacts)


class ArtifactRenderer:
    """A real publication renderer: bytes beside a content-free claim."""

    def __init__(self, surface: str) -> None:
        self._surface = surface

    @property
    def surface(self) -> str:
        return self._surface

    def render_materialized(self, bundle: ReportBundle) -> MaterializedSurface:
        artifacts = tuple(_payload(kind) for kind in SURFACE_ARTIFACT_KINDS[self.surface])
        return MaterializedSurface(
            content=surface_of(
                bundle,
                self.surface,
                output_size_bytes=sum(len(item.content) for item in artifacts),
            ),
            artifacts=artifacts,
        )


def _payload(kind: str, *, content: bytes | None = None) -> ArtifactPayload:
    if kind.startswith("web_"):
        media_type, file_name = HTML_MEDIA_TYPE, "khepri-report.html"
        if "evidence" in kind:
            file_name = "khepri-evidence.html"
    elif kind.startswith("pdf_"):
        media_type, file_name = PDF_MEDIA_TYPE, "khepri-report.pdf"
    else:
        media_type, file_name = XLSX_MEDIA_TYPE, "khepri-report.xlsx"
    return ArtifactPayload.of(
        kind=kind,
        media_type=media_type,
        file_name=file_name,
        content=content or f"artifact:{kind}".encode(),
    )


class Publications:
    def __init__(self) -> None:
        self.records: dict[str, DeliveryRecord] = {}
        self.published: list[ReportPublication] = []

    def find_delivery(self, job_id: str) -> DeliveryRecord | None:
        return self.records.get(job_id)

    def publish(self, publication: ReportPublication) -> DeliveryRecord:
        self.published.append(publication)
        record = publication.delivery.record
        self.records[record.job_id] = record
        return record


class BrokenRenderer(Renderer):
    def render(self, bundle: ReportBundle) -> SurfaceContent:
        self.calls += 1
        raise SurfaceUnavailable("Cairo branch workbook could not be written")


class StaleRenderer(Renderer):
    """A surface built for some other bundle."""

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        self.calls += 1
        return surface_of(bundle, self._surface, bundle_id="0" * 64)


class DriftingRenderer(Renderer):
    """A surface that rounded a figure the bundle had already rendered."""

    def render(self, bundle: ReportBundle) -> SurfaceContent:
        self.calls += 1
        content = surface_of(bundle, self._surface)
        first = content.languages[0]
        return SurfaceContent(
            surface=content.surface,
            bundle_id=content.bundle_id,
            output_size_bytes=content.output_size_bytes,
            languages=(
                SurfaceLanguage(
                    language=first.language,
                    direction=first.direction,
                    sections=bundle.section_ids,
                    stated=(
                        StatedFigure(
                            figure_id=first.stated[0].figure_id,
                            text="1",
                            section=first.stated[0].section,
                        ),
                        *first.stated[1:],
                    ),
                    caveats=first.caveats,
                    disclosure=first.disclosure,
                ),
                *content.languages[1:],
            ),
        )


def delivery_record() -> DeliveryRecord:
    """A well-formed record. Tests bend one field of it with `replace`."""
    return DeliveryRecord(
        job_id="job_alpha",
        session_id="ses_alpha",
        bundle_id="a" * 64,
        package_version="rra004.package.v1",
        narrative_state=NARRATIVE_INCLUDED,
        surfaces=REQUIRED_SURFACES,
    )


def renderers_but(failing: Renderer) -> tuple[Renderer, ...]:
    """Every surface rendered faithfully, except the one a test broke."""
    return tuple(
        failing if name == failing.surface else Renderer(name) for name in REQUIRED_SURFACES
    )


class Deliveries:
    """A delivery store, remembering one record per job."""

    def __init__(self) -> None:
        self.records: dict[str, DeliveryRecord] = {}
        self.delivered: list[ReportDelivery] = []

    def find_delivery(self, job_id: str) -> DeliveryRecord | None:
        return self.records.get(job_id)

    def publish(self, publication: ReportPublication) -> DeliveryRecord:
        delivery = publication.delivery
        self.delivered.append(delivery)
        self.records[delivery.record.job_id] = delivery.record
        return delivery.record


class Execution:
    """A leased execution whose heartbeat may lose the lease on any beat."""

    def __init__(self, leased: ReportJob | None = None, *, lose_on: int | None = None) -> None:
        self.job = leased or job()
        self.beats = 0
        self._lose_on = lose_on

    def heartbeat(self) -> ReportJob:
        self.beats += 1
        if self._lose_on is not None and self.beats == self._lose_on:
            raise LeaseLost("The lease was taken by another worker.")
        return self.job


@dataclass
class Harness:
    pipeline: ReportPipeline
    packages: Packages
    adapter: Adapter
    renderers: tuple[Renderer, ...]
    deliveries: Deliveries


def harness(
    *,
    packages: Packages | None = None,
    adapter: Adapter | None = None,
    renderers: tuple[Renderer, ...] | None = None,
    deliveries: Deliveries | None = None,
) -> Harness:
    source = packages if packages is not None else Packages(package())
    provider = adapter or Adapter()
    surfaces = renderers or tuple(Renderer(name) for name in REQUIRED_SURFACES)
    store = deliveries or Deliveries()
    return Harness(
        pipeline=ReportPipeline(
            ports=ReportPipelinePorts(
                packages=source,
                adapter=provider,
                renderers=surfaces,
                deliveries=store,
            ),
            monotonic_ms=lambda: 0,
        ),
        packages=source,
        adapter=provider,
        renderers=surfaces,
        deliveries=store,
    )


# --- the whole pipeline ----------------------------------------------------


def test_one_run_publishes_one_reconciled_seven_artifact_set() -> None:
    sink = Publications()
    pipeline = ReportPipeline(
        ports=ReportPipelinePorts(
            packages=Packages(package()),
            adapter=Adapter(),
            renderers=tuple(ArtifactRenderer(name) for name in REQUIRED_SURFACES),
            deliveries=sink,
        ),
        monotonic_ms=lambda: 0,
    )

    outcome = pipeline.run(Execution())

    publication = sink.published[0]
    assert publication.delivery.record == outcome.record
    assert tuple(item.kind for item in publication.artifacts) == REQUIRED_ARTIFACT_KINDS


def test_one_run_delivers_every_surface_of_one_fact_package() -> None:
    built = harness()

    outcome = built.pipeline.run(Execution())

    assert outcome.delivered is True
    assert outcome.record.surfaces == REQUIRED_SURFACES
    assert outcome.record.narrative_state == NARRATIVE_INCLUDED
    assert [entry.surface for entry in built.deliveries.delivered[0].surfaces] == list(
        REQUIRED_SURFACES
    )


def test_every_delivered_surface_names_the_bundle_it_was_built_for() -> None:
    # RRA-006 excludes independent surface calculations, and DEC-005 requires
    # every surface to reconcile to one fact package before delivery. What
    # reaches the store is therefore one bundle and three echoes of its name.
    built = harness()

    outcome = built.pipeline.run(Execution())

    delivery = built.deliveries.delivered[0]
    assert outcome.record.bundle_id == delivery.bundle.bundle_id
    assert {entry.bundle_id for entry in delivery.surfaces} == {delivery.bundle.bundle_id}


def test_the_stages_run_in_order_over_one_package() -> None:
    built = harness()

    built.pipeline.run(Execution())

    assert built.packages.asked == ["job_alpha"]
    assert built.adapter.calls == 1
    assert [renderer.calls for renderer in built.renderers] == [1, 1, 1]


def test_nothing_about_when_a_run_happened_reaches_the_delivered_bundle() -> None:
    # Two runs against fresh stores must agree on the bundle name, or the
    # deterministic regeneration RRA-006 requires is impossible: it would mean
    # this module injected a timestamp or an identifier of its own.
    first = harness().pipeline.run(Execution())
    second = harness().pipeline.run(Execution())

    assert first.record.bundle_id == second.record.bundle_id


# --- leases ---------------------------------------------------------------


def test_a_heartbeat_separates_every_stage_boundary() -> None:
    built = harness()
    execution = Execution()

    built.pipeline.run(execution)

    # Four stages, so three boundaries between them. A stage that renders a
    # PDF or a workbook may outlast a lease, and a lease renewed only once
    # would leave the later stages running unleased.
    assert execution.beats == 3


@pytest.mark.parametrize("boundary", [1, 2, 3])
def test_a_lost_lease_propagates_from_every_boundary(boundary: int) -> None:
    # LeaseLost is what tells a worker that another worker owns this job. A
    # stage that caught it would convert the one condition that must abandon
    # the run into an ordinary failure, and two workers would deliver.
    built = harness()

    with pytest.raises(LeaseLost):
        built.pipeline.run(Execution(lose_on=boundary))

    assert built.deliveries.delivered == []


# --- failing closed -------------------------------------------------------


def test_a_missing_fact_package_delivers_nothing() -> None:
    built = harness(packages=Packages(None))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline.run(Execution())

    assert raised.value.reason == REASON_PACKAGE_MISSING
    assert built.adapter.calls == 0
    assert built.deliveries.delivered == []


def test_a_refused_narrative_delivers_nothing() -> None:
    built = harness(adapter=Adapter(error=ProviderRefused("no")))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline.run(Execution())

    assert raised.value.reason == REASON_PROVIDER_REFUSED
    assert [renderer.calls for renderer in built.renderers] == [0, 0, 0]
    assert built.deliveries.delivered == []


@pytest.mark.parametrize(
    ("failing", "surface", "reason"),
    [
        pytest.param(
            BrokenRenderer,
            SURFACE_PDF,
            REASON_SURFACE_FAILED,
            id="a_renderer_that_raised",
        ),
        pytest.param(
            StaleRenderer,
            SURFACE_EXCEL,
            REASON_BUNDLE_MISMATCH,
            id="a_surface_built_for_another_bundle",
        ),
        pytest.param(
            DriftingRenderer,
            SURFACE_PDF,
            REASON_FIGURE_NOT_RECONCILED,
            id="a_surface_that_restated_a_figure",
        ),
    ],
)
def test_a_surface_that_cannot_be_trusted_delivers_nothing(
    failing: type[Renderer],
    surface: str,
    reason: str,
) -> None:
    # RRA-006 calls a partial export an incomplete bundle, so one untrustworthy
    # surface discards the whole attempt rather than itself — whether it failed
    # outright, was built for another bundle, or restated a governed figure.
    built = harness(renderers=renderers_but(failing(surface)))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline.run(Execution())

    assert raised.value.reason == reason
    assert built.deliveries.delivered == []


def test_a_missing_surface_delivers_nothing() -> None:
    built = harness(renderers=(Renderer(SURFACE_WEB), Renderer(SURFACE_PDF)))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline.run(Execution())

    assert raised.value.reason == REASON_MISSING_SURFACE
    assert built.deliveries.delivered == []


def test_a_refusal_records_a_governed_reason_and_nothing_a_renderer_wrote() -> None:
    # The reason travels into operational evidence documented as content-free,
    # so it is a code from a closed vocabulary rather than whatever text a
    # renderer or a provider happened to raise.
    built = harness(renderers=renderers_but(BrokenRenderer(SURFACE_PDF)))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline.run(Execution())

    assert raised.value.reason in GOVERNED_REASONS
    assert "Cairo" not in str(raised.value)


def test_an_ungoverned_reason_is_recorded_coarsely() -> None:
    assert ReportPipelineFailed("customer Cairo record 12345").reason in GOVERNED_REASONS


# --- idempotency ----------------------------------------------------------


def test_rerunning_a_delivered_job_does_not_deliver_it_twice() -> None:
    built = harness()
    first = built.pipeline.run(Execution())

    second = built.pipeline.run(Execution())

    assert second.delivered is False
    assert second.record == first.record
    assert len(built.deliveries.delivered) == 1


def test_rerunning_a_delivered_job_repeats_no_stage() -> None:
    built = harness()
    built.pipeline.run(Execution())

    built.pipeline.run(Execution())

    assert built.packages.asked == ["job_alpha"]
    assert built.adapter.calls == 1
    assert [renderer.calls for renderer in built.renderers] == [1, 1, 1]


def test_another_job_is_delivered_on_its_own() -> None:
    built = harness()
    built.pipeline.run(Execution())

    outcome = built.pipeline.run(Execution(job("job_beta")))

    assert outcome.delivered is True
    assert sorted(built.deliveries.records) == ["job_alpha", "job_beta"]


# --- the record the store is handed ---------------------------------------


def test_a_delivered_report_names_the_session_it_belongs_to() -> None:
    # RRA-006 stores published outputs under the same session expiry and
    # deletion boundary as the input, and RRA-007 correlates evidence with the
    # opaque session identifier. A record naming only the job would leave a
    # store unable to apply either without a second lookup.
    built = harness()

    outcome = built.pipeline.run(Execution())

    assert outcome.record.session_id == "ses_alpha"
    assert outcome.record.as_document()["session_id"] == "ses_alpha"


@pytest.mark.parametrize(
    ("malformed", "message"),
    [
        pytest.param(
            lambda: replace(delivery_record(), job_id=""),
            "job_id",
            id="an_unnamed_job",
        ),
        pytest.param(
            lambda: replace(delivery_record(), session_id=""),
            "session_id",
            id="an_unnamed_session",
        ),
        pytest.param(
            lambda: replace(delivery_record(), surfaces=(SURFACE_WEB, SURFACE_PDF)),
            "required surface",
            id="a_partial_set_of_surfaces",
        ),
    ],
)
def test_a_delivery_record_refuses_evidence_it_cannot_stand_behind(
    malformed: Callable[[], DeliveryRecord],
    message: str,
) -> None:
    # The record is what a store writes and what operational evidence is
    # correlated by, so a missing identifier or a partial export is refused at
    # construction rather than written and reasoned about later.
    with pytest.raises(ValueError, match=message):
        malformed()


def test_a_delivery_refuses_a_surface_built_for_another_bundle() -> None:
    bundle = ReportBundle.of(package())
    record = replace(
        delivery_record(),
        bundle_id=bundle.bundle_id,
        package_version=bundle.identity.package_version,
        narrative_state=bundle.narrative_state,
    )

    with pytest.raises(ValueError, match="another bundle"):
        ReportDelivery(
            record=record,
            bundle=bundle,
            surfaces=(
                surface_of(bundle, SURFACE_WEB),
                surface_of(bundle, SURFACE_PDF),
                surface_of(bundle, SURFACE_EXCEL, bundle_id="0" * 64),
            ),
        )


# --- the handler the worker was waiting for --------------------------------


class Jobs:
    """The job state a worker leases through, in memory."""

    def __init__(self, leased: ReportJob) -> None:
        self.job = leased
        self.completed: list[str] = []
        self.failed: list[str] = []

    def lease(self, request: LeaseRequest) -> ReportJob | None:
        return self.job if request.job_id == self.job.job_id else None

    def heartbeat(self, request: LeaseRequest) -> ReportJob:
        return self.job

    def complete(self, request: LeaseAction) -> ReportJob:
        self.completed.append(request.job_id)
        return self.job

    def fail(self, request: FailureRequest) -> ReportJob:
        self.failed.append(request.lease.job_id)
        return self.job


def worker(pipeline: ReportPipeline, jobs: Jobs) -> ReportWorker:
    return ReportWorker(
        jobs=jobs,
        handler=pipeline,
        clock=lambda: NOW,
        policy=WorkerPolicy(
            worker_id="worker_alpha",
            lease_for=timedelta(minutes=5),
            retry_delay=timedelta(minutes=1),
        ),
    )


def test_the_pipeline_is_the_handler_the_worker_expects() -> None:
    built = harness()
    jobs = Jobs(job())

    worker(built.pipeline, jobs).process(ReportJobMessage(job_id="job_alpha"))

    assert jobs.completed == ["job_alpha"]
    assert jobs.failed == []
    assert len(built.deliveries.delivered) == 1


def test_a_failing_stage_reaches_the_worker_as_a_failed_execution() -> None:
    built = harness(packages=Packages(None))
    jobs = Jobs(job())

    with pytest.raises(ReportExecutionFailed):
        worker(built.pipeline, jobs).process(ReportJobMessage(job_id="job_alpha"))

    assert jobs.completed == []
    assert jobs.failed == ["job_alpha"]


def test_a_lost_lease_reaches_the_worker_as_a_lost_lease() -> None:
    # The worker re-raises LeaseLost rather than recording a failure, so a
    # pipeline that swallowed it would have this job retried by a worker that
    # no longer owns it.
    built = harness()

    class Losing(Jobs):
        def heartbeat(self, request: LeaseRequest) -> ReportJob:
            raise LeaseLost("The lease was taken by another worker.")

    jobs = Losing(job())

    with pytest.raises(LeaseLost):
        worker(built.pipeline, jobs).process(ReportJobMessage(job_id="job_alpha"))

    assert jobs.failed == []
    assert built.deliveries.delivered == []


def test_the_narrative_stage_reports_why_the_provider_did_not_answer() -> None:
    # A timeout and a refusal are different operational facts, and the reason
    # the narrative service already determined is carried rather than flattened
    # into one pipeline-level failure.
    built = harness(adapter=Adapter(error=TimeoutError("provider took too long")))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline.run(Execution())

    assert raised.value.reason == REASON_PROVIDER_TIMEOUT
    assert built.deliveries.delivered == []
