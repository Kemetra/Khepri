"""What a value's dimension is called beside it, in each language (`RRA-006`, SCRUM-26 A3b).

A product `Water` and a category `Water` share one source value. The figure carries the
dimension as a governed token and its label stays the bare value; every surface composes the
two through `qualified`. A module of its own for `refused_results`' reason: this is one
composition with its own table, which shares no data with `wording`'s, and `wording.worded` is
its only caller there.
"""

from __future__ import annotations

from khepri.rra.analysis import basket
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH

#: The qualifier name of each dimension. Governed wording in both languages, distinct from
#: `wording.DIMENSION_NAMES`' "each category", which describes a series.
DIMENSION_QUALIFIERS: dict[str, dict[str, str]] = {
    LANGUAGE_ENGLISH: {"product": "product", "category": "category"},
    LANGUAGE_ARABIC: {"product": "منتج", "category": "فئة"},
}

#: How a value and its qualifier name are composed, per language.
_QUALIFIED = {
    LANGUAGE_ENGLISH: "{value} ({qualifier})",
    LANGUAGE_ARABIC: "{value} ({qualifier})",
}


def _assert_dimension_qualifiers_complete() -> None:
    """Every dimension a figure can carry is named in every language.

    Read from `basket.GOVERNED_DIMENSIONS`, the vocabulary the token is drawn from,
    rather than from this table's own keys: a token with no name would raise during a
    customer's render.
    """
    languages = {LANGUAGE_ARABIC, LANGUAGE_ENGLISH}
    covered = set(DIMENSION_QUALIFIERS) == languages == set(_QUALIFIED)
    named = all(
        set(names) == set(basket.GOVERNED_DIMENSIONS) for names in DIMENSION_QUALIFIERS.values()
    )
    if not (covered and named):
        raise RuntimeError("every governed dimension needs a qualifier name in every language")


_assert_dimension_qualifiers_complete()


def qualified(value: str, dimension: str | None, language: str) -> str:
    """A customer value with its dimension's qualifier name, or unchanged without one."""
    if dimension is None:
        return value
    return _QUALIFIED[language].format(
        value=value, qualifier=DIMENSION_QUALIFIERS[language][dimension]
    )
