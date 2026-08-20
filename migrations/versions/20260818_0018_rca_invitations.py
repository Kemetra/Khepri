"""Add `rca_invitations` (`R4-03`).

One table, carrying the record `R4-01` §3 specifies and the four `CHECK` constraints it requires.

**`down_revision` is `20260817_0017`, an RRA revision.** The chain is no longer RCA-contiguous:
`R7-02`'s `rra_sessions_allow_many_per_scope` merged after `R3-03`'s tables, so the current head is
RRA's and this revision chains from it. `tests/test_rca001_migration.py` reads each revision's
parent
from its own table rather than deriving it positionally, so an interleaved chain stays checkable.

**Values are spelled literally here and built from `ROLES` in the model, deliberately.** Same split
as `20260814_0015`: a migration is a historical record of what the schema became on a given day, and
importing a module constant into one would let a later edit to that constant silently rewrite
history. The model does the opposite, building the constraint from `ROLES` so the domain and the
column cannot drift. `test_the_role_check_agrees_between_the_migration_and_the_model` is what keeps
the two spellings honest, and `R4-03` adds its invitation counterpart.

**No `UNIQUE` of any kind, and that is the decision rather than an omission.** `R4-01` §3: one
organization may hold many open invitations, and in particular there is no
`UNIQUE (organization_id, target_identity)` because the same person may hold two outstanding
invitations -- the scenario §7's counter-example turns on. Encoding a cardinality nobody requires is
the defect `R7-02` spent a slice unwinding, and `KHEPRI-DEC-020` §4's lesson asks that a schema
change state which constraints it considered. These are the ones considered and refused.

**No foreign key on `issued_by`.** `organization_id` gets a `RESTRICT` constraint onto
`rca_organizations`; the inviting account deliberately gets none. `KHEPRI-DEC-015` §2b purges an
account by tombstoning its row, but `R4-01` §8.2 accepted the residual that an unredeemed invitation
may outlive the account that issued it, and a `RESTRICT` here would convert that accepted residual
into a purge failure. The column holds an opaque account identifier for `FR-014`-style attribution,
which survives the tombstone.

**Nothing to backfill.** The table has not existed before and no earlier column holds invitation
state, so the upgrade creates and the downgrade drops. No data is at risk in either direction.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0018"
down_revision: str | None = "20260817_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled literally rather than imported -- see the module docstring. The five-column clause
# compares every column against the first rather than chaining pairwise: with a chain, transitivity
# holds only if every link is present, and a comparison against one anchor survives a gap.
_ROLE_CHECK = "intended_role IN ('owner', 'member')"
_TERMINAL_STATE_CHECK = "redeemed_at IS NULL OR revoked_at IS NULL"
_EXPIRY_CHECK = "expires_at > issued_at"
_VERIFIER_WHOLE_CHECK = (
    "((secret_salt IS NULL) = (secret_digest IS NULL))"
    " AND ((secret_salt IS NULL) = (kdf_n IS NULL))"
    " AND ((secret_salt IS NULL) = (kdf_r IS NULL))"
    " AND ((secret_salt IS NULL) = (kdf_p IS NULL))"
)


def upgrade() -> None:
    op.create_table(
        "rca_invitations",
        sa.Column("invitation_id", sa.String(), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("intended_role", sa.String(), nullable=False),
        sa.Column("target_identity", sa.String(), nullable=False),
        # The verifier's five columns, nullable together or not at all -- see the CHECK below.
        sa.Column("secret_salt", sa.LargeBinary(), nullable=True),
        sa.Column("secret_digest", sa.LargeBinary(), nullable=True),
        sa.Column("kdf_n", sa.Integer(), nullable=True),
        sa.Column("kdf_r", sa.Integer(), nullable=True),
        sa.Column("kdf_p", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_by", sa.String(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("invitation_id", name="pk_rca_invitations"),
        sa.CheckConstraint(_ROLE_CHECK, name="ck_rca_invitation_role"),
        sa.CheckConstraint(_TERMINAL_STATE_CHECK, name="ck_rca_invitation_terminal_state"),
        sa.CheckConstraint(_EXPIRY_CHECK, name="ck_rca_invitation_expiry_after_issuance"),
        sa.CheckConstraint(_VERIFIER_WHOLE_CHECK, name="ck_rca_invitation_verifier_whole"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_invitation_organization",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_rca_invitations_organization_id", "rca_invitations", ["organization_id"]
    )
    op.create_index(
        "ix_rca_invitations_target_identity", "rca_invitations", ["target_identity"]
    )


def downgrade() -> None:
    op.drop_index("ix_rca_invitations_target_identity", table_name="rca_invitations")
    op.drop_index("ix_rca_invitations_organization_id", table_name="rca_invitations")
    op.drop_table("rca_invitations")
