from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import count

import pytest

from khepri.rra.bundle import SURFACE_EXCEL, SURFACE_PDF, SURFACE_WEB
from khepri.rra.facts import FactPackage
from khepri.rra.jobs import LeaseLost, ReportJob
from khepri.rra.narrative import (
    REASON_PROVIDER_FAILED,
    REASON_PROVIDER_REFUSED,
    NarrativeDraft,
    NarrativeRequest,
    ProviderRefused,
)
from khepri.rra.pipeline import (
    REASON_PACKAGE_MISSING,
    DeliveryRecord,
    PipelineOutcome,
    ReportPipeline,
    ReportPipelineFailed,
    ReportPipelinePorts,
    ReportPublication,
)
from khepri.rra.sessions import SessionScope
from khepri.rra.stage_telemetry import (
    RECORDED_STAGES,
    STAGE_BUNDLE,
    STAGE_DELIVERY,
    STAGE_NARRATIVE,
    STAGE_PACKAGE,
    UNREACHED_STAGES,
    InstrumentedReportPipeline,
    StageNotMeasurable,
    StageRecorder,
)
from khepri.rra.telemetry import (
    STAGES,
    TRANSITION_FAILED,
    TRANSITION_REFUSED,
    TRANSITION_STARTED,
    TRANSITION_SUCCEEDED,
    OperationalEvent,
)
from khepri.rra.telemetry_service import OperationalTelemetryService
from tests.test_rra006_pipeline import (
    GOLDEN,
    Adapter,
    BrokenRenderer,
    Deliveries,
    Execution,
    Packages,
    Renderer,
    job,
    package,
)

NOW = datetime(2026, 7, 30, 17, 0, tzinfo=UTC)
TICK = timedelta(milliseconds=5)
QUEUED_AGO = timedelta(milliseconds=125)
HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")

# A word no governed vocabulary, version string, digest, or stage name can
# contain, planted in the customer content this run reads and writes.
SENTINEL = "Zqsentinel"
SENTINEL_CSV = (
    GOLDEN.replace(b"Beverages", SENTINEL.encode() + b"Drinks")
    .replace(b"Snacks", SENTINEL.encode() + b"Food")
    .replace(b"Cairo", SENTINEL.encode() + b"North")
    .replace(b"Giza", SENTINEL.encode() + b"South")
)

# Every transition of a whole delivered run, in order.
DELIVERED = [
    (STAGE_PACKAGE, TRANSITION_STARTED),
    (STAGE_PACKAGE, TRANSITION_SUCCEEDED),
    (STAGE_NARRATIVE, TRANSITION_STARTED),
    (STAGE_NARRATIVE, TRANSITION_SUCCEEDED),
    (STAGE_BUNDLE, TRANSITION_STARTED),
    (STAGE_BUNDLE, TRANSITION_SUCCEEDED),
    (STAGE_DELIVERY, TRANSITION_STARTED),
    (STAGE_DELIVERY, TRANSITION_SUCCEEDED),
]


# --- fakes ----------------------------------------------------------------


class Clock:
    """A monotonic clock, advancing one tick every time it is read."""

    def __init__(self, *, start: datetime = NOW, tick: timedelta = TICK) -> None:
        self._now = start
        self._tick = tick
        self.reads = 0

    def __call__(self) -> datetime:
        reading = self._now
        self._now += self._tick
        self.reads += 1
        return reading


class EventWriter:
    """An operational event writer that keeps every event, and may refuse one."""

    def __init__(self, *, fails_on: int | None = None) -> None:
        self.events: list[OperationalEvent] = []
        self.scopes: list[SessionScope] = []
        self._fails_on = fails_on

    def record(
        self,
        *,
        scope: SessionScope,
        event: OperationalEvent,
    ) -> OperationalEvent:
        if self._fails_on is not None and len(self.events) == self._fails_on:
            self._fails_on = None
            raise RuntimeError("The operational event store is unavailable.")
        self.scopes.append(scope)
        self.events.append(event)
        return event

    @property
    def transitions(self) -> list[tuple[str, str]]:
        return [(event.stage, event.transition) for event in self.events]

    @property
    def kinds(self) -> set[str]:
        return {event.transition for event in self.events}

    def terminal(self, stage: str) -> OperationalEvent:
        return next(
            event
            for event in self.events
            if event.stage == stage and event.transition != TRANSITION_STARTED
        )

    def measured(self, read: Callable[[OperationalEvent], object]) -> dict[tuple[str, str], object]:
        """Whatever each event measured, for the events that measured it."""
        return {
            (event.stage, event.transition): read(event)
            for event in self.events
            if read(event) is not None
        }


class BrokenPackages:
    """A source that fails outright rather than declining."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def load(self, leased: ReportJob) -> FactPackage | None:
        self.asked.append(leased.job_id)
        raise RuntimeError("The fact package store is unavailable.")


class LosingDeliveries(Deliveries):
    """A store that will not write for a worker whose lease has moved on."""

    def publish(self, publication: ReportPublication) -> DeliveryRecord:
        raise LeaseLost("The lease was taken by another worker.")


class UnnamedAdapter(Adapter):
    """A provider that cannot say which build it is, so it is never called."""

    @property
    def adapter_version(self) -> str:
        raise RuntimeError("The provider is misconfigured.")


class ProseAdapter(Adapter):
    """A provider whose sentences carry a sentinel word."""

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft:
        draft = super().draft(request, timeout_seconds=timeout_seconds)
        return replace(
            draft,
            languages=tuple(
                replace(
                    entry,
                    sections=tuple(
                        replace(section, text=f"{section.text} {SENTINEL}prose.")
                        for section in entry.sections
                    ),
                )
                for entry in draft.languages
            ),
        )


# A different size for each surface, and no two of them summing to a third. A
# stage that recorded one surface's payload, or counted one twice, reaches a
# total no combination of these can be mistaken for.
SURFACE_BYTES = {SURFACE_WEB: 11, SURFACE_PDF: 222, SURFACE_EXCEL: 3333}
RENDERED_BYTES = sum(SURFACE_BYTES.values())


def surfaces() -> tuple[Renderer, ...]:
    return tuple(
        Renderer(surface, output_size_bytes=size) for surface, size in SURFACE_BYTES.items()
    )


def monotonic_ms() -> int:
    """The narrative service's own stopwatch, which this slice does not read."""
    return 0


@dataclass
class Harness:
    """Every collaborator one run needs, each of them replaceable."""

    packages: Packages | BrokenPackages = field(default_factory=lambda: Packages(package()))
    adapter: Adapter = field(default_factory=Adapter)
    renderers: tuple[Renderer, ...] = field(default_factory=surfaces)
    deliveries: Deliveries = field(default_factory=Deliveries)
    writer: EventWriter = field(default_factory=EventWriter)
    clock: Clock = field(default_factory=Clock)

    @property
    def ports(self) -> ReportPipelinePorts:
        return ReportPipelinePorts(
            packages=self.packages,
            adapter=self.adapter,
            renderers=self.renderers,
            deliveries=self.deliveries,
        )

    @property
    def recorder(self) -> StageRecorder:
        events = count()
        return StageRecorder(
            telemetry=OperationalTelemetryService(
                writer=self.writer,
                new_event_id=lambda: f"evt_{next(events)}",
            ),
            clock=self.clock,
        )

    def pipeline(self, *, instrumented: bool = True) -> ReportPipeline:
        if not instrumented:
            return ReportPipeline(ports=self.ports, monotonic_ms=monotonic_ms)
        return InstrumentedReportPipeline(
            ports=self.ports,
            monotonic_ms=monotonic_ms,
            recorder=self.recorder,
        )


def leased(**changes: object) -> ReportJob:
    return replace(job(), queued_at=NOW - QUEUED_AGO, **changes)  # type: ignore[arg-type]


def execution(**changes: object) -> Execution:
    return Execution(leased(**changes))


# --- the stage vocabulary --------------------------------------------------


def test_every_governed_stage_is_either_recorded_here_or_named_unreachable() -> None:
    # RRA-007 names eleven stages. A stage this pipeline cannot reach is
    # declared rather than left out, so no stage can be forgotten silently.
    assert frozenset(RECORDED_STAGES) | UNREACHED_STAGES == STAGES
    assert frozenset(RECORDED_STAGES).isdisjoint(UNREACHED_STAGES)
    assert RECORDED_STAGES == (STAGE_PACKAGE, STAGE_NARRATIVE, STAGE_BUNDLE, STAGE_DELIVERY)


# --- one measured run -----------------------------------------------------


def test_every_stage_boundary_records_a_started_and_a_terminal_transition() -> None:
    built = Harness()

    built.pipeline().run(execution())

    assert built.writer.transitions == DELIVERED


def test_the_handler_a_worker_calls_is_measured_too() -> None:
    # `ReportWorker` calls its handler; it never calls `run` itself.
    built = Harness()
    handler = built.pipeline()

    handler(execution())

    assert built.writer.transitions == DELIVERED


def test_a_stage_called_outside_a_run_refuses_to_be_measured() -> None:
    # The stages stay separately callable, and a measured one outside a run has
    # no attempt to correlate to. Refusing is the fail-closed answer;
    # correlating it to whichever attempt ran last would be worse.
    built = Harness()

    with pytest.raises(StageNotMeasurable):
        built.pipeline().load_package(leased())


def test_every_terminal_transition_carries_a_measured_duration() -> None:
    built = Harness()

    built.pipeline().run(execution())

    # The narrative stage reads the clock once more than the others, because the
    # provider call is timed inside it.
    assert built.writer.measured(lambda event: event.duration_ms) == {
        (STAGE_PACKAGE, TRANSITION_SUCCEEDED): 5,
        (STAGE_NARRATIVE, TRANSITION_SUCCEEDED): 10,
        (STAGE_BUNDLE, TRANSITION_SUCCEEDED): 5,
        (STAGE_DELIVERY, TRANSITION_SUCCEEDED): 5,
    }


def test_only_the_first_stage_records_the_time_this_job_waited_in_the_queue() -> None:
    # Queue time is how long the job waited to be worked, which is measured once
    # at the first boundary. Repeating it on later stages would record elapsed
    # time since enqueue and call it queue time.
    built = Harness()

    built.pipeline().run(execution())

    assert built.writer.measured(lambda event: event.queue_time_ms) == {
        (STAGE_PACKAGE, TRANSITION_STARTED): 125
    }


def test_provider_latency_is_recorded_for_the_narrative_stage_alone() -> None:
    # The provider was called one clock tick into the stage, and the reading runs
    # to the end of the stage rather than to the adapter's return.
    built = Harness()

    built.pipeline().run(execution())

    assert built.writer.measured(lambda event: event.provider_latency_ms) == {
        (STAGE_NARRATIVE, TRANSITION_SUCCEEDED): 5
    }


def test_the_stage_that_rendered_the_surfaces_records_how_large_they_were() -> None:
    # RRA-007 records output size per stage. Every renderer reports the size of
    # the payload it produced, so the boundary that produced them is the one
    # boundary that can name the total -- and it is named once. Recorded again at
    # delivery, the same bytes would be counted twice by anything aggregating
    # them. The dictionary is exact: no other stage may invent a size.
    built = Harness()

    built.pipeline().run(execution())

    assert built.writer.measured(lambda event: event.output_size_bytes) == {
        (STAGE_BUNDLE, TRANSITION_SUCCEEDED): RENDERED_BYTES
    }


def test_a_rendering_stage_that_produced_nothing_records_no_size() -> None:
    # A refused bundle delivers no surface at all, so there are no bytes to
    # name. A size recorded here would be a measurement of a run that produced
    # nothing, which is worse evidence than none.
    built = Harness(renderers=(Renderer(SURFACE_WEB), BrokenRenderer(SURFACE_PDF)))

    with pytest.raises(ReportPipelineFailed):
        built.pipeline().run(execution())

    assert built.writer.terminal(STAGE_BUNDLE).output_size_bytes is None


def test_no_stage_claims_a_dataset_size_it_was_never_told() -> None:
    # The source size is known at intake and is not carried into a fact package.
    # A band derived from anything else -- the report's own weight, a row count
    # -- would be evidence about something other than the dataset.
    built = Harness()

    built.pipeline().run(execution())

    assert built.writer.measured(lambda event: event.dataset_size_band) == {}


def test_stage_events_correlate_the_opaque_session_job_and_attempt() -> None:
    built = Harness()

    built.pipeline().run(execution())

    assert {event.session_id for event in built.writer.events} == {"ses_alpha"}
    assert {event.job_id for event in built.writer.events} == {"job_alpha"}
    assert built.writer.scopes[0] == SessionScope(owner_id="own_alpha", session_id="ses_alpha")
    assert {event.attempt_number for event in built.writer.events} == {1}
    assert {event.retry_count for event in built.writer.events} == {0}


def test_stage_events_name_the_package_and_the_bundle_once_each_is_known() -> None:
    built = Harness()

    outcome = built.pipeline().run(execution())

    named = built.writer.measured(lambda event: event.fact_package_id)
    # A started transition cannot name a package the stage has not loaded yet.
    assert list(named) == DELIVERED[1:]
    assert set(named.values()) == {package().digest}
    assert list(built.writer.measured(lambda event: event.report_bundle_id)) == DELIVERED[5:]
    assert built.writer.terminal(STAGE_DELIVERY).report_bundle_id == outcome.record.bundle_id


# --- failing stages still produce evidence --------------------------------


def test_a_missing_fact_package_records_a_refused_first_stage() -> None:
    built = Harness(packages=Packages(None))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline().run(execution())

    assert raised.value.reason == REASON_PACKAGE_MISSING
    assert built.writer.transitions == [
        (STAGE_PACKAGE, TRANSITION_STARTED),
        (STAGE_PACKAGE, TRANSITION_REFUSED),
    ]
    assert built.writer.terminal(STAGE_PACKAGE).duration_ms == 5


def test_a_refused_narrative_records_a_refused_narrative_stage() -> None:
    built = Harness(adapter=Adapter(error=ProviderRefused("no")))

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline().run(execution())

    assert raised.value.reason == REASON_PROVIDER_REFUSED
    assert built.writer.transitions == [
        *DELIVERED[:3],
        (STAGE_NARRATIVE, TRANSITION_REFUSED),
    ]
    # A provider that refused still consumed time, and how long it took before
    # refusing is the measurement a timeout budget is set from.
    assert built.writer.terminal(STAGE_NARRATIVE).provider_latency_ms == 5


def test_a_failed_surface_records_a_refused_bundle_stage() -> None:
    built = Harness(renderers=(Renderer(SURFACE_WEB), BrokenRenderer(SURFACE_PDF)))

    with pytest.raises(ReportPipelineFailed):
        built.pipeline().run(execution())

    assert built.writer.transitions == [
        *DELIVERED[:5],
        (STAGE_BUNDLE, TRANSITION_REFUSED),
    ]
    # No bundle was delivered, so no terminal transition names one.
    assert built.writer.terminal(STAGE_BUNDLE).report_bundle_id is None


def test_a_provider_that_was_never_called_records_no_provider_latency() -> None:
    # A misconfigured provider is a refusal, and the timed adapter passes the
    # failure through rather than answering for it. Nothing was asked of the
    # provider, so there is no provider latency to record.
    built = Harness(adapter=UnnamedAdapter())

    with pytest.raises(ReportPipelineFailed) as raised:
        built.pipeline().run(execution())

    assert raised.value.reason == REASON_PROVIDER_FAILED
    assert built.adapter.calls == 0
    assert built.writer.terminal(STAGE_NARRATIVE).provider_latency_ms is None


def test_a_stage_that_broke_records_a_failed_transition() -> None:
    # A governed refusal and a collaborator that broke are different operational
    # facts. Recording both as refusals would hide every outage.
    built = Harness(packages=BrokenPackages())

    with pytest.raises(RuntimeError):
        built.pipeline().run(execution())

    assert built.writer.transitions == [
        (STAGE_PACKAGE, TRANSITION_STARTED),
        (STAGE_PACKAGE, TRANSITION_FAILED),
    ]


# --- leases ---------------------------------------------------------------


@pytest.mark.parametrize("boundary", [1, 2, 3])
def test_a_lost_lease_between_stages_leaves_every_measured_stage_finished(
    boundary: int,
) -> None:
    # LeaseLost means another worker owns this job. Heartbeats sit between
    # stages, so a lease lost on a heartbeat is lost while no stage is in
    # flight: every stage that started also finished, and none is recorded as
    # having failed because a lease moved.
    built = Harness()

    with pytest.raises(LeaseLost):
        built.pipeline().run(Execution(leased(), lose_on=boundary))

    assert built.deliveries.delivered == []
    assert built.writer.transitions == DELIVERED[: boundary * 2]


def test_a_lease_lost_inside_a_stage_is_not_recorded_as_that_stage_failing() -> None:
    # A collaborator can discover the lease has moved while a stage is running.
    # The stage is then left with a started transition and no terminal one,
    # which is true: this worker neither finished it nor failed at it. Recording
    # `failed` would assert a report failure that did not happen, and catching
    # LeaseLost at all would let a second worker deliver the same report.
    built = Harness(deliveries=LosingDeliveries())

    with pytest.raises(LeaseLost):
        built.pipeline().run(execution())

    assert built.writer.transitions == DELIVERED[:7]
    assert built.writer.kinds == {TRANSITION_STARTED, TRANSITION_SUCCEEDED}


# --- idempotency ----------------------------------------------------------


def test_an_already_delivered_job_records_no_stage_at_all() -> None:
    built = Harness()
    pipeline = built.pipeline()
    first = pipeline.run(execution())

    second = pipeline.run(execution())

    assert second == PipelineOutcome(record=first.record, delivered=False)
    assert len(built.deliveries.delivered) == 1
    # The short-circuit runs no stage, so there is no stage to measure.
    assert built.writer.transitions == DELIVERED


def test_a_job_that_was_never_leased_fails_closed() -> None:
    # Every event correlates to one attempt, and a job with no attempt has no
    # attempt to correlate to.
    built = Harness()

    with pytest.raises(ValueError):
        built.pipeline().run(execution(attempt_count=0))

    assert built.writer.events == []
    assert built.deliveries.delivered == []


# --- content-free ---------------------------------------------------------


def test_no_recorded_event_carries_customer_content() -> None:
    built = Harness(packages=Packages(package(SENTINEL_CSV)), adapter=ProseAdapter())

    built.pipeline().run(execution())

    # The sentinel really did flow through this run: it is in the labels of the
    # delivered bundle and in the prose the provider wrote.
    delivered = repr(built.deliveries.delivered[0])
    assert SENTINEL in delivered
    assert f"{SENTINEL}prose" in delivered

    recorded = "\n".join(repr(event) for event in built.writer.events)
    assert SENTINEL.lower() not in recorded.lower()
    for event in built.writer.events:
        assert event.stage in STAGES
        for identifier in (event.fact_package_id, event.report_bundle_id):
            # Every identifier an event carries is a content address, not a
            # name, a location, or a path.
            assert identifier is None or HEX64.match(identifier)


# --- instrumentation changes nothing --------------------------------------


SCENARIOS: dict[str, Callable[[], Harness]] = {
    "delivered": Harness,
    "missing_package": lambda: Harness(packages=Packages(None)),
    "broken_package_source": lambda: Harness(packages=BrokenPackages()),
    "refused_narrative": lambda: Harness(adapter=Adapter(error=ProviderRefused("no"))),
    "failed_surface": lambda: Harness(
        renderers=(Renderer(SURFACE_WEB), BrokenRenderer(SURFACE_PDF))
    ),
}


def observe(built: Harness, *, instrumented: bool) -> tuple[object, ...]:
    """Everything a caller of this pipeline can see, measured or not."""
    beats = Execution(leased())
    outcome: PipelineOutcome | None = None
    failure: tuple[type[BaseException], object] | None = None
    try:
        outcome = built.pipeline(instrumented=instrumented).run(beats)
    except Exception as error:  # noqa: BLE001 - the failure is what is compared
        failure = (type(error), getattr(error, "reason", None))
    return (
        None if outcome is None else outcome.record,
        None if outcome is None else outcome.delivered,
        failure,
        beats.beats,
        tuple(built.packages.asked),
        built.adapter.calls,
        tuple(renderer.calls for renderer in built.renderers),
        tuple(entry.record for entry in built.deliveries.delivered),
    )


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_a_measured_run_and_an_unmeasured_run_agree(scenario: str) -> None:
    # Telemetry is evidence about a run, never a participant in it. The same
    # deliveries, the same exceptions, the same reasons, the same heartbeats and
    # the same collaborator calls — measured or not. The bundle identity is
    # compared too, so a wrapped adapter that altered the request, the adapter
    # version, or the draft would be caught: it would deliver another report.
    factory = SCENARIOS[scenario]

    plain = observe(factory(), instrumented=False)
    measured = observe(factory(), instrumented=True)

    assert plain == measured


# --- telemetry failures ---------------------------------------------------


def test_a_telemetry_write_failure_stops_the_run_before_anything_is_delivered() -> None:
    # Fail closed: an unrecorded run is missing evidence, and the constitution
    # blocks on missing evidence. Nothing has been delivered at the first
    # boundary, so blocking costs the work of one attempt and nothing else.
    built = Harness(writer=EventWriter(fails_on=0))

    with pytest.raises(RuntimeError):
        built.pipeline().run(execution())

    assert built.deliveries.delivered == []
    assert built.packages.asked == []


def test_a_write_failure_after_delivery_is_recoverable_by_the_retry() -> None:
    # The last write of a run happens after the report was delivered, so failing
    # closed there fails a job whose report exists. The retry is safe because the
    # pipeline asks the store whether this job was already delivered before it
    # runs a stage, so the report is neither built twice nor delivered twice.
    built = Harness(writer=EventWriter(fails_on=7))
    pipeline = built.pipeline()

    with pytest.raises(RuntimeError):
        pipeline.run(execution())

    assert len(built.deliveries.delivered) == 1
    assert built.writer.transitions == DELIVERED[:7]

    retried = pipeline.run(execution())

    assert retried.delivered is False
    assert len(built.deliveries.delivered) == 1
    # The honest gap: the short-circuit runs no stage, so the terminal event
    # that failed to write is never written by the retry either.
    assert built.writer.transitions == DELIVERED[:7]
