from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from khepri.rra.sessions import SessionScope
from khepri.rra.telemetry import (
    TRANSITION_FAILED,
    TRANSITION_REFUSED,
    TRANSITION_STARTED,
    TRANSITION_SUCCEEDED,
    OperationalEvent,
)
from khepri.rra.telemetry_service import (
    OperationalTelemetryService,
    StageCompletion,
    StageMeasurement,
)

NOW = datetime(2026, 7, 30, 15, 0, tzinfo=UTC)
MIB = 1024 * 1024


class MemoryEventWriter:
    def __init__(self) -> None:
        self.records: list[tuple[SessionScope, OperationalEvent]] = []

    def record(
        self,
        *,
        scope: SessionScope,
        event: OperationalEvent,
    ) -> OperationalEvent:
        self.records.append((scope, event))
        return event


def stage(**changes: object) -> StageMeasurement:
    values = {
        "scope": SessionScope(owner_id="own_alpha", session_id="ses_alpha"),
        "job_id": "job_alpha",
        "stage": "profiling",
        "attempt_number": 1,
        "started_at": NOW,
        "queued_at": NOW - timedelta(milliseconds=125),
        "fact_package_id": None,
        "report_bundle_id": None,
        "dataset_size_bytes": 10 * MIB,
    }
    values.update(changes)
    return StageMeasurement(**values)  # type: ignore[arg-type]


def service(writer: MemoryEventWriter) -> OperationalTelemetryService:
    event_ids = iter(("evt_started", "evt_terminal", "evt_extra"))
    return OperationalTelemetryService(writer=writer, new_event_id=lambda: next(event_ids))


def test_stage_start_records_queue_time_and_a_bounded_dataset_size() -> None:
    writer = MemoryEventWriter()
    measurement = stage(fact_package_id="fct_alpha")

    event = service(writer).start(measurement)

    assert writer.records == [(measurement.scope, event)]
    assert event == OperationalEvent(
        event_id="evt_started",
        session_id="ses_alpha",
        job_id="job_alpha",
        fact_package_id="fct_alpha",
        report_bundle_id=None,
        stage="profiling",
        transition=TRANSITION_STARTED,
        attempt_number=1,
        recorded_at=NOW,
        duration_ms=None,
        queue_time_ms=125,
        provider_latency_ms=None,
        dataset_size_band="le_10_mib",
        output_size_bytes=None,
    )


def test_terminal_stage_records_elapsed_time_and_output_size() -> None:
    writer = MemoryEventWriter()
    telemetry = service(writer)
    measurement = stage(report_bundle_id="bnd_alpha")
    telemetry.start(measurement)

    terminal = telemetry.finish(
        measurement,
        StageCompletion(
            transition=TRANSITION_SUCCEEDED,
            completed_at=NOW + timedelta(milliseconds=25),
            output_size_bytes=2048,
        ),
    )

    assert terminal.transition == TRANSITION_SUCCEEDED
    assert terminal.duration_ms == 25
    assert terminal.queue_time_ms is None
    assert terminal.output_size_bytes == 2048
    assert terminal.dataset_size_band == "le_10_mib"
    assert [event.event_id for _, event in writer.records] == [
        "evt_started",
        "evt_terminal",
    ]


@pytest.mark.parametrize("transition", [TRANSITION_FAILED, TRANSITION_REFUSED])
def test_terminal_failures_and_refusals_are_content_free(transition: str) -> None:
    writer = MemoryEventWriter()

    terminal = service(writer).finish(
        stage(),
        StageCompletion(
            transition=transition,
            completed_at=NOW + timedelta(milliseconds=5),
        ),
    )

    assert terminal.transition == transition
    assert terminal.duration_ms == 5
    assert not hasattr(terminal, "error_message")


def test_provider_latency_is_derived_only_for_narrative_generation() -> None:
    writer = MemoryEventWriter()

    terminal = service(writer).finish(
        stage(stage="narrative_generation"),
        StageCompletion(
            transition=TRANSITION_SUCCEEDED,
            completed_at=NOW + timedelta(milliseconds=40),
            provider_started_at=NOW + timedelta(milliseconds=10),
        ),
    )

    assert terminal.provider_latency_ms == 30


@pytest.mark.parametrize(
    ("size_bytes", "expected"),
    [
        (0, "le_1_mib"),
        (MIB, "le_1_mib"),
        (MIB + 1, "le_10_mib"),
        (10 * MIB + 1, "le_25_mib"),
        (25 * MIB + 1, "le_50_mib"),
    ],
)
def test_dataset_size_is_reduced_to_an_approved_band(
    size_bytes: int,
    expected: str,
) -> None:
    event = service(MemoryEventWriter()).start(stage(dataset_size_bytes=size_bytes))

    assert event.dataset_size_band == expected


@pytest.mark.parametrize(
    "measurement",
    [
        stage(queued_at=NOW + timedelta(milliseconds=1)),
        stage(dataset_size_bytes=-1),
        stage(dataset_size_bytes=50 * MIB + 1),
    ],
)
def test_invalid_stage_measurements_fail_closed(measurement: StageMeasurement) -> None:
    with pytest.raises(ValueError):
        service(MemoryEventWriter()).start(measurement)


def test_invalid_terminal_measurements_fail_closed() -> None:
    telemetry = service(MemoryEventWriter())

    with pytest.raises(ValueError):
        telemetry.finish(
            stage(),
            StageCompletion(
                transition=TRANSITION_STARTED,
                completed_at=NOW + timedelta(milliseconds=1),
            ),
        )
    with pytest.raises(ValueError):
        telemetry.finish(
            stage(),
            StageCompletion(
                transition=TRANSITION_SUCCEEDED,
                completed_at=NOW - timedelta(milliseconds=1),
            ),
        )
    with pytest.raises(ValueError):
        telemetry.finish(
            stage(),
            StageCompletion(
                transition=TRANSITION_SUCCEEDED,
                completed_at=NOW + timedelta(milliseconds=1),
                provider_started_at=NOW,
            ),
        )


def test_stage_measurement_has_no_customer_content_fields() -> None:
    names = {
        field.name
        for record_type in (StageMeasurement, StageCompletion)
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
