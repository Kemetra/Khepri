"""Persistence for commercial sessions and external-identity links (`R3-03`).

**Its own module rather than more of `persistence.py`.** That file holds the account, organization,
and membership stores and had grown past the point where a fourth unrelated store belonged in it --
CodeScene flagged it at 709 lines against a 600 threshold, and the fix it prompted is the one this
repository's own standard already asks for. The `Base` metadata stays shared, so `SessionRow` and
`ExternalIdentityRow` remain declared beside the tables they reference; only the store moves.

**Both concerns live here together**, because they are one job: resolving a request to an actor. A
link answers "which account is this provider subject", a session answers "which account holds this
cookie", and `R3-04` needs both to authenticate one request.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.errors import (
    OWNER_CHANGE_APPLIED,
    OWNER_CHANGE_FINAL_OWNER,
    OWNER_CHANGE_NOT_APPLICABLE,
)
from khepri.rca.persistence import (
    AccountRow,
    ExternalIdentityRow,
    SessionRow,
    _utc,
    owner_reduction_outcome,
)
from khepri.rca.records import assert_sealed
from khepri.rca.sessions import Session, StoredSession


def _session_from_row(row: SessionRow) -> Session:
    return Session._from_storage(
        StoredSession(
            session_id_hash=row.session_id_hash,
            account_id=row.account_id,
            active_organization_id=row.active_organization_id,
            created_at=_utc(row.created_at),
            expires_at=_utc(row.expires_at),
            revoked_at=_utc(row.revoked_at),
        )
    )


def _loses_authentication_capability(has_local_verifier: bool, another_link) -> bool:
    return not has_local_verifier and another_link is None


class SqlSessionStore:
    """Persistence for commercial sessions and external-identity links (`R3-03`).

    **Both live here rather than in two stores**, because they are one concern: resolving a request
    to an actor. A link answers "which account is this provider subject", a session answers "which
    account holds this cookie", and `R3-04` needs both to authenticate one request.

    **Timestamps are normalized to UTC on read.** SQLite drops `tzinfo`, so a naive `expires_at`
    would compare wrongly against an aware `now` and silently mis-decide expiry -- the one thing the
    column exists to decide. `_utc` is the same helper the account path already uses.
    """

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def add_session(self, session: Session) -> bool:
        """Write a newly issued session. Returns False if the identifier is already present."""
        assert_sealed(session)
        with self._factory.begin() as database:
            if database.get(SessionRow, session.session_id_hash) is not None:
                return False
            database.add(
                SessionRow(
                    session_id_hash=session.session_id_hash,
                    account_id=session.account_id,
                    active_organization_id=session.active_organization_id,
                    created_at=session.created_at,
                    expires_at=session.expires_at,
                    revoked_at=session.revoked_at,
                )
            )
        return True

    def get_session(self, session_id_hash: str) -> Session | None:
        """Resolve a session by the hash of the presented token.

        Returns the record whatever its state -- expired and revoked sessions come back, and the
        caller decides. `R3-04` needs the distinction: an expired session and an absent one produce
        the same uniform refusal externally (`FR-004`), but only one of them is worth sweeping.
        """
        with self._factory() as database:
            row = database.get(SessionRow, session_id_hash)
            return None if row is None else _session_from_row(row)

    def save_session(self, session: Session) -> bool:
        """Write a session's current state back. Returns False if the row has gone."""
        assert_sealed(session)
        with self._factory.begin() as database:
            row = database.get(SessionRow, session.session_id_hash)
            if row is None:
                return False
            row.active_organization_id = session.active_organization_id
            row.revoked_at = session.revoked_at
        return True

    def revoke_all_for_account(self, account_id: str, *, now: datetime) -> int:
        """Revoke every live session for one account (`FR-007`, `FR-008`).

        **The requirement that made Khepri hold its own sessions at all.** `FR-007` requires
        recovery to invalidate *every* pre-existing session, which is unsatisfiable over a bearer
        token Khepri can neither enumerate nor revoke (`R3-09` Â§2).

        **Already-revoked rows are left alone rather than re-stamped.** `revoked_at` records when
        authority actually ended; moving it would misreport that, which is the same reason
        `Session.revoked` refuses a second revocation. The returned count is rows actually changed.

        One statement: the predicate selects and the update writes together, so a session issued
        between a select and a write cannot slip through the gap.
        """
        with self._factory.begin() as database:
            revoked = database.execute(
                update(SessionRow)
                .where(
                    SessionRow.account_id == account_id,
                    SessionRow.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        return revoked.rowcount

    def revoke_all_for_provider(self, provider: str, *, now: datetime) -> int:
        """Revoke every live session for every account linked to one provider.

        Khepri sessions deliberately carry no provider provenance, so the fail-closed affected
        set at a provider hard stop is every session belonging to an account with that provider's
        link. One statement selects and updates that set; a dual-capability account may be logged
        out conservatively, while an unrelated account cannot be touched.
        """
        linked_accounts = select(ExternalIdentityRow.account_id).where(
            ExternalIdentityRow.provider == provider
        )
        with self._factory.begin() as database:
            revoked = database.execute(
                update(SessionRow)
                .where(
                    SessionRow.account_id.in_(linked_accounts),
                    SessionRow.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
        return revoked.rowcount

    def purge_sessions_dead_before(self, horizon: datetime) -> int:
        """Delete every session whose retention horizon has elapsed (`R3-07`).

        **A session's retention clock starts when it died, not when it was issued.** For an
        expired session that is `expires_at`; for a revoked one it is `revoked_at`, which may be
        much earlier. Measuring both from `expires_at` would keep a session revoked on its first
        day for the remainder of its original horizon -- retention counted from an instant that
        stopped being meaningful the moment it was revoked.

        A revoked session uses `revoked_at` even when `expires_at` is later, so the two predicates
        are `OR`-ed rather than combined: dead by either route, long enough ago.

        **Deleting a row is never what ends authority.** `KHEPRI-DEC-015` retains a session record
        "only until purged; it authorizes nothing from the trigger instant", so `resolve` has
        already refused these rows for as long as they have been dead. This reclaims storage.
        """
        with self._factory.begin() as database:
            deleted = database.execute(
                delete(SessionRow).where(
                    or_(
                        SessionRow.revoked_at <= horizon,
                        and_(SessionRow.revoked_at.is_(None), SessionRow.expires_at <= horizon),
                    )
                )
            )
        return deleted.rowcount

    def get_session_count(self) -> int:
        """How many session rows exist, in any state. For retention evidence only."""
        with self._factory() as database:
            return database.execute(select(func.count()).select_from(SessionRow)).scalar_one()

    def link_external_identity(
        self, provider: str, provider_subject: str, account_id: str, *, now: datetime
    ) -> bool:
        """Link one verified provider subject to one account (`KHEPRI-DEC-018` Â§7).

        Returns False if the identity is already linked -- refused rather than re-pointed, because
        "re-pointing a link is account takeover" (Â§7). The composite primary key enforces the same
        rule against a caller that reaches the row directly, so this check is the courteous path
        rather than the guarantee.
        """
        try:
            with self._factory.begin() as database:
                existing = database.get(ExternalIdentityRow, (provider, provider_subject))
                if existing is not None:
                    return False
                database.add(
                    ExternalIdentityRow(
                        provider=provider,
                        provider_subject=provider_subject,
                        account_id=account_id,
                        linked_at=now,
                    )
                )
        except IntegrityError:
            return False
        return True

    def account_for_external_identity(
        self, provider: str, provider_subject: str
    ) -> str | None:
        """The local resolution `R3-09` Â§2.1 depends on: no provider call, one indexed lookup."""
        with self._factory() as database:
            row = database.get(ExternalIdentityRow, (provider, provider_subject))
            return None if row is None else row.account_id

    def unlink_external_identity(self, provider: str, provider_subject: str) -> bool:
        return (
            self.unlink_external_identity_outcome(provider, provider_subject)
            == OWNER_CHANGE_APPLIED
        )

    def unlink_external_identity_outcome(self, provider: str, provider_subject: str) -> str:
        """Remove a link, leaving every other record standing (`KHEPRI-DEC-018` Â§7).

        The account, memberships, and audit events survive. If this is the account's final
        authentication capability, the shared locked owner-reduction decision refuses a change
        that would strand an organization.
        """
        with self._factory.begin() as database:
            row = database.get(ExternalIdentityRow, (provider, provider_subject))
            if row is None:
                return OWNER_CHANGE_NOT_APPLICABLE
            outcome = owner_reduction_outcome(database, row.account_id)
            account = database.get(AccountRow, row.account_id)
            another_link = database.execute(
                select(ExternalIdentityRow.account_id).where(
                    ExternalIdentityRow.account_id == row.account_id,
                    or_(
                        ExternalIdentityRow.provider != provider,
                        ExternalIdentityRow.provider_subject != provider_subject,
                    ),
                )
            ).first()
            has_local_verifier = account is not None and account.credential_digest is not None
            loses_capability = _loses_authentication_capability(
                has_local_verifier, another_link
            )
            if loses_capability and outcome == OWNER_CHANGE_FINAL_OWNER:
                return outcome
            database.delete(row)
        return OWNER_CHANGE_APPLIED


__all__ = ["SqlSessionStore"]
