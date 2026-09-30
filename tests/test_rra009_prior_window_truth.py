"""`RRA-009` §Refusals: the `prior_window_absent` sentence is true wherever it prints.

SCRUM-21 A4. The sentence said "Your file covers a single period". The code fires
per comparison mode, so a file with several periods, whose period-over-period
comparison is answered, still refuses year-over-year with it. The page then states
a comparison between the file's periods and, beside it, that the file holds only
one period. That is a wrong second part under the five-part rule.

What stays open is naming the basis, which needs prose keyed by mode and so an
`RRA-009` amendment. This module holds only the claim the sentence may not make.
"""

from __future__ import annotations

import json

from khepri.rra.rendering.wording import LANGUAGE_ARABIC, LANGUAGE_ENGLISH, caveat_prose
from tests.rra_printed_support import retail_bundle, web_documents

_YEAR_OVER_YEAR_ABSENT = "revenue_delta_absolute.year_over_year:prior_window_absent"

#: What the sentence claimed, in each language: that the file holds one period.
_SINGLE_PERIOD_CLAIM = {
    LANGUAGE_ENGLISH: "covers a single period",
    LANGUAGE_ARABIC: "يغطي ملفك فترة واحدة",
}


def test_the_fixture_answers_one_basis_and_refuses_the_other() -> None:
    """The case under test is present: several periods, and year-over-year refused."""
    document = json.dumps(retail_bundle().as_document(), default=str)

    assert _YEAR_OVER_YEAR_ABSENT in document
    assert "period_over_period:" not in document, "period-over-period must be answered"
    assert '"metric": "revenue_delta_absolute"' in document


def test_a_file_with_several_periods_is_not_told_it_has_one() -> None:
    """The printed report and the sentence itself make no single-period claim."""
    documents = web_documents()

    for language, claim in _SINGLE_PERIOD_CLAIM.items():
        prose = caveat_prose(_YEAR_OVER_YEAR_ABSENT, language)
        assert prose in documents[language], f"{language}: the sentence is not printed"
        assert claim not in prose, f"{language}: {prose}"
