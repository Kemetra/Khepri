"""Drive the approved benchmark workload, measure it, and hand it to the gate.

**What this fills.** `performance.enforce_performance` is implemented and tested,
and until now nothing produced a `BenchmarkSample` for it: the gate existed with
nothing feeding it. This module is the thing that feeds it -- it runs each declared
dataset through the report path, measures what happened, and offers the samples for
enforcement.

**The harness measures; the trial works.** A trial reports only the moment it
began. Every duration is a difference between readings this module took, because a
trial free to report its own duration could report a shorter one than the work it
did. The reading it does supply is checked against the readings around it, and a
start outside that window makes the whole run unmeasurable rather than
approximately right.

**Three durations, one of which the gate reads.** Queue time is from the moment a
dataset was offered to the moment its trial began; processing time is from there to
the moment it ended; the total spans both, and the total is what
`BenchmarkSample.duration_ms` carries. RRA-007 asks for all three, and only the
total answers "did the complete bundle arrive within ten minutes".

**Nothing is certified without approved authority.** `certify_benchmark` refuses a
run with no approved benchmark rather than returning a provisional result: an
absent authority is not a weaker pass. It then refuses a run whose datasets do not
match the workload digest the approved record cites, because an identity pointed at
a workload nobody approved is the substitution `BenchmarkTampered` names. Only then
does it call `enforce_performance`, whose objective and deadline it never restates
and cannot weaken -- the policy is built from the approved declaration and the
constants `performance` already guards.

**The expected sample count comes from the declaration, never from the samples.** A
run that lost a measurement would otherwise certify a smaller, easier run.

**Content-free.** A measurement carries an opaque sample identifier, a size, three
durations, and a boolean. No dataset bytes, no labels, no figures, and no prose can
reach one; there is no field for them.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from khepri.rra.benchmark_authorization import ApprovedBenchmark, BenchmarkNotAuthorized
from khepri.rra.benchmark_trial import TrialOutcome
from khepri.rra.benchmark_workload import BenchmarkDataset, BenchmarkWorkload
from khepri.rra.performance import (
    BenchmarkPolicy,
    BenchmarkResult,
    BenchmarkRun,
    BenchmarkSample,
    BenchmarkTampered,
    enforce_performance,
)


class BenchmarkUnmeasurable(RuntimeError):
    """A reading is inconsistent, so no duration derived from it is evidence."""


class ReportTrial(Protocol):
    """Whatever runs one dataset through the report path."""

    def run(self, dataset: BenchmarkDataset) -> TrialOutcome: ...


@dataclass(frozen=True, slots=True)
class SampleDurations:
    """How long one sample waited, how long it ran, and how long that was.

    Held together rather than spread across a measurement, because the three are
    one reading of one sample and the total is not independent of the other two.
    """

    queue_ms: int
    processing_ms: int
    total_ms: int

    def __post_init__(self) -> None:
        _require_non_negative(self.queue_ms, "queue_ms")
        _require_non_negative(self.processing_ms, "processing_ms")
        _require_consistent_total(self)


@dataclass(frozen=True, slots=True)
class BenchmarkMeasurement:
    """One measured sample: what was run, how large it was, how long it took."""

    sample_id: str
    dataset_size_bytes: int
    durations: SampleDurations
    complete_bundle: bool

    @property
    def sample(self) -> BenchmarkSample:
        """The same reading, as the performance gate reads it."""
        return BenchmarkSample(
            sample_id=self.sample_id,
            dataset_size_bytes=self.dataset_size_bytes,
            duration_ms=self.durations.total_ms,
            complete_bundle=self.complete_bundle,
        )


class BenchmarkHarness:
    """Run every declared dataset through the report path, once, and time it."""

    def __init__(
        self,
        *,
        workload: BenchmarkWorkload,
        trial: ReportTrial,
        monotonic_ms: Callable[[], int],
    ) -> None:
        self._workload = workload
        self._trial = trial
        self._clock = monotonic_ms

    def measure(self) -> tuple[BenchmarkMeasurement, ...]:
        """Every sample of this workload, measured in the declared order."""
        return tuple(self._measure(dataset) for dataset in self._workload.datasets())

    def _measure(self, dataset: BenchmarkDataset) -> BenchmarkMeasurement:
        offered_at_ms = self._clock()
        outcome = self._trial.run(dataset)
        finished_at_ms = self._clock()
        return BenchmarkMeasurement(
            sample_id=dataset.sample_id,
            dataset_size_bytes=dataset.size_bytes,
            durations=_durations(offered_at_ms, outcome.started_at_ms, finished_at_ms),
            complete_bundle=outcome.complete,
        )


def certify_benchmark(
    *,
    approved: ApprovedBenchmark | None,
    measurements: Sequence[BenchmarkMeasurement],
) -> BenchmarkResult:
    """Enforce the approved completion objective over one measured run.

    Raises rather than returns on every unhappy answer: `BenchmarkNotAuthorized`
    when no approved benchmark exists, `BenchmarkTampered` when the evidence is
    not of the approved workload, and `PerformanceRegression` when the objective
    was missed. There is no return value that means "nearly".
    """
    if approved is None:
        raise BenchmarkNotAuthorized("No approved benchmark workload authorizes this run.")
    _require_approved_workload(approved)
    return enforce_performance(
        policy=BenchmarkPolicy(
            identity=approved.identity,
            expected_sample_count=approved.workload.sample_count,
        ),
        run=BenchmarkRun(
            identity=approved.identity,
            samples=tuple(entry.sample for entry in measurements),
        ),
    )


def _require_approved_workload(approved: ApprovedBenchmark) -> None:
    """Refuse evidence built from a workload the approved record does not cite."""
    if approved.workload.digest != approved.identity.workload_digest:
        raise BenchmarkTampered("Benchmark datasets do not match the approved workload digest.")


def _durations(offered_at_ms: int, started_at_ms: int, finished_at_ms: int) -> SampleDurations:
    _require_ordered(offered_at_ms, started_at_ms)
    _require_ordered(started_at_ms, finished_at_ms)
    return SampleDurations(
        queue_ms=started_at_ms - offered_at_ms,
        processing_ms=finished_at_ms - started_at_ms,
        total_ms=finished_at_ms - offered_at_ms,
    )


def _require_ordered(earlier_ms: int, later_ms: int) -> None:
    if later_ms < earlier_ms:
        raise BenchmarkUnmeasurable("Benchmark readings are out of order.")


def _require_non_negative(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative.")


def _require_consistent_total(durations: SampleDurations) -> None:
    if durations.total_ms != durations.queue_ms + durations.processing_ms:
        raise ValueError("total_ms must be the queue and processing durations together.")


__all__ = [
    "BenchmarkHarness",
    "BenchmarkMeasurement",
    "BenchmarkUnmeasurable",
    "ReportTrial",
    "SampleDurations",
    "certify_benchmark",
]
