"""Add `rca_sessions` and `rca_external_identities` (`R3-03`, `#150` R3).

Two tables in one revision, as `R3-09` §3.3 records. Shipping them apart would cost a second
migration and re-open the single-head coordination window `R2` and `R3` have already serialized
around twice; shipping them together costs one unused table until a provider is admitted under
`KHEPRI-DEC-018` §5.

**Both carry a `RESTRICT` foreign key onto `rca_accounts`, unlike `rca_membership_events`.** That
table deliberately carries none, because a RESTRICT constraint would make the account purge fail
while an event still referenced it -- inverting the horizon relationship where the twenty-four month
tombstone must outlast the twelve-month audit event. `R3-09` §3.1 checked whether the same reasoning
applies here and found it does not: `purge_if_still_eligible` nulls the identity columns and *keeps
the row*, `KHEPRI-DEC-015` §2b calls the result "an opaque tombstone" holding "an opaque account
identifier", and nothing in `src/khepri/rca/` deletes an `AccountRow`. So `account_id` survives
every horizon and there is no delete for a RESTRICT constraint to block.

**Nothing to backfill.** Neither table has existed before, and no earlier column holds session or
external-identity state, so the upgrade creates and the downgrade drops. No data is at risk in
either direction -- which is why this revision may drop on downgrade where `20260814_0014` had to
reconstruct.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_0016"
down_revision: str | None = "20260814_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rca_sessions",
        # The hash, never the raw token. KHEPRI-DEC-015 §5 calls session identifiers bearer
        # material; R3-01 §9 settled hashing at rest so a database disclosure hands over no live
        # session. R3-02's `Session.issue` returns the raw token exactly once, for the cookie.
        sa.Column("session_id_hash", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        # Nullable: FR-028 requires an account with no membership to authenticate, and one nullable
        # column cannot hold two organizations -- FR-027 satisfied structurally, not by validation.
        sa.Column("active_organization_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # NULL means live. FR-008 requires revocation to take effect without waiting for expiry.
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("session_id_hash", name="pk_rca_sessions"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_session_account",
            ondelete="RESTRICT",
        ),
    )
    # FR-007 revokes every session for one account, so that is the query the index serves.
    op.create_index("ix_rca_sessions_account_id", "rca_sessions", ["account_id"])

    op.create_table(
        "rca_external_identities",
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_subject", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        # The composite key is what makes KHEPRI-DEC-018 §7 structural: "duplicate links fail
        # closed" and "an existing link MUST NOT silently move between accounts" are uniqueness
        # properties, and a primary key enforces them against every caller -- including one reaching
        # the row directly, which is the seam #151 was opened to close.
        sa.PrimaryKeyConstraint("provider", "provider_subject", name="pk_rca_external_identities"),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_external_identity_account",
            ondelete="RESTRICT",
        ),
    )
    # Not unique: one account may hold several links -- enterprise SSO beside a password provider.
    op.create_index(
        "ix_rca_external_identities_account_id", "rca_external_identities", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_rca_external_identities_account_id", table_name="rca_external_identities")
    op.drop_table("rca_external_identities")
    op.drop_index("ix_rca_sessions_account_id", table_name="rca_sessions")
    op.drop_table("rca_sessions")
