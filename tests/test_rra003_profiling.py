from __future__ import annotations

import hashlib

import pytest

from khepri.rra.intake import CSV_MEDIA_TYPE, XLSX_MEDIA_TYPE
from khepri.rra.profiling import (
    MAX_PROFILED_COLUMNS,
    PROFILE_VERSION,
    TYPE_DATE,
    TYPE_DECIMAL,
    TYPE_EMPTY,
    TYPE_INTEGER,
    TYPE_TEXT,
    DatasetProfile,
    ProfileRejected,
    build_profile,
)
from tests.rra_workbooks import workbook

GOLDEN = (
    b"date,revenue,units,store,category\n"
    b"2026-01-05,125.50,3,Cairo Downtown,Beverages\n"
    b"2026-01-06,90.00,2,Giza Mall,Snacks\n"
    b"2026-01-07,210.25,5,Cairo Downtown,Beverages\n"
)


def profile(content: bytes, *, media_type: str = CSV_MEDIA_TYPE) -> DatasetProfile:
    return build_profile(
        content=content,
        media_type=media_type,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )


def test_golden_schema_is_profiled_without_exposing_text_values() -> None:
    result = profile(GOLDEN)

    assert result.profile_version == PROFILE_VERSION
    assert result.row_count == 3
    assert result.column_count == 5
    assert [column.safe_label for column in result.columns] == [
        "date",
        "revenue",
        "units",
        "store",
        "category",
    ]
    assert [column.inferred_type for column in result.columns] == [
        TYPE_DATE,
        TYPE_DECIMAL,
        TYPE_INTEGER,
        TYPE_TEXT,
        TYPE_TEXT,
    ]
    date_column, revenue, units, store, _ = result.columns
    assert (date_column.minimum, date_column.maximum) == ("2026-01-05", "2026-01-07")
    assert date_column.date_format == "iso_date"
    assert (revenue.minimum, revenue.maximum) == ("90.00", "210.25")
    assert (units.minimum, units.maximum) == ("2", "5")
    assert (store.minimum, store.maximum) == (None, None)
    assert store.distinct_count == 2
    assert result.findings == ()


def test_profiling_is_deterministic_across_reruns() -> None:
    assert profile(GOLDEN).digest == profile(GOLDEN).digest


def test_profile_digest_changes_with_content() -> None:
    other = GOLDEN.replace(b"125.50", b"125.51")

    assert profile(GOLDEN).digest != profile(other).digest


def test_null_rate_is_exact_and_decimal() -> None:
    content = b"date,revenue\n2026-01-05,1\n2026-01-06,\n2026-01-07,\n"

    revenue = profile(content).columns[1]

    assert revenue.null_count == 2
    assert revenue.non_null_count == 1
    assert revenue.null_rate == "0.6667"
    assert "high_null_rate" in revenue.findings


def test_mixed_numeric_and_text_column_is_flagged() -> None:
    content = b"date,revenue\n2026-01-05,125.50\n2026-01-06,not available\n"

    revenue = profile(content).columns[1]

    assert revenue.inferred_type == TYPE_TEXT
    assert "mixed_numeric_and_text" in revenue.findings
    assert (revenue.minimum, revenue.maximum) == (None, None)


def test_currency_decorated_numbers_are_not_silently_parsed() -> None:
    content = b"date,revenue\n2026-01-05,EGP 125.50\n2026-01-06,EGP 90.00\n"

    revenue = profile(content).columns[1]

    assert revenue.inferred_type == TYPE_TEXT


def test_unambiguous_day_first_dates_are_accepted() -> None:
    content = b"day,units\n25/01/2026,1\n05/01/2026,2\n"

    column = profile(content).columns[0]

    assert column.inferred_type == TYPE_DATE
    assert column.date_format == "day_first"
    assert (column.minimum, column.maximum) == ("2026-01-05", "2026-01-25")


def test_ambiguous_day_or_month_order_is_refused_instead_of_guessed() -> None:
    content = b"day,units\n05/01/2026,1\n06/02/2026,2\n"

    column = profile(content).columns[0]

    assert column.inferred_type == TYPE_TEXT
    assert column.date_format is None
    assert "ambiguous_date_order" in column.findings


def test_month_periods_are_recognized_as_dates() -> None:
    content = b"period,units\n2026-01,1\n2026-02,2\n"

    column = profile(content).columns[0]

    assert column.inferred_type == TYPE_DATE
    assert column.date_format == "iso_month"


def test_personal_data_columns_are_detected_by_label_and_shape() -> None:
    content = (
        b"date,units,contact_email,mobile\n"
        b"2026-01-05,1,buyer.one@example.com,+201234567890\n"
        b"2026-01-06,2,buyer.two@example.com,+201234567891\n"
    )

    _, _, email, mobile = profile(content).columns

    assert email.personal_data_risk is True
    assert email.personal_data_signals == ("label_email", "value_email")
    assert mobile.personal_data_risk is True
    assert "label_phone" in mobile.personal_data_signals


def test_personal_data_columns_never_expose_a_value_range() -> None:
    content = (
        b"date,national_id\n"
        b"2026-01-05,2980112345678\n"
        b"2026-01-06,2980112345679\n"
    )

    national_id = profile(content).columns[1]

    assert national_id.inferred_type == TYPE_INTEGER
    assert national_id.personal_data_risk is True
    assert (national_id.minimum, national_id.maximum) == (None, None)


def test_payment_card_shape_is_detected_without_a_matching_label() -> None:
    content = b"date,reference\n2026-01-05,4111111111111111\n2026-01-06,5500005555555559\n"

    reference = profile(content).columns[1]

    assert reference.personal_data_risk is True
    assert "value_payment_card" in reference.personal_data_signals


def test_store_and_customer_id_labels_are_not_treated_as_personal_data() -> None:
    content = b"date,store,customer_id\n2026-01-05,Cairo,c-1\n2026-01-06,Giza,c-2\n"

    _, store, customer_id = profile(content).columns

    assert store.personal_data_risk is False
    assert customer_id.personal_data_risk is False


def test_arabic_headers_survive_safe_label_normalization() -> None:
    content = "التاريخ,المبيعات\n2026-01-05,125.50\n".encode()

    result = profile(content)

    assert [column.safe_label for column in result.columns] == ["التاريخ", "المبيعات"]


def test_formula_and_control_characters_are_stripped_from_safe_labels() -> None:
    content = b'"=cmd|calc",\t revenue \n2026-01-05,1\n'

    result = profile(content)

    assert [column.safe_label for column in result.columns] == ["cmdcalc", "revenue"]


def test_empty_header_falls_back_to_a_positional_safe_label() -> None:
    content = b'date," "\n2026-01-05,1\n'

    result = profile(content)

    assert result.columns[1].safe_label == "column_2"


def test_all_null_column_is_reported_as_empty() -> None:
    content = b"date,note\n2026-01-05,\n2026-01-06,\n"

    note = profile(content).columns[1]

    assert note.inferred_type == TYPE_EMPTY
    assert "all_values_null" in note.findings
    assert note.distinct_count == 0


def test_whitespace_padding_is_reported_and_normalized() -> None:
    content = b'date,store\n2026-01-05," Cairo "\n2026-01-06,Cairo\n'

    store = profile(content).columns[1]

    assert "whitespace_padded_values" in store.findings
    assert store.distinct_count == 1


def test_header_only_dataset_reports_no_data_rows() -> None:
    result = profile(b"date,revenue\n")

    assert result.row_count == 0
    assert "no_data_rows" in result.findings


def test_column_count_above_the_profiler_limit_is_rejected() -> None:
    header = ",".join(f"c{index}" for index in range(MAX_PROFILED_COLUMNS + 1))
    row = ",".join("1" for _ in range(MAX_PROFILED_COLUMNS + 1))
    content = f"{header}\n{row}\n".encode()

    with pytest.raises(ProfileRejected):
        profile(content)


def test_unsupported_media_type_is_refused() -> None:
    with pytest.raises(ProfileRejected):
        profile(b"date,revenue\n2026-01-05,1\n", media_type="application/json")


def test_unparsable_content_is_refused() -> None:
    with pytest.raises(ProfileRejected):
        profile(b"PK\x03\x04 not a workbook", media_type=XLSX_MEDIA_TYPE)


def test_xlsx_and_csv_inputs_profile_to_the_same_schema() -> None:
    content = workbook(
        [
            ["date", "revenue", "units"],
            ["2026-01-05", "125.50", "3"],
            ["2026-01-06", "90.00", "2"],
        ]
    )

    result = profile(content, media_type=XLSX_MEDIA_TYPE)

    assert result.row_count == 2
    assert [column.safe_label for column in result.columns] == ["date", "revenue", "units"]
    assert [column.inferred_type for column in result.columns] == [
        TYPE_DATE,
        TYPE_DECIMAL,
        TYPE_INTEGER,
    ]
