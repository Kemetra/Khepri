"""The workspace revocation ledger (`W1-07a`, `RCA-005` `FR-126`, `KHEPRI-DEC-015` §8).

`FR-126`: a restore from backup MUST NOT make a deleted object readable. Deletion is immediate and
independent of any backup, but a backup taken before it still holds the row -- so the guarantee
cannot be a property of the delete alone. This table is what a read consults afterwards.

**Four columns, and §8 item 6 is why.** The ledger holds opaque identifiers, revocation timestamps
and status only. Enforcing the guarantee means retaining what was revoked, which could quietly
become a second content store; the bound is the design. There is no `status` column because an
entry's presence is the status, and a column admitting two values would be a second state machine
over a table whose only question is membership.

**No foreign key to the object it names.** Every sibling workspace table binds `owner_id` to the
isolation scope with `RESTRICT`; this one binds nothing, because the entry must outlive the record
it revokes -- which is the entire point -- and a `RESTRICT` key would enforce the opposite
ordering. `rca_workspace_audit_events` omits its scope key for the same shape of reason.

**`down_revision` is `20260906_0026`**, `W1-07a`'s deletion vocabulary, the head this slice
inherits.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260906_0027"
down_revision: str | None = "20260906_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: `AUDIT_OBJECTS`, spelled literally as a migration must: a migration is a historical record, and
#: importing the constant would let a later edit rewrite history.
_OBJECTS = "('version', 'run', 'profile')"


def upgrade() -> None:
    op.create_table(
        "rca_workspace_revocations",
        sa.Column("object_kind", sa.String(), nullable=False),
        sa.Column("object_id", sa.String(), nullable=False),
        sa.Column("owner_id", sa.String(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            f"object_kind IN {_OBJECTS}", name="ck_rca_workspace_revocation_object"
        ),
        sa.PrimaryKeyConstraint(
            "object_kind", "object_id", "owner_id", name="pk_rca_workspace_revocations"
        ),
    )
    op.create_index(
        "ix_rca_workspace_revocations_owner_id", "rca_workspace_revocations", ["owner_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_rca_workspace_revocations_owner_id", table_name="rca_workspace_revocations")
    op.drop_table("rca_workspace_revocations")
