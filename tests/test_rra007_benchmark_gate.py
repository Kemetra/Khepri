from __future__ import annotations

import io
from collections.abc import Callable

import pytest

from khepri.rra.benchmark import ReportTrial
from khepri.rra.benchmark_authorization import BENCHMARK_APPROVAL_KEYS
from khepri.rra.benchmark_gate import (
    EXIT_BLOCKED,
    EXIT_CERTIFIED,
    EXIT_NOTHING_CERTIFIED,
    main,
    run_benchmark_gate,
)
from khepri.rra.benchmark_trial import DeterministicReportTrial, TrialOutcome, TrialPorts
from khepri.rra.benchmark_workload import BenchmarkDataset, BenchmarkWorkload
from khepri.rra.bundle import REQUIRED_SURFACES
from tests.rra_benchmark_fakes import faithful_renderers

WORKLOAD = BenchmarkWorkload(sample_count=2, rows_per_dataset=8)


def environment(*, workload_digest: str | None = None) -> dict[str, str]:
    """What a workflow would supply from an approved benchmark record.

    Nothing here is approval evidence. No approved benchmark workload exists, and
    these values exist only so the gate's wiring can be exercised.
    """
    return {
        "KHEPRI_BENCHMARK_ID": "test_supplied_benchmark",
        "KHEPRI_BENCHMARK_WORKLOAD_DIGEST": workload_digest or WORKLOAD.digest,
        "KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST": "sha256:test_supplied_environment",
        "KHEPRI_BENCHMARK_APPROVAL_REF": "test_supplied_ref_no_approval_exists",
        "KHEPRI_BENCHMARK_SAMPLE_COUNT": str(WORKLOAD.sample_count),
        "KHEPRI_BENCHMARK_DATASET_ROWS": str(WORKLOAD.rows_per_dataset),
    }


class IncompleteTrial:
    """A report path that completes no bundle at all."""

    def __init__(self, monotonic_ms: Callable[[], int]) -> None:
        self._clock = monotonic_ms

    def run(self, dataset: BenchmarkDataset) -> TrialOutcome:
        return TrialOutcome(started_at_ms=self._clock(), surfaces=(), complete=False)


class DriftingTrial:
    """A report path that reports beginning before it was offered a dataset."""

    def __init__(self, monotonic_ms: Callable[[], int]) -> None:
        self._clock = monotonic_ms

    def run(self, dataset: BenchmarkDataset) -> TrialOutcome:
        self._clock()
        return TrialOutcome(started_at_ms=-1, surfaces=REQUIRED_SURFACES, complete=True)


def faithful_trial(monotonic_ms: Callable[[], int]) -> ReportTrial:
    return DeterministicReportTrial(
        ports=TrialPorts(renderers=faithful_renderers()),
        monotonic_ms=monotonic_ms,
    )


def gated(
    supplied: dict[str, str] | None,
    *,
    trial_for: Callable[[Callable[[], int]], ReportTrial] | None = None,
) -> tuple[int, str]:
    report = io.StringIO()
    code = run_benchmark_gate(
        environment=supplied or {},
        report=report,
        trial_for=trial_for,
    )
    return code, report.getvalue()


# --- no approved workload --------------------------------------------------


def test_with_no_approved_workload_the_gate_certifies_nothing() -> None:
    code, said = gated({"PATH": "/usr/bin"})

    assert code == EXIT_NOTHING_CERTIFIED
    assert "NOT CERTIFIED" in said
    assert "no approved benchmark workload" in said.lower()


def test_the_workflow_shape_of_no_approved_workload_certifies_nothing() -> None:
    # What the CI job supplies today: every variable named, none configured.
    code, said = gated(dict.fromkeys(environment(), ""), trial_for=faithful_trial)

    assert code == EXIT_NOTHING_CERTIFIED
    assert "NOT CERTIFIED" in said


def test_the_gate_never_reports_a_pass_it_did_not_measure() -> None:
    # A green build must not be readable as evidence that the 95% objective is
    # met. Nothing in the unauthorized output may say it was.
    _, said = gated({})

    lowered = said.lower()
    assert "objective met" not in lowered
    assert "passed" not in lowered
    assert "95%" not in lowered
    assert "certified " not in lowered


@pytest.mark.parametrize("missing", sorted(BENCHMARK_APPROVAL_KEYS))
def test_a_partly_declared_benchmark_blocks_the_build(missing: str) -> None:
    supplied = {name: value for name, value in environment().items() if name != missing}

    code, said = gated(supplied, trial_for=faithful_trial)

    assert code == EXIT_BLOCKED
    assert "not authorized" in said.lower()


def test_an_approved_benchmark_with_no_runner_blocks_rather_than_passes() -> None:
    # An approved workload the gate cannot run is missing evidence, and missing
    # evidence blocks. It is deliberately not reported as nothing to do.
    code, said = gated(environment())

    assert code == EXIT_BLOCKED
    assert "no benchmark runner" in said.lower()


# --- with a runner and an authorization supplied by a test ------------------


def test_the_gate_runs_the_report_path_and_enforces_the_objective() -> None:
    code, said = gated(environment(), trial_for=faithful_trial)

    assert code == EXIT_CERTIFIED
    assert "2/2" in said


def test_a_run_that_missed_the_objective_fails_the_build() -> None:
    code, said = gated(environment(), trial_for=IncompleteTrial)

    assert code == EXIT_BLOCKED
    assert "objective" in said.lower()


def test_a_runner_whose_readings_are_inconsistent_fails_the_build() -> None:
    # A runner that misreports when it began makes every duration derived from
    # that reading fiction. The build blocks rather than certifying fiction.
    code, said = gated(environment(), trial_for=DriftingTrial)

    assert code == EXIT_BLOCKED
    assert "inconsistent" in said.lower()


def test_evidence_from_another_workload_fails_the_build() -> None:
    code, said = gated(
        environment(workload_digest="rra007.workload.v1:another"),
        trial_for=faithful_trial,
    )

    assert code == EXIT_BLOCKED
    assert "approved workload" in said.lower()


# --- content-free ----------------------------------------------------------


@pytest.mark.parametrize(
    "supplied",
    [
        pytest.param(None, id="unauthorized"),
        pytest.param(environment(), id="authorized"),
    ],
)
def test_the_gate_reports_no_dataset_content(supplied: dict[str, str] | None) -> None:
    _, said = gated(supplied, trial_for=faithful_trial)

    assert "Beverages" not in said
    assert "Cairo" not in said
    assert "2026-01" not in said
    assert "revenue" not in said


# --- the entry point CI runs ------------------------------------------------


def test_the_entry_point_certifies_nothing_in_an_environment_naming_none(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for key in BENCHMARK_APPROVAL_KEYS:
        monkeypatch.delenv(key, raising=False)

    assert main() == EXIT_NOTHING_CERTIFIED
    assert "NOT CERTIFIED" in capsys.readouterr().out
