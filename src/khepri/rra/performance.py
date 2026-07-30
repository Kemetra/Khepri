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
        for name, value in (
            ("benchmark_id", self.benchmark_id),
            ("workload_digest", self.workload_digest),
            ("environment_digest", self.environment_digest),
            ("approval_ref", self.approval_ref),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required.")


@dataclass(frozen=True, slots=True)
class BenchmarkPolicy:
    identity: BenchmarkIdentity
    expected_sample_count: int
    minimum_on_time_percent: int = MINIMUM_ON_TIME_PERCENT
    max_duration_ms: int = MAX_DURATION_MS

    def __post_init__(self) -> None:
        if self.expected_sample_count <= 0:
            raise ValueError("expected_sample_count must be positive.")
        if not MINIMUM_ON_TIME_PERCENT <= self.minimum_on_time_percent <= 100:
            raise ValueError("The approved completion objective cannot be weakened.")
        if not 0 < self.max_duration_ms <= MAX_DURATION_MS:
            raise ValueError("The approved completion deadline cannot be weakened.")


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    sample_id: str
    dataset_size_bytes: int
    duration_ms: int | None
    complete_bundle: bool

    def __post_init__(self) -> None:
        if not self.sample_id.strip():
            raise ValueError("sample_id is required.")
        if not 0 <= self.dataset_size_bytes <= MAX_DATASET_SIZE_BYTES:
            raise ValueError("Dataset size exceeds the approved beta boundary.")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative.")
        if self.complete_bundle and self.duration_ms is None:
            raise ValueError("A complete bundle requires a measured duration.")


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
