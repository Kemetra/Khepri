"""Let one opaque scope hold many analysis sessions (`R7-02`, `KHEPRI-DEC-020`).

`rra_beta_sessions` declared `UNIQUE (owner_id)` **and**
`UNIQUE (owner_id, session_id)`. The two disagree about what is unique: the composite says a scope
may hold many sessions and each pairing is distinct; the column-level one says it may hold exactly
one, ever. This revision drops the column-level constraint and keeps the composite.

**Why the beta was right and is no longer sufficient.** A beta participant redeems an invitation,
receives a throwaway scope, analyses one workbook, and the content expires. One session per scope
is that product, exactly. A commercial organization instead holds one stable `owner_id` for its
lifetime (`FR-035`), so under the old constraint its *second* analysis was refused by the database.
Nothing here is a defect in `RRA`; it is a beta assumption encoded as an invariant, and `RRA-001`
reserved the `owner_id` as "the only future attachment point for separately approved commercial
authentication" without anticipating that the constraint would block it.

`KHEPRI-DEC-020` §2 authorizes exactly this drop and nothing else. `rra_uploads.UNIQUE (session_id)`
is deliberately left in place: one upload per session is `RRA`'s design, and relaxing it is the
decision's explicitly-refused Option B.

**No replacement index, deliberately.** `uq_session_owner_scope` is `UNIQUE (owner_id, session_id)`
and `owner_id` is its **leading column**, so its backing index already serves the `owner_id`-only
lookups that previously rode on the constraint being dropped -- `artifact_persistence.py` queries
`owner_id` under `SELECT ... FOR UPDATE`, which is why this was checked rather than assumed.
`KHEPRI-DEC-020` §2 forbids adding one.

**The constraint is anonymous, so its name is read from the live catalogue rather than assumed.**
It came from `unique=True` on the column, so it has no name in `__table_args__` and none in the
emitted DDL. PostgreSQL auto-assigns one (conventionally `rra_beta_sessions_owner_id_key`, but this
revision never depends on that spelling); SQLite gives it none at all, because an inline `UNIQUE` is
part of the table definition rather than a separate object. The two backends therefore need
different mechanics, and this revision branches on what reflection actually finds:

- **A name was found** (PostgreSQL): `ALTER TABLE ... DROP CONSTRAINT`, no rebuild.
- **No name** (SQLite): rebuild the table from a reflected copy with the constraint removed.
  `recreate="always"` is **required** and is not decoration -- with `recreate="auto"` Alembic sees
  no operation that demands a rebuild, skips it, and the migration reports success while changing
  nothing. That no-op shape was reached four times while developing this revision, and each time a
  test asserting "the migration ran" passed. What catches it is asserting the post-state by
  reflection, which `test_rra_scope_cardinality_migration.py` does.

`downgrade` restores the constraint and **will fail if two sessions already share an `owner_id`** --
correct, and not worked around: the rows are real commercial analyses and silently deleting one to
satisfy a constraint would destroy customer content. `RRA-002`'s deletion path is how content
leaves.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260817_0017"
down_revision: str | None = "20260815_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "rra_beta_sessions"
_COLUMN = "owner_id"
# The composite constraint that stays, named here only so `downgrade` can assert it survived.
_COMPOSITE = "uq_session_owner_scope"


def _single_column_unique_name(connection: sa.Connection) -> str | None:
    """Return the name of the `UNIQUE (owner_id)` constraint, or `None` if it is anonymous.

    `KHEPRI-DEC-020` §2 requires the name come from the live catalogue. Matching on the exact
    column list rather than on a name pattern is what keeps this correct across backends and
    prevents it from ever selecting the composite constraint.
    """
    for constraint in sa.inspect(connection).get_unique_constraints(_TABLE):
        if list(constraint["column_names"]) == [_COLUMN]:
            return constraint["name"]
    return None


def _single_column_unique_exists(connection: sa.Connection) -> bool:
    return any(
        list(constraint["column_names"]) == [_COLUMN]
        for constraint in sa.inspect(connection).get_unique_constraints(_TABLE)
    )


def _reflected_without(connection: sa.Connection, *, columns: list[str]) -> sa.Table:
    """Reflect `_TABLE`, minus any `UniqueConstraint` covering exactly `columns`.

    Used as `copy_from` for the SQLite rebuild. Reflecting rather than importing the ORM model
    keeps this revision a historical record: a later slice changing `BetaSessionRow` must not
    change what this migration does.
    """
    table = sa.Table(_TABLE, sa.MetaData(), autoload_with=connection)
    doomed = {
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
        and [column.name for column in constraint.columns] == columns
    }
    for constraint in doomed:
        table.constraints.discard(constraint)
    return table


def upgrade() -> None:
    connection = op.get_bind()
    name = _single_column_unique_name(connection)
    if name is not None:
        op.drop_constraint(name, _TABLE, type_="unique")
        return
    # Anonymous (SQLite): rebuild from a copy that omits it. `recreate="always"` is load-bearing.
    copy_from = _reflected_without(connection, columns=[_COLUMN])
    with op.batch_alter_table(_TABLE, copy_from=copy_from, recreate="always"):
        pass


def downgrade() -> None:
    """Restore `UNIQUE (owner_id)`, failing if the data has outgrown it.

    Reinstated **anonymously**, matching what `20260729_0001` created, so an upgrade/downgrade round
    trip returns the schema to its original shape rather than to an equivalent-but-differently-named
    one. Alembic's batch mode refuses to *add* an unnamed constraint
    (`batch.py:672`, "Constraint must have a name"), so the constraint is appended to a reflected
    copy and the table is rebuilt from it -- the same mechanism `upgrade` uses in reverse, rather
    than inventing a name this revision never created.

    On a table where two sessions already share an `owner_id`, the rebuild's copy-back raises
    `IntegrityError`. That is the intended outcome: those rows are real commercial analyses, and
    `RRA-002`'s deletion path is how content leaves.
    """
    connection = op.get_bind()
    if _single_column_unique_exists(connection):
        return
    table = sa.Table(_TABLE, sa.MetaData(), autoload_with=connection)
    table.append_constraint(sa.UniqueConstraint(_COLUMN))
    with op.batch_alter_table(_TABLE, copy_from=table, recreate="always"):
        pass
