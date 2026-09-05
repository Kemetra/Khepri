"""`W1-07a` -- the audit vocabulary a customer deletion needs (`RCA-005` `FR-123`).

`FR-123` requires that a repeated deletion emit one audit event with outcome `already_deleted`, so
an idempotency test and an evidence consumer read the same contract. Both vocabularies are
`CHECK`-constrained on `rca_workspace_audit_events`, so admitting a value in Python alone would
fail at the driver rather than at the domain -- these tests assert both halves.
"""

from __future__ import annotations

from datetime import UTC, datetime

from khepri.rca.workspace.audit import (
    ACTION_VERSION_DELETED,
    AUDIT_ACTIONS,
    AUDIT_OUTCOMES,
    OUTCOME_ALREADY_DELETED,
    OUTCOME_ALREADY_RECORDED,
)

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)


def test_the_deletion_vocabulary_is_admitted_by_the_domain() -> None:
    """`FR-123` names `already_deleted` literally."""
    assert ACTION_VERSION_DELETED in AUDIT_ACTIONS
    assert OUTCOME_ALREADY_DELETED in AUDIT_OUTCOMES


def test_already_deleted_is_not_already_recorded() -> None:
    """Two contracts, deliberately distinct. `already_recorded` says a *write* was a duplicate;
    `already_deleted` says the object had already ended and no new evidence was written. Reusing
    the first for the second would make `FR-123`'s contract unreadable to an evidence consumer,
    and the two reach different ones."""
    assert OUTCOME_ALREADY_DELETED != OUTCOME_ALREADY_RECORDED
    assert OUTCOME_ALREADY_RECORDED in AUDIT_OUTCOMES


def test_a_repeat_of_a_deletion_is_recorded_as_already_deleted() -> None:
    """The named constructor an idempotent deletion reaches, beside `completed` and `refused`."""
    from khepri.rca.workspace.audit import (
        OBJECT_VERSION,
        AuditActor,
        AuditSubject,
        WorkspaceAuditEvent,
    )

    event = WorkspaceAuditEvent.already_deleted(
        AuditActor(owner_id="scope-1", actor_account_id="acct-1"),
        ACTION_VERSION_DELETED,
        AuditSubject(OBJECT_VERSION, "dsv-1"),
        now=NOW,
    )

    assert event.outcome == OUTCOME_ALREADY_DELETED
    assert event.action == ACTION_VERSION_DELETED
    assert event.object_id == "dsv-1"
