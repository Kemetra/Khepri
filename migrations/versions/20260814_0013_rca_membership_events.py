"""Add `rca_membership_events` and backfill attribution from `rca_memberships` (`#150`).

`FR-014` requires every membership or role change to record which account made it, which
membership it affected, **what the prior and resulting roles were**, and when. A current-state
row cannot express a transition, so attribution moves to an append-only event table.

`KHEPRI-DEC-015` §82 fixes the record's content — opaque actor identifier, opaque membership
identity, prior role, next role, timestamp — and its horizon at twelve months, against the
account record's twenty-four. That ordering is deliberate: the account tombstone outlives the
audit event so an event never refers to a subject that no longer exists.

**This migration does not drop `changed_by` and `changed_at`.** It backfills them and leaves them
in place. Dropping them belongs to a separate change (`R2-03`) for a reason worth stating: a
backfill and a column drop in one migration cannot be verified independently, because if the
backfill is wrong the source data is already gone. Landing them apart means the drop runs against
a backfill that has been reviewed on `main`.

**No foreign keys.** A `RESTRICT` foreign key onto `rca_accounts` would make the account purge
fail while any event referenced it, inverting the horizon relationship above. A foreign key onto
`rca_memberships` would prevent revocation from removing the membership its own event describes,
which is exactly what `KHEPRI-DEC-015` means by retaining the membership "only as the subject of
the `FR-014` audit event". The identifiers are opaque strings, which is what content-free means
here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0013"
down_revision: str | None = "20260813_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rca_membership_events",
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        # FR-014: which authenticated account made the change.
        sa.Column("actor_account_id", sa.String(), nullable=False),
        # Nullable in both directions, and the pair carries the event kind: a creation has no
        # prior role, a revocation has no next role. A separate event_type column could
        # contradict them, so there is none.
        sa.Column("prior_role", sa.String(), nullable=True),
        sa.Column("next_role", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )
    # The twelve-month sweeper selects on this column, so it is indexed for the same reason
    # rra_beta_sessions.content_expires_at is.
    op.create_index(
        "ix_rca_membership_events_occurred_at",
        "rca_membership_events",
        ["occurred_at"],
    )
    _backfill_creation_events()


def _backfill_creation_events() -> None:
    """Synthesize one creation event per existing membership, from its attribution columns.

    The mapping is exact: `changed_by` becomes the actor, `changed_at` becomes the timestamp,
    the current `role` becomes the resulting role, and there is no prior role because none was
    recorded and none existed.

    **A backfilled event is a reconstruction, not an observed event.** It asserts that this
    membership existed at this role, attributed to this account, at this time — all true, and all
    that the source columns support — but it did not come from an operation that emitted it. A
    later reader comparing event counts against operation counts should expect this discrepancy
    for every membership created before this migration.

    Identifiers are derived from the membership's own identity rather than randomly generated, so
    re-running the backfill cannot produce a second event for the same membership. That matters
    because `op.get_bind()` executes outside this module's control on a downgrade-and-replay.
    """
    bind = op.get_bind()
    memberships = bind.execute(
        sa.text(
            "SELECT organization_id, account_id, role, changed_by, changed_at "
            "FROM rca_memberships"
        )
    ).fetchall()
    if not memberships:
        return
    bind.execute(
        sa.text(
            "INSERT INTO rca_membership_events "
            "(event_id, organization_id, account_id, actor_account_id, "
            " prior_role, next_role, occurred_at) "
            "VALUES (:event_id, :organization_id, :account_id, :actor_account_id, "
            " NULL, :next_role, :occurred_at)"
        ),
        [
            {
                "event_id": f"mev_backfill_{row.organization_id}_{row.account_id}",
                "organization_id": row.organization_id,
                "account_id": row.account_id,
                "actor_account_id": row.changed_by,
                "next_role": row.role,
                "occurred_at": row.changed_at,
            }
            for row in memberships
        ],
    )


def downgrade() -> None:
    """Drop the table and its index.

    This discards the backfilled events, which is correct: their source columns are still on
    `rca_memberships` until `R2-03` removes them, so nothing is lost that cannot be reconstructed
    by re-running the upgrade. Once `R2-03` has merged, downgrading past this point *does* lose
    attribution, and that is why the two are separate revisions rather than one.
    """
    op.drop_index("ix_rca_membership_events_occurred_at", table_name="rca_membership_events")
    op.drop_table("rca_membership_events")
