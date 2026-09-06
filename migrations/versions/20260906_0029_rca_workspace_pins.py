"""The workspace pin table (`W1-09`, `RCA-005` `FR-128`, `KHEPRI-DEC-034` §1).

`FR-128` closes the field list -- "and **nothing else** -- no count, no access record, no ordering
weight" -- so the five columns below are the whole table, and their absence of a sixth is the
requirement rather than an omission. `KHEPRI-DEC-034` §2 refuses counting, ranking and frequency by
name, and leaves `KHEPRI-DEC-015` §3 unamended.

**No retention state and no tombstone**, unlike the content tables. `KHEPRI-DEC-034` §1's matrix
ends this row by deletion with no tombstone: `KHEPRI-DEC-033` §3's allowlist governs what survives
a customer's deletion, and a stated preference survives nothing.

**The kind values are spelled literally rather than imported from `PIN_KINDS`.** A migration is a
historical record, and importing a constant into one would let a later edit rewrite history --
`_states_check`'s docstring states the rule, and `test_migration_columns_match_the_declared_models`
asserts the two spellings agree.

**`down_revision` is `20260906_0028`**, `W1-07b`'s sweep action, the head this slice inherits.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0029"
down_revision: str | None = "20260906_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        # Idempotency in the database rather than in the store. A read-then-insert passes under
        # SQLite, which serializes writes, and admits a duplicate under PostgreSQL -- the shape
        # `store.py`'s `set_retention_state` records from `#370`, where the environment supplied
        # the property the assertion checked.
        sa.UniqueConstraint("owner_id", "object_id", name="uq_rca_workspace_pin_owner_object"),
    )
    op.create_index("ix_rca_workspace_pins_owner_id", "rca_workspace_pins", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_rca_workspace_pins_owner_id", table_name="rca_workspace_pins")
    op.drop_table("rca_workspace_pins")
