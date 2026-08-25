from __future__ import annotations

import importlib
import re

import pytest

from khepri.rra.analysis.basket import REASON_DIMENSION_ABSENT
from khepri.rra.analysis.comparison import REASON_NEGATIVE_BASE
from khepri.rra.analysis.growth import (
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
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
    REASON_INCOMPLETE_IDENTIFIERS,
    REASON_INPUT_UNAVAILABLE,
    REASON_RECONCILIATION_FAILED,
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
        REASON_INCOMPLETE_IDENTIFIERS,
        REASON_AMBIGUOUS_MAPPING,
        REASON_DIMENSION_ABSENT,
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
        CAVEAT_INTERACTION_ASSIGNED_TO_PRICE,
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
    REASON_DIMENSION_ABSENT: (
        "نسبة عمليات البيع التي تتضمن المنتج أو الفئة غير معروضة — لا يحتوي "
        "الملف على عمود للمنتج أو الفئة لقياس هذه النسبة. عدد الأصناف لكل "
        "عملية بيع غير متأثر."
    ),
    REASON_NEGATIVE_BASE: (
        "{metric} غير معروض — حساب نسبة التغير من قيمة بداية سالبة سيعكس "
        "المعنى الظاهر للتغير. التغير المطلق في الإيرادات غير متأثر."
    ),
}

_ACCEPTED_ARABIC_CAVEAT_MESSAGES = {
    CAVEAT_CURRENCY_NOT_DECLARED: (
        "لا يحدد ملفك العملة المستخدمة للمبالغ. تُعرض الأرقام كما وردت من دون تحويل."
    ),
    CAVEAT_DUPLICATE_ROWS: (
        "بعض صفوف ملفك مكررة بالكامل. احتُسبت كما وردت — إذا كانت مبيعات "
        "متكررة فعلاً فهذا صحيح، وإذا كانت خطأ في التصدير فالإجماليات أعلى من الواقع."
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
        "المنتجات. وتستخدم الأرقام المعروضة بجانبه كل الصفوف."
    ),
    CAVEAT_INTERACTION_ASSIGNED_TO_PRICE: (
        "عندما تغير السعر والكمية معاً، احتُسب الجزء المشترك من التغير ضمن أثر "
        "السعر. هذه قاعدة معلنة تُطبق بالطريقة نفسها كل مرة، ولذلك يظل مجموع "
        "الأثرين مساوياً تماماً للتغير الإجمالي."
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


def test_section_refusal_universe_is_eight_codes() -> None:
    assert len(_SECTION_REFUSAL_CODES) == 8


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


def test_result_refusal_universe_is_eight_current_codes() -> None:
    """A deliberate count, moved deliberately.

    Seven until the version compatibility gate landed. It added one result-tier
    refusal, the unadmitted family pairing, so the universe is eight. Its sibling
    -- an unadmitted package pairing -- is Internal under `RRA-009`, because no
    report is published when it fires and no customer can encounter it. The number is asserted rather than derived so that
    a code arriving without its accepted bilingual prose fails here instead of
    reaching a reader as an untranslated identifier.
    """
    assert len(_RESULT_REFUSAL_CODES) == 8


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
