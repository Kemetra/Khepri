"""R3-07: session records are swept; sweeping is never what ends authority.

**The distinction this suite exists to hold.** `KHEPRI-DEC-015` retains an authentication session
"until expiry or revocation… the record may persist only until purged; it authorizes nothing from
the trigger instant", and **retention never delays revocation**. So the sweeper purges *records*.
What stops a session authorizing is `R3-04`'s read path, which refuses a dead row on sight.

That separation is testable: `test_a_revoked_session_stops_authorizing_before_any_sweep` proves
authority ends with no sweep at all, and the horizon tests prove the row survives its own death
until swept. If a future edit made authorization depend on the sweeper having run, the first test
fails.

**Not a scheduler.** One pass when called, following `khepri.local.sweeper` and
`AccountRetentionSweeper`. A loop inventing a cadence here would model a deployment nobody has
authorized.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.session_persistence import SqlSessionStore
from khepri.rca.session_retention import (
    SESSION_RETENTION_DAYS,
    SessionRetentionSweeper,
    SessionSweepReport,
)
from khepri.rca.session_service import SessionService
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    NOW,
    OTHER_EMAIL,
    factory_fixture,
)

LIFETIME = timedelta(hours=12)
BEYOND = timedelta(days=SESSION_RETENTION_DAYS) + timedelta(seconds=1)


def _account(factory: sessionmaker, email: str = EMAIL) -> str:
    return AccountService(SqlAccountStore(factory)).create_account(email, CREDENTIAL).account_id


def _sessions(factory: sessionmaker) -> SessionService:
    return SessionService(SqlSessionStore(factory), lifetime=LIFETIME)


def _sweeper(factory: sessionmaker) -> SessionRetentionSweeper:
    return SessionRetentionSweeper(SqlSessionStore(factory))


class TestRetentionNeverDelaysRevocation:
    def test_a_revoked_session_stops_authorizing_before_any_sweep(
        self, factory: sessionmaker
    ) -> None:
        """`KHEPRI-DEC-015`: "it authorizes nothing from the trigger instant".

        The row still exists — nothing has swept — and it already refuses. This is the property
        that makes the sweeper a retention mechanism rather than a security one.
        """
        from khepri.rca.errors import AuthenticationFailed

        sessions = _sessions(factory)
        token = sessions.create(_account(factory), now=NOW)
        sessions.revoke(token, now=NOW)

        assert SqlSessionStore(factory).get_session_count() == 1
        with pytest.raises(AuthenticationFailed):
            sessions.resolve(token, now=NOW)

    def test_an_expired_session_stops_authorizing_before_any_sweep(
        self, factory: sessionmaker
    ) -> None:
        from khepri.rca.errors import AuthenticationFailed

        sessions = _sessions(factory)
        token = sessions.create(_account(factory), now=NOW)
        assert SqlSessionStore(factory).get_session_count() == 1
        with pytest.raises(AuthenticationFailed):
            sessions.resolve(token, now=NOW + LIFETIME)


class TestTheHorizon:
    def test_a_live_session_is_never_swept(self, factory: sessionmaker) -> None:
        sessions = _sessions(factory)
        sessions.create(_account(factory), now=NOW)
        assert _sweeper(factory).sweep(now=NOW).purged_sessions == 0
        assert SqlSessionStore(factory).get_session_count() == 1

    def test_a_session_inside_the_horizon_is_kept(self, factory: sessionmaker) -> None:
        """Dead but retained. The record outlives its authority deliberately."""
        sessions = _sessions(factory)
        sessions.create(_account(factory), now=NOW)
        moment = NOW + LIFETIME + timedelta(days=1)
        assert _sweeper(factory).sweep(now=moment).purged_sessions == 0
        assert SqlSessionStore(factory).get_session_count() == 1

    def test_an_expired_session_past_the_horizon_is_purged(
        self, factory: sessionmaker
    ) -> None:
        sessions = _sessions(factory)
        sessions.create(_account(factory), now=NOW)
        assert _sweeper(factory).sweep(now=NOW + LIFETIME + BEYOND).purged_sessions == 1
        assert SqlSessionStore(factory).get_session_count() == 0

    def test_a_revoked_session_past_the_horizon_is_purged(
        self, factory: sessionmaker
    ) -> None:
        """The horizon runs from revocation, not from expiry, for a revoked session.

        Otherwise revoking a long-lived session early would keep its row for the remainder of the
        original horizon plus the retention window -- retention measured from an instant that
        stopped being meaningful the moment it was revoked.
        """
        sessions = _sessions(factory)
        token = sessions.create(_account(factory), now=NOW)
        sessions.revoke(token, now=NOW)
        assert _sweeper(factory).sweep(now=NOW + BEYOND).purged_sessions == 1
        assert SqlSessionStore(factory).get_session_count() == 0

    def test_the_horizon_boundary_is_closed(self, factory: sessionmaker) -> None:
        """Exactly at the horizon counts as elapsed, matching `is_expired_at` and
        `MembershipEvent.is_purgeable_at`. A boundary excluded here would leave a one-instant
        window where a record is neither retained nor purgeable."""
        sessions = _sessions(factory)
        sessions.create(_account(factory), now=NOW)
        moment = NOW + LIFETIME + timedelta(days=SESSION_RETENTION_DAYS)
        assert _sweeper(factory).sweep(now=moment).purged_sessions == 1

    def test_one_instant_before_the_horizon_is_kept(self, factory: sessionmaker) -> None:
        """The other half of the boundary, so the predicate cannot be always-true."""
        sessions = _sessions(factory)
        sessions.create(_account(factory), now=NOW)
        moment = (
            NOW + LIFETIME + timedelta(days=SESSION_RETENTION_DAYS) - timedelta(microseconds=1)
        )
        assert _sweeper(factory).sweep(now=moment).purged_sessions == 0


class TestTheReport:
    def test_the_report_is_counts_only(self, factory: sessionmaker) -> None:
        """`FR-040`: no identifier is echoed. The account and session identifiers of a purged
        row must not survive in the object describing the purge."""
        sessions = _sessions(factory)
        account = _account(factory)
        token = sessions.create(account, now=NOW)
        report = _sweeper(factory).sweep(now=NOW + LIFETIME + BEYOND)
        rendered = repr(report)
        assert account not in rendered
        assert token not in rendered

    def test_the_report_is_frozen(self, factory: sessionmaker) -> None:
        report = _sweeper(factory).sweep(now=NOW)
        with pytest.raises(AttributeError):
            report.purged_sessions = 99  # type: ignore[misc]

    def test_a_pass_over_nothing_reports_zero(self, factory: sessionmaker) -> None:
        assert _sweeper(factory).sweep(now=NOW) == SessionSweepReport(purged_sessions=0)


class TestSelectivity:
    def test_only_the_dead_are_purged(self, factory: sessionmaker) -> None:
        """A live session for another account survives a pass that purges a dead one."""
        sessions = _sessions(factory)
        old = sessions.create(_account(factory), now=NOW)
        moment = NOW + LIFETIME + BEYOND
        live = sessions.create(_account(factory, OTHER_EMAIL), now=moment)

        assert _sweeper(factory).sweep(now=moment).purged_sessions == 1
        assert sessions.resolve(live, now=moment) is not None
        from khepri.rca.errors import AuthenticationFailed

        with pytest.raises(AuthenticationFailed):
            sessions.resolve(old, now=moment)

    def test_the_horizon_is_not_rra_content_retention(self) -> None:
        """`R3-01` §7 says explicitly: do not copy RRA's 7 days.

        That is an `RRA-002` content rule, not an auth-session horizon. Asserting the number here
        makes an accidental re-alignment a test failure rather than a silent policy change.
        """
        assert SESSION_RETENTION_DAYS != 7
