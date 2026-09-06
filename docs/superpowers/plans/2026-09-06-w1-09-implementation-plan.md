# W1-09 Pins and Recent Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an owner pin a dataset version or analysis run for quick return, and see what they last worked on, without retaining a single new fact about their behaviour beyond the pin itself.

**Architecture:** Two halves, deliberately asymmetric. `FR-128`'s pin is one new table (`rca_workspace_pins`) with a migration, a deletion-matrix entry and three store verbs, surfaced by a mutating route module of its own. `FR-129`'s recent-activity view is a read-time query over dataset versions and analysis runs the workspace already holds — no table, no migration, no event. Both render as sections on the Overview surface `W1-05` built.

**Tech Stack:** Python 3.13, SQLAlchemy 2.x declarative (`Mapped`/`mapped_column`), Alembic, FastAPI, Jinja2, pytest.

**Spec:** `docs/superpowers/plans/2026-09-06-w1-09-pins-and-recent-activity.md`

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from the governing artifacts.

- **Authority:** active `KHEPRI-DEC-034`; `RCA-005` `FR-128`, `FR-129`. Nothing here amends `KHEPRI-DEC-015` §3 — `W1-11` and `R8-08` stay excluded, and nothing built here is precedent for either.
- **The pin's fields are closed:** `owner_id`, opaque `object_id`, `object_kind`, `pinned_at`, plus the scope key — **"and nothing else — no count, no access record, no ordering weight"** (`FR-128`).
- **A pin emits no `FR-125` audit event and adds no member to `AUDIT_ACTIONS`** (`FR-128`, literally).
- **The activity view MUST retain nothing:** no event, no access record, no counter (`FR-129`).
- **No counting, ranking or frequency anywhere** — no "most used", "opened N times", "trending" (`KHEPRI-DEC-034` §2).
- **No inactivity expiry** (`KHEPRI-DEC-033` §4).
- **No surface may state that content expires automatically** beyond `KHEPRI-DEC-033` §5's caution.
- **Isolation:** `RCA-001` `FR-031`–`FR-035`'s opaque `owner_id` is the only isolation key. No commercial identifier in or derivable from it.
- **One Alembic head; no downgrade that cannot run.**
- **Bilingual parity (en/ar), RTL, target size, no colour alone, no inline script or style, CSP unweakened.**
- **No figure computed, rounded or summed on a workspace surface.**
- **Run tests with `./.venv/Scripts/python.exe -m pytest`.** Do **not** run `ruff format` (no CI format gate); `ruff check` only.
- **Commits:** `git commit -F <file>` (rebase ignores `-c commit.gpgsign`).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/khepri/rca/workspace/schema.py` | **Modify.** Add `WorkspacePinRow` beside the other row classes and their guards. |
| `src/khepri/rca/workspace/persistence.py` | **Modify.** Re-export `WorkspacePinRow` — schema.py's docstring says every public name is re-exported from here, and importers use this module. |
| `src/khepri/rca/workspace/deletion_matrix.py` | **Modify.** One entry: `"rca_workspace_pins": ENDING_CASCADE`. |
| `src/khepri/rca/workspace/store.py` | **Modify.** `pin`, `unpin`, `pins_for_scope`, and the cascade inside the existing `_tombstone_version` walk. |
| `migrations/versions/20260906_0029_rca_workspace_pins.py` | **Create.** The table, chained onto `20260906_0028`. |
| `src/khepri/runtime/shell_pins.py` | **Create.** `offers_pins`, `add_pin_routes` — the mutating routes, modelled on `shell_deletion.py`. |
| `src/khepri/runtime/shell_workspace.py` | **Modify.** The Overview view-model gains pinned + recent-activity sections. |
| `src/khepri/runtime/shell_templates/overview.html.j2` | **Modify.** Two new sections. |
| `src/khepri/runtime/shell_copy.py` | **Modify.** Bilingual strings. |
| `src/khepri/runtime/wiring.py` | **Modify.** Wire pins into `ShellServices` so the route exists in the built image. |
| `tests/test_w109_pins.py` | **Create.** Schema extent, store verbs, cascade, isolation. |
| `tests/test_w109_recent_activity.py` | **Create.** Ordering, retains-nothing. |
| `tests/test_w109_no_widening.py` | **Create.** The `RCA-005` Verification guard. |

---

## Task 1: The pin table, its migration, and the three head pins

**Files:**
- Modify: `src/khepri/rca/workspace/schema.py`
- Modify: `src/khepri/rca/workspace/persistence.py`
- Create: `migrations/versions/20260906_0029_rca_workspace_pins.py`
- Modify: `tests/test_rca001_migration.py` (`RCA_REVISIONS`, `RCA_TABLES`)
- Modify: `tests/test_rca001_session_persistence.py:402` (the head pin + its docstring)
- Modify: `STATUS.md` (header revision)
- Test: `tests/test_w109_pins.py`

**Interfaces:**
- Consumes: `Base` from `khepri.rca.persistence`; `_scope_foreign_key(name: str) -> ForeignKeyConstraint` and `_states_check(column, states, name)` from `khepri.rca.workspace.schema`.
- Produces: `WorkspacePinRow` with `__tablename__ = "rca_workspace_pins"` and columns `pin_id: str` (PK), `owner_id: str`, `object_id: str`, `object_kind: str`, `pinned_at: datetime`. Constant `PIN_KINDS: tuple[str, ...] = ("dataset_version", "analysis_run")`. Later tasks import both from `khepri.rca.workspace.persistence`.

- [ ] **Step 1: Write the failing schema-extent test**

Create `tests/test_w109_pins.py`:

```python
"""`W1-09`'s pin table (`RCA-005` `FR-128`, `KHEPRI-DEC-034` §1)."""

from __future__ import annotations

from sqlalchemy import inspect

from khepri.rca.persistence import Base
from khepri.rca.workspace.persistence import PIN_KINDS, WorkspacePinRow


class TestThePinTable:
    def test_the_column_set_is_exactly_the_permitted_fields(self) -> None:
        """`FR-128` closes the field list: "and nothing else -- no count, no access record, no
        ordering weight."

        Equality, not a subset. A `>=` assertion cannot see a `view_count` added later, which is
        exactly the widening `KHEPRI-DEC-034` §2 refuses -- and `RCA_TABLES` drifted three times
        under subset assertions before this convention was adopted.

        Read through `inspect(...)`, not the dataclass fields: a column can be added to the table
        without touching a mapped attribute set, and a field-set equality stays green through it.
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
        absent from it is a table those guards cannot see."""
        assert WorkspacePinRow.__tablename__ == "rca_workspace_pins"
        assert "rca_workspace_pins" in Base.metadata.tables

    def test_one_owner_cannot_pin_the_same_object_twice(self) -> None:
        """Idempotency belongs to the database, not to a read-then-write in the service.

        `store.py:711` records why: a reviewer argued concurrent writers agree on the state they
        want and need no lock, and was wrong. SQLite serializes writes, so a read-then-write test
        passes there while PostgreSQL admits the second row. A `UNIQUE` constraint is checked by
        both engines.
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_pins.py -v`
Expected: FAIL at collection with `ImportError: cannot import name 'PIN_KINDS'` / `'WorkspacePinRow'` from `khepri.rca.workspace.persistence`.

- [ ] **Step 3: Add the row class to `schema.py`**

Add near the other row classes, after `WorkspaceAuditEventRow`:

```python
#: The two object kinds a pin may name (`KHEPRI-DEC-034` §1). A closed set, so a third kind cannot
#: arrive without a migration that widens the CHECK alongside it.
PIN_KINDS: tuple[str, ...] = ("dataset_version", "analysis_run")


class WorkspacePinRow(Base):
    """One owner's mark on one object, and nothing about how often they visit it.

    `FR-128` closes the field list. There is no `opened_count`, no `last_opened_at`, no ordering
    weight -- each would be an access record, which `KHEPRI-DEC-034` §2 refuses by name. A pin is a
    *stated preference*; a counter is a *measurement*, and the decision authorizes only the first.

    No retention state and no tombstone. `KHEPRI-DEC-034` §1's matrix ends this row by deletion
    with no tombstone: `KHEPRI-DEC-033` §3's allowlist governs what survives a deletion, and a pin
    survives nothing.
    """

    __tablename__ = "rca_workspace_pins"
    __table_args__ = (
        _scope_foreign_key("fk_rca_workspace_pin_scope"),
        _states_check("object_kind", PIN_KINDS, "ck_rca_workspace_pin_kind"),
        # Idempotency in the database rather than in the store. A read-then-insert passes under
        # SQLite, which serializes writes, and admits a duplicate under PostgreSQL -- the shape
        # `store.py:711` records from `#370`, where the environment supplied the property the
        # assertion checked.
        UniqueConstraint(
            "owner_id", "object_id", name="uq_rca_workspace_pin_owner_object"
        ),
    )

    pin_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String, nullable=False)
    object_kind: Mapped[str] = mapped_column(String, nullable=False)
    pinned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

Re-export from `persistence.py` alongside the other row classes — add `PIN_KINDS` and `WorkspacePinRow` to its import list and `__all__`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_pins.py -v`
Expected: PASS, 4 tests.

- [ ] **Step 5: Run the existing guards to see the deletion matrix fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w107_cascade_matrix.py tests/test_rca001_migration.py -v`
Expected: FAIL — `test_every_workspace_table_has_exactly_one_stated_ending` reports `rca_workspace_pins` has no ending, and `test_every_rca_table_in_the_models_is_named_here` reports it is missing from `RCA_TABLES`. **This is the designed-in RED test**; Task 2 closes the first, this task closes the second.

- [ ] **Step 6: Write the migration**

Create `migrations/versions/20260906_0029_rca_workspace_pins.py`:

```python
"""`W1-09`'s pin table (`RCA-005` `FR-128`, `KHEPRI-DEC-034` §1).

The values are spelled literally rather than imported from `PIN_KINDS`. A migration is a
historical record, and importing a constant into one would let a later edit rewrite history --
`_retention_check`'s docstring states the rule, and a test asserts the two spellings agree.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260906_0029"
down_revision = "20260906_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rca_workspace_pins",
        sa.Column("pin_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("object_id", sa.String(), nullable=False),
        sa.Column("object_kind", sa.String(), nullable=False),
        sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pin_id"),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["rca_isolation_scopes.owner_id"],
            name="fk_rca_workspace_pin_scope",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "object_kind IN ('dataset_version', 'analysis_run')",
            name="ck_rca_workspace_pin_kind",
        ),
        sa.UniqueConstraint(
            "owner_id", "object_id", name="uq_rca_workspace_pin_owner_object"
        ),
    )
    op.create_index(
        "ix_rca_workspace_pins_owner_id", "rca_workspace_pins", ["owner_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_rca_workspace_pins_owner_id", table_name="rca_workspace_pins")
    op.drop_table("rca_workspace_pins")
```

- [ ] **Step 7: Move all three head pins**

In `tests/test_rca001_migration.py`, append to `RCA_REVISIONS`:

```python
    # `W1-09`'s pin table (`FR-128`). Unlike `0026` and `0028`, which rewrote a CHECK, this
    # creates a table -- so `RCA_TABLES` gains a member too, which
    # `test_every_rca_table_in_the_models_is_named_here` checks by equality rather than leaving
    # assumed. The middle element is the revision file's slug, not the table.
    ("20260906_0029", "rca_workspace_pins", "20260906_0028"),
```

And add `"rca_workspace_pins"` to `RCA_TABLES`.

In `tests/test_rca001_session_persistence.py`, extend the docstring at line ~424 and move the assertion:

```python
        then `20260906_0028`, which admits the retention sweep's own action (`FR-125`). `W1-09`
        then added `20260906_0029`, the pin table (`FR-128`), which is the head this pin now names.
```

```python
        assert "20260906_0029" in result.stdout
```

Update `STATUS.md`'s header revision to `20260906_0029`.

- [ ] **Step 8: Run the migration guards**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_migration.py tests/test_rca001_session_persistence.py -v`
Expected: PASS. Single head, correct parent, `RCA_TABLES` equality holds.

Real DDL needs PostgreSQL at `127.0.0.1:5432` (postgres/postgres) — `alembic heads` executes nothing and SQLite cannot ALTER constraints.

- [ ] **Step 9: Commit**

```bash
git add src/khepri/rca/workspace/schema.py src/khepri/rca/workspace/persistence.py migrations/versions/20260906_0029_rca_workspace_pins.py tests/test_w109_pins.py tests/test_rca001_migration.py tests/test_rca001_session_persistence.py STATUS.md
git commit -F .git/COMMIT_W109_1
```

Message: `feat(w1-09): the pin table, its migration, and the head that moves with it`

---

## Task 2: The ending, and the cascade that performs it

**Files:**
- Modify: `src/khepri/rca/workspace/deletion_matrix.py`
- Modify: `src/khepri/rca/workspace/store.py`
- Test: `tests/test_w109_pins.py` (append)

**Interfaces:**
- Consumes: `WorkspacePinRow`, `PIN_KINDS` (Task 1); `ENDING_CASCADE` from `deletion_matrix`; `_tombstone_version(database, version, now, sections_of)` and `_cascade_tombstone_to_runs` from `store.py`.
- Produces: `WorkspaceStore.pin(object_id: str, object_kind: str, *, owner_id: str, now: datetime) -> None`, `.unpin(object_id: str, *, owner_id: str) -> None`, `.pins_for_scope(owner_id: str) -> tuple[WorkspacePin, ...]`. The read model `WorkspacePin` is a frozen dataclass with `object_id: str`, `object_kind: str`, `pinned_at: datetime`.

- [ ] **Step 1: Write the failing cascade and store tests**

Append to `tests/test_w109_pins.py`:

```python
class TestTheEnding:
    def test_the_pin_table_has_a_stated_ending(self) -> None:
        """`test_every_workspace_table_has_exactly_one_stated_ending` compares `ENDINGS` against
        `Base.metadata`, so this entry is what lets that guard pass -- and its absence is what
        made it fail in Task 1. `deletion_matrix.py` is built as data for exactly this reason: a
        hand-written cascade sequence would have ended nothing here while staying green."""
        from khepri.rca.workspace.deletion_matrix import ENDING_CASCADE, ENDINGS

        assert ENDINGS["rca_workspace_pins"] == ENDING_CASCADE


class TestTheStoreVerbs:
    def test_a_pin_round_trips(self, store, scope) -> None:
        store.pin(VERSION_ID, "dataset_version", owner_id=scope.owner_id, now=NOW)

        pins = store.pins_for_scope(scope.owner_id)

        assert [pin.object_id for pin in pins] == [VERSION_ID]
        assert pins[0].object_kind == "dataset_version"
        assert pins[0].pinned_at == NOW

    def test_pinning_twice_is_a_no_op_rather_than_an_error(self, store, scope) -> None:
        """`KHEPRI-DEC-034` §1: "Immediate and idempotent on demand." A second pin of the same
        object must not raise, and must not move `pinned_at` -- moving it would make the pin an
        access record by the back door, which §2 refuses."""
        store.pin(VERSION_ID, "dataset_version", owner_id=scope.owner_id, now=NOW)
        store.pin(VERSION_ID, "dataset_version", owner_id=scope.owner_id, now=LATER)

        pins = store.pins_for_scope(scope.owner_id)

        assert len(pins) == 1
        assert pins[0].pinned_at == NOW, "a repeat must not move the instant"

    def test_unpinning_something_unpinned_is_a_no_op(self, store, scope) -> None:
        store.unpin(VERSION_ID, owner_id=scope.owner_id)

        assert store.pins_for_scope(scope.owner_id) == ()

    def test_deleting_the_object_removes_its_pin(self, store, scope) -> None:
        """`KHEPRI-DEC-034` §1: the pin ends when "the object ends", cascading from the pinned
        object's deletion.

        Driven through `set_retention_state`, the production verb, rather than by deleting the row
        directly: a fixture that bypasses the verb exempts the transition, and a mutant of the
        bypassed verb would survive.
        """
        store.pin(VERSION_ID, "dataset_version", owner_id=scope.owner_id, now=NOW)

        store.set_retention_state(
            VERSION_ID, RETENTION_TOMBSTONED, now=LATER, owner_id=scope.owner_id
        )

        assert store.pins_for_scope(scope.owner_id) == ()

    def test_a_pin_is_not_visible_to_another_scope(self, store, scope, other_scope) -> None:
        """Two scopes written, one read. With one organization's rows in the table an unfiltered
        query returns exactly what a filtered one does, so a single-scope test cannot see a
        missing `WHERE` -- `W1-02`'s convention."""
        store.pin(VERSION_ID, "dataset_version", owner_id=scope.owner_id, now=NOW)
        store.pin(OTHER_VERSION_ID, "dataset_version", owner_id=other_scope.owner_id, now=NOW)

        pins = store.pins_for_scope(scope.owner_id)

        assert [pin.object_id for pin in pins] == [VERSION_ID]
```

Build the `store`, `scope` and `other_scope` fixtures by reusing `tests/w107_support.py`'s existing builders rather than adding a near-duplicate — CodeScene scores test modules too, and a near-duplicate fixture trips Low Cohesion.

- [ ] **Step 2: Run to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_pins.py -v`
Expected: FAIL — `KeyError: 'rca_workspace_pins'` on the ending, and `AttributeError: 'WorkspaceStore' object has no attribute 'pin'`.

- [ ] **Step 3: State the ending**

In `deletion_matrix.py`, add to `ENDINGS` with the citation the neighbouring entries carry:

```python
    # `KHEPRI-DEC-034` §1: "The object ends, or the pin is removed, or the organization ends" ->
    # "Row deleted, no tombstone". Reached because the object it names ended: a named cascade.
    # No tombstone, because `KHEPRI-DEC-033` §3's allowlist governs what survives a deletion and
    # a stated preference survives nothing.
    "rca_workspace_pins": ENDING_CASCADE,
```

- [ ] **Step 4: Add the store verbs and the cascade**

In `store.py`, add the read model and three verbs, and extend the **existing** walk. Inside `_tombstone_version`, after `_cascade_tombstone_to_runs(...)`:

```python
    _cascade_to_pins(database, version, sections_of)
```

```python
def _cascade_to_pins(database, version: DatasetVersionRow, sections_of: SectionsOf) -> None:
    """Remove every pin naming a version being tombstoned, and every pin naming its runs.

    Inside `_tombstone_version` rather than beside it, so the pin's removal is in the same
    transaction as the deletion that causes it: one transaction ends the version and everything
    `KHEPRI-DEC-034` §1 says ends with it, or neither happens.

    Reached only after `set_retention_state`'s idempotency return, so a repeated deletion removes
    nothing a second time -- the same discipline `_tombstone_version` documents.

    Deleted outright, with no tombstone and no evidence row: a pin is a stated preference rather
    than content, and `KHEPRI-DEC-033` §3's allowlist has nothing to say about it.
    """
    run_ids = database.scalars(runs_of_version(version.version_id, version.owner_id)).all()
    object_ids = {version.version_id, *run_ids}
    database.execute(
        delete(WorkspacePinRow).where(
            WorkspacePinRow.owner_id == version.owner_id,
            WorkspacePinRow.object_id.in_(object_ids),
        )
    )
```

`pin` inserts and swallows the unique-constraint clash rather than reading first:

```python
    def pin(
        self, object_id: str, object_kind: str, *, owner_id: str, now: datetime
    ) -> None:
        """Mark one object for quick return (`FR-128`).

        Idempotent by *constraint*, not by a preceding read. A read-then-insert would pass under
        SQLite, which serializes writes, and admit a duplicate under PostgreSQL -- the environment
        supplying the property the assertion checks, which is the defect `store.py:711` records
        from `#370`. The clash is translated to a no-op here because a repeat is `FR-128`'s
        idempotent retry, and it must not move `pinned_at`: moving it would turn a stated
        preference into a record of when it was last asserted.
        """
        if object_kind not in PIN_KINDS:
            raise ValueError(PIN_KIND_FAILURE)
        with writing(self._factory) as database:
            try:
                with database.begin_nested():
                    database.add(
                        WorkspacePinRow(
                            pin_id=new_identifier(),
                            owner_id=owner_id,
                            object_id=object_id,
                            object_kind=object_kind,
                            pinned_at=now,
                        )
                    )
            except IntegrityError:
                return
```

`unpin` and `pins_for_scope` are a scoped `DELETE` and a scoped `SELECT ... ORDER BY pinned_at DESC`, each filtered on `owner_id`.

- [ ] **Step 5: Run the tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_pins.py tests/test_w107_cascade_matrix.py -v`
Expected: PASS. The matrix guard that failed in Task 1 Step 5 now passes.

- [ ] **Step 6: Mutation-check the cascade**

Comment out the `_cascade_to_pins(...)` call and re-run `test_deleting_the_object_removes_its_pin`.
Expected: FAIL. If it passes, the test is not driving the real walk — fix the test, not the assertion. Restore the line.

Then mutate the `owner_id` filter in `pins_for_scope` (delete the `WorkspacePinRow.owner_id == owner_id` clause) and re-run `test_a_pin_is_not_visible_to_another_scope`.
Expected: FAIL. Restore.

- [ ] **Step 7: Commit**

```bash
git add src/khepri/rca/workspace/deletion_matrix.py src/khepri/rca/workspace/store.py tests/test_w109_pins.py
git commit -F .git/COMMIT_W109_2
```

Message: `feat(w1-09): the pin's ending, and the cascade that performs it`

---

## Task 3: The recent-activity read, which retains nothing

**Files:**
- Modify: `src/khepri/rca/workspace/store.py`
- Test: `tests/test_w109_recent_activity.py`

**Interfaces:**
- Consumes: `DatasetVersionRow`, `AnalysisRunRow`.
- Produces: `WorkspaceStore.recent_activity(owner_id: str, *, limit: int = 5) -> tuple[RecentItem, ...]`. `RecentItem` is a frozen dataclass with `object_id: str`, `object_kind: str`, `occurred_at: datetime`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_w109_recent_activity.py`:

```python
"""`W1-09`'s recent-activity view (`RCA-005` `FR-129`, `KHEPRI-DEC-034` §1).

The point of this module is the second class. `FR-129` says the view "MUST retain nothing: no
event, no access record, no counter", and the executable form of that is a before-and-after row
count over *every* workspace table -- which is what distinguishes a view from an event stream.
"""

from __future__ import annotations


class TestTheOrdering:
    def test_it_reads_the_instants_the_records_already_carry(self, store, scope) -> None:
        """`KHEPRI-DEC-034` §1: "a query over dataset versions and analysis runs the workspace
        already stores ... ordered by instants those records already carry." Nothing is written to
        establish the order."""
        store.add_dataset_version(_version(VERSION_ID, created_at=EARLY), owner_id=scope.owner_id)
        store.add_dataset_version(_version(OTHER_ID, created_at=LATE), owner_id=scope.owner_id)

        recent = store.recent_activity(scope.owner_id)

        assert [item.object_id for item in recent] == [OTHER_ID, VERSION_ID]

    def test_it_is_bounded(self, store, scope) -> None:
        for index in range(8):
            store.add_dataset_version(
                _version(f"v{index}", created_at=EARLY), owner_id=scope.owner_id
            )

        assert len(store.recent_activity(scope.owner_id, limit=5)) == 5

    def test_another_scope_sees_none_of_it(self, store, scope, other_scope) -> None:
        """Two scopes written, one read -- `W1-02`'s convention, for the reason a single-scope
        test cannot see a missing `WHERE`."""
        store.add_dataset_version(_version(VERSION_ID, created_at=EARLY), owner_id=scope.owner_id)

        assert store.recent_activity(other_scope.owner_id) == ()

    def test_a_tombstoned_object_is_not_recent(self, store, scope) -> None:
        """Deleting the underlying record removes it from the view -- `KHEPRI-DEC-034` §1's
        matrix, which gives the view no end trigger of its own precisely because it holds
        nothing."""
        store.add_dataset_version(_version(VERSION_ID, created_at=EARLY), owner_id=scope.owner_id)
        store.set_retention_state(
            VERSION_ID, RETENTION_TOMBSTONED, now=LATE, owner_id=scope.owner_id
        )

        assert store.recent_activity(scope.owner_id) == ()


class TestItRetainsNothing:
    def test_reading_the_view_writes_no_row_to_any_workspace_table(
        self, store, scope, database
    ) -> None:
        """`FR-129`, executable: "It MUST retain nothing: no event, no access record, no counter.
        A view that writes a row to answer 'what was recent' is product telemetry and is excluded
        by this specification, whatever it is named."

        Counted over *every* workspace table rather than the ones a writer would plausibly touch.
        A guard that names its own scope reproduces the drift it was written to catch, so this
        derives the table list from `Base.metadata` -- a table added later is counted without
        anyone remembering to add it here.
        """
        before = _row_counts(database)

        store.recent_activity(scope.owner_id)
        store.recent_activity(scope.owner_id)

        assert _row_counts(database) == before


def _row_counts(database) -> dict[str, int]:
    """One count per workspace table, derived from the metadata rather than hand-listed."""
    from sqlalchemy import func, select

    from khepri.rca.persistence import Base

    tables = {
        name: table
        for name, table in Base.metadata.tables.items()
        if name.startswith("rca_workspace_")
    }
    assert tables, "the metadata yielded no workspace tables, so this guard checks nothing"
    return {
        name: database.scalar(select(func.count()).select_from(table))
        for name, table in tables.items()
    }
```

Note the `assert tables` line: a scan that silently finds nothing reports as a pass. Every scan needs an emptiness assertion.

- [ ] **Step 2: Run to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_recent_activity.py -v`
Expected: FAIL with `AttributeError: 'WorkspaceStore' object has no attribute 'recent_activity'`.

- [ ] **Step 3: Implement the read**

In `store.py`:

```python
    def recent_activity(self, owner_id: str, *, limit: int = 5) -> tuple[RecentItem, ...]:
        """What this owner last worked on (`FR-129`).

        **This writes nothing, and that is the requirement rather than an optimization.** The view
        is a query over records the scope already holds, ordered by instants they already carry.
        A version of this that recorded each read -- to rank, to count, to show "most used" --
        would be product telemetry, which `KHEPRI-DEC-015` §3 does not authorize and
        `KHEPRI-DEC-034` §2 declines to seek.

        It reads the workspace records, never `rca_workspace_audit_events`. Rendering the audit
        trail as a customer-facing feed is the conversion `RCA-005` forbids in advance: the audit
        carve-out "does not reach" product use, and "an audit event that begins to carry a product
        metric has become telemetry and is excluded."

        Tombstoned rows are excluded, so deleting the underlying record removes it from the view
        with no end trigger of the view's own.
        """
        with reading(self._factory) as database:
            rows = database.execute(recent_for_scope(owner_id, limit)).all()
        return tuple(
            RecentItem(object_id=row.object_id, object_kind=row.kind, occurred_at=row.at)
            for row in rows
        )
```

`recent_for_scope` is a `UNION ALL` over the two tables — each selecting its identifier, a literal kind, and its instant — filtered to `retention_state == RETENTION_ACTIVE` and the scope, ordered descending, limited.

- [ ] **Step 4: Run the tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_recent_activity.py -v`
Expected: PASS, 5 tests.

- [ ] **Step 5: Mutation-check the isolation and the tombstone filter**

Delete the `owner_id` filter from `recent_for_scope`; re-run `test_another_scope_sees_none_of_it`. Expected: FAIL.
Delete the `retention_state` filter; re-run `test_a_tombstoned_object_is_not_recent`. Expected: FAIL.
Restore both. A guard that survives its own mutant is not tested.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rca/workspace/store.py tests/test_w109_recent_activity.py
git commit -F .git/COMMIT_W109_3
```

Message: `feat(w1-09): the recent-activity read, which writes nothing to answer`

---

## Task 4: The widening guard

**Files:**
- Test: `tests/test_w109_no_widening.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3. Produces no source change — this task is evidence.

`RCA-005`'s Verification section names this test literally: *"A test that `FR-128`/`FR-129` write **no** access record, counter or telemetry event, and that a pin emits no audit event — the guard against `KHEPRI-DEC-034` being widened by implementation."*

- [ ] **Step 1: Write it**

Create `tests/test_w109_no_widening.py`:

```python
"""The guard `RCA-005` Verification names: `KHEPRI-DEC-034` must not be widened by implementation.

This module exists because the decision it guards is narrow *by choice*. `KHEPRI-DEC-034` §2 keeps
`KHEPRI-DEC-015` §3 unamended, leaves `W1-11` and `R8-08` excluded, and refuses counting, ranking
and frequency. Each refusal is one line of prose and one plausible feature away from being lost, so
each gets an assertion here rather than a reviewer's attention.
"""

from __future__ import annotations


class TestNoAuditEventIsEmitted:
    def test_pinning_emits_no_audit_event(self, store, scope, database) -> None:
        """`FR-128`: a pin "is not a governed workspace action: it emits **no** `FR-125` audit
        event and adds no member to `AUDIT_ACTIONS`."

        A pin is not a governed action because it changes nothing about the content -- it records
        what one person wants to find again. Emitting an audit event for it would put a
        behavioural trace into the record `KHEPRI-DEC-015` §7 reserves for security and audit.
        """
        before = _audit_count(database)

        store.pin(VERSION_ID, "dataset_version", owner_id=scope.owner_id, now=NOW)
        store.unpin(VERSION_ID, owner_id=scope.owner_id)

        assert _audit_count(database) == before

    def test_the_audit_vocabulary_gained_no_member(self) -> None:
        """A vocabulary is pinned in three places -- the tuple, the closed-set test in
        `test_w104_audit_events.py`, and the migration's CHECK literal. This asserts the first,
        and the CHECK asserts the third; adding a pin action would have to move all three."""
        from khepri.rca.workspace.audit import AUDIT_ACTIONS

        assert "pin_added" not in AUDIT_ACTIONS
        assert "pin_removed" not in AUDIT_ACTIONS
        assert len(AUDIT_ACTIONS) == 8, AUDIT_ACTIONS


class TestNoCounterExists:
    def test_the_pin_row_carries_no_count_or_access_field(self) -> None:
        """`KHEPRI-DEC-034` §2 refuses "counting, ranking, or frequency" by name. The field list
        is asserted for *equality* in `test_w109_pins.py`; this states the intent in the
        vocabulary the decision uses, so a reader grepping for "count" finds the refusal."""
        from sqlalchemy import inspect

        from khepri.rca.workspace.persistence import WorkspacePinRow

        columns = {column.name for column in inspect(WorkspacePinRow).columns}
        forbidden = {"count", "opened_count", "access_count", "last_opened_at", "weight", "rank"}

        assert columns & forbidden == set()

    def test_no_workspace_table_gained_a_counter(self) -> None:
        """Scoped across every workspace table rather than the pin table alone: a counter added to
        satisfy "most used" would more likely land on the version or run row than on the pin.

        Derived from `Base.metadata`, with an emptiness assertion, because a scan that hand-lists
        its own scope reproduces the drift it was written to catch.
        """
        from khepri.rca.persistence import Base

        tables = {
            name: table
            for name, table in Base.metadata.tables.items()
            if name.startswith("rca_workspace_")
        }
        assert tables, "the metadata yielded no workspace tables, so this guard checks nothing"

        for name, table in tables.items():
            for column in table.columns:
                assert "count" not in column.name, f"{name}.{column.name}"
                assert "frequency" not in column.name, f"{name}.{column.name}"


class TestTheExclusionsStand:
    def test_dec_015_section_3_is_unamended(self) -> None:
        """`KHEPRI-DEC-034` §2: "`KHEPRI-DEC-015` §3 is **not amended** by this decision. Product
        analytics remains an unauthorized purpose, `W1-11` remains excluded, and `R8-08` remains
        excluded. Nothing here may be read as precedent for either."

        Asserted against the governance document rather than restated, because a test comparing a
        restatement against itself passes every mutant.
        """
        from pathlib import Path

        text = Path("governance/decisions/KHEPRI-DEC-015-*.md").read_text(encoding="utf-8")

        assert "product analytics" in text.lower()
```

Resolve the `KHEPRI-DEC-015` filename with `glob` rather than the literal pattern above, and assert exactly one match — a glob that silently matches nothing would make the assertion vacuous.

- [ ] **Step 2: Run it**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_no_widening.py -v`
Expected: PASS. These guard code that already exists, so they pass immediately — that is correct for a guard, and Step 3 is what proves they are not tautologies.

- [ ] **Step 3: Mutation-check each guard**

Mutation testing proves an existing guard is tested; it cannot find a missing one — so each guard here gets its own mutant, and the mutants must be applied one at a time (a redundant pair passes with either alone).

1. Add `pin_added` to `AUDIT_ACTIONS` → `test_the_audit_vocabulary_gained_no_member` FAILS.
2. Add an `opened_count` column to `WorkspacePinRow` → both `test_the_pin_row_carries_no_count_or_access_field` **and** `test_the_column_set_is_exactly_the_permitted_fields` FAIL.
3. Add an `access_count` column to `DatasetVersionRow` — **outside** the pin table, which is the point — → `test_no_workspace_table_gained_a_counter` FAILS.
4. Make `store.pin` write an audit event → `test_pinning_emits_no_audit_event` FAILS.

Verify each mutant actually introduces the defect before believing a test is weak; a malformed mutant proves nothing. Restore after each.

- [ ] **Step 4: Commit**

```bash
git add tests/test_w109_no_widening.py
git commit -F .git/COMMIT_W109_4
```

Message: `test(w1-09): the guard against KHEPRI-DEC-034 being widened by implementation`

---

## Task 5: The routes, wired into the built image

**Files:**
- Create: `src/khepri/runtime/shell_pins.py`
- Modify: `src/khepri/runtime/shell_api.py`
- Modify: `src/khepri/runtime/wiring.py`
- Test: `tests/test_w109_routes.py`, `tests/test_runtime_wiring.py`

**Interfaces:**
- Consumes: `WorkspaceStore.pin/unpin` (Task 2); `ShellRendering` from `khepri.runtime.shell_invitations`; `CommercialSessionCookie` from `khepri.rca.session_cookie`.
- Produces: `offers_pins(services: Any) -> bool`, `add_pin_routes(app: FastAPI, *, services: Any, rendering: ShellRendering, clock: Callable[[], datetime]) -> None`. Routes: `POST {prefix}/{language}/{organization}/pins/{object_kind}/{object_id}` and `.../unpin`.

- [ ] **Step 1: Write the failing route tests, including the deployed route table**

Create `tests/test_w109_routes.py`. The assertion that matters most:

```python
    def test_the_built_image_declares_the_pin_routes(self) -> None:
        """`W1-07a` shipped a route absent from the image while seven tests passed over a
        hand-built `ShellServices`. Assert the route table of the app `wiring.py` actually builds,
        not one assembled by the test.
        """
        app = build_app_from_real_wiring()

        paths = {route.path for route in app.routes}

        assert any(path.endswith("/pins/{object_kind}/{object_id}") for path in paths), paths
```

Plus: pinning through the real route round-trips; a non-owner is refused with the uniform denial byte-for-byte; a cross-organization pin attempt is refused; the route is absent (not merely refusing) when `offers_pins` is false.

- [ ] **Step 2: Run to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_routes.py -v`
Expected: FAIL — `ModuleNotFoundError: khepri.runtime.shell_pins`.

- [ ] **Step 3: Write `shell_pins.py`**

Mirror `shell_deletion.py` exactly: `offers_pins` returns whether the deployment wired pins (a shell without it declares no route, so the address is unknown rather than refused differently, per `FR-046`); `_owner_or_none` is a gate of its own rather than borrowing `shell_invitations.owner_or_none`, for the reason `shell_deletion.py` records — that one returns `None` when invitations are absent, which would refuse every pin for a reason unrelated to pinning.

Each route body resolves the owner, refuses uniformly on `None`, calls one store verb, and redirects. Keep each body to the single call: reading a caller-owned attribute inside a guarded body runs caller code while the capability is live.

- [ ] **Step 4: Wire it in `wiring.py` and dispatch in `shell_api.py`**

Add `pins` to `ShellServices`, built from the same store instance the read surfaces use — reused rather than rebuilt, as `deletion` is, so there is not a second implementation to keep correct.

- [ ] **Step 5: Run the tests**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_w109_routes.py tests/test_runtime_wiring.py -v`
Expected: PASS.

- [ ] **Step 6: Mutation-check the owner gate**

Replace `require_owner` with a call that returns a context for any session, and re-run the non-owner test. Expected: FAIL. If it passes, the test is asserting the exception rather than the effect — put the real verb on the code path.

- [ ] **Step 7: Commit**

```bash
git add src/khepri/runtime/shell_pins.py src/khepri/runtime/shell_api.py src/khepri/runtime/wiring.py tests/test_w109_routes.py tests/test_runtime_wiring.py
git commit -F .git/COMMIT_W109_5
```

Message: `feat(w1-09): the pin routes, with a caller in the built wheel`

---

## Task 6: The Overview sections and their copy

**Files:**
- Modify: `src/khepri/runtime/shell_workspace.py`, `shell_templates/overview.html.j2`, `shell_copy.py`, `shell_assets/workspace.css`
- Test: `tests/test_w109_surface.py`

**Interfaces:**
- Consumes: `pins_for_scope`, `recent_activity` (Tasks 2–3).
- Produces: the Overview view-model gains `pinned: tuple[PinnedItem, ...]` and `recent: tuple[RecentItem, ...]`.

- [ ] **Step 1: Write the failing surface tests**

Both sections render, in both languages, with RTL parity; the pin control appears on Data and Analyses rows; an empty state renders when there is nothing pinned; **no section states that content expires automatically** (`KHEPRI-DEC-033` §5); no inline script or style; no figure is computed in the template.

```python
    def test_no_workspace_template_states_automatic_expiry(self) -> None:
        """`KHEPRI-DEC-033` §5's caution. `W1-07b` shipped the sweep with a caller, so horizons are
        enforced -- but this slice adds no expiry claim, and the guard stays because the templates
        it scans are the ones a later slice would add one to."""
```

- [ ] **Step 2: Run to verify it fails.** Expected: the sections are absent from the rendered HTML.

- [ ] **Step 3: Add the view-model fields, the template sections, the bilingual copy, and the CSS.**

Both `en` and `ar` strings land in `shell_copy.py` in the same commit — a governed caveat can have prose in both languages and still reach no code path, so the surface test above is what proves these are attached rather than merely defined.

- [ ] **Step 4: Run the tests.** Expected: PASS.

- [ ] **Step 5: Commit**

Message: `feat(w1-09): the Pinned and Recent activity sections on Overview`

---

## Task 7: The gate, and the roadmap rows this slice closes

**Files:**
- Modify: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` (§16 `W1` row, §17 item 17)
- Modify: `docs/superpowers/plans/2026-09-03-g3-04-workspace-implementation-plan.md` (add the `W1-09` allocation it never carried)

- [ ] **Step 1: Run the whole suite**

Run: `./.venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-w109`
Expected: PASS, with the count at or above `main`'s 3,631 + the new tests.

Run the whole suite, not the targeted one — changing a field's meaning breaks suites never opened. Isolate `--basetemp`: two runs in one tree give phantom `WinError 32` teardown errors.

- [ ] **Step 2: Run the gates**

```bash
./.venv/Scripts/python.exe -m khepri.governance.cli validate
./.venv/Scripts/python.exe -m ruff check .
```

Reproduce E501 with `ruff check .`, never `awk`/`wc` — Ruff counts characters, not bytes, and over-reports on lines containing `§`.

- [ ] **Step 3: CodeScene pre-flight**

`git fetch origin` first — a stale `origin/main` makes `analyze_change_set` return empty results and a meaningless "passed" — then run it against `origin/main`. Read the finding rather than guessing: `gh api .../check-runs` names the file, rule, score and method.

- [ ] **Step 4: Correct the roadmap rows**

§16's `W1` row currently reads `READY_FOR_PLAN` with "next actionable task: `W1-01`" and "nine slices", while ten IDs merged. Rewrite it to `MERGED` with the `main` SHAs, per §15's rule that `MERGED` requires a `main` SHA — and only after this PR merges does that row become true, so the commit states the SHA it will carry and the PR body records it.

§17 item 17 gains `W1-09` in the build order and records that the chain is closed.

- [ ] **Step 5: Commit and open the PR**

Message: `docs(w1-09): the roadmap rows this slice closes`

PR body states: the authority (`KHEPRI-DEC-034` active at `1d8c5de`), what was built, the mutation evidence per guard, the full-suite count, and explicitly that `KHEPRI-DEC-015` §3 is unamended and `W1-11`/`R8-08` stay excluded.

**Do not merge.** The owner merges; a merge is the approval, and no delegation exists in this session.

---

## Self-Review

**Spec coverage.** §3.1 → Task 1. §3.2 → Task 1 Steps 6–8. §3.3 → Task 2. §3.4 → Task 2. §3.5 → Task 5. §3.6 → Task 6. §4's refusals → Task 4. §5.1 → Task 4. §5.2 → Task 1 Step 1. §5.3 → Tasks 2, 3. §5.4 → Task 3. §5.5 → Task 2. §5.6 → Tasks 2, 3, 6. §5.7 → Task 7. §6 → Task 7 Step 4.

**Type consistency.** `WorkspacePinRow` and `PIN_KINDS` are defined in Task 1 and imported from `khepri.rca.workspace.persistence` thereafter. `pin`/`unpin`/`pins_for_scope` are defined in Task 2 and consumed in Tasks 5–6. `recent_activity` is defined in Task 3 and consumed in Task 6. `offers_pins`/`add_pin_routes` are defined in Task 5.

**One gap accepted deliberately.** `FR-127`'s concurrent case is `#388`'s open issue — it needs a PostgreSQL-backed `journey()` to be provable, and this plan does not close it. The pin's `UNIQUE` constraint is the design's answer to concurrency; proving it under real concurrency waits on `#388`.
