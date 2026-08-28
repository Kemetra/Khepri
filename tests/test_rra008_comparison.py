"""Period comparison over a governed trend, in both modes RRA-008 requires.

The packages here are built from real CSV bytes through the real pipeline rather
than assembled by hand. A fabricated `FactPackage` would let a test assert over
an aggregate the package builder would never produce, which is exactly the
failure this family exists to avoid.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal

import pytest

from khepri.rra import facts
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.aggregates import GRANULARITY_DAY, GRANULARITY_MONTH
from khepri.rra.analysis import comparison, windows
from khepri.rra.analysis.comparison import (
    METRIC_DELTA_ABSOLUTE,
    METRIC_DELTA_PERCENT,
    MODE_PERIOD_OVER_PERIOD,
    MODE_YEAR_OVER_YEAR,
    REASON_NEGATIVE_BASE,
    REASON_PRIOR_WINDOW_ABSENT,
)
from khepri.rra.bundle import SECTION_COMPARISON, SECTION_REASONS
from khepri.rra.facts import (
    CAVEAT_UNDATED_ROWS_EXCLUDED,
    REASON_INPUT_UNAVAILABLE,
    REASON_ZERO_DENOMINATOR,
    UNIT_MONETARY,
    UNIT_RATIO,
    AdmittedInput,
    FactPackage,
    RefusedResult,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import (
    SEMANTIC_REVENUE,
    SEMANTIC_TRANSACTION_DATE,
    build_mapping,
)
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import (
    TEST_CONTRACT,
    attesting_manifest,
    published_mapping_identity,
)

HEADER = b"date,revenue,units,invoice_no,category,branch\n"

FOUR_DAYS = tuple(
    date(2026, 1, 5) + timedelta(days=offset) for offset in range(4)
)


def package_for(
    rows: list[tuple[date | None, str]],
    *,
    attested: bool = True,
    attested_days: tuple[date, ...] | None = None,
) -> FactPackage:
    """One package through the real pipeline, attested unless told otherwise.

    `attested_days` narrows the attestation to fewer days than the rows carry,
    which is what an export ending mid-period looks like: the signature spans
    the *data*, so the attested days form a contiguous prefix of it and
    `build_coverage_signature` records `COVERAGE_MODE_PREFIX`. Folded in here
    rather than given its own builder, because a second copy of this
    assembly differing in one argument is what drives a test module's
    cohesion down.
    """
    body = b"".join(
        f"{'' if when is None else when.isoformat()},"
        f"{amount},1,INV-{index},Beverages,Cairo\n".encode()
        for index, (when, amount) in enumerate(rows)
    )
    content = HEADER + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    # Built under the published mapping identity: this module's subject is
    # comparison, not the version gate, so its packages must keep combining a
    # triple `versions.ADMITTED_PACKAGE_PAIRS` admits.
    # Coverage is attested for exactly the dates these rows carry. `RRA-008`
    # refuses completeness-dependent comparison "without an authoritative valid
    # manifest", so a module whose subject is comparison arithmetic has to
    # attest its own coverage or every case refuses before reaching the
    # arithmetic it was written to prove.
    dated = (
        ()
        if not attested
        else attested_days
        if attested_days is not None
        else tuple(when for when, _ in rows if when is not None)
    )
    manifest = (
        None
        if not dated
        else attesting_manifest(
            content=content, contract=TEST_CONTRACT, days=dated
        )
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                manifest=manifest,
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            ),
        )


def month_start(offset: int, *, year: int = 2024, month: int = 1) -> date:
    index = year * 12 + month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def monthly(months: int, *, skip: int | None = None) -> FactPackage:
    """One row on the first of each of `months` consecutive months from offset 0.

    A month of run-up is prepended at offset -1 and is never compared. Only
    periods with data on both sides are known whole, so without it the month at
    offset 0 would be excluded as possibly left-truncated and every window here
    would slide by one. Prepending it means offsets keep meaning what their names
    say: `monthly(26)` still compares the same two periods it always did.

    `skip` omits one offset, which shifts every bucket after it -- the shape that
    makes positional pairing wrong and label pairing right.
    """
    return package_for(
        [
            (month_start(offset), "100.00")
            for offset in range(-1, months)
            if offset != skip
        ]
    )


def daily(days: int) -> FactPackage:
    start = date(2026, 1, 1)
    return package_for([(start + timedelta(days=n), "100.00") for n in range(days)])


def facts_of(package: FactPackage) -> tuple:
    result = comparison.derive(package)
    assert not isinstance(result, RefusedResult), result
    return result


def modes_for(package: FactPackage) -> set[str]:
    return {
        comparison.mode_of(fact)
        for fact in facts_of(package)
        if fact.metric == METRIC_DELTA_ABSOLUTE
    }


def window(package: FactPackage, mode: str):
    return comparison._window_for(package, mode)


def months_apart(current: str, prior: str) -> int:
    current_year, current_month = (int(part) for part in current.split("-"))
    prior_year, prior_month = (int(part) for part in prior.split("-"))
    return (current_year - prior_year) * 12 + (current_month - prior_month)


def two_settled_days(prior: str, current: str) -> FactPackage:
    """Two days to compare, bracketed by a day on each side so both have settled.

    Neither bracketing day is ever compared. They exist so the two that matter
    have data on both sides, which is the only evidence available here that a
    period is whole rather than cut off by where the export began or ended.
    """
    return package_for(
        [
            (date(2026, 1, 1), "1.00"),
            (date(2026, 1, 2), prior),
            (date(2026, 1, 3), current),
            (date(2026, 1, 4), "1.00"),
        ]
    )


def test_the_trend_granularity_is_what_the_labels_mean() -> None:
    # The premise every label assertion below rests on.
    assert monthly(26).trend().series.granularity == GRANULARITY_MONTH
    assert daily(20).trend().series.granularity == GRANULARITY_DAY


def test_both_governed_modes_are_emitted() -> None:
    # RRA-008 requires period-over-period *and* year-over-year. One unnamed
    # current/prior pair satisfies neither fully.
    assert modes_for(monthly(14)) == {MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR}


def test_the_two_modes_carry_distinct_stable_identities() -> None:
    facts = [f for f in facts_of(monthly(14)) if f.metric == METRIC_DELTA_ABSOLUTE]
    assert len({fact.fact_id for fact in facts}) == 2
    assert len({fact.citation_id for fact in facts}) == 2


def test_facts_are_named_under_this_familys_own_formula_version() -> None:
    # Not the package's. A correction to the comparison alone would otherwise
    # reuse the same fact and citation identifiers for a materially different
    # number, and a stored citation would point at an answer that had changed
    # underneath it. Within this pull request the derivation moved from
    # half-history windows to one-period windows and from a percentage to a
    # fraction -- under the package's version every one produced identical ids.
    assert comparison.COMPARISON_FORMULA_VERSION != facts.FORMULA_VERSION
    absolute = next(
        fact for fact in facts_of(monthly(14)) if fact.metric == METRIC_DELTA_ABSOLUTE
    )
    expected, _ = facts.fact_identity(
        metric=METRIC_DELTA_ABSOLUTE,
        scope=(comparison.mode_of(absolute),),
        formula_version=comparison.COMPARISON_FORMULA_VERSION,
    )
    assert absolute.fact_id == expected
    under_package, _ = facts.fact_identity(
        metric=METRIC_DELTA_ABSOLUTE,
        scope=(comparison.mode_of(absolute),),
        formula_version=facts.FORMULA_VERSION,
    )
    assert absolute.fact_id != under_package


def test_identities_are_stable_across_runs_over_the_same_input() -> None:
    # Stable, not merely unique. RRA-008 requires a rerun to reach the same
    # identity, which is what makes a citation followable between reports.
    assert {f.fact_id for f in facts_of(monthly(14))} == {
        f.fact_id for f in facts_of(monthly(14))
    }


# --- which two periods each mode compares -----------------------------------


@pytest.mark.parametrize(
    ("mode", "expected_gap"),
    [
        pytest.param(MODE_PERIOD_OVER_PERIOD, 1, id="the-immediately-preceding-period"),
        pytest.param(MODE_YEAR_OVER_YEAR, 12, id="the-same-period-a-year-earlier"),
    ],
)
def test_each_mode_compares_the_period_its_name_says(mode: str, expected_gap: int) -> None:
    found = window(monthly(26), mode)
    assert found is not None
    assert months_apart(found.current.label, found.prior.label) == expected_gap


@pytest.mark.parametrize(
    ("mode", "expected_gap"),
    [
        pytest.param(MODE_PERIOD_OVER_PERIOD, 1, id="period-over-period"),
        pytest.param(MODE_YEAR_OVER_YEAR, 12, id="year-over-year"),
    ],
)
def test_a_gap_in_coverage_does_not_move_which_periods_are_compared(
    mode: str,
    expected_gap: int,
) -> None:
    # A missing month shifts every bucket after it, so pairing by position would
    # silently substitute a neighbour: with January, March, April and May in the
    # series, April's predecessor *by position* is January. Every label still
    # looks plausible and every sum is correct, which is what makes it dangerous.
    found = window(monthly(26, skip=5), mode)
    assert found is not None
    assert months_apart(found.current.label, found.prior.label) == expected_gap


def test_a_missing_counterpart_refuses_rather_than_substituting_a_neighbour() -> None:
    # The period right before the compared one is absent, so there is nothing to
    # compare against. It refuses rather than reaching one further back, which is
    # what positional pairing would have done.
    package = monthly(26, skip=23)
    labels = [bucket.label for bucket in package.trend().series.buckets]
    assert "2025-12" not in labels
    assert "2026-01" in labels
    found = window(package, MODE_PERIOD_OVER_PERIOD)
    assert found is None
    # The other mode is unaffected: a year before 2026-01 is present.
    assert window(package, MODE_YEAR_OVER_YEAR) is not None


@pytest.mark.parametrize("months", [14, 26, 38, 62])
def test_the_compared_periods_never_overlap_however_long_the_history(months: int) -> None:
    # An earlier revision took half the available history as the window, which at
    # 37 settled months produced an 18-month year-over-year comparison whose two
    # windows overlapped by six months -- a period compared partly against itself.
    for mode in (MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR):
        found = window(monthly(months), mode)
        assert found is not None
        assert found.current.label != found.prior.label


def test_older_history_does_not_change_which_periods_are_compared() -> None:
    # The same recent data must give the same answer however much history sits
    # behind it. A window derived from total coverage failed this: prepending old
    # rows moved the boundary and changed the reported delta.
    short = window(monthly(14), MODE_YEAR_OVER_YEAR)
    long = window(monthly(14 + 24), MODE_YEAR_OVER_YEAR)
    assert months_apart(short.current.label, short.prior.label) == 12
    assert months_apart(long.current.label, long.prior.label) == 12


# --- what settles, and what refuses -----------------------------------------


def test_the_period_at_each_end_is_left_out_because_its_completeness_is_unknown() -> (
    None
):
    # Four days of data compare the third against the second. Both outer days are
    # excluded: nothing in the series says whether the last was cut off partway by
    # wherever the export ended, or the first by wherever it began.
    package = two_settled_days("100.00", "150.00")
    assert len(package.trend().series.buckets) == 4
    absolute = next(
        fact for fact in facts_of(package) if fact.metric == METRIC_DELTA_ABSOLUTE
    )
    assert Decimal(absolute.value) == Decimal(50)


def test_every_reason_this_family_refuses_with_is_one_its_section_can_state() -> None:
    # A section may only carry a reason in SECTION_REASONS, so a family that
    # refuses with anything else cannot be assembled into one: the section either
    # raises on a valid package or relabels the refusal and tells a reader the
    # opposite of what happened. Nothing serializes these facts yet, so this is
    # the only place the mismatch is visible before the assembly slice lands.
    refused = {
        comparison.derive(package).reason
        for package in (
            monthly(1),
            package_for(
                [
                    (date(2026, 1, 1), "1.00"),
                    (date(2026, 1, 2), "100.00"),
                    (date(2026, 1, 3), ""),
                    (date(2026, 1, 4), "1.00"),
                ]
            ),
        )
    }
    # Both reachable reasons, named so the subset assertion below cannot pass by
    # exercising only one of them.
    assert refused == {REASON_PRIOR_WINDOW_ABSENT, REASON_INPUT_UNAVAILABLE}
    assert refused <= SECTION_REASONS[SECTION_COMPARISON]


def test_a_left_truncated_first_period_is_never_compared_against() -> None:
    # An export beginning on 15 January holds seventeen days in its first bucket.
    # Every month here bills the same 3,100, so the honest year-over-year answer
    # is no change -- but comparing a whole January 2026 against seventeen days of
    # January 2025 reports +82%, an artifact of where the export started rather
    # than anything the business did. Excluding only the final period caught the
    # boundary the report points at and left the one it compares against.
    rows = [(date(2025, 1, day), "100.00") for day in range(15, 32)]
    rows += [
        (month_start(offset, year=2025, month=2), "3100.00") for offset in range(13)
    ]
    package = package_for(rows)
    assert package.trend().series.buckets[0].label == "2025-01"

    found = window(package, MODE_YEAR_OVER_YEAR)
    assert found is None or found.prior.label != "2025-01"
    assert MODE_YEAR_OVER_YEAR not in modes_for(package)
    assert REASON_PRIOR_WINDOW_ABSENT in {
        refusal.reason for refusal in comparison.refusals(package)
    }


def test_one_settled_period_has_nothing_to_compare() -> None:
    result = comparison.derive(
        package_for([(date(2026, 1, 1), "100.00"), (date(2026, 1, 2), "150.00")])
    )
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT


def test_year_over_year_refuses_alone_when_coverage_is_under_a_year() -> None:
    # Thirteen months leaves twelve settled, so the latest has a predecessor and
    # no counterpart a year back. RRA-008 refuses the affected comparison and not
    # the report, so the other mode survives.
    package = monthly(13)
    assert modes_for(package) == {MODE_PERIOD_OVER_PERIOD}
    assert REASON_PRIOR_WINDOW_ABSENT in {
        refusal.reason for refusal in comparison.refusals(package)
    }


@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: monthly(13), id="no-counterpart-period"),
        pytest.param(
            lambda: package_for(
                [
                    (date(2026, 1, 1), "100.00"),
                    (date(2026, 1, 2), ""),
                    (date(2026, 1, 3), "1.00"),
                ]
            ),
            id="a-compared-period-with-no-revenue",
        ),
    ],
)
def test_a_mode_that_states_nothing_refuses_every_metric_it_would_have(
    build: Callable[[], FactPackage],
) -> None:
    # Built inside the test rather than in the `pytest.param` call, which
    # evaluates at import. A package construction that refuses -- as it does
    # whenever a version this file combines has moved ahead of its consumers --
    # would otherwise abort collection of the whole module, turning one
    # attributable failure into a suite that cannot run.
    package = build()
    # Recording only the absolute delta would leave the percentage
    # indistinguishable from a metric quietly left out, which is the distinction
    # refusals() exists to preserve. A whole-mode failure has no survivor and
    # owes a refusal for both.
    recorded = comparison.refusals(package)
    for metric in (METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT):
        assert any(refusal.metric.startswith(metric) for refusal in recorded), metric


def test_a_single_mode_refusal_is_not_a_report_refusal() -> None:
    assert not isinstance(comparison.derive(monthly(13)), RefusedResult)


def test_both_modes_refusing_refuses_the_comparison() -> None:
    result = comparison.derive(monthly(1))
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT


@pytest.mark.parametrize(
    ("label", "shift"),
    [
        pytest.param("2024-02-29", "year", id="a-leap-day-a-year-earlier"),
        pytest.param("0001-01-01", "day", id="the-day-before-the-calendar-starts"),
    ],
)
def test_a_counterpart_that_is_not_a_date_refuses(label: str, shift: str) -> None:
    # Two ways a counterpart fails to exist, and they raise different
    # exceptions: 29 February a year earlier is a ValueError, and the day before
    # 0001-01-01 is an OverflowError, which is not a ValueError. Guarding only
    # the first let the second escape both entry points as an abort.
    mode = MODE_YEAR_OVER_YEAR if shift == "year" else MODE_PERIOD_OVER_PERIOD
    assert windows.counterpart_label(label, GRANULARITY_DAY, mode) is None


def test_an_unrepresentable_predecessor_refuses_instead_of_aborting() -> None:
    # The profiling parser accepts year 1, so this is a valid package. Both
    # entry points must report the governed refusal rather than raise.
    package = package_for(
        [(date(1, 1, 1), "100.00"), (date(1, 1, 2), "150.00")]
    )
    result = comparison.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_PRIOR_WINDOW_ABSENT
    assert {refusal.reason for refusal in comparison.refusals(package)} == {
        REASON_PRIOR_WINDOW_ABSENT
    }


def test_a_leap_day_has_no_counterpart_and_refuses() -> None:
    # 29 February a year earlier is not a date. The nearest day is a different
    # day, and substituting one would state a comparison nobody asked for.
    assert (
        windows.counterpart_label("2024-02-29", GRANULARITY_DAY, MODE_YEAR_OVER_YEAR)
        is None
    )
    assert (
        windows.counterpart_label("2024-02-28", GRANULARITY_DAY, MODE_YEAR_OVER_YEAR)
        == "2023-02-28"
    )


# --- what each fact says ----------------------------------------------------


def test_the_percentage_delta_is_a_fraction_not_a_percentage() -> None:
    # UNIT_RATIO already means a fraction here: gross_margin stores one, and
    # narrative multiplies every ratio by a hundred to render it. Storing 50 for
    # a rise from 100 to 150 would reach a reader as 5000%.
    percent = next(
        fact
        for fact in facts_of(two_settled_days("100.00", "150.00"))
        if fact.metric == METRIC_DELTA_PERCENT
    )
    assert percent.unit_kind == UNIT_RATIO
    assert Decimal(percent.value) == Decimal("0.5")


def test_the_absolute_delta_is_monetary() -> None:
    absolute = next(
        fact
        for fact in facts_of(two_settled_days("100.00", "150.00"))
        if fact.metric == METRIC_DELTA_ABSOLUTE
    )
    assert absolute.unit_kind == UNIT_MONETARY


@pytest.mark.parametrize(
    ("prior", "reason"),
    [
        pytest.param("0.00", REASON_ZERO_DENOMINATOR, id="a-base-of-zero"),
        pytest.param("-50.00", REASON_NEGATIVE_BASE, id="a-negative-base"),
    ],
)
def test_a_non_positive_base_refuses_the_percentage_and_records_it(
    prior: str,
    reason: str,
) -> None:
    # A percentage of zero is undefined and of a negative base it misleads: a
    # shrinking loss reads as growth. The absolute delta stands either way, and
    # the refusal is recorded -- a consumer must be able to tell a governed
    # refusal from a metric quietly left out.
    package = two_settled_days(prior, "10.00")
    metrics = {fact.metric for fact in facts_of(package)}
    assert METRIC_DELTA_ABSOLUTE in metrics
    assert METRIC_DELTA_PERCENT not in metrics
    recorded = comparison.refusals(package)
    assert reason in {refusal.reason for refusal in recorded}
    assert any(METRIC_DELTA_PERCENT in refusal.metric for refusal in recorded)


def test_every_fact_declares_the_governed_measures_it_came_from() -> None:
    # `Fact.inputs` holds semantic measures. A formula version here would
    # mislabel a version string as provenance and leave the fact declaring no
    # measure at all. The date is an input too: it decides which period a row
    # lands in, and so which two periods are compared.
    for fact in facts_of(monthly(14)):
        assert fact.inputs == (SEMANTIC_TRANSACTION_DATE, SEMANTIC_REVENUE)


def test_a_refusal_names_the_reason_the_mode_actually_gave() -> None:
    # The compared period has no revenue at all while its neighbours do, so both
    # counterpart windows exist and the measure is what is missing. Reporting
    # prior_window_absent would explain the refusal wrongly: the window was
    # there.
    package = package_for(
        [
            (date(2026, 1, 1), "1.00"),
            (date(2026, 1, 2), "100.00"),
            (date(2026, 1, 3), ""),
            (date(2026, 1, 4), "1.00"),
        ]
    )
    result = comparison.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == REASON_INPUT_UNAVAILABLE


def test_modes_refusing_for_different_reasons_do_not_lose_one_of_them() -> None:
    # The two modes fail differently: period-over-period has no predecessor
    # because 2025-12 is missing, while year-over-year finds its counterpart and
    # finds no revenue in it. One field cannot hold both causes, so the summary
    # says which mode it speaks for -- and picks the specific cause over the
    # generic one rather than whichever mode was derived first.
    rows = [(date(2024, 12, 1), "100.00")]
    rows.append((date(2025, 1, 1), ""))
    rows += [(date(2025, month, 1), "100.00") for month in range(2, 12)]
    rows += [(date(2026, 1, 1), "100.00"), (date(2026, 2, 1), "100.00")]
    package = package_for(rows)
    assert "2025-12" not in {
        bucket.label for bucket in package.trend().series.buckets
    }

    # Nothing is lost: refusals() still carries every cause, per mode.
    assert {
        (refusal.metric, refusal.reason) for refusal in comparison.refusals(package)
    } == {
        (metric_and_mode, reason)
        for reason, mode in (
            (REASON_PRIOR_WINDOW_ABSENT, MODE_PERIOD_OVER_PERIOD),
            (REASON_INPUT_UNAVAILABLE, MODE_YEAR_OVER_YEAR),
        )
        for metric_and_mode in (
            f"{METRIC_DELTA_ABSOLUTE}.{mode}",
            f"{METRIC_DELTA_PERCENT}.{mode}",
        )
    }

    result = comparison.derive(package)
    assert isinstance(result, RefusedResult)
    # Not prior_window_absent, which is what iteration order used to yield.
    assert result.reason == REASON_INPUT_UNAVAILABLE
    # And it names the mode it explains, rather than implying it covers both.
    assert result.metric == f"{METRIC_DELTA_ABSOLUTE}.{MODE_YEAR_OVER_YEAR}"


def test_a_derived_fact_inherits_the_caveats_of_the_series_it_read() -> None:
    # The trend excluded rows with no date, which is a limitation of the
    # aggregate these deltas are derived from. RRA-008 requires every derived
    # fact reconciled to its source aggregate, so a delta that dropped the
    # caveat would be presented as covering rows the aggregate never saw.
    package = package_for(
        [
            (date(2026, 1, 1), "1.00"),
            (date(2026, 1, 2), "100.00"),
            (date(2026, 1, 3), "150.00"),
            (date(2026, 1, 4), "1.00"),
        ]
        + [(None, "5.00")]
    )
    assert CAVEAT_UNDATED_ROWS_EXCLUDED in package.trend().caveats
    facts = facts_of(package)
    assert facts
    assert all(CAVEAT_UNDATED_ROWS_EXCLUDED in fact.caveats for fact in facts)


def test_a_high_magnitude_ratio_does_not_abort_the_comparison() -> None:
    # A valid package can hold values large enough that the ratio against a small
    # prior period needs more than Python's default 28 digits. Under that context
    # `quantize` raises InvalidOperation and takes the caller down -- neither a
    # fact nor a governed refusal. The derivation borrows the package's own
    # arithmetic precision, which is what `build_fact_package` computes under.
    # Every value here is admissible: 18 digits is the governed maximum and six
    # decimal places the governed monetary maximum. Four hundred such rows against
    # a millionth-scale prior period is enough to need 29 digits, which is one
    # more than the default context allows.
    largest = "9" * 16 + ".99"
    package = package_for(
        [
            (date(2026, 1, 1), "1.00"),
            (date(2026, 1, 2), "0.000001"),
            *[(date(2026, 1, 3), largest) for _ in range(400)],
            (date(2026, 1, 4), "1.00"),
        ]
    )
    percent = next(
        fact for fact in facts_of(package) if fact.metric == METRIC_DELTA_PERCENT
    )
    # Enormous but stated, rather than an exception escaping the module.
    assert Decimal(percent.value) > Decimal(10) ** 20


def test_the_governed_arithmetic_precision_is_the_packages_own() -> None:
    # Borrowed rather than chosen. If the bound on admissible values is ever
    # wrong, it is wrong in one place instead of two.
    assert comparison.ARITHMETIC_PRECISION == facts.ARITHMETIC_PRECISION


def test_no_fact_claims_a_caveat_this_module_cannot_reach() -> None:
    # A one-period window either has its counterpart or refuses, so there is no
    # shortened window to disclose -- and RRA-008's day-count truncation is not
    # derivable from a period series at all. A governed caveat with no reachable
    # trigger reads as a guarantee that something is being watched.
    assert all(fact.caveats == () for fact in facts_of(monthly(14)))


@pytest.mark.parametrize("metric", [METRIC_DELTA_ABSOLUTE, METRIC_DELTA_PERCENT])
def test_every_emitted_fact_names_a_governed_mode(metric: str) -> None:
    facts = [fact for fact in facts_of(monthly(14)) if fact.metric == metric]
    assert facts
    assert all(comparison.mode_of(fact) is not None for fact in facts)


# --- `rra008.comparison.v2` ------------------------------------------------


def test_this_family_publishes_its_governed_successor() -> None:
    """`V-comparison` opens its own gate, which is part of its definition of done.

    A family commit that published the successor without adding its
    compatibility row would leave the family refusing its own results.
    """
    from khepri.rra.facts import FORMULA_VERSION
    from khepri.rra.versions import admits_family

    assert comparison.COMPARISON_FORMULA_VERSION == "rra008.comparison.v2"
    assert admits_family(
        formula_version=FORMULA_VERSION,
        family_version=comparison.COMPARISON_FORMULA_VERSION,
    )


def test_the_accepted_window_is_available_to_the_family_that_must_consume_it() -> None:
    """`RRA-008`: "Growth consumes the exact PoP window selected by period
    comparison and may not select another."

    Growth re-derived the labels through the same shared rule, which shares the
    rule and not the acceptance. This exposes what comparison *accepted*, so a
    later family consumes a decision rather than reproducing a computation.
    """
    package = monthly(26)

    accepted = comparison.accepted_window(package)

    assert accepted is not None
    assert accepted.current.label != accepted.prior.label


def test_a_package_comparison_refuses_offers_no_window_to_consume() -> None:
    """The half that makes the seam worth having.

    When this family accepts nothing, a consumer must receive nothing -- not the
    labels the shared rule would still have produced.
    """
    assert comparison.accepted_window(monthly(1)) is None


def test_the_partial_window_caveat_is_governed_and_bilingual() -> None:
    """`RRA-008` requires a partial-prefix comparison to carry "the bilingual
    partial-window caveat required by `RRA-009`".

    A caveat with no wording cannot reach a customer, and `RRA-009` enforces
    that structurally: its tables are checked for set equality at import, so a
    code admitted without prose raises rather than rendering blank.
    """
    from khepri.rra.rendering.wording import (
        _GOVERNED_CAVEAT_CODES,
        LANGUAGE_ARABIC,
        LANGUAGE_ENGLISH,
        caveat_message,
    )

    assert comparison.CAVEAT_PARTIAL_WINDOW in _GOVERNED_CAVEAT_CODES

    arabic = caveat_message(comparison.CAVEAT_PARTIAL_WINDOW, language=LANGUAGE_ARABIC)
    english = caveat_message(
        comparison.CAVEAT_PARTIAL_WINDOW, language=LANGUAGE_ENGLISH
    )
    assert arabic and english
    assert arabic != english


def test_a_window_the_manifest_does_not_prove_is_refused() -> None:
    """`RRA-008`: "Sparse, non-contiguous, count-equal, gap-containing,
    scope-mismatched, store-mismatched, or filter-mismatched structures refuse."

    Built without an attestation, so no signature is retained and the comparison
    is unproven rather than compatible. Accepting it would restore the inference
    the signature exists to replace -- and `RRA-008` says so directly: "Without
    an authoritative valid manifest, observed trends may survive but
    completeness-dependent comparison and growth refuse."
    """
    import hashlib

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.profiling import build_profile

    content = HEADER + b"".join(
        f"2026-0{month}-01,100.00,1,INV-{month},Beverages,Cairo\n".encode()
        for month in range(1, 5)
    )
    with published_mapping_identity():
        profile = build_profile(
            content=content,
            media_type=CSV_MEDIA_TYPE,
            source_sha256_hex=hashlib.sha256(content).hexdigest(),
        )
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        unattested = build_fact_package(
            AdmittedInput(
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            )
        )

    assert not unattested.coverage_signatures
    assert comparison.accepted_window(unattested) is None


def test_an_incompatible_window_refuses_for_coverage_not_for_absence() -> None:
    """Four causes reach one `return None`, and they are not the same finding.

    `_window_for` returns nothing when there is no trend, no label pair, no
    counterpart bucket, or -- since `rra008.comparison.v2` -- when the manifest
    does not prove the two windows structurally comparable. Collapsing the last
    into `prior_window_absent` tells a customer "your file covers a single
    period" when it covers several, and points them at re-exporting more history,
    which produces the same refusal again.

    `REASON_COVERAGE_INCOMPATIBLE` was defined by `V-comparison` and left
    unattached; the CAL1-11 sweep is what found it.
    """
    # Four days leave two settled periods, so a label pair exists and a
    # counterpart is found -- every other cause of the `None` is excluded. No
    # manifest, so coverage alone is what is unproven. Measured: the same rows
    # *with* a manifest publish, which is what makes the refusal attributable.
    rows = [
        (date(2026, 1, 5) + timedelta(days=offset), f"{100 + offset * 10}.00")
        for offset in range(4)
    ]
    package = package_for(rows, attested=False)
    assert package.trend() is not None, "a trend must exist, or absence is the honest reason"
    assert not isinstance(comparison.derive(package_for(rows)), RefusedResult), (
        "the attested twin must publish, or the refusal is not about coverage"
    )
    assert not package.coverage_signatures, "the case needs coverage to be unproven"

    refused = comparison.derive(package)
    assert isinstance(refused, RefusedResult), refused
    assert refused.reason == comparison.REASON_COVERAGE_INCOMPATIBLE, refused.reason


def test_a_genuinely_absent_prior_window_still_says_so() -> None:
    """The converse, so the new reason cannot swallow the old one.

    One period cannot settle a pair. Coverage is equally unproven here, and the
    honest finding is still that there is no earlier period to compare against.
    """
    package = package_for([(date(2026, 1, 5), "100.00")], attested=False)
    refused = comparison.derive(package)
    assert isinstance(refused, RefusedResult), refused
    assert refused.reason in {
        comparison.REASON_PRIOR_WINDOW_ABSENT,
        REASON_INPUT_UNAVAILABLE,
    }, refused.reason
