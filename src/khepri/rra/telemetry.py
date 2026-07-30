from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

TRANSITION_STARTED = "started"
TRANSITION_SUCCEEDED = "succeeded"
TRANSITION_FAILED = "failed"
TRANSITION_REFUSED = "refused"

STAGES = frozenset(
    {
        "upload_validation",
        "materialization",
        "profiling",
        "mapping",
        "fact_calculation",
        "narrative_generation",
        "chart_rendering",
        "pdf_generation",
        "excel_generation",
        "storage",
        "delivery",
    }
)
TRANSITIONS = frozenset(
    {
        TRANSITION_STARTED,
        TRANSITION_SUCCEEDED,
        TRANSITION_FAILED,
        TRANSITION_REFUSED,
    }
)
DATASET_SIZE_BANDS = frozenset(
    {
        "le_1_mib",
        "le_10_mib",
        "le_25_mib",
        "le_50_mib",
    }
)


@dataclass(frozen=True, slots=True)
class OperationalEvent:
    event_id: str
    session_id: str
    job_id: str
    fact_package_id: str | None
    report_bundle_id: str | None
    stage: str
    transition: str
    attempt_number: int
    recorded_at: datetime
    duration_ms: int | None
    queue_time_ms: int | None
    provider_latency_ms: int | None
    dataset_size_band: str | None
    output_size_bytes: int | None

    @property
    def retry_count(self) -> int:
        return self.attempt_number - 1

    def __post_init__(self) -> None:
        self._validate_vocabulary()
        self._validate_measurements()
        self._validate_data_boundaries()
        self._validate_duration()

    def _validate_vocabulary(self) -> None:
        if self.stage not in STAGES:
            raise ValueError("Unknown telemetry stage.")
        if self.transition not in TRANSITIONS:
            raise ValueError("Unknown telemetry transition.")

    def _validate_duration(self) -> None:
        if self.transition == TRANSITION_STARTED and self.duration_ms is not None:
            raise ValueError("A started transition cannot have a duration.")
        if self.transition != TRANSITION_STARTED and self.duration_ms is None:
            raise ValueError("A terminal transition requires a measured duration.")

    def _validate_measurements(self) -> None:
        if self.attempt_number <= 0:
            raise ValueError("attempt_number must be positive.")
        measurements = {
            "duration_ms": self.duration_ms,
            "queue_time_ms": self.queue_time_ms,
            "provider_latency_ms": self.provider_latency_ms,
            "output_size_bytes": self.output_size_bytes,
        }
        for name, value in measurements.items():
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative.")

    def _validate_data_boundaries(self) -> None:
        if (
            self.dataset_size_band is not None
            and self.dataset_size_band not in DATASET_SIZE_BANDS
        ):
            raise ValueError("Unknown dataset_size_band.")
        if (
            self.provider_latency_ms is not None
            and self.stage != "narrative_generation"
        ):
            raise ValueError(
                "provider_latency_ms is restricted to narrative generation."
            )
