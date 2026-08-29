"""The read-only catalog of governed vocabulary, derived and never restated.

**What this module is.** One place to ask which metrics, populations, reasons and
caveats the governed calculation can publish, and what each is called. `RRA-011`
authorizes it as a catalog over calculation that already exists: it adds no
arithmetic, admits no code, and decides nothing about what a figure means.

**Derived, not retyped.** Every code here is read from the module that already
governs it — `facts.GOVERNED_METRICS`, `populations.GOVERNED_POPULATIONS`, and
each `RRA-008` family's own `GOVERNED_METRICS`. That is `RRA-011`'s third scope
test, and it is stated against *hand-maintenance* rather than duplication in
general: a set computed from the governed source at import is the same truth read
twice, while a retyped list is a second truth that nothing makes wrong when the
source moves. `wording.py` carried such a list until this slice replaced it.

**Two scopes, and the discipline is not conflating them.** A metric's identity is
a constant; its precision and the population it was computed over are properties
of a run. `facts.py` reads monetary precision from the admitted data, and no
governed record ties a metric to a population, so neither appears on a definition
here. A catalog that published them would be guessing in a field named as though
it knew, which is the fabrication the fail-closed rule exists to prevent. A reader
who needs them reads the package that carries them.

**Family codes are admitted by their family's own rule.** A population like
`dimension_complete_sales:category` is a member of a family whose members are
whichever dimensions the mapping resolved, so `GOVERNED_POPULATIONS` excludes them
by design and `populations.is_governed_population` admits them by prefix. This
module delegates to that predicate rather than testing set membership, which would
reject a population real packages carry.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra import facts, populations
from khepri.rra.analysis import basket, comparison, concentration, growth


class UnknownCode(LookupError):
    """A code no governed module admits.

    Raised rather than returning `None` or the code itself. `RRA-011` requires a
    lookup to fail closed: a definition invented for an unrecognized code would
    be indistinguishable from a real one, and the raw identifier reaching a
    customer surface is the failure the wording layer already refuses.
    """


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """What is knowable about a metric without a package.

    The code, and the governed version of the contract that computes it.
    Everything else a reader might want -- the value, its precision, the rows
    behind it -- belongs to a produced package and is read from there.
    """

    code: str
    #: The governed version of the contract that computes this metric --
    #: `rra004.formula.v2` for a core metric, `rra008.<family>.v2` for an
    #: analysis family. A governed constant read from the module that declares
    #: it, never a label this module coins: `RRA-011` admits no code of its own,
    #: and a family name invented here would be one.
    formula_version: str


@dataclass(frozen=True, slots=True)
class PopulationDefinition:
    """A population code, and whether it names a family rather than a constant."""

    code: str
    is_family: bool


#: Which governed contract publishes which metrics, keyed by that contract's own
#: version constant. Both halves are read from the module that declares them, so
#: a metric added there reaches this catalog without an edit here, and no name in
#: this table is one this module invented.
FAMILY_METRICS: dict[str, tuple[str, ...]] = {
    facts.FORMULA_VERSION: tuple(sorted(facts.GOVERNED_METRICS)),
    comparison.COMPARISON_FORMULA_VERSION: tuple(comparison.GOVERNED_METRICS),
    growth.GROWTH_FORMULA_VERSION: tuple(growth.GOVERNED_METRICS),
    basket.BASKET_FORMULA_VERSION: tuple(basket.GOVERNED_METRICS),
    concentration.CONCENTRATION_FORMULA_VERSION: tuple(
        concentration.GOVERNED_METRICS
    ),
}

#: Every metric code any governed family publishes.
METRIC_CODES: frozenset[str] = frozenset(
    code for codes in FAMILY_METRICS.values() for code in codes
)

#: Every population code that is a constant. Family members are admitted by
#: `admits_population` instead, which is `populations`' own rule.
POPULATION_CODES: frozenset[str] = frozenset(populations.GOVERNED_POPULATIONS)

_METRIC_VERSIONS: dict[str, str] = {
    code: version for version, codes in FAMILY_METRICS.items() for code in codes
}


def admits_metric(code: str) -> bool:
    """Whether any governed family publishes this metric."""
    return code in METRIC_CODES


def admits_population(code: str) -> bool:
    """Whether `RRA-004` defines this population, constant or family member.

    Delegates to `populations.is_governed_population` rather than testing
    `POPULATION_CODES`, so a `dimension_complete_sales:<dimension>` member is
    admitted by the same rule the rest of the system admits it by.
    """
    return populations.is_governed_population(code)


def define_metric(code: str) -> MetricDefinition:
    """The definition for one metric code, or `UnknownCode`."""
    formula_version = _METRIC_VERSIONS.get(code)
    if formula_version is None:
        raise UnknownCode(code)
    return MetricDefinition(code=code, formula_version=formula_version)


def define_population(code: str) -> PopulationDefinition:
    """The definition for one population code, or `UnknownCode`.

    A family member is reported as one. The dimension it names is the package's
    to state, not this catalog's: the same code means a different set of rows in
    two packages, and only the package knows which.
    """
    if not admits_population(code):
        raise UnknownCode(code)
    return PopulationDefinition(code=code, is_family=code not in POPULATION_CODES)


#: What each metric means, in a sentence a reader who is not an analyst can use.
#:
#: `RRA-011` authors this rather than deriving it, because no other artifact
#: declares it: `RRA-009` governs what a metric is *called* and this governs what
#: it *means*. The one exception the specification grants to its own derivation
#: rule, and bounded by it -- every key here is a code some governed family
#: already publishes, asserted at import below.
METRIC_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "en": {
        "revenue": "Money from sales, after returns are subtracted.",
        "units": "How many items were sold, after returned items are subtracted.",
        "transactions": "How many separate sales happened.",
        "average_order_value": "Money from sales divided by the number of sales.",
        "average_selling_price": "Money from sales divided by items sold.",
        "cost": "What the goods sold cost you to buy.",
        "gross_profit": "Money from sales minus what those goods cost.",
        "gross_margin": "Gross profit as a share of sales.",
        "discount": "Money taken off the stated price.",
        "returns": "Money refunded on returned goods.",
        "growth_revenue_change": "How much sales money changed between the two periods.",
        "growth_price_effect": "The part of that change explained by prices and product mix.",
        "growth_volume_effect": "The part of that change explained by selling more or fewer items.",
        "revenue_delta_absolute": "The difference in sales money between the two periods.",
        "revenue_delta_percent": "That difference as a percentage of the earlier period.",
        "basket_items_per_transaction": "How many items an average sale contains.",
        "basket_attach_rate": "The share of sales that included this product or category.",
        "concentration_curve": "How sales are spread across products, largest to smallest.",
        "concentration_distinct_values": "How many products or branches were counted.",
        "concentration_ranked_values": "How many of those could be ranked.",
        "concentration_top_decile_share": "The share of sales held by the top tenth.",
        "concentration_top_quartile_share": "The share of sales held by the top quarter.",
    },
    "ar": {
        "revenue": "الأموال الناتجة عن المبيعات بعد خصم المرتجعات.",
        "units": "عدد الأصناف المبيعة بعد خصم الأصناف المرتجعة.",
        "transactions": "عدد عمليات البيع المنفصلة.",
        "average_order_value": "أموال المبيعات مقسومة على عدد عمليات البيع.",
        "average_selling_price": "أموال المبيعات مقسومة على عدد الأصناف المبيعة.",
        "cost": "تكلفة شراء البضاعة التي بيعت.",
        "gross_profit": "أموال المبيعات ناقص تكلفة تلك البضاعة.",
        "gross_margin": "إجمالي الربح كنسبة من المبيعات.",
        "discount": "المبالغ المخصومة من السعر المعلن.",
        "returns": "المبالغ المستردة عن البضاعة المرتجعة.",
        "growth_revenue_change": "مقدار تغير أموال المبيعات بين الفترتين.",
        "growth_price_effect": "الجزء من ذلك التغير الذي تفسره الأسعار ومزيج المنتجات.",
        "growth_volume_effect": "الجزء من ذلك التغير الذي يفسره بيع أصناف أكثر أو أقل.",
        "revenue_delta_absolute": "الفرق في أموال المبيعات بين الفترتين.",
        "revenue_delta_percent": "ذلك الفرق كنسبة مئوية من الفترة الأسبق.",
        "basket_items_per_transaction": "عدد الأصناف التي تتضمنها عملية البيع الوسطية.",
        "basket_attach_rate": "نسبة عمليات البيع التي تضمنت هذا المنتج أو الفئة.",
        "concentration_curve": "كيف تتوزع المبيعات على المنتجات، من الأكبر إلى الأصغر.",
        "concentration_distinct_values": "عدد المنتجات أو الفروع التي جرى احتسابها.",
        "concentration_ranked_values": "عدد ما أمكن ترتيبه منها.",
        "concentration_top_decile_share": "حصة أعلى عُشر من المبيعات.",
        "concentration_top_quartile_share": "حصة أعلى ربع من المبيعات.",
    },
}

#: What each metric is *not*, stated because the wrong reading is the likely one.
#:
#: An unsupported interpretation names the specific mistake a metric invites,
#: not a general hedge. `average_order_value` divides by sale transactions, so a
#: reader taking it as revenue per customer is wrong in a way no caveat on the
#: figure would tell them -- one customer buying three times is three sales.
#:
#: `RRA-011` bounds this: it states what a metric does not mean and never
#: redefines what it does. Where wording and computation could be read as
#: disagreeing, `RRA-004` and `RRA-008` govern and the wording is wrong.
METRIC_NOT_MEANT: dict[str, dict[str, str]] = {
    "en": {
        "revenue": "Not money received. A sale recorded today counts today, whenever it is paid.",
        "units": "Not stock on hand. This counts what was sold, not what remains.",
        "transactions": "Not customers. One customer buying three times is three sales.",
        "average_order_value": (
            "Not revenue per customer. It divides by sales, and one customer can make several."
        ),
        "average_selling_price": (
            "Not a price list. It averages everything sold, so product mix moves it as much as "
            "pricing."
        ),
        "cost": "Not total spending. Only the cost of goods that sold is counted here.",
        "gross_profit": "Not profit. Rent, salaries and other running costs are not subtracted.",
        "gross_margin": "Not net margin, for the same reason: running costs are not in it.",
        "discount": "Not lost revenue. A discount may have been what made the sale happen.",
        "returns": (
            "Not a quality measure on its own. A return can follow a policy rather than a fault."
        ),
        "growth_revenue_change": "Not a forecast. It compares two periods that already happened.",
        "growth_price_effect": (
            "Not a pricing result. Selling more of an expensive product moves this with no price "
            "change."
        ),
        "growth_volume_effect": "Not customer count. It follows items sold, not who bought them.",
        "revenue_delta_absolute": "Not a trend. Two periods are two points, not a direction.",
        "revenue_delta_percent": (
            "Not comparable across different-sized periods. A small base makes a small change look "
            "large."
        ),
        "basket_items_per_transaction": (
            "Not distinct products. Three of one item is three items here."
        ),
        "basket_attach_rate": (
            "Not a cross-sell result. It counts sales containing the value, not sales it was added "
            "to."
        ),
        "concentration_curve": (
            "Not a ranking of importance. It ranks by sales money and nothing else."
        ),
        "concentration_distinct_values": (
            "Not your catalogue. Only values that appear in sales are counted."
        ),
        "concentration_ranked_values": (
            "Not equal to the count above when some values could not be ranked."
        ),
        "concentration_top_decile_share": (
            "Not a health measure. Whether concentration is good depends on your business."
        ),
        "concentration_top_quartile_share": "Not a health measure, for the same reason.",
    },
    "ar": {
        "revenue": "ليست الأموال المحصلة. عملية البيع المسجلة اليوم تُحتسب اليوم مهما تأخر سدادها.",
        "units": "ليست المخزون المتاح. هذا عدد ما بيع لا ما تبقى.",
        "transactions": "ليست عدد العملاء. العميل الذي يشتري ثلاث مرات هو ثلاث عمليات بيع.",
        "average_order_value": (
            "ليس الإيراد لكل عميل. القسمة على عمليات البيع، والعميل الواحد قد يجري عدة عمليات."
        ),
        "average_selling_price": (
            "ليس قائمة أسعار. هو متوسط عبر كل ما بيع، فمزيج المنتجات يحركه بقدر التسعير."
        ),
        "cost": "ليست إجمالي المصروفات. تُحتسب هنا تكلفة البضاعة التي بيعت فقط.",
        "gross_profit": "ليس صافي الربح. الإيجار والرواتب وبقية مصاريف التشغيل غير مخصومة.",
        "gross_margin": "ليس هامش الربح الصافي، للسبب نفسه: مصاريف التشغيل ليست ضمنه.",
        "discount": "ليس إيراداً ضائعاً. قد يكون الخصم هو ما جعل عملية البيع تحدث.",
        "returns": "ليست مقياس جودة بمفردها. قد يكون الإرجاع اتباعاً لسياسة لا نتيجة عيب.",
        "growth_revenue_change": "ليس تنبؤاً. هو مقارنة بين فترتين وقعتا بالفعل.",
        "growth_price_effect": (
            "ليس نتيجة قرار تسعير. بيع كمية أكبر من منتج مرتفع السعر يحركه دون تغير الأسعار."
        ),
        "growth_volume_effect": "ليس عدد العملاء. يتبع الأصناف المبيعة لا من اشتراها.",
        "revenue_delta_absolute": "ليس اتجاهاً. الفترتان نقطتان لا مسار.",
        "revenue_delta_percent": (
            "غير قابل للمقارنة بين فترات مختلفة الحجم. القاعدة الصغيرة تجعل التغير الصغير نسبة "
            "كبيرة."
        ),
        "basket_items_per_transaction": (
            "ليست منتجات مختلفة. ثلاث قطع من صنف واحد هي ثلاثة أصناف هنا."
        ),
        "basket_attach_rate": (
            "ليست نتيجة بيع متقاطع. تحتسب عمليات البيع التي تضمنت القيمة لا التي أُضيفت فيها."
        ),
        "concentration_curve": "ليس ترتيباً حسب الأهمية. يرتب حسب أموال المبيعات فقط.",
        "concentration_distinct_values": "ليس كتالوجك. تُحتسب القيم التي تظهر في المبيعات فقط.",
        "concentration_ranked_values": "لا يساوي العدد أعلاه حين يتعذر ترتيب بعض القيم.",
        "concentration_top_decile_share": "ليست مقياس صحة. كون التركز جيداً يعتمد على نشاطك.",
        "concentration_top_quartile_share": "ليست مقياس صحة، للسبب نفسه.",
    },
}


def _assert_vocabulary_complete() -> None:
    """Both tables cover every admitted metric, in both languages, and no others.

    Flat rather than nested loops: the same gate that scores this file flagged
    that shape in `wording.py` as a bumpy road, and a new file is scored from
    scratch. The comprehension finds every discrepancy and one guard clause
    raises with all of them named.
    """
    wrong = [
        f"{table_name}/{language}"
        for table_name, table in (
            ("descriptions", METRIC_DESCRIPTIONS),
            ("not_meant", METRIC_NOT_MEANT),
        )
        for language, entries in table.items()
        if set(entries) != METRIC_CODES
    ]
    if wrong:
        message = f"every admitted metric needs vocabulary in every language: {wrong}"
        raise RuntimeError(message)


_assert_vocabulary_complete()


def describe_metric(code: str, language: str) -> str:
    """What this metric means, or `UnknownCode`.

    No fallback to another language: an Arabic reader gets Arabic or an error,
    because a silently English answer on an Arabic surface is the parity failure
    `RRA-006` forbids.
    """
    if not admits_metric(code):
        raise UnknownCode(code)
    return METRIC_DESCRIPTIONS[language][code]


def not_meant(code: str, language: str) -> str:
    """The reading this metric invites and does not support, or `UnknownCode`."""
    if not admits_metric(code):
        raise UnknownCode(code)
    return METRIC_NOT_MEANT[language][code]


@dataclass(frozen=True, slots=True)
class AnalysisQualitySummary:
    """What one package answered, answered with a qualification, and refused.

    **An aggregation, never a measurement.** Every number here counts outcomes
    the bundle already carries. Nothing is computed, scored, or weighted, and
    `RRA-011` excludes a confidence score, a quality score, and a completeness
    percentage by name — a reader learns what the system could and could not
    answer, not how much to trust an answer it gave.

    **No Internal-tier field.** `Section.state` is Internal and `RRA-009` renders
    an Internal field on no customer surface, so this classifies a section by
    whether it carries a refusal reason. That reaches the same answer from
    Audit-tier evidence: `RRA-008` refuses the affected analysis rather than the
    report, and a refused section is the one that states why.

    `refusals` and `caveats` carry codes rather than prose. What a code *says* to
    a customer is `RRA-009`'s, and restating it here would put the same sentence
    in two places to drift apart.
    """

    answered: int
    caveated: int
    refused: int
    #: `(section_id, reason)` for each refused analysis, so a reader learns which
    #: and why rather than only how many.
    refusals: tuple[tuple[str, str], ...]
    #: Every caveat code the bundle states, deduplicated and ordered.
    caveats: tuple[str, ...]


def summarize(bundle) -> AnalysisQualitySummary:
    """Group one bundle's outcomes without recomputing any of them.

    Flat by construction: three comprehensions over `bundle.sections` and
    `bundle.caveats`, no branch nesting. The tiering is the bundle's own — a
    section carrying a reason is refused, and one carrying none is not — so this
    never re-derives what `RRA-009` already decided.
    """
    refusals = tuple(
        (section.section_id, section.reason)
        for section in bundle.sections
        if section.reason is not None
    )
    answered = tuple(
        section for section in bundle.sections if section.reason is None
    )
    # `section is None` is a report-level caveat -- `currency_not_declared`
    # qualifies the dataset, not one analysis -- so it qualifies no section and
    # is filtered out. The filter is belt-and-braces rather than load-bearing:
    # `None` matches no `section_id`, so the intersection below is the same
    # either way. Kept because the set is named `qualified` and a reader should
    # not have to work out that a report-level caveat is silently excluded by
    # arithmetic rather than by intent.
    qualified = {
        caveat.section for caveat in bundle.caveats if caveat.section is not None
    }
    return AnalysisQualitySummary(
        answered=len(answered),
        caveated=len({s.section_id for s in answered} & qualified),
        refused=len(refusals),
        refusals=refusals,
        caveats=tuple(sorted({caveat.code for caveat in bundle.caveats})),
    )
