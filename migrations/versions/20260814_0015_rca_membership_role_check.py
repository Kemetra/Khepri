"""Constrain `rca_memberships.role` to the two roles `FR-015` allows (`#150`).

`FR-015` fixes the role model at exactly `owner` and `member`, and says any further role
"requires a separate specification". The column was an unconstrained `String`, so a third role
was writable -- `STATUS.md` records this as FR-015's gap.

**The domain refusing a third role is not sufficient.** A store caller reaching the row directly
bypasses `Membership`, and that seam is exactly what `#151` was opened to close. The constraint
puts the rule where it cannot be gone around.

**Declared in the model as well as here.** Store tests build their schema from
`Base.metadata.create_all`, which reads constraints from `MembershipRow` and not from this file,
so a CHECK that lived only in the migration would leave the entire store suite able to write
`role="admin"` while production refused it.

No existing row can violate it: `create_organization` is the only writer of this column and it
writes `OWNER_ROLE` exclusively, so every row on `main` is `'owner'`.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260814_0015"
down_revision: str | None = "20260814_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled out rather than imported from `khepri.rca.organizations`. A migration is a historical
# record of the schema at a point in time: if a later slice adds a third role, this revision must
# keep meaning what it meant when it ran, and an import would silently rewrite history. The model
# builds its matching constraint from `ROLES`, and the parity test holds the two together.
_ROLE_CHECK = "role IN ('owner', 'member')"
_CONSTRAINT = "ck_rca_membership_role"


def upgrade() -> None:
    # batch_alter_table because SQLite cannot add a CHECK constraint in place: Alembic rebuilds
    # the table from reflection. `20260813_0011` established the same pattern for nullability.
    with op.batch_alter_table("rca_memberships") as batch:
        batch.create_check_constraint(_CONSTRAINT, _ROLE_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("rca_memberships") as batch:
        batch.drop_constraint(_CONSTRAINT, type_="check")
