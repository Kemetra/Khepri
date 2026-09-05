"""The staged Analyses spine reads what `W1-04` wrote and what `W1-03` tombstoned -- through the
real stores and isolation door (`FR-117`, `FR-122`; the lesson of `#373`'s first review).

A run completed by the real actions over the real `RRA-004` package shows its report as available,
because every required artifact is bound; a version deleted through the store's one deletion door
cascades to its run, and that run reads as a tombstone in the internal renderer while the Data
surface no longer lists the version. A second organization on the same engine sees none of it.

The public Analyses route remains withheld under `FR-049` until trust state can be persisted and a
valid next action is addressable; these tests exercise the read model without exposing that route.

`artifact_bindings_for_scope` is the read this surface adds to the store, and it is exercised here
against real rows: scoped, joined to a live run, and hiding the bindings of a tombstoned one.
"""

from __future__ import annotations

from sqlalchemy import event

from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_copy import SHELL_COPY
from tests.w104_support import LATER, member, world
from tests.w105_support import completed_run, page, staged_analyses_page, started_run


def _rows(html: str) -> list[str]:
    return html.split('<li class="spine-item')[1:]


def test_a_completed_run_shows_its_report_as_available() -> None:
    w = world()
    who = member(w)
    completed_run(w, who)

    rows = _rows(staged_analyses_page(w, who))

    assert len(rows) == 1
    assert SHELL_COPY["en"]["run_state_completed"] in rows[0]
    assert SHELL_COPY["en"]["report_available"] in rows[0]


def test_a_started_run_has_no_report_yet() -> None:
    w = world()
    who = member(w)
    started_run(w, who)

    rows = _rows(staged_analyses_page(w, who))

    assert len(rows) == 1
    assert SHELL_COPY["en"]["run_state_started"] in rows[0]
    assert SHELL_COPY["en"]["report_not_yet"] in rows[0]


def test_a_deleted_versions_run_reads_as_a_tombstone_and_the_data_row_is_gone() -> None:
    w = world()
    who = member(w)
    _session_id, version_id, _run_id = completed_run(w, who)
    w.store.tombstone_dataset_version(version_id, now=LATER, owner_id=who.owner_id)

    spine = _rows(staged_analyses_page(w, who))
    data = page(w, who, "data")

    assert len(spine) == 1
    assert "spine-item--tombstone" in spine[0]
    assert SHELL_COPY["en"]["tombstone_deleted"] in spine[0]
    assert SHELL_COPY["en"]["report_available"] not in spine[0]
    assert "data-item" not in data


def test_another_organization_sees_no_history() -> None:
    w = world()
    who = member(w)
    other = member(w, email="other@example.test", name="Other")
    completed_run(w, who)

    html = staged_analyses_page(w, other)

    assert "spine-item" not in html
    assert SHELL_COPY["en"]["analyses_empty"] in html


def test_bindings_for_scope_are_scoped_joined_to_live_runs_and_hide_the_deleted() -> None:
    w = world()
    who = member(w)
    other = member(w, email="other@example.test", name="Other")
    _session_id, version_id, run_id = completed_run(w, who)

    before = w.store.artifact_bindings_for_scope(who.owner_id)
    assert {binding.run_id for binding in before} == {run_id}
    assert len(before) == len(REQUIRED_ARTIFACT_KINDS)
    assert w.store.artifact_bindings_for_scope(other.owner_id) == ()

    w.store.tombstone_dataset_version(version_id, now=LATER, owner_id=who.owner_id)

    assert w.store.artifact_bindings_for_scope(who.owner_id) == ()


def test_the_history_is_one_read_carrying_all_four_parts() -> None:
    """`history_for_scope` is what the shell reads: the four parts of one scope in one transaction,
    with the deleted run present only as its tombstone."""
    w = world()
    who = member(w)
    _session_id, version_id, run_id = completed_run(w, who)

    live = w.store.history_for_scope(who.owner_id)
    w.store.tombstone_dataset_version(version_id, now=LATER, owner_id=who.owner_id)
    after = w.store.history_for_scope(who.owner_id)

    assert [run.run_id for run in live.runs] == [run_id]
    assert len(live.bindings) == len(REQUIRED_ARTIFACT_KINDS) and live.tombstones == ()
    assert after.runs == () and after.bindings == () and after.versions == ()
    assert {tombstone.deleted_at for tombstone in after.tombstones} == {LATER}


def test_the_history_parts_share_one_database_transaction() -> None:
    """The store-level history read is one snapshot boundary, not four method calls that each
    open a fresh transaction (review on `#374`)."""
    w = world()
    who = member(w)
    completed_run(w, who)
    transactions: list[object] = []

    def record_transaction(_session: object, transaction: object, _connection: object) -> None:
        transactions.append(transaction)

    session_type = w.factory.class_
    event.listen(session_type, "after_begin", record_transaction)
    try:
        w.store.history_for_scope(who.owner_id)
    finally:
        event.remove(session_type, "after_begin", record_transaction)

    assert len(transactions) == 1
