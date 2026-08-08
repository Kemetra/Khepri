"""Which business worksheet presents which governed figures.

**Why this is a table and not a function.** RRA-009 requires business worksheets
be "named by business meaning rather than from a section identifier", which puts a
presentation grouping between the bundle's five governed sections and the
workbook's sheets. That grouping is a decision about what a customer reads
together, so it is written down once, where a reviewer can check it, rather than
distributed through a writer that computes it.

**It regroups and never recomputes.** Every metric named here is a metric the
bundle produced, and every figure a sheet lists is the string the fact package
rendered. `KHEPRI-DEC-005` forbids a surface calculating anything, and `excel.py`
holds that line for the whole module.

**Several sheets present one governed section under different business names.**
`Profitability` and `Discounts and Returns` both draw on `overview`, because the
bundle has no profitability section and RRA-009 excludes adding one -- "Any new
figure, aggregate, analysis family, metric, or chart kind". The information
architecture adopted the same route for `Branch Performance`, which re-presents
`concentration`'s ranked buckets under a business name. This is presentation, not
a new analysis: the figures are the same figures, so a sheet can never disagree
with the section that computed them.

That fan-out is why `excel.py` resolves a chart's target sheet from an ordered
list rather than a section-keyed mapping: four sheets name `overview`, and a dict
would keep only the last of them.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra import facts
from khepri.rra.analysis import growth

# Excel caps a worksheet name at 31 characters and XlsxWriter raises at 32
# (measured: 31 accepted, 32 raises `InvalidWorksheetName`). Both governed
# language suffixes -- " (English)" and " (العربية)" -- are exactly 10
# characters, so the budget is symmetric.
SHEET_NAME_SUFFIX_WIDTH = 10
EXCEL_SHEET_NAME_LIMIT = 31
MAX_SHEET_NAME_BUDGET = EXCEL_SHEET_NAME_LIMIT - SHEET_NAME_SUFFIX_WIDTH


@dataclass(frozen=True, slots=True)
class BusinessSheet:
    """One business worksheet: what it is called, and what it presents.

    `key` is a stable identifier for the sheet rather than a name a reader sees;
    `wording.BUSINESS_SHEET_NAMES` holds the per-language names. Keeping them
    apart is what lets the name be a wording decision and the layout be a
    presentation decision.
    """

    key: str
    section: str
    metrics: tuple[str, ...]


SHEET_EXECUTIVE_SUMMARY = "executive_summary"
SHEET_SALES_PERFORMANCE = "sales_performance"
SHEET_PERIOD_COMPARISON = "period_comparison"
SHEET_GROWTH_DRIVERS = "growth_drivers"
SHEET_PROFITABILITY = "profitability"
SHEET_DISCOUNTS_AND_RETURNS = "discounts_and_returns"
SHEET_BRANCH_PERFORMANCE = "branch_performance"
SHEET_BASKET = "basket"

# Reading order, and it is the information architecture: worksheet order is what a
# reader sees on opening the file. Business sheets first, in the order the report
# reads; the audit sheets `excel.py` appends come after all of them.
BUSINESS_SHEETS: tuple[BusinessSheet, ...] = (
    BusinessSheet(
        key=SHEET_EXECUTIVE_SUMMARY,
        section="overview",
        metrics=(
            facts.METRIC_REVENUE,
            facts.METRIC_TRANSACTIONS,
            facts.METRIC_UNITS,
            facts.METRIC_AVERAGE_ORDER_VALUE,
        ),
    ),
    BusinessSheet(
        key=SHEET_SALES_PERFORMANCE,
        section="overview",
        metrics=(
            facts.METRIC_AVERAGE_SELLING_PRICE,
            "revenue_by_period",
            "units_by_period",
        ),
    ),
    BusinessSheet(
        key=SHEET_PERIOD_COMPARISON,
        section="comparison",
        metrics=("revenue_delta_absolute", "revenue_delta_percent"),
    ),
    BusinessSheet(
        key=SHEET_GROWTH_DRIVERS,
        section="growth",
        metrics=growth.GOVERNED_METRICS,
    ),
    BusinessSheet(
        key=SHEET_PROFITABILITY,
        section="overview",
        metrics=(
            facts.METRIC_COST,
            facts.METRIC_GROSS_PROFIT,
            facts.METRIC_GROSS_MARGIN,
        ),
    ),
    BusinessSheet(
        key=SHEET_DISCOUNTS_AND_RETURNS,
        section="overview",
        metrics=(facts.METRIC_DISCOUNT, facts.METRIC_RETURNS),
    ),
    BusinessSheet(
        key=SHEET_BRANCH_PERFORMANCE,
        section="concentration",
        metrics=(
            "revenue_by_product",
            "units_by_product",
            "concentration_ranked_values",
            "concentration_distinct_values",
            "concentration_top_decile_share",
            "concentration_top_quartile_share",
            "concentration_curve",
        ),
    ),
    BusinessSheet(
        key=SHEET_BASKET,
        section="basket",
        metrics=("basket_items_per_transaction", "basket_attach_rate"),
    ),
)


def sheet_for(metric: str) -> BusinessSheet | None:
    """Which business sheet presents one metric, if any presents it."""
    for sheet in BUSINESS_SHEETS:
        if metric in sheet.metrics:
            return sheet
    return None
