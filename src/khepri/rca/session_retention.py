"""Session records are swept; sweeping is never what ends authority (`R3-07`).

**The distinction this module has to hold.** `KHEPRI-DEC-015` retains an authentication session
"until expiry or revocation… the record may persist only until purged; it authorizes nothing from
the trigger instant", and **retention never delays revocation**. So this purges *records*. What
stops a session authorizing is `R3-04`'s read path, which refuses a dead row on sight — before any
sweep, and whether or not one ever runs.

That ordering makes the sweeper a storage-reclamation mechanism rather than a security one, which
is why nothing in the authorization path depends on it having run.

**Not a scheduler**, following `khepri.local.sweeper` and `AccountRetentionSweeper`: one pass when
called. Choosing a cadence is an operational decision, and a loop inventing one here would model a
deployment nobody has authorized. It plugs into `LocalSweeper` through `RetentionPasses` for the
reason recorded there: a retention rule whose only caller does not exist is indefinite retention
with a policy comment on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from khepri.rca.session_persistence import SqlSessionStore

#: Days a dead session record is kept before purging.
#:
#: **Deliberately not RRA's 7 days.** `R3-01` §7 says so explicitly: that is an `RRA-002` content
#: retention rule, not an authentication-session horizon, and the two are unrelated policies that
#: would only look consistent by coincidence.
#:
#: `KHEPRI-DEC-015` bounds this no further than "until expiry or revocation", so the horizon is
#: R3's to propose. Thirty days is chosen to sit under §2a's twelve-month audit horizon by a wide
#: margin — a session record is an operational artifact, not audit evidence, and
#: `rca_membership_events` is what answers "what happened to this membership" long after the fact.
SESSION_RETENTION_DAYS = 30


@dataclass(frozen=True, slots=True)
class SessionSweepReport:
    """What one pass did, in counts only. No identifier is echoed (`FR-040`).

    Frozen and count-bearing for the same reason as `PurgeReport`: a report naming the sessions it
    purged would reintroduce, in the audit trail, exactly the identifiers the purge exists to
    remove.
    """

    purged_sessions: int


class SessionRetentionSweeper:
    """Purges session records whose retention horizon has elapsed.

    **Why a sweeper rather than lazy deletion on read.** A session nobody presents is a session
    never read, so under lazy deletion its row would persist indefinitely — and the rows that are
    never read again are precisely the abandoned ones this horizon exists to bound. The same
    reasoning `AccountRetentionSweeper` records for `KHEPRI-DEC-015` §2b.
    """

    def __init__(
        self, sessions: SqlSessionStore, *, retention_days: int = SESSION_RETENTION_DAYS
    ) -> None:
        self._sessions = sessions
        self._retention_days = retention_days

    def sweep(self, *, now: datetime) -> SessionSweepReport:
        """Purge every session dead longer than the horizon.

        The horizon is measured from the instant the session died — `revoked_at` where it was
        revoked, `expires_at` otherwise — so a session revoked early does not linger for the
        remainder of a lifetime it never used.

        **No account or membership check.** A session references an account, but purging the
        session changes no authority: it stopped authorizing when it died, and `FR-013`'s owner
        count reads memberships rather than sessions. A guard here would refuse nothing that was
        not already refused, while implying this path protects an invariant it does not.
        """
        horizon = now - timedelta(days=self._retention_days)
        return SessionSweepReport(
            purged_sessions=self._sessions.purge_sessions_dead_before(horizon)
        )


__all__ = [
    "SESSION_RETENTION_DAYS",
    "SessionRetentionSweeper",
    "SessionSweepReport",
]
