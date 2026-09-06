"""`W1-09`'s recent-activity view (`RCA-005` `FR-129`, `KHEPRI-DEC-034` §1).

The point of this module is `TestItRetainsNothing`. `FR-129` says the view "MUST retain nothing: no
event, no access record, no counter", and the executable form of that is a before-and-after row
count over *every* workspace table -- which is what distinguishes a view from an event stream.

Setup runs through production verbs (`sealed_version` submits an upload and drives the worker), so
a mutant of a bypassed verb cannot survive behind a hand-shaped row.
"""

from __future__ import annotations

from sqlalchemy import func, select

from khepri.rca.persistence import Base
from khepri.rca.workspace.persistence import RETENTION_TOMBSTONED
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w107_support import LATER, NOW, sealed_version


def _row_counts(factory) -> dict[str, int]:
    """One count per workspace table, derived from the metadata rather than hand-listed.

    A scan that names its own scope reproduces the drift it was written to catch: a table added
    later would go uncounted while this still reported a pass. The emptiness assertion is the
    other half -- a scan that silently finds nothing reports as a passed one.
    """
    tables = {
        name: table
        for name, table in Base.metadata.tables.items()
        if name.startswith("rca_workspace_")
    }
    assert tables, "the metadata yielded no workspace tables, so this guard checks nothing"
    with factory() as database:
        return {
            name: database.scalar(select(func.count()).select_from(table))
            for name, table in tables.items()
        }


class TestTheOrdering:
    def test_it_reads_the_instants_the_records_already_carry(self) -> None:
        """`KHEPRI-DEC-034` §1: "a query over dataset versions and analysis runs the workspace
        already stores ... ordered by instants those records already carry."

        Nothing is written to establish the order, and nothing needs to be: the records were
        already timestamped by the acts that created them.
        """
        j = journey()
        who = member(j.w)
        version, run = sealed_version(j, who, with_run=True)

        recent = j.w.store.recent_activity(who.owner_id)

        assert {item.object_id for item in recent} == {version.version_id, run.run_id}
        assert [item.occurred_at for item in recent] == sorted(
            (item.occurred_at for item in recent), reverse=True
        ), "most recent first"

    def test_both_kinds_are_named_the_way_a_pin_names_them(self) -> None:
        """One vocabulary across both halves of `W1-09`.

        A surface renders pins and recent items side by side, so a version called
        `dataset_version` in one and `version` in the other would make the template carry a
        translation -- and the audit vocabulary those alternatives come from governs evidence
        records, not presentation labels.
        """
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)

        kinds = {item.object_kind for item in j.w.store.recent_activity(who.owner_id)}

        assert kinds == {"dataset_version", "analysis_run"}

    def test_it_is_bounded(self) -> None:
        """A convenience view, not a history spine. `W1-05`'s Analyses surface is where a full
        listing lives; this shows the few most recent so returning to work needs no search."""
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)

        assert len(j.w.store.recent_activity(who.owner_id, limit=1)) == 1

    def test_another_scope_sees_none_of_it(self) -> None:
        """Two scopes written, one read -- `W1-02`'s convention, for the reason a single-scope
        test cannot see a missing `WHERE`: with one organization's rows in the table, an
        unfiltered query returns exactly what a filtered one does."""
        j = journey()
        who = member(j.w)
        other = member(j.w, email="other@example.test", name="Other")
        sealed_version(j, who, with_run=True)

        assert j.w.store.recent_activity(other.owner_id) == ()

    def test_a_tombstoned_version_and_its_run_are_both_dropped(self) -> None:
        """Deleting the underlying record removes it from the view -- `KHEPRI-DEC-034` §1's
        matrix, which gives the view no end trigger of its own precisely because it holds nothing.

        **Both arms of the UNION, in one case.** `AnalysisRunRow` carries its own
        `retention_state`, so the read has two retention filters, and a version-only assertion
        would prove one while the run arm returned tombstoned rows untouched. The run here is
        tombstoned by the cascade rather than directly, which is how it happens in production.
        """
        j = journey()
        who = member(j.w)
        version, _run = sealed_version(j, who, with_run=True)
        assert len(j.w.store.recent_activity(who.owner_id)) == 2, "both arms populated"

        j.w.store.set_retention_state(
            version.version_id, RETENTION_TOMBSTONED, now=LATER, owner_id=who.owner_id
        )

        assert j.w.store.recent_activity(who.owner_id) == ()


class TestItRetainsNothing:
    def test_reading_the_view_writes_no_row_to_any_workspace_table(self) -> None:
        """`FR-129`, executable: "It MUST retain nothing: no event, no access record, no counter.
        A view that writes a row to answer 'what was recent' is product telemetry and is excluded
        by this specification, whatever it is named."

        Read twice, because a writer that recorded only the first read -- an "first seen" row, say
        -- would leave the second pair of counts equal to the first and pass a single-read test.

        Counted over every workspace table rather than the ones a writer would plausibly touch:
        the counter this guards against is at least as likely to land on the version or run row as
        on a table of its own.
        """
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)
        before = _row_counts(j.w.factory)

        j.w.store.recent_activity(who.owner_id)
        j.w.store.recent_activity(who.owner_id)

        assert _row_counts(j.w.factory) == before

    def test_it_writes_no_audit_event(self) -> None:
        """The audit trail is `KHEPRI-DEC-015` §7 security-and-audit evidence, not a product feed.

        `RCA-005` closes the conversion in advance -- "an audit event that begins to carry a
        product metric has become telemetry and is excluded" -- so the view neither reads the
        events nor adds to them.
        """
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)
        before = len(j.w.audit.events_for_scope(who.owner_id))

        j.w.store.recent_activity(who.owner_id)

        assert len(j.w.audit.events_for_scope(who.owner_id)) == before

    def test_a_pin_does_not_appear_as_recent_activity(self) -> None:
        """Pinning is not working on something.

        The two halves of `W1-09` stay separate: `FR-129`'s view reads dataset versions and
        analysis runs, and if pinning fed it, the pin table would have become an activity log --
        a record of when a person did something, which is the shape §2 refuses.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        before = j.w.store.recent_activity(who.owner_id)

        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        assert j.w.store.recent_activity(who.owner_id) == before
