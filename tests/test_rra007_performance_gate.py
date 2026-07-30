from __future__ import annotations

from dataclasses import fields

import pytest

from khepri.rra.performance import (
    BenchmarkIdentity,
    BenchmarkPolicy,
    BenchmarkRun,
    BenchmarkSample,
    BenchmarkTampered,
    PerformanceRegression,
    enforce_performance,
)

MIB = 1024 * 1024
IDENTITY = BenchmarkIdentity(
    benchmark_id="bmk_beta_v1",
    workload_digest="sha256:workload",
    environment_digest="sha256:environment",
    approval_ref="approval_ref_alpha",
)
POLICY = BenchmarkPolicy(identity=IDENTITY, expected_sample_count=20)


def sample(position: int, *, duration_ms: int | None = 500_000) -> BenchmarkSample:
    return BenchmarkSample(
        sample_id=f"sample_{position}",
        dataset_size_bytes=50 * MIB,
        duration_ms=duration_ms,
        complete_bundle=duration_ms is not None,
    )


def test_exactly_ninety_five_percent_within_ten_minutes_passes() -> None:
    run = BenchmarkRun(
        identity=IDENTITY,
        samples=tuple(sample(position) for position in range(19))
        + (sample(19, duration_ms=None),),
    )

    result = enforce_performance(policy=POLICY, run=run)

    assert result.sample_count == 20
    assert result.on_time_count == 19
    assert result.on_time_percent == 95


def test_performance_regression_fails_the_gate() -> None:
    run = BenchmarkRun(
        identity=IDENTITY,
        samples=tuple(sample(position) for position in range(18))
        + (
            sample(18, duration_ms=600_001),
            sample(19, duration_ms=None),
        ),
    )

    with pytest.raises(PerformanceRegression, match="18/20"):
        enforce_performance(policy=POLICY, run=run)


@pytest.mark.parametrize(
    "run",
    [
        BenchmarkRun(
            identity=BenchmarkIdentity(
                benchmark_id="bmk_beta_v1",
                workload_digest="sha256:other",
                environment_digest="sha256:environment",
                approval_ref="approval_ref_alpha",
            ),
            samples=tuple(sample(position) for position in range(20)),
        ),
        BenchmarkRun(
            identity=IDENTITY,
            samples=tuple(sample(position) for position in range(19)),
        ),
        BenchmarkRun(
            identity=IDENTITY,
            samples=tuple(sample(0) for _ in range(20)),
        ),
    ],
)
def test_gate_rejects_substituted_or_incomplete_evidence(run: BenchmarkRun) -> None:
    with pytest.raises(BenchmarkTampered):
        enforce_performance(policy=POLICY, run=run)


@pytest.mark.parametrize(
    "changes",
    [
        {"minimum_on_time_percent": 94},
        {"max_duration_ms": 600_001},
    ],
)
def test_policy_cannot_weaken_the_approved_objective(
    changes: dict[str, int],
) -> None:
    with pytest.raises(ValueError, match="cannot be weakened"):
        BenchmarkPolicy(
            identity=IDENTITY,
            expected_sample_count=20,
            **changes,  # type: ignore[arg-type]
        )


def test_benchmark_evidence_has_no_customer_content_fields() -> None:
    names = {
        field.name
        for record_type in (BenchmarkIdentity, BenchmarkSample, BenchmarkRun)
        for field in fields(record_type)
    }

    assert {
        "filename",
        "label",
        "source_value",
        "narrative",
        "facts",
        "token",
        "object_location",
    }.isdisjoint(names)
