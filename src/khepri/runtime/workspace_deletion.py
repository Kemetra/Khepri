"""Owner-requested deletion of a dataset version (`W1-07a`; `RCA-005` `FR-123`, `FR-124`,
`FR-126`).

**This composes; it does not re-implement.** `store.set_retention_state` already locks the version
row, writes its tombstone, cascades to every live run's tombstone, and returns early on a repeat
without moving `retention_changed_at` -- `KHEPRI-DEC-033` §5 anchors a horizon to that instant, so
a repeat that moved it would let repeated requests push a deadline outward. What was missing was
not the walk but everything around it: a caller, evidence, an audit event, and the ledger entry a
restore must meet.

**Composed in `khepri.runtime`** because it joins `khepri.rca`'s store to a revocation ledger and,
in a later slice, to `khepri.rra`'s deletion repository for the content the version derived. `R7-01`
§3 forbids either package importing the other, and this ending is a *decision the shell makes*, not
a rule either package owns -- the seam `W1-04b` established.

**What the repeat must and must not do** (`FR-123`, three claims, each separately evidenced):
the response is the same, **no new deletion evidence** is written, and **one** audit event is
emitted carrying `already_deleted`. One outcome test would pass with two of the three broken, so
`test_w107_deletion_service.py` asserts them apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from khepri.rca.workspace.audit import (
    ACTION_VERSION_DELETED,
    OBJECT_VERSION,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.revocation import RevokedObject
from khepri.rca.workspace.unit_of_work import unit_of_work


@dataclass(frozen=True, slots=True)
class DeletionSources:
    """Where one ending is performed: the workspace records, the audit log, the revocation ledger,
    the `RRA` content path, and the session factory the upload bridge reads through.

    Grouped rather than passed flat for `ProvenanceSources`' and `ShellRendering`'s reason -- five
    parameters trips CodeScene's Excess Number of Function Arguments, and these five travel
    together on every construction and have no meaning apart. Extracting a helper instead would
    raise the module's function mean, which the same gate scores.
    """

    store: Any
    audit: Any
    ledger: Any
    content: Any
    factory: Any


@dataclass(frozen=True, slots=True)
class DeletionOutcome:
    """What one deletion request produced. `deleted` is `False` for `FR-123`'s idempotent repeat --
    the object had already ended -- and the rest of the response is identical either way, because
    the requirement makes a repeat succeed *with the same response as the first*."""

    version_id: str
    deleted: bool


class WorkspaceDeletion:
    """Ends a dataset version and everything named as cascading from it."""

    #: `rra_deletion_jobs` admits `immediate` and `expiry`. An owner-requested deletion is the
    #: first: `FR-123` makes it immediate, and `expiry` is `W1-07b`'s retention-triggered purge.
    REASON_IMMEDIATE = "immediate"

    def __init__(self, sources: DeletionSources) -> None:
        self._sources = sources

    def delete_version(
        self, owner_id: str, version_id: str, *, actor_account_id: str, now: datetime
    ) -> DeletionOutcome:
        """End this scope's dataset version, immediately, idempotently, and evidenced.

        The already-ended case is read from the store rather than inferred from a return value:
        `get_dataset_version` answers `None` for a version that is tombstoned as well as for one
        that never existed, and both are the same answer to a customer -- there is nothing here to
        end. Answering `deleted=False` for either keeps `FR-123`'s "same response" true without
        telling one scope whether another's identifier ever existed.

        **That read is a fast path, not the decision.** It is unlocked and outside the unit of
        work, so two overlapping requests can both pass it. What decides the outcome is the
        tombstone call itself, under the version lock inside the unit: it reports whether *this*
        call ended the version, and the request that did not records `already_deleted` and no
        revocation (`FR-123`). Before `#526` both recorded `completed` and answered `deleted=True`.
        """
        actor = AuditActor(owner_id=owner_id, actor_account_id=actor_account_id)
        subject = AuditSubject(OBJECT_VERSION, version_id)
        if self._sources.store.get_dataset_version(version_id, owner_id) is None:
            return self._already_deleted(actor, subject, now)
        version = self._sources.store.get_dataset_version(version_id, owner_id)
        # Content first, records second, and **not** the other way round. The two orderings fail
        # very differently:
        #
        # - Content first, then a fault in the records: the content is gone and the version is
        #   still live and readable. A retry re-enters, finds the version, gets the already
        #   `complete` job back from `delete_session_content`, and commits the records. Recoverable.
        # - Records first, then a fault in the content: the version is withdrawn from every read,
        #   the content is orphaned, and the already-ended guard above short-circuits every retry.
        #   Permanently unreachable.
        #
        # So this line stays where it is. It is also the only step that cannot join the unit of
        # work: it deletes from the object store, which no database transaction can roll back, and
        # it raises `DeletionRetryRequired` as ordinary control flow.
        self._end_derived_content(version, now)
        # The three record writes commit together or not at all (`FR-123`, `FR-125`). Review on
        # `#382` found them in three transactions, and tombstone-then-fault was unrepairable: the
        # version reads back `None`, so the guard above answers the next attempt `deleted=False`
        # and the ledger row is never written -- a version withdrawn from every read with no
        # revocation recorded, which is `FR-126` silently unmet. `W1-04` closed this same window
        # on the recording side; `unit_of_work` is that instrument and the three stores below all
        # reach the database through `writing`, so they join the ambient session unchanged.
        with unit_of_work(self._sources.factory):
            if not self._sources.store.tombstone_dataset_version(
                version_id, now=now, owner_id=owner_id
            ):
                # Overtaken: another request ended it after the read above. The winner wrote the
                # revocation; this one is `FR-123`'s repeat.
                return self._already_deleted(actor, subject, now)
            self._sources.ledger.revoke(
                RevokedObject(
                    object_kind=OBJECT_VERSION,
                    object_id=version_id,
                    owner_id=owner_id,
                    revoked_at=now,
                )
            )
            self._sources.audit.record(
                WorkspaceAuditEvent.completed(actor, ACTION_VERSION_DELETED, subject, now=now)
            )
        return DeletionOutcome(version_id=version_id, deleted=True)

    def _already_deleted(
        self, actor: AuditActor, subject: AuditSubject, now: datetime
    ) -> DeletionOutcome:
        """`FR-123`'s repeat: one `already_deleted` event, no evidence, the first's response."""
        self._sources.audit.record(
            WorkspaceAuditEvent.already_deleted(actor, ACTION_VERSION_DELETED, subject, now=now)
        )
        return DeletionOutcome(version_id=subject.object_id, deleted=False)

    def _sessions_of_version(self, version: Any) -> tuple[str, ...]:
        """Every analysis session that holds content derived from this version.

        The upload row is the shortest path while raw retention still keeps it.  After seal plus
        seven days DEC-033 removes that row, so completed runs provide the durable path through
        their run-to-job links.  Both reads remain owner-scoped at this composition seam.
        """
        from sqlalchemy import select

        from khepri.rca.workspace.run_reports import RunReportRow
        from khepri.rca.workspace.schema import AnalysisRunRow
        from khepri.rra.job_persistence import ReportJobRow
        from khepri.rra.persistence import UploadRow

        with self._sources.factory() as database:
            upload_session = database.scalar(
                select(UploadRow.session_id).where(
                    UploadRow.owner_id == version.owner_id,
                    UploadRow.ciphertext_sha256_hex == version.upload_ciphertext_digest,
                )
            )
            report_sessions = database.scalars(
                select(ReportJobRow.session_id)
                .join(RunReportRow, RunReportRow.job_id == ReportJobRow.job_id)
                .join(AnalysisRunRow, AnalysisRunRow.run_id == RunReportRow.run_id)
                .where(
                    AnalysisRunRow.owner_id == version.owner_id,
                    AnalysisRunRow.version_id == version.version_id,
                    RunReportRow.owner_id == version.owner_id,
                    ReportJobRow.owner_id == version.owner_id,
                )
            )
            sessions = set(report_sessions)
            if upload_session is not None:
                sessions.add(upload_session)
            return tuple(sorted(sessions))

    def _end_derived_content(self, version: Any, now: datetime) -> None:
        """End the upload this version was admitted from, and everything derived from it.

        `KHEPRI-DEC-033` §1: *derived content never outlives its input's right to exist*. Ending
        only the `RCA` records would leave the customer's upload, fact packages and artifacts in
        place under a version they withdrew.

        **Bridged on the ciphertext digest**, because a `DatasetVersion` holds the upload's digests
        and no session identifier -- §3 fixes what a version may keep, and a session identifier is
        not on that list. The upload row carries both the digest and its session, and the digest is
        already the key `dataset_version_for_upload` joins on, so this reuses an existing link
        rather than inventing one. Resolved here, in `khepri.runtime`, because it reads an `RRA`
        row on behalf of an `RCA` ending and `R7-01` §3 forbids either package importing the other.

        Through `DeletionService.delete_session_content`, which is the one implementation of this
        ending -- `local/sweeper.py` records why: *"an expiry route that deleted differently from
        the on-demand route would be a second deletion implementation to keep correct"*. It is also
        what writes `FR-124`'s content-free evidence, so the evidence arrives by using the existing
        path rather than by this slice writing a second kind.

        The job it begins is idempotent per session, so a repeat that reached here would not start
        a second ending -- but the caller returns before this on the already-deleted path, so a
        repeat does not reach it at all.
        """
        session_ids = self._sessions_of_version(version)
        if not session_ids:
            # The upload already ended -- its own seven-day horizon, or an earlier deletion. The
            # version's ending is not blocked by content that is already gone.
            return
        for session_id in session_ids:
            self._sources.content.delete_session_content(
                session_id=session_id, reason=self.REASON_IMMEDIATE, now=now
            )


__all__ = ["DeletionOutcome", "DeletionSources", "WorkspaceDeletion"]
