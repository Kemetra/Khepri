"""Persistence for organization invitations (`R4-03`).

**Its own module rather than more of `persistence.py`**, following the `R3-03` split recorded in
`session_persistence.py:1-12`: that file was moved out when CodeScene flagged `persistence.py`
at 709 lines against a 600 threshold, and it is larger now. The `Base` metadata stays shared, so
`InvitationRow` remains declared beside the table it references; only the store moves.

**Scope.** The store, the destroy-on-touch read path, and the retention sweep. Issuance and
revocation services are `R4-04`; the `FR-020` and purge cascades are `R4-06`; redemption and its
uniform-failure path are `R4-05`. Nothing here decides who may invite whom.

## Two things this module does that a plain store would not

**Reads destroy.** `KHEPRI-DEC-015` §5 requires an expired verifier's *bytes* not to survive -- it
measures the harm in days of survival -- and expiry fires no event, so nothing happens at the
horizon unless a read makes it happen. `find_for_redemption` therefore destroys the verifier of an
expired invitation in the same transaction that reads it, before refusing. This costs nothing on a
read that was already occurring and closes the case that matters most: an expired invitation someone
is actively presenting is exactly the one whose verifier should not still be there.

**The purge predicate is evaluated in the deleting statement**, not selected and then deleted.
`_purge_expired_events`' bare-DELETE shape is safe only because events are append-only; invitations
are not, so a row could be redeemed between a select and a delete. `R4-01` §3 requires the predicate
inline for that reason.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.credentials import KdfParams, Verifier
from khepri.rca.invitations import (
    Invitation,
    InvitationLifecycle,
    InvitationOffer,
    StoredInvitationSecret,
)
from khepri.rca.persistence import InvitationRow, _canonical_or_none, _utc
from khepri.rca.records import assert_sealed


def _verifier_from_row(row: InvitationRow) -> Verifier | None:
    """None once the verifier has been destroyed -- on acceptance, revocation, or expiry.

    Treats the five columns as one value, matching `persistence.py`'s account-side helper and the
    `ck_rca_invitation_verifier_whole` constraint: a row is either a complete verifier or none
    at all. A partially-populated row is not a verifier missing a piece; it is a record that cannot
    be verified, and admitting it would let a half-destroyed row look live.
    """
    stored = (row.secret_salt, row.secret_digest, row.kdf_n, row.kdf_r, row.kdf_p)
    if any(part is None for part in stored):
        return None
    salt, digest, n, r, p = stored
    return Verifier._from_storage(salt=salt, digest=digest, kdf=KdfParams(n=n, r=r, p=p))


def _invitation_from_row(row: InvitationRow) -> Invitation:
    """Rebuild the record from its row, through the reconstruction door.

    Timestamps go through `_utc`: SQLite drops `tzinfo`, so a naive `expires_at` would compare
    wrongly against an aware `now` and silently mis-decide expiry -- the one thing the column exists
    to decide.
    """
    expires_at = _utc(row.expires_at)
    issued_at = _utc(row.issued_at)
    assert expires_at is not None and issued_at is not None  # NOT NULL columns
    return Invitation._from_storage(
        InvitationOffer(
            organization_id=row.organization_id,
            intended_role=row.intended_role,
            target_identity=row.target_identity,
            issued_by=row.issued_by,
        ),
        StoredInvitationSecret(
            invitation_id=row.invitation_id,
            verifier=_verifier_from_row(row),
            expires_at=expires_at,
        ),
        issued_at=issued_at,
        lifecycle=InvitationLifecycle(
            redeemed_at=_utc(row.redeemed_at),
            revoked_at=_utc(row.revoked_at),
        ),
    )


def _expired(row: InvitationRow, now: datetime) -> bool:
    """`expires_at <= now`, on the row rather than the record.

    One spelling of the boundary for every read path, matching `Invitation.is_expired_at`. The
    instant itself counts as expired; a `<` here would leave a one-instant window in which a read
    hands back a verifier the domain already considers spent.
    """
    stored = _utc(row.expires_at)
    assert stored is not None  # NOT NULL column
    return stored <= now


def _destroy_verifier(row: InvitationRow) -> None:
    """Null all five verifier columns together.

    One helper rather than five assignments at each of three call sites, because "cannot be
    destroyed by halves" is the invariant, and a call site that set four of five would satisfy
    every test that checks the digest is gone.
    """
    row.secret_salt = None
    row.secret_digest = None
    row.kdf_n = None
    row.kdf_r = None
    row.kdf_p = None


class SqlInvitationStore:
    """Persistence for organization invitations (`R4-03`).

    Timestamps are normalized to UTC on read; see `_invitation_from_row`.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def add_invitation(self, invitation: Invitation) -> bool:
        """Write a newly issued invitation. Returns False if the identifier is already present.

        `target_identity` is canonicalized here as well as by `R4-04`'s service, because a store
        caller that bypassed the service would otherwise write a raw address, and the addressee
        check, the recipient cascade, and the purge cascade would all then fail to match it.
        `R4-01` §4 requires both.
        """
        assert_sealed(invitation)
        verifier = invitation.verifier
        if verifier is not None:
            assert_sealed(verifier)
        with self._factory.begin() as database:
            if database.get(InvitationRow, invitation.invitation_id) is not None:
                return False
            database.add(
                InvitationRow(
                    invitation_id=invitation.invitation_id,
                    organization_id=invitation.organization_id,
                    intended_role=invitation.intended_role,
                    target_identity=_canonical_or_none(invitation.target_identity),
                    secret_salt=None if verifier is None else verifier.salt,
                    secret_digest=None if verifier is None else verifier.digest,
                    kdf_n=None if verifier is None else verifier.kdf.n,
                    kdf_r=None if verifier is None else verifier.kdf.r,
                    kdf_p=None if verifier is None else verifier.kdf.p,
                    expires_at=invitation.expires_at,
                    issued_by=invitation.issued_by,
                    issued_at=invitation.issued_at,
                    redeemed_at=invitation.redeemed_at,
                    revoked_at=invitation.revoked_at,
                )
            )
            try:
                database.flush()
            except IntegrityError:
                return False
        return True

    def get_invitation(self, invitation_id: str, *, now: datetime) -> Invitation | None:
        """Read one invitation, destroying its verifier first if the horizon has passed.

        **Every read is expiry-aware, and an earlier version of this store had only one that was.**
        That version documented this method as deliberately non-destroying, so `R4-04`'s revocation
        path and the tests could observe stored bytes unambiguously. Review on `#217` traced where
        that leads: a revocation attempted *after* expiry reads the verifier here, then
        `Invitation.revoked` refuses because the invitation has expired, so nothing saves and
        nothing destroys. With no scheduled sweeper -- see `invitation_retention.py` -- those bytes
        survive indefinitely, which `KHEPRI-DEC-015` §5 forbids in exactly the terms it uses:
        "every day it survives is unjustified risk".

        Test convenience was the wrong thing to weigh against that. A test needing to observe an
        undestroyed verifier reads the row, not the record.
        """
        return self._read_destroying_expired(invitation_id, now=now)

    def _read_destroying_expired(self, invitation_id: str, *, now: datetime) -> Invitation | None:
        """The one read shape: load, destroy if expired, return.

        Both public single-row reads route through this rather than each implementing the rule,
        because a second implementation is how one of them ends up not destroying -- which is the
        defect `#217` found.
        """
        with self._factory.begin() as database:
            row = database.get(InvitationRow, invitation_id)
            if row is None:
                return None
            if _expired(row, now):
                _destroy_verifier(row)
            return _invitation_from_row(row)

    def find_for_redemption(self, invitation_id: str, *, now: datetime) -> Invitation | None:
        """Read an invitation, destroying its verifier first if the horizon has passed.

        This is `R4-01` §3's destroy-on-first-touch mechanism. Expiry is not a write -- it is
        `expires_at <= now`, a derived state with no column and no event -- so an expired verifier's
        bytes survive until something looks at the row. `KHEPRI-DEC-015` §5 measures that
        survival in days and forbids it, so the read does the destroying.

        The returned record already carries `verifier=None`, so a caller cannot verify a
        secret against a verifier this call has just destroyed. Refusing is still the caller's job:
        `FR-017`'s uniform failure and its timing discipline are `R4-05`'s, and a store that raised
        here would put one rule in two places.

        Identical to `get_invitation` since `#217` made every read expiry-aware. Both names are
        kept because they carry different obligations for their callers: a redeemer must not treat a
        `None` verifier as a reason to raise, and `R4-04`'s revoker must.
        """
        return self._read_destroying_expired(invitation_id, now=now)

    def save_invitation(self, invitation: Invitation) -> bool:
        """Persist a state change. Returns False if the row has gone.

        Writes the terminal timestamps and the verifier together, because the domain's transitions
        produce them together: `Invitation.redeemed` and `.revoked` both return a record whose
        verifier is `None`, and a store that wrote the timestamp while leaving the bytes would
        undo the destruction the record performed.

        **Not the at-most-once guarantee.** Two concurrent redeemers both reading an open invitation
        would both reach here. `R4-01` §6.2 assigns that control to `R4-05`, which takes a lock or a
        conditional update; this method is deliberately not it and does not pretend to be.
        """
        assert_sealed(invitation)
        with self._factory.begin() as database:
            row = database.get(InvitationRow, invitation.invitation_id)
            if row is None:
                return False
            row.redeemed_at = invitation.redeemed_at
            row.revoked_at = invitation.revoked_at
            verifier = invitation.verifier
            if verifier is None:
                _destroy_verifier(row)
            else:
                assert_sealed(verifier)
                row.secret_salt = verifier.salt
                row.secret_digest = verifier.digest
                row.kdf_n = verifier.kdf.n
                row.kdf_r = verifier.kdf.r
                row.kdf_p = verifier.kdf.p
        return True

    def invitations_for_organization(
        self, organization_id: str, *, now: datetime
    ) -> tuple[Invitation, ...]:
        """Every invitation an organization holds, in issuance order.

        Scoped by `organization_id` rather than returning all rows: `R4-01` §4.1 requires revocation
        be scoped by `(organization_id, invitation_id)` and never by identifier alone, and a listing
        that crossed organizations would be the enumeration oracle `FR-023` forbids.

        **Expiry-aware like the single-row reads** (`#217`). A listing is the path `R8-05`'s team
        screen will use, so it is the read most likely to touch a stale invitation nobody has
        presented -- the exact row the sweeper cannot reach without a schedule.
        """
        with self._factory.begin() as database:
            rows = database.scalars(
                select(InvitationRow)
                .where(InvitationRow.organization_id == organization_id)
                .order_by(InvitationRow.issued_at, InvitationRow.invitation_id)
            ).all()
            for row in rows:
                if _expired(row, now):
                    _destroy_verifier(row)
            # No explicit flush. `factory.begin()` commits on exit, which flushes the pending
            # updates -- verified by removing the flush and reading the row directly, which showed
            # the columns already NULL. A `touched` flag guarding a redundant flush read as
            # load-bearing while a mutant proved it was not, so it is gone rather than kept.
            return tuple(_invitation_from_row(row) for row in rows)

    def _purge_spent_invitations(self, horizon: datetime, *, now: datetime) -> int:
        """Delete invitations whose purpose has ended. Returns the number of rows removed.

        Underscore-prefixed, following `_purge_expired_events`: this is the retention sweep's entry
        point and not an operation any service may call. `R2-07`'s source audit reserved that
        spelling for exactly this.

        **Two lifecycle rules, not one horizon**, per `R4-01` §3's matrix of authorized purposes:

        - *Never redeemed, and expired or revoked* -- purged as soon as the verifier's purpose has
          ended. There is no interval in which such a row lingers with its `target_identity`
          retained: the same pass that would destroy the verifier deletes the row.
        - *Redeemed* -- retained only while it must still refuse replay and attribute the resulting
          membership, so it is purged once the `FR-014` `MembershipEvent` it produced is purged.
          `horizon` is that anchor, passed in by the sweeper.

        The predicate is evaluated **in the DELETE**, not selected then deleted. An invitation is
        not append-only: a row could be redeemed between a select and a delete, and the redeemed
        branch has a longer horizon than the expired one, so the two-statement shape could delete a
        row that had just become retainable.
        """
        with self._factory.begin() as database:
            spent_unredeemed = and_(
                InvitationRow.redeemed_at.is_(None),
                or_(
                    InvitationRow.revoked_at.is_not(None),
                    InvitationRow.expires_at <= now,
                ),
            )
            redeemed_past_horizon = and_(
                InvitationRow.redeemed_at.is_not(None),
                InvitationRow.redeemed_at <= horizon,
            )
            result = database.execute(
                delete(InvitationRow).where(or_(spent_unredeemed, redeemed_past_horizon))
            )
            return int(result.rowcount or 0)


__all__ = [
    "SqlInvitationStore",
]
