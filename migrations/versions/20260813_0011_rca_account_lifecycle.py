"""Add the account lifecycle columns: disablement timestamp and a nullable login identity.

`KHEPRI-DEC-015` §2b retains a disabled account's record and login identity for twenty-four
months from disablement, then purges the identity fields leaving an opaque tombstone. Two schema
changes are required for that state to be representable at all:

- `disabled_at` — the horizon is computed from it, and the enabled/disabled state is derived from
  it rather than duplicated into a boolean that could disagree.
- `email` becomes nullable — otherwise the post-horizon purge state cannot be written, and A-1's
  uniqueness reservation would be held forever on an address §2b explicitly releases.

The verifier columns are already nullable, so destruction needs no change here. That was
deliberate in `20260812_0010`.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0011"
down_revision: str | None = "20260812_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table because SQLite cannot ALTER a column's nullability in place: Alembic
    # rebuilds the table instead. Postgres takes the direct path through the same API.
    with op.batch_alter_table("rca_accounts") as batch:
        batch.add_column(sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
        batch.alter_column("email", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Reverse the columns.

    Restoring NOT NULL on `email` fails if any tombstoned row exists, and that is correct: those
    rows have no email to restore, so a downgrade that succeeded would have to invent one. The
    failure is the honest outcome.
    """
    with op.batch_alter_table("rca_accounts") as batch:
        batch.alter_column("email", existing_type=sa.String(), nullable=False)
        batch.drop_column("disabled_at")
