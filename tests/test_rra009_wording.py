from __future__ import annotations

import pytest

from khepri.rra.analysis.growth import GOVERNED_METRICS
from khepri.rra.bundle import GOVERNED_SECTION_REASONS
from khepri.rra.facts import (
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
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, REQUIRED_LANGUAGES
from khepri.rra.rendering import wording

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
