"""`W1-04` -- the audit event and its table (`RCA-005` `FR-125`; `KHEPRI-DEC-015` §7).

Split from `test_w104_workspace_services.py`: these are about the *record* -- what an event may
carry, how the table constrains it, that the migration agrees -- and the other file is about the
actions that produce one. The fixtures are shared through `tests/w104_support.py`.

**Equality, not absence.** `FR-125` fixes the event's contents: opaque actor, opaque organization,
object identifiers, action, outcome, timestamp. The field set is asserted equal to that list, and
again off the emitted table, so a column that could carry content fails until named here.
"""

from __future__ import annotations

from dataclasses import fields

import pytest
from sqlalchemy import inspect

from khepri.rca.workspace.audit import (
    ACTION_PROFILE_REMEMBERED,
    ACTION_PROFILE_REUSED,
    ACTION_RETENTION_SWEPT,
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    ACTION_RUN_STARTED,
    ACTION_VERSION_CREATED,
    ACTION_VERSION_DELETED,
    AUDIT_ACTIONS,
    AUDIT_OBJECTS,
    AUDIT_OUTCOMES,
    OBJECT_PROFILE,
    OBJECT_RUN,
    OBJECT_VERSION,
    OUTCOME_ALREADY_DELETED,
    OUTCOME_ALREADY_RECORDED,
    OUTCOME_COMPLETED,
    OUTCOME_REFUSED,
    AuditActor,
    AuditSubject,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import WorkspaceAuditEventRow
from tests.w104_support import NOW, events, member, world


def _field_names(record_type: type) -> set[str]:
    return {f.name for f in fields(record_type)}


def test_audit_event_fields_are_exactly_fr125s() -> None:
    """Opaque actor, opaque organization, object identifiers, action, outcome, timestamp -- and
    nothing else. Equality, so a field that could carry content fails until named here."""
    assert _field_names(WorkspaceAuditEvent) == {
        "event_id",
        "owner_id",
        "actor_account_id",
        "action",
        "outcome",
        "object_kind",
        "object_id",
        "occurred_at",
    }


def test_the_audit_vocabularies_are_closed() -> None:
    assert set(AUDIT_ACTIONS) == {
        ACTION_VERSION_CREATED,
        ACTION_RUN_STARTED,
        ACTION_RUN_COMPLETED,
        ACTION_RUN_FAILED,
        ACTION_PROFILE_REMEMBERED,
        ACTION_PROFILE_REUSED,
        # `W1-07a` (`FR-123`): a customer ending a dataset version. The cascade to its runs is
        # part of this action, so there is no `run_deleted` beside it.
        ACTION_VERSION_DELETED,
        # `W1-07b` (`FR-125`, which names `sweep` literally): one retention pass over one scope.
        # Its subject is `None` -- a sweep acts on a class over a horizon, not on an object -- so
        # `AUDIT_OBJECTS` below is unchanged, which is the point of asserting all three sets here.
        ACTION_RETENTION_SWEPT,
    }
    assert set(AUDIT_OUTCOMES) == {
        OUTCOME_COMPLETED,
        OUTCOME_REFUSED,
        OUTCOME_ALREADY_RECORDED,
        # `W1-07a`. `FR-123` names this string, and it is not `already_recorded`: that one says a
        # write was a duplicate, this says the object had already ended.
        OUTCOME_ALREADY_DELETED,
    }
    assert set(AUDIT_OBJECTS) == {OBJECT_VERSION, OBJECT_RUN, OBJECT_PROFILE}


@pytest.mark.parametrize(
    ("action", "kind"),
    [("deleted_everything", OBJECT_VERSION), (ACTION_RUN_STARTED, "session")],
)
def test_an_audit_event_refuses_a_word_outside_its_vocabulary(action: str, kind: str) -> None:
    """Fail closed (Constitution V): an unrecognized action or object kind is refused, not stored.
    A `session` object kind is refused in particular -- `KHEPRI-DEC-015` §7 forbids the session
    identifier from any log, and an event that could name one would be that log."""
    actor = AuditActor(owner_id="own_abc", actor_account_id="acc_abc")
    with pytest.raises(ValueError):
        WorkspaceAuditEvent.completed(actor, action, AuditSubject(kind, "x_1"), now=NOW)


def test_the_audit_table_holds_exactly_the_events_columns() -> None:
    """Read off the emitted schema, not the model's fields (`W1-02`'s reasoning): a column added
    to the table without touching the dataclass would pass a field-set test."""
    columns = {column.name for column in WorkspaceAuditEventRow.__table__.columns}
    assert columns == _field_names(WorkspaceAuditEvent)


def test_the_migration_states_the_same_audit_vocabularies_the_model_does() -> None:
    """The migration keeps literal strings by this repo's convention, so the two can drift.

    **Each constant is read from the migration that states it *last*, not from a named file.**
    This guard pointed at `20260905_0022` while that was the only migration to set these
    constraints; `W1-07a`'s `20260906_0026` widened two of the three, and the guard could not see
    it. A drift guard that hand-names its source reproduces the drift it exists to catch, and
    re-pinning it to `0026` would only move the trap one slice along -- `0026` does not restate
    `_OBJECTS`, so the newest file is not the authority for every constant, only for the ones it
    spells.
    """
    import pathlib
    import re

    versions = pathlib.Path(__file__).resolve().parents[1] / "migrations" / "versions"
    sources = sorted(
        (path.name, path.read_text(encoding="utf-8")) for path in versions.glob("*.py")
    )

    def literal(constant: str) -> set[str]:
        marker = f"{constant} = "
        bodies = [
            text.split(marker, 1)[1].splitlines()[0] for _name, text in sources if marker in text
        ]
        assert bodies, f"no migration states {constant}"
        return set(re.findall(r"'([a-z_]+)'", bodies[-1]))

    assert literal("_ACTIONS_AFTER") == set(AUDIT_ACTIONS)
    assert literal("_OUTCOMES_AFTER") == set(AUDIT_OUTCOMES)
    assert literal("_OBJECTS") == set(AUDIT_OBJECTS)


def test_audit_events_are_read_by_scope_and_cannot_be_rewritten() -> None:
    w = world()
    ours, theirs = member(w), member(w, "other@example.test", "Other")
    for who in (ours, theirs):
        actor = AuditActor(owner_id=who.owner_id, actor_account_id=who.account_id)
        w.audit.record(
            WorkspaceAuditEvent.completed(
                actor, ACTION_RUN_STARTED, AuditSubject(OBJECT_RUN, "run_x"), now=NOW
            )
        )

    assert [e.owner_id for e in w.audit.events_for_scope(ours.owner_id)] == [ours.owner_id]
    with w.factory.begin() as database:
        row = database.get(WorkspaceAuditEventRow, events(w, ours)[0].event_id)
        row.outcome = OUTCOME_REFUSED
        with pytest.raises(ValueError, match="audit event"):
            database.flush()


def test_the_audit_table_is_a_workspace_table_keyed_by_scope() -> None:
    """Every workspace table is keyed by the opaque scope (`FR-109`). The audit table carries no
    foreign key onto it, for the reason `rca_membership_events` carries none: the event must
    outlive the organization it describes until its own twelve-month horizon, and a `RESTRICT`
    key would enforce the opposite ordering."""
    table = WorkspaceAuditEventRow.__table__
    assert table.name == "rca_workspace_audit_events"
    assert not table.foreign_keys
    indexed = {tuple(column.name for column in index.columns) for index in table.indexes}
    assert ("owner_id",) in indexed and ("occurred_at",) in indexed


def test_no_workspace_column_can_hold_a_session_identifier() -> None:
    """`KHEPRI-DEC-015` §7: the session identifier never reaches a log, and no workspace column
    can hold one -- the link between a version and its upload is the digest, between a run and its
    package the package digest.

    **One job column, on one table.** `W1-04b` binds each run to the report job that settles it
    (`rca_workspace_run_reports.job_id`), because the worker holds a job and must find the run.
    A job identifier confers nothing (`FR-023`) and is not bearer-adjacent, which is the property
    this test protects; the allowance is exact so a job column arriving anywhere else, or a second
    one here, still fails.
    """
    w = world()
    inspector = inspect(w.factory().get_bind())
    job_columns: dict[str, set[str]] = {}
    for table in inspector.get_table_names():
        if not table.startswith("rca_workspace_"):
            continue
        names = {column["name"] for column in inspector.get_columns(table)}
        assert not {name for name in names if "session" in name}, table
        if jobs := {name for name in names if "job" in name}:
            job_columns[table] = jobs
    assert job_columns == {"rca_workspace_run_reports": {"job_id"}}
