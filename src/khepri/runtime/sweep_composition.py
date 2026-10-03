"""The deployed retention sweep's composition (`KHEPRI-DEC-033` §5, `RRA-017` `FR-271`).

`khepri-retention-sweep` runs what `build_retention_sweep` returns. It lives apart from
`khepri.runtime.wiring`, which re-exports it, because it composes one process's collaborators
from the shared stack and nothing else in that module calls it; it reads `RuntimeStack`, which
it imports for typing only, so the two modules never import each other at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Session, sessionmaker

from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.invitation_retention import InvitationRetentionSweeper
from khepri.rca.lifecycle import AccountRetentionSweeper, MembershipEventSweeper
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.recovery_security import RecoverySecurityEventSweeper
from khepri.rca.recovery_security_persistence import SqlRecoverySecurityEventStore
from khepri.rca.session_persistence import SqlSessionStore as SqlCommercialSessionStore
from khepri.rca.session_retention import SessionRetentionSweeper
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from khepri.rra.definer_calls import RecoveryCandidates
from khepri.rra.evidence_retention import DeletionEvidenceSweeper
from khepri.rra.job_persistence import SqlReportJobRepository
from khepri.rra.persistence import SqlDeletionRepository
from khepri.runtime.retention_sweep import (
    RetentionPasses,
    RetentionSweeper,
    build_retention_sweeper,
)
from khepri.runtime.workspace_retention import DueUploadLister, RawUploadRetentionSweeper

if TYPE_CHECKING:
    from khepri.runtime.wiring import RuntimeStack


def build_retention_sweep(
    stack: RuntimeStack, *, sweep_factory: sessionmaker[Session] | None = None
) -> RetentionSweeper:
    """The sweep `khepri-retention-sweep` runs (`KHEPRI-DEC-033` §5).

    Takes the stack rather than settings so the object store, the session factory and the
    `DeletionService` are the **same ones** the API and the worker use. `DeletionService` needs the
    `S3EncryptedObjectStore` that `build_stack` already constructs; building a second one here
    would be a second wiring of the same collaborators, and `retention_sweep.py` records why that
    is the thing to avoid: *"an expiry route that deleted differently from the on-demand route
    would be a second deletion implementation to keep correct."*

    The collaborators mirror `local/wiring.py`'s composition exactly, so the local sweep and the
    deployed sweep cannot enforce different horizons. No horizon overrides: production runs the
    governed twenty-four months, twelve months and thirty days.

    **Two engines, per component (`RRA-017` `FR-271`).** `sweep_factory`, the sweep role's
    engine, reaches exactly four components: the expired-session lister, the due-upload lister,
    the evidence purge store and the recovery candidate source. Everything else, the sweep's own
    `DeletionService` included, runs on the stack's scoped engine, one owner at a time. Without a
    `sweep_factory` (SQLite, and tests) every component reads through the stack's factory.
    """
    cross = sweep_factory or stack.factory
    return build_retention_sweeper(
        jobs=SqlReportJobRepository(stack.factory, candidates=RecoveryCandidates(cross)),
        deletion=stack.services.deletion,
        factory=stack.factory,
        sweep_factory=cross,
        retention=RetentionPasses(
            accounts=AccountRetentionSweeper(SqlAccountStore(stack.factory)),
            events=MembershipEventSweeper(SqlOrganizationStore(stack.factory)),
            sessions=SessionRetentionSweeper(SqlCommercialSessionStore(stack.factory)),
            invitations=InvitationRetentionSweeper(SqlInvitationStore(stack.factory)),
            recovery_events=RecoverySecurityEventSweeper(
                SqlRecoverySecurityEventStore(stack.factory)
            ),
            # `W1-07b`'s two `KHEPRI-DEC-033` §2 horizons, which had no implementation at all
            # before that slice -- not merely no caller. Without these the workspace audit events
            # and the deletion evidence `W1-07a` writes accumulate indefinitely under a stated
            # twelve-month rule, which is the shape §5 exists to close.
            workspace_audit=WorkspaceAuditSweeper(SqlWorkspaceAuditStore(stack.factory)),
            evidence=DeletionEvidenceSweeper(SqlDeletionRepository(cross)),
            raw_uploads=RawUploadRetentionSweeper(
                factory=stack.factory,
                objects=stack.objects,
                audit=SqlWorkspaceAuditStore(stack.factory),
                due=DueUploadLister(cross),
            ),
        ),
    )


__all__ = ["build_retention_sweep"]
