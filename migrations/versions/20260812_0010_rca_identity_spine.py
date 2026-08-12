"""Create the RCA commercial identity spine: accounts, organizations, memberships, scopes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0010"
down_revision: str | None = "20260730_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("rca_accounts", *_account_columns(), *_account_constraints())
    op.create_table("rca_organizations", *_organization_columns())
    op.create_table("rca_memberships", *_membership_columns(), *_membership_constraints())
    op.create_table("rca_isolation_scopes", *_scope_columns(), *_scope_constraints())


def downgrade() -> None:
    op.drop_table("rca_isolation_scopes")
    op.drop_table("rca_memberships")
    op.drop_table("rca_organizations")
    op.drop_table("rca_accounts")


def _account_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("credential_salt", sa.LargeBinary(), nullable=False),
        sa.Column("credential_digest", sa.LargeBinary(), nullable=False),
        # The scrypt cost parameters this digest was produced with, so the work factor can
        # be raised later without invalidating existing records.
        sa.Column("kdf_n", sa.Integer(), nullable=False),
        sa.Column("kdf_r", sa.Integer(), nullable=False),
        sa.Column("kdf_p", sa.Integer(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
    )


def _account_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("email", name="uq_rca_account_email"),
    )


def _organization_columns() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def _membership_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        # FR-014: every membership or role change records which account made it.
        sa.Column("changed_by", sa.String(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )


def _membership_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("organization_id", "account_id"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_membership_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_membership_account",
            ondelete="RESTRICT",
        ),
    )


def _scope_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("organization_id", sa.String(), nullable=False),
        # FR-032/FR-033: an opaque token allocated per organization, never derived from
        # any commercial identifier.
        sa.Column("owner_id", sa.String(), nullable=False),
    )


def _scope_constraints() -> tuple[sa.schema.SchemaItem, ...]:
    return (
        sa.PrimaryKeyConstraint("organization_id"),
        sa.UniqueConstraint("owner_id", name="uq_rca_scope_owner"),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_scope_organization",
            ondelete="RESTRICT",
        ),
    )
