from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from khepri.rca.accounts import Account, KdfParams, canonical_email
from khepri.rca.organizations import IsolationScope, Membership, Organization


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "rca_accounts"
    __table_args__ = (UniqueConstraint("email", name="uq_rca_account_email"),)

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    # Nullable so an account with no verifier is representable. KHEPRI-DEC-015 requires the
    # credential verifier to be DESTROYED ("immediate, non-recoverable") on disablement or
    # replacement. Disablement is a later slice; declaring the columns nullable now means
    # that slice needs no migration to satisfy the retention rule.
    credential_salt: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    credential_digest: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    kdf_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kdf_r: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kdf_p: Mapped[int | None] = mapped_column(Integer, nullable=True)


class OrganizationRow(Base):
    __tablename__ = "rca_organizations"

    organization_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MembershipRow(Base):
    __tablename__ = "rca_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_membership_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_membership_account",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    changed_by: Mapped[str] = mapped_column(String, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IsolationScopeRow(Base):
    __tablename__ = "rca_isolation_scopes"
    __table_args__ = (
        UniqueConstraint("owner_id", name="uq_rca_scope_owner"),
        ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_scope_organization",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _kdf_from_row(row: AccountRow) -> KdfParams | None:
    """None once the verifier has been destroyed on disablement (KHEPRI-DEC-015)."""
    stored = (row.kdf_n, row.kdf_r, row.kdf_p)
    if None in stored:
        return None
    n, r, p = stored
    return KdfParams(n=n, r=r, p=p)


def _account_from_row(row: AccountRow) -> Account:
    return Account(
        account_id=row.account_id,
        email=row.email,
        credential_salt=row.credential_salt,
        credential_digest=row.credential_digest,
        kdf=_kdf_from_row(row),
    )


def _membership_from_row(row: MembershipRow) -> Membership:
    return Membership(
        organization_id=row.organization_id,
        account_id=row.account_id,
        role=row.role,
        changed_by=row.changed_by,
        changed_at=_utc(row.changed_at),
    )


def _scope_from_row(row: IsolationScopeRow) -> IsolationScope:
    return IsolationScope.restore(
        organization_id=row.organization_id,
        owner_id=row.owner_id,
    )


class SqlAccountStore:
    """Persistence for accounts.

    Canonicalizes the email address on both write and read. `AccountService` also
    canonicalizes, but the store cannot rely on that: an importer, a backfill, or any other
    internal caller reaching `add_account` directly would otherwise persist `Owner@Example.Test`
    verbatim, and the case-sensitive unique constraint would admit it beside
    `owner@example.test` — two durable identities for one mailbox, in violation of `RCA-001`
    A-1, with the mixed-case row unreachable through canonicalized service lookups.
    Enforcing it at the boundary that owns the constraint makes the invariant unconditional.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def add_account(self, account: Account) -> bool:
        try:
            with self._factory.begin() as database:
                database.add(
                    AccountRow(
                        account_id=account.account_id,
                        email=canonical_email(account.email),
                        credential_salt=account.credential_salt,
                        credential_digest=account.credential_digest,
                        kdf_n=account.kdf.n,
                        kdf_r=account.kdf.r,
                        kdf_p=account.kdf.p,
                    )
                )
        except IntegrityError:
            return False
        return True

    def get_account_by_email(self, email: str) -> Account | None:
        with self._factory() as database:
            row = database.scalar(
                select(AccountRow).where(AccountRow.email == canonical_email(email))
            )
            if row is None:
                return None
            return _account_from_row(row)

    def get_account(self, account_id: str) -> Account | None:
        with self._factory() as database:
            row = database.get(AccountRow, account_id)
            if row is None:
                return None
            return _account_from_row(row)


class SqlOrganizationStore:
    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
    ) -> bool:
        """Write the organization, its owner membership, and its isolation scope atomically.

        The three records form one aggregate, so their identifiers must agree. Foreign keys
        alone do not enforce that: a membership naming a *different* existing organization
        satisfies every constraint, and the new organization commits with no owner. Verified
        — that produced an orphan organization, which FR-013's "never zero owner-role
        members" forbids from the moment of creation.
        """
        if membership.organization_id != organization.organization_id:
            return False
        if scope.organization_id != organization.organization_id:
            return False
        try:
            with self._factory.begin() as database:
                database.add(
                    OrganizationRow(
                        organization_id=organization.organization_id,
                        name=organization.name,
                        created_at=organization.created_at,
                    )
                )
                # Flush the parent row first: SQLAlchemy's unit-of-work sorts insert order
                # across mappers by their declaration sort key when no relationship() is
                # declared, not by ForeignKeyConstraint dependency. Without this explicit
                # flush, rca_isolation_scopes can be inserted before rca_organizations and
                # trip the FK even though both rows belong to the same commit.
                database.flush()
                database.add(
                    MembershipRow(
                        organization_id=membership.organization_id,
                        account_id=membership.account_id,
                        role=membership.role,
                        changed_by=membership.changed_by,
                        changed_at=membership.changed_at,
                    )
                )
                database.add(
                    IsolationScopeRow(
                        organization_id=scope.organization_id,
                        owner_id=scope.owner_id,
                    )
                )
        except IntegrityError:
            return False
        return True

    def get_membership(self, organization_id: str, account_id: str) -> Membership | None:
        with self._factory() as database:
            row = database.get(MembershipRow, (organization_id, account_id))
            if row is None:
                return None
            return _membership_from_row(row)

    def get_scope(self, organization_id: str) -> IsolationScope | None:
        with self._factory() as database:
            row = database.get(IsolationScopeRow, organization_id)
            if row is None:
                return None
            return _scope_from_row(row)
