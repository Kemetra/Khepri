"""The Analyses spine reads what `W1-04` wrote and what `W1-03` tombstoned -- through the real
stores and the real isolation door (`FR-117`, `FR-122`; the lesson of `#373`'s first review).

A run completed by the real actions over the real `RRA-004` package shows its report as available,
because every required artifact is bound; a version deleted through the store's one deletion door
cascades to its run, and that run reads as a tombstone on the spine while the Data surface no
longer lists the version. A second organization on the same engine sees none of it.

`artifact_bindings_for_scope` is the read this surface adds to the store, and it is exercised here
against real rows: scoped, joined to a live run, and hiding the bindings of a tombstoned one.
"""

from __future__ import annotations

from khepri.rra.report_artifacts import REQUIRED_ARTIFACT_KINDS
from khepri.runtime.shell_copy import SHELL_COPY
from tests.w104_support import LATER, member, world
from tests.w105_support import completed_run, page, started_run


def _rows(html: str) -> list[str]:
    return html.split('<li class="spine-item')[1:]


def test_a_completed_run_shows_its_report_as_available() -> None:
    w = world()
    who = member(w)
    completed_run(w, who)

    rows = _rows(page(w, who, "analyses"))

    assert len(rows) == 1
    assert SHELL_COPY["en"]["run_state_completed"] in rows[0]
    assert SHELL_COPY["en"]["report_available"] in rows[0]


def test_a_started_run_has_no_report_yet() -> None:
    w = world()
    who = member(w)
    started_run(w, who)

    rows = _rows(page(w, who, "analyses"))

    assert len(rows) == 1
    assert SHELL_COPY["en"]["run_state_started"] in rows[0]
    assert SHELL_COPY["en"]["report_not_yet"] in rows[0]


def test_a_deleted_versions_run_reads_as_a_tombstone_and_the_data_row_is_gone() -> None:
    w = world()
    who = member(w)
    _session_id, version_id, _run_id = completed_run(w, who)
    w.store.tombstone_dataset_version(version_id, now=LATER, owner_id=who.owner_id)

    spine = _rows(page(w, who, "analyses"))
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

    html = page(w, other, "analyses")

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
