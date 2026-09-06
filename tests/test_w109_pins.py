"""`W1-09`'s pin table (`RCA-005` `FR-128`, `KHEPRI-DEC-034` §1).

`FR-128` closes the field list -- "and **nothing else** -- no count, no access record, no ordering
weight" -- so the assertions here are about *extent* rather than presence. A pin is a stated
preference; a counter is a measurement, and `KHEPRI-DEC-034` §2 authorizes only the first.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

from khepri.rca.persistence import Base
from khepri.rca.workspace.persistence import (
    PIN_KINDS,
    RETENTION_TOMBSTONED,
    WorkspacePinRow,
)
from khepri.rca.workspace.schema import PIN_KIND_FAILURE
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w107_support import LATER, NOW, sealed_version


class TestThePinTable:
    def test_the_column_set_is_exactly_the_permitted_fields(self) -> None:
        """`FR-128` closes the field list.

        Equality, not a subset. A `>=` assertion cannot see a `view_count` added later, which is
        exactly the widening `KHEPRI-DEC-034` §2 refuses -- and `RCA_TABLES` drifted three times
        under assertions that could only ever weaken.

        Read through `inspect(...)`, not the mapped attributes: a column can be added to the table
        without touching a dataclass field set, and a field-set equality stays green through it.
        `W1-02` established the convention for `FR-109`'s reason -- only a schema read can answer
        "no commercial identifier appears in any workspace table".
        """
        columns = {column.name for column in inspect(WorkspacePinRow).columns}

        assert columns == {
            "pin_id",
            "owner_id",
            "object_id",
            "object_kind",
            "pinned_at",
        }

    def test_the_table_is_named_and_reachable_from_the_metadata(self) -> None:
        """The deletion matrix and the migration guard both read `Base.metadata`, so a table
        absent from it is a table those guards cannot see -- the `#240` shape, where a drift guard
        whose inputs depend on import order passed while covering nothing."""
        assert WorkspacePinRow.__tablename__ == "rca_workspace_pins"
        assert "rca_workspace_pins" in Base.metadata.tables

    def test_one_owner_cannot_pin_the_same_object_twice(self) -> None:
        """Idempotency belongs to the database, not to a read-then-write in the store.

        `store.py:711` records why, from `#370`: a reviewer argued concurrent writers agree on the
        state they want and need no lock, and was wrong. SQLite serializes writes, so a
        read-then-write test passes there while PostgreSQL admits the second row -- the
        environment supplying the property the assertion checks. A `UNIQUE` constraint is enforced
        by both engines.
        """
        constraints = {
            constraint.name
            for constraint in WorkspacePinRow.__table__.constraints
            if constraint.name is not None
        }

        assert "uq_rca_workspace_pin_owner_object" in constraints

    def test_the_object_kind_is_a_closed_set(self) -> None:
        """Built from `PIN_KINDS` rather than spelled out, following `_retention_check`: adding a
        third kind without a migration then fails against the constraint rather than silently
        widening it."""
        assert PIN_KINDS == ("dataset_version", "analysis_run")

        checks = {
            constraint.name
            for constraint in WorkspacePinRow.__table__.constraints
            if constraint.name is not None
        }

        assert "ck_rca_workspace_pin_kind" in checks

    def test_the_scope_is_bound_and_indexed(self) -> None:
        """Every workspace table binds `owner_id` to the isolation scope, and every read is by it.

        `RESTRICT` rather than `CASCADE`, as `_scope_foreign_key` gives all of them: a cascade
        would delete workspace rows as a side effect of a delete elsewhere, and
        `KHEPRI-DEC-033`'s deletion records evidence rather than happening silently in the
        database.
        """
        assert {
            constraint.name for constraint in WorkspacePinRow.__table__.foreign_key_constraints
        } == {"fk_rca_workspace_pin_scope"}

        owner = WorkspacePinRow.__table__.columns["owner_id"]
        assert owner.index, "every pin read is scoped by owner_id"
        assert not owner.nullable


class TestTheEnding:
    def test_the_pin_table_has_a_stated_ending(self) -> None:
        """`test_every_workspace_table_has_exactly_one_stated_ending` compares `ENDINGS` against
        `Base.metadata`, so this entry is what lets that guard pass -- and its absence is what made
        it fail when the table was added.

        `deletion_matrix.py` is built as data for exactly this reason: a hand-written cascade
        sequence would have ended nothing here while every existing test stayed green.
        """
        from khepri.rca.workspace.deletion_matrix import ENDING_CASCADE, ENDINGS

        assert ENDINGS["rca_workspace_pins"] == ENDING_CASCADE


class TestTheStoreVerbs:
    """The three verbs, driven through the journey's real store.

    Setup runs through production verbs -- `sealed_version` submits an upload and drives the
    worker -- because raw setup exempts the transition it skips, and a mutant of the bypassed verb
    then survives every test built on it.
    """

    def test_a_pin_round_trips(self) -> None:
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)

        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        (pin,) = j.w.store.pins_for_scope(who.owner_id)
        assert pin.object_id == version.version_id
        assert pin.object_kind == "dataset_version"
        assert pin.pinned_at == NOW

    def test_pinning_twice_is_a_no_op_and_does_not_move_the_instant(self) -> None:
        """`KHEPRI-DEC-034` §1: "Immediate and idempotent on demand."

        The second assertion is the one that matters. Rewriting `pinned_at` on every request would
        turn a stated preference into a record of when it was last asserted -- an access record by
        the back door, which §2 refuses by name.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)

        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=LATER)

        (pin,) = j.w.store.pins_for_scope(who.owner_id)
        assert pin.pinned_at == NOW, "a repeat must not move the instant"

    def test_unpinning_something_unpinned_is_a_no_op(self) -> None:
        """Removing nothing is success: the post-condition a caller wants is that the object is
        not pinned, and it already holds."""
        j = journey()
        who = member(j.w)

        j.w.store.unpin("dsv-absent", owner_id=who.owner_id)

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_a_kind_the_domain_does_not_name_is_refused(self) -> None:
        """Refused in the store as well as by the `CHECK`, and the duplication is the point: the
        constraint holds when a row arrives by another route, and this gives a caller a
        content-free refusal rather than a driver error carrying its input."""
        j = journey()
        who = member(j.w)

        with pytest.raises(ValueError, match=PIN_KIND_FAILURE):
            j.w.store.pin("dsv-1", "organization", owner_id=who.owner_id, now=NOW)

    def test_deleting_the_version_removes_its_pin(self) -> None:
        """`KHEPRI-DEC-034` §1: the pin ends when "the object ends", cascading from the pinned
        object's deletion.

        Driven through `set_retention_state`, the production verb, rather than by deleting the row:
        a fixture that bypasses the verb exempts the transition, and a mutant of the bypassed verb
        survives.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        j.w.store.set_retention_state(
            version.version_id, RETENTION_TOMBSTONED, now=LATER, owner_id=who.owner_id
        )

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_deleting_the_version_removes_a_pin_on_its_run(self) -> None:
        """The run arm of the cascade, which the version arm cannot prove.

        A pin may name a run directly. That run ends with its version through
        `_cascade_tombstone_to_runs`, so its pin must end too -- and a test that pinned only the
        version would pass with the run arm of `_cascade_to_pins` deleted entirely.
        """
        j = journey()
        who = member(j.w)
        version, run = sealed_version(j, who, with_run=True)
        j.w.store.pin(run.run_id, "analysis_run", owner_id=who.owner_id, now=NOW)

        j.w.store.set_retention_state(
            version.version_id, RETENTION_TOMBSTONED, now=LATER, owner_id=who.owner_id
        )

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_a_pin_is_not_visible_to_another_scope(self) -> None:
        """Two scopes written, one read.

        With one organization's rows in the table an unfiltered query returns exactly what a
        filtered one does, so a single-scope test cannot see a missing `WHERE` -- `W1-02`'s
        convention, and the reason both scopes here hold a pin.
        """
        j = journey()
        who = member(j.w)
        other = member(j.w, email="other@example.test", name="Other")
        mine, _ = sealed_version(j, who)
        theirs, _ = sealed_version(j, other)

        j.w.store.pin(mine.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)
        j.w.store.pin(theirs.version_id, "dataset_version", owner_id=other.owner_id, now=NOW)

        assert [pin.object_id for pin in j.w.store.pins_for_scope(who.owner_id)] == [
            mine.version_id
        ]

    def test_one_scope_cannot_unpin_another_scopes_mark(self) -> None:
        """`unpin` is scoped by `owner_id` as well as by the object. The filter is the isolation,
        not an optimization: without it, knowing an opaque identifier would be enough to remove
        another organization's pin."""
        j = journey()
        who = member(j.w)
        other = member(j.w, email="other@example.test", name="Other")
        mine, _ = sealed_version(j, who)
        j.w.store.pin(mine.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        j.w.store.unpin(mine.version_id, owner_id=other.owner_id)

        assert len(j.w.store.pins_for_scope(who.owner_id)) == 1


class TestWhatMayBePinned:
    """`KHEPRI-DEC-034` §1's end trigger is what makes this a requirement rather than tidiness.

    The matrix ends a pin when "the object ends, or the pin is removed, or the organization ends".
    A pin naming an object that never existed has **no end trigger that can ever fire** --
    `cascade_to_pins` only reaches rows whose version is tombstoned -- so it would be a retained
    row outside the matrix the decision authorizes. Found by review on `#390`.
    """

    def test_a_fabricated_identifier_pins_nothing(self) -> None:
        j = journey()
        who = member(j.w)

        j.w.store.pin("dsv-never-existed", "dataset_version", owner_id=who.owner_id, now=NOW)

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_an_object_of_the_wrong_kind_pins_nothing(self) -> None:
        """A real version identifier offered as an analysis run. Both kinds resolve against their
        own table, so the identifier exists and still finds nothing."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)

        j.w.store.pin(version.version_id, "analysis_run", owner_id=who.owner_id, now=NOW)

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_another_scopes_object_pins_nothing(self) -> None:
        """The isolation half. A caller holding another organization's opaque identifier must not
        be able to pin it -- and must not be able to tell that it exists."""
        j = journey()
        who = member(j.w)
        other = member(j.w, email="other@example.test", name="Other")
        theirs, _ = sealed_version(j, other)

        j.w.store.pin(theirs.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_a_deleted_object_pins_nothing(self) -> None:
        """Pinning a version the customer already deleted would create the same unendable row: the
        cascade that would have removed the pin has already run."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        j.w.store.set_retention_state(
            version.version_id, RETENTION_TOMBSTONED, now=NOW, owner_id=who.owner_id
        )

        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=LATER)

        assert j.w.store.pins_for_scope(who.owner_id) == ()

    def test_a_refusal_is_indistinguishable_from_a_repeat(self) -> None:
        """**The reason this refuses by returning rather than raising.**

        If a caller could tell "pinned" from "refused", the pin address would be an existence
        probe: ask whether an opaque identifier belongs to another organization, one guess at a
        time. `FR-050`'s uniform answer exists to prevent exactly that, and `shell_pins.py`'s
        docstring claims this property -- so it gets an assertion rather than a comment.

        Both calls return `None` and raise nothing. The only observable difference is the scope's
        own pin list, which the caller was entitled to read anyway.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        repeat = j.w.store.pin(
            version.version_id, "dataset_version", owner_id=who.owner_id, now=LATER
        )
        fabricated = j.w.store.pin(
            "dsv-never-existed", "dataset_version", owner_id=who.owner_id, now=LATER
        )

        assert repeat is None and fabricated is None
