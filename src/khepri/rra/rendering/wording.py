"""The governed per-language wording that more than one surface has to agree on.

**Why a module rather than each surface's own chrome.** Most of a surface's furniture
is its own: a web page needs a skip link and a workbook does not. But three kinds of
wording are read by two or three surfaces at once -- what a section is called, what a
chart kind does, and what a plotted mark is named -- and every copy of those is a place
the surfaces can drift apart. A section titled one thing on the page and another in the
spreadsheet is one report making two claims about what a reader is looking at.

**Chart categories are the case that forced this.** A mark is named either by the
customer's own category -- a product, a branch -- or, when the figure has no category,
by a governed code standing for its metric or its comparison mode. `category_of` makes
that choice; `LABEL_WORDING` says what each code means. Those two lived in different
modules, the codes minted in `rendering.charts` and the wording in `rendering.html`'s
chrome, with nothing tying them together: a new code could be minted with nowhere to be
translated, and the failure surfaced only when a reader loaded the page --
`StrictUndefined` raising, or worse, `metric.growth_price_effect` reaching an Arabic
axis. Holding both here makes that tie structural, and lets a test assert that every
code `category_of` can produce has wording in both languages.

**This module invents no arithmetic and reads no value.** It is handed a figure and
returns a name. The number a mark is drawn at comes from the figure's own `Decimal` and
its authoritative text from the figure's own rendering; neither is touched here.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra import facts
from khepri.rra.analysis import growth
from khepri.rra.bundle import (
    GOVERNED_FIGURE_LABELS,
    ORDERED_SECTIONS,
    CitedFigure,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH


@dataclass(frozen=True, slots=True)
class ChartCategory:
    """A mark's name, and whether the surface must translate it before showing it.

    Two kinds of text reach an axis and they must not be confused. A bucket figure
    carries the customer's own product or branch name, which is final and only needs
    escaping. A scalar figure -- a growth price effect, say -- has no category, and
    its *metric* is what identifies the mark; that name is governed wording, so it is
    a code the surface resolves through `LABEL_WORDING`.

    A bare string could not tell those apart, and a surface guessing would either
    print `metric.growth_price_effect` at a reader or run a customer's product name
    through a translation table.
    """

    value: str
    localize: bool


# Every governed code `category_of` can return, in both languages. One table with one
# key set per language, so wording added to one cannot be silently missing from the
# other -- the same discipline the surfaces' own chrome tables follow.
LABEL_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "metric.growth_revenue_change": "Revenue change",
        "metric.growth_price_effect": "Price effect",
        "metric.growth_volume_effect": "Volume effect",
        "label.period_over_period": "Against the previous period",
        "label.year_over_year": "Against the same period last year",
    },
    LANGUAGE_ARABIC: {
        "metric.growth_revenue_change": "التغيّر في الإيرادات",
        "metric.growth_price_effect": "أثر السعر",
        "metric.growth_volume_effect": "أثر الحجم",
        "label.period_over_period": "مقابل الفترة السابقة",
        "label.year_over_year": "مقابل الفترة نفسها من العام الماضي",
    },
}

# Business names for the governed metric codes. These are separate from
# `LABEL_WORDING`: a metric name is report prose, while a label names a chart mark
# or comparison mode. The renderers consume these strings without touching the
# figure's value, so this table adds presentation vocabulary and no arithmetic.
METRIC_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "revenue": "Revenue",
        "units": "Units sold",
        "transactions": "Number of sales",
        "average_order_value": "Average sale value",
        "average_selling_price": "Average selling price",
        "cost": "Cost of goods sold",
        "gross_profit": "Gross profit",
        "gross_margin": "Gross margin",
        "discount": "Discounts given",
        "returns": "Returns",
        "growth_revenue_change": "Total revenue change",
        "growth_price_effect": "Effect of price changes",
        "growth_volume_effect": "Effect of volume changes",
    },
    LANGUAGE_ARABIC: {
        "revenue": "الإيرادات",
        "units": "الوحدات المبيعة",
        "transactions": "عدد المبيعات",
        "average_order_value": "متوسط قيمة البيع",
        "average_selling_price": "متوسط سعر البيع",
        "cost": "تكلفة المبيعات",
        "gross_profit": "إجمالي الربح",
        "gross_margin": "هامش الربح الإجمالي",
        "discount": "الخصومات الممنوحة",
        "returns": "المرتجعات",
        "growth_revenue_change": "إجمالي تغير الإيرادات",
        "growth_price_effect": "أثر تغير الأسعار",
        "growth_volume_effect": "أثر تغير الكميات",
    },
}

_FACT_METRIC_CODES = {
    facts.METRIC_REVENUE,
    facts.METRIC_UNITS,
    facts.METRIC_TRANSACTIONS,
    facts.METRIC_AVERAGE_ORDER_VALUE,
    facts.METRIC_AVERAGE_SELLING_PRICE,
    facts.METRIC_COST,
    facts.METRIC_GROSS_PROFIT,
    facts.METRIC_GROSS_MARGIN,
    facts.METRIC_DISCOUNT,
    facts.METRIC_RETURNS,
}
_GOVERNED_METRIC_CODES = _FACT_METRIC_CODES | set(growth.GOVERNED_METRICS)

if set(METRIC_WORDING) != {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}:
    raise RuntimeError("metric business names must cover every governed language")

for _language, _wording in METRIC_WORDING.items():
    if set(_wording) != _GOVERNED_METRIC_CODES:
        raise RuntimeError("every governed metric needs a business name in every language")


def metric_business_name(metric: str, language: str) -> str:
    """Return a metric's business name, refusing unknown codes or languages."""
    return METRIC_WORDING[language][metric]


# Customer-facing refusal messages -- docs/reporting/refusal-presentation.md §D.
# Two tiers are required because a section refusal loses a whole analysis, while a
# result refusal loses one metric and leaves the section standing. Each message
# states what was unavailable, why, whether the rest of the report is unaffected,
# which field would fix it, and how. The result tier is filled by the next slice.
REFUSAL_WORDING: dict[str, dict[str, dict[str, str]]] = {
    "section": {
        LANGUAGE_ENGLISH: {
            "prior_window_absent": (
                "Comparison with an earlier period — not available. Your file "
                "covers a single period, so there is no earlier period inside it "
                "to compare against. Everything else in this review is unaffected "
                "and describes the period you supplied. To add comparison, export "
                "a file that also covers the period you want to compare with — "
                "the same months a year earlier, or the months immediately before."
            ),
            "required_input_unavailable": (
                "This analysis — not available. The figures this analysis needs "
                "are not present in the file. The rest of the review is "
                "unaffected. Include the missing column in your export and this "
                "becomes available."
            ),
            "aggregate_unavailable": (
                "Sales concentration — not available. The totals this analysis "
                "is built from could not be produced from the supplied rows. The "
                "rest of the review is unaffected."
            ),
            "distinct_set_uncomputable": (
                "Sales concentration — not available. Concentration compares "
                "each product or branch against all the others, and the file "
                "does not identify them distinctly enough to separate one from "
                "another. The rest of the review is unaffected. Export with a "
                "consistent product or branch name in every row and this "
                "becomes available."
            ),
            "units_absent": (
                "Growth drivers — not available. Splitting growth into price "
                "and volume needs a quantity for each sale, and the file has "
                "none. Revenue figures are unaffected — the review still shows "
                "how much revenue changed, but not how much of that change came "
                "from price rather than from volume. Include the quantity sold "
                "in your export and this becomes available."
            ),
            "decomposition_not_additive": (
                "Growth drivers — withheld. Price and volume effects were "
                "calculated, but they do not add up to the total revenue "
                "change. Rather than present a split that does not reconcile, "
                "it is withheld. Revenue figures are unaffected and remain "
                "correct. This usually means quantities and revenue in the "
                "file are measured over different sets of rows."
            ),
            "transaction_identifier_absent": (
                "Basket size — not available. Your file has no receipt or "
                "invoice number, so there is no way to tell which rows belong "
                "to the same sale. Counting rows instead would overstate "
                "basket size wherever one sale spans several lines. The rest "
                "of the review is unaffected. Export with the receipt number "
                "included and this becomes available."
            ),
            "incomplete_transaction_identifiers": (
                "Basket size — not available. Some rows carry a receipt number "
                "and some do not. Basket size calculated from the rows that "
                "have one would describe part of your sales and be presented "
                "as if it described all of them. The rest of the review is "
                "unaffected. Export with a receipt number on every row and "
                "this becomes available."
            ),
        },
        LANGUAGE_ARABIC: {
            "prior_window_absent": (
                "المقارنة بفترة سابقة — غير متاحة. يغطي ملفك فترة واحدة، فلا "
                "توجد داخله فترة أسبق للمقارنة بها. وما عدا ذلك في هذا التقرير "
                "غير متأثر، وهو يوصف الفترة التي قدّمتها. ولإتاحة المقارنة، "
                "صدِّر ملفاً يغطي أيضاً الفترة التي تريد المقارنة بها — الأشهر "
                "نفسها من العام السابق، أو الأشهر التي تسبقها مباشرة."
            ),
            "required_input_unavailable": (
                "هذا التحليل — غير متاح. الأرقام التي يحتاجها هذا التحليل غير "
                "موجودة في الملف. وما عدا ذلك في التقرير غير متأثر. أضِف العمود "
                "الناقص إلى ملف التصدير ليصبح هذا التحليل متاحاً."
            ),
            "aggregate_unavailable": (
                "تركّز المبيعات — غير متاح. الإجماليات التي يُبنى عليها هذا "
                "التحليل لم يتسنَّ إنتاجها من الصفوف المقدَّمة. وما عدا ذلك في "
                "التقرير غير متأثر."
            ),
            "distinct_set_uncomputable": (
                "تركّز المبيعات — غير متاح. يقارن تحليل التركّز كل منتج أو فرع "
                "بالبقية، والملف لا يحدّد هويتها بدرجة تكفي للتمييز بينها. وما "
                "عدا ذلك في التقرير غير متأثر. صدِّر الملف باسم منتج أو فرع "
                "ثابت في كل صف ليصبح هذا التحليل متاحاً."
            ),
            "units_absent": (
                "محرّكات النمو — غير متاحة. يحتاج تقسيم النمو إلى سعر وكمية إلى "
                "كمية مبيعة لكل عملية، وهي غير موجودة في الملف. أرقام الإيرادات "
                "غير متأثرة — يبيّن التقرير مقدار تغيّر الإيرادات، لكن لا يبيّن "
                "ما جاء منه من السعر وما جاء من الكمية. أضِف الكمية المبيعة إلى "
                "ملف التصدير ليصبح هذا التحليل متاحاً."
            ),
            "decomposition_not_additive": (
                "محرّكات النمو — محجوبة. حُسب أثر السعر وأثر الكمية، لكن مجموعهما "
                "لا يساوي إجمالي تغيّر الإيرادات. وبدلاً من عرض تقسيم لا يتوازن، "
                "حُجب. أرقام الإيرادات غير متأثرة وتبقى صحيحة. وغالباً ما يعني "
                "ذلك أن الكميات والإيرادات في الملف مقيسة على مجموعتين مختلفتين "
                "من الصفوف."
            ),
            "transaction_identifier_absent": (
                "حجم سلة الشراء — غير متاح. لا يحتوي ملفك على رقم فاتورة أو "
                "إيصال، فلا توجد طريقة لمعرفة أي الصفوف تنتمي إلى البيع نفسه. "
                "وعدّ الصفوف بدلاً من ذلك سيضخّم حجم السلة في كل بيع يمتد على "
                "عدة أسطر. وما عدا ذلك في التقرير غير متأثر. صدِّر الملف مع رقم "
                "الإيصال ليصبح هذا التحليل متاحاً."
            ),
            "incomplete_transaction_identifiers": (
                "حجم سلة الشراء — غير متاح. بعض الصفوف تحمل رقم إيصال وبعضها لا "
                "يحمله. وحجم السلة المحسوب من الصفوف التي تحمله يوصف جزءاً من "
                "مبيعاتك ويُعرض كأنه يوصفها كلها. وما عدا ذلك في التقرير غير "
                "متأثر. صدِّر الملف مع رقم إيصال في كل صف ليصبح هذا التحليل "
                "متاحاً."
            ),
        },
    },
    "result": {},
}


def refusal_message(reason: str, *, context: str, language: str) -> str:
    """Return the customer message for one refusal reason at one tier.

    Unknown reason codes, tiers, and languages raise instead of falling back to
    internal identifiers or wording from the wrong refusal context.
    """
    return REFUSAL_WORDING[context][language][reason]


# What each governed section is called. The page shows it as a heading, the printed
# report as the heading a page break lands before, and the workbook as the title of the
# chart drawn on that section's sheet -- which is also what makes that chart accessible:
# an embedded object with no programmatic text tells a screen reader nothing about which
# analysis it belongs to.
SECTION_HEADINGS: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "overview": "Overview",
        "comparison": "Period comparison",
        "concentration": "Concentration",
        "growth": "Growth decomposition",
        "basket": "Basket structure",
    },
    LANGUAGE_ARABIC: {
        "overview": "نظرة عامة",
        "comparison": "مقارنة الفترات",
        "concentration": "التركّز",
        "growth": "تحليل النمو",
        "basket": "بنية السلة",
    },
}

# What each chart kind shows, as the alternative text a reader who cannot see it gets.
# Keyed by the `chart_description.<kind>` codes `charts.ChartView` carries, so a surface
# resolves a description the same way it resolves a category.
CHART_DESCRIPTIONS: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "chart_description.bar": "Bar chart of the figures in this section",
        "chart_description.grouped_bar": "Grouped bar chart of the figures in this section",
        "chart_description.line": "Cumulative share curve over the ranked values",
    },
    LANGUAGE_ARABIC: {
        "chart_description.bar": "رسم بالأعمدة للأرقام في هذا القسم",
        "chart_description.grouped_bar": "رسم بأعمدة مجمّعة للأرقام في هذا القسم",
        "chart_description.line": "منحنى النصيب التراكمي عبر القيم المرتّبة",
    },
}

# Every governed section has a heading in every governed language, checked at import
# rather than left to a test. A section added to `ORDERED_SECTIONS` without wording
# would otherwise reach a reader as a `KeyError` mid-render on one surface and as a
# missing chart title on another.
for _language, _headings in SECTION_HEADINGS.items():
    if set(_headings) != set(ORDERED_SECTIONS):
        raise RuntimeError("every governed section needs a heading in every language")


def category_of(figure: CitedFigure) -> ChartCategory:
    """A mark's category if the figure has one, otherwise the code for its metric.

    An earlier version used the figure's own rendered *value* as its name, which
    showed several amounts and identified none of them.
    """
    if figure.label in GOVERNED_FIGURE_LABELS:
        # A governed label is an internal identifier, not customer text. Treating one
        # as final put `period_over_period` on both the English and the Arabic axis.
        return ChartCategory(value=f"label.{figure.label}", localize=True)
    if figure.label is not None:
        return ChartCategory(value=figure.label, localize=False)
    return ChartCategory(value=f"metric.{figure.metric}", localize=True)


def worded(category: ChartCategory, language: str) -> str:
    """The text one language shows for a category.

    A customer value is returned unchanged -- it is already final, and putting it
    through the table would be this module editing a product name. A governed code is
    looked up, and a missing one raises rather than falling back to the code: an
    identifier shown to a reader is the failure this module exists to prevent, and a
    fallback would ship it quietly.
    """
    if not category.localize:
        return category.value
    return LABEL_WORDING[language][category.value]
