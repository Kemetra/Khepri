from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    and_,
    delete,
    func,
    or_,
    select,
    text,
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
    MEMBER_ROLE,
    OWNER_ROLE,
    ROLES,
    IsolationScope,
    Membership,
    MembershipEvent,
    Organization,
)
from khepri.rca.records import assert_sealed


def _role_in(roles: tuple[str, ...], column: str = "role") -> str:
    """Render a role CHECK from the declared roles, for the named column.

    Built from `ROLES` rather than spelled out, so adding a third role to the domain without a
    migration fails against the constraint rather than silently widening it. The values are
    module constants, never caller input, so quoting them here is not a parameterization
    boundary -- but the assertion keeps it that way if that ever stops being true.

    `column` exists because `R4-03`'s invitation carries `intended_role` rather than `role`, and one
    renderer for both keeps the two constraints from drifting into describing one rule two ways --
    which is the whole reason this function is not a string literal.
    """
    assert all(role.isalpha() for role in roles), f"role names must be plain identifiers: {roles}"
    assert column.replace("_", "").isalpha(), f"column must be an identifier: {column!r}"
    values = ", ".join(f"'{role}'" for role in roles)
    return f"{column} IN ({values})"


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


class SessionRow(Base):
    """One commercial authentication session (`R3-02`, `R3-03`).

    **The primary key is the hash, never the raw token.** `KHEPRI-DEC-015` §5 calls session
    identifiers bearer material, and `R3-01` §9 settled hashing at rest: a database disclosure must
    not hand over live sessions. `Session.issue` returns the raw token exactly once, for the cookie.

    **No role, no membership, no `owner_id`, no `can_act`.** `FR-030` requires a membership or role
    change to take effect for decisions made after it without the session ending, and `FR-008`
    requires disablement to stop authorization without waiting for expiry. A column here for any of
    those goes stale exactly when it matters, so the schema does not offer one.
    """

    __tablename__ = "rca_sessions"
    __table_args__ = (
        # RESTRICT, matching `fk_rca_membership_account`. Safe against KHEPRI-DEC-015 §2b because
        # the purge tombstones the account row rather than deleting it -- verified in `R3-09` §3.1.
        ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_session_account",
            ondelete="RESTRICT",
        ),
    )

    session_id_hash: Mapped[str] = mapped_column(String, primary_key=True)
    account_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Nullable because FR-028 requires an account with no membership to authenticate. One nullable
    # column cannot hold two organizations, which is how FR-027 is satisfied structurally.
    active_organization_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL means live. FR-007 revokes by account, which is why `account_id` is indexed.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExternalIdentityRow(Base):
    """`(provider, provider_subject) -> account_id` (`KHEPRI-DEC-018` §7, `R3-09` §3).

    **The composite primary key is what makes `§7` structural.** "Duplicate links fail closed" and
    "an existing link MUST NOT silently move between accounts" are uniqueness properties, and a
    primary key enforces them against every caller -- including one reaching the row directly, which
    is the seam `#151` was opened to close. An application check could be forgotten; this cannot.

    **What is deliberately absent:** no email (`§7`: "Email is not the durable identity key"), no
    provider organization/role/permission claim (`§4`), and no provider access or refresh token --
    `§5` gate 1 admits only enumerated personal-data classes, and a stored provider token would be
    both a new class and a credential Khepri has no reason to hold.
    """

    __tablename__ = "rca_external_identities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id"],
            ["rca_accounts.account_id"],
            name="fk_rca_external_identity_account",
            ondelete="RESTRICT",
        ),
    )

    provider: Mapped[str] = mapped_column(String, primary_key=True)
    provider_subject: Mapped[str] = mapped_column(String, primary_key=True)
    # Not unique: one account may hold several links -- enterprise SSO beside a password provider.
    # `R3-09` §3 chose a dedicated table over columns on `rca_accounts` for exactly this.
    account_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def _verifier_columns_agree(prefix: str) -> str:
    """Render the CHECK that the five verifier columns are NULL together or not at all.

    `Verifier` is an optional *whole*: `credentials.py:77-80` records that destruction "replaces the
    whole verifier with `None` and cannot be done by halves". Held as five independently-nullable
    columns, a half-destroyed verifier -- salt gone, digest kept -- is expressible and nothing
    in the schema refuses it. `_verifier_from_row` already treats them as one whole on read; this
    makes the storage layer agree.

    **`AccountRow` does not carry this constraint**, and `R4-03` adds what that table lacks rather
    than retrofitting it: widening an existing table is a separate migration on its own slice, and
    `KHEPRI-DEC-015`'s account path already destroys all five together at its one call site.
    """
    assert prefix.replace("_", "").isalnum(), f"prefix must be an identifier: {prefix!r}"
    parts = [f"{prefix}salt", f"{prefix}digest", "kdf_n", "kdf_r", "kdf_p"]
    first, *rest = parts
    clauses = [f"(({first} IS NULL) = ({column} IS NULL))" for column in rest]
    return " AND ".join(clauses)


class InvitationRow(Base):
    """One offer of one membership in one organization (`R4-01` §3, `R4-03`).

    Declared here rather than in `invitation_persistence.py` because the `Base` metadata is shared
    and this table carries a foreign key onto `rca_organizations`; only the store moves, following
    the `R3-03` split recorded in `session_persistence.py:1-12`.

    **Four states, discriminated by nullability rather than a status column**, matching
    `Invitation`'s own model: a `status` column could disagree with the timestamps and then two
    fields would describe one fact. Expiry has no column at all -- it is `expires_at <= now`.

    **No `UNIQUE` of any kind, and that is a decision rather than an omission.** `R4-01` §3 is
    explicit: one organization may hold many open invitations, and in particular there is no
    `UNIQUE (organization_id, target_identity)` because the same person may hold two outstanding
    invitations -- the scenario §7's counter-example turns on. Encoding a cardinality nobody
    requires is the defect `R7-02` spent a slice unwinding (`KHEPRI-DEC-020`).

    **`target_identity`, not `email`.** `KHEPRI-DEC-015` §2 governs "Login identity (email)" as its
    own class with a fixed 24-month horizon; this field is lifecycle-derived and purged when replay
    refusal no longer needs it. One name for both would make the shorter rule invisible. Stored
    canonicalized, per §4.

    **What no CHECK here can say.** "The verifier is NULL only in a terminal state" cannot be
    expressed: expiry is time-derived, so a legitimately-swept expired invitation has a NULL
    verifier and both timestamps NULL, which at the row level is indistinguishable from an open
    invitation whose verifier was wrongly destroyed. `CHECK (... expires_at <= now())` is not
    writable -- `now()` is not immutable and PostgreSQL refuses it. That invariant is the domain's,
    held by the two paths that may destroy without a timestamp both evaluating `expires_at <= now`
    in the destroying transaction. Recorded rather than papered over with a constraint that would be
    wrong. """

    __tablename__ = "rca_invitations"
    __table_args__ = (
        # Every CHECK below is declared here **as well as** in the migration. Store tests build
        # their schema from `Base.metadata.create_all`, which reads this model and not the
        # migration -- so a CHECK that existed only there would let the whole store suite write
        # forbidden rows while production refused them. Same trap `ck_rca_membership_role`
        # documents, and the same deliberate asymmetry: the migration spells the values literally
        # because it is a historical record, this builds them from `ROLES`.
        CheckConstraint(
            _role_in(ROLES, "intended_role"),
            name="ck_rca_invitation_role",
        ),
        # An invitation cannot be both redeemed and revoked. §5's state table has four states and
        # this is the pair it excludes.
        CheckConstraint(
            "redeemed_at IS NULL OR revoked_at IS NULL",
            name="ck_rca_invitation_terminal_state",
        ),
        # Following `ck_session_expiry_after_creation`. `Invitation.create` already refuses this in
        # the domain; a store caller reaching the row directly would not.
        CheckConstraint(
            "expires_at > issued_at",
            name="ck_rca_invitation_expiry_after_issuance",
        ),
        CheckConstraint(
            _verifier_columns_agree("secret_"),
            name="ck_rca_invitation_verifier_whole",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["rca_organizations.organization_id"],
            name="fk_rca_invitation_organization",
            ondelete="RESTRICT",
        ),
    )

    invitation_id: Mapped[str] = mapped_column(String, primary_key=True)
    # Indexed: revocation is scoped by `(organization_id, invitation_id)` per §4.1, and listing an
    # organization's open invitations is what `R8-05`'s team screens will ask for.
    organization_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    intended_role: Mapped[str] = mapped_column(String, nullable=False)
    # Indexed: the `FR-020` and purge cascades both look invitations up by recipient.
    target_identity: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # The five verifier columns, nullable together or not at all -- see the CHECK above. `secret_`
    # prefixed rather than `credential_` because this is not a credential: it verifies a bearer
    # token, and one name for both classes would invite one retention rule for both.
    secret_salt: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    secret_digest: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    kdf_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kdf_r: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kdf_p: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # `FR-014`-style attribution. No foreign key onto `rca_accounts`: the inviting account may be
    # purged under `KHEPRI-DEC-015` §2b while an unredeemed invitation survives, and a `RESTRICT`
    # here would make the purge fail. §8.2 accepted that residual explicitly.
    issued_by: Mapped[str] = mapped_column(String, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    redeemed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


def account_for_update(account_id: str):
    """Lock one account row for the duration of the caller's transaction (`R4-05`, §6.1).

    A **module-level named statement** rather than an inline `.with_for_update()`, following
    `owner_memberships_for_update` and `organization_owners_for_update` for the reason stated at
    those: SQLite emits no `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so an
    inline lock someone later dropped would leave the whole RCA suite green. Because it is named, a
    test compiles it against the PostgreSQL dialect and asserts `FOR UPDATE` is present without
    needing a database.

    **Why redemption locks the account row and not the memberships.**
    `owner_memberships_for_update` selects owner rows in organizations the account already owns, and
    `FR-019`'s invitee owns none -- frequently the account did not exist when the invitation was
    issued. `SELECT ... FOR UPDATE` over an **empty result set acquires no lock at all**, so a
    concurrent `disable_account` would block on nothing. The account row is the one row both
    operations certainly touch: disablement writes it, and redemption's liveness question is about
    it.

    **The counterpart writes need no change.** They already take conflicting row locks by virtue of
    being `UPDATE`s -- `_apply_account` on the disable path, `save_session` and the bulk
    `update(SessionRow)` on the session-ending paths -- so this lock is the second half of a mutual
    exclusion rather than one waiting for a partner. §8.4 withdrew the counterpart slice two earlier
    revisions of the design note required.
    """
    return select(AccountRow).where(AccountRow.account_id == account_id).with_for_update()


def identity_lock_key(canonical_address: str) -> int:
    """The advisory-lock key for one canonical address (`R4-01` §8.2).

    **A stable digest, never `hash()`.** `pg_advisory_xact_lock` takes a `bigint`, so the address
    must be mapped to one -- and Python's `hash()` on a `str` is randomised per process under
    PEP 456, so two workers would derive **different** keys for the same address, acquire
    non-conflicting locks, and serialize nothing. The lock would look present in code review and in
    any single-process test while doing nothing in production. That is the defect `#212`/`#213`
    fixed once already in this note's own key derivation.

    **The address must be canonical**, per §4's storage rule and for the same reason: a case
    difference produces a different digest, and the two paths would lock different keys. Callers
    pass a value already folded; this does not fold again, so that the key is a pure function of
    what it is given and the test's committed constant means what it says.

    `signed=True` because `bigint` is signed and PostgreSQL rejects an out-of-range key.
    """
    return int.from_bytes(sha256(canonical_address.encode()).digest()[:8], "big", signed=True)


def identity_advisory_lock(canonical_address: str):
    """A transaction-scoped advisory lock over one identity (`R4-01` §8.2).

    A **module-level named statement** rather than an inline `text()` call, following
    `owner_memberships_for_update` and its siblings: SQLite silently ignores what PostgreSQL
    honours, so a lock the suite cannot compile is a lock the suite cannot assert. The evidence is
    a dialect-compilation test, not a database round trip.

    **What this closes and what it does not.** It serializes the **issuance-first** ordering: an
    `issue` that begins before the purge is held behind it, so its invitation is visible to the
    purge's cascade. It does **not** close the purge-first ordering -- an `issue` beginning after
    the purge commits looks the addressee up by canonical address, finds the tombstone has no
    address, takes no lock correctly (a post-purge miss is indistinguishable from `FR-019`'s
    ordinary no-account case), and inserts an open invitation after the cascade has run. §7.1
    retracted a row-lock fix for exactly this reason: "a **row** lock cannot serialize two
    operations when the discriminating fact is that the row stops being *discoverable* by the key
    one of them uses."

    §8.2 records the owner's decision of 2026-08-18 to **accept that residual** rather than amend
    `KHEPRI-DEC-015` to retain an address-derived marker. So this is half a fix, deliberately, and
    this docstring says so rather than letting a reader mistake a half-closed race for a closed one
    -- which §8.2 requires in those words.

    It stores nothing and is transaction-scoped, so it releases on commit or rollback with no
    cleanup path and prejudges none of the answers §8.2 left open.
    """
    return text("SELECT pg_advisory_xact_lock(:identity_lock_key)").bindparams(
        identity_lock_key=identity_lock_key(canonical_address)
    )


def take_identity_lock(database, canonical_address: str) -> bool:
    """Acquire the identity lock when the backend has one. True when it was taken.

    **Guarded on the dialect, not on a setting.** `pg_advisory_xact_lock` does not exist in SQLite
    -- executing the statement there raises `no such function` -- and the suite runs on SQLite while
    production runs on PostgreSQL. An environment-flag guard would be worse than this: a lock that
    silently vanishes when a variable is unset is the shape §8.2 warns about, where the code reads
    correctly and serializes nothing. The dialect *is* the fact that decides whether the lock means
    anything, so it is what the branch reads.

    This is stated in §8.2: "SQLite emits no advisory lock, so `R4-07`'s race case runs against
    PostgreSQL". A serialization claim made from a SQLite run is unfounded, and the returned bool is
    what lets a test assert which happened rather than infer it.
    """
    bind = database.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    database.execute(identity_advisory_lock(canonical_address))
    return True


def _cascade_invitations(
    database,
    *,
    organization_id: str | None,
    target_identity: str | None = None,
    issued_by: str | None = None,
    now: datetime | None = None,
) -> int:
    """Delete open invitations matched by a recipient and/or an issuer predicate (`R4-06`).

    **A `DELETE`, not a `revoked_at` marker.** `R4-01` §3: "Both purposes therefore lapse for a
    non-redeemed invitation the moment it is closed, and neither authorizes holding
    `target_identity` past that point." Every row this reaches is `redeemed_at IS NULL` by
    construction, so all of them are that rule's first row. §7 previously said to mark and keep,
    contradicting §4.1's "§7's cascades take the same shape" as its `DELETE`; corrected in the note
    on 2026-08-20 and recorded there rather than decided here.

    **Takes `database` rather than opening a transaction.** Every caller is already inside one, and
    that is the whole point: §7 argues at length that a cascade running *after* its trigger's
    transaction commits leaves a window in which the membership is revoked and the invitation is
    still redeemable, so the revoked member walks back in through a held token. The three writes --
    the membership row, its `FR-014` event, and these invitations -- commit or roll back together.

    **`organization_id=None` means every organization**, which only the purge trigger uses (§7.1):
    "the trigger is the identity ending, not a membership ending, so every outstanding offer to that
    person lapses at once". Passing `None` accidentally is the one dangerous mistake here, so the
    two membership callers pass a real value and this is the only branch that widens.

    **`now=None` omits the expiry clause**, which again only the purge trigger does. §4.1's
    `expires_at > :now` stops *revocation* reporting success on a state its caller may not change;
    this cascade has no actor and reports nothing, and an expired invitation to a purged address is
    exactly a row §3 says may no longer hold its target identity. Corrected in §7.1 on 2026-08-20,
    where "§7's cascades inherit this clause" was too broad.

    Returns the number of rows deleted, for the caller's evidence rather than for control flow.
    """
    anchors = []
    if target_identity is not None:
        anchors.append(InvitationRow.target_identity == canonical_email(target_identity))
    if issued_by is not None:
        anchors.append(InvitationRow.issued_by == issued_by)
    if not anchors:
        # Neither anchor is resolvable -- a tombstone whose address is gone and no issuer given.
        # Deleting on the remaining predicates alone would close every open invitation in the
        # organization, so this fails closed by doing nothing.
        return 0

    conditions = [
        or_(*anchors),
        InvitationRow.redeemed_at.is_(None),
        InvitationRow.revoked_at.is_(None),
    ]
    if organization_id is not None:
        conditions.append(InvitationRow.organization_id == organization_id)
    if now is not None:
        conditions.append(InvitationRow.expires_at > now)

    result = database.execute(delete(InvitationRow).where(and_(*conditions)))
    return int(result.rowcount or 0)


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


def _account_row(account: Account) -> AccountRow:
    verifier = account.verifier
    return AccountRow(
        account_id=account.account_id,
        email=_canonical_or_none(account.email),
        credential_salt=None if verifier is None else verifier.salt,
        credential_digest=None if verifier is None else verifier.digest,
        kdf_n=None if verifier is None else verifier.kdf.n,
        kdf_r=None if verifier is None else verifier.kdf.r,
        kdf_p=None if verifier is None else verifier.kdf.p,
        disabled_at=account.disabled_at,
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
        try:
            with self._factory.begin() as database:
                database.add(_account_row(account))
        except IntegrityError:
            return False
        return True

    def add_account_with_external_identity(
        self,
        account: Account,
        provider: str,
        provider_subject: str,
        *,
        linked_at: datetime,
    ) -> bool:
        """Commit an external-only account and its immutable subject mapping together."""
        assert_sealed(account)
        try:
            with self._factory.begin() as database:
                database.add(_account_row(account))
                database.flush()
                database.add(
                    ExternalIdentityRow(
                        provider=provider,
                        provider_subject=provider_subject,
                        account_id=account.account_id,
                        linked_at=linked_at,
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
            # `R4-01` §8.2's advisory lock over the identity, taken before the cascade below and
            # released when this transaction ends. It closes the **issuance-first** ordering: an
            # `issue` for this address that began first holds the same key, so this blocks until it
            # commits and the cascade then sees its row. The purge-first ordering stays open and is
            # the residual the owner accepted -- see `identity_advisory_lock`.
            #
            # After the eligibility check, so a declined purge acquires nothing and blocks nobody.
            take_identity_lock(database, canonical_email(row.email))
            # `R4-01` §7.1's third trigger, in this transaction and **after** the eligibility
            # check above. A cascade placed before it would close invitations for an account that
            # turned out not to be purgeable -- the "erased a re-enabled account's email" defect
            # this method exists to prevent, in a second column.
            #
            # Unscoped by organization, deliberately: the trigger is the identity ending, so every
            # outstanding offer to that person lapses at once. And no expiry clause -- an expired
            # invitation to a released address is exactly a row whose `target_identity` §3 says may
            # no longer be held.
            #
            # The address is read here, before the line below nulls it, which is the ordering §7.1
            # fixes inside this transaction.
            _cascade_invitations(
                database, organization_id=None, target_identity=row.email
            )
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
    NULL`), is not purged (`email IS NOT NULL`), and can actually authenticate through either a
    local verifier or a durable external-identity link. The last is load-bearing:
    re-enablement deliberately leaves the verifier destroyed (`KHEPRI-DEC-015` §5), so an
    enabled, unpurged owner may still be unable to log in -- and FR-013 asks whether an owner
    can *act*. Verified before that clause existed: disable A, re-enable A, disable B left an
    organization whose only remaining owner could not authenticate. A correlated `EXISTS` keeps
    external capability live from the local link table rather than a copied account flag.

    This mirrors `Account.can_authenticate` in SQL. Extracted because it is now evaluated in two
    places -- the unlocked count and the locked guard -- and two copies of a rule this sharp
    drift. `test_rca001_final_owner.py` asserts the SQL and the Python agree state by state.
    """
    external_identity_exists = (
        select(ExternalIdentityRow.account_id)
        .where(ExternalIdentityRow.account_id == AccountRow.account_id)
        .exists()
    )
    return (
        MembershipRow.role == OWNER_ROLE,
        AccountRow.disabled_at.is_(None),
        AccountRow.email.is_not(None),
        or_(AccountRow.credential_digest.is_not(None), external_identity_exists),
    )


def organization_owners_for_update(organization_id: str):
    """Lock one organization's owner-role memberships for the duration of the transaction.

    The sibling of `owner_memberships_for_update`, which locks by *account* because the disable
    path reduces ownership across every organization the account owns. Revocation and demotion
    touch one membership, so the contended set is one organization's owner rows -- and that is
    where the invariant lives, so that is what must be locked.

    Named at module level for the same reason as its sibling: SQLite emits no `FOR UPDATE` and
    SQLAlchemy silently omits it, so an inline lock could be deleted and leave the whole RCA
    suite green while `#155`'s defect class returned through the revoke path. A test compiles
    this against the PostgreSQL dialect and asserts `FOR UPDATE` is present.
    """
    return (
        select(MembershipRow)
        .where(
            MembershipRow.organization_id == organization_id,
            MembershipRow.role == OWNER_ROLE,
        )
        .with_for_update()
    )


def owner_memberships_for_update(account_id: str):
    """Lock every owner row of every organization this account owns, for the transaction.

    A named module-level statement rather than an inline `.with_for_update()`, following
    `khepri.rra.persistence.invitation_for_update_statement`. The reason is testability: SQLite
    emits no `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so if the lock were
    inline and someone later dropped it, the whole RCA suite would stay green while `#155`
    returned. Because this is a named function, a test compiles it against the PostgreSQL
    dialect and asserts `FOR UPDATE` is present without needing a database.

    **This locks the organizations' owner rows, not only this account's own.** It previously
    selected `WHERE account_id = A AND role = 'owner'`, which locked exactly one row per
    organization -- the account's own. Three callers disabling three *different* owners of one
    organization therefore locked three pairwise-disjoint single-row sets, so `FOR UPDATE` had
    nothing to block on: all three read "other effective owners exist", all three passed the
    guard, and all three committed, leaving zero. That is `#155` surviving on the disable path,
    and `test_concurrent_disablement_of_three_owners_leaves_one` was written for it and passed
    against it two runs in three. Measured at 4 failures in 12 against real PostgreSQL.

    A lock serializes only where row sets *intersect*, so the set has to be every row the count
    will read, not merely the row about to change.

    **The subquery and the lock are one statement, deliberately.** Reading the organization list
    and then locking it would reintroduce the same race one level up -- a concurrent write could
    add an owner membership between the two. In one statement PostgreSQL evaluates and locks at
    one snapshot, so a new membership either is not visible (and cannot affect the count being
    guarded) or blocks.

    **The order is fixed** so concurrent callers acquire rows in the same sequence. Two accounts
    each owning the same two organizations, disabled at once, would otherwise be free to lock in
    opposite orders and deadlock -- trading a correctness defect for an intermittent one that
    these tests would not reliably catch either.
    """
    owned_organizations = (
        select(MembershipRow.organization_id)
        .where(
            MembershipRow.account_id == account_id,
            MembershipRow.role == OWNER_ROLE,
        )
        .scalar_subquery()
    )
    return (
        select(MembershipRow)
        .where(
            MembershipRow.organization_id.in_(owned_organizations),
            MembershipRow.role == OWNER_ROLE,
        )
        .order_by(MembershipRow.organization_id, MembershipRow.account_id)
        .with_for_update()
    )


def owner_reduction_outcome(database, account_id: str) -> str:
    """Lock every affected owner set and decide whether losing this account would strand one."""
    locked = database.scalars(owner_memberships_for_update(account_id)).all()
    if database.get(AccountRow, account_id) is None:
        return OWNER_CHANGE_NOT_APPLICABLE
    owned_organizations = {
        row.organization_id for row in locked if row.account_id == account_id
    }
    for organization_id in sorted(owned_organizations):
        remaining = database.execute(
            select(func.count())
            .select_from(MembershipRow)
            .join(AccountRow, AccountRow.account_id == MembershipRow.account_id)
            .where(
                MembershipRow.organization_id == organization_id,
                MembershipRow.account_id != account_id,
                *_effective_owner_conditions(),
            )
        ).scalar()
        if not remaining:
            return OWNER_CHANGE_FINAL_OWNER
    return OWNER_CHANGE_APPLIED


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

        **`prior_role` is checked against the stored row, not against the caller's claim.** The
        event carries no foreign key, so these checks are the only thing between a caller and a
        false audit record -- and `prior_role` is the one `FR-014` field ("what the prior and
        resulting roles were") that a destination check alone leaves undefended. Reading it from
        the row inside the transaction also closes the service's read-then-write gap: if the
        role changed after the service read it, the event's `prior_role` is stale and describes
        a transition that did not happen, so the write refuses instead of recording it.
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
                if event.prior_role != row.role:
                    return False
                row.role = membership.role
                database.add(_event_row(event))
        except IntegrityError:
            return False
        return True

    def _purge_expired_events(self, horizon: datetime) -> int:
        """Delete every `FR-014` event at or before `horizon`, returning how many went.

        **The only place production removes a membership event**, which `R2-07`'s source audit
        enforces by name rather than by convention. Called solely by `MembershipEventSweeper`, which
        owns the horizon arithmetic; passing the horizon in rather than the retention months keeps
        the calendar reasoning in one module.

        **One statement, no prior select.** Events are append-only and `occurred_at` never changes,
        so there is no window in which a selected row stops qualifying — the re-check the account
        purge needs has nothing to guard against here. `occurred_at` is indexed for this predicate.

        **`<=`, matching `MembershipEvent.is_purgeable_at`.** The horizon instant itself qualifies;
        the domain method and this query must agree on the boundary or the same event would be
        purgeable in one and retained in the other.
        """
        with self._factory.begin() as database:
            purged = database.execute(
                delete(MembershipEventRow).where(MembershipEventRow.occurred_at <= horizon)
            )
        return purged.rowcount

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
            outcome = owner_reduction_outcome(database, account_id)
            if outcome != OWNER_CHANGE_APPLIED:
                return outcome
            if not _apply_account(database, updated):
                return OWNER_CHANGE_NOT_APPLICABLE
        return OWNER_CHANGE_APPLIED

    def revoke_membership(
        self,
        organization_id: str,
        account_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> str:
        """Delete one membership and record its revocation, guarding FR-013 (`FR-012`).

        **The same lock-count-write shape as `apply_owner_reducing_change`, not a second
        guard.** The roadmap's stop condition names "two independent final-owner guards"
        explicitly, and this is the sibling `R1-02` §6 anticipated: the outcome vocabulary is
        about ownership rather than accounts, so it transfers unchanged. What differs is only
        what is locked and what is written -- one organization's owner rows rather than one
        account's, and a deleted row rather than a saved account.

        **The event is built here rather than by the caller.** `prior_role` must be the role the
        row actually held, and only this transaction can read that without a race: a role that
        changed after the service read it would make a caller-supplied prior role describe a
        transition that did not happen, and the event has no foreign key to contradict it. The
        same defect was fixed in `promote_membership`.

        **The deletion and the event commit together.** `KHEPRI-DEC-015` retains the membership
        "only as the subject of the `FR-014` audit event", so the event must outlive the row --
        which is why `MembershipEventRow` carries no foreign key onto `rca_memberships`. An
        event written outside this transaction could describe a revocation that rolled back,
        and a deletion without its event is an unattributed membership change.

        No door opens here, following `apply_owner_reducing_change`: a round trip under
        `FOR UPDATE` can block on another transaction's lock, which is a far wider grant than
        the single constructor call `records.py` scopes doors to.
        """

        def revoke(database, row: MembershipRow) -> MembershipEvent:
            event = MembershipEvent.revoked(
                organization_id,
                account_id,
                prior_role=row.role,
                actor_account_id=actor_account_id,
                now=now,
            )
            # `FR-020` and `KHEPRI-DEC-015` §2's fourth end trigger (`R4-06`), inside this
            # transaction with the deletion and the event.
            #
            # **In this callback rather than in `_apply_membership_change`'s body**, and the
            # placement is load-bearing: `demote_membership` delegates to the same helper, so a
            # cascade in the helper would invalidate a *demoted* member's invitations, which
            # `R4-01` §8.3 settles it must not. The callback is per-verb, so revocation scoping is
            # by construction rather than by a guard someone can drop.
            #
            # **Both anchors, and the recipient one is not optional.** §7's counter-example: a
            # person holding two invitations to this organization redeems one, is revoked, and
            # redeems the second to rejoin immediately -- untouched by an `issued_by`-only
            # cascade, because that column names the owner who sent it.
            #
            # The address is read inside this transaction, and `None` when the addressee's account
            # is already a tombstone (`KHEPRI-DEC-015` §2b). The issuer half still runs then: it
            # keys on `account_id`, which the tombstone retains, so an unresolvable address must
            # not abort a trigger the decision governs.
            addressee = database.get(AccountRow, account_id)
            _cascade_invitations(
                database,
                organization_id=organization_id,
                target_identity=None if addressee is None else addressee.email,
                issued_by=account_id,
                now=now,
            )
            database.delete(row)
            return event

        return self._apply_membership_change(organization_id, account_id, revoke)

    def demote_membership(
        self,
        organization_id: str,
        account_id: str,
        *,
        actor_account_id: str,
        now: datetime,
    ) -> str:
        """Lower one owner to member, guarding FR-013 (`FR-013` "downgrade", `FR-015`).

        **The third caller of one guard, not a third guard.** `FR-013` names remove, downgrade,
        and disable; disable goes through `apply_owner_reducing_change`, and remove and downgrade
        share `_apply_membership_change` below. The roadmap's stop condition forbids two
        independent final-owner guards, and the way to honour it with three operations is for the
        owner-reducing ones to differ only in the write they hand over.

        Unlike `promote_membership`, this locks. Promotion raises the owner count and has no
        guard to invalidate; demotion lowers it, so the count it acts on must be read under the
        same lock the write commits behind.
        """

        def demote(database, row: MembershipRow) -> MembershipEvent:
            event = MembershipEvent.role_changed(
                organization_id,
                account_id,
                prior_role=row.role,
                next_role=MEMBER_ROLE,
                actor_account_id=actor_account_id,
                now=now,
            )
            row.role = MEMBER_ROLE
            return event

        return self._apply_membership_change(organization_id, account_id, demote)

    def _apply_membership_change(self, organization_id: str, account_id: str, write) -> str:
        """Lock this organization's owners, refuse if the change would strand it, else write.

        The shared body of every owner-reducing change to a *membership* -- revocation and
        demotion today. `write` receives the session and the locked row and returns the
        `FR-014` event describing what it did, so the two operations differ only in that
        callback and the guard exists once.

        **Why the count runs inside this transaction on locked rows.** `#155` was two callers
        each reading a live co-owner, each passing, and both committing, leaving zero. The
        `FOR UPDATE` above blocks a competing owner-reducing operation on this organization at
        its own `SELECT` until this commits, so it observes this write rather than the state
        that preceded it. `R1` proved a two-thread test cannot establish this on its own; the
        three-contender and mixed revoke/demote proofs are in
        `tests/test_rca001_concurrent_final_owner.py`.

        The event is returned by the callback rather than passed in because `prior_role` must be
        the role the locked row actually held. A caller-supplied value could describe a
        transition that did not happen, and the event carries no foreign key to contradict it.

        **Why this serializes against `apply_owner_reducing_change`, which locks differently.**
        That method locks `WHERE account_id = A AND role = 'owner'`, because disabling one
        account reduces ownership in every organization it owns; this one locks
        `WHERE organization_id = O AND role = 'owner'`, because revoking or demoting touches one
        organization. Those row sets intersect on exactly `{(O, A)}`, and only when `A` holds an
        owner row in `O`.

        That is the definition of contention here rather than a coincidence: two owner-reducing
        operations can affect the same organization's owner count **only if** the disabled
        account is itself an owner of that organization -- in which case its row is in both
        predicates and the two block on each other. When the sets are disjoint neither operation
        can change the other's count, so serializing them would be contention with no invariant
        behind it. Both directions are tested: the mixed-race test proves the dangerous one and
        `test_the_two_lock_predicates_intersect_on_every_contended_organization` the wasteful one.
        """
        with self._factory.begin() as database:
            owners = database.scalars(organization_owners_for_update(organization_id)).all()
            row = database.get(MembershipRow, (organization_id, account_id))
            if row is None:
                return OWNER_CHANGE_NOT_APPLICABLE
            if any(owner.account_id == account_id for owner in owners):
                remaining = database.execute(
                    select(func.count())
                    .select_from(MembershipRow)
                    .join(AccountRow, AccountRow.account_id == MembershipRow.account_id)
                    .where(
                        MembershipRow.organization_id == organization_id,
                        MembershipRow.account_id != account_id,
                        *_effective_owner_conditions(),
                    )
                ).scalar()
                if not remaining:
                    return OWNER_CHANGE_FINAL_OWNER
            event = write(database, row)
            database.flush()
            database.add(_event_row(event))
        return OWNER_CHANGE_APPLIED
