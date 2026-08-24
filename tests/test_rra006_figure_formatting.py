"""How a governed figure is presented, which `RRA-006` requires and did not have.

The scope line requires "accessible tables, units, **formats**". What shipped
reproduced the package's own string verbatim -- `726919.57` for revenue and
`0.8665` for a margin -- because `bundle._renderings` was written to reproduce
rather than reformat, and `rendering/html.py` is deliberately given nothing to
format with. Reproduction is the right rule for *arithmetic*; it is the wrong
rule for *presentation*, and the two were conflated.

**Formatting happens here rather than in a renderer, and that is the whole
point.** `bundle` is where the `Decimal` and its `unit_kind` already sit
together, and it is the single string all four surfaces copy. A renderer that
formatted would be four renderers disagreeing about precision -- exactly the
failure `rendering/html.py`'s docstring refuses. So the renderers still receive
a finished string and still calculate nothing; that string is now readable.

**No currency symbol appears anywhere in this module.** `facts` emits
`CAVEAT_CURRENCY_NOT_DECLARED` for every monetary package precisely because the
currency is not knowable from the upload. Printing `EGP` would assert a fact the
package refuses to assert, so monetary figures are grouped and never marked.
"""

from __future__ import annotations

import hashlib
import re
from decimal import Decimal, Inexact

import pytest

from khepri.rra import bundle as bundle_module
from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    KIND_ROWS,
    KIND_VALUE,
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    PERCENTAGE_METRICS,
    RATE_METRICS,
    ReportBundle,
)
from khepri.rra.facts import (
    RATIO_PRECISION,
    UNIT_COUNT,
    UNIT_MONETARY,
    UNIT_RATIO,
    build_fact_package,
)
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile

#: Values deliberately above the grouping threshold. The golden fixture in
#: `test_rra006_bundle` tops out at `500.00`, which cannot distinguish a grouped
#: rendering from an ungrouped one -- a test built on it would pass either way.
LARGE = (
    b"date,revenue,units,invoice_no,category,branch,cost\n"
    b"2026-01-05,125000.50,1300,INV-1,Beverages,Cairo,40000.00\n"
    b"2026-01-06,90500.00,2400,INV-2,Snacks,Giza,30000.00\n"
    b"2026-01-07,210250.25,5100,INV-3,Beverages,Cairo,70000.00\n"
    # A repeated invoice is what gives the basket family a multi-line
    # transaction, and a second month is what gives the comparison family an
    # earlier period. Without both, the ratio metrics this module classifies are
    # never produced and every check over them passes vacuously.
    b"2026-02-08,150000.00,3000,INV-4,Dairy,Luxor,50000.00\n"
    b"2026-02-09,175000.00,3500,INV-4,Beverages,Cairo,60000.00\n"
)


def package(content: bytes = LARGE):
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )


def figures_of(unit_kind: str, *, kind: str = KIND_VALUE):
    bundle = ReportBundle.of(package())
    return [
        entry
        for entry in bundle.figures
        if entry.unit_kind == unit_kind and entry.kind == kind
    ]


class TestMonetaryFigures:
    def test_a_monetary_figure_is_grouped_in_thousands(self) -> None:
        # `726919.57` is the defect this slice exists for: a six-figure total
        # with no separator reads as a serial number, not money.
        monetary = figures_of(UNIT_MONETARY)
        assert monetary, "the fixture must produce at least one monetary figure"

        grouped = [
            entry
            for entry in monetary
            if len(entry.renderings[LANGUAGE_ENGLISH].split(".")[0].lstrip("-")) > 3
        ]
        assert grouped, "the fixture must produce a figure above the grouping threshold"
        for entry in grouped:
            english = entry.renderings[LANGUAGE_ENGLISH]
            assert "," in english, f"{entry.metric} is not grouped: {english}"

    def test_no_monetary_figure_carries_a_currency_marker(self) -> None:
        # `CAVEAT_CURRENCY_NOT_DECLARED` is emitted for every monetary package
        # because the currency is not knowable. A symbol here would contradict
        # the package's own disclosure.
        for entry in figures_of(UNIT_MONETARY):
            english = entry.renderings[LANGUAGE_ENGLISH]
            for marker in ("EGP", "USD", "$", "£", "€"):
                assert marker not in english, f"{entry.metric} asserts a currency"

    def test_the_decimal_precision_of_a_monetary_figure_is_preserved(self) -> None:
        # Grouping must not become rounding. Two decimal places went in.
        for entry in figures_of(UNIT_MONETARY):
            english = entry.renderings[LANGUAGE_ENGLISH]
            assert re.fullmatch(r"-?[\d,]+\.\d{2}", english), english


class TestCountFigures:
    def test_a_count_is_grouped_and_keeps_no_decimal_part(self) -> None:
        counts = figures_of(UNIT_COUNT)
        assert counts, "the fixture must produce at least one count figure"
        for entry in counts:
            english = entry.renderings[LANGUAGE_ENGLISH]
            assert re.fullmatch(r"-?[\d,]+", english), english

        grouped = [
            entry
            for entry in counts
            if len(entry.renderings[LANGUAGE_ENGLISH].replace(",", "").lstrip("-")) > 3
        ]
        assert grouped, "the fixture must produce a count above the grouping threshold"
        for entry in grouped:
            assert "," in entry.renderings[LANGUAGE_ENGLISH]


class TestRatioFigures:
    def test_a_proportion_is_presented_as_a_percentage(self) -> None:
        # A gross margin of `0.8665` is the single worst cell on the page: it
        # reads as a broken number rather than as 86.65%.
        proportions = [
            entry
            for entry in figures_of(UNIT_RATIO)
            if entry.metric in PERCENTAGE_METRICS
        ]
        assert proportions, "the fixture must produce at least one proportion"
        for entry in proportions:
            english = entry.renderings[LANGUAGE_ENGLISH]
            assert english.endswith("%"), f"{entry.metric} is not a percentage: {english}"
            assert re.fullmatch(r"-?[\d,]+\.\d{2}%", english), english

    def test_a_percentage_is_the_stored_ratio_times_one_hundred(self) -> None:
        # The one arithmetic claim this slice makes, asserted rather than
        # assumed: presentation scales by exactly 100 and rounds to 2 places.
        for entry in figures_of(UNIT_RATIO):
            if entry.metric not in PERCENTAGE_METRICS:
                continue
            shown = entry.renderings[LANGUAGE_ENGLISH]
            percent = float(shown.rstrip("%").replace(",", ""))
            assert abs(percent - float(entry.value) * 100) < 0.005, shown

    def test_a_rate_is_never_presented_as_a_percentage(self) -> None:
        # `basket_items_per_transaction` carries `UNIT_RATIO` but means "items in
        # an average basket". A rich package puts it in the thousands, so scaling
        # it by a hundred prints a six-figure percentage -- not a smaller defect
        # than the `0.8665` this slice set out to fix.
        rates = [
            entry for entry in figures_of(UNIT_RATIO) if entry.metric in RATE_METRICS
        ]
        assert rates, "the fixture must produce at least one rate figure"
        for entry in rates:
            english = entry.renderings[LANGUAGE_ENGLISH]
            assert not english.endswith("%"), f"{entry.metric} scaled to: {english}"

    def test_scaling_a_ratio_by_one_hundred_is_exact(self) -> None:
        # The invariant that makes the percentage form free of any rounding mode,
        # asserted instead of a rounding behaviour. Every ratio-kind fact is
        # quantized to `RATIO_PRECISION` -- four places -- by all four producers,
        # so moving the point two places always lands within two and there is
        # nothing to round. An earlier version of this test asserted half-up on
        # `0.12345`, a five-place input no governed fact can produce: it pinned a
        # branch unreachable in production while leaving the real property
        # unchecked.
        for entry in figures_of(UNIT_RATIO):
            assert entry.value is not None
            places = -entry.value.as_tuple().exponent
            assert places <= RATIO_PRECISION, (entry.metric, entry.value)
            scaled = entry.value * 100
            assert scaled == scaled.quantize(Decimal("0.01")), (entry.metric, scaled)

    def test_the_percentage_form_needs_no_rounding_decision(self) -> None:
        # The direct consequence: `_percentage` is exact on a four-place ratio, so
        # no rounding mode is chosen here and none has to agree with the mode the
        # fact boundary already applied.
        assert bundle_module._percentage("0.8665") == "86.65%"

    def test_a_high_magnitude_ratio_renders_rather_than_aborting(self) -> None:
        # The precision half of the exactness context, and the reason it is not
        # `Context()`'s default 28. A comparison against a very small prior period
        # is admissible and produces a ratio needing more than 28 digits --
        # `test_rra008_comparison.py::test_a_high_magnitude_ratio_does_not_abort_
        # the_comparison` builds one from 18-digit values and six governed decimal
        # places. Scaling it by a hundred under a 28-digit context raises
        # `InvalidOperation`, which takes `ReportBundle.of` down: neither a fact
        # nor a governed refusal, and the one outcome this module may not produce.
        #
        # Twenty-nine significant digits, shaped as a governed ratio: quantized to
        # `RATIO_PRECISION`, so the scaling itself is still exact.
        enormous = "3999999999999999600000000.0000"
        assert len(Decimal(enormous).as_tuple().digits) > 28, (
            "this input must exceed the default context to be the case at issue"
        )
        assert bundle_module._percentage(enormous).endswith("%")

    def test_a_negative_with_a_zero_whole_part_keeps_its_sign(self) -> None:
        # `int("-0")` is `0`, so grouping through the integer dropped the sign of
        # every negative between -1 and 0. A monetary decrease of half a unit was
        # published as an increase, on every surface, because they all copy this
        # string. Governed figures reach this range routinely: an absolute revenue
        # delta, a growth effect, a negative gross profit.
        assert bundle_module._grouped("-0.50") == "-0.50"
        assert bundle_module._grouped("-0.0001") == "-0.0001"
        # And the sign survives grouping proper, which was never broken.
        assert bundle_module._grouped("-1234.56") == "-1,234.56"
        # A positive is unchanged, so the fix is not a blanket prefix.
        assert bundle_module._grouped("0.50") == "0.50"

    def test_a_small_negative_ratio_is_not_published_as_a_gain(self) -> None:
        # The consequence at the percentage path, which scales before grouping:
        # `-0.0001` is a tenth of a percent down and was printed as `0.01%` up.
        assert bundle_module._percentage("-0.0001") == "-0.01%"
        assert bundle_module._percentage("-0.5000") == "-50.00%"

    def test_the_arabic_rendering_uses_the_arabic_percent_sign(self) -> None:
        # The rest of the Arabic string already leaves ASCII behind -- Arabic-Indic
        # digits, `٫` for the decimal point, `٬` for the group separator. An ASCII
        # `%` on the end produced a mixed-script figure, and the percent sign is
        # not the place to stop having committed to the rest.
        arabic = bundle_module._renderings(
            "0.8665", unit_kind=UNIT_RATIO, kind=KIND_VALUE, metric="gross_margin"
        )[LANGUAGE_ARABIC]

        assert arabic == "٨٦٫٦٥٪"
        assert "%" not in arabic

    def test_the_scaling_itself_runs_at_the_governed_precision(self) -> None:
        # The other half, and the subtler one. Passing `context=` to `quantize`
        # governs the quantize only: `parsed * 100` would still run under the
        # ambient 28-digit context and round a high-magnitude ratio *before* the
        # exactness trap could inspect it. The quantize is then exact on an
        # already-damaged value, so nothing raises and nothing looks wrong.
        #
        # This ratio is what 400 rows of `9999999999999999.98` against a prior of
        # `0.000003` produces -- every input admissible, the ratio quantized to
        # `RATIO_PRECISION` as every producer quantizes it.
        governed = "1333333333333333330666665.6667"
        rendered = bundle_module._percentage(governed)

        # Scaling by a hundred moves the point two places and nothing else.
        assert rendered == "133,333,333,333,333,333,066,666,566.67%"
        # The specific corruption this guards: a trailing `.70` instead of `.67`.
        assert not rendered.endswith("566.70%")

    def test_a_fifth_place_raises_rather_than_rounding_unheard(self) -> None:
        # The guard the two tests above rely on, fired rather than assumed. No
        # governed producer emits five places, so nothing reaches this in
        # production -- which is exactly why it needs its own proof: an
        # unreachable guard is indistinguishable from an absent one until the
        # day it is reached.
        #
        # Without the trapped context this returns "86.66%": `Decimal`'s default
        # context does not trap `Inexact`, so a five-place ratio is rounded
        # half-even and printed with no signal. That silent path is the defect
        # this asserts is closed.
        with pytest.raises(Inexact):
            bundle_module._percentage("0.86655")
        assert bundle_module._percentage("1.0000") == "100.00%"
        assert bundle_module._percentage("0.0001") == "0.01%"


class TestTheRatioClassificationIsComplete:
    def test_every_ratio_metric_a_package_produces_is_classified(self) -> None:
        # The emptiness assertion that stops `PERCENTAGE_METRICS` from
        # self-disarming. An allowlist nobody is forced to extend silently
        # mis-formats the next ratio metric somebody adds -- it would render as a
        # plain number with no test objecting. This fails when that happens, and
        # names the metric.
        produced = {
            entry.metric
            for entry in ReportBundle.of(package()).figures
            if entry.unit_kind == UNIT_RATIO
        }
        assert produced, "the fixture must produce ratio figures for this to check"

        classified = PERCENTAGE_METRICS | RATE_METRICS
        unclassified = produced - classified
        assert not unclassified, (
            f"unclassified ratio metrics: {sorted(unclassified)} -- add each to "
            "PERCENTAGE_METRICS (a 0-1 proportion) or RATE_METRICS (a rate)"
        )


class TestTheArabicRendering:
    def test_the_arabic_form_transliterates_the_grouping_separator(self) -> None:
        # `_arabic_character` already maps `,` and `.`; this holds it to doing so
        # now that a grouped string actually contains a separator to map.
        bundle = ReportBundle.of(package())
        grouped = [
            entry
            for entry in bundle.figures
            if "," in entry.renderings[LANGUAGE_ENGLISH]
        ]
        assert grouped, "the fixture must produce a grouped figure"
        for entry in grouped:
            arabic = entry.renderings[LANGUAGE_ARABIC]
            assert "٬" in arabic, f"ASCII separator survived: {arabic}"
            assert "," not in arabic

    def test_the_arabic_form_carries_the_same_digits_as_the_english_one(self) -> None:
        # Replaces the old `len(ar) == len(en)` check, which was how rounding was
        # detected and which grouping legitimately breaks. Comparing the digit
        # sequences catches a dropped or rounded digit without depending on how
        # many separators each script uses.
        bundle = ReportBundle.of(package())
        for entry in bundle.figures:
            english = entry.renderings[LANGUAGE_ENGLISH]
            arabic = entry.renderings[LANGUAGE_ARABIC]
            ascii_digits = [c for c in english if c.isdigit()]
            arabic_digits = [c for c in arabic if "٠" <= c <= "٩"]
            assert len(ascii_digits) == len(arabic_digits), f"{english} vs {arabic}"


class TestProvenanceSurvivesFormatting:
    def test_the_raw_decimal_is_still_carried_beside_the_formatted_string(self) -> None:
        # The percentage form no longer equals the stored value, so the exact
        # `Decimal` has to remain reachable or reconciliation loses its anchor.
        for entry in ReportBundle.of(package()).figures:
            assert entry.value is not None
            assert isinstance(repr(entry.value), str)

    def test_every_figure_still_names_the_fact_it_came_from(self) -> None:
        for entry in ReportBundle.of(package()).figures:
            assert entry.fact_id
            assert entry.citation_id

    def test_a_row_count_figure_is_never_presented_as_a_percentage(self) -> None:
        # `KIND_ROWS` figures share their owner's `unit_kind`, so a ratio-owned
        # row count would be scaled by 100 and printed as `28200.00%` if the
        # formatter dispatched on unit alone. Row counts are counts.
        for entry in figures_of(UNIT_RATIO, kind=KIND_ROWS):
            english = entry.renderings[LANGUAGE_ENGLISH]
            assert not english.endswith("%"), english
            assert re.fullmatch(r"-?[\d,]+", english), english
