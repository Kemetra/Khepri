"""`W1-07b` -- the two `KHEPRI-DEC-033` §2 horizons that had no implementation anywhere.

§5 says every horizon in §2 is unenforced because no sweeper has a caller in the shipped image.
That is true of five sweepers; it understates these two, which had no code at all. `W1-07a` shipped
the deletion that *writes* both classes, so `W1-07b` is where they gain an ending.

Both are twelve months, and both take that number from a named constant rather than a literal: §2
says the horizon is "adopted rather than re-derived", and two literals for one decided number is how
they come to disagree the day one moves.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from khepri.rca.workspace.audit import (
    ACTION_VERSION_CREATED,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper
from tests.w104_support import member
from tests.w107_support import journey

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
#: Comfortably past the twelve-month horizon, and comfortably inside it. Written as day offsets
#: rather than month arithmetic so the fixture does not restate the code under test.
THIRTEEN_MONTHS_AGO = NOW - timedelta(days=396)
ELEVEN_MONTHS_AGO = NOW - timedelta(days=334)


def _event(store: SqlWorkspaceAuditStore, owner_id: str, account_id: str, when: datetime) -> None:
    """One real audit event, through the store's own verb."""
    store.record(
        WorkspaceAuditEvent.completed(
            AuditActor(owner_id=owner_id, actor_account_id=account_id),
            ACTION_VERSION_CREATED,
            AuditSubject("version", "dsv_example"),
            now=when,
        )
    )


def test_an_audit_event_past_twelve_months_is_purged() -> None:
    """`KHEPRI-DEC-033` §2: the retention/lifecycle audit event is purged on elapse of twelve
    months, "the `KHEPRI-DEC-015` §2a horizon, adopted rather than re-derived"."""
    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)

    report = WorkspaceAuditSweeper(audit).sweep(now=NOW)

    assert report.purged_events == 1


def test_an_audit_event_inside_twelve_months_survives() -> None:
    """The horizon is a boundary, not a purge-everything.

    A sweeper that removed live evidence would destroy the attribution `FR-125` exists to keep --
    which is a worse failure than the unbounded growth this pass was written to stop.
    """
    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, ELEVEN_MONTHS_AGO)

    report = WorkspaceAuditSweeper(audit).sweep(now=NOW)

    assert report.purged_events == 0
    assert len(audit.events_for_scope(who.owner_id)) == 1


def _evidence_aged(j, who, *, attempted_at: datetime) -> int:
    """One real deletion's evidence, aged to `attempted_at`. Returns how many rows exist.

    Produced by the **production verb** -- the deletion service ends a sealed version and the
    `RRA` path writes its own evidence -- rather than by inserting rows. Raw setup exempts the
    transition it skips, so a mutant of the bypassed verb survives every test built on it. Only
    the *clock* is faked, with a single `UPDATE`, because a test cannot wait thirteen months.
    """
    from sqlalchemy import text

    from tests.w107_support import deletion_service, sealed_version

    version, _run = sealed_version(j, who, with_run=True)
    deletion_service(j).delete_version(
        who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
    )
    with j.w.factory() as database:
        aged = database.execute(
            text("UPDATE rra_deletion_evidence SET attempted_at = :t"),
            {"t": attempted_at},
        ).rowcount
        database.commit()
    assert aged > 0, "the deletion wrote no evidence to age"
    return aged


def test_deletion_evidence_past_twelve_months_is_purged() -> None:
    """`KHEPRI-DEC-033` `OD-2`: twelve months, "on `KHEPRI-DEC-015` §2a's discipline that no
    horizon is quietly longer than another". Rejected there: indefinite, by Constitution VII's
    least-data default."""
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository

    j = journey()
    who = member(j.w)
    written = _evidence_aged(j, who, attempted_at=THIRTEEN_MONTHS_AGO)

    report = DeletionEvidenceSweeper(SqlDeletionRepository(j.w.factory)).sweep(now=NOW)

    assert report.purged_evidence == written


def test_deletion_evidence_inside_twelve_months_survives() -> None:
    """Evidence is what proves content ended (`FR-124`). Purging it early destroys the proof, so
    the boundary matters in both directions."""
    from khepri.rra.evidence_retention import DeletionEvidenceSweeper
    from khepri.rra.persistence import SqlDeletionRepository

    j = journey()
    who = member(j.w)
    _evidence_aged(j, who, attempted_at=ELEVEN_MONTHS_AGO)

    report = DeletionEvidenceSweeper(SqlDeletionRepository(j.w.factory)).sweep(now=NOW)

    assert report.purged_evidence == 0


def test_the_two_twelve_month_horizons_agree() -> None:
    """One decision, restated across a package boundary `R7-01` §3 forbids crossing.

    `KHEPRI-DEC-033` §2 gives audit events and deletion evidence the same twelve months, and
    `khepri.rra` may not import `khepri.rca`, so the number appears in both packages. This is what
    keeps that a restatement of one decision rather than two policies: move one and this fails.
    """
    from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS
    from khepri.rra.evidence_retention import EVIDENCE_RETENTION_MONTHS

    assert EVIDENCE_RETENTION_MONTHS == MEMBERSHIP_EVENT_RETENTION_MONTHS


def test_a_workspace_run_keeps_its_reconstructable_package_past_day_seven() -> None:
    """DEC-033: a session timer must not erase the facts retained with a live run."""
    from khepri.rca.semantic_queries import ports
    from khepri.rra.deletion import DeletionService
    from khepri.rra.persistence import SqlDeletionRepository, SqlFactPackageRepository
    from khepri.runtime.job_sessions import SqlJobSessions
    from khepri.runtime.retention_sweep import RetentionPasses, RetentionSweeper
    from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
    from khepri.runtime.workspace_retention import RawUploadRetentionSweeper
    from tests.w107_support import sealed_version, uploads_for

    j = journey()
    who = member(j.w)
    _version, run = sealed_version(j, who, with_run=True)
    assert run.package_digest is not None

    report = RetentionSweeper(
        jobs=j.jobs,
        deletion=DeletionService(
            sessions=j.w.sessions,
            deletions=SqlDeletionRepository(j.w.factory),
            objects=j.w.objects,
        ),
        factory=j.w.factory,
        retention=RetentionPasses(
            raw_uploads=RawUploadRetentionSweeper(
                factory=j.w.factory,
                objects=j.w.objects,
                audit=j.w.audit,
            )
        ),
    ).sweep(now=NOW + timedelta(days=8))

    projected = SemanticViewAdapter(SqlFactPackageRepository(j.w.factory)).project(
        ports.SemanticViewRequest(
            view_id="ExecutiveOverviewView",
            view_version="sv1.executive_overview.v1",
        ),
        (run,),
    )
    assert report.expired_sessions == 0
    assert report.purged_uploads == 1
    assert uploads_for(j, who.owner_id) == ()
    assert projected is not None
    assert projected.kind == ports.KIND_ADMITTED
    assert projected.projection is not None and projected.projection.rows
    job_id = j.reports.job_id_for_run(run.run_id, who.owner_id)
    assert job_id is not None
    job = SqlJobSessions(j.w.factory).job(job_id, who.owner_id)
    assert job is not None
    assert j.artifacts.list_for_job(
        session_id=job.session_id,
        job_id=job.job_id,
        now=NOW + timedelta(days=8),
    )


def test_raw_upload_purges_at_seal_plus_seven_days_not_session_plus_seven() -> None:
    """The durable package survives while the least-useful source bytes end on their own clock."""
    from khepri.rra.persistence import SqlFactPackageRepository
    from khepri.runtime.workspace_retention import RawUploadRetentionSweeper
    from tests.w107_support import sealed_version, uploads_for

    j = journey()
    who = member(j.w)
    version, run = sealed_version(j, who, with_run=True)
    assert version.sealed_at is not None
    assert run.package_digest is not None
    (upload,) = uploads_for(j, who.owner_id)
    assert upload.object_key in j.w.objects.objects
    sweeper = RawUploadRetentionSweeper(
        factory=j.w.factory,
        objects=j.w.objects,
        audit=j.w.audit,
    )

    early = sweeper.sweep(now=version.sealed_at + timedelta(days=7) - timedelta(seconds=1))
    due = sweeper.sweep(now=version.sealed_at + timedelta(days=7))

    assert early.purged_uploads == 0
    assert due.purged_uploads == 1
    assert upload.object_key not in j.w.objects.objects
    assert uploads_for(j, who.owner_id) == ()
    assert (
        SqlFactPackageRepository(j.w.factory).get_owned_package(
            run.package_digest, who.owner_id
        )
        is not None
    )


def test_dataset_deletion_still_purges_derivatives_after_the_raw_row_is_gone() -> None:
    """Removing the upload row must not erase the only path to its run's retained content."""
    from khepri.rra.persistence import SqlFactPackageRepository
    from khepri.runtime.workspace_retention import RawUploadRetentionSweeper
    from tests.w107_support import deletion_service, sealed_version

    j = journey()
    who = member(j.w)
    version, run = sealed_version(j, who, with_run=True)
    assert version.sealed_at is not None
    assert run.package_digest is not None
    RawUploadRetentionSweeper(
        factory=j.w.factory,
        objects=j.w.objects,
        audit=j.w.audit,
    ).sweep(now=version.sealed_at + timedelta(days=7))

    deletion_service(j).delete_version(
        who.owner_id,
        version.version_id,
        actor_account_id=who.account_id,
        now=version.sealed_at + timedelta(days=8),
    )

    assert (
        SqlFactPackageRepository(j.w.factory).get_owned_package(
            run.package_digest, who.owner_id
        )
        is None
    )


def test_a_beta_only_session_still_expires_after_seven_days() -> None:
    """Workspace durability must not widen the invitation beta's content horizon."""
    from khepri.rra.deletion import DeletionService
    from khepri.rra.persistence import SqlDeletionRepository
    from khepri.rra.sessions import InvitationService
    from khepri.runtime.retention_sweep import RetentionSweeper

    j = journey()
    invitations = InvitationService(j.w.sessions)
    token = invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    session = invitations.redeem(token, now=NOW)
    report = RetentionSweeper(
        jobs=j.jobs,
        deletion=DeletionService(
            sessions=j.w.sessions,
            deletions=SqlDeletionRepository(j.w.factory),
            objects=j.w.objects,
        ),
        factory=j.w.factory,
    ).sweep(now=NOW + timedelta(days=7))

    ended = j.w.sessions.get_session(session.session_id)
    assert report.expired_sessions == 1
    assert ended is not None and ended.content_deleted_at == NOW + timedelta(days=7)


def test_the_sweep_records_one_audit_event_per_scope_it_purged() -> None:
    """`FR-125` names `sweep` among the workspace actions that MUST emit an audit event, and
    `KHEPRI-DEC-033` §2 says the audit class's ending is "run by the retention sweep, recorded as
    a" content-free record.

    **Per scope**, because `rca_workspace_audit_events.owner_id` is `nullable=False`: a cross-scope
    pass cannot write one global event, and a customer's audit trail should show the sweeps that
    touched *their* rows rather than a counter for everyone's.

    **Subject `None`**, because a sweep acts on a class over a horizon and not on an object.
    `AuditEntry.subject` already admits that, and `ck_rca_workspace_audit_subject_pair` pins the
    pairing -- naming `version` here would make an evidence consumer read a class-level purge as an
    act on one customer's dataset version.
    """
    from khepri.rca.workspace.audit import ACTION_RETENTION_SWEPT

    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)

    WorkspaceAuditSweeper(audit).sweep(now=NOW)

    events = audit.events_for_scope(who.owner_id)
    assert [event.action for event in events] == [ACTION_RETENTION_SWEPT]
    assert events[0].object_kind is None
    assert events[0].object_id is None


def test_a_sweep_that_purged_nothing_records_nothing() -> None:
    """An event per scope *purged from*, not per scope that exists.

    Otherwise every pass would write one row per organization forever, and the table this horizon
    exists to bound would grow fastest under the sweep that bounds it.
    """
    from khepri.rca.workspace.audit import ACTION_RETENTION_SWEPT

    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, ELEVEN_MONTHS_AGO)

    WorkspaceAuditSweeper(audit).sweep(now=NOW)

    actions = [event.action for event in audit.events_for_scope(who.owner_id)]
    assert ACTION_RETENTION_SWEPT not in actions


def test_the_sweep_does_not_purge_its_own_evidence() -> None:
    """The sweep's event is itself subject to the horizon the sweep enforces.

    It is written at `now` and the horizon is twelve months before `now`, so no correctly ordered
    pass can reach it -- but that is a property to assert, not to assume: it becomes false the day
    a later slice moves the horizon or reorders the pass, and nothing else would notice.
    """
    from khepri.rca.workspace.audit import ACTION_RETENTION_SWEPT

    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)
    sweeper = WorkspaceAuditSweeper(audit)

    sweeper.sweep(now=NOW)
    second = sweeper.sweep(now=NOW)

    assert second.purged_events == 0
    assert [event.action for event in audit.events_for_scope(who.owner_id)] == [
        ACTION_RETENTION_SWEPT
    ]


def test_the_sweep_records_only_scopes_whose_rows_it_deleted() -> None:
    """Evidence follows the rows *this* call removed, not a separate earlier read.

    The pass used to ask `scopes_with_events_before` which scopes held expired rows, then issue a
    second statement to delete them. Between those two statements the rows can go: two overlapping
    `khepri-retention-sweep` invocations both read the scope, one deletes its rows and the other
    deletes none -- and both then wrote `retention_swept`, an audit record for a purge that did not
    happen. `FR-125`'s event attests an action; one attesting nothing is worse than absent, because
    a reader cannot tell it apart from the real thing.

    The interleaving is driven at the seam where it occurs -- the other invocation commits its
    delete *after* this pass has read and *before* it purges -- rather than by running two
    connections and hoping for the ordering. Deleting with `RETURNING` closes the window by making
    the recorded scopes be the rows this statement removed.
    """
    from khepri.rca.workspace.audit import ACTION_RETENTION_SWEPT

    j = journey()
    who = member(j.w)
    audit = SqlWorkspaceAuditStore(j.w.factory)
    _event(audit, who.owner_id, who.account_id, THIRTEEN_MONTHS_AGO)

    class TheOtherInvocationWinsFirst:
        """The real store, with the rival invocation's delete committing first.

        Hooked at `purge_events_before` because that is where this pass now learns what it
        removed. A pass whose rows a rival already took must come back empty-handed from its own
        statement -- and record nothing on the strength of it.
        """

        def __init__(self, store: SqlWorkspaceAuditStore) -> None:
            self._store = store

        def __getattr__(self, name: str) -> object:
            return getattr(self._store, name)

        def purge_events_before(self, horizon: datetime) -> object:
            self._store.purge_events_before(horizon)  # the rival invocation, committing.
            return self._store.purge_events_before(horizon)

    report = WorkspaceAuditSweeper(TheOtherInvocationWinsFirst(audit)).sweep(now=NOW)

    assert report.purged_events == 0
    actions = [event.action for event in audit.events_for_scope(who.owner_id)]
    assert ACTION_RETENTION_SWEPT not in actions, (
        "recorded a sweep of a scope whose rows another invocation had already deleted"
    )


# --- #460 review: retention promotion must not outrun a requested deletion -------------------


def test_retention_refuses_once_a_deletion_has_been_requested() -> None:
    """A deletion already requested is never revived by a later promotion.

    `retain_workspace_content` answers `False` for such a scope. Before the
    review on `#460` nothing asserted the caller acts on that answer: both
    `create_version` branches discarded it, so a version could commit and report
    success after deletion had won.
    """
    from khepri.rra.persistence import SqlDeletionRepository
    from khepri.rra.sessions import SessionScope
    from khepri.runtime.workspace_retention import retain_workspace_content
    from tests.w107_support import sealed_version

    j = journey()
    who = member(j.w)
    sealed_version(j, who)
    session_id = _session_of(j, who)
    SqlDeletionRepository(j.w.factory).begin(
        scope=SessionScope(owner_id=who.owner_id, session_id=session_id),
        deletion_id="del_race",
        reason="immediate",
        requested_at=NOW,
    )

    retained = retain_workspace_content(
        j.w.factory, owner_id=who.owner_id, session_id=session_id
    )

    assert retained is False


def _session_of(j, who) -> str:
    """The session this scope's upload belongs to, read as the store holds it."""

    from khepri.rra.persistence import UploadRow

    with j.w.factory() as database:
        row = database.scalar(select(UploadRow).where(UploadRow.owner_id == who.owner_id))
        assert row is not None
        return row.session_id


def test_create_version_refuses_when_retention_cannot_promote() -> None:
    """The caller acts on retention's answer instead of discarding it.

    Review on `#460` found both `create_version` branches calling
    `retain_workspace_content` for effect and ignoring its result, so a version
    could be recorded and reported successful after a deletion had won.

    **The sequential case is already closed upstream and this test says so.**
    `_admission` runs first and `SessionExpired` fires for a session whose
    `deletion_requested_at` is set, so a deletion *already requested* never
    reaches the retention call -- the refusal arrives as `NO_ADMISSION_FAILURE`.
    What the discarded result left open is the **concurrent** case that guard
    cannot cover: a deletion committing after `_admission` passed. The lock in
    `retain_workspace_content` makes that read wait, and this refusal is what the
    caller does with the answer once it arrives.

    Driven here by calling the promotion directly under a requested deletion --
    the state the concurrent race produces at the moment retention reads it.
    """
    from khepri.rra.persistence import SqlDeletionRepository
    from khepri.rra.sessions import SessionScope
    from khepri.runtime.workspace_recording import RETENTION_REFUSED_FAILURE, WorkspaceRefused
    from khepri.runtime.workspace_retention import retain_workspace_content
    from tests.w107_support import submitted

    j = journey()
    who = member(j.w)
    submitted(j, who)
    session_id = _session_of(j, who)
    SqlDeletionRepository(j.w.factory).begin(
        scope=SessionScope(owner_id=who.owner_id, session_id=session_id),
        deletion_id="del_race_version",
        reason="immediate",
        requested_at=NOW,
    )

    retained = retain_workspace_content(
        j.w.factory, owner_id=who.owner_id, session_id=session_id
    )

    assert retained is False
    # And the caller turns that answer into a refusal rather than dropping it.
    assert RETENTION_REFUSED_FAILURE
    assert issubclass(WorkspaceRefused, ValueError)


def test_both_create_version_branches_act_on_the_retention_answer() -> None:
    """Neither branch may call the promotion for effect. Asserted on source.

    A behavioural test cannot reach these branches while `_admission` closes the
    sequential case, and the concurrent one is not reproducible over SQLite. What
    is checkable, and what actually regressed, is that the result is consumed:
    a bare `retain_workspace_content(...)` statement is the defect `#460` found.
    """
    import inspect

    from khepri.runtime import workspace_recording

    create = inspect.getsource(workspace_recording.WorkspaceRecording.create_version)
    retain = inspect.getsource(workspace_recording.WorkspaceRecording._retain)

    assert "retain_workspace_content(" not in create
    assert create.count("self._retain(") == 2
    assert "raise WorkspaceRefused(RETENTION_REFUSED_FAILURE)" in retain
    # The promotion precedes the version, so a refusal rolls the version back
    # rather than committing it beside the refusal event.
    assert create.index("self._retain(") < create.index("add_dataset_version")


def test_retention_takes_the_same_named_lock_the_deletion_takes() -> None:
    """The read must wait for a deletion in flight, not race it.

    `SqlDeletionRepository.begin` locks the session row before setting
    `deletion_requested_at`. A plain `SELECT` here would not wait for it, so the
    promotion could read a live session and revive a scope the deletion had
    already claimed.

    Asserted by source rather than by a timing test: SQLite emits no `FOR UPDATE`
    and SQLAlchemy silently omits it, so a concurrency test over the suite's
    database cannot see the clause at all -- the reason `rca/workspace/locks.py`
    names every lock instead of inlining it.
    """
    import inspect

    from khepri.runtime import workspace_retention

    source = inspect.getsource(workspace_retention.retain_workspace_content)

    assert "session_scope_for_update_statement" in source
    assert "select(BetaSessionRow)" not in source
