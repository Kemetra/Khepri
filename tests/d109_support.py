"""Shared harness for `D1-09`'s two test files (active `RCA-008`).

`D1-09` has two subjects -- how many reads a surface performs, and what
acquisition costs -- and they need one set of fixtures. Kept out of
`tests/d105_support.py` deliberately: that file was split from a combined one
because the combined file scored 8.03 on Lines of Code in a Single File and on
Low Cohesion, and adding a counting harness to it re-scores it. The scripted
port, the governed outcomes and the field tuples are imported from there rather
than redefined, so there is no second definition of what the port answers.

**The counter is here and not in `src/`.** A read-count accumulator living in
`khepri.rca.workspace` would be state surviving a request, which is exactly what
`FR-169` and `RCA-008` §Retention forbid -- and shipping retention is a strange
way to assert non-retention. The instrument is test-only and per-call.

**It wraps `SemanticQueryActions.request`, not the port.** `SV1-08` ledger §3a
measures the uniform-miss path at 1331 us, "authorization plus the scoped run
read alone", so a read that misses still costs acquisition. Counting `project`
calls would measure the 11.6 us half and under-count every miss. The precedent
is `_CountingIsolation`/`_LoggingReader` in `test_sv108_query_baseline.py`, which
wrap the door and the reader for the same reason.
"""

from __future__ import annotations

from typing import Any

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import seam
from khepri.rca.workspace.decision.card import CardsRequest
from khepri.rca.workspace.decision.controls import ControlSelection
from khepri.runtime.shell_decisions import read_surface
from tests.d105_support import (
    BASKET_FIELDS,
    BRANCH_FIELDS,
    CONCENTRATION_FIELDS,
    PRODUCT_FIELDS,
    ScriptedPort,
    actions,
    availability,
    breakdown,
    evidence_outcome,
    overview,
)

__all__ = [
    "CountingActions",
    "ScriptedPort",
    "actions",
    "admitted_script",
    "refused_overview_script",
    "request_for",
    "surface_reads",
]

ORGANIZATION = "org1"
ACCOUNT = "acc1"
SOURCE = "run1"


class CountingActions:
    """Records the `view_id` of every read, then serves it from the real seam.

    A list rather than a counter: which views were read, and in what order, is
    what a later slice would quietly change. A bare total would not see a
    substitution.
    """

    def __init__(self, inner: Any) -> None:
        """Wrap `inner`; every request appends its view id to `views`."""
        self._inner = inner
        self.views: list[str] = []

    def request(self, query: Any) -> Any:
        """Record the view read, then answer from the real orchestration."""
        self.views.append(query.view.view_id)
        return self._inner.request(query)


def admitted_script() -> dict[str, ports.ViewOutcome]:
    """The seven reachable views, each admitting.

    `PeriodComparisonView` is absent and that is deliberate, not an omission:
    it answers through the semantic-query composition root (`RCA-009`) and no
    read model on this surface calls it.
    """
    return {
        seam.EXECUTIVE_OVERVIEW.view_id: overview(),
        seam.METRIC_AVAILABILITY.view_id: availability(
            (("revenue", "available", None, ()),)
        ),
        seam.REPORT_EVIDENCE.view_id: evidence_outcome(),
        seam.BRANCH_PERFORMANCE.view_id: breakdown(
            seam.BRANCH_PERFORMANCE, BRANCH_FIELDS, (("s1", "revenue", "1", "complete"),)
        ),
        seam.PRODUCT_CATEGORY.view_id: breakdown(
            seam.PRODUCT_CATEGORY,
            PRODUCT_FIELDS,
            (("category", "c", "revenue", "1", "complete"),),
        ),
        seam.BASKET.view_id: breakdown(
            seam.BASKET, BASKET_FIELDS, (("revenue", "1", "complete", ()),)
        ),
        seam.CONCENTRATION.view_id: breakdown(
            seam.CONCENTRATION,
            CONCENTRATION_FIELDS,
            (("product", "revenue", "1", "complete"),),
        ),
    }


def refused_overview_script() -> dict[str, ports.ViewOutcome]:
    """The admitted seven, with S-1 refusing so `read_cards` returns early."""
    script = admitted_script()
    script[seam.EXECUTIVE_OVERVIEW.view_id] = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(cause="incompatible source shape"),
    )
    return script


def request_for(source_id: str = SOURCE) -> CardsRequest:
    """One organization member's request for one run."""
    return CardsRequest(
        organization_id=ORGANIZATION, account_id=ACCOUNT, source_id=source_id
    )


def surface_reads(
    script: dict[str, ports.ViewOutcome], selection: ControlSelection
) -> tuple[str, ...]:
    """Drive the real `read_surface` once and return the views it read, in order."""
    counting = CountingActions(actions(ScriptedPort(script)))
    read_surface(counting, request_for(), selection=selection)
    return tuple(counting.views)
