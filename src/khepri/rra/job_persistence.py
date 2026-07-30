from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import (
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
from sqlalchemy.sql import Select

from khepri.rra.jobs import (
    ATTEMPT_LEASE_RECLAIMED,
    ATTEMPT_RETRIES_EXHAUSTED,
    ATTEMPT_RETRY_SCHEDULED,
    DEAD_LETTER_CONTENT_DELETED,
    DEAD_LETTER_RETRIES_EXHAUSTED,
    JOB_DEAD_LETTERED,
    JOB_QUEUED,
    JOB_RETRYABLE,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    EnqueueJob,
    FailureRequest,
    JobAttempt,
    LeaseAction,
    LeaseLost,
    LeaseRequest,
    ReportJob,
    orphanable,
)
from khepri.rra.persistence import (
    Base,
    BetaSessionRow,
    _utc,
    session_scope_for_update_statement,
)
from khepri.rra.sessions import CrossSessionAccessDenied, SessionScope


class ReportJobRow(Base):
    __tablename__ = "rra_report_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ("
            "'queued', 'running', 'retryable', 'succeeded', 'dead_lettered'"
            ")",
            name="ck_report_job_state",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_report_job_attempt_count"),
        CheckConstraint("max_attempts > 0", name="ck_report_job_max_attempts"),
        CheckConstraint(
            "length(idempotency_key) = 64",
            name="ck_report_job_idempotency_digest",
        ),
        CheckConstraint(
            "available_at >= queued_at",
            name="ck_report_job_availability",
        ),
        CheckConstraint(
            "attempt_count <= max_attempts",
            name="ck_report_job_attempt_limit",
        ),
        CheckConstraint(
            "(state = 'running') = "
            "(lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_report_job_lease",
        ),
        CheckConstraint(
            "(state IN ('succeeded', 'dead_lettered')) = (completed_at IS NOT NULL)",
            name="ck_report_job_completion",
        ),
        CheckConstraint(
            "(state = 'dead_lettered') = (dead_letter_reason IS NOT NULL)",
            name="ck_report_job_dead_letter",
        ),
        CheckConstraint(
            "dead_letter_reason IS NULL OR dead_letter_reason IN ("
            "'retries_exhausted', 'content_deleted'"
            ")",
            name="ck_report_job_dead_letter_reason",
        ),
        UniqueConstraint(
            "session_id",
            "idempotency_key",
            name="uq_report_job_session_idempotency",
        ),
        UniqueConstraint(
            "job_id",
            "session_id",
            name="uq_report_job_session_scope",
        ),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_report_job_session_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_report_job_available", "state", "available_at"),
        Index("ix_report_job_lease_expiry", "lease_expires_at"),
        Index("ix_report_job_session_state", "session_id", "state"),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dead_letter_reason: Mapped[str | None] = mapped_column(String)


class ReportJobAttemptRow(Base):
    __tablename__ = "rra_report_job_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="ck_job_attempt_number"),
        CheckConstraint(
            "disposition IN ("
            "'retry_scheduled', 'lease_reclaimed', 'retries_exhausted'"
            ")",
            name="ck_job_attempt_disposition",
        ),
        CheckConstraint(
            "(disposition = 'retries_exhausted') = (available_at IS NULL)",
            name="ck_job_attempt_availability",
        ),
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["rra_report_jobs.job_id", "rra_report_jobs.session_id"],
            name="fk_job_attempt_job_scope",
            ondelete="RESTRICT",
        ),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    attempt_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    disposition: Mapped[str] = mapped_column(String, nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SqlReportJobRepository:
    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def enqueue(self, request: EnqueueJob) -> ReportJob:
        self._validate_enqueue(request)
        try:
            return self._insert_or_get(request)
        except IntegrityError:
            with self._factory() as database:
                row = self._existing(database, request)
                if row is None:
                    raise
                return _report_job_from_row(row)

    def lease(self, request: LeaseRequest) -> ReportJob | None:
        _require_positive_lease(request.lease_for)
        statement = (
            select(ReportJobRow)
            .where(
                ReportJobRow.job_id == request.job_id,
                ReportJobRow.state.in_((JOB_QUEUED, JOB_RETRYABLE)),
                ReportJobRow.available_at <= request.now,
                ReportJobRow.attempt_count < ReportJobRow.max_attempts,
            )
            .with_for_update()
        )
        with self._factory.begin() as database:
            row = database.scalar(statement)
            if row is None:
                return None
            row.state = JOB_RUNNING
            row.attempt_count += 1
            row.lease_owner = request.worker_id
            row.lease_expires_at = request.now + request.lease_for
            database.flush()
            return _report_job_from_row(row)

    def recover_expired(self, *, now: datetime) -> tuple[ReportJob, ...]:
        statement = (
            select(ReportJobRow)
            .where(
                ReportJobRow.state == JOB_RUNNING,
                ReportJobRow.lease_expires_at <= now,
            )
            .order_by(ReportJobRow.lease_expires_at, ReportJobRow.job_id)
            .with_for_update(skip_locked=True)
        )
        with self._factory.begin() as database:
            rows = list(database.scalars(statement))
            for row in rows:
                self._reclaim(database, row, now=now)
            database.flush()
            return tuple(_report_job_from_row(row) for row in rows)

    def recover_orphans(self, *, now: datetime) -> tuple[ReportJob, ...]:
        """Dead-letter unfinished jobs whose session content is already deleted."""
        statement = (
            select(ReportJobRow)
            .where(
                ReportJobRow.session_id.in_(_deleted_content_sessions()),
                ReportJobRow.state.not_in((JOB_SUCCEEDED, JOB_DEAD_LETTERED)),
            )
            .order_by(ReportJobRow.queued_at, ReportJobRow.job_id)
            .with_for_update(skip_locked=True)
        )
        with self._factory.begin() as database:
            candidates = list(database.scalars(statement))
            orphans = [row for row in candidates if orphanable(row.state)]
            for row in orphans:
                self._orphan(row, now=now)
            database.flush()
            return tuple(_report_job_from_row(row) for row in orphans)

    def list_attempts(
        self,
        *,
        scope: SessionScope,
        job_id: str,
    ) -> tuple[JobAttempt, ...]:
        statement = (
            select(ReportJobAttemptRow)
            .where(ReportJobAttemptRow.job_id == job_id)
            .order_by(ReportJobAttemptRow.attempt_number)
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
            return tuple(
                _attempt_from_row(row) for row in database.scalars(statement)
            )

    def fail(self, request: FailureRequest) -> ReportJob:
        with self._factory.begin() as database:
            row = self._active_lease(database, request.lease)
            released_at = request.lease.now
            if row.attempt_count >= row.max_attempts:
                outcome = self._exhaust(row, now=released_at)
            elif request.retry_at <= released_at:
                raise ValueError("Retry time must be in the future.")
            else:
                outcome = self._reschedule(
                    row,
                    available_at=request.retry_at,
                    disposition=ATTEMPT_RETRY_SCHEDULED,
                )
            self._release(row)
            self._record_attempt(database, row, released_at=released_at, outcome=outcome)
            database.flush()
            return _report_job_from_row(row)

    def complete(self, request: LeaseAction) -> ReportJob:
        with self._factory.begin() as database:
            row = self._active_lease(database, request)
            row.state = JOB_SUCCEEDED
            row.completed_at = request.now
            self._release(row)
            database.flush()
            return _report_job_from_row(row)

    def heartbeat(self, request: LeaseRequest) -> ReportJob:
        _require_positive_lease(request.lease_for)
        action = LeaseAction(
            job_id=request.job_id,
            worker_id=request.worker_id,
            now=request.now,
        )
        with self._factory.begin() as database:
            row = self._active_lease(database, action)
            row.lease_expires_at = request.now + request.lease_for
            database.flush()
            return _report_job_from_row(row)

    def _insert_or_get(self, request: EnqueueJob) -> ReportJob:
        with self._factory.begin() as database:
            session_row = database.scalar(
                session_scope_for_update_statement(request.scope)
            )
            if session_row is None:
                raise CrossSessionAccessDenied("Resource is unavailable.")
            existing = self._existing(database, request)
            if existing is not None:
                return _report_job_from_row(existing)
            row = _new_job_row(request)
            database.add(row)
            database.flush()
            return _report_job_from_row(row)

    @staticmethod
    def _existing(database: Session, request: EnqueueJob) -> ReportJobRow | None:
        return database.scalar(
            select(ReportJobRow).where(
                ReportJobRow.session_id == request.scope.session_id,
                ReportJobRow.idempotency_key == request.idempotency_key,
            )
        )

    @staticmethod
    def _active_lease(database: Session, request: LeaseAction) -> ReportJobRow:
        row = database.scalar(
            select(ReportJobRow)
            .where(
                ReportJobRow.job_id == request.job_id,
                ReportJobRow.state == JOB_RUNNING,
                ReportJobRow.lease_owner == request.worker_id,
                ReportJobRow.lease_expires_at > request.now,
            )
            .with_for_update()
        )
        if row is None:
            raise LeaseLost("Report job lease is unavailable.")
        return row

    @staticmethod
    def _validate_enqueue(request: EnqueueJob) -> None:
        if len(request.idempotency_key) != 64:
            raise ValueError("Idempotency key must be a SHA-256 digest.")
        if request.max_attempts <= 0:
            raise ValueError("Maximum attempts must be positive.")

    def _reclaim(
        self,
        database: Session,
        row: ReportJobRow,
        *,
        now: datetime,
    ) -> None:
        if row.attempt_count >= row.max_attempts:
            outcome = self._exhaust(row, now=now)
        else:
            outcome = self._reschedule(
                row,
                available_at=now,
                disposition=ATTEMPT_LEASE_RECLAIMED,
            )
        self._release(row)
        self._record_attempt(database, row, released_at=now, outcome=outcome)

    @staticmethod
    def _exhaust(row: ReportJobRow, *, now: datetime) -> tuple[str, None]:
        row.state = JOB_DEAD_LETTERED
        row.dead_letter_reason = DEAD_LETTER_RETRIES_EXHAUSTED
        row.completed_at = now
        return ATTEMPT_RETRIES_EXHAUSTED, None

    @staticmethod
    def _reschedule(
        row: ReportJobRow,
        *,
        available_at: datetime,
        disposition: str,
    ) -> tuple[str, datetime]:
        row.state = JOB_RETRYABLE
        row.available_at = available_at
        row.completed_at = None
        return disposition, available_at

    @staticmethod
    def _record_attempt(
        database: Session,
        row: ReportJobRow,
        *,
        released_at: datetime,
        outcome: tuple[str, datetime | None],
    ) -> None:
        disposition, available_at = outcome
        database.add(
            ReportJobAttemptRow(
                job_id=row.job_id,
                session_id=row.session_id,
                attempt_number=row.attempt_count,
                released_at=released_at,
                disposition=disposition,
                available_at=available_at,
            )
        )

    def _orphan(self, row: ReportJobRow, *, now: datetime) -> None:
        row.state = JOB_DEAD_LETTERED
        row.dead_letter_reason = DEAD_LETTER_CONTENT_DELETED
        row.completed_at = now
        self._release(row)

    @staticmethod
    def _release(row: ReportJobRow) -> None:
        row.lease_owner = None
        row.lease_expires_at = None


def _new_job_row(request: EnqueueJob) -> ReportJobRow:
    return ReportJobRow(
        job_id=request.job_id,
        owner_id=request.scope.owner_id,
        session_id=request.scope.session_id,
        idempotency_key=request.idempotency_key,
        state=JOB_QUEUED,
        queued_at=request.queued_at,
        available_at=request.queued_at,
        attempt_count=0,
        max_attempts=request.max_attempts,
        lease_owner=None,
        lease_expires_at=None,
        completed_at=None,
        dead_letter_reason=None,
    )


def _deleted_content_sessions() -> Select[tuple[str]]:
    return select(BetaSessionRow.session_id).where(
        BetaSessionRow.content_deleted_at.is_not(None)
    )


def _attempt_from_row(row: ReportJobAttemptRow) -> JobAttempt:
    return JobAttempt(
        job_id=row.job_id,
        session_id=row.session_id,
        attempt_number=row.attempt_number,
        released_at=_utc(row.released_at),
        disposition=row.disposition,
        available_at=_utc(row.available_at),
    )


def _report_job_from_row(row: ReportJobRow) -> ReportJob:
    return ReportJob(
        job_id=row.job_id,
        owner_id=row.owner_id,
        session_id=row.session_id,
        idempotency_key=row.idempotency_key,
        state=row.state,
        queued_at=_utc(row.queued_at),
        available_at=_utc(row.available_at),
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        lease_owner=row.lease_owner,
        lease_expires_at=_utc(row.lease_expires_at),
        completed_at=_utc(row.completed_at),
        dead_letter_reason=row.dead_letter_reason,
    )


def _require_positive_lease(lease_for: timedelta) -> None:
    if lease_for <= timedelta(0):
        raise ValueError("Lease duration must be positive.")
