from __future__ import annotations

from collections.abc import Sequence
from dataclasses import fields

import pytest

from khepri.rra.benchmark import (
    BenchmarkHarness,
    BenchmarkMeasurement,
    BenchmarkUnmeasurable,
    SampleDurations,
    certify_benchmark,
)
from khepri.rra.benchmark_authorization import ApprovedBenchmark, BenchmarkNotAuthorized
from khepri.rra.benchmark_trial import DeterministicReportTrial, TrialOutcome, TrialPorts
from khepri.rra.benchmark_workload import BenchmarkDataset, BenchmarkWorkload
from khepri.rra.bundle import REQUIRED_SURFACES, SURFACE_PDF
from khepri.rra.performance import (
    MAX_DURATION_MS,
    BenchmarkIdentity,
    BenchmarkTampered,
    PerformanceRegression,
)
from tests.rra_benchmark_fakes import BrokenRenderer, faithful_renderers, renderers_but

ON_TIME_MS = 500_000
LATE_MS = MAX_DURATION_MS + 1


class Clock:
    """A monotonic reading in milliseconds, scripted reading by reading."""

    def __init__(self, readings: Sequence[int]) -> None:
        self._readings = list(readings)

    def __call__(self) -> int:
        return self._readings.pop(0)


def scripted(totals: Sequence[int], *, queue_ms: int = 0) -> Clock:
    """A clock that makes each trial wait `queue_ms` and take its own total."""
    readings: list[int] = []
    now = 0
    for total in totals:
        readings.extend([now, now + queue_ms, now + queue_ms + total])
        now += queue_ms + total + 1
    return Clock(readings)


class ScriptedTrial:
    """A trial that starts when the clock says, and completes if told to."""

    def __init__(self, clock: Clock, *, complete: bool = True) -> None:
        self._clock = clock
        self._complete = complete
        self.datasets: list[str] = []

    def run(self, dataset: BenchmarkDataset) -> TrialOutcome:
        self.datasets.append(dataset.sample_id)
        surfaces = REQUIRED_SURFACES if self._complete else ()
        return TrialOutcome(
            started_at_ms=self._clock(),
            surfaces=surfaces,
            complete=self._complete,
        )


class DriftingTrial:
    """A trial that reports starting at a moment of its own choosing."""

    def __init__(self, clock: Clock, *, started_at_ms: int) -> None:
        self._clock = clock
        self._started_at_ms = started_at_ms

    def run(self, dataset: BenchmarkDataset) -> TrialOutcome:
        self._clock()
        return TrialOutcome(
            started_at_ms=self._started_at_ms,
            surfaces=REQUIRED_SURFACES,
            complete=True,
        )


def workload(sample_count: int = 2) -> BenchmarkWorkload:
    return BenchmarkWorkload(sample_count=sample_count, rows_per_dataset=8)


def approved(
    declared: BenchmarkWorkload,
    *,
    workload_digest: str | None = None,
) -> ApprovedBenchmark:
    """A benchmark identity supplied by a test. It approves nothing."""
    return ApprovedBenchmark(
        identity=BenchmarkIdentity(
            benchmark_id="test_supplied_benchmark",
            workload_digest=workload_digest or declared.digest,
            environment_digest="sha256:test_supplied_environment",
            approval_ref="test_supplied_ref_no_approval_exists",
        ),
        workload=declared,
    )


def measured(
    declared: BenchmarkWorkload,
    totals: Sequence[int],
    *,
    complete: bool = True,
) -> tuple[BenchmarkMeasurement, ...]:
    clock = scripted(totals)
    harness = BenchmarkHarness(
        workload=declared,
        trial=ScriptedTrial(clock, complete=complete),
        monotonic_ms=clock,
    )
    return harness.measure()


def real_harness(declared: BenchmarkWorkload, renderers: tuple[object, ...]) -> BenchmarkHarness:
    clock = Clock(list(range(1, 3 * declared.sample_count + 1)))
    return BenchmarkHarness(
        workload=declared,
        trial=DeterministicReportTrial(
            ports=TrialPorts(renderers=renderers),  # type: ignore[arg-type]
            monotonic_ms=clock,
        ),
        monotonic_ms=clock,
    )


# --- measuring -------------------------------------------------------------


def test_every_declared_dataset_is_measured_once() -> None:
    clock = scripted([ON_TIME_MS] * 3)
    trial = ScriptedTrial(clock)

    measurements = BenchmarkHarness(
        workload=workload(3),
        trial=trial,
        monotonic_ms=clock,
    ).measure()

    assert len(measurements) == 3
    assert trial.datasets == [entry.sample_id for entry in workload(3).datasets()]


def test_a_sample_carries_its_queue_processing_and_total_durations() -> None:
    # RRA-007 records queue time, processing time and total duration. The total
    # is what the gate reads; the other two are why a total is what it is.
    measurements = measured(workload(1), [ON_TIME_MS])

    assert measurements[0].durations == SampleDurations(
        queue_ms=0,
        processing_ms=ON_TIME_MS,
        total_ms=ON_TIME_MS,
    )


def test_time_a_dataset_waited_is_measured_apart_from_time_it_took() -> None:
    clock = scripted([ON_TIME_MS], queue_ms=4_000)
    harness = BenchmarkHarness(
        workload=workload(1),
        trial=ScriptedTrial(clock),
        monotonic_ms=clock,
    )

    durations = harness.measure()[0].durations

    assert durations.queue_ms == 4_000
    assert durations.processing_ms == ON_TIME_MS
    assert durations.total_ms == 4_000 + ON_TIME_MS


def test_a_measured_sample_names_the_size_of_what_was_measured() -> None:
    declared = workload(1)

    measurements = measured(declared, [ON_TIME_MS])

    assert measurements[0].dataset_size_bytes == declared.datasets()[0].size_bytes


def test_the_gate_reads_the_total_duration_of_each_sample() -> None:
    measurements = measured(workload(1), [ON_TIME_MS], complete=False)

    sample = measurements[0].sample
    assert sample.duration_ms == ON_TIME_MS
    assert sample.complete_bundle is False


@pytest.mark.parametrize(
    "started_at_ms",
    [
        pytest.param(-1, id="before_it_was_offered"),
        pytest.param(10_000_000, id="after_it_had_finished"),
    ],
)
def test_a_trial_that_misreports_when_it_began_is_refused(started_at_ms: int) -> None:
    # Queue time and processing time are differences from that reading. A trial
    # free to choose it could report a run that finished before it started.
    clock = scripted([ON_TIME_MS])
    harness = BenchmarkHarness(
        workload=workload(1),
        trial=DriftingTrial(clock, started_at_ms=started_at_ms),
        monotonic_ms=clock,
    )

    with pytest.raises(BenchmarkUnmeasurable):
        harness.measure()


@pytest.mark.parametrize(
    ("queue_ms", "processing_ms", "total_ms"),
    [
        pytest.param(-1, 10, 9, id="a_negative_wait"),
        pytest.param(0, -1, -1, id="a_negative_run"),
        pytest.param(10, 10, 30, id="a_total_that_is_neither"),
    ],
)
def test_durations_that_do_not_describe_one_sample_are_refused(
    queue_ms: int,
    processing_ms: int,
    total_ms: int,
) -> None:
    # The total is what the gate compares against the ten-minute deadline, so a
    # total unrelated to the wait and the run would be the one number that
    # matters describing nothing.
    with pytest.raises(ValueError):
        SampleDurations(queue_ms=queue_ms, processing_ms=processing_ms, total_ms=total_ms)


# --- measuring the actual report path --------------------------------------


def test_samples_come_from_running_the_report_path_over_built_datasets() -> None:
    declared = workload(2)
    renderers = faithful_renderers()

    measurements = real_harness(declared, renderers).measure()

    assert [entry.sample.complete_bundle for entry in measurements] == [True, True]
    assert [len(renderer.seen) for renderer in renderers] == [2, 2, 2]


def test_a_report_the_path_could_not_complete_is_measured_as_incomplete() -> None:
    declared = workload(1)

    measurements = real_harness(declared, renderers_but(BrokenRenderer(SURFACE_PDF))).measure()

    assert measurements[0].sample.complete_bundle is False
    assert measurements[0].sample.duration_ms is not None


# --- certifying ------------------------------------------------------------


def test_nothing_is_certified_without_an_approved_benchmark() -> None:
    # Constitution V: unknown authority blocks progress. There is no approved
    # benchmark workload, so there is no result to hand back -- not a passing
    # one, and not a provisional one.
    declared = workload(1)

    with pytest.raises(BenchmarkNotAuthorized):
        certify_benchmark(approved=None, measurements=measured(declared, [ON_TIME_MS]))


def test_an_approved_benchmark_certifies_the_run_it_approved() -> None:
    declared = workload(20)

    result = certify_benchmark(
        approved=approved(declared),
        measurements=measured(declared, [ON_TIME_MS] * 20),
    )

    assert result.sample_count == 20
    assert result.on_time_count == 20
    assert result.identity.benchmark_id == "test_supplied_benchmark"


def test_missing_the_completion_objective_fails_the_gate() -> None:
    # Eighteen of twenty inside ten minutes is 90%, and the approved objective
    # is 95%. The gate must refuse, and refuse loudly enough to fail a build.
    declared = workload(20)

    with pytest.raises(PerformanceRegression, match="18/20"):
        certify_benchmark(
            approved=approved(declared),
            measurements=measured(declared, [ON_TIME_MS] * 18 + [LATE_MS] * 2),
        )


def test_a_run_that_lost_a_sample_is_not_a_smaller_passing_run() -> None:
    # The expected count comes from the approved declaration, so a measurement
    # that never arrived cannot quietly shrink the evidence into a pass.
    declared = workload(20)
    measurements = measured(declared, [ON_TIME_MS] * 20)

    with pytest.raises(BenchmarkTampered):
        certify_benchmark(approved=approved(declared), measurements=measurements[:19])


def test_datasets_that_no_longer_match_the_approved_digest_are_refused() -> None:
    # The approved record cites the workload it approved. A dataset builder or a
    # declaration edited afterwards is a different workload, whatever it claims.
    declared = workload(2)

    with pytest.raises(BenchmarkTampered):
        certify_benchmark(
            approved=approved(declared, workload_digest="rra007.workload.v1:another"),
            measurements=measured(declared, [ON_TIME_MS] * 2),
        )


# --- content-free ----------------------------------------------------------


def test_benchmark_measurements_have_no_customer_content_fields() -> None:
    names = {
        field.name
        for record_type in (BenchmarkMeasurement, SampleDurations, TrialOutcome)
        for field in fields(record_type)
    }

    assert {
        "content",
        "filename",
        "label",
        "source_value",
        "narrative",
        "facts",
        "token",
        "object_location",
    }.isdisjoint(names)
