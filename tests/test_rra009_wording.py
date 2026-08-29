from __future__ import annotations

import importlib
import pkgutil
import re

import pytest

from khepri.rra import bundle
from khepri.rra.analysis.basket import (
    REASON_DIMENSION_ABSENT,
    REASON_DIMENSION_INCOMPLETE,
)
from khepri.rra.analysis.comparison import (
    CAVEAT_PARTIAL_WINDOW,
    REASON_COVERAGE_INCOMPATIBLE,
    REASON_NEGATIVE_BASE,
)
from khepri.rra.analysis.growth import (
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
    CAVEAT_ROUNDING_RESIDUAL,
    GOVERNED_METRICS,
)
from khepri.rra.bundle import (
    CAVEAT_CHART_NOT_DRAWN,
    CAVEAT_CURVE_SAMPLED,
    GOVERNED_SECTION_REASONS,
)
from khepri.rra.facts import (
    CAVEAT_BUCKETS_TRUNCATED,
    CAVEAT_CURRENCY_NOT_DECLARED,
    CAVEAT_DERIVED_OVER_MATCHED_ROWS,
    CAVEAT_DUPLICATE_ROWS,
    CAVEAT_NEGATIVE_REVENUE,
    CAVEAT_NULL_MEASURE_INPUTS,
    CAVEAT_PERSONAL_VALUES_REDACTED,
    CAVEAT_RETURNS_NOT_NETTED,
    CAVEAT_UNDATED_ROWS_EXCLUDED,
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
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    REASON_RECONCILIATION_FAILED,
    REASON_REPEATED_ROW_SIGNATURE,
    REASON_ZERO_DENOMINATOR,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering import wording
from khepri.rra.versions import REASON_FAMILY_VERSION_UNADMITTED

_FACT_METRICS = (
    METRIC_REVENUE,
    METRIC_UNITS,
    METRIC_TRANSACTIONS,
    METRIC_AVERAGE_ORDER_VALUE,
    METRIC_AVERAGE_SELLING_PRICE,
    METRIC_COST,
    METRIC_GROSS_PROFIT,
    METRIC_GROSS_MARGIN,
    METRIC_DISCOUNT,
    METRIC_RETURNS,
)
_GOVERNED_METRIC_CODES = frozenset(_FACT_METRICS) | frozenset(GOVERNED_METRICS)
_SECTION_REFUSAL_CODES = frozenset(GOVERNED_SECTION_REASONS)
_RESULT_REFUSAL_CODES = frozenset(
    {
        REASON_INPUT_UNAVAILABLE,
        REASON_ZERO_DENOMINATOR,
        REASON_RECONCILIATION_FAILED,
        REASON_INCOMPLETE_COVERAGE,
        REASON_INCOMPLETE_IDENTIFIERS,
        REASON_AMBIGUOUS_MAPPING,
        REASON_REPEATED_ROW_SIGNATURE,
        REASON_DIMENSION_ABSENT,
        REASON_DIMENSION_INCOMPLETE,
        REASON_COVERAGE_INCOMPATIBLE,
        REASON_NEGATIVE_BASE,
        REASON_FAMILY_VERSION_UNADMITTED,
    }
)
_GOVERNED_CAVEAT_CODES = frozenset(
    {
        CAVEAT_CURRENCY_NOT_DECLARED,
        CAVEAT_DUPLICATE_ROWS,
        CAVEAT_NEGATIVE_REVENUE,
        CAVEAT_RETURNS_NOT_NETTED,
        CAVEAT_NULL_MEASURE_INPUTS,
        CAVEAT_UNDATED_ROWS_EXCLUDED,
        CAVEAT_BUCKETS_TRUNCATED,
        CAVEAT_PERSONAL_VALUES_REDACTED,
        CAVEAT_DERIVED_OVER_MATCHED_ROWS,
        CAVEAT_CHART_NOT_DRAWN,
        CAVEAT_CURVE_SAMPLED,
        CAVEAT_PARTIAL_WINDOW,
        CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
        CAVEAT_ROUNDING_RESIDUAL,
    }
)

_ACCEPTED_ARABIC_RESULT_MESSAGES = {
    REASON_FAMILY_VERSION_UNADMITTED: (
        "{metric} غير معروض — يصدر هذا التحليل على مراحل، والجزء الذي "
        "ينتجه لم يصدر بعد مع الجزء الذي يقرأ ملفك. بقية هذا التقرير "
        "غير متأثرة وأرقامها كاملة. لا ينقص ملفك شيء ولا يحتاج أي عمود "
        "إلى تعديل. سيظهر هذا الرقم عند صدور الإصدار المتبقي، ولا "
        "يلزمك أي إجراء."
    ),
    REASON_INPUT_UNAVAILABLE: (
        "{metric} غير معروض — لا يحتوي الملف على {column}. الأرقام الأخرى في "
        "هذا القسم غير متأثرة."
    ),
    REASON_ZERO_DENOMINATOR: (
        "يتعذر حساب {metric} لهذه الفترة لأن الرقم الذي يُقسم عليه يساوي صفراً. "
        "الأرقام الأخرى في هذا القسم غير متأثرة."
    ),
    REASON_RECONCILIATION_FAILED: (
        "حُسب {metric} لكنه لم يتطابق مع مدخلاته، لذلك حُجب بدلاً من عرضه. "
        "الأرقام الأخرى في هذا القسم غير متأثرة."
    ),
    REASON_INCOMPLETE_IDENTIFIERS: (
        "{metric} غير معروض — أرقام الإيصالات مفقودة من بعض الصفوف، ولذلك "
        "سيصف هذا الرقم جزءاً من مبيعاتك فقط. الأرقام الأخرى في هذا القسم "
        "غير متأثرة."
    ),
    REASON_AMBIGUOUS_MAPPING: (
        "{metric} غير معروض — قد يكون أكثر من عمود في الملف هو {field}، ولا "
        "يمكن تحديد العمود الصحيح. أعد تسمية العمود المكرر أو احذفه ليصبح هذا "
        "الرقم متاحاً."
    ),
    REASON_REPEATED_ROW_SIGNATURE: (
        "{metric} غير معروض — يحتوي الملف على سطور بيع لا يمكن التمييز بينها، "
        "إما لتطابقها في كل الأعمدة أو لاشتراكها في المرجع الذي يُعرِّفها، ولا "
        "توجد طريقة للتمييز بين سطر بيع مُتكرر فعلاً وسطر صُدِّر مرتين. إظهار "
        "الإجمالي يعني اختيار أحد التفسيرين نيابةً عنك. أضف مرجعاً للسطر أو "
        "الإيصال يختلف بين التكرارات الحقيقية، أو أعد التصدير بدون الصفوف "
        "المكررة، ليصبح هذا الرقم متاحاً."
    ),
    REASON_INCOMPLETE_COVERAGE: (
        "{metric} غير معروض — {column} موجود في ملفك لكن بعض الصفوف تتركه "
        "فارغاً. والإجمالي المحسوب من الصفوف التي عبّأته يصف جزءاً من نشاطك "
        "ويُقرأ كأنه يصفه كله. الأرقام الأخرى في هذا القسم غير متأثرة. عبّئ هذا "
        "العمود في كل صف ليصبح هذا الرقم متاحاً."
    ),
    REASON_DIMENSION_ABSENT: (
        "نسبة عمليات البيع التي تتضمن المنتج أو الفئة غير معروضة — لا يحتوي "
        "الملف على عمود للمنتج أو الفئة لقياس هذه النسبة. عدد الأصناف لكل "
        "عملية بيع غير متأثر."
    ),
    REASON_DIMENSION_INCOMPLETE: (
        "نسبة عمليات البيع التي تتضمن المنتج أو الفئة غير معروضة — بعض عمليات "
        "البيع لا يوجد لها منتج أو فئة مسجلة، ولذلك لا يمكن قياس هذه النسبة "
        "بصدق؛ فقد تتضمن تلك العمليات المنتج نفسه. املأ عمود المنتج أو الفئة في "
        "كل الصفوف لعرض هذه النسب. عدد الأصناف لكل عملية بيع غير متأثر."
    ),
    REASON_NEGATIVE_BASE: (
        "{metric} غير معروض — حساب نسبة التغير من قيمة بداية سالبة سيعكس "
        "المعنى الظاهر للتغير. التغير المطلق في الإيرادات غير متأثر."
    ),
    REASON_COVERAGE_INCOMPATIBLE: (
        "{metric} غير معروض — الفترتان المقارنتان غير مغطاتين بالطريقة "
        "نفسها في ملفك، ولذلك سيخلط الفرق بينهما تغيراً حقيقياً بنقص في "
        "المسجل. صدِّر ملفاً يغطي الفترتين كاملتين وللفروع نفسها، وستظهر "
        "هذه المقارنة."
    ),
}

_ACCEPTED_ARABIC_CAVEAT_MESSAGES = {
    CAVEAT_PARTIAL_WINDOW: (
        "الفترة الحالية لم تكتمل بعد. وقد قُورنت بالعدد نفسه من الأيام من "
        "بداية الفترة السابقة، حتى تغطي المقارنة المدة نفسها من النشاط. "
        "وستتغير هذه المقارنة كلما سُجل ما تبقى من الفترة."
    ),
    CAVEAT_CURRENCY_NOT_DECLARED: (
        "لا يحدد ملفك العملة المستخدمة للمبالغ. تُعرض الأرقام كما وردت من دون تحويل."
    ),
    CAVEAT_DUPLICATE_ROWS: (
        "بعض صفوف ملفك تسجل عملية البيع نفسها مرتين — كل حقل يقرأه هذا التقرير "
        "متطابق، مهما اختلف ما عداه. عملية البيع المتكررة فعلاً والعملية التي "
        "صُدِّرت مرتين تبدوان متطابقتين هنا، ولذلك لا تُعرض الإجماليات التي كانت "
        "ستحتسبها بدلاً من ذكرها وفق أحد هذين التفسيرين."
    ),
    CAVEAT_NEGATIVE_REVENUE: (
        "تتضمن بعض الصفوف قيمة بيع سالبة. أُدرجت كما وردت، وهذا صحيح إذا كانت "
        "تمثل مبالغ مستردة مسجلة في ملف المبيعات."
    ),
    CAVEAT_RETURNS_NOT_NETTED: (
        "تُعرض المرتجعات بصورة منفصلة ولم تُطرح من الإيرادات. الإيرادات هنا "
        "إجمالية قبل المرتجعات."
    ),
    CAVEAT_NULL_MEASURE_INPUTS: (
        "لا تحمل بعض الصفوف مبلغاً مسجلاً. استُبعدت من الإجماليات بدلاً من "
        "احتسابها صفراً."
    ),
    CAVEAT_UNDATED_ROWS_EXCLUDED: (
        "لا تحمل بعض الصفوف تاريخاً. استُبعدت من أي قياس حسب الفترة، لذلك "
        "تغطي الأرقام الشهرية صفوفاً أقل قليلاً من الإجماليات."
    ),
    CAVEAT_BUCKETS_TRUNCATED: (
        "يغطي ملفك فترات أكثر مما تعرضه هذه المقارنة. تستخدم المقارنة أحدث "
        "الفترات المكتملة."
    ),
    CAVEAT_PERSONAL_VALUES_REDACTED: (
        "أُزيلت قبل التحليل القيم التي بدت وكأنها تحدد أشخاصاً بعينهم. لا "
        "يعتمد عليها أي رقم في هذا التقرير."
    ),
    CAVEAT_DERIVED_OVER_MATCHED_ROWS: (
        "تستخدم الأرقام التي تجمع بين مقياسين — مثل متوسط السعر — الصفوف التي "
        "يتوفر فيها المقياسان معاً فقط. ولذلك قد تغطي صفوفاً أقل من كل مقياس منفرداً."
    ),
    CAVEAT_CHART_NOT_DRAWN: (
        "لا يظهر رسم بياني لهذا القسم. الأرقام المعروضة بجانبه مكتملة."
    ),
    CAVEAT_CURVE_SAMPLED: (
        "رُسم منحنى التركز باستخدام 100 نقطة موزعة بالتساوي على كامل نطاق "
        "القيم التي يرتّبها. وتستخدم الأرقام المعروضة بجانبه كل الصفوف."
    ),
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE: (
        "عندما تغير السعر والكمية معاً، احتُسب الجزء المشترك من التغير ضمن أثر "
        "السعر. هذه قاعدة معلنة تُطبق بالطريقة نفسها كل مرة، ولذلك يظل مجموع "
        "الأثرين مساوياً تماماً للتغير الإجمالي."
    ),
    CAVEAT_ROUNDING_RESIDUAL: (
        "أثر السعر المعروض هو التغير الإجمالي مطروحاً منه أثر الحجم، حتى "
        "يكون مجموع الأرقام الثلاثة مطابقاً تماماً كما تظهر. ولذلك يختلف "
        "بمقدار وحدة واحدة من آخر خانة عشرية معروضة عن أثر السعر محسوباً "
        "بمفرده. لم يسقط أي رقم ولم يُعدَّل شيء."
    ),
}

_ARABIC_SCRIPT = re.compile(r"[؀-ۿ]")
_EASTERN_ARABIC_DIGITS = re.compile(r"[٠-٩]")


def _refusal_wording_copy() -> dict[str, dict[str, dict[str, str]]]:
    return {
        tier: {
            language: dict(entries)
            for language, entries in table.items()
        }
        for tier, table in wording.REFUSAL_WORDING.items()
    }


def test_metric_wording_covers_every_governed_metric_in_every_language() -> None:
    assert len(_GOVERNED_METRIC_CODES) == 13
    for language in REQUIRED_LANGUAGES:
        assert set(wording.METRIC_WORDING[language]) == _GOVERNED_METRIC_CODES


def test_metric_business_name_returns_reviewed_copy() -> None:
    assert wording.metric_business_name(METRIC_REVENUE, LANGUAGE_ENGLISH) == "Revenue"
    assert wording.metric_business_name(METRIC_REVENUE, LANGUAGE_ARABIC) == "الإيرادات"


def test_metric_business_name_refuses_an_unknown_code() -> None:
    with pytest.raises(KeyError):
        wording.metric_business_name("not_a_governed_metric", LANGUAGE_ENGLISH)


def test_section_refusal_universe_is_eleven_codes() -> None:
    """A deliberate count, moved deliberately.

    `rra008.comparison.v2` adds the tenth: a window whose structural coverage the
    manifest cannot prove comparable. It is distinct from `prior_window_absent`,
    which says there is no earlier period at all -- and a reader acts on the
    difference, because re-exporting more history does not fix the first.

    Growth carries the same code: it consumes the window comparison accepted, so
    a window refused on coverage grounds refuses growth with the cause comparison
    gave rather than with a measure-shaped reason that would misattribute it.

    The eleventh is growth's alone: `RRA-008` requires both aligned windows to
    be "return-free posted-sale populations" and says a return "refuses
    growth" -- so a package recording returns refuses the decomposition rather
    than netting them out. No other family refuses on returns, and the
    comparison beside it is unaffected, which the customer wording says.

    The twelfth is the basket family's, and it arrives from the fact package
    rather than from `RRA-008`: `RRA-003` refuses every additive or
    distinct-transaction result over a repeated canonical row signature, so the
    transaction count is gone and both basket metrics with it.
    `basket._identifier_reason` reports the package's cause verbatim, and a
    section that could not say it would have to relabel the refusal as
    "identifier absent" -- naming a cause that did not occur.
    """
    assert len(_SECTION_REFUSAL_CODES) == 12


def test_refusal_wording_section_tier_covers_every_code_in_every_language() -> None:
    for language in REQUIRED_LANGUAGES:
        assert set(wording.REFUSAL_WORDING["section"][language]) == (
            _SECTION_REFUSAL_CODES
        )


def test_refusal_message_states_the_rest_of_report_is_unaffected() -> None:
    message = wording.refusal_message(
        "prior_window_absent",
        context="section",
        language=LANGUAGE_ENGLISH,
    )

    assert "unaffected" in message.lower()


def test_refusal_message_raises_on_unknown_code() -> None:
    with pytest.raises(KeyError):
        wording.refusal_message(
            "not_a_code",
            context="section",
            language=LANGUAGE_ENGLISH,
        )


def test_result_refusal_universe_is_twelve_current_codes() -> None:
    """A deliberate count, moved deliberately.

    Seven until the version compatibility gate landed, which added the unadmitted
    family pairing. Its sibling -- an unadmitted *package* pairing -- is Internal
    under `RRA-009`, because no report is published when it fires and no customer
    can encounter it.

    `rra008.basket.v2` adds the ninth: a dimension mapped but not carried on every
    eligible row. The tenth is `rra008.comparison.v2`'s coverage refusal, which the
    CAL1-11 sweep found defined and unattached -- so a comparison refused because
    the manifest could not prove the windows comparable was telling a customer
    their file covered a single period, and sending them to re-export history that
    would not help. `RRA-008` refuses that dimension's whole attach family rather
    than letting the unlabelled transactions enter only the denominator, so a
    reader who sees no rates has to be told which of the two dimension failures
    happened.

    The eleventh is `RRA-003`'s repeated canonical row signature. It had no code
    because the defect published instead of refusing: a doubled extract stated a
    doubled total and disclosed a caveat beside it, which asked the reader to
    decide which reading was true when nothing in the file answers. It is
    distinct from `required_input_unavailable` -- every input is present and
    readable -- so reusing that code would have told a customer a column was
    missing when none is.

    The twelfth separates a column that is *absent* from one that is present and
    incomplete. `RRA-004`:46 refuses a headline whose own column has gaps, and
    `required_input_unavailable` renders as "the file does not contain
    {column}" with "include the missing column" as its remedy -- a cause that did
    not occur and advice that cannot work when the column is already there.

    The number is asserted rather than derived so that
    a code arriving without its accepted bilingual prose fails here instead of
    reaching a reader as an untranslated identifier.
    """
    assert len(_RESULT_REFUSAL_CODES) == 12


def test_refusal_wording_result_tier_covers_every_code_in_every_language() -> None:
    for language in REQUIRED_LANGUAGES:
        assert set(wording.REFUSAL_WORDING["result"][language]) == (
            _RESULT_REFUSAL_CODES
        )


def test_accepted_arabic_result_messages_are_pinned() -> None:
    assert wording.REFUSAL_WORDING["result"][LANGUAGE_ARABIC] == (
        _ACCEPTED_ARABIC_RESULT_MESSAGES
    )


def test_result_refusal_message_formats_metric_placeholder() -> None:
    template = wording.refusal_message(
        REASON_ZERO_DENOMINATOR,
        context="result",
        language=LANGUAGE_ENGLISH,
    )

    filled = template.format(metric="Gross margin")
    assert "Gross margin" in filled
    assert "unaffected" in filled.lower()


def test_caveat_wording_covers_every_code_in_every_language() -> None:
    for language in REQUIRED_LANGUAGES:
        assert set(wording.CAVEAT_WORDING[language]) == _GOVERNED_CAVEAT_CODES


def test_accepted_arabic_caveat_messages_are_pinned() -> None:
    assert wording.CAVEAT_WORDING[LANGUAGE_ARABIC] == (
        _ACCEPTED_ARABIC_CAVEAT_MESSAGES
    )


def test_caveat_message_raises_on_unknown_code() -> None:
    with pytest.raises(KeyError):
        wording.caveat_message("not_a_caveat", LANGUAGE_ENGLISH)


def test_composite_dimension_refusal_uses_accepted_arabic_prose() -> None:
    message = wording.caveat_prose(
        f"basket_attach_rate:{REASON_DIMENSION_ABSENT}",
        LANGUAGE_ARABIC,
    )

    assert message == _ACCEPTED_ARABIC_RESULT_MESSAGES[REASON_DIMENSION_ABSENT]


def test_composite_section_reason_reuses_section_prose_without_identifiers() -> None:
    code = "revenue_delta_percent.year_over_year:prior_window_absent"

    message = wording.caveat_prose(code, LANGUAGE_ENGLISH)

    assert message == wording.refusal_message(
        "prior_window_absent",
        context="section",
        language=LANGUAGE_ENGLISH,
    )
    assert "revenue_delta_percent" not in message
    assert "year_over_year" not in message


def test_composite_negative_base_uses_a_localized_metric_name() -> None:
    code = "revenue_delta_percent.year_over_year:negative_base"

    english = wording.caveat_prose(code, LANGUAGE_ENGLISH)
    arabic = wording.caveat_prose(code, LANGUAGE_ARABIC)

    assert "Revenue percentage change" in english
    assert "نسبة تغير الإيرادات" in arabic
    assert "revenue_delta_percent" not in english
    assert "year_over_year" not in english


def _iter_language_values():
    tables = {
        "METRIC_WORDING": wording.METRIC_WORDING,
        "DERIVED_METRIC_WORDING": wording.DERIVED_METRIC_WORDING,
        "LABEL_WORDING": wording.LABEL_WORDING,
        "SECTION_HEADINGS": wording.SECTION_HEADINGS,
        "CHART_DESCRIPTIONS": wording.CHART_DESCRIPTIONS,
        "CAVEAT_WORDING": wording.CAVEAT_WORDING,
        **{
            f"REFUSAL_WORDING[{tier}]": table
            for tier, table in wording.REFUSAL_WORDING.items()
        },
    }
    for table_name, table in tables.items():
        for language, entries in table.items():
            for key, value in entries.items():
                yield table_name, language, key, value


def test_bilingual_values_use_their_declared_script() -> None:
    violations = [
        (table, language, key)
        for table, language, key, value in _iter_language_values()
        if (
            language == LANGUAGE_ENGLISH
            and _ARABIC_SCRIPT.search(value)
            or language == LANGUAGE_ARABIC
            and not _ARABIC_SCRIPT.search(value)
        )
    ]

    assert violations == []


def test_no_eastern_arabic_numerals_or_owner_placeholders_remain() -> None:
    violations = [
        (table, language, key)
        for table, language, key, value in _iter_language_values()
        if _EASTERN_ARABIC_DIGITS.search(value)
        or value == "__NEEDS_OWNER_AUTHORSHIP__"
    ]

    assert violations == []


def test_metric_wording_guard_raises_on_incomplete_table(monkeypatch) -> None:
    broken = {
        language: dict(entries)
        for language, entries in wording.METRIC_WORDING.items()
    }
    del broken[LANGUAGE_ENGLISH][METRIC_REVENUE]
    monkeypatch.setattr(wording, "METRIC_WORDING", broken)

    with pytest.raises(RuntimeError, match="metric"):
        wording._assert_metric_wording_complete()


def test_refusal_wording_guard_raises_on_incomplete_table(monkeypatch) -> None:
    broken = _refusal_wording_copy()
    del broken["result"][LANGUAGE_ENGLISH][REASON_DIMENSION_ABSENT]
    monkeypatch.setattr(wording, "REFUSAL_WORDING", broken)

    with pytest.raises(RuntimeError, match="refusal"):
        wording._assert_refusal_wording_complete()


def test_refusal_wording_guard_raises_when_a_tier_is_missing(monkeypatch) -> None:
    broken = _refusal_wording_copy()
    del broken["section"]
    monkeypatch.setattr(wording, "REFUSAL_WORDING", broken)

    with pytest.raises(RuntimeError, match="tier"):
        wording._assert_refusal_wording_complete()


def test_refusal_wording_guard_raises_when_a_language_is_missing(monkeypatch) -> None:
    broken = _refusal_wording_copy()
    del broken["section"][LANGUAGE_ARABIC]
    monkeypatch.setattr(wording, "REFUSAL_WORDING", broken)

    with pytest.raises(RuntimeError, match="language"):
        wording._assert_refusal_wording_complete()


def test_caveat_wording_guard_raises_on_incomplete_table(monkeypatch) -> None:
    broken = {
        language: dict(entries)
        for language, entries in wording.CAVEAT_WORDING.items()
    }
    del broken[LANGUAGE_ENGLISH][CAVEAT_CURRENCY_NOT_DECLARED]
    monkeypatch.setattr(wording, "CAVEAT_WORDING", broken)

    with pytest.raises(RuntimeError, match="caveat"):
        wording._assert_caveat_wording_complete()


def test_wording_module_imports_cleanly_with_complete_copy() -> None:
    importlib.reload(wording)


# --- CAL1-11 compatibility sweep: registry derivation ---------------------
#
# The cross-product tests above prove every code *in* a registry has prose in
# both languages. They cannot prove the registry holds every code production
# actually defines, because two of the three registries are hand-listed sets of
# imported constants: adding `CAVEAT_NEW_THING` to `facts.py` and stating it on a
# result leaves `_GOVERNED_CAVEAT_CODES` unchanged, every test above green, and a
# customer reading an untranslated code.
#
# The section tier already closes this: `GOVERNED_SECTION_REASONS` is derived
# from `SECTION_REASONS` (`bundle.py`), and `_SECTION_REFUSAL_CODES` above is
# derived from *that*, so the chain from definition to prose is unbroken. These
# two tests give the caveat and result tiers the same property by deriving the
# expected universe from the production modules rather than restating it.
#
# Introspection is the point, not a shortcut. A hand-listed expectation here
# would be the very thing it is meant to catch -- and so would a hand-listed set
# of modules to look in. An earlier version of this scan named four modules and
# a `CAVEAT_*` added to `analysis/basket.py` survived it: a guard that cannot see
# the surface a new constant appears on disarms itself silently. The package is
# walked instead, so a new module is covered the day it is added.
def _rra_module_names() -> tuple[str, ...]:
    """Every importable module in `khepri.rra`, the package that owns caveats.

    The package root is included explicitly: `walk_packages` yields descendants
    and never the package itself, so a caveat defined in `khepri/rra/__init__.py`
    would sit outside a walk that looks complete.
    """
    package = importlib.import_module("khepri.rra")
    return tuple(
        sorted(
            {package.__name__}
            | {
                info.name
                for info in pkgutil.walk_packages(
                    package.__path__, f"{package.__name__}."
                )
            }
        )
    )


def _constants_named(module_name: str, prefix: str) -> frozenset[str]:
    """Every `str` constant in one module whose name starts with `prefix`.

    An import failure propagates. Swallowing it would let a module that defines
    an unregistered `CAVEAT_*` and happens to raise on import contribute nothing
    to the scan -- the other modules keep the comparison non-empty, so the sweep
    would report success over a module it never read. That is the same
    self-disarming shape the walk replaced, one level further down.
    """
    module = importlib.import_module(module_name)
    return frozenset(
        value
        for name in vars(module)
        if name.startswith(prefix) and isinstance(value := getattr(module, name), str)
    )


def test_every_caveat_constant_defined_in_production_is_a_governed_caveat() -> None:
    """A caveat a module can state must be a caveat the wording tables know.

    Derived from the modules rather than listed, so a new `CAVEAT_*` constant
    fails here until it is added to `_GOVERNED_CAVEAT_CODES` -- which the
    cross-product tests then force to carry Arabic and English prose.
    """
    modules = _rra_module_names()
    assert modules, "walked no modules; the scan is looking in the wrong place"
    defined = frozenset().union(
        *(_constants_named(name, "CAVEAT_") for name in modules)
    )
    assert defined, "no CAVEAT_* constants found; the scan is looking in the wrong place"
    assert defined == frozenset(wording._GOVERNED_CAVEAT_CODES), sorted(
        defined.symmetric_difference(wording._GOVERNED_CAVEAT_CODES)
    )


#: The five codes both customer tiers state. A shared code is deliberate and
#: `bundle.py` says why: a family that refuses for one of these hands its own
#: code straight to the section, because two spellings of one condition would
#: make the hand-off a translation nobody would remember to keep honest.
_SHARED_TIER_CODES = frozenset(
    {
        "coverage_structurally_incompatible",
        "family_version_pairing_unadmitted",
        "incomplete_transaction_identifiers",
        "repeated_row_signature",
        "required_input_unavailable",
    }
)


def test_the_two_customer_tiers_are_the_only_ones_wording_states() -> None:
    """`section` and `result` are different vocabularies that overlap by design.

    A section refusal says why a whole analysis is absent; a result refusal says
    why one metric inside a produced package is. They are not two spellings of
    one set, so a sweep that unioned them would report their difference as drift.
    Five codes appear in both, deliberately -- pinned here so a sixth is a
    decision someone makes rather than one that arrives.

    The internal `GOVERNED_REASONS` in `bundle` and `narrative` carry
    `BundleRefused`/`NarrativeRefused` integrity codes, which reach no customer
    and are correctly absent from both tiers.
    """
    assert set(wording.REFUSAL_WORDING) == {"section", "result"}
    assert _SECTION_REFUSAL_CODES & _RESULT_REFUSAL_CODES == _SHARED_TIER_CODES


# --- CAL1-11 finding F5: tables without a completeness guard ---------------
#
# F5 filed five tables as unguarded. One of the five, `SECTION_HEADINGS`, was
# already guarded at `wording.py` by a bare import-time loop -- the finding was
# wrong about it, and that is recorded here rather than silently skipped. The
# other four are guarded now, and each test below drives its guard directly with
# a broken table, because a guard is only evidence if it can fail.


def test_kind_qualifier_guard_raises_when_a_language_loses_its_only_kind(
    monkeypatch,
) -> None:
    broken = {
        language: dict(entries)
        for language, entries in wording.KIND_QUALIFIERS.items()
    }
    broken[LANGUAGE_ENGLISH].clear()
    monkeypatch.setattr(wording, "KIND_QUALIFIERS", broken)

    with pytest.raises(RuntimeError, match="kind"):
        wording._assert_kind_qualifiers_complete()


def test_chart_description_guard_raises_when_a_governed_kind_has_no_description(
    monkeypatch,
) -> None:
    """The guard's set is derived from the chart-kind constants, not retyped.

    `charts.py` composes `chart_description.{spec.kind}` and `excel.py` reads it
    back the same way, so a kind added there with no description here is a
    `KeyError` on one surface and a chart with no accessible description on the
    other.
    """
    broken = {
        language: dict(entries)
        for language, entries in wording.CHART_DESCRIPTIONS.items()
    }
    del broken[LANGUAGE_ARABIC]["chart_description.line"]
    monkeypatch.setattr(wording, "CHART_DESCRIPTIONS", broken)

    with pytest.raises(RuntimeError, match="chart"):
        wording._assert_chart_descriptions_complete()


def test_chart_description_codes_follow_a_kind_added_to_the_governed_set(
    monkeypatch,
) -> None:
    """The direction the deletion case above cannot see: the scope grows.

    Removing a description proves the guard notices a table that shrank, and it
    passes just as well when `_CHART_DESCRIPTION_CODES` hand-lists the three kinds
    it knows -- the deletion is *inside* the scope it named. A fourth kind admitted
    in `bundle` is outside it: an enumerated set stays at three, compares equal to
    a three-entry table, and the chart reaches Excel with a `KeyError` on a
    description nobody wrote.

    The codes are computed once at import, so patching `GOVERNED_CHART_KINDS` alone
    changes nothing a test can observe -- the module already holds the value it
    derived. Re-importing is what makes the derivation run against the widened set,
    which is why this reloads rather than calling the guard directly. Derived, the
    codes become four against a three-entry table and the import-time call raises;
    hand-listed, nothing raises and this fails.

    `monkeypatch.undo()` precedes the restoring reload deliberately: reloading first
    would re-derive from the patched set and leave the widened codes installed for
    every test after this one.
    """
    monkeypatch.setattr(
        bundle,
        "GOVERNED_CHART_KINDS",
        frozenset(bundle.GOVERNED_CHART_KINDS | {"stacked_bar"}),
    )
    try:
        with pytest.raises(RuntimeError, match="chart"):
            importlib.reload(wording)
    finally:
        monkeypatch.undo()
        importlib.reload(wording)


def test_every_governed_chart_kind_has_a_description_code() -> None:
    """An equality, so neither side may drift from the other.

    A subset assertion would admit a code for a kind `bundle` does not govern --
    the reverse leak: wording for a chart no surface can draw. This states the
    extent; the reload case above states the derivation.
    """
    derived = frozenset(
        f"chart_description.{kind}" for kind in bundle.GOVERNED_CHART_KINDS
    )

    assert derived == wording._CHART_DESCRIPTION_CODES


def test_derived_metric_guard_raises_when_one_language_names_a_metric(
    monkeypatch,
) -> None:
    """`business_metric_name` falls back here per language.

    An entry present in English alone names a figure on the English surface and
    leaves the same figure unnamed in Arabic, which is the parity obligation
    `RRA-006` states and the one this table could break quietly.
    """
    broken = {
        language: dict(entries)
        for language, entries in wording.DERIVED_METRIC_WORDING.items()
    }
    del broken[LANGUAGE_ARABIC]["basket_attach_rate"]
    monkeypatch.setattr(wording, "DERIVED_METRIC_WORDING", broken)

    with pytest.raises(RuntimeError, match="language"):
        wording._assert_derived_metric_wording_complete()


def test_derived_metric_guard_raises_when_a_metric_is_named_in_two_tables(
    monkeypatch,
) -> None:
    """A code in both tables makes `METRIC_WORDING` win silently.

    `business_metric_name` consults `METRIC_WORDING` first, so a derived entry
    for the same code sits there looking authoritative and never renders. The
    duplicate is added in *both* languages, so the parity check above passes and
    this test proves the disjointness check rather than re-proving parity.
    """
    broken = {
        language: {**entries, "revenue": "Revenue"}
        for language, entries in wording.DERIVED_METRIC_WORDING.items()
    }
    monkeypatch.setattr(wording, "DERIVED_METRIC_WORDING", broken)

    with pytest.raises(RuntimeError, match="two tables"):
        wording._assert_derived_metric_wording_complete()


def test_disclosure_guard_raises_when_a_governed_narrative_state_has_no_prose(
    monkeypatch,
) -> None:
    """`disclosure()` indexes `_DISCLOSURE` by the package's narrative state.

    A state added to `GOVERNED_NARRATIVE_STATES` without prose here raises
    `KeyError` mid-render, after the analysis succeeded, on the one paragraph
    that tells a reader the commentary was generated automatically.
    """
    broken = {
        state: dict(entries) for state, entries in bundle._DISCLOSURE.items()
    }
    del broken[bundle.NARRATIVE_OMITTED]
    monkeypatch.setattr(bundle, "_DISCLOSURE", broken)

    with pytest.raises(RuntimeError, match="narrative state"):
        bundle._assert_disclosure_complete()


def test_section_headings_were_already_guarded_when_f5_filed_them() -> None:
    """F5 named `SECTION_HEADINGS`, and F5 was wrong about that one.

    Recorded rather than dropped: a later reader comparing the finding against
    this slice would otherwise see four of five tables addressed and reasonably
    conclude one was missed. The guard is a bare import-time loop rather than a
    named `_assert_*` function, which is why a reader scanning for the naming
    convention could miss it -- so the property is asserted here directly.
    """
    for headings in wording.SECTION_HEADINGS.values():
        assert set(headings) == set(bundle.ORDERED_SECTIONS)


def test_label_wording_guard_raises_when_a_localizable_code_lacks_wording(
    monkeypatch,
) -> None:
    """Beyond F5, and found while closing it: the same shape, the same cost.

    `worded` deliberately refuses to fall back to the raw code, because an
    identifier on a customer axis is the failure that function exists to
    prevent. So a missing entry here is an exception during chart rendering
    rather than a cosmetic gap, and the import is where it should surface.

    The governed set is derived from the two branches `category_of` can take: a
    governed comparison mode becomes `label.{mode}`, and a charted figure with no
    label of its own becomes `metric.{metric}`, which for marks is the growth
    family.
    """
    broken = {
        language: dict(entries) for language, entries in wording.LABEL_WORDING.items()
    }
    del broken[LANGUAGE_ENGLISH]["label.year_over_year"]
    monkeypatch.setattr(wording, "LABEL_WORDING", broken)

    with pytest.raises(RuntimeError, match="chart code"):
        wording._assert_label_wording_complete()


def test_label_wording_covers_every_mode_and_growth_metric_category_of_emits() -> None:
    """The table's key set equals what `category_of` can localize, exactly.

    Asserted against the governed sources rather than against the table's own
    derived constant: importing `_LOCALIZABLE_CHART_CODES` to check the table it
    built would compare a restatement with itself.
    """
    expected = {f"label.{mode}" for mode in bundle.GOVERNED_FIGURE_LABELS} | {
        f"metric.{metric}" for metric in GOVERNED_METRICS
    }

    for entries in wording.LABEL_WORDING.values():
        assert set(entries) == expected
