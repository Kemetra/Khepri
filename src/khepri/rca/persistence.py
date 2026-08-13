from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from khepri.rca.accounts import Account, canonical_email
from khepri.rca.credentials import KdfParams, Verifier
from khepri.rca.organizations import OWNER_ROLE, IsolationScope, Membership, Organization
from khepri.rca.records import assert_sealed


class Base(DeclarativeBase):
    pass


class AccountRow(Base):
    __tablename__ = "rca_accounts"
    __table_args__ = (UniqueConstraint("email", name="uq_rca_account_email"),)

    account_id: Mapped[str] = mapped_column(String, primary_key=True)
    # Nullable so KHEPRI-DEC-015 §2b's post-horizon tombstone is representable: 24 months after
    # disablement the identity fields are purged and only an opaque identifier and the
    # disablement timestamp remain. A NOT NULL email would also hold the A-1 uniqueness
    # reservation forever, which §2b explicitly releases ("that address may be registered
    # again ... because no account claims it any longer").
    #
    # The unique constraint still expresses A-1 correctly: SQL treats NULLs as distinct, so many
    # purged rows coexist while live addresses stay unique.
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    # NULL means enabled. The 24-month horizon in §2b is computed from this, and account state is
    # derived from it rather than duplicated into a boolean that could disagree.
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


def _canonical_or_none(email: str | None) -> str | None:
    """Canonicalize a live address; leave a purged tombstone's NULL alone (KHEPRI-DEC-015 §2b)."""
    return None if email is None else canonical_email(email)


def _verifier_from_row(row: AccountRow) -> Verifier | None:
    """None once the verifier has been destroyed on disablement (KHEPRI-DEC-015).

    Treats the five verifier columns as one value: a row is either a complete verifier or no
    verifier at all. A partially-populated row — a salt with no digest, a digest with no work
    factor — is not a verifier that happens to be missing a piece; it is a record that cannot
    be verified, and admitting it as a `Verifier` would let a half-destroyed row look live.
    """
    stored = (row.credential_salt, row.credential_digest, row.kdf_n, row.kdf_r, row.kdf_p)
    if any(part is None for part in stored):
        return None
    salt, digest, n, r, p = stored
    return Verifier._from_storage(salt=salt, digest=digest, kdf=KdfParams(n=n, r=r, p=p))


def _account_from_row(row: AccountRow) -> Account:
    return Account._from_storage(
        account_id=row.account_id,
        email=row.email,
        verifier=_verifier_from_row(row),
        disabled_at=_utc(row.disabled_at),
    )


def _membership_from_row(row: MembershipRow) -> Membership:
    return Membership._from_storage(
        organization_id=row.organization_id,
        account_id=row.account_id,
        role=row.role,
        changed_by=row.changed_by,
        changed_at=_utc(row.changed_at),
    )


def _scope_from_row(row: IsolationScopeRow) -> IsolationScope:
    return IsolationScope._from_storage(
        organization_id=row.organization_id,
        owner_id=row.owner_id,
    )


class SqlAccountStore:
    """Persistence for accounts.

    Canonicalizes the email address on both write and read. `Account.create` also
    canonicalizes, but the store cannot rely on that: an importer, a backfill, or any other
    internal caller reaching `add_account` directly would otherwise persist `Owner@Example.Test`
    verbatim, and the case-sensitive unique constraint would admit it beside
    `owner@example.test` — two durable identities for one mailbox, in violation of `RCA-001`
    A-1, with the mixed-case row unreachable through canonicalized service lookups.
    Enforcing it at the boundary that owns the constraint makes the invariant unconditional.

    The verifier is written as one value or not at all (#151): the five credential columns are
    populated together from `Account.verifier`, or all set NULL, so a half-destroyed verifier
    cannot be produced here.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def add_account(self, account: Account) -> bool:
        assert_sealed(account)
        verifier = account.verifier
        try:
            with self._factory.begin() as database:
                database.add(
                    AccountRow(
                        account_id=account.account_id,
                        email=_canonical_or_none(account.email),
                        credential_salt=None if verifier is None else verifier.salt,
                        credential_digest=None if verifier is None else verifier.digest,
                        kdf_n=None if verifier is None else verifier.kdf.n,
                        kdf_r=None if verifier is None else verifier.kdf.r,
                        kdf_p=None if verifier is None else verifier.kdf.p,
                        disabled_at=account.disabled_at,
                    )
                )
        except IntegrityError:
            return False
        return True

    def save_account(self, account: Account) -> bool:
        """Write an existing account's current state back, as one row update.

        Every verifier column moves together with the record's `verifier`, so a partially
        destroyed verifier cannot be written — which is what makes KHEPRI-DEC-015's "immediate,
        non-recoverable" destruction hold at the boundary rather than only in the domain type.

        Returns False when the row does not exist, so a caller cannot mistake a no-op for a
        successful write. The lifecycle service turns that into a uniform refusal.
        """
        assert_sealed(account)
        verifier = account.verifier
        with self._factory.begin() as database:
            row = database.get(AccountRow, account.account_id)
            if row is None:
                return False
            row.email = _canonical_or_none(account.email)
            row.credential_salt = None if verifier is None else verifier.salt
            row.credential_digest = None if verifier is None else verifier.digest
            row.kdf_n = None if verifier is None else verifier.kdf.n
            row.kdf_r = None if verifier is None else verifier.kdf.r
            row.kdf_p = None if verifier is None else verifier.kdf.p
            row.disabled_at = account.disabled_at
        return True

    def get_account_by_email(self, email: str) -> Account | None:
        with self._factory() as database:
            row = database.scalar(
                select(AccountRow).where(AccountRow.email == canonical_email(email))
            )
            if row is None:
                return None
            return _account_from_row(row)

    def accounts_disabled_before(self, horizon: datetime) -> list[Account]:
        """Disabled, not-yet-purged accounts whose 24-month horizon has elapsed.

        `email.is_not(None)` is what makes the sweep idempotent: a purged row no longer matches,
        so repeated passes do no repeated work and the count a pass reports is the work it
        actually did.
        """
        with self._factory() as database:
            rows = database.scalars(
                select(AccountRow).where(
                    AccountRow.disabled_at.is_not(None),
                    AccountRow.disabled_at < horizon,
                    AccountRow.email.is_not(None),
                )
            ).all()
            return [_account_from_row(row) for row in rows]

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
        assert_sealed(organization, membership, scope)
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

    def memberships_for_account(self, account_id: str) -> list[Membership]:
        with self._factory() as database:
            rows = database.scalars(
                select(MembershipRow).where(MembershipRow.account_id == account_id)
            ).all()
            return [_membership_from_row(row) for row in rows]

    def count_owners(self, organization_id: str, *, excluding_account_id: str) -> int:
        """How many owner-role members this organization would still have without that account.

        Phrased as the remaining count rather than the total because that is the question FR-013
        actually asks. The alternative — return the total and let the caller compare against one —
        pushes "is this account an owner?" into the service, where it has to be decided a second
        time and can disagree with the row this query saw.
        """
        with self._factory() as database:
            return (
                database.execute(
                    select(func.count())
                    .select_from(MembershipRow)
                    .where(
                        MembershipRow.organization_id == organization_id,
                        MembershipRow.role == OWNER_ROLE,
                        MembershipRow.account_id != excluding_account_id,
                    )
                ).scalar()
                or 0
            )
