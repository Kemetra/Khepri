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
from khepri.rra.analysis import basket, comparison, growth
from khepri.rra.bundle import (
    CAVEAT_CHART_NOT_DRAWN,
    CAVEAT_CURVE_SAMPLED,
    GOVERNED_FIGURE_LABELS,
    GOVERNED_SECTION_REASONS,
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
_RESULT_REASON_CODES = {
    facts.REASON_INPUT_UNAVAILABLE,
    facts.REASON_ZERO_DENOMINATOR,
    facts.REASON_RECONCILIATION_FAILED,
    facts.REASON_INCOMPLETE_IDENTIFIERS,
    facts.REASON_AMBIGUOUS_MAPPING,
    basket.REASON_DIMENSION_ABSENT,
    comparison.REASON_NEGATIVE_BASE,
}
_GOVERNED_CAVEAT_CODES = {
    facts.CAVEAT_CURRENCY_NOT_DECLARED,
    facts.CAVEAT_DUPLICATE_ROWS,
    facts.CAVEAT_NEGATIVE_REVENUE,
    facts.CAVEAT_RETURNS_NOT_NETTED,
    facts.CAVEAT_NULL_MEASURE_INPUTS,
    facts.CAVEAT_UNDATED_ROWS_EXCLUDED,
    facts.CAVEAT_BUCKETS_TRUNCATED,
    facts.CAVEAT_PERSONAL_VALUES_REDACTED,
    facts.CAVEAT_DERIVED_OVER_MATCHED_ROWS,
    CAVEAT_CHART_NOT_DRAWN,
    CAVEAT_CURVE_SAMPLED,
    growth.CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
}


def _assert_metric_wording_complete() -> None:
    if set(METRIC_WORDING) != {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}:
        raise RuntimeError("metric business names must cover every governed language")
    for language, entries in METRIC_WORDING.items():
        if set(entries) != _GOVERNED_METRIC_CODES:
            message = (
                "every governed metric needs a business name in every language "
                f"(language={language!r})"
            )
            raise RuntimeError(message)


_assert_metric_wording_complete()


def metric_business_name(metric: str, language: str) -> str:
    """Return a metric's business name, refusing unknown codes or languages."""
    return METRIC_WORDING[language][metric]


# Business names for figure metrics that are not governed metric codes and carry
# no customer label of their own. This table stays separate from `METRIC_WORDING`
# so the governed-vocabulary completeness guard above keeps its exact meaning.
DERIVED_METRIC_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "basket_items_per_transaction": "Items per sale",
        "basket_attach_rate": "Attach rate",
        "concentration_top_decile_share": "Share of sales, top tenth",
        "concentration_top_quartile_share": "Share of sales, top quarter",
        "concentration_distinct_values": "Products or branches counted",
        "concentration_ranked_values": "Ranked contribution",
        "revenue_delta_absolute": "Revenue change",
        "revenue_delta_percent": "Revenue percentage change",
    },
    LANGUAGE_ARABIC: {
        "basket_items_per_transaction": "عدد الأصناف لكل عملية بيع",
        "basket_attach_rate": "نسبة عمليات البيع التي تتضمن المنتج أو الفئة",
        "concentration_top_decile_share": "حصة أعلى عُشر من المبيعات",
        "concentration_top_quartile_share": "حصة أعلى ربع من المبيعات",
        "concentration_distinct_values": "عدد المنتجات أو الفروع المحتسبة",
        "concentration_ranked_values": "المساهمة حسب الترتيب",
        "revenue_delta_absolute": "تغير الإيرادات",
        "revenue_delta_percent": "نسبة تغير الإيرادات",
    },
}


def business_metric_name(metric: str, language: str) -> str | None:
    """Return a business name, or `None` when the row's label names it.

    The raw code is never a fallback: returning it would quietly expose an
    internal identifier on a customer surface.
    """
    governed = METRIC_WORDING[language].get(metric)
    if governed is not None:
        return governed
    return DERIVED_METRIC_WORDING[language].get(metric)


# Customer-facing refusal messages -- docs/reporting/refusal-presentation.md §D.
# Two tiers are required because a section refusal loses a whole analysis, while a
# result refusal loses one metric and leaves the section standing. Each message
# states what was unavailable, why, whether the rest of the report is unaffected,
# which field would fix it, and how.
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
    "result": {
        LANGUAGE_ENGLISH: {
            "required_input_unavailable": (
                "{metric} is not shown — the file does not contain {column}. "
                "The other figures in this section are unaffected."
            ),
            "zero_denominator": (
                "{metric} cannot be calculated for this period because the "
                "figure it divides by is zero. The other figures in this "
                "section are unaffected."
            ),
            "reconciliation_failed": (
                "{metric} was calculated but did not reconcile against its "
                "own inputs, so it is withheld rather than shown. The other "
                "figures in this section are unaffected."
            ),
            "incomplete_transaction_identifiers": (
                "{metric} is not shown — receipt numbers are missing from "
                "some rows, so this would describe only part of your sales. "
                "The other figures in this section are unaffected."
            ),
            "ambiguous_mapping": (
                "{metric} is not shown — more than one column in the file "
                "could be the {field} and it is not clear which. Rename or "
                "remove the duplicate and this becomes available."
            ),
            "dimension_absent": (
                "Attach rate is not shown — the file has no product or category "
                "column to measure attachment against. Items per sale is unaffected."
            ),
            "negative_base": (
                "{metric} is not shown — calculating a percentage change from a "
                "negative starting value would reverse the apparent direction of "
                "change. The absolute revenue change is unaffected."
            ),
        },
        LANGUAGE_ARABIC: {
            "required_input_unavailable": (
                "{metric} غير معروض — لا يحتوي الملف على {column}. الأرقام "
                "الأخرى في هذا القسم غير متأثرة."
            ),
            "zero_denominator": (
                "يتعذر حساب {metric} لهذه الفترة لأن الرقم الذي يُقسم عليه "
                "يساوي صفراً. الأرقام الأخرى في هذا القسم غير متأثرة."
            ),
            "reconciliation_failed": (
                "حُسب {metric} لكنه لم يتطابق مع مدخلاته، لذلك حُجب بدلاً من "
                "عرضه. الأرقام الأخرى في هذا القسم غير متأثرة."
            ),
            "incomplete_transaction_identifiers": (
                "{metric} غير معروض — أرقام الإيصالات مفقودة من بعض الصفوف، "
                "ولذلك سيصف هذا الرقم جزءاً من مبيعاتك فقط. الأرقام الأخرى "
                "في هذا القسم غير متأثرة."
            ),
            "ambiguous_mapping": (
                "{metric} غير معروض — قد يكون أكثر من عمود في الملف هو "
                "{field}، ولا يمكن تحديد العمود الصحيح. أعد تسمية العمود "
                "المكرر أو احذفه ليصبح هذا الرقم متاحاً."
            ),
            "dimension_absent": (
                "نسبة عمليات البيع التي تتضمن المنتج أو الفئة غير معروضة — لا "
                "يحتوي الملف على عمود للمنتج أو الفئة لقياس هذه النسبة. عدد "
                "الأصناف لكل عملية بيع غير متأثر."
            ),
            "negative_base": (
                "{metric} غير معروض — حساب نسبة التغير من قيمة بداية سالبة سيعكس "
                "المعنى الظاهر للتغير. التغير المطلق في الإيرادات غير متأثر."
            ),
        },
    },
}


def _assert_refusal_wording_complete() -> None:
    expected = {
        "section": set(GOVERNED_SECTION_REASONS),
        "result": _RESULT_REASON_CODES,
    }
    if set(REFUSAL_WORDING) != set(expected):
        raise RuntimeError("refusal wording must cover every governed tier")
    for tier, by_language in REFUSAL_WORDING.items():
        if set(by_language) != {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}:
            raise RuntimeError(f"refusal wording misses a language (tier={tier!r})")
        for language, entries in by_language.items():
            if set(entries) != expected[tier]:
                message = (
                    "every governed refusal reason needs a customer message in "
                    f"every language (tier={tier!r}, language={language!r})"
                )
                raise RuntimeError(message)


_assert_refusal_wording_complete()


def refusal_message(reason: str, *, context: str, language: str) -> str:
    """Return the customer message for one refusal reason at one tier.

    Unknown reason codes, tiers, and languages raise instead of falling back to
    internal identifiers or wording from the wrong refusal context.
    """
    return REFUSAL_WORDING[context][language][reason]


# Customer prose for every governed caveat. Reconciliation compares caveat sets
# for equality, so one missing entry is a refused report rather than a cosmetic gap.
CAVEAT_WORDING: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {
        "currency_not_declared": (
            "Your file does not state which currency the amounts are in. "
            "The figures are shown as supplied and have not been converted."
        ),
        "duplicate_rows_present": (
            "Some rows in your file are exact duplicates of each other. "
            "They have been counted as supplied — if they are genuine "
            "repeat sales this is correct, and if they are an export error "
            "the totals are overstated."
        ),
        "negative_revenue_present": (
            "Some rows carry a negative sale amount. These are included as "
            "supplied, which is correct if they are refunds recorded in the "
            "sales file."
        ),
        "returns_not_netted": (
            "Returns are reported separately and have not been subtracted "
            "from revenue. Revenue here is gross of returns."
        ),
        "null_measure_inputs": (
            "Some rows have no amount recorded. They are excluded from the "
            "totals rather than counted as zero."
        ),
        "rows_without_time_field_excluded": (
            "Some rows carry no date. They are excluded from anything "
            "measured by period, so month-by-month figures cover slightly "
            "fewer rows than the totals."
        ),
        "comparison_buckets_truncated": (
            "Your file covers more periods than this comparison shows. The "
            "comparison uses the most recent complete periods."
        ),
        "personal_values_redacted": (
            "Values that appeared to identify individual people were "
            "removed before analysis. No figure in this report depends on them."
        ),
        "derived_metrics_use_matched_rows": (
            "Figures that combine two measures — such as average price — "
            "use only the rows where both measures are present. They may "
            "therefore cover fewer rows than either measure alone."
        ),
        "chart_not_drawn": (
            "No chart is shown for this section. The figures beside it are complete."
        ),
        "curve_points_sampled": (
            "The concentration curve is drawn from 100 evenly spaced points "
            "across your full product range. The figures beside it use every row."
        ),
        "growth_interaction_assigned_to_price": (
            "Where price and quantity both changed, the combined part of "
            "the change is counted with the price effect. This is a stated "
            "convention, applied the same way every time, so the two "
            "effects still add exactly to the total."
        ),
    },
    LANGUAGE_ARABIC: {
        "currency_not_declared": (
            "لا يحدد ملفك العملة المستخدمة للمبالغ. تُعرض الأرقام كما وردت "
            "من دون تحويل."
        ),
        "duplicate_rows_present": (
            "بعض صفوف ملفك مكررة بالكامل. احتُسبت كما وردت — إذا كانت مبيعات "
            "متكررة فعلاً فهذا صحيح، وإذا كانت خطأ في التصدير فالإجماليات أعلى "
            "من الواقع."
        ),
        "negative_revenue_present": (
            "تتضمن بعض الصفوف قيمة بيع سالبة. أُدرجت كما وردت، وهذا صحيح إذا "
            "كانت تمثل مبالغ مستردة مسجلة في ملف المبيعات."
        ),
        "returns_not_netted": (
            "تُعرض المرتجعات بصورة منفصلة ولم تُطرح من الإيرادات. الإيرادات "
            "هنا إجمالية قبل المرتجعات."
        ),
        "null_measure_inputs": (
            "لا تحمل بعض الصفوف مبلغاً مسجلاً. استُبعدت من الإجماليات بدلاً "
            "من احتسابها صفراً."
        ),
        "rows_without_time_field_excluded": (
            "لا تحمل بعض الصفوف تاريخاً. استُبعدت من أي قياس حسب الفترة، لذلك "
            "تغطي الأرقام الشهرية صفوفاً أقل قليلاً من الإجماليات."
        ),
        "comparison_buckets_truncated": (
            "يغطي ملفك فترات أكثر مما تعرضه هذه المقارنة. تستخدم المقارنة "
            "أحدث الفترات المكتملة."
        ),
        "personal_values_redacted": (
            "أُزيلت قبل التحليل القيم التي بدت وكأنها تحدد أشخاصاً بعينهم. لا "
            "يعتمد عليها أي رقم في هذا التقرير."
        ),
        "derived_metrics_use_matched_rows": (
            "تستخدم الأرقام التي تجمع بين مقياسين — مثل متوسط السعر — الصفوف "
            "التي يتوفر فيها المقياسان معاً فقط. ولذلك قد تغطي صفوفاً أقل من "
            "كل مقياس منفرداً."
        ),
        "chart_not_drawn": (
            "لا يظهر رسم بياني لهذا القسم. الأرقام المعروضة بجانبه مكتملة."
        ),
        "curve_points_sampled": (
            "رُسم منحنى التركز باستخدام 100 نقطة موزعة بالتساوي على كامل "
            "نطاق المنتجات. وتستخدم الأرقام المعروضة بجانبه كل الصفوف."
        ),
        "growth_interaction_assigned_to_price": (
            "عندما تغير السعر والكمية معاً، احتُسب الجزء المشترك من التغير ضمن "
            "أثر السعر. هذه قاعدة معلنة تُطبق بالطريقة نفسها كل مرة، ولذلك "
            "يظل مجموع الأثرين مساوياً تماماً للتغير الإجمالي."
        ),
    },
}


def _assert_caveat_wording_complete() -> None:
    if set(CAVEAT_WORDING) != {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}:
        raise RuntimeError("caveat wording must cover every governed language")
    for language, entries in CAVEAT_WORDING.items():
        if set(entries) != _GOVERNED_CAVEAT_CODES:
            message = (
                "every governed caveat needs a customer message in every language "
                f"(language={language!r})"
            )
            raise RuntimeError(message)


_assert_caveat_wording_complete()


def caveat_message(code: str, language: str) -> str:
    """Return customer prose for one governed caveat code."""
    return CAVEAT_WORDING[language][code]


RESULT_CAVEAT_SEPARATOR = ":"


def caveat_prose(code: str, language: str) -> str:
    """Return prose for a caveat or a result-tier refusal travelling as one."""
    if RESULT_CAVEAT_SEPARATOR not in code:
        return caveat_message(code, language)
    result, reason = code.rsplit(RESULT_CAVEAT_SEPARATOR, 1)
    if reason in GOVERNED_SECTION_REASONS:
        return refusal_message(reason, context="section", language=language)
    metric = _result_business_name(result, language)
    return refusal_message(reason, context="result", language=language).format(
        metric=metric,
        column=metric,
        field=metric,
    )


def _result_business_name(result: str, language: str) -> str:
    """Name a refused result without allowing its scope or code onto the page."""
    metric = result.split(".", maxsplit=1)[0]
    name = business_metric_name(metric, language)
    if name is None:
        raise KeyError(result)
    return name


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
