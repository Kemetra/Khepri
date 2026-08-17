"""`20260817_0017` lets one opaque scope hold many analysis sessions (`R7-02`).

**What makes this file necessary rather than ceremonial.** The revision's SQLite path rebuilds the
table, and Alembic's `recreate="auto"` skips the rebuild when it sees no operation demanding one --
so a migration that changes *nothing* completes without error and reports success. That exact
no-op was reached four times while developing the revision. Every test below therefore asserts the
**post-state read back by reflection**, never that the migration ran.

The complementary claim matters as much: `uq_session_owner_scope` must **survive**. A rebuild that
dropped both constraints would satisfy "the single-column one is gone" while destroying the
invariant `KHEPRI-DEC-020` §2 says to keep.

**Not a `test_rra*` file by accident.** `FR-037` requires `RRA-001`'s controls stay covered by its
existing tests *unmodified*, and `KHEPRI-DEC-020` §3 repeats that no `test_rra*` file may be edited.
This file is new and edits none of them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from khepri.rra.persistence import Base as RraBase

REPO_ROOT = Path(__file__).resolve().parents[1]
REVISION = "20260817_0017"
SLUG = "rra_sessions_allow_many_per_scope"
TABLE = "rra_beta_sessions"
COMPOSITE = "uq_session_owner_scope"


def _migration_module() -> ModuleType:
    path = REPO_ROOT / "migrations" / "versions" / f"{REVISION}_{SLUG}.py"
    spec = importlib.util.spec_from_file_location(f"_migration_{REVISION}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _drive(engine: sa.Engine, direction: str) -> None:
    """Run the revision's own `upgrade`/`downgrade` against a real engine and DDL dialect."""
    module = _migration_module()
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        token = module.op
        try:
            module.op = operations
            getattr(module, direction)()
        finally:
            module.op = token


def _unique_constraints(engine: sa.Engine) -> list[dict[str, object]]:
    with engine.connect() as connection:
        return sa.inspect(connection).get_unique_constraints(TABLE)


def _single_column_owner_uniques(engine: sa.Engine) -> list[dict[str, object]]:
    return [
        constraint
        for constraint in _unique_constraints(engine)
        if list(constraint["column_names"]) == ["owner_id"]  # type: ignore[arg-type]
    ]


def _composite_survives(engine: sa.Engine) -> bool:
    return any(
        list(constraint["column_names"]) == ["owner_id", "session_id"]  # type: ignore[arg-type]
        for constraint in _unique_constraints(engine)
    )


@pytest.fixture(name="engine")
def _engine(tmp_path: Path) -> sa.Engine:
    """A real file-backed SQLite database at the pre-revision schema.

    Built from the ORM's `create_all` rather than by replaying the migration chain, because the
    earlier RRA revisions use ALTER-style operations the SQLite dialect refuses -- the same reason
    `test_rca001_migration.py:106-109` gives. The ORM no longer declares the constraint this
    revision drops, so the fixture adds it back explicitly: that is what makes the starting state
    the *pre-revision* one rather than the post-revision one, and without it every assertion below
    would pass vacuously.
    """
    engine = sa.create_engine(f"sqlite+pysqlite:///{(tmp_path / 'scope.db').as_posix()}")
    RraBase.metadata.create_all(engine)
    with engine.begin() as connection:
        table = sa.Table(TABLE, sa.MetaData(), autoload_with=connection)
        table.append_constraint(sa.UniqueConstraint("owner_id"))
        operations = Operations(MigrationContext.configure(connection))
        with operations.batch_alter_table(TABLE, copy_from=table, recreate="always"):
            pass
    assert _single_column_owner_uniques(engine), "fixture did not establish the pre-revision schema"
    return engine


def test_the_fixture_starts_from_the_constraint_this_revision_removes(engine: sa.Engine) -> None:
    """Guards every other test here. If the fixture drifts to the post-revision schema, the
    upgrade assertions pass without the migration doing anything."""
    assert len(_single_column_owner_uniques(engine)) == 1
    assert _composite_survives(engine)


def test_upgrade_removes_the_single_column_scope_constraint(engine: sa.Engine) -> None:
    """The claim `KHEPRI-DEC-020` §2 authorizes, asserted by reading the schema back."""
    _drive(engine, "upgrade")
    assert _single_column_owner_uniques(engine) == []


def test_upgrade_keeps_the_composite_constraint(engine: sa.Engine) -> None:
    """Fails on a rebuild that drops both -- which would read as success to the test above."""
    _drive(engine, "upgrade")
    assert _composite_survives(engine)


def test_upgrade_lets_one_scope_hold_two_sessions(engine: sa.Engine) -> None:
    """The behavioral claim, and the one that actually matters to `R7`.

    Asserting constraint metadata is not the same as asserting the database accepts the write:
    a rebuild could drop the named constraint and leave an equivalent unique *index*, which
    reflection reports differently but which refuses the row identically.
    """
    _drive(engine, "upgrade")
    _insert_session(engine, session_id="ses_first", owner_id="own_shared")
    _insert_session(engine, session_id="ses_second", owner_id="own_shared")
    with engine.connect() as connection:
        count = connection.execute(
            sa.text(f"SELECT COUNT(*) FROM {TABLE} WHERE owner_id = :owner"),
            {"owner": "own_shared"},
        ).scalar_one()
    assert count == 2


def test_the_composite_still_refuses_a_duplicated_pairing(engine: sa.Engine) -> None:
    """Keeping the composite is only meaningful if it still fires."""
    _drive(engine, "upgrade")
    _insert_session(engine, session_id="ses_only", owner_id="own_shared")
    with pytest.raises(sa.exc.IntegrityError):
        _insert_session(engine, session_id="ses_only", owner_id="own_shared")


def test_downgrade_restores_the_constraint(engine: sa.Engine) -> None:
    _drive(engine, "upgrade")
    _drive(engine, "downgrade")
    assert len(_single_column_owner_uniques(engine)) == 1
    assert _composite_survives(engine)


def test_downgrade_refuses_to_discard_a_second_analysis(engine: sa.Engine) -> None:
    """`KHEPRI-DEC-020` §2 requires the downgrade fail rather than delete commercial content.

    Two sessions under one scope are two real analyses. A downgrade that silently dropped one to
    satisfy the restored constraint would destroy customer content; `RRA-002`'s deletion path is
    how content leaves.
    """
    _drive(engine, "upgrade")
    _insert_session(engine, session_id="ses_first", owner_id="own_shared")
    _insert_session(engine, session_id="ses_second", owner_id="own_shared")
    with pytest.raises(sa.exc.IntegrityError):
        _drive(engine, "downgrade")


def test_the_orm_model_no_longer_declares_the_constraint() -> None:
    """The database and the model must agree.

    A migration that changed only the database would leave `create_all` -- which every store test
    builds its schema from -- still refusing a second session, so the whole suite would model
    weaker semantics than production. `20260814_0015` records the same reasoning in reverse.
    """
    table = RraBase.metadata.tables[TABLE]
    assert table.c.owner_id.unique is not True
    single_column = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
        and [column.name for column in constraint.columns] == ["owner_id"]
    ]
    assert single_column == []
    assert any(
        isinstance(constraint, sa.UniqueConstraint)
        and [column.name for column in constraint.columns] == ["owner_id", "session_id"]
        for constraint in table.constraints
    ), f"{COMPOSITE} is the invariant that must remain"


def test_a_freshly_created_schema_accepts_two_sessions_per_scope() -> None:
    """`create_all`, not the migration -- the path every store test uses.

    Without this, the ORM and migration could diverge in the direction the migration test cannot
    see: green migration tests plus a model that still refuses the write.
    """
    engine = sa.create_engine("sqlite://")
    RraBase.metadata.create_all(engine)
    _insert_session(engine, session_id="ses_first", owner_id="own_shared")
    _insert_session(engine, session_id="ses_second", owner_id="own_shared")


def _insert_session(engine: sa.Engine, *, session_id: str, owner_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                f"INSERT INTO {TABLE} "
                "(session_id, owner_id, created_at, content_expires_at) "
                "VALUES (:session_id, :owner_id, '2026-08-17 00:00:00', '2026-08-24 00:00:00')"
            ),
            {"session_id": session_id, "owner_id": owner_id},
        )
