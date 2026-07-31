"""Measure every report stage boundary, from outside the stage.

**Why this is a subclass rather than a rewrite.** `pipeline` publishes
`load_package`, `compose_narrative`, `assemble`, and `deliver` as separately
callable methods precisely so a later change could time each boundary without
reaching inside a long method, and `ReportPipeline.run` dispatches through
`self`. Overriding those four therefore instruments every boundary while the
*order* of the stages, the heartbeat between each pair, and the
already-delivered short-circuit stay in the code that owns them. Nothing here
decides what a report is or when a stage runs; it decides only what was
measured.

**`LeaseLost` is not a stage failure.** A lost lease means another worker owns
this job, and the run must abandon it rather than record it. Every measured
boundary re-raises `LeaseLost` before any other handler sees it, so no event
claims a stage failed because a lease moved. Heartbeats stay where `pipeline`
put them — strictly between stages, in the inherited `run` — which is also why
a lost lease can only arrive when no stage is in flight.

**Why the injected renderers are still deliberately *not* wrapped.**
`chart_rendering`, `pdf_generation`, and `excel_generation` are three stages in
the RRA-007 vocabulary and one boundary here, because `BundleAssembler` owns the
render loop. Timing them individually would mean wrapping each renderer, which
would put a telemetry write inside the assembler's `except Exception` — and a
failed write would then be recorded as `surface_failed`, a telemetry fault
disguised as a bundle refusal. That is exactly the silent corruption this module
must not introduce, so the whole boundary is measured once.

Renderers now report the *size* of what they produced, which is why
`output_size_bytes` is recordable below. It is not why the split can happen. A
size arrives on `SurfaceContent`, on the assembler's return, after every
`except` clause has been passed; a duration would have to be read on both sides
of a call the assembler makes, and `OperationalEvent` refuses a terminal
transition with no duration at all. The remaining route — letting the assembler
time each renderer and report the readings back — would produce per-surface
events only for surfaces that *succeeded*, since a refused assembly returns no
readings. `pdf_generation` would then never carry `failed`, and every PDF
failure would still be recorded as this boundary refusing. Evidence that exists
only when nothing went wrong is worse than a stage honestly named unreached, so
both stay in `UNREACHED_STAGES` until a renderer reports its own timing.

**Telemetry fails closed.** A write that fails raises, the stage abandons, and
the worker fails the job. An unrecorded run is missing evidence, and the
constitution blocks on missing evidence rather than proceeding quietly. This is
affordable because `run` asks the store whether this job was already delivered
before running any stage: a retry after a telemetry failure re-runs the stages
without building or delivering a second report. The residual gap is honest and
narrow — a terminal write that fails *after* `deliver` succeeded leaves that
attempt's last event permanently unwritten, because the retry short-circuits and
runs no stage. Failing closed protects the report, not the completeness of the
evidence.

**What is measured, and what cannot be.** Duration is measured at every
boundary. Queue time is measured once, at the first boundary, because it is a
property of the job's wait rather than of each stage; on a retry it is measured
from the original enqueue and so includes the backoff. Provider latency is
measured by wrapping the narrative adapter, which is the only honest source for
it. Output size is recorded at the rendering boundary and nowhere else: every
surface reports how many bytes it produced, and this adds them up once, where
they were produced. `delivery` hands on those same bytes, so recording a size
there too would be one payload counted twice by anything aggregating them.

`dataset_size_band` is still never recorded. The source size is known at intake
and is not carried into a fact package, and a band derived from anything else —
the report's own weight, a row count — would be evidence about something other
than the dataset.

**Correlation, without content.** The events carry the opaque session and job
identifiers, the fact package's content address, the bundle's, and a count of
bytes. The package
is named by `FactPackage.digest` because that is the only identifier the
`FactPackageSource` port returns, and it is the same digest the store records as
`package_digest`, so the correlation joins. No filename, label, source value,
sentence, fact, invitation, token, or object location can reach an
`OperationalEvent`: it has no field one would fit in, and this module passes it
none.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal

from khepri.rra.bundle import SurfaceContent
from khepri.rra.facts import FactPackage
from khepri.rra.jobs import LeaseLost, ReportJob
from khepri.rra.narrative import NarrativeAdapter, NarrativeDraft, NarrativeRequest
from khepri.rra.pipeline import (
    DeliveryRecord,
    PipelineOutcome,
    ReportDelivery,
    ReportPipeline,
    ReportPipelineFailed,
    ReportPipelinePorts,
)
from khepri.rra.sessions import SessionScope
from khepri.rra.telemetry import (
    TRANSITION_FAILED,
    TRANSITION_REFUSED,
    TRANSITION_SUCCEEDED,
)
from khepri.rra.telemetry_service import (
    OperationalTelemetryService,
    StageCompletion,
    StageMeasurement,
)
from khepri.rra.worker import WorkerExecution

# The RRA-007 stage each pipeline boundary is recorded as.
#
# `fact_calculation` names the boundary the report's facts arrive at. The
# package was calculated and published on the intake path, so this duration is a
# read rather than a computation, and it is still the only stage in the governed
# vocabulary that names facts.
STAGE_PACKAGE = "fact_calculation"
STAGE_NARRATIVE = "narrative_generation"
# One boundary, three vocabulary stages. See the module docstring for why it is
# still not split: the renderers report their size, and splitting needs
# renderers that report their own timing.
STAGE_BUNDLE = "chart_rendering"
# The whole report handed to the store as one unit. `storage` is reserved for a
# store that writes surface bytes, which nothing does yet.
STAGE_DELIVERY = "delivery"

RECORDED_STAGES = (STAGE_PACKAGE, STAGE_NARRATIVE, STAGE_BUNDLE, STAGE_DELIVERY)

# Named rather than left out, so a stage cannot be forgotten silently. The first
# four belong to intake and profiling, which run before a report job exists.
# `pdf_generation` and `excel_generation` are measurable in size but not in
# duration, which is not enough for an event — see the module docstring.
# `storage` waits for a store that writes surface bytes.
UNREACHED_STAGES = frozenset(
    {
        "upload_validation",
        "materialization",
        "profiling",
        "mapping",
        "pdf_generation",
        "excel_generation",
        "storage",
    }
)


class StageNotMeasurable(RuntimeError):
    """A stage was called outside a run, so there is no attempt to correlate to."""


@dataclass(frozen=True, slots=True)
class StageRecorder:
    """How a boundary is recorded: with this service, timed by this clock.

    A pair rather than two arguments, so the ports a deployment chooses stay in
    `ReportPipelinePorts` and are not restated here. The two belong together:
    neither a recorder with no clock nor a clock with nothing to record is a way
    to measure anything.

    The clock is injected rather than read from `time`, and it must not run
    backwards — the recorder refuses timestamps that are out of order, which is
    the answer a measurement wants.
    """

    telemetry: OperationalTelemetryService
    clock: Callable[[], datetime]


@dataclass(frozen=True, slots=True)
class _RunContext:
    """What every event of one attempt correlates to.

    Every field is an opaque identifier, a content address, a positive attempt
    number, or the moment the job was enqueued. Nothing a label, a sentence, or
    a location could occupy.
    """

    scope: SessionScope
    job_id: str
    attempt_number: int
    queued_at: datetime
    fact_package_id: str | None = None
    report_bundle_id: str | None = None
    rendered_size_bytes: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.job_id, "job_id")
        _require_attempt(self.attempt_number)

    @classmethod
    def of(cls, job: ReportJob) -> _RunContext:
        return cls(
            scope=SessionScope(owner_id=job.owner_id, session_id=job.session_id),
            job_id=job.job_id,
            attempt_number=job.attempt_count,
            queued_at=job.queued_at,
        )


class _TimedNarrativeAdapter:
    """The provider adapter, timed from just outside itself.

    A stage duration is not a provider latency: the narrative boundary also
    builds the request and grounds the answer. Recording the stage as the
    provider's would credit the provider with work it did not do, so the call
    itself is timed here. The reading still runs to the end of the stage rather
    than to this method's return, which makes it an upper bound that includes
    validation — a bound measured at the call is the closest one available from
    outside `NarrativeService`.

    Everything else is passed straight through, including exceptions from
    `adapter_version`: a provider that cannot say which build it is must still
    reach `NarrativeService` as the refusal it already is.
    """

    def __init__(
        self,
        *,
        adapter: NarrativeAdapter,
        clock: Callable[[], datetime],
    ) -> None:
        self._adapter = adapter
        self._clock = clock
        self._called_at: datetime | None = None

    @property
    def adapter_version(self) -> str:
        return self._adapter.adapter_version

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft:
        self._called_at = self._clock()
        return self._adapter.draft(request, timeout_seconds=timeout_seconds)

    @property
    def called_at(self) -> datetime | None:
        return self._called_at

    def forget(self) -> None:
        """Discard the last reading, so no stage inherits another's latency."""
        self._called_at = None


class InstrumentedReportPipeline(ReportPipeline):
    """The report pipeline, with every stage boundary measured.

    Callable and substitutable wherever `ReportPipeline` is, because it is one:
    the stages, their order, and the deliveries are inherited unchanged.
    """

    def __init__(
        self,
        *,
        ports: ReportPipelinePorts,
        monotonic_ms: Callable[[], int],
        recorder: StageRecorder,
    ) -> None:
        # The adapter is wrapped before the pipeline is built, so
        # `NarrativeService` calls the timed one and nothing downstream knows the
        # difference. Swapped on the port set rather than unpacked and rebuilt:
        # a port this module listed field by field would be a port it could
        # silently drop when `pipeline` adds one.
        self._provider = _TimedNarrativeAdapter(adapter=ports.adapter, clock=recorder.clock)
        super().__init__(
            ports=replace(ports, adapter=self._provider),
            monotonic_ms=monotonic_ms,
        )
        self._telemetry = recorder.telemetry
        self._clock = recorder.clock
        self._context: _RunContext | None = None

    def run(self, execution: WorkerExecution) -> PipelineOutcome:
        """One attempt, measured. The stage order is the inherited one.

        The context is held for the length of one run because the stage
        signatures carry a job, a package, or a delivery rather than an
        attempt. One worker runs one leased job at a time, and the context is
        discarded whichever way the run ends.
        """
        self._context = _RunContext.of(execution.job)
        try:
            return super().run(execution)
        finally:
            self._context = None

    def load_package(self, job: ReportJob) -> FactPackage:
        loaded = super().load_package
        return self._measure(
            STAGE_PACKAGE,
            lambda: loaded(job),
            queued=True,
            learn=_learn_package,
        )

    def compose_narrative(self, package: FactPackage) -> NarrativeDraft:
        composed = super().compose_narrative
        return self._measure(STAGE_NARRATIVE, lambda: composed(package))

    def assemble(
        self,
        job: ReportJob,
        package: FactPackage,
        narrative: NarrativeDraft,
    ) -> ReportDelivery:
        assembled = super().assemble
        return self._measure(
            STAGE_BUNDLE,
            lambda: assembled(job, package, narrative),
            learn=_learn_bundle,
        )

    def deliver(self, delivery: ReportDelivery) -> DeliveryRecord:
        delivered = super().deliver
        return self._measure(STAGE_DELIVERY, lambda: delivered(delivery))

    def _measure[T](
        self,
        stage: str,
        work: Callable[[], T],
        *,
        queued: bool = False,
        learn: Callable[[_RunContext, T], _RunContext] | None = None,
    ) -> T:
        """One boundary: a started transition, the stage, a terminal transition."""
        measurement = self._begin(stage, queued=queued)
        try:
            result = work()
        except LeaseLost:
            # Another worker owns this job. Not a stage failure, and not this
            # module's to record — see the module docstring.
            raise
        except ReportPipelineFailed:
            # A governed refusal. The reason is not recorded because an
            # operational event has nowhere to put one, which is the point.
            self._finish(measurement, TRANSITION_REFUSED)
            raise
        except Exception:
            self._finish(measurement, TRANSITION_FAILED)
            raise
        if learn is not None:
            self._context = learn(self._require_context(), result)
        self._finish(self._correlated(measurement), TRANSITION_SUCCEEDED)
        return result

    def _begin(self, stage: str, *, queued: bool) -> StageMeasurement:
        context = self._require_context()
        if stage == STAGE_NARRATIVE:
            self._provider.forget()
        measurement = StageMeasurement(
            scope=context.scope,
            job_id=context.job_id,
            stage=stage,
            attempt_number=context.attempt_number,
            started_at=self._clock(),
            queued_at=context.queued_at if queued else None,
            fact_package_id=context.fact_package_id,
            report_bundle_id=context.report_bundle_id,
        )
        self._telemetry.start(measurement)
        return measurement

    def _finish(self, measurement: StageMeasurement, transition: str) -> None:
        self._telemetry.finish(
            measurement,
            StageCompletion(
                transition=transition,
                completed_at=self._clock(),
                provider_started_at=self._provider_started(measurement.stage),
                output_size_bytes=self._rendered_size(measurement.stage),
            ),
        )

    def _provider_started(self, stage: str) -> datetime | None:
        if stage != STAGE_NARRATIVE:
            # The recorder refuses provider latency anywhere else, and it is
            # right to: no other stage calls a provider.
            return None
        return self._provider.called_at

    def _rendered_size(self, stage: str) -> int | None:
        """How large the surfaces were, for the one stage that produced them.

        Only this boundary, for the same reason provider latency belongs to only
        one: `delivery` hands on the very bytes this stage produced, and a size
        recorded at both would be the same payload counted twice by anything
        that adds them up.

        Nothing to return unless the stage delivered, because the size is
        learned from the delivery. A boundary that refused or broke leaves the
        context without one, which is the honest reading: no surface exists.
        """
        if stage != STAGE_BUNDLE:
            return None
        return self._require_context().rendered_size_bytes

    def _correlated(self, measurement: StageMeasurement) -> StageMeasurement:
        """The same measurement, naming what the stage has since identified.

        A started transition cannot name a package the stage has not loaded or a
        bundle it has not built, so the terminal transition names them instead.
        """
        context = self._require_context()
        return replace(
            measurement,
            fact_package_id=context.fact_package_id,
            report_bundle_id=context.report_bundle_id,
        )

    def _require_context(self) -> _RunContext:
        if self._context is None:
            raise StageNotMeasurable("A report stage was measured outside a run.")
        return self._context


def _learn_package(context: _RunContext, package: FactPackage) -> _RunContext:
    """Name the package by the content address its store keys it by."""
    return replace(context, fact_package_id=package.digest)


def _learn_bundle(context: _RunContext, delivery: ReportDelivery) -> _RunContext:
    """Name the bundle, and how many bytes its surfaces came to.

    Read from the delivery *after* the assembler returned it, never from inside
    the render loop. See the module docstring: a reading taken in there would
    have to be taken by something the assembler's `except Exception` can catch.
    """
    return replace(
        context,
        report_bundle_id=delivery.bundle.bundle_id,
        rendered_size_bytes=_rendered_bytes(delivery.surfaces),
    )


def _rendered_bytes(surfaces: tuple[SurfaceContent, ...]) -> int:
    """Every surface's payload, added up. Sizes only; no payload is in reach."""
    return sum(entry.output_size_bytes for entry in surfaces)


def _require_text(value: str, name: str) -> None:
    if not value:
        raise ValueError(f"{name} is required.")


def _require_attempt(value: int) -> None:
    if value <= 0:
        raise ValueError("A leased job has at least one attempt.")


__all__ = [
    "RECORDED_STAGES",
    "STAGE_BUNDLE",
    "STAGE_DELIVERY",
    "STAGE_NARRATIVE",
    "STAGE_PACKAGE",
    "UNREACHED_STAGES",
    "InstrumentedReportPipeline",
    "StageNotMeasurable",
    "StageRecorder",
]
