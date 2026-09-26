"""What a customer reads when a cross-version comparison refuses, in both languages.

`RRA-008` §Refusals and caveats freezes the complete set of causes this family
introduces and requires each carry "its complete customer wording in **both
Arabic and English in the same code slice that raises it**", under `RRA-009`.
`#400` declined to write those strings into the specification -- no
specification in this repository holds customer copy -- and named this slice.

**The causes are imported, never retyped.** They come from `compatibility` and
`dataset_period`, the modules that raise them, so a cause added there without
wording here fails this slice's coverage test rather than reaching a customer
unworded. A retyped list would drift silently, and `RRA-008` states the set is
not extendable without amending the specification.

**No figure, no version name, no digit.** `RCA-005` `FR-131` requires a refused
pair show "no partial, indicative, or best-effort figure" and `FR-133` that the
audit record carry no figure, delta, version name or refusal detail. So every
string here is static: nothing is interpolated, because a format placeholder is
where a value would eventually be passed.

**`RRA-009`'s parts** (`#560` item 7): every string opens by naming the
comparison as unavailable (part 1), says why (2), and says neither period's
report is affected (3). Part 4 names a field for `CAUSE_SCOPE`, in the
journey's own mapping label, and the missing record for `CAUSE_INCOMPLETE`;
whether the other causes owe one is an open owner question.

**Nine of the ten say what to do about it** (part 5): which of the two versions
to change, or that the pair itself is the wrong question. `CAUSE_INCOMPLETE`
ends on its part 4 and carries no remedy sentence yet; its wording is an open
owner question rather than copy this slice may invent.
"""

from __future__ import annotations

from khepri.rra.analysis.compatibility import (
    CAUSE_BASIS,
    CAUSE_FORMULA_DRIFT,
    CAUSE_MAPPING_DRIFT,
    CAUSE_PACKAGE_DRIFT,
    CAUSE_SCOPE,
    CAUSE_STORE_SET,
)
from khepri.rra.analysis.dataset_period import (
    CAUSE_GRANULARITY,
    CAUSE_INCOMPLETE,
    CAUSE_RETAIL_DAY,
    CAUSE_UNORDERED_PAIR,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH

__all__ = [
    "CROSSVERSION_CAVEATS",
    "CROSSVERSION_REFUSALS",
    "refusal_wording",
]

#: One entry per cause `RRA-008` §Refusals and caveats freezes. Keyed by the
#: cause constant rather than a string literal, so a renamed cause is a failed
#: import here rather than a missing lookup at render time.
CROSSVERSION_REFUSALS: dict[str, dict[str, str]] = {
    CAUSE_SCOPE: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "These two datasets do not describe the same scope, so a comparison "
            "between them would not be a comparison. Neither period's own report "
            "is affected. What decides the scope is the Store or branch column: both "
            "datasets must list the same stores, or both must state one aggregate. "
            "Choose two datasets covering the same stores or the same aggregate."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "لا تصف مجموعتا البيانات هاتان النطاق نفسه، لذا لن تكون المقارنة بينهما "
            "مقارنة فعلية. لا يتأثر تقرير أي من الفترتين. ما يحدد النطاق هو عمود "
            "المتجر أو الفرع: يجب أن تذكر المجموعتان المتاجر نفسها، أو أن تذكر "
            "كلتاهما مستوى إجماليًا واحدًا. اختر مجموعتين تغطيان المتاجر نفسها أو "
            "المستوى الإجمالي نفسه."
        ),
    },
    CAUSE_MAPPING_DRIFT: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "The two datasets were mapped differently, so their figures were "
            "measured differently and the difference between them would have no "
            "meaning. Neither period's own report is affected. Re-admit the older "
            "dataset under the current mapping."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "جرى ربط مجموعتي البيانات بطريقتين مختلفتين، لذا قيست أرقامهما بطريقتين "
            "مختلفتين ولن يكون للفرق بينهما معنى. لا يتأثر تقرير أي من الفترتين. "
            "أعد إدخال المجموعة الأقدم وفق الربط الحالي."
        ),
    },
    CAUSE_FORMULA_DRIFT: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "The two datasets were calculated under different governed formulas, "
            "so their figures are not the same measure. Neither period's own "
            "report is affected. Re-run the older dataset to bring it onto the "
            "current formula."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "حُسبت مجموعتا البيانات وفق صيغتين محكومتين مختلفتين، لذا ليست أرقامهما "
            "المقياس نفسه. لا يتأثر تقرير أي من الفترتين. أعد تشغيل المجموعة "
            "الأقدم لتصبح وفق الصيغة الحالية."
        ),
    },
    CAUSE_PACKAGE_DRIFT: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "The two analyses were packaged under different governed shapes, so "
            "their figures cannot be addressed alike. Neither period's own report "
            "is affected. Re-run the older analysis."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "جُمعت نتيجتا التحليلين وفق بنيتين محكومتين مختلفتين، لذا لا يمكن "
            "الإشارة إلى أرقامهما بالطريقة نفسها. لا يتأثر تقرير أي من الفترتين. "
            "أعد تشغيل التحليل الأقدم."
        ),
    },
    # `D-5`'s one basis cause covers currency and admitted filters alike (`RRA-008`
    # §Frozen contracts), so one wording names both. A `filter mismatch` entry once
    # sat beside this one under a cause the frozen set does not contain.
    CAUSE_BASIS: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "The two datasets are not stated on the same basis: they differ in "
            "currency, in the kinds of transaction admitted, or in the statuses "
            "admitted, so their figures do not measure the same events. Neither "
            "period's own report is affected. Compare datasets stated on one basis."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "مجموعتا البيانات غير مذكورتين على الأساس نفسه: تختلفان في العملة، أو في "
            "أنواع الحركات المدخلة، أو في الحالات المدخلة، لذا لا تقيس أرقامهما الأحداث "
            "نفسها. لا يتأثر تقرير أي من الفترتين. قارن مجموعات بيانات مذكورة على "
            "أساس واحد."
        ),
    },
    CAUSE_STORE_SET: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "The two datasets cover different sets of stores. Each is complete on "
            "its own, but comparing them would compare different populations "
            "rather than the same population over time. Neither period's own "
            "report is affected. Compare two datasets covering the same stores."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "تغطي مجموعتا البيانات مجموعتين مختلفتين من المتاجر. كل منهما مكتملة "
            "بذاتها، لكن مقارنتهما ستقارن مجتمعين مختلفين بدل مقارنة المجتمع نفسه "
            "على مدى الزمن. لا يتأثر تقرير أي من الفترتين. قارن مجموعتي بيانات "
            "تغطيان المتاجر نفسها."
        ),
    },
    CAUSE_GRANULARITY: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "One dataset covers days and the other covers months. Khepri compares "
            "periods as they are stated and never rescales one to fit the other. "
            "Neither period's own report is affected. Compare two datasets stated "
            "at the same granularity, both by day or both by month."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "تغطي إحدى المجموعتين أيامًا وتغطي الأخرى أشهرًا. تقارن خِبري الفترات كما "
            "هي مذكورة ولا تعيد قياس إحداهما لتوافق الأخرى. لا يتأثر تقرير أي من "
            "الفترتين. قارن مجموعتي بيانات مذكورتين بالدقة نفسها، كلتاهما باليوم أو "
            "كلتاهما بالشهر."
        ),
    },
    CAUSE_RETAIL_DAY: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "The two datasets close their retail day at different hours, so their "
            "days do not hold the same trading. Neither period's own report is "
            "affected. Compare datasets sharing one retail day boundary."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "تُغلق مجموعتا البيانات اليوم البيعي في ساعتين مختلفتين، لذا لا يحتوي "
            "يوماهما التداول نفسه. لا يتأثر تقرير أي من الفترتين. قارن مجموعات "
            "بيانات تشترك في حد اليوم البيعي نفسه."
        ),
    },
    # Part 4 names the missing evidence without naming the period: the refusal
    # carries only its cause, and the wording is static (`FR-131`/`FR-133`). It
    # must also hold where `crossversion_assembly` raises this cause for two
    # packages that share no measured figure.
    CAUSE_INCOMPLETE: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "At least one of the two periods is not fully covered. Khepri compares "
            "complete periods only, and will not compare part of one period "
            "against the whole of another. Neither period's own report is "
            "affected. What is missing is a complete record: one of the two "
            "datasets does not cover its whole period, or does not record the "
            "same figures as the other."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "إحدى الفترتين على الأقل غير مغطاة بالكامل. تقارن خِبري الفترات المكتملة "
            "فقط، ولا تقارن جزءًا من فترة بفترة كاملة أخرى. لا يتأثر تقرير أي من "
            "الفترتين. الناقص هو سجل مكتمل: إحدى المجموعتين لا تغطي فترتها كاملة، "
            "أو لا تسجل الأرقام نفسها التي تسجلها الأخرى."
        ),
    },
    CAUSE_UNORDERED_PAIR: {
        LANGUAGE_ENGLISH: (
            "The comparison between these two datasets is not available. "
            "A comparison needs two different datasets, and needs to know which is "
            "the subject and which the baseline. Neither period's own report is "
            "affected. Choose two and state which one is being measured against "
            "the other."
        ),
        LANGUAGE_ARABIC: (
            "المقارنة بين مجموعتي البيانات هاتين غير متاحة. "
            "تحتاج المقارنة إلى مجموعتي بيانات مختلفتين، وإلى معرفة أيهما الموضوع "
            "وأيهما الأساس. لا يتأثر تقرير أي من الفترتين. اختر مجموعتين وحدد "
            "أيهما تُقاس مقابل الأخرى."
        ),
    },
}

#: What an *admitted* pair carries. A cross-version comparison is not a period
#: comparison, and a reader who assumes it is would read a restated dataset as
#: a change in trading.
CROSSVERSION_CAVEATS: dict[str, str] = {
    LANGUAGE_ENGLISH: (
        "This compares two datasets you admitted separately, not two periods "
        "inside one dataset. A difference here can mean the trading changed or "
        "that the second dataset was extracted differently."
    ),
    LANGUAGE_ARABIC: (
        "تقارن هذه النتيجة مجموعتي بيانات أدخلتهما بشكل منفصل، لا فترتين داخل "
        "مجموعة واحدة. قد يعني الفرق هنا أن التداول تغيّر أو أن المجموعة الثانية "
        "استُخرجت بطريقة مختلفة."
    ),
}


def refusal_wording(cause: str) -> dict[str, str]:
    """Both languages for one governed cause.

    Raises `KeyError` for anything else, deliberately: `RRA-008` freezes the
    cause set, so an unworded cause is a programming error rather than a
    customer-facing state, and failing closed is `Constitution V`.
    """
    return dict(CROSSVERSION_REFUSALS[cause])
