"""The deletion-evidence horizon (`W1-07b`; `KHEPRI-DEC-033` §2, `OD-2`; `RRA-002` `FR-124`).

`OD-2` decided twelve months, "on `KHEPRI-DEC-015` §2a's discipline that no horizon is quietly
longer than another", rejecting indefinite retention by Constitution VII's least-data default.

**Why the number is repeated here rather than imported.** `R7-01` §3 forbids `khepri.rra` importing
`khepri.rca`, and twelve months lives in `rca/lifecycle.py`. This is a second *constant* for one
decided number, which the boundary requires; it is not a second *decision* -- both cite
`KHEPRI-DEC-033` §2, and `test_the_two_twelve_month_horizons_agree` fails if either moves alone.
The same applies to the calendar arithmetic below.

**Nothing implemented this horizon before `W1-07b`.** `W1-07a` shipped the deletion that writes
these rows; this is where they gain an ending.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

#: `KHEPRI-DEC-033` `OD-2`. Kept equal to `khepri.rca.lifecycle.MEMBERSHIP_EVENT_RETENTION_MONTHS`
#: by a test, which is what makes this a restatement of one decision rather than a second policy.
EVIDENCE_RETENTION_MONTHS = 12


class EvidencePurge(Protocol):
    """The one verb this sweeper needs, so it depends on a capability and not on a repository."""

    def purge_evidence_before(self, horizon: datetime) -> int: ...


@dataclass(frozen=True, slots=True)
class EvidenceSweepReport:
    """What one pass purged, in counts only. No identifier is echoed (`KHEPRI-DEC-015` §7)."""

    purged_evidence: int


class DeletionEvidenceSweeper:
    """Purges deletion evidence past `KHEPRI-DEC-033` §2's twelve-month horizon.

    No horizon override in production: `retention_months` exists so a test can name a boundary
    without waiting a year, and `RetentionPasses` constructs this with the default.
    """

    def __init__(
        self, deletions: EvidencePurge, *, retention_months: int = EVIDENCE_RETENTION_MONTHS
    ) -> None:
        self._deletions = deletions
        self._retention_months = retention_months

    def sweep(self, *, now: datetime) -> EvidenceSweepReport:
        """One pass, measured from each row's own attempt instant."""
        horizon = _months_before(now, self._retention_months)
        return EvidenceSweepReport(purged_evidence=self._deletions.purge_evidence_before(horizon))


def _months_before(moment: datetime, months: int) -> datetime:
    """`moment` shifted back by whole calendar months, clamping a short target month.

    The same arithmetic as `rca/lifecycle._months_before`, restated for the reason
    `EVIDENCE_RETENTION_MONTHS` is: `R7-01` §3 forbids `khepri.rra` importing `khepri.rca`.
    `timedelta` has no month unit and a fixed day count drifts across leap years, so the horizon is
    computed on the calendar; a day-of-month absent from the target month (31 March going back to
    February) clamps to that month's last day, which keeps the horizon monotonic.

    `dateutil` is deliberately not used: it is not a dependency of this project, and adding one for
    nine lines the repository already implements would be a dependency bought cheaply and paid for
    forever.
    """
    month_index = moment.month - 1 - months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


__all__ = ["EVIDENCE_RETENTION_MONTHS", "DeletionEvidenceSweeper", "EvidenceSweepReport"]
