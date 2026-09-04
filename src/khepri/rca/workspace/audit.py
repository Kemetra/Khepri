"""Content-free audit events for workspace actions (`W1-04`; `RCA-005` `FR-125`).

`FR-125`: every workspace action -- create version, run, delete, sweep, profile reuse -- emits one
content-free audit event carrying opaque actor, opaque organization, object identifiers, action,
outcome and timestamp, under `KHEPRI-DEC-015` §7's logging rule and its twelve-month horizon.

**Exactly those fields, and no other.** `test_w104_workspace_services.py` asserts the field set as
an equality, the way `W1-01` asserts its records and `W1-03` its tombstones: a field that could
carry content -- a filename, a figure, a label -- fails until someone names it here, and §7 gives
no field that could be named.

**No session identifier, structurally.** §7 forbids the session identifier from every log, "and it
admits no exception". The workspace holds no `RRA` identifier at all -- a version is linked to its
upload by digest and a run to its package by digest -- and `AuditSubject` refuses an object kind
outside `AUDIT_OBJECTS`, so an event that named a session could not be constructed.

**The vocabularies are closed and enforced twice**, in the value types here and by `CHECK`
constraints in `schema.py`, on `W1-02`'s reasoning: the type is where a caller gets a content-free
refusal, the constraint is what holds for a row that arrives by any other route.

**Sealed, on `records.py`'s two-door rule.** An audit event persists and is read back, and a
mutable one is not evidence. The three creation doors are the three outcomes, so a caller states
how the action ended by which door it opens; `MembershipEvent` in `rca/organizations.py` carries
its kind the same way.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from khepri.rca.records import Sealed, register_sealed, through_door
from khepri.rca.workspace.contracts import _identifier

ACTION_VERSION_CREATED = "version_created"
ACTION_RUN_STARTED = "run_started"
ACTION_RUN_COMPLETED = "run_completed"
ACTION_RUN_FAILED = "run_failed"
ACTION_PROFILE_REMEMBERED = "profile_remembered"
ACTION_PROFILE_REUSED = "profile_reused"
#: The workspace actions this slice performs. `W1-07` adds deletion and the sweep when it writes
#: them -- `FR-125` names both -- and the migration literal moves in the same commit.
AUDIT_ACTIONS = (
    ACTION_VERSION_CREATED,
    ACTION_RUN_STARTED,
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_PROFILE_REMEMBERED,
    ACTION_PROFILE_REUSED,
)

OUTCOME_COMPLETED = "completed"
OUTCOME_REFUSED = "refused"
#: `FR-123` gives a repeated deletion the outcome `already_deleted`; this is the same shape for a
#: repeated creation, so an idempotent retry is recorded as what it was rather than as a second act.
OUTCOME_ALREADY_RECORDED = "already_recorded"
AUDIT_OUTCOMES = (OUTCOME_COMPLETED, OUTCOME_REFUSED, OUTCOME_ALREADY_RECORDED)

OBJECT_VERSION = "version"
OBJECT_RUN = "run"
OBJECT_PROFILE = "profile"
AUDIT_OBJECTS = (OBJECT_VERSION, OBJECT_RUN, OBJECT_PROFILE)

# Content-free, per the refusal discipline in `rca/errors.py`.
AUDIT_ACTION_FAILURE = "Audit action is not one of the workspace actions this domain names."
AUDIT_OUTCOME_FAILURE = "Audit outcome is not one of the outcomes this domain names."
AUDIT_OBJECT_FAILURE = "Audit subject is not one of the workspace objects this domain names."


@dataclass(frozen=True, slots=True)
class AuditActor:
    """Who acted, in which scope: the two opaque identifiers `FR-125` puts on every event.

    Paired at the type so a caller cannot attribute an action to one scope's actor under another
    scope's identifier one argument at a time -- `RunSubject`'s reasoning, one layer over.
    """

    owner_id: str
    actor_account_id: str


@dataclass(frozen=True, slots=True)
class AuditSubject:
    """Which workspace object the action was about. Validated, so no other kind is representable."""

    object_kind: str
    object_id: str

    def __post_init__(self) -> None:
        if self.object_kind not in AUDIT_OBJECTS:
            raise ValueError(AUDIT_OBJECT_FAILURE)


@dataclass(frozen=True, slots=True)
class AuditAction:
    """What was attempted and how it ended, as one validated value."""

    action: str
    outcome: str

    def __post_init__(self) -> None:
        if self.action not in AUDIT_ACTIONS:
            raise ValueError(AUDIT_ACTION_FAILURE)
        if self.outcome not in AUDIT_OUTCOMES:
            raise ValueError(AUDIT_OUTCOME_FAILURE)


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Who, what, and about which object -- everything an event records except its own identity
    and instant. Grouped so both doors stay within the argument threshold."""

    actor: AuditActor
    action: AuditAction
    subject: AuditSubject | None


@register_sealed
@dataclass(frozen=True, slots=True)
class WorkspaceAuditEvent(Sealed):
    """One workspace action, as `FR-125` allows it to be recorded.

    `object_kind` and `object_id` are `None` together, for a refusal that produced no object -- a
    version that was not created has no identifier to name. `schema.py` pins the pairing with a
    `CHECK`, so a kind without an identifier is unrepresentable in a row as it is here.
    """

    event_id: str
    owner_id: str
    actor_account_id: str
    action: str
    outcome: str
    object_kind: str | None
    object_id: str | None
    occurred_at: datetime

    @staticmethod
    def _build(event_id: str, entry: AuditEntry, occurred_at: datetime) -> WorkspaceAuditEvent:
        """The constructor call every door shares."""
        return WorkspaceAuditEvent(
            event_id=event_id,
            owner_id=entry.actor.owner_id,
            actor_account_id=entry.actor.actor_account_id,
            action=entry.action.action,
            outcome=entry.action.outcome,
            object_kind=None if entry.subject is None else entry.subject.object_kind,
            object_id=None if entry.subject is None else entry.subject.object_id,
            occurred_at=occurred_at,
        )

    @classmethod
    def _record(
        cls, actor: AuditActor, action: AuditAction, subject: AuditSubject | None, now: datetime
    ) -> WorkspaceAuditEvent:
        entry = AuditEntry(actor=actor, action=action, subject=subject)
        with through_door():
            return cls._build(_identifier("aud"), entry, now)

    @classmethod
    def completed(
        cls, actor: AuditActor, action: str, subject: AuditSubject | None, *, now: datetime
    ) -> WorkspaceAuditEvent:
        """The action was performed and produced `subject`."""
        return cls._record(actor, AuditAction(action, OUTCOME_COMPLETED), subject, now)

    @classmethod
    def refused(
        cls, actor: AuditActor, action: str, subject: AuditSubject | None, *, now: datetime
    ) -> WorkspaceAuditEvent:
        """The action was refused. `subject` names the object it was about, if one existed."""
        return cls._record(actor, AuditAction(action, OUTCOME_REFUSED), subject, now)

    @classmethod
    def already_recorded(
        cls, actor: AuditActor, action: str, subject: AuditSubject | None, *, now: datetime
    ) -> WorkspaceAuditEvent:
        """A repeat of an action already performed; `subject` is the object the first produced."""
        return cls._record(actor, AuditAction(action, OUTCOME_ALREADY_RECORDED), subject, now)

    @classmethod
    def _from_storage(
        cls, *, event_id: str, entry: AuditEntry, occurred_at: datetime
    ) -> WorkspaceAuditEvent:
        with through_door():
            return cls._build(event_id, entry, occurred_at)
