from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
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
from khepri.rca.errors import (
    OWNER_CHANGE_APPLIED,
    OWNER_CHANGE_FINAL_OWNER,
    OWNER_CHANGE_NOT_APPLICABLE,
)
from khepri.rca.organizations import (
    OWNER_ROLE,
    ROLES,
    IsolationScope,
    Membership,
    MembershipEvent,
    Organization,
)
from khepri.rca.records import assert_sealed


def _role_in(roles: tuple[str, ...]) -> str:
    """Render the FR-015 role CHECK from the declared roles.

    Built from `ROLES` rather than spelled out, so adding a third role to the domain without a
    migration fails against the constraint rather than silently widening it. The values are
    module constants, never caller input, so quoting them here is not a parameterization
    boundary -- but the assertion keeps it that way if that ever stops being true.
    """
    assert all(role.isalpha() for role in roles), f"role names must be plain identifiers: {roles}"
    values = ", ".join(f"'{role}'" for role in roles)
    return f"role IN ({values})"


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
        # FR-015: exactly two roles. Built from `ROLES` rather than restating the two values,
        # so the column and the domain cannot drift into describing one rule two ways.
        #
        # **Declared here as well as in the migration, deliberately.** Store tests build their
        # schema from `Base.metadata.create_all`, which takes constraints from this model and
        # not from the migration -- so a CHECK that existed only in the migration would let the
        # whole store suite write `role="admin"` while production refused it. The inverse of
        # the trap `test_migration_preserves_constraints_and_nullability` documents.
        CheckConstraint(
            _role_in(ROLES),
            name="ck_rca_membership_role",
        ),
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
    # No attribution columns: `changed_by`/`changed_at` were dropped by `20260814_0014`.
    # Audit data on a state row with no expiry outlives its own twelve-month horizon
    # (`KHEPRI-DEC-015` §2a); it lives on `MembershipEventRow`, which is swept.


class MembershipEventRow(Base):
    """Append-only attribution for membership and role changes (`FR-014`).

    **No foreign key to `rca_accounts` or `rca_memberships`, deliberately.** Two reasons, and the
    second is the load-bearing one. `KHEPRI-DEC-015` §82 requires the record to be content-free —
    opaque identifiers only — and a `RESTRICT` foreign key is a referential claim rather than a
    content one, but it would make the *account purge* fail while any event still referenced the
    account. That inverts the horizon relationship the decision sets up: the twenty-four month
    account tombstone exists partly "to outlast the twelve-month audit horizon so that audit
    evidence never outlives the subject it refers to". The event must expire first and the
    account row must survive until it does; a RESTRICT constraint would enforce the opposite.

    The membership row is likewise unreferenced: revocation removes it while its event must
    survive, which is exactly what `KHEPRI-DEC-015` means by retaining the membership "only as
    the subject of the `FR-014` audit event".
    """

    __tablename__ = "rca_membership_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    organization_id: Mapped[str] = mapped_column(String, nullable=False)
    account_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_account_id: Mapped[str] = mapped_column(String, nullable=False)
    # Nullable in both directions: a creation has no prior role, a revocation has no next role.
    # The pair carries the event kind, so no event_type column can disagree with it.
    prior_role: Mapped[str | None] = mapped_column(String, nullable=True)
    next_role: Mapped[str | None] = mapped_column(String, nullable=True)
    # The twelve-month horizon is computed from this, and the sweeper selects on it.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )


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

    def purge_if_still_eligible(self, account_id: str, horizon: datetime) -> bool:
        """Tombstone an account, but only if the row still qualifies at write time.

        The sweep selects, then writes, and those were separate transactions with no predicate
        between them — so `enable_account` landing in the gap made the sweeper write its stale
        snapshot back, erasing a re-enabled account's email and restoring its old `disabled_at`.
        Verified before this method existed, and irreversible when it happened: §2b's purge is
        deliberately non-recoverable.

        Re-reading and re-checking the condition inside the writing transaction closes it. The
        predicate is the selection rule restated — disabled, before the horizon, not already
        purged — so a row that stopped qualifying is skipped rather than clobbered, and the
        returned count is work actually done.
        """
        with self._factory.begin() as database:
            row = database.get(AccountRow, account_id)
            if row is None or not _account_from_row(row).is_purgeable_at(horizon):
                return False
            row.email = None
            row.credential_salt = None
            row.credential_digest = None
            row.kdf_n = None
            row.kdf_r = None
            row.kdf_p = None
        return True

    def save_account(self, account: Account) -> bool:
        """Write an existing account's current state back, as one row update.

        Every verifier column moves together with the record's `verifier`, so a partially
        destroyed verifier cannot be written — which is what makes KHEPRI-DEC-015's "immediate,
        non-recoverable" destruction hold at the boundary rather than only in the domain type.

        Returns False when the row does not exist, so a caller cannot mistake a no-op for a
        successful write. The lifecycle service turns that into a uniform refusal.
        """
        with self._factory.begin() as database:
            return _apply_account(database, account)

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

        `disabled_at.is_not(None)` is **redundant and deliberately kept**. SQL's three-valued
        logic already excludes an enabled row, because `NULL < horizon` evaluates to NULL rather
        than TRUE. It is stated anyway because "only disabled accounts" is the rule this query
        implements, and leaving it to an emergent property of NULL comparison would make the
        next reader derive it. Mutation testing cannot kill this clause — removing it selects
        exactly the same rows, verified — so its absence from the mutation score is expected and
        is not a missing test.
        """
        with self._factory() as database:
            rows = database.scalars(
                select(AccountRow).where(
                    AccountRow.disabled_at.is_not(None),
                    # `<=`: DEC-015 2b purges "at the horizon", so the anniversary
                    # instant is eligible rather than one tick short of it.
                    AccountRow.disabled_at <= horizon,
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


def _event_row(event: MembershipEvent) -> MembershipEventRow:
    """One event record's row. Every field moves together; there is no partial event."""
    return MembershipEventRow(
        event_id=event.event_id,
        organization_id=event.organization_id,
        account_id=event.account_id,
        actor_account_id=event.actor_account_id,
        prior_role=event.prior_role,
        next_role=event.next_role,
        occurred_at=event.occurred_at,
    )


def _apply_account(database, account: Account) -> bool:
    """Write an account's current state onto its row inside the caller's transaction.

    Takes the session rather than opening one, because two callers need this with different
    transaction scopes: `save_account`, which is the whole operation, and
    `apply_owner_reducing_change`, where the write must land in the same transaction as the
    guard that permitted it. Extracting it is what stops those two from drifting into writing
    different column sets.

    Every verifier column moves together with the record's `verifier`, so a partially destroyed
    verifier cannot be written -- which is what makes `KHEPRI-DEC-015`'s "immediate,
    non-recoverable" destruction hold at the boundary rather than only in the domain type.

    Returns False when the row does not exist, so a caller cannot mistake a no-op for a
    successful write.
    """
    assert_sealed(account)
    verifier = account.verifier
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


def _effective_owner_conditions() -> tuple:
    """The effective-owner rule, expressed once.

    An owner counts only if the account holds the owner role, is enabled (`disabled_at IS
    NULL`), is not purged (`email IS NOT NULL`), and can actually authenticate
    (`credential_digest IS NOT NULL`). The last is load-bearing and the least obvious:
    re-enablement deliberately leaves the verifier destroyed (`KHEPRI-DEC-015` §5), so an
    enabled, unpurged owner may still be unable to log in -- and FR-013 asks whether an owner
    can *act*. Verified before that clause existed: disable A, re-enable A, disable B left an
    organization whose only remaining owner could not authenticate.

    This mirrors `Account.can_authenticate` in SQL. Extracted because it is now evaluated in two
    places -- the unlocked count and the locked guard -- and two copies of a rule this sharp
    drift. `test_rca001_final_owner.py` asserts the SQL and the Python agree state by state.
    """
    return (
        MembershipRow.role == OWNER_ROLE,
        AccountRow.disabled_at.is_(None),
        AccountRow.email.is_not(None),
        AccountRow.credential_digest.is_not(None),
    )


def owner_memberships_for_update(account_id: str):
    """Lock this account's owner-role memberships for the duration of the transaction.

    A named module-level statement rather than an inline `.with_for_update()`, following
    `khepri.rra.persistence.invitation_for_update_statement`. The reason is testability: SQLite
    emits no `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so if the lock were
    inline and someone later dropped it, the whole RCA suite would stay green while `#155`
    returned. Because this is a named function, a test compiles it against the PostgreSQL
    dialect and asserts `FOR UPDATE` is present without needing a database.

    Locking the *membership* rows rather than the account row is what makes competing
    operations on the same organization serialize: two different accounts disabling themselves
    contend on the organization's owner rows, which is where the invariant lives.
    """
    return (
        select(MembershipRow)
        .where(
            MembershipRow.account_id == account_id,
            MembershipRow.role == OWNER_ROLE,
        )
        .with_for_update()
    )


class SqlOrganizationStore:
    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def create_organization(
        self,
        organization: Organization,
        membership: Membership,
        scope: IsolationScope,
        event: MembershipEvent,
    ) -> bool:
        """Write the organization, its owner membership, its scope, and the creation event.

        The four records form one aggregate, so their identifiers must agree. Foreign keys
        alone do not enforce that: a membership naming a *different* existing organization
        satisfies every constraint, and the new organization commits with no owner. Verified
        — that produced an orphan organization, which FR-013's "never zero owner-role
        members" forbids from the moment of creation.

        **The event is written here rather than by a later call** because FR-014 requires every
        membership change to be attributable, and an event emitted outside this transaction
        could describe a creation that rolled back — or be missing for one that did not. The
        event carries no foreign key (see `MembershipEventRow`), so nothing but this identifier
        check stops it naming a different organization.
        """
        assert_sealed(organization, membership, scope, event)
        if membership.organization_id != organization.organization_id:
            return False
        if scope.organization_id != organization.organization_id:
            return False
        if event.organization_id != organization.organization_id:
            return False
        if event.account_id != membership.account_id:
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
                    )
                )
                database.add(
                    IsolationScopeRow(
                        organization_id=scope.organization_id,
                        owner_id=scope.owner_id,
                    )
                )
                database.add(_event_row(event))
        except IntegrityError:
            return False
        return True

    def promote_membership(self, membership: Membership, event: MembershipEvent) -> bool:
        """Write the promoted role and its event in one transaction (`FR-014`, `FR-015`).

        **No `SELECT ... FOR UPDATE` here, unlike `apply_owner_reducing_change`.** That method
        locks because it must count owners and then act on the count, and a concurrent write can
        invalidate a count between the two. Promotion has no such guard to invalidate: it raises
        the owner count, which `FR-013` never constrains, and two callers promoting the same
        membership converge on the same row. Taking the lock anyway would imply a guard exists
        here and invite a later reader to add one, which is what the roadmap's "two independent
        final-owner guards" stop condition forbids.

        The event travels with the write for the same reason it does in `create_organization`:
        an event committed separately can describe a change that rolled back, and a change
        committed without its event is an unattributed role change, which is `FR-014` unmet.

        Returns False rather than raising if the membership has vanished between the service's
        read and this write, so a concurrent revocation surfaces as an ordinary refusal.
        """
        assert_sealed(membership, event)
        if event.organization_id != membership.organization_id:
            return False
        if event.account_id != membership.account_id:
            return False
        if event.next_role != membership.role:
            return False
        try:
            with self._factory.begin() as database:
                key = (membership.organization_id, membership.account_id)
                row = database.get(MembershipRow, key)
                if row is None:
                    return False
                row.role = membership.role
                database.add(_event_row(event))
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
        """How many *effective* owners this organization would still have without that account.

        Phrased as the remaining count rather than the total because that is the question FR-013
        actually asks. The alternative — return the total and let the caller compare against one —
        pushes "is this account an owner?" into the service, where it has to be decided a second
        time and can disagree with the row this query saw.

        **The join onto `rca_accounts` is the load-bearing part.** Counting membership rows alone
        is not counting owners: disablement does not touch `rca_memberships`, so a disabled
        account keeps its owner-role row and would be counted as a live owner by the very guard
        meant to prevent stranding. Verified before this join existed — disabling a two-owner
        organization's owners one after the other passed the guard both times and left the
        organization with zero owners able to act, which is exactly the harm FR-013 forbids and
        which the `khepri.rca.accounts` module docstring records slice 1 having already caused
        once by a different route.

        Which accounts count is `_effective_owner_conditions`, not restated here — an earlier
        version of this docstring listed the enabled and not-purged conditions and omitted the
        `credential_digest` clause, which is the one that matters most. Naming the function is
        what stops the prose and the query from disagreeing again.

        The purged tombstone is worth calling out even so: its membership row survives because
        `fk_rca_membership_account` is `RESTRICT`, so without that predicate it would be counted
        as an owner forever.

        **This count is unlocked**, and is the right tool for a read. An owner-reducing
        *decision* must use `apply_owner_reducing_change`, which counts the same way inside a
        transaction that holds the rows — see `#155` for what a count read outside the write's
        transaction permits.
        """
        with self._factory() as database:
            return (
                database.execute(
                    select(func.count())
                    .select_from(MembershipRow)
                    .join(AccountRow, AccountRow.account_id == MembershipRow.account_id)
                    .where(
                        MembershipRow.organization_id == organization_id,
                        MembershipRow.account_id != excluding_account_id,
                        *_effective_owner_conditions(),
                    )
                ).scalar()
                or 0
            )

    def apply_owner_reducing_change(self, account_id: str, updated: Account) -> str:
        """Guard FR-013 and write `updated` as one atomic decision (`#155`).

        The defect this closes: the guard and the write were three round trips on three
        sessions, so two concurrent disablements of a two-owner organization could both count
        a live co-owner, both pass, and both commit, leaving zero. Verified deterministically
        against PostgreSQL before this method existed -- see
        `tests/test_rca001_concurrent_final_owner.py`, where three contending owners left the
        organization with none.

        `updated` arrives already built. `Account` is frozen and sealed, so a state change is a
        new instance through a door, and there is no mutable handle a transaction could be
        handed instead. That is also why no door opens in here: `records.py` records that a
        door authorizes the *thread* rather than one call, and a round trip under `FOR UPDATE`
        blocks and can wait on another transaction's lock, which is a far wider grant than the
        single constructor call the doors are scoped to.

        Returns an outcome rather than raising, so the FR-013 refusal message stays in
        `errors.py` with the rest of the refusal vocabulary.
        """
        with self._factory.begin() as database:
            owned = database.scalars(owner_memberships_for_update(account_id)).all()
            if database.get(AccountRow, account_id) is None:
                return OWNER_CHANGE_NOT_APPLICABLE
            for membership in owned:
                # Counted inside the transaction, on rows this statement holds a lock over. A
                # competing owner-reducing operation on the same organization is blocked at the
                # SELECT above until this commits, so it observes the write rather than the
                # state that preceded it.
                remaining = database.execute(
                    select(func.count())
                    .select_from(MembershipRow)
                    .join(AccountRow, AccountRow.account_id == MembershipRow.account_id)
                    .where(
                        MembershipRow.organization_id == membership.organization_id,
                        MembershipRow.account_id != account_id,
                        *_effective_owner_conditions(),
                    )
                ).scalar()
                if not remaining:
                    return OWNER_CHANGE_FINAL_OWNER
            if not _apply_account(database, updated):
                return OWNER_CHANGE_NOT_APPLICABLE
        return OWNER_CHANGE_APPLIED
