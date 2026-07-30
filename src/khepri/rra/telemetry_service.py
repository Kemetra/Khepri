from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from khepri.rra.sessions import SessionScope
from khepri.rra.telemetry import (
    TRANSITION_FAILED,
    TRANSITION_REFUSED,
    TRANSITION_STARTED,
    TRANSITION_SUCCEEDED,
    OperationalEvent,
)

_MIB = 1024 * 1024
_DATASET_SIZE_BANDS = (
    (_MIB, "le_1_mib"),
    (10 * _MIB, "le_10_mib"),
    (25 * _MIB, "le_25_mib"),
    (50 * _MIB, "le_50_mib"),
)
_TERMINAL_TRANSITIONS = frozenset(
    {
        TRANSITION_SUCCEEDED,
        TRANSITION_FAILED,
        TRANSITION_REFUSED,
    }
)


@dataclass(frozen=True, slots=True)
class StageMeasurement:
    scope: SessionScope
    job_id: str
    stage: str
    attempt_number: int
    started_at: datetime
    queued_at: datetime | None = None
    fact_package_id: str | None = None
    report_bundle_id: str | None = None
    dataset_size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class StageCompletion:
    transition: str
    completed_at: datetime
    provider_started_at: datetime | None = None
    output_size_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class _EventMetrics:
    transition: str
    recorded_at: datetime
    duration_ms: int | None
    queue_time_ms: int | None
    provider_latency_ms: int | None
    output_size_bytes: int | None


class OperationalEventWriter(Protocol):
    def record(
        self,
        *,
        scope: SessionScope,
        event: OperationalEvent,
    ) -> OperationalEvent: ...


class OperationalTelemetryService:
    def __init__(
        self,
        *,
        writer: OperationalEventWriter,
        new_event_id: Callable[[], str] | None = None,
    ) -> None:
        self._writer = writer
        self._new_event_id = new_event_id or (
            lambda: f"evt_{secrets.token_urlsafe(18)}"
        )

    def start(self, measurement: StageMeasurement) -> OperationalEvent:
        queue_time_ms = (
            None
            if measurement.queued_at is None
            else _elapsed_ms(measurement.queued_at, measurement.started_at)
        )
        return self._record(
            measurement,
            _EventMetrics(
                transition=TRANSITION_STARTED,
                recorded_at=measurement.started_at,
                duration_ms=None,
                queue_time_ms=queue_time_ms,
                provider_latency_ms=None,
                output_size_bytes=None,
            ),
        )

    def finish(
        self,
        measurement: StageMeasurement,
        completion: StageCompletion,
    ) -> OperationalEvent:
        if completion.transition not in _TERMINAL_TRANSITIONS:
            raise ValueError("A terminal telemetry transition is required.")
        provider_latency_ms = self._provider_latency(
            measurement,
            provider_started_at=completion.provider_started_at,
            completed_at=completion.completed_at,
        )
        return self._record(
            measurement,
            _EventMetrics(
                transition=completion.transition,
                recorded_at=completion.completed_at,
                duration_ms=_elapsed_ms(measurement.started_at, completion.completed_at),
                queue_time_ms=None,
                provider_latency_ms=provider_latency_ms,
                output_size_bytes=completion.output_size_bytes,
            ),
        )

    def _record(
        self,
        measurement: StageMeasurement,
        metrics: _EventMetrics,
    ) -> OperationalEvent:
        event = OperationalEvent(
            event_id=self._new_event_id(),
            session_id=measurement.scope.session_id,
            job_id=measurement.job_id,
            fact_package_id=measurement.fact_package_id,
            report_bundle_id=measurement.report_bundle_id,
            stage=measurement.stage,
            transition=metrics.transition,
            attempt_number=measurement.attempt_number,
            recorded_at=metrics.recorded_at,
            duration_ms=metrics.duration_ms,
            queue_time_ms=metrics.queue_time_ms,
            provider_latency_ms=metrics.provider_latency_ms,
            dataset_size_band=_dataset_size_band(measurement.dataset_size_bytes),
            output_size_bytes=metrics.output_size_bytes,
        )
        return self._writer.record(scope=measurement.scope, event=event)

    @staticmethod
    def _provider_latency(
        measurement: StageMeasurement,
        *,
        provider_started_at: datetime | None,
        completed_at: datetime,
    ) -> int | None:
        if provider_started_at is None:
            return None
        if provider_started_at < measurement.started_at:
            raise ValueError("Provider timing cannot precede the stage.")
        return _elapsed_ms(provider_started_at, completed_at)


def _dataset_size_band(size_bytes: int | None) -> str | None:
    if size_bytes is None:
        return None
    if size_bytes < 0:
        raise ValueError("Dataset size must be non-negative.")
    for maximum, band in _DATASET_SIZE_BANDS:
        if size_bytes <= maximum:
            return band
    raise ValueError("Dataset size exceeds the approved beta boundary.")


def _elapsed_ms(started_at: datetime, completed_at: datetime) -> int:
    elapsed = completed_at - started_at
    if elapsed < timedelta(0):
        raise ValueError("Telemetry timestamps are out of order.")
    microseconds = elapsed // timedelta(microseconds=1)
    return (microseconds + 999) // 1000
