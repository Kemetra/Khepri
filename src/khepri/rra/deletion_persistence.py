"""Small SQL helpers for resolving and removing deletion targets."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.deletion import DeletionEvidence, DeletionTarget
from khepri.rra.persistence import (
    DatasetProfileRow,
    DeletionEvidenceRow,
    DeletionJobRow,
    FactPackageRow,
    UploadRow,
    _utc,
)
from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS

if TYPE_CHECKING:
    from khepri.rra.job_persistence import ReportJobRow

# How long an exhausted publisher is assumed to still be capable of writing. It
# matches the deletion retry delay so that the sweep which runs once the deferral
# elapses is the one that finds the drain served.
_DRAIN_INTERVAL = timedelta(minutes=5)


def defer_for_publication(
    database: Session,
    deletion: DeletionJobRow,
    *,
    now: datetime,
    next_retry_at: datetime,
) -> bool:
    from khepri.rra.job_persistence import ReportJobRow  # noqa: PLC0415
    from khepri.rra.jobs import JOB_DEAD_LETTERED, JOB_SUCCEEDED  # noqa: PLC0415

    report_jobs = list(
        database.scalars(
            select(ReportJobRow)
            .where(ReportJobRow.session_id == deletion.session_id)
            .with_for_update()
        )
    )
    _settle_unleased(report_jobs, completed_at=deletion.requested_at)
    if _needs_drain(deletion, report_jobs, now=now):
        return _defer_drain(deletion, next_retry_at=next_retry_at)
    terminal = {JOB_SUCCEEDED, JOB_DEAD_LETTERED}
    if all(candidate.state in terminal for candidate in report_jobs):
        return False
    return _defer(deletion, next_retry_at=next_retry_at)


def _settle_unleased(
    report_jobs: list[ReportJobRow],
    *,
    completed_at: datetime,
) -> None:
    from khepri.rra.jobs import (  # noqa: PLC0415
        DEAD_LETTER_CONTENT_DELETED,
        JOB_DEAD_LETTERED,
        orphanable,
    )

    for candidate in report_jobs:
        if orphanable(candidate.state):
            candidate.state = JOB_DEAD_LETTERED
            candidate.dead_letter_reason = DEAD_LETTER_CONTENT_DELETED
            candidate.completed_at = completed_at


def _needs_drain(
    deletion: DeletionJobRow,
    report_jobs: list[ReportJobRow],
    *,
    now: datetime,
) -> bool:
    """Whether an exhausted publisher could still be writing.

    The interval is measured from the moment exhaustion was recorded, never from
    the deletion's own `next_retry_at`. That field answers a different question --
    when to look again -- and it is already set whenever deletion was deferred for
    a publisher that was still running. Reading it as a drain would let a deferral
    taken against a live worker be spent before that worker ever became terminal,
    so the sweep that first observes the transition would sweep immediately and an
    in-flight object write could land after it.
    """
    from khepri.rra.jobs import DEAD_LETTER_RETRIES_EXHAUSTED  # noqa: PLC0415

    if deletion.attempt_count > 0:
        return False
    exhausted_at = [
        _utc(candidate.completed_at)
        for candidate in report_jobs
        if candidate.dead_letter_reason == DEAD_LETTER_RETRIES_EXHAUSTED
    ]
    if not exhausted_at:
        return False
    # An unrecorded transition time cannot be shown to have drained.
    return any(
        observed is None or observed + _DRAIN_INTERVAL > now for observed in exhausted_at
    )


def _defer(deletion: DeletionJobRow, *, next_retry_at: datetime) -> bool:
    deletion.state = "retryable"
    deletion.next_retry_at = next_retry_at
    return True


def _defer_drain(deletion: DeletionJobRow, *, next_retry_at: datetime) -> bool:
    """Hold the deletion until the drain interval has run.

    The deadline is pushed forward rather than kept, because a deadline recorded
    while the publisher was still running has no bearing on when its drain ends.
    Keeping the earlier value would let the very next sweep proceed.
    """
    retry_at = _utc(deletion.next_retry_at)
    if retry_at is None or retry_at < next_retry_at:
        _defer(deletion, next_retry_at=next_retry_at)
    return True


def deletion_targets(
    database: Session,
    owner_id: str,
    session_id: str,
) -> tuple[DeletionTarget, ...]:
    upload = _upload_target(database, owner_id, session_id)
    artifacts = _artifact_targets(database, owner_id, session_id)
    return (() if upload is None else (upload,)) + artifacts


def delete_derived_content(
    database: Session,
    owner_id: str,
    session_id: str,
) -> None:
    for model in (FactPackageRow, DatasetProfileRow):
        _delete_scoped(database, model, owner_id, session_id)


def delete_object_metadata(
    database: Session,
    owner_id: str,
    session_id: str,
) -> None:
    for model in (ReportArtifactRow, UploadRow):
        _delete_scoped(database, model, owner_id, session_id)


def add_evidence(
    database: Session,
    job: DeletionJobRow,
    evidence: tuple[DeletionEvidence, ...],
) -> None:
    _validate_attempt(job, evidence)
    database.add_all(_evidence_row(item) for item in evidence)


def _upload_target(
    database: Session,
    owner_id: str,
    session_id: str,
) -> DeletionTarget | None:
    upload = database.scalar(
        select(UploadRow).where(
            UploadRow.owner_id == owner_id,
            UploadRow.session_id == session_id,
        )
    )
    if upload is None:
        return None
    return DeletionTarget(
        target_kind="input",
        target_id=upload.upload_id,
        owner_id=upload.owner_id,
        session_id=upload.session_id,
        object_key=upload.object_key,
        content_digest=upload.sha256_hex,
    )


def _artifact_targets(
    database: Session,
    owner_id: str,
    session_id: str,
) -> tuple[DeletionTarget, ...]:
    statement = select(ReportArtifactRow).where(
        ReportArtifactRow.owner_id == owner_id,
        ReportArtifactRow.session_id == session_id,
    )
    order = {kind: index for index, kind in enumerate(REQUIRED_ARTIFACT_KINDS)}
    rows = sorted(
        database.scalars(statement),
        key=lambda item: (item.job_id, order[item.artifact_kind]),
    )
    return tuple(_artifact_target(row) for row in rows)


def _artifact_target(artifact: ReportArtifactRow) -> DeletionTarget:
    return DeletionTarget(
        target_kind="report_artifact",
        target_id=f"{artifact.job_id}:{artifact.artifact_kind}",
        owner_id=artifact.owner_id,
        session_id=artifact.session_id,
        object_key=artifact.object_key,
        content_digest=artifact.sha256_hex,
    )


def _delete_scoped(
    database: Session,
    model: type,
    owner_id: str,
    session_id: str,
) -> None:
    database.execute(
        delete(model).where(
            model.owner_id == owner_id,
            model.session_id == session_id,
        )
    )


def _validate_attempt(
    job: DeletionJobRow,
    evidence: tuple[DeletionEvidence, ...],
) -> None:
    attempt = job.attempt_count + 1
    expected = (job.deletion_id, attempt)
    if any((item.deletion_id, item.attempt_number) != expected for item in evidence):
        raise ValueError("Deletion evidence does not match the current attempt.")
    identities = {(item.target_kind, item.target_id) for item in evidence}
    if len(identities) != len(evidence):
        raise ValueError("Deletion evidence repeats a target.")


def _evidence_row(item: DeletionEvidence) -> DeletionEvidenceRow:
    return DeletionEvidenceRow(
        evidence_id=item.evidence_id,
        deletion_id=item.deletion_id,
        target_kind=item.target_kind,
        target_id=item.target_id,
        location_digest=item.location_digest,
        content_digest=item.content_digest,
        attempted_at=item.attempted_at,
        attempt_number=item.attempt_number,
        outcome=item.outcome,
        error_code=item.error_code,
    )


__all__ = [
    "add_evidence",
    "delete_derived_content",
    "delete_object_metadata",
    "deletion_targets",
    "defer_for_publication",
]
