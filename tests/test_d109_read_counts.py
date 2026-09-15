"""Per-path read-count bounds for the decision surface (`D1-09`; active `RCA-008`).

`FR-168` bars every usual performance instrument, so what is left is the number
of reads a surface performs. `read_surface` and `read_cards` both state in prose
that each view is read exactly once; this file makes that an assertion, per path,
so a later slice cannot quietly multiply them.

**Counted at `SemanticQueryActions.request`, not at the port.** `SV1-08` ledger
§3a puts the uniform-miss path at 1331 us -- "authorization plus the scoped run
read alone" -- so a read that misses still costs acquisition. A counter on
`project` would measure the 11.6 us half and under-count every miss.
"""

from __future__ import annotations

from khepri.rca.workspace.decision.controls import ControlSelection
from tests.d109_support import (
    admitted_script,
    refused_overview_script,
    surface_reads,
)

#: The admitted page, in the order `read_surface` issues it. Seven and not eight:
#: `PeriodComparisonView` is published and unreachable (`FR-170`), so this is not
#: derived from `DECISION_VIEWS`.
ADMITTED_VIEWS = (
    "ExecutiveOverviewView",
    "MetricAvailabilityView",
    "ReportEvidenceView",
    "BranchPerformanceView",
    "ProductCategoryView",
    "BasketView",
    "ConcentrationView",
)

#: `read_cards` returns before S-6 and S-9 when the overview refuses.
REFUSED_VIEWS = (
    "ExecutiveOverviewView",
    "BranchPerformanceView",
    "ProductCategoryView",
    "BasketView",
    "ConcentrationView",
)


def _plain() -> ControlSelection:
    """A request asking for no filter at all."""
    return ControlSelection(source_id="run1")


def test_the_admitted_page_reads_seven_views_each_exactly_once() -> None:
    """`read_surface`'s "each view exactly once", asserted rather than documented."""
    read = surface_reads(admitted_script(), _plain())

    assert read == ADMITTED_VIEWS
    assert len(read) == len(set(read))


def test_a_refused_overview_reads_five_because_cards_returns_early() -> None:
    """The count is path-dependent, and the short path is asserted too.

    `read_cards` returns at `card.py:276` before S-6 and S-9 when the overview
    projection is `None`. A suite asserting only the admitted seven would leave
    this path unmeasured.
    """
    read = surface_reads(refused_overview_script(), _plain())

    assert read == REFUSED_VIEWS
    assert len(read) == len(set(read))


def test_every_view_unavailable_reads_the_same_five() -> None:
    """A uniform miss costs acquisition on the same path as a refusal."""
    read = surface_reads({}, _plain())

    assert read == REFUSED_VIEWS


def test_an_unroutable_parameter_adds_exactly_one_read_and_only_then() -> None:
    """`_unsupported_read`'s extra read is earned, conditional, and bounded at one.

    `FR-137` refuses a parameter no view admits before projection, and the
    refusal must be earned by a real read rather than invented. What is asserted
    is that it fires only for the unroutable ask and adds exactly one.
    """
    asked = ControlSelection(source_id="run1", filters=(("nosuchdim", "x"),))

    read = surface_reads(admitted_script(), asked)

    assert read == (*ADMITTED_VIEWS, "BranchPerformanceView")


def test_a_real_filter_adds_no_read() -> None:
    """`store` is routed to the views admitting it, and routing is not a read."""
    asked = ControlSelection(source_id="run1", filters=(("store", "s1"),))

    read = surface_reads(admitted_script(), asked)

    assert read == ADMITTED_VIEWS


def test_no_view_is_read_twice_on_any_ordinary_path() -> None:
    """The coalescing `D1-03` and `D1-05` performed, held as a standing bound.

    Derived from the recorded reads rather than hand-listed, and asserted
    non-empty: a scan that silently recorded nothing would otherwise pass.
    """
    for script in (admitted_script(), refused_overview_script(), {}):
        read = surface_reads(script, _plain())

        assert read
        assert len(read) == len(set(read))
