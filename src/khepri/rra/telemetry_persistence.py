from __future__ import annotations

from dataclasses import fields
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.persistence import Base, _utc
from khepri.rra.sessions import CrossSessionAccessDenied, SessionScope
from khepri.rra.telemetry import OperationalEvent


class OperationalEventRow(Base):
    __tablename__ = "rra_operational_events"
    __table_args__ = (
        CheckConstraint(
            "stage IN ("
            "'upload_validation', 'materialization', 'profiling', 'mapping', "
            "'fact_calculation', 'narrative_generation', 'chart_rendering', "
            "'pdf_generation', 'excel_generation', 'storage', 'delivery'"
            ")",
            name="ck_operational_event_stage",
        ),
        CheckConstraint(
            "transition IN ('started', 'succeeded', 'failed', 'refused')",
            name="ck_operational_event_transition",
        ),
        CheckConstraint(
            "(transition = 'started') = (duration_ms IS NULL)",
            name="ck_operational_event_duration",
        ),
        CheckConstraint(
            "attempt_number > 0",
            name="ck_operational_event_attempt",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_operational_event_duration_nonnegative",
        ),
        CheckConstraint(
            "queue_time_ms IS NULL OR queue_time_ms >= 0",
            name="ck_operational_event_queue_nonnegative",
        ),
        CheckConstraint(
            "provider_latency_ms IS NULL OR provider_latency_ms >= 0",
            name="ck_operational_event_provider_nonnegative",
        ),
        CheckConstraint(
            "output_size_bytes IS NULL OR output_size_bytes >= 0",
            name="ck_operational_event_output_nonnegative",
        ),
        CheckConstraint(
            "dataset_size_band IS NULL OR dataset_size_band IN "
            "('le_1_mib', 'le_10_mib', 'le_25_mib', 'le_50_mib')",
            name="ck_operational_event_dataset_band",
        ),
        CheckConstraint(
            "provider_latency_ms IS NULL OR stage = 'narrative_generation'",
            name="ck_operational_event_provider_stage",
        ),
        UniqueConstraint(
            "job_id",
            "attempt_number",
            "stage",
            "transition",
            name="uq_operational_event_transition",
        ),
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["rra_report_jobs.job_id", "rra_report_jobs.session_id"],
            name="fk_operational_event_job_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_operational_event_job_time",
            "job_id",
            "recorded_at",
        ),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    fact_package_id: Mapped[str | None] = mapped_column(String)
    report_bundle_id: Mapped[str | None] = mapped_column(String)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    transition: Mapped[str] = mapped_column(String, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)
    queue_time_ms: Mapped[int | None] = mapped_column(BigInteger)
    provider_latency_ms: Mapped[int | None] = mapped_column(BigInteger)
    dataset_size_band: Mapped[str | None] = mapped_column(String)
    output_size_bytes: Mapped[int | None] = mapped_column(BigInteger)


class SqlOperationalEventRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def record(
        self,
        *,
        scope: SessionScope,
        event: OperationalEvent,
    ) -> OperationalEvent:
        try:
            return self._insert_or_get(scope=scope, event=event)
        except IntegrityError:
            with self._factory() as database:
                row = self._existing(database, event)
                if row is None:
                    raise
                return _event_from_row(row)

    def _insert_or_get(
        self,
        *,
        scope: SessionScope,
        event: OperationalEvent,
    ) -> OperationalEvent:
        with self._factory.begin() as database:
            self._require_job_scope(database, scope=scope, event=event)
            existing = self._existing(database, event)
            if existing is not None:
                return _event_from_row(existing)
            row = _event_row(event)
            database.add(row)
            database.flush()
            return _event_from_row(row)

    def list_for_job(
        self,
        *,
        scope: SessionScope,
        job_id: str,
    ) -> list[OperationalEvent]:
        statement = (
            select(OperationalEventRow)
            .where(OperationalEventRow.job_id == job_id)
            .order_by(
                OperationalEventRow.attempt_number,
                OperationalEventRow.recorded_at,
                OperationalEventRow.event_id,
            )
        )
        with self._factory() as database:
            job = database.scalar(
                select(ReportJobRow).where(
                    ReportJobRow.job_id == job_id,
                    ReportJobRow.owner_id == scope.owner_id,
                    ReportJobRow.session_id == scope.session_id,
                )
            )
            if job is None:
                raise CrossSessionAccessDenied("Resource is unavailable.")
            return [_event_from_row(row) for row in database.scalars(statement)]

    @staticmethod
    def _require_job_scope(
        database: Session,
        *,
        scope: SessionScope,
        event: OperationalEvent,
    ) -> None:
        row = database.scalar(
            select(ReportJobRow)
            .where(
                ReportJobRow.job_id == event.job_id,
                ReportJobRow.owner_id == scope.owner_id,
                ReportJobRow.session_id == scope.session_id,
                ReportJobRow.session_id == event.session_id,
            )
            .with_for_update()
        )
        if row is None:
            raise CrossSessionAccessDenied("Resource is unavailable.")

    @staticmethod
    def _existing(
        database: Session,
        event: OperationalEvent,
    ) -> OperationalEventRow | None:
        return database.scalar(
            select(OperationalEventRow).where(
                OperationalEventRow.job_id == event.job_id,
                OperationalEventRow.attempt_number == event.attempt_number,
                OperationalEventRow.stage == event.stage,
                OperationalEventRow.transition == event.transition,
            )
        )


_EVENT_FIELDS = tuple(field.name for field in fields(OperationalEvent))


def _event_values(
    source: OperationalEvent | OperationalEventRow,
) -> dict[str, object]:
    return {name: getattr(source, name) for name in _EVENT_FIELDS}


def _event_row(event: OperationalEvent) -> OperationalEventRow:
    return OperationalEventRow(**_event_values(event))


def _event_from_row(row: OperationalEventRow) -> OperationalEvent:
    values = _event_values(row)
    values["recorded_at"] = _utc(row.recorded_at)
    return OperationalEvent(**values)  # type: ignore[arg-type]
