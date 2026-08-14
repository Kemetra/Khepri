"""Drop `changed_by` and `changed_at` from `rca_memberships` (`#150`).

`20260814_0013` moved membership attribution to `rca_membership_events` and backfilled one
creation event per existing row. This removes the source columns, completing the move.

**Why the two are separate revisions.** A backfill and a column drop in one migration cannot be
verified independently: if the backfill is wrong the source data is already gone by the time
anyone can compare. Landing them apart means this drop runs against a backfill that has been
reviewed on `main`, with both representations coexisting for a full cycle.

**Why the columns had to go rather than stay as a convenience.** `KHEPRI-DEC-015` §2a gives
membership audit a twelve-month horizon. `rca_memberships` is a live state row with no expiry.
Attribution left on it would outlive its own horizon indefinitely -- not because anyone decided
it should, but because it happened to ride on a row that never expires. `FR-014`'s record now
has exactly one home, and that home is swept.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0014"
down_revision: str | None = "20260814_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("rca_memberships") as batch:
        batch.drop_column("changed_by")
        batch.drop_column("changed_at")


def downgrade() -> None:
    """Re-add the columns and reconstruct their values from the creation events.

    `20260812_0010` declares both `NOT NULL`, so re-adding them empty would fail on any table
    that has rows -- and would fail only against real data, having passed every test run
    against an empty one. The columns are therefore added nullable, populated, and only then
    tightened.

    The reconstruction inverts the backfill: `actor_account_id` becomes `changed_by` and
    `occurred_at` becomes `changed_at`, read from each membership's creation event
    (`prior_role IS NULL`). Where a membership has several -- it should not, but the table is
    append-only and carries no uniqueness constraint saying so -- the most recent is used, so
    the outcome is deterministic rather than dependent on physical row order.

    **This is lossy by design, in one case.** A membership whose creation event has passed its
    twelve-month horizon and been swept has no source left to reconstruct from, and gets the
    placeholder below. That is not a defect in the downgrade: it is the direct consequence of
    giving audit data a shorter life than the row it describes, which is the point of the move
    rather than an accident of it. A downgrade cannot resurrect what a retention policy
    deliberately destroyed, and it should not pretend otherwise by inventing a plausible actor.

    **This reconstruction is exercised on SQLite only, and the PostgreSQL path is unproven.**
    `test_full_chain_upgrades_to_head_on_postgres` upgrades and never downgrades, so CI proves
    the *drop* against the dialect that runs in production and proves the *restore* against the
    one that does not. The residual risk is narrow and worth naming rather than leaving for a
    reader to rediscover: `COALESCE(<subquery>, :epoch)` requires PostgreSQL to infer the bound
    parameter's type from the subquery's `timestamptz`, which it normally does and psycopg
    normally sends typed. Low, not zero. A downgrade is an emergency path and this is the same
    exposure `20260814_0013` carries, so it is recorded here rather than treated as blocking.
    """
    with op.batch_alter_table("rca_memberships") as batch:
        batch.add_column(sa.Column("changed_by", sa.String(), nullable=True))
        batch.add_column(sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True))

    _reconstruct_attribution()

    with op.batch_alter_table("rca_memberships") as batch:
        batch.alter_column("changed_by", existing_type=sa.String(), nullable=False)
        batch.alter_column(
            "changed_at", existing_type=sa.DateTime(timezone=True), nullable=False
        )


# Stands in for attribution whose creation event has been swept. It is deliberately not a
# plausible account identifier: a reader must be able to tell reconstructed-unknown from
# genuinely-recorded, and a downgrade that invented a credible actor would be forging the audit
# record it is supposed to be restoring.
_UNKNOWN_ACTOR = "unknown_swept_event"

# The placeholder timestamp for a membership whose creation event has been swept. Bound as a
# `datetime` rather than a string: `changed_at` is `TIMESTAMPTZ` on PostgreSQL, which will not
# implicitly cast a text literal in this position the way SQLite does, so binding the string
# would pass every SQLite test and fail on the dialect that actually runs in production.
_UNKNOWN_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)


def _reconstruct_attribution() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE rca_memberships SET "
            " changed_by = COALESCE(("
            "  SELECT e.actor_account_id FROM rca_membership_events e"
            "  WHERE e.organization_id = rca_memberships.organization_id"
            "    AND e.account_id = rca_memberships.account_id"
            "    AND e.prior_role IS NULL"
            "  ORDER BY e.occurred_at DESC LIMIT 1"
            " ), :unknown_actor),"
            " changed_at = COALESCE(("
            "  SELECT e.occurred_at FROM rca_membership_events e"
            "  WHERE e.organization_id = rca_memberships.organization_id"
            "    AND e.account_id = rca_memberships.account_id"
            "    AND e.prior_role IS NULL"
            "  ORDER BY e.occurred_at DESC LIMIT 1"
            " ), :epoch)"
        ),
        {"unknown_actor": _UNKNOWN_ACTOR, "epoch": _UNKNOWN_TIMESTAMP},
    )
