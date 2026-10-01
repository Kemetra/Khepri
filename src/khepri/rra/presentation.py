"""How a supplied figure is written in each language: the one form every table prints.

Moved out of `bundle` unchanged (SCRUM-26 A9(b)) so that `narrative` can supply the same form
to a provider. `RRA-005` as amended by `#637` requires prose to state each figure in the display
form the report's own tables give it in that language, and a second implementation of that form
is how "the same" would drift. `bundle` imports `narrative`, so the form had to live below both.

This module knows no language code. `forms` returns the English and the Arabic form in that
order, and each caller keys them with its own governed language constants.
"""

from __future__ import annotations

from decimal import (
    Context,
    Decimal,
    DivisionByZero,
    Inexact,
    InvalidOperation,
    Overflow,
    localcontext,
)

from khepri.rra.facts import ARITHMETIC_PRECISION, UNIT_RATIO

# Arabic-Indic digits and the separators that accompany them.
_ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
_ARABIC_DECIMAL = "٫"
_ARABIC_GROUP = "٬"
#: `U+066A ARABIC PERCENT SIGN`, the counterpart of the separators above. The
#: ratio scaling appends an ASCII `%`, and leaving it there produced a
#: mixed-script `٨٦٫٦٥%` -- Arabic-Indic digits with an Arabic decimal separator
#: and an Arabic group separator, then a Latin sign. Having committed to the
#: Arabic numeric conventions for the rest of the string, the percent sign is
#: not the place to stop.
_ARABIC_PERCENT = "٪"
_ASCII_DIGITS = "0123456789"


def forms(
    text: str,
    *,
    unit_kind: str | None = None,
    counts_rows: bool = False,
    metric: str | None = None,
) -> tuple[str, str]:
    """The one English and one Arabic form of a supplied figure, in that order.

    The English rendering keeps the precision the fact was computed to and adds
    only what makes it legible: digit grouping, and a percent sign for a ratio.
    **`RRA-006` requires "units, formats"** in the same scope line that requires
    accessible tables, and an ungrouped `726919.57` beside a margin printed as
    `0.8665` satisfies neither. The earlier rule here was to reproduce the
    package's string verbatim, on the ground that re-rendering would make this
    module decide a governed figure's precision. That ground is sound and is
    kept: grouping inserts separators and the ratio scaling is exact, so the
    significant digits crossing this function are the ones that entered it.

    **Formatted here rather than in a renderer, deliberately.** This is the one
    place the `Decimal` and its `unit_kind` sit together, and the single string
    all four surfaces copy. `rendering/html.py` refuses to format because four
    renderers formatting independently is four renderers disagreeing about
    precision; that refusal only holds if the string reaching them is already
    the finished one.

    **No currency marker, at any unit.** The reason stated here was that `facts`
    appends `CAVEAT_CURRENCY_NOT_DECLARED` to *every* package carrying a
    monetary fact, so a symbol would assert what that caveat exists to
    disclaim. That has not been true since `rra004.package.v3`: `facts`
    attaches it only when the package declares no currency, because a package
    stating both `EGP` and "currency not declared" contradicts itself in front
    of the customer.

    The rule stands on the narrower ground that remains. A `v3` package that
    *does* declare a currency carries one currency for the whole document, and
    this function formats a single figure with no access to it -- so a symbol
    here would still be this layer asserting something it cannot read, and four
    renderers would each need the same fact to agree.

    Whether a declared currency *should* reach the formatted string is a
    governed question rather than a docstring edit: it would change what
    `RRA-009` renders, and it is adjacent to the open `CAL1` `P2` finding that
    `CAVEAT_CURRENCY_NOT_DECLARED` is now unreachable on the declared path.
    Recorded, not decided (`#507` item 4).

    `unit_kind` is optional so a caller with no unit in hand -- a label, a
    timestamp, anything that is not a measured quantity -- gets the previous
    verbatim behaviour rather than a guess.
    """
    english = presented(text, unit_kind=unit_kind, counts_rows=counts_rows, metric=metric)
    return english, arabic(english)


#: The `UNIT_RATIO` metrics that are *proportions* and therefore presentable as
#: percentages, named rather than inferred.
#:
#: **`unit_kind` does not carry this distinction, and cannot be made to here.**
#: `basket._fact` stamps `UNIT_RATIO` on both of its metrics through one helper:
#: `basket_attach_rate` is a proportion of transactions, while
#: `basket_items_per_transaction` is a *rate* -- 3.6667 items in an average
#: basket. Scaling the second by a hundred prints `366.67%`, which is not a
#: smaller defect than the `0.8665` this slice set out to fix. The honest
#: long-term fix is a fourth unit kind on `Fact`, which is an `RRA-004` change to
#: a digested document and not something a presentation slice may make; this
#: allowlist is the bounded form, and it fails *closed*.
#:
#: A ratio metric absent from this set renders as a plain grouped number, which
#: is wrong-looking rather than wrong. `test_every_ratio_metric_is_classified`
#: enumerates what a rich package actually produces and fails when a new one
#: appears, because an allowlist nobody is forced to extend is an allowlist that
#: silently mis-formats the next metric added.
PERCENTAGE_METRICS = frozenset(
    {
        "gross_margin",
        "revenue_delta_percent",
        "concentration_top_decile_share",
        "concentration_top_quartile_share",
        "concentration_curve",
        "basket_attach_rate",
    }
)

#: The `UNIT_RATIO` metrics that are rates rather than proportions, named so the
#: coverage test can tell "classified as not-a-percentage" from "forgotten".
#:
#: `basket_items_per_transaction` is the whole reason this pair of sets exists: a
#: rich package renders it as `3825.0000` items per basket, which as a percentage
#: is `382500.00%`.
RATE_METRICS = frozenset({"basket_items_per_transaction"})


def presented(
    text: str, *, unit_kind: str | None, counts_rows: bool = False, metric: str | None = None
) -> str:
    """Group a figure's digits, and scale a ratio to a percentage.

    **A row count is a count whatever it counts.** A row count (`bundle.KIND_ROWS`) inherits
    its owner's `unit_kind`, so dispatching on unit alone would take the row
    count beside a margin and print `28200.00%`. The kind is checked first for
    that reason, and the check is not defensive: `_bucket` builds exactly such a
    pair on every aggregated fact.

    A value this cannot parse is returned untouched. Refusing would turn a
    presentation concern into a bundle failure, and the caller already treats a
    non-numeric figure as legitimate -- `_parsed` returns `None` for one.
    """
    if counts_rows:
        return grouped(text)
    if unit_kind == UNIT_RATIO and metric in PERCENTAGE_METRICS:
        return percentage(text)
    return grouped(text)


def grouped(text: str) -> str:
    """Insert thousands separators, preserving the sign and decimal places as given.

    **The sign is carried explicitly because `int` loses it on a zero whole
    part.** `int("-0")` is `0`, so grouping `-0.50` through the integer produced
    `0.50` and a decrease was published as an increase -- on a monetary delta, a
    growth effect, or, after scaling, a `-0.0001` ratio printed as `0.01%`. Every
    surface copies this string, so the sign had to survive here or nowhere.
    """
    parsed = _parsed(text)
    if parsed is None:
        return text
    stripped = text.strip()
    whole, _, fraction = stripped.lstrip("+-").partition(".")
    try:
        grouped = f"{int(whole):,}"
    except ValueError:
        return text
    if stripped.startswith("-"):
        grouped = f"-{grouped}"
    return f"{grouped}.{fraction}" if fraction else grouped


#: The context `_percentage` quantizes in: exact or nothing, at the governed
#: arithmetic precision.
#:
#: **A bare `quantize` does not raise, and the comment that said so was wrong.**
#: `Decimal`'s default context traps `InvalidOperation`, `DivisionByZero` and
#: `Overflow` but not `Inexact`, so a five-place ratio would have been rounded
#: half-even and printed without a word -- `0.86655` as `86.66%`. That is a mode
#: chosen by inheritance, which is the thing this module declines to do
#: deliberately. Trapping `Inexact` makes the exactness claim enforced rather
#: than asserted: the quantize either drops trailing zeros the scaling produced
#: or it raises.
#:
#: The other three traps are carried over from the default context, because
#: `Context(traps=...)` replaces the trap set rather than adding to it.
#:
#: **`prec` is the governed arithmetic precision, not `Context`'s default 28.**
#: A comparison against a very small prior period is admissible and produces a
#: ratio needing more than 28 digits -- `test_a_high_magnitude_ratio_does_not_
#: abort_the_comparison` builds one from 18-digit values and six governed decimal
#: places, which is 29. Scaling that by a hundred and quantizing under a 28-digit
#: context raises `InvalidOperation` and takes `ReportBundle.of` down with it:
#: neither a fact nor a governed refusal, which is the one outcome this module
#: may not produce. `facts` already computes under `ARITHMETIC_PRECISION` for the
#: same reason; presentation borrows it rather than silently narrowing it.
_EXACT = Context(
    prec=ARITHMETIC_PRECISION,
    traps=[Inexact, InvalidOperation, DivisionByZero, Overflow],
)


def percentage(text: str) -> str:
    """Scale a stored ratio to a percentage at two decimal places.

    **Exact, and therefore free of any rounding mode.** Every ratio-kind fact is
    quantized to `facts.RATIO_PRECISION` -- four places -- by all four producers
    (`facts`, `analysis.basket`, `analysis.comparison`, `analysis.concentration`),
    so multiplying by a hundred moves the point two places and always lands
    within two: `0.8665` is `86.65%` and `1.0000` is `100.00%`, with nothing to
    round away. `test_scaling_a_ratio_by_one_hundred_is_exact` asserts that
    invariant rather than a rounding behaviour, because a rounding mode chosen
    here would be a second rounding on top of the one the fact boundary already
    performed -- and the mode would then have to agree with a decision this
    module does not own.

    `_EXACT` enforces that rather than trusting it. If a producer ever emits a
    fifth place, this raises `Inexact` instead of half-even rounding a governed
    margin behind the reader's back.

    The stored `Decimal` stays on the figure's `value`, which is what
    reconciliation and the audit trail read: the percentage is presentation, and
    the figure it was derived from remains addressable.
    """
    parsed = _parsed(text)
    if parsed is None:
        return text
    # **Both operations inside the context, not just the quantize.** Passing
    # `context=` to `quantize` alone leaves `parsed * 100` running under the
    # ambient 28-digit context, where a high-magnitude ratio is rounded *before*
    # the trap can inspect it: a governed `…566.6667` scaled to `…566.70%`
    # instead of `…566.67%`, silently, because the quantize it was handed was
    # then exact on an already-damaged value.
    with localcontext(_EXACT):
        scaled = (parsed * 100).quantize(Decimal("0.01"))
    return f"{grouped(str(scaled))}%"


def arabic(text: str) -> str:
    return "".join(_arabic_character(character) for character in text)


def _arabic_character(character: str) -> str:
    if character in _ASCII_DIGITS:
        return _ARABIC_DIGITS[_ASCII_DIGITS.index(character)]
    if character == ".":
        return _ARABIC_DECIMAL
    if character == ",":
        return _ARABIC_GROUP
    if character == "%":
        return _ARABIC_PERCENT
    return character


def _parsed(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", ""))
    except InvalidOperation:
        return None
