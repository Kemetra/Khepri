"""Invitation records are swept; sweeping is never what ends an invitation (`R4-03`).

**The distinction this module has to hold**, matching `session_retention.py`'s. What stops an
invitation being redeemable is `R4-05`'s read path, which refuses an expired, revoked, or already
redeemed one on sight -- before any sweep, and whether or not one ever runs. This purges *records*.

But unlike sessions, sweeping here is **not purely storage reclamation**, and that difference is the
reason this module exists rather than a horizon being added to an existing sweeper.
`KHEPRI-DEC-015` §5 requires a spent verifier's bytes not to survive -- "a used or expired verifier
has no remaining purpose and every day it survives is unjustified risk", which measures harm in
*duration*. Expiry fires no event, so an invitation nobody presents has no other mechanism that
reaches it: `find_for_redemption` destroys on touch, and this bounds the untouched rows. It is
therefore a retention control with a privacy obligation behind it, not a disk-space measure.

**Not a scheduler**, following `AccountRetentionSweeper`, `MembershipEventSweeper`, and
`SessionRetentionSweeper`: one pass when called. See the note below the imports, which records what
that means now that `W1-07b` has put a caller in the shipped image.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from khepri.rca.invitation_persistence import SqlInvitationStore
from khepri.rca.lifecycle import MEMBERSHIP_EVENT_RETENTION_MONTHS, _months_before

#: **The caller now exists; the cadence is still an operational decision.**
#:
#: `W1-07b` moved the composition into `khepri.runtime` and gave it a console script,
#: `khepri-retention-sweep`, which ships in the wheel -- so `RetentionPasses` is reachable from the
#: deployed image and this horizon is enforced when that command runs. Until then it was reached
#: only by `khepri.local.cli`, which the wheel excludes, and this module carried
#: `INVITATION_HORIZON_IS_UNENFORCED = True` to say so; `KHEPRI-DEC-033` §5 makes deleting that
#: flag part of the evidence that the gap closed.
#:
#: `R4-01` §8.1's obligation survives the flag and is restated here: *the cadence being an
#: operational decision must not be allowed to imply that somebody is choosing one.* Nothing in
#: this repository schedules the command. "One pass when called" now means "one pass when the
#: deployment invokes the command it has", which is a different sentence from the one this note
#: used to make and is still not "a scheduler exists".
#:
#: `tests/test_w107b_unenforced_flag.py` is what replaced the deleted flag's assertion: it scans
#: for any `*_IS_UNENFORCED` constant and asserts the deployed composition reaches every pass.


@dataclass(frozen=True, slots=True)
class InvitationSweepReport:
    """What one pass did, in counts only. No identifier is echoed (`FR-040`).

    Frozen and count-bearing for the same reason as `SessionSweepReport` and `PurgeReport`: a report
    naming the invitations it purged would reintroduce, in the audit trail, exactly the
    `target_identity` values the purge exists to remove. That is sharper here than for sessions --
    an invitation's identifier is opaque, but the row it names carried an email address.
    """

    purged_invitations: int


class InvitationRetentionSweeper:
    """Purges invitation records whose authorized purpose has ended.

    **Two lifecycle rules, not one number**, per `R4-01` §3's matrix of authorized purposes. The
    store holds the predicate; this class supplies the one anchor it cannot derive.

    - *Never redeemed, and expired or revoked* -- no horizon at all. The purpose ended when the
      verifier's did, so the row goes in the same pass. There is no interval in which such a row
      survives with its `target_identity` retained.
    - *Redeemed* -- retained only while it must still refuse replay and attribute the membership it
      produced, so it is purged once that `FR-014` `MembershipEvent` is purged.

    **The redeemed horizon is anchored, never a literal.** `R4-01` §3 is explicit that `R4-03` must
    not write twelve months into this sweeper as a number. It imports
    `MEMBERSHIP_EVENT_RETENTION_MONTHS` and reuses `_months_before`, so the invitation horizon
    *follows* the event horizon by construction: shortening or lengthening the event retention moves
    this with it, and the two cannot drift into describing one rule two ways. A literal here would
    read as consistent on the day it was written and silently diverge on the day the other changed.
    """

    def __init__(
        self,
        invitations: SqlInvitationStore,
        *,
        retention_months: int = MEMBERSHIP_EVENT_RETENTION_MONTHS,
    ) -> None:
        self._invitations = invitations
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> InvitationSweepReport:
        """Purge every invitation whose purpose has ended.

        Calendar months, not days, via `_months_before` -- the same reason `MembershipEventSweeper`
        uses it: 730 days is not 24 months across a leap year, and a horizon that drifts by
        a day is a horizon nobody fixed.

        `now` is passed through as well as the derived horizon, because the two branches need
        different instants: the redeemed branch compares against the horizon, and the unredeemed
        branch asks whether the invitation has expired *now*.
        """
        horizon = _months_before(now, self._retention_months)
        return InvitationSweepReport(
            purged_invitations=self._invitations._purge_spent_invitations(horizon, now=now)
        )


__all__ = [
    "InvitationRetentionSweeper",
    "InvitationSweepReport",
]
