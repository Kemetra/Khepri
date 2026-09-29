"""The results a package refused on its own, as a report states them (`RRA-018` FR-246, FR-247).

A refused result reaches the reader as its name and its reason, and this module composes both
from words that already exist. It authors no word.

**The name.** A core metric is named by its business name. A composed breakdown is named by
its measure, which reads "Revenue" because a figure row also carries its own label. A refusal
carries none, so "Revenue" alone would tell a reader revenue was refused on a page whose
Overview states it. The breakdown therefore adds its dimension, joined as the figure rows join
a name and a label: "Revenue — Sales channel". A comparison dimension is named by the journey
label of the column a customer mapped; a period, which no column names, by
`wording.BREAKDOWN_QUALIFIERS`.

**The reason.** It is `wording.caveat_prose`'s, the one resolver family-scoped refusals already
use, with its `#560`/`#575` rules. With no recorded input the result sentence would name the
metric as a missing column, which is false, so it falls back to the section sentence. Several
refusals then share one sentence, and a reader is told it once, above every name it covers --
`wording.stated_once`'s rule, applied by sentence.

**Why a module of its own.** `RRA-018`, as amended, places this composition here rather than in
`wording.py`. Its functions share no data with that module's tables, so putting them there gave
the file a responsibility it does not otherwise have, which CodeScene's cohesion rule refused.
`wording.py` keeps what is wording: the region's labels and the period qualifier.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

from khepri.rra import facts
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering import wording

LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)


@cache
def _composed_results() -> dict[str, tuple[str, str]]:
    """Every composed breakdown code and what it was composed from.

    Built from the constants the builders iterate, and looked up rather than parsed: an unknown
    code fails closed instead of being split into a measure and a dimension nobody governs.
    """
    return {
        f"{measure}_by_{dimension}": (measure, dimension)
        for measure in facts.SERIES_MEASURES
        for dimension in facts.SERIES_DIMENSIONS
    }


#: Every code a package's `RefusedResult` can carry: a core metric, or a breakdown.
REFUSABLE_RESULT_CODES: frozenset[str] = facts.GOVERNED_METRICS | frozenset(_composed_results())


@dataclass(frozen=True, slots=True)
class RefusedGroup:
    """One reason, stated once, and the refused results it covers, in package order."""

    prose: str
    names: tuple[str, ...]


def _qualifier(dimension: str, language: str) -> str:
    if dimension in facts.COMPARISON_DIMENSIONS:
        return wording.column_label(dimension, language)
    return wording.BREAKDOWN_QUALIFIERS[language][dimension]


def refused_result_name(result: str, language: str) -> str:
    """A refused result's name on the page, refusing any code outside the governed set."""
    code = result.split(".", maxsplit=1)[0]
    name = wording.business_metric_name(code, language)
    if code not in REFUSABLE_RESULT_CODES or name is None:
        raise KeyError(result)
    composed = _composed_results().get(code)
    if composed is None:
        return name
    return f"{name} — {_qualifier(composed[1], language)}"


def refused_result_groups(
    refusals: Iterable[facts.RefusedResult], language: str
) -> tuple[RefusedGroup, ...]:
    """The bundle's refusals as the page states them: each sentence once, then its names."""
    grouped: dict[str, list[str]] = {}
    for refusal in refusals:
        prose = wording.caveat_prose(
            f"{refusal.metric}{wording.RESULT_CAVEAT_SEPARATOR}{refusal.reason}",
            language,
            refusing_input=refusal.input,
        )
        grouped.setdefault(prose, []).append(refused_result_name(refusal.metric, language))
    return tuple(RefusedGroup(prose=prose, names=tuple(names)) for prose, names in grouped.items())


def assert_refused_result_names_complete() -> None:
    """Every refusable code names itself, distinctly, in every language.

    Read from `REFUSABLE_RESULT_CODES` rather than from any table's own keys, for
    `wording._assert_dimension_names_complete`'s reason: the failure this catches is a code a
    package can refuse and no page can name -- which would refuse the whole report at render --
    or two codes a reader could not tell apart.
    """
    for language in LANGUAGES:
        try:
            names = [refused_result_name(code, language) for code in sorted(REFUSABLE_RESULT_CODES)]
        except KeyError as missing:
            message = f"a refused result has no name in {language}: {missing}"
            raise RuntimeError(message) from None
        if len(set(names)) != len(names):
            message = f"two refused results would read the same in {language}"
            raise RuntimeError(message)


assert_refused_result_names_complete()


def _refused_result_names() -> frozenset[str]:
    """Every name a refused result can be given, in every language."""
    return frozenset(
        refused_result_name(code, language)
        for code in REFUSABLE_RESULT_CODES
        for language in LANGUAGES
    )


#: For surfaces that must show a cell holds governed text (the workbook's cell provenance).
REFUSED_RESULT_NAMES = _refused_result_names()
