from __future__ import annotations

from datetime import UTC, datetime

import pytest

from khepri.rra.telemetry import OperationalEvent

NOW = datetime(2026, 7, 30, 14, 0, tzinfo=UTC)


def event(**changes: object) -> OperationalEvent:
    values = {
        "event_id": "evt_alpha",
        "session_id": "ses_alpha",
        "job_id": "job_alpha",
        "fact_package_id": None,
        "report_bundle_id": None,
        "stage": "profiling",
        "transition": "succeeded",
        "attempt_number": 1,
        "recorded_at": NOW,
        "duration_ms": 25,
        "queue_time_ms": None,
        "provider_latency_ms": None,
        "dataset_size_band": "le_10_mib",
        "output_size_bytes": None,
    }
    values.update(changes)
    return OperationalEvent(**values)  # type: ignore[arg-type]


def test_terminal_transition_requires_a_measured_duration() -> None:
    with pytest.raises(ValueError, match="duration"):
        event(duration_ms=None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", "customer_export"),
        ("transition", "maybe"),
    ],
)
def test_telemetry_refuses_unknown_vocabularies(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        event(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("attempt_number", 0),
        ("duration_ms", -1),
        ("queue_time_ms", -1),
        ("provider_latency_ms", -1),
        ("output_size_bytes", -1),
    ],
)
def test_telemetry_refuses_negative_measurements(field: str, value: int) -> None:
    with pytest.raises(ValueError, match=field):
        event(**{field: value})


def test_telemetry_refuses_an_unknown_dataset_size_band() -> None:
    with pytest.raises(ValueError, match="dataset_size_band"):
        event(dataset_size_band="customer_named_band")


def test_provider_latency_is_restricted_to_narrative_generation() -> None:
    with pytest.raises(ValueError, match="provider_latency_ms"):
        event(stage="profiling", provider_latency_ms=12)


def test_retry_count_is_derived_from_the_attempt_number() -> None:
    measured = event(
        stage="narrative_generation",
        attempt_number=3,
        provider_latency_ms=12,
        fact_package_id="fct_alpha",
        report_bundle_id="bnd_alpha",
    )

    assert measured.retry_count == 2
    assert measured.fact_package_id == "fct_alpha"
    assert measured.report_bundle_id == "bnd_alpha"
