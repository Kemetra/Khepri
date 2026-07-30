from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

MIB = 1024 * 1024
MAX_DATASET_SIZE_BYTES = 50 * MIB
MAX_DURATION_MS = 10 * 60 * 1000
MINIMUM_ON_TIME_PERCENT = 95


class BenchmarkTampered(ValueError):
    pass


class PerformanceRegression(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BenchmarkIdentity:
    benchmark_id: str
    workload_digest: str
    environment_digest: str
    approval_ref: str

    def __post_init__(self) -> None:
        _require_text(self.benchmark_id, "benchmark_id")
        _require_text(self.workload_digest, "workload_digest")
        _require_text(self.environment_digest, "environment_digest")
        _require_text(self.approval_ref, "approval_ref")


@dataclass(frozen=True, slots=True)
class BenchmarkPolicy:
    identity: BenchmarkIdentity
    expected_sample_count: int
    minimum_on_time_percent: int = MINIMUM_ON_TIME_PERCENT
    max_duration_ms: int = MAX_DURATION_MS

    def __post_init__(self) -> None:
        _require_positive(self.expected_sample_count, "expected_sample_count")
        _require_completion_objective(self.minimum_on_time_percent)
        _require_completion_deadline(self.max_duration_ms)


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    sample_id: str
    dataset_size_bytes: int
    duration_ms: int | None
    complete_bundle: bool

    def __post_init__(self) -> None:
        _require_text(self.sample_id, "sample_id")
        _require_dataset_size(self.dataset_size_bytes)
        _require_duration(self.duration_ms)
        _require_complete_duration(self.complete_bundle, self.duration_ms)


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    identity: BenchmarkIdentity
    samples: tuple[BenchmarkSample, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    identity: BenchmarkIdentity
    sample_count: int
    on_time_count: int
    on_time_percent: Decimal


def enforce_performance(
    *,
    policy: BenchmarkPolicy,
    run: BenchmarkRun,
) -> BenchmarkResult:
    _verify_evidence(policy, run)
    on_time_count = sum(
        sample.complete_bundle
        and sample.duration_ms is not None
        and sample.duration_ms <= policy.max_duration_ms
        for sample in run.samples
    )
    sample_count = len(run.samples)
    if on_time_count * 100 < sample_count * policy.minimum_on_time_percent:
        raise PerformanceRegression(
            f"Performance objective missed: {on_time_count}/{sample_count} "
            "samples completed on time."
        )
    return BenchmarkResult(
        identity=run.identity,
        sample_count=sample_count,
        on_time_count=on_time_count,
        on_time_percent=Decimal(on_time_count * 100) / Decimal(sample_count),
    )


def _verify_evidence(policy: BenchmarkPolicy, run: BenchmarkRun) -> None:
    if run.identity != policy.identity:
        raise BenchmarkTampered("Benchmark identity does not match the approved policy.")
    if len(run.samples) != policy.expected_sample_count:
        raise BenchmarkTampered("Benchmark evidence has an unexpected sample count.")
    sample_ids = {sample.sample_id for sample in run.samples}
    if len(sample_ids) != len(run.samples):
        raise BenchmarkTampered("Benchmark evidence contains duplicate samples.")


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} is required.")


def _require_positive(value: int, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive.")


def _require_completion_objective(value: int) -> None:
    if not MINIMUM_ON_TIME_PERCENT <= value <= 100:
        raise ValueError("The approved completion objective cannot be weakened.")


def _require_completion_deadline(value: int) -> None:
    if not 0 < value <= MAX_DURATION_MS:
        raise ValueError("The approved completion deadline cannot be weakened.")


def _require_dataset_size(value: int) -> None:
    if not 0 <= value <= MAX_DATASET_SIZE_BYTES:
        raise ValueError("Dataset size exceeds the approved beta boundary.")


def _require_duration(value: int | None) -> None:
    if value is not None and value < 0:
        raise ValueError("duration_ms must be non-negative.")


def _require_complete_duration(
    complete_bundle: bool,
    duration_ms: int | None,
) -> None:
    if complete_bundle and duration_ms is None:
        raise ValueError("A complete bundle requires a measured duration.")
