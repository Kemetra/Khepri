"""`facts.GOVERNED_METRICS`: the core metric vocabulary as one governed set.

`RRA-011` requires a catalog to be *derived* from the constants that already
govern each code, and requires a slice to reduce the repository's count of
hand-maintained code lists rather than add one. This module proves both halves
for the first of those sets.

**The expectation is stated independently.** Every assertion below names the ten
metrics literally rather than importing the frozenset to check itself. A test
that read `GOVERNED_METRICS` to verify `GOVERNED_METRICS` would pass against any
content, including an empty set, which is the tautology `RRA-011`'s verification
clause exists to exclude.
"""

from __future__ import annotations

from khepri.rra import facts
from khepri.rra.rendering import wording


def test_the_governed_set_holds_exactly_the_ten_core_metrics() -> None:
    """`RRA-004` names ten headline metrics, and the set holds those ten.

    Written out rather than derived so this test fails when the set changes,
    which is the point: adding a metric is a governed act and should require
    someone to say so here.
    """
    assert {
        "revenue",
        "units",
        "transactions",
        "average_order_value",
        "average_selling_price",
        "cost",
        "gross_profit",
        "gross_margin",
        "discount",
        "returns",
    } == facts.GOVERNED_METRICS


def test_every_metric_constant_is_a_member() -> None:
    """The constants and the set cannot disagree.

    Reads the module's `METRIC_*` attributes rather than a list, so a constant
    added without reaching the set fails here even though the test names no
    metric of its own.
    """
    constants = {
        value
        for name, value in vars(facts).items()
        if name.startswith("METRIC_") and isinstance(value, str)
    }

    assert constants == facts.GOVERNED_METRICS


def test_an_unknown_code_is_not_a_governed_metric() -> None:
    """The predicate refuses rather than admitting by shape."""
    assert facts.is_governed_metric("revenue")
    assert not facts.is_governed_metric("revenues")
    assert not facts.is_governed_metric("")


def test_the_wording_guard_now_reads_the_governed_set_rather_than_a_copy() -> None:
    """The reduction `RRA-011` requires, asserted as a property.

    `wording.py` held a retyped copy of these ten constants. A metric added to
    `facts.py` left that copy unchanged, so `METRIC_WORDING` stayed "complete"
    while missing the new code and the first reader to meet that metric met its
    raw identifier instead of a name.

    Now the guard's expectation contains the governed set, so the same addition
    makes the import demand wording for it.
    """
    assert facts.GOVERNED_METRICS <= wording._GOVERNED_METRIC_CODES
