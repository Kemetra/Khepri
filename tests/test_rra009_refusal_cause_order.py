"""Every refused result states one cause, in the order `RRA-009` §Refusals governs.

"When more than one cause refuses the same result, state exactly one, chosen in
this order: a gap in one of the result's own input columns
(`incomplete_column_coverage`); then a repeated canonical row signature
(`repeated_row_signature`); then the mapping's own cause
(`required_input_unavailable` or `ambiguous_mapping`)."

`#431`'s 2026-09-22 comment traced three wrong causes (A-05) to one root: each
metric picked its reason at its own call site. So these tests do not name the
metrics they check. They take the set from the package itself -- facts,
refusals, series and comparisons -- assert that set is the whole governed
catalogue, and then hold *every* member to an expectation. A metric the table
does not list must publish; a metric that refuses must state the listed cause.

The fixtures are built so each refusal has a known cause: a date column, every
dimension the oracle contract maps, and one well-signed return row, so nothing
refuses for an unrelated reason. The one standing cause is `channel`, which this
contract does not map -- so its comparisons refuse in every fixture, and they are
where the mapping cause meets the other two.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

import pytest

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.facts import (
    GOVERNED_METRICS,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_DISCOUNT,
    METRIC_GROSS_MARGIN,
    METRIC_GROSS_PROFIT,
    METRIC_RETURNS,
    METRIC_REVENUE,
    METRIC_TRANSACTIONS,
    METRIC_UNITS,
    REASON_AMBIGUOUS_MAPPING,
    REASON_INCOMPLETE_COVERAGE,
    REASON_INPUT_UNAVAILABLE,
    REASON_REPEATED_ROW_SIGNATURE,
    SERIES_DIMENSIONS,
    SERIES_MEASURES,
    AdmittedInput,
    FactPackage,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import SEMANTIC_CHANNEL, build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import attesting_manifest, oracle_contract

COVERAGE = REASON_INCOMPLETE_COVERAGE
REPEATED = REASON_REPEATED_ROW_SIGNATURE
UNAVAILABLE = REASON_INPUT_UNAVAILABLE
AMBIGUOUS = REASON_AMBIGUOUS_MAPPING

_HEADER = (
    "date,event_kind,status,revenue,units,invoice_no,store,product,category,cost,discount_amount"
)
_SALE_1 = "2026-03-04,sale,posted,100.00,2,INV-1,S1,P1,C1,50.00,5.00"
_SALE_2 = "2026-03-05,sale,posted,200.00,4,INV-2,S1,P2,C1,90.00,0.00"
_RETURN = "2026-03-06,return,posted,-30.00,-1,INV-9,S1,P1,C1,0.00,0.00"

_SALE_2_NO_REVENUE = "2026-03-05,sale,posted,,4,INV-2,S1,P2,C1,90.00,0.00"
_SALE_2_NO_COST = "2026-03-05,sale,posted,200.00,4,INV-2,S1,P2,C1,,0.00"
_SALE_2_NO_DISCOUNT = "2026-03-05,sale,posted,200.00,4,INV-2,S1,P2,C1,90.00,"
#: `RRA-003`:93 -- a return whose revenue is positive breaks the sign contract
#: and refuses returns *and* the financial revenue population.
_RETURN_POSITIVE = "2026-03-06,return,posted,30.00,-1,INV-9,S1,P1,C1,0.00,0.00"

_DAYS = (date(2026, 3, 4), date(2026, 3, 5), date(2026, 3, 6))


def _csv(*rows: str, header: str = _HEADER) -> bytes:
    return ("\n".join((header, *rows)) + "\n").encode()


def _without_column(content: bytes, name: str) -> bytes:
    lines = content.decode().strip().split("\n")
    position = lines[0].split(",").index(name)
    kept = [
        ",".join(cell for index, cell in enumerate(line.split(",")) if index != position)
        for line in lines
    ]
    return ("\n".join(kept) + "\n").encode()


def _renamed(content: bytes, old: str, new: str) -> bytes:
    header, _, body = content.decode().partition("\n")
    columns = [new if column == old else column for column in header.split(",")]
    return (",".join(columns) + "\n" + body).encode()


def _build(content: bytes, *, attested: bool = False) -> FactPackage:
    contract = oracle_contract()
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile, contract=contract)
    return build_fact_package(
        AdmittedInput(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            profile=profile,
            mapping=mapping,
            decision=assess_admissibility(profile, mapping),
            contract=contract,
            manifest=(
                attesting_manifest(content=content, contract=contract, days=_DAYS)
                if attested
                else None
            ),
        )
    )


def _composed(measure: str) -> set[str]:
    return {f"{measure}_by_{dimension}" for dimension in SERIES_DIMENSIONS}


#: The whole catalogue a package answers for, composed from the package's own
#: constants rather than typed out, so a metric added there joins every test here.
_CATALOGUE = frozenset(
    GOVERNED_METRICS | {code for measure in SERIES_MEASURES for code in _composed(measure)}
)

#: `channel` is not mapped by the oracle contract, so both of its comparisons
#: refuse in every fixture -- truthfully for the mapping's cause, unless a
#: narrower cause also refuses them.
_CHANNEL = {f"{measure}_by_{SEMANTIC_CHANNEL}" for measure in SERIES_MEASURES}


def _emitted(result: FactPackage) -> dict[str, str | None]:
    """Every metric the package answered for, mapped to its refusal cause or `None`."""
    answered: dict[str, str | None] = {}
    for published in (*result.facts, *result.series, *result.comparisons):
        answered[published.metric] = None
    for refused in result.refusals:
        assert refused.metric not in answered, f"{refused.metric} both published and refused"
        answered[refused.metric] = refused.reason
    return answered


def _assert_causes(result: FactPackage, expected: dict[str, str]) -> None:
    answered = _emitted(result)
    assert set(answered) == _CATALOGUE, "the package answered for a different catalogue"
    refused = {metric: reason for metric, reason in answered.items() if reason is not None}
    assert refused, "nothing refused, so this fixture proves nothing about causes"
    assert refused == expected


def _all(metrics: set[str] | frozenset[str], reason: str) -> dict[str, str]:
    return dict.fromkeys(metrics, reason)


_MARGIN_PAIR = {METRIC_GROSS_PROFIT, METRIC_GROSS_MARGIN}


# -- one cause at a time -----------------------------------------------------------


def test_the_well_signed_control_refuses_only_the_unmapped_channel() -> None:
    """The baseline every fixture below departs from by exactly one cause."""
    _assert_causes(_build(_csv(_SALE_1, _SALE_2, _RETURN)), _all(_CHANNEL, UNAVAILABLE))


def test_a_gap_in_revenue_states_coverage_on_every_result_it_refuses() -> None:
    """A-05(1): profit and margin said "the file does not contain cost" here.

    `RRA-009`: "a derived result such as gross margin states coverage when either
    of its inputs has a gap." ASP refuses too -- a sale carrying units and no
    revenue is an unmatched row in `sales_complete_revenue_units` -- and its cause
    is the same gap. The trend and comparisons survive a plain gap (`#503`), and
    AOV narrows to its matched rows, so neither is listed.
    """
    result = _build(_csv(_SALE_1, _SALE_2_NO_REVENUE, _RETURN))

    _assert_causes(
        result,
        {
            **_all({METRIC_REVENUE, METRIC_AVERAGE_SELLING_PRICE, *_MARGIN_PAIR}, COVERAGE),
            **_all(_CHANNEL, UNAVAILABLE),
        },
    )


def test_a_gap_in_cost_states_coverage_on_cost_and_the_pair_derived_from_it() -> None:
    result = _build(_csv(_SALE_1, _SALE_2_NO_COST, _RETURN))

    _assert_causes(
        result,
        {**_all({METRIC_COST, *_MARGIN_PAIR}, COVERAGE), **_all(_CHANNEL, UNAVAILABLE)},
    )


def test_a_repeated_row_signature_states_itself_on_every_result_it_refuses() -> None:
    """A-05(2) and A-05(3), and the channel comparison under `#539`'s order.

    The units series said "the file does not contain units", and discount and
    returns named a mapping cause about columns that are present. The channel
    comparisons are refused twice -- by the repeat and by the absent column --
    and the repeat is the narrower of the two.
    """
    result = _build(_csv(_SALE_1, _SALE_1, _SALE_2, _RETURN))

    _assert_causes(result, _all(_CATALOGUE, REPEATED))


def test_an_unmapped_column_states_the_mapping_cause() -> None:
    result = _build(_without_column(_csv(_SALE_1, _SALE_2, _RETURN), "cost"))

    _assert_causes(result, _all({METRIC_COST, *_MARGIN_PAIR, *_CHANNEL}, UNAVAILABLE))


def test_an_ambiguous_label_states_the_mapping_cause() -> None:
    result = _build(_renamed(_csv(_SALE_1, _SALE_2, _RETURN), "discount_amount", "discount"))

    _assert_causes(result, {METRIC_DISCOUNT: AMBIGUOUS, **_all(_CHANNEL, UNAVAILABLE)})


# -- two causes at once: the order is the subject --------------------------------------

#: Everything the repeat refuses, which is the whole catalogue.
_REPEAT = _all(_CATALOGUE, REPEATED)


def test_a_revenue_gap_outranks_a_repeat_on_the_results_the_gap_refuses() -> None:
    """Coverage first -- but only where the gap is one of the causes.

    Revenue, ASP and the margin pair are refused by both, and state coverage.
    AOV, returns and the revenue trend survive a plain revenue gap on their own,
    so the repeat is their only cause and they state it: telling a reader to fill
    a revenue cell would not make those results available.
    """
    result = _build(_csv(_SALE_1, _SALE_1, _SALE_2_NO_REVENUE, _RETURN))

    _assert_causes(
        result,
        {
            **_REPEAT,
            **_all({METRIC_REVENUE, METRIC_AVERAGE_SELLING_PRICE, *_MARGIN_PAIR}, COVERAGE),
        },
    )


def test_a_cost_gap_outranks_a_repeat() -> None:
    result = _build(_csv(_SALE_1, _SALE_1, _SALE_2_NO_COST, _RETURN))

    _assert_causes(result, {**_REPEAT, **_all({METRIC_COST, *_MARGIN_PAIR}, COVERAGE)})


def test_a_discount_gap_outranks_a_repeat() -> None:
    result = _build(_csv(_SALE_1, _SALE_1, _SALE_2_NO_DISCOUNT, _RETURN))

    _assert_causes(result, {**_REPEAT, METRIC_DISCOUNT: COVERAGE})


def test_a_violating_return_outranks_a_repeat_on_the_revenue_population() -> None:
    """`RRA-003`:93 refuses the financial revenue population, trend and all.

    So every result reading that population -- revenue, returns, the pair, and
    each revenue series and comparison, channel included -- states coverage over
    the repeat. Units, AOV and ASP do not read the return's revenue, so the repeat
    is their cause.
    """
    result = _build(_csv(_SALE_1, _SALE_1, _SALE_2, _RETURN_POSITIVE))

    _assert_causes(
        result,
        {
            **_REPEAT,
            **_all(
                {METRIC_REVENUE, METRIC_RETURNS, *_MARGIN_PAIR, *_composed("revenue")},
                COVERAGE,
            ),
        },
    )


def test_a_violating_return_outranks_an_absent_channel_column() -> None:
    """Coverage before the mapping's cause, on the comparison both refuse.

    `#503` pinned the opposite -- the absent channel column winning -- before
    `RRA-009` ordered the pair. The revenue population is refused whatever the
    reader does about channel, so coverage is the cause they can act on first.
    """
    result = _build(_csv(_SALE_1, _SALE_2, _RETURN_POSITIVE))

    _assert_causes(
        result,
        {
            **_all(
                {METRIC_REVENUE, METRIC_RETURNS, *_MARGIN_PAIR, *_composed("revenue")},
                COVERAGE,
            ),
            f"units_by_{SEMANTIC_CHANNEL}": UNAVAILABLE,
        },
    )


@pytest.mark.parametrize(
    ("content", "metrics"),
    [
        pytest.param(
            _without_column(_csv(_SALE_1, _SALE_1, _SALE_2, _RETURN), "cost"),
            {METRIC_COST, *_MARGIN_PAIR},
            id="unmapped-cost",
        ),
        pytest.param(
            _renamed(_csv(_SALE_1, _SALE_1, _SALE_2, _RETURN), "discount_amount", "discount"),
            {METRIC_DISCOUNT},
            id="ambiguous-discount",
        ),
    ],
)
def test_a_repeat_outranks_the_mapping_cause(content: bytes, metrics: set[str]) -> None:
    result = _build(content)

    assert metrics <= set(_emitted(result))
    _assert_causes(result, _REPEAT)


def test_the_transaction_family_keeps_the_repeat_it_already_stated() -> None:
    """The control on the sale-only family, whose cause did not move.

    Transactions and AOV stated `repeated_row_signature` before the resolver; a
    gap in revenue does not refuse either, so it must not displace that.
    """
    result = _build(_csv(_SALE_1, _SALE_1, _SALE_2_NO_REVENUE, _RETURN))

    for metric in (METRIC_TRANSACTIONS, METRIC_AVERAGE_ORDER_VALUE, METRIC_UNITS):
        refused = result.refusal(metric)
        assert refused is not None, metric
        assert refused.reason == REPEATED, metric


# -- A-09: the refused population does not reach the retained evidence -------------


def test_a_violating_return_is_not_summed_into_the_daily_bases() -> None:
    """A-09: the revenue headline refused while the daily basis summed the reversal.

    `RRA-003`:93 refuses the financial revenue population, and a daily basis is the
    evidence a figure is reconciled against -- so its revenue is withheld the way
    a refused currency withholds it, and units, which the violation does not
    reach, stay.
    """
    control = _build(_csv(_SALE_1, _SALE_2, _RETURN), attested=True)
    violated = _build(_csv(_SALE_1, _SALE_2, _RETURN_POSITIVE), attested=True)

    assert control.daily_bases, "the control retains no daily basis to compare against"
    assert violated.value(METRIC_REVENUE) is None
    assert violated.daily_bases
    control_values = _basis_values(control)
    violated_values = _basis_values(violated)
    assert all(value.revenue is None for value in violated_values), violated_values
    assert [value.units for value in violated_values] == [value.units for value in control_values]
    assert any(value.revenue == Decimal("-30.00") for value in control_values), (
        "the control's basis does not carry the return, so it cannot show the difference"
    )


def _basis_values(package):
    """Every per-day value across a package's daily bases, in order."""
    return [value for basis in package.daily_bases for value in basis.values]


def test_a_violating_return_withholds_the_financial_retained_bases_only() -> None:
    """The financial bases sum the reversal; the sale-only bases never read it.

    Transactions, AOV and ASP still publish over sales, and `RRA-004`:123 requires
    each to cite a compatible basis -- so the `sales_*` bases stay.
    """
    control = _build(_csv(_SALE_1, _SALE_2, _RETURN))
    violated = _build(_csv(_SALE_1, _SALE_2, _RETURN_POSITIVE))

    def populations(result: FactPackage) -> set[str]:
        return {basis.population for basis in result.retained_bases}

    financial = {code for code in populations(control) if code.startswith("financial_")}
    sales = {code for code in populations(control) if code.startswith("sales_")}
    assert financial and sales, "the control retains no bases of one family"
    assert violated.value(METRIC_TRANSACTIONS) is not None
    assert populations(violated) == sales
