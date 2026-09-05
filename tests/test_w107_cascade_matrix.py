"""`W1-07a` -- the ending each workspace class gets (`KHEPRI-DEC-033` §2).

The matrix in §2 is authoritative and assigns every class an ending. This table restates it as
data, and the extent assertion below is why it is data rather than a sequence: a hand-written
cascade is a scope that disarms itself, because a class added later that the sequence does not
mention ends nothing while every existing test still passes.

The table does **not** re-implement the walk. `store.set_retention_state` already cascades a
version's tombstone to its runs, and `DeletionService` already ends the `RRA` content. What this
asserts is that every workspace table has a *stated* ending, so a new one cannot appear without a
decision about what a customer's deletion does to it.
"""

from __future__ import annotations

import pytest

from khepri.rca.workspace.deletion_matrix import (
    ENDING_CASCADE,
    ENDING_PURGE,
    ENDING_SURVIVES,
    ENDING_TOMBSTONE,
    ENDINGS,
)
from khepri.rca.workspace.schema import Base


def test_every_workspace_table_has_exactly_one_stated_ending() -> None:
    """The extent assertion. A table added without a rule fails here rather than surviving a
    customer's deletion silently."""
    workspace_tables = {name for name in Base.metadata.tables if name.startswith("rca_workspace_")}

    assert set(ENDINGS) == workspace_tables, (
        f"unruled: {sorted(workspace_tables - set(ENDINGS))}; "
        f"unknown: {sorted(set(ENDINGS) - workspace_tables)}"
    )


@pytest.mark.parametrize("table,ending", sorted(ENDINGS.items()))
def test_each_ending_is_one_of_the_four_the_decision_names(table: str, ending: str) -> None:
    """`KHEPRI-DEC-033` §2's post-trigger states, and nothing invented beside them."""
    assert ending in {ENDING_TOMBSTONE, ENDING_PURGE, ENDING_CASCADE, ENDING_SURVIVES}


def test_the_version_is_tombstoned_and_its_runs_cascade() -> None:
    """The two rows the customer's deletion acts on directly, as §2 assigns them."""
    assert ENDINGS["rca_workspace_dataset_versions"] == ENDING_TOMBSTONE
    assert ENDINGS["rca_workspace_analysis_runs"] == ENDING_CASCADE


def test_what_a_deletion_produces_is_not_itself_ended_by_one() -> None:
    """A tombstone is what survives a deletion, and an audit event and a revocation entry are what
    record it -- ending them with the object would erase the evidence that it ended. Each has its
    own twelve-month horizon under `KHEPRI-DEC-015` §2a, which `W1-07b`'s sweep enforces."""
    assert ENDINGS["rca_workspace_tombstones"] == ENDING_SURVIVES
    assert ENDINGS["rca_workspace_audit_events"] == ENDING_SURVIVES
    assert ENDINGS["rca_workspace_revocations"] == ENDING_SURVIVES
