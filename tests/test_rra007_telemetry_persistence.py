from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.jobs import EnqueueJob
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.sessions import CrossSessionAccessDenied, InvitationService, SessionScope
from khepri.rra.telemetry import OperationalEvent
from khepri.rra.telemetry_persistence import (
    OperationalEventRow,
    SqlOperationalEventRepository,
)

NOW = datetime(2026, 7, 30, 14, 0, tzinfo=UTC)
IDEMPOTENCY_KEY = "8f99c79c1c79c892c1a30a74fcc1b536b04e409ee4562acfb82d8d76fb750d7d"


def repositories() -> tuple[SqlOperationalEventRepository, SessionScope]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = SqlSessionStore(factory)
    invitations = InvitationService(sessions)
    beta_session = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
        now=NOW,
    )
    scope = SessionScope(
        owner_id=beta_session.owner_id,
        session_id=beta_session.session_id,
    )
    SqlReportJobRepository(factory).enqueue(
        EnqueueJob(
            scope=scope,
            job_id="job_alpha",
            idempotency_key=IDEMPOTENCY_KEY,
            queued_at=NOW,
            max_attempts=3,
        )
    )
    return SqlOperationalEventRepository(factory), scope


def event(
    *,
    event_id: str = "evt_alpha",
    session_id: str = "ses_placeholder",
) -> OperationalEvent:
    return OperationalEvent(
        event_id=event_id,
        session_id=session_id,
        job_id="job_alpha",
        fact_package_id="fct_alpha",
        report_bundle_id="bnd_alpha",
        stage="narrative_generation",
        transition="succeeded",
        attempt_number=1,
        recorded_at=NOW,
        duration_ms=25,
        queue_time_ms=5,
        provider_latency_ms=12,
        dataset_size_band="le_10_mib",
        output_size_bytes=2048,
    )


def test_operational_event_roundtrips_without_customer_content_columns() -> None:
    telemetry, scope = repositories()
    measured = event(session_id=scope.session_id)

    stored = telemetry.record(scope=scope, event=measured)

    assert stored == measured
    assert telemetry.list_for_job(scope=scope, job_id="job_alpha") == [measured]
    columns = set(inspect(OperationalEventRow).columns.keys())
    assert {
        "payload",
        "message",
        "filename",
        "label",
        "narrative",
        "source_value",
        "token",
        "object_location",
    }.isdisjoint(columns)


def test_duplicate_stage_transition_returns_the_original_event() -> None:
    telemetry, scope = repositories()
    measured = event(session_id=scope.session_id)
    original = telemetry.record(scope=scope, event=measured)
    duplicate = replace(
        measured,
        event_id="evt_duplicate",
        recorded_at=NOW + timedelta(seconds=1),
        duration_ms=999,
    )

    result = telemetry.record(scope=scope, event=duplicate)

    assert result == original
    assert telemetry.list_for_job(scope=scope, job_id="job_alpha") == [original]


def test_event_cannot_be_attached_outside_the_job_session() -> None:
    telemetry, scope = repositories()
    mismatched = event(session_id="ses_other")

    with pytest.raises(CrossSessionAccessDenied):
        telemetry.record(scope=scope, event=mismatched)


def test_operational_events_cannot_be_read_outside_the_job_session() -> None:
    telemetry, scope = repositories()
    telemetry.record(scope=scope, event=event(session_id=scope.session_id))
    foreign_scope = SessionScope(owner_id="own_other", session_id="ses_other")

    with pytest.raises(CrossSessionAccessDenied):
        telemetry.list_for_job(scope=foreign_scope, job_id="job_alpha")
