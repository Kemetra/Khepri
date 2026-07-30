"""The command CI runs, and the reason a green build proves nothing yet.

**What this is for.** RRA-007 requires CI to fail when an approved performance
tolerance is exceeded. `performance.enforce_performance` decides that, `benchmark`
measures the run it decides over, and this is the command that connects the two to
an exit code.

**Why exit 0 does not mean the objective is met.** There is no approved benchmark
workload. Run today, this command finds no approved authority, says so, and exits
0 -- it asserts nothing, so it cannot assert something false, and it must not fail
every pull request over an authorization that no slice in flight is allowed to
grant. The exit code is therefore not the evidence; the reported line is. Exactly
one line is written, and only one of them describes a certified run.

**Why an approved benchmark with no runner blocks instead.** A named authority the
command cannot execute is missing evidence, and the constitution blocks on missing
evidence. So the moment someone supplies the four identity values without wiring a
runner for the approved environment, this command starts failing. That is the fail-
closed rule working, not a regression: an approved objective nobody measured must
not read as an objective that held.

**Nothing here names a benchmark.** No identifier, digest, or approval reference
appears in this file. They arrive from the environment, which a workflow populates
from the approved governance record once one exists, and are refused when partly
supplied.

**What is written.** One line naming an outcome, a sample count, and an opaque
benchmark identifier. Durations and counts are numbers; no dataset content, label,
figure, or sentence reaches a build log through this module.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Mapping
from typing import TextIO

from khepri.rra.benchmark import (
    BenchmarkHarness,
    BenchmarkMeasurement,
    BenchmarkUnmeasurable,
    ReportTrial,
    certify_benchmark,
)
from khepri.rra.benchmark_authorization import (
    ApprovedBenchmark,
    BenchmarkNotAuthorized,
    resolve_approved_benchmark,
)
from khepri.rra.performance import BenchmarkResult, BenchmarkTampered, PerformanceRegression

# Nothing was asserted, so nothing can be false. The reported line says which of
# the two zero-exit outcomes this was.
EXIT_NOTHING_CERTIFIED = 0
EXIT_CERTIFIED = 0
EXIT_BLOCKED = 1

NOTHING_CERTIFIED = (
    "benchmark: NOT CERTIFIED. No approved benchmark workload exists, so no "
    "sample was measured and no completion objective was tested."
)
NOT_AUTHORIZED = (
    "benchmark: BLOCKED. The benchmark declaration is not authorized: it is "
    "absent in part, blank, or unreadable."
)
NO_RUNNER = (
    "benchmark: BLOCKED. An approved benchmark is named but no benchmark runner "
    "is configured for this environment, so no evidence can be produced."
)
OBJECTIVE_MISSED = "benchmark: BLOCKED. The approved completion objective was missed."
NOT_THE_APPROVED_WORKLOAD = (
    "benchmark: BLOCKED. The evidence is not of the approved workload or is incomplete."
)
UNMEASURABLE = "benchmark: BLOCKED. The benchmark readings are inconsistent."

TrialFactory = Callable[[Callable[[], int]], ReportTrial]


def run_benchmark_gate(
    *,
    environment: Mapping[str, str],
    report: TextIO,
    trial_for: TrialFactory | None = None,
) -> int:
    """Certify one benchmark run, or say plainly that nothing was certified."""
    try:
        approved = resolve_approved_benchmark(environment)
    except BenchmarkNotAuthorized:
        return _say(report, NOT_AUTHORIZED, EXIT_BLOCKED)
    if approved is None:
        return _say(report, NOTHING_CERTIFIED, EXIT_NOTHING_CERTIFIED)
    if trial_for is None:
        return _say(report, NO_RUNNER, EXIT_BLOCKED)
    return _certify(report, approved, trial_for)


def _certify(report: TextIO, approved: ApprovedBenchmark, trial_for: TrialFactory) -> int:
    """Measure the approved workload and enforce the approved objective over it.

    Every refusal is caught and reported as a blocked build rather than a
    traceback, and none of them can reach the certified line: each returns.
    """
    try:
        measurements = _measure(approved, trial_for)
        result = certify_benchmark(approved=approved, measurements=measurements)
    except PerformanceRegression:
        return _say(report, OBJECTIVE_MISSED, EXIT_BLOCKED)
    except BenchmarkTampered:
        return _say(report, NOT_THE_APPROVED_WORKLOAD, EXIT_BLOCKED)
    except BenchmarkUnmeasurable:
        return _say(report, UNMEASURABLE, EXIT_BLOCKED)
    return _say(report, _certified(result), EXIT_CERTIFIED)


def _measure(
    approved: ApprovedBenchmark,
    trial_for: TrialFactory,
) -> tuple[BenchmarkMeasurement, ...]:
    """One harness, one clock, shared with the trial it drives.

    The trial is built around the harness's clock rather than one of its own, so
    the moment a trial reports beginning is comparable with the readings the
    queue and processing durations are taken from.
    """
    harness = BenchmarkHarness(
        workload=approved.workload,
        trial=trial_for(monotonic_ms),
        monotonic_ms=monotonic_ms,
    )
    return harness.measure()


def _certified(result: BenchmarkResult) -> str:
    """One line of evidence about one run, and no adjective about the product."""
    return (
        f"benchmark {result.identity.benchmark_id}: "
        f"{result.on_time_count}/{result.sample_count} samples completed within the "
        f"approved deadline under approval {result.identity.approval_ref}."
    )


def _say(report: TextIO, line: str, code: int) -> int:
    report.write(f"{line}\n")
    return code


def monotonic_ms() -> int:
    """A monotonic reading in milliseconds, which cannot run backwards."""
    return time.monotonic_ns() // 1_000_000


def main() -> int:
    return run_benchmark_gate(environment=os.environ, report=sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXIT_BLOCKED",
    "EXIT_CERTIFIED",
    "EXIT_NOTHING_CERTIFIED",
    "NOTHING_CERTIFIED",
    "TrialFactory",
    "main",
    "monotonic_ms",
    "run_benchmark_gate",
]
