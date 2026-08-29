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

import dataclasses
import importlib
import pathlib
import re

import pytest

from khepri.rra import definitions, facts, populations
from khepri.rra.analysis import basket, comparison, concentration, growth
from khepri.rra.bundle import ReportBundle
from khepri.rra.rendering import wording
from tests.test_rra006_html_sections import ROWS, package_for

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
    # A series metric is composed, not declared: `facts.py` builds
    # `<measure>_by_<dimension>` from two governed constants, so the expectation is
    # composed here the same way rather than listed. Both operands are read from
    # `facts`, so a code the catalog invented still appears on one side only.
    #
    # The measure axis is `SERIES_MEASURES`, the tuple the `aggregated` builder is
    # asserted against, not `GOVERNED_METRICS`: the eight core metrics that are not
    # aggregated over a dimension have no series form to catalogue.
    composed = {
        f"{measure}_by_{dimension}"
        for measure in facts.SERIES_MEASURES
        for dimension in facts.SERIES_DIMENSIONS
    }

    assert declared | composed == set(definitions.METRIC_CODES)


# --- parity ----------------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_catalogued_metric_has_vocabulary_in_every_language(
    language: str,
) -> None:
    """Arabic and English remain equal surfaces, over the catalog too."""
    for code in definitions.METRIC_CODES:
        assert definitions.describe_metric(code, language)
        assert definitions.not_meant(code, language)
        assert definitions.synonyms(code, language)


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
        assert definitions.synonyms(code, "en") != definitions.synonyms(code, "ar")


# --- fail closed -----------------------------------------------------------


@pytest.mark.parametrize(
    "lookup",
    [
        pytest.param(lambda code: definitions.define_metric(code), id="define_metric"),
        pytest.param(
            lambda code: definitions.describe_metric(code, "en"), id="describe_metric"
        ),
        pytest.param(lambda code: definitions.not_meant(code, "en"), id="not_meant"),
        pytest.param(lambda code: definitions.synonyms(code, "en"), id="synonyms"),
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


def test_the_quality_summary_states_no_score() -> None:
    """`RRA-011` excludes a confidence, quality or completeness measure by name.

    Read from the dataclass rather than from a dict this test builds. An earlier
    form assembled three hardcoded keys and then asserted those keys were not
    forbidden ones, which could not fail: it compared a literal against itself
    and would have passed with a `score` field sitting beside it.
    """
    fields = {field.name for field in dataclasses.fields(definitions.AnalysisQualitySummary)}
    forbidden = {"score", "confidence", "quality", "completeness", "percentage", "ratio"}

    assert not (fields & forbidden)
    assert {"answered", "caveated", "refused", "refused_results"} <= fields


def test_a_refused_result_is_reported_even_when_its_section_answered() -> None:
    """A partial refusal is a refusal, and the summary must say so.

    `RRA-008` refuses a *result* rather than a family where it can: comparison
    publishes `revenue_delta_absolute` and refuses `revenue_delta_percent` when the
    prior window is absent. `bundle._scoped` carries that as a caveat coded
    `<result>:<reason>` on a section that states something and therefore has no
    reason of its own.

    Classifying whole sections alone reported `refused == 0` and `refusals == ()`
    for exactly that package -- a consumer was told nothing had been refused while
    two results had been. The information was never lost, it sat in `caveats`; the
    summary's own fields disagreed with it.

    Driven from the shared published fixture rather than a hand-built bundle,
    because the subject is the code shape `_scoped` writes: a stand-in asserting
    `<result>:<reason>` would keep passing if that convention moved.
    """
    summary = definitions.summarize(
        ReportBundle.of(package_for(ROWS, published=True))
    )

    assert summary.refused == 0, "no analysis refused outright; only two results did"
    assert dict(summary.refused_results) == {
        "revenue_delta_absolute.year_over_year": "prior_window_absent",
        "revenue_delta_percent.year_over_year": "prior_window_absent",
    }


def test_a_refused_result_and_a_refused_section_are_told_apart() -> None:
    """Both kinds are counted, and each names what it refused.

    Counting them together without distinguishing them would be the same defect
    inverted: a reader learns two things were refused and cannot tell whether an
    analysis was unavailable or one figure inside it was. The section case keys on
    the section id, the result case on the result's own mode-qualified metric, and
    no governed reason or caveat code contains a colon -- so the two never collide.
    """
    refused_family = definitions.summarize(
        ReportBundle.of(package_for(ROWS, published=False))
    )

    # Under the predecessor pin every family sits unadmitted, so all four sections
    # refuse outright and no result-level refusal is recorded.
    assert refused_family.refused == 4
    assert all(
        reason == "family_version_pairing_unadmitted"
        for _, reason in refused_family.refusals
    )
    assert not refused_family.refused_results
    assert not any(":" in key for key, _ in refused_family.refusals)


def test_a_refused_result_is_not_also_counted_as_a_caveat() -> None:
    """`refusals` and `caveats` partition one channel; they do not overlap.

    `bundle.caveats` carries both qualifications and scoped result refusals, so a
    summary reading it twice without partitioning reports the same refused result
    under both fields -- and a surface rendering both shows the reader one refusal
    twice, once as a reason and once as a caveat about the figure it refused.

    Asserted as a disjointness over the codes rather than as a count, because a
    count agrees by coincidence whenever the two totals happen to match.
    """
    summary = definitions.summarize(
        ReportBundle.of(package_for(ROWS, published=True))
    )

    assert summary.caveats, "fixture states no caveat; the case would be vacuous"
    assert summary.refused_results, "fixture refuses no result; case would be vacuous"
    assert not set(summary.caveats) & {r for r, _ in summary.refused_results}
    assert not any(":" in code for code in summary.caveats)


def test_a_synonym_never_introduces_a_code() -> None:
    """`RRA-011`'s bound on authored wording, stated over the table itself.

    Vocabulary attaches only to a code some other module already governs. A
    synonym keyed to a code the governed sets do not contain would be this
    specification admitting one through the wording layer, which is exactly the
    hole the single-truth test closes -- and the guard would not see it, because
    the guard checks that every *catalogued* code has an entry, not that every
    entry has a catalogued code.
    """
    for language in LANGUAGES:
        keyed = set(wording.METRIC_SYNONYMS[language])

        # The authored tables key the base metrics. A series metric offers its
        # measure's synonyms rather than its own entry, so the table is a subset of
        # the catalog by design -- but nothing in it may be outside the catalog,
        # which is the direction this rule is about.
        assert keyed <= set(definitions.METRIC_CODES), language
        assert keyed == set(facts.GOVERNED_METRICS) | {
            code
            for codes in (
                comparison.GOVERNED_METRICS,
                growth.GOVERNED_METRICS,
                basket.GOVERNED_METRICS,
                concentration.GOVERNED_METRICS,
            )
            for code in codes
        }, language


def test_a_synonym_is_never_the_business_name_it_stands_beside() -> None:
    """A synonym is an alternative, not a restatement.

    Offering a reader the name they are already looking at is noise, and it is the
    shape a table gets when it is filled by copying the name column. Compared
    case-insensitively so a differently-capitalized copy is caught too.
    """
    for language in LANGUAGES:
        for code in definitions.METRIC_CODES:
            name = wording.business_metric_name(code, language)
            if name is None:
                continue
            offered = {synonym.casefold() for synonym in definitions.synonyms(code, language)}

            assert name.casefold() not in offered, f"{language}/{code}"


def test_the_vocabulary_guard_covers_every_authored_table() -> None:
    """The guard's scope is asserted, because the guard cannot assert its own.

    `_assert_vocabulary_complete` iterates `_VOCABULARY_TABLES`, a tuple naming
    the tables it checks. Removing an entry from that tuple removes the table from
    the guard and breaks nothing: every case above still passes, because they read
    the tables directly and the guard simply stops looking. A fourth table authored
    later and not added to the tuple is the same hole on the first day it exists.

    So this compares the guard's scope against every module-level table keyed by
    language and metric code -- discovered, not listed -- which is the one form
    that cannot be satisfied by editing this test's own expectation.
    """
    authored = {
        name
        for name, value in vars(wording).items()
        if name.startswith("METRIC_")
        and isinstance(value, dict)
        and set(value) == {"en", "ar"}
        and set(value["en"]) == set(wording._CATALOGUED_METRIC_CODES)
    }
    guarded = {
        name
        for name, value in vars(wording).items()
        if name.startswith("METRIC_")
        and any(value is table for _, table in wording._VOCABULARY_TABLES)
    }

    assert authored, "no vocabulary table discovered; the case would be vacuous"
    assert authored == guarded, f"unguarded vocabulary tables: {authored - guarded}"


def test_exactly_one_catalogued_metric_has_no_business_name() -> None:
    """The asymmetry is pinned rather than tolerated, and it is deliberate.

    `concentration_curve` names the retained series a chart reads. `RRA-008` keeps
    it label-free on purpose: a business name would title something no reader meets
    as a figure. So it carries a description, an unsupported reading and synonyms
    -- a reader asking what it means gets an answer -- and no name.

    Stated as an equality over the whole catalog because a surface offering a name
    field has to decide what to do when there is none. A review round found a
    withdrawn route publishing `name: None` beside real names; the route is gone
    and the asymmetry that made it possible is not, so it is written down here for
    whichever surface serves the catalog next.
    """
    # Over the authored base metrics. A series metric's name is governed by the
    # same table, and every composed code has a producing builder now that the
    # cross-product reads `SERIES_MEASURES`.
    #
    # `all` rather than a second loop clause: a comprehension that adds the code
    # when *either* language returns `None` passes while a name exists in one
    # language and not the other, which is the half-authored table this is meant
    # to catch. Absence has to hold in both to be absence.
    unnamed = {
        code
        for code in wording._CATALOGUED_METRIC_CODES
        if all(
            wording.business_metric_name(code, language) is None
            for language in LANGUAGES
        )
    }

    assert unnamed == {"concentration_curve"}
    assert definitions.describe_metric("concentration_curve", "en")
    assert definitions.synonyms("concentration_curve", "ar")


def test_answered_and_refused_always_partition_the_sections() -> None:
    """The invariant that keeps `refused` a section count, over both fixtures.

    An earlier form of `summarize` added result refusals into `refused`, which
    broke this without breaking any case that read the field alone: the number
    grew, stayed plausible, and no longer meant what its name said. A surface
    showing "N of M analyses" would have shown more than M.

    Both pins are exercised, because one refuses whole families and the other
    refuses results inside surviving ones -- and this must hold under each.
    """
    for published in (True, False):
        bundle = ReportBundle.of(package_for(ROWS, published=published))
        summary = definitions.summarize(bundle)

        assert summary.answered + summary.refused == len(bundle.sections), published


# --- reasons and caveats ---------------------------------------------------


def test_the_reason_and_caveat_registries_derive_from_the_wording_tables() -> None:
    """No third and fourth hand-maintained list, asserted rather than intended.

    `RRA-009`'s two registries already declare which reasons and caveats exist,
    and both already carry bilingual prose. The catalog exposes them; it does not
    restate them. Compared against the tables directly so a catalog that grew its
    own copy would disagree here on the day the copy drifted.
    """
    stated_caveats = frozenset(wording.CAVEAT_WORDING["en"])
    stated_reasons = frozenset(
        code
        for scope in wording.GOVERNED_REASON_SCOPES
        for code in wording.REFUSAL_WORDING[scope]["en"]
    )

    assert stated_caveats == definitions.CAVEAT_CODES
    assert stated_reasons == definitions.REASON_CODES


def test_a_reason_reports_every_scope_it_is_stated_at() -> None:
    """Scope is part of the answer, and a reason may be governed at both.

    `RRA-009` words a section refusal and a result refusal differently -- one says
    an analysis is unavailable, the other that one figure inside a surviving
    analysis is -- so a reader asking about a code needs to know which applies.

    Both directions are pinned: a code stated at one scope reports one, and a code
    stated at both reports both in the governed order. Asserting only the second
    would pass for an implementation that returned every scope unconditionally.
    """
    both = definitions.define_reason("family_version_pairing_unadmitted")
    assert both.scopes == ("section", "result")

    for code in definitions.REASON_CODES:
        for scope in definitions.define_reason(code).scopes:
            assert code in wording.reason_codes(scope), (code, scope)


def _reason_scopes() -> list[tuple[str, str]]:
    """Every `(reason, scope)` pair the catalog states a reason at.

    Flattened out of the test so the assertion loops stay one level deep: the
    reason-by-scope fan-out is data, not control flow, and building it here keeps
    the parity check a flat walk over pairs.
    """
    return [
        (code, scope)
        for code in definitions.REASON_CODES
        for scope in definitions.define_reason(code).scopes
    ]


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_reason_or_caveat_explains_itself_in_both_languages(language: str) -> None:
    """Parity over the two registries the catalog exposes, not only over metrics."""
    for code in definitions.CAVEAT_CODES:
        assert definitions.explain_caveat(code, language), code
    for code, scope in _reason_scopes():
        assert definitions.explain_reason(code, language, scope), (code, scope)


def test_an_unknown_reason_or_caveat_refuses() -> None:
    """Fail-closed, at the two entry points this slice added.

    `RRA-011` states the rule about entry points rather than about functions, so
    a lookup added later with no refusal is the hole -- and these are the ones
    added later.
    """
    with pytest.raises(definitions.UnknownCode):
        definitions.define_reason("zero_denominatr")
    with pytest.raises(definitions.UnknownCode):
        definitions.define_caveat("currency_not_declard")
    with pytest.raises(definitions.UnknownCode):
        definitions.explain_reason("zero_denominator", "en", "section")
    # An unrecognized *scope* is the third way in, and it escaped as `KeyError`
    # until this was written: a caller catching the catalog's own refusal saw an
    # unhandled exception from one entry point and a governed refusal everywhere
    # else. `RRA-011` states fail-closed about entry points, not about codes.
    with pytest.raises(definitions.UnknownCode):
        definitions.explain_reason("zero_denominator", "en", "footnote")


def test_a_reason_refuses_at_a_scope_it_is_not_stated_at() -> None:
    """Scope is checked, not decoration.

    `zero_denominator` is a result refusal and `RRA-009` states no section wording
    for it. Returning the result sentence for a section query would put "the other
    figures in this section are unaffected" under a heading where every figure was
    withheld. Asserted over every single-scope reason, so this holds for the set
    rather than for the one code that prompted it.
    """
    for code in definitions.REASON_CODES:
        scopes = definitions.define_reason(code).scopes
        if len(scopes) != 1:
            continue
        absent = next(
            s for s in wording.GOVERNED_REASON_SCOPES if s != scopes[0]
        )
        with pytest.raises(definitions.UnknownCode):
            definitions.explain_reason(code, "en", absent)


def test_a_refusal_sentence_keeps_the_placeholder_it_was_authored_with() -> None:
    """The catalog hands back `RRA-009`'s sentence, it does not fill it in.

    A result refusal names the metric it withheld -- `{metric} is not shown` --
    and only a surface rendering one knows which. Substituting the code would put
    a raw identifier into a customer's sentence, which the wording layer refuses
    everywhere else; substituting nothing would state a sentence about no metric.
    So the placeholder survives, and this says so rather than leaving a caller to
    discover it.
    """
    sentence = definitions.explain_reason("zero_denominator", "en", "result")

    assert "{metric}" in sentence


def test_every_metric_on_a_published_figure_has_a_definition() -> None:
    """The gap this closed, asserted against what a reader actually sees.

    `revenue_by_period` and `units_by_product` sit on published figures, and
    `describe_metric` raised `UnknownCode` for them: a reader looking at one of
    those charts could not ask what it meant. The catalog's whole outcome clause
    is that every code the calculation *already emits* has a definition, so the
    check that matters is driven from a rendered bundle rather than from a list.

    Both pins, because they publish different families, and the series metrics
    appear under each.
    """
    seen: set[str] = set()
    for published in (True, False):
        bundle = ReportBundle.of(package_for(ROWS, published=published))
        for figure in bundle.figures:
            seen.add(figure.metric)
            for language in LANGUAGES:
                assert definitions.describe_metric(figure.metric, language)

    assert {"revenue_by_period", "units_by_product"} <= seen, seen


def test_a_series_metric_says_what_it_is_broken_down_by() -> None:
    """Composed vocabulary, and the composition is visible in the answer.

    A series description that returned only its measure's sentence would pass a
    "has a definition" check while telling a reader nothing about the dimension --
    which is the only thing distinguishing `revenue_by_product` from `revenue`.
    """
    base = definitions.describe_metric("revenue", "en")
    series = definitions.describe_metric("revenue_by_product", "en")

    assert series.startswith(base)
    assert series != base
    assert "product" in series

    # And the same holds in Arabic, which orders the two parts differently.
    arabic = definitions.describe_metric("revenue_by_product", "ar")
    assert arabic != definitions.describe_metric("revenue", "ar")
    assert "منتج" in arabic


def test_a_dimension_admitted_without_a_name_refuses_at_import(monkeypatch) -> None:
    """The dimension table's guard, mutated outside the scope it names.

    Deleting an entry proves the guard notices a table that shrank. The failure
    that matters is the reverse: a dimension added to `facts.SERIES_DIMENSIONS`
    with no name here composes a description with a `KeyError` in it, and a guard
    reading its own keys would never see it.
    """
    monkeypatch.setattr(
        facts, "SERIES_DIMENSIONS", (*facts.SERIES_DIMENSIONS, "supplier")
    )
    try:
        with pytest.raises(RuntimeError, match="dimension"):
            importlib.reload(wording)
    finally:
        monkeypatch.undo()
        importlib.reload(wording)
