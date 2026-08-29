"""`T1-08`: parity, fail-closed, and no-duplicate-truth across the catalog.

Three named properties, each over the customer-visible metric, definition,
quality and evidence surfaces. They are separated deliberately: a single
"everything works" test passes with any one of them broken, and `RRA-011`'s
verification clause names all three.

**No-duplicate-truth is the load-bearing one**, and the one this program is most
likely to fail by accident. `RRA-011` requires a slice to *reduce* the
repository's count of hand-maintained code lists rather than add one — so this
counts them, mechanically, rather than asserting the intent.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from khepri.rra import definitions, facts, populations
from khepri.rra.analysis import basket, comparison, concentration, growth
from khepri.rra.rendering import wording
from tests.rra009_fixtures import rich_bundle

LANGUAGES = ("en", "ar")

#: A set or frozenset whose body is three or more dotted or bare constant names,
#: which is what a hand-maintained code list looks like. Three because a pair is
#: as likely to be a genuine two-element vocabulary as a copied list.
_HAND_LISTED = re.compile(
    r"^(_?[A-Z][A-Z_0-9]*)\s*[:=].*?(?:frozenset\(|\{)\s*\n"
    r"((?:\s+[a-z_]+\.[A-Z][A-Z_0-9]*,\n|\s+[A-Z][A-Z_0-9]*,\n)+)",
    re.MULTILINE,
)


def _hand_listed_sets() -> dict[str, str]:
    """Every hand-maintained code list in the product source, by name."""
    found: dict[str, str] = {}
    for path in pathlib.Path("src/khepri/rra").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for match in _HAND_LISTED.finditer(source):
            if len(match.group(2).strip().splitlines()) >= 3:
                found[match.group(1)] = str(path)
    return found


# --- no duplicate truth ----------------------------------------------------


def test_the_catalog_adds_no_hand_maintained_code_list() -> None:
    """`RRA-011`'s reduction requirement, counted rather than claimed.

    Two lists remain, both in `wording.py` and both pre-dating this catalog:
    `_RESULT_REASON_CODES` and `_GOVERNED_CAVEAT_CODES`. A third was
    `_FACT_METRIC_CODES`, which this program replaced with an import of
    `facts.GOVERNED_METRICS` — so the net effect is one fewer, which is the
    direction the specification requires.

    Pinned by name so that adding one fails here, and so that removing one of
    the two remaining is a deliberate edit to this test rather than a silent
    loosening.
    """
    assert set(_hand_listed_sets()) == {
        "_RESULT_REASON_CODES",
        "_GOVERNED_CAVEAT_CODES",
    }


def test_the_catalog_and_the_wording_guard_cannot_disagree_about_metrics() -> None:
    """One vocabulary, read twice, never restated.

    `wording._GOVERNED_METRIC_CODES` guards the business-name table and
    `definitions.METRIC_CODES` backs the catalog. If those were separately
    maintained, a metric could have a name and no definition, or the reverse.
    They are not: both are unions over the same governed exports.
    """
    assert facts.GOVERNED_METRICS <= wording._GOVERNED_METRIC_CODES
    assert facts.GOVERNED_METRICS <= definitions.METRIC_CODES
    assert set(growth.GOVERNED_METRICS) <= wording._GOVERNED_METRIC_CODES
    assert set(growth.GOVERNED_METRICS) <= definitions.METRIC_CODES


def test_every_catalogued_metric_is_declared_by_the_module_that_computes_it() -> None:
    """The catalog states no code of its own, asserted end to end.

    The expectation is built from the five governed exports rather than read
    back from the catalog, so a code the catalog invented would appear on one
    side only.
    """
    declared = (
        set(facts.GOVERNED_METRICS)
        | set(comparison.GOVERNED_METRICS)
        | set(growth.GOVERNED_METRICS)
        | set(basket.GOVERNED_METRICS)
        | set(concentration.GOVERNED_METRICS)
    )

    assert declared == set(definitions.METRIC_CODES)


# --- parity ----------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_catalogued_metric_has_vocabulary_in_every_language(
    language: str,
) -> None:
    """Arabic and English remain equal surfaces, over the catalog too."""
    for code in definitions.METRIC_CODES:
        assert definitions.describe_metric(code, language)
        assert definitions.not_meant(code, language)


def test_the_two_languages_describe_the_same_codes_differently() -> None:
    """Equal coverage is not the same as equal text.

    A table populated by copying English into the Arabic slot would pass a
    coverage check and fail a reader. Every description must differ between the
    languages, because none of these codes has an identical rendering in both.
    """
    for code in definitions.METRIC_CODES:
        assert definitions.describe_metric(code, "en") != definitions.describe_metric(
            code, "ar"
        )
        assert definitions.not_meant(code, "en") != definitions.not_meant(code, "ar")


# --- fail closed -----------------------------------------------------------


@pytest.mark.parametrize(
    "lookup",
    [
        pytest.param(lambda code: definitions.define_metric(code), id="define_metric"),
        pytest.param(
            lambda code: definitions.describe_metric(code, "en"), id="describe_metric"
        ),
        pytest.param(lambda code: definitions.not_meant(code, "en"), id="not_meant"),
    ],
)
def test_an_unknown_metric_refuses_at_every_entry_point(lookup) -> None:
    """One unrecognised code, every door, and none of them opens.

    Parametrized rather than written once because `RRA-011`'s fail-closed rule
    is about entry points: a lookup added later with no refusal would be a hole
    a single-function test could not see.
    """
    with pytest.raises(definitions.UnknownCode):
        lookup("revenues")


def test_an_unknown_population_refuses_and_a_family_member_does_not() -> None:
    """The two halves of the same rule, asserted together.

    Refusing everything unrecognised is easy; refusing everything unrecognised
    *while admitting a family member* is the property, and a guard that failed
    the second half would look correct against the first.
    """
    with pytest.raises(definitions.UnknownCode):
        definitions.define_population("sales_postd")

    concrete = populations.dimension_population("category")
    assert definitions.define_population(concrete).is_family


def test_the_quality_summary_states_no_score_on_any_surface() -> None:
    """`RRA-011` excludes a confidence, quality or completeness measure by name.

    Asserted over the rendered mapping rather than the dataclass, because a
    score could be added to what a surface emits without touching the type.
    """
    summary = definitions.summarize(rich_bundle())
    emitted = {
        "answered": summary.answered,
        "caveated": summary.caveated,
        "refused": summary.refused,
    }

    assert all(isinstance(value, int) for value in emitted.values())
    assert not {"score", "confidence", "completeness"} & set(emitted)
