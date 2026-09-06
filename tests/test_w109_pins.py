"""`W1-09`'s pin table (`RCA-005` `FR-128`, `KHEPRI-DEC-034` §1).

`FR-128` closes the field list -- "and **nothing else** -- no count, no access record, no ordering
weight" -- so the assertions here are about *extent* rather than presence. A pin is a stated
preference; a counter is a measurement, and `KHEPRI-DEC-034` §2 authorizes only the first.
"""

from __future__ import annotations

from sqlalchemy import inspect

from khepri.rca.persistence import Base
from khepri.rca.workspace.persistence import PIN_KINDS, WorkspacePinRow


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
