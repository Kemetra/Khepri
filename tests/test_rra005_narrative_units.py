"""The commentary and the tables must state a figure in one unit.

**The defect.** `RRA-006`'s surfaces render a proportion as `55.89%`. The
narrator quoted the package's own `0.5589`, and both reached the same document
-- `html._passages` renders the prose above the figure tables -- so one report
said "The recorded gross margin is 0.5589" in its commentary and `55.89%` in the
table below it. Two correct numbers, two units, one page.

**Why quoting the percentage is not a calculation.** `narrative._stated`
attaches `value_percent` to every ratio fact for exactly this purpose: "a
narrative that says `66.67%` is quoting a supplied value, not performing a
calculation." The narrator selects between two supplied strings and converts
nothing.

**Why the unit alone cannot choose.** `basket._fact` stamps `UNIT_RATIO` on a
rate as well as a proportion, so `value_percent` is computed for
`basket_items_per_transaction` too -- and quoting it would say a basket holds
`382500.0000%` items. That is the defect `bundle.PERCENTAGE_METRICS` was
introduced to stop on the surfaces, and it is the same defect here.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.bundle import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    PERCENTAGE_METRICS,
    RATE_METRICS,
    ReportBundle,
)
from khepri.rra.deterministic_narrative import (
    ADAPTER_VERSION,
    DeterministicNarrator,
    _fact_figure,
)
from khepri.rra.facts import AdmittedInput, FactPackage, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.narrative import NarrativeRequest, validate
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import TEST_CONTRACT

#: Carries `cogs`, so the package produces the `gross_margin` ratio the bare
#: fixtures elsewhere have no way to reach.
CONTENT = (
    b"date,revenue,units,invoice_no,category,branch,cogs\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo,60.00\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza,41.00\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo,98.50\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza,30.75\n"
)


def package() -> FactPackage:
    profile = build_profile(
        content=CONTENT,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(CONTENT).hexdigest(),
    )
    mapping = build_mapping(profile, contract=TEST_CONTRACT)
    return build_fact_package(
               AdmittedInput(
                   content=CONTENT,
                   media_type=CSV_MEDIA_TYPE,
                   profile=profile,
                   mapping=mapping,
                   decision=assess_admissibility(profile, mapping),
                   contract=TEST_CONTRACT,
               ),
           )


def drafted():
    request = NarrativeRequest.of(package(), adapter_version=ADAPTER_VERSION)
    draft = DeterministicNarrator().draft(
        request.for_provider(),
        timeout_seconds=Decimal("30"),
    )
    return request, draft


def prose(draft, language: str) -> str:
    entry = next(item for item in draft.languages if item.language == language)
    return "\n".join(section.text for section in entry.sections)


def ratio_facts() -> tuple[dict, ...]:
    """The request's proportion facts, so no assertion below can pass vacuously."""
    request = NarrativeRequest.of(package(), adapter_version=ADAPTER_VERSION)
    return tuple(
        entry
        for entry in request.for_provider().document.get("facts", [])
        if entry.get("metric") in PERCENTAGE_METRICS
    )


class TestAProportionIsQuotedInTheUnitTheTablesState:
    def test_the_fixture_produces_a_proportion_to_argue_about(self) -> None:
        # Without this the three tests below would agree about nothing.
        assert ratio_facts(), "fixture carries no proportion fact"

    def test_the_commentary_and_the_table_state_one_unit(self) -> None:
        # The defect itself, checked across the two artifacts that disagreed.
        bundle = ReportBundle.of(package())
        _, draft = drafted()
        text = prose(draft, LANGUAGE_ENGLISH)

        for entry in ratio_facts():
            figure = next(
                item for item in bundle.figures if item.metric == entry["metric"]
            )
            rendered = figure.renderings[LANGUAGE_ENGLISH]
            assert rendered.endswith("%"), rendered
            quoted = f"{entry['value_percent']}%"
            assert quoted in text, (quoted, text)
            assert Decimal(quoted.rstrip("%")) == Decimal(rendered.rstrip("%"))

    def test_the_bare_ratio_is_no_longer_stated(self) -> None:
        # The old sentence, gone rather than merely joined by a new one.
        _, draft = drafted()
        text = prose(draft, LANGUAGE_ENGLISH)

        for entry in ratio_facts():
            assert f"is {entry['value']}." not in text, entry["value"]

    def test_both_languages_quote_the_same_percentage(self) -> None:
        # `validate` compares stated figures across languages; this states the
        # same property directly, so a divergence is named rather than inferred.
        _, draft = drafted()

        for entry in ratio_facts():
            quoted = f"{entry['value_percent']}%"
            assert quoted in prose(draft, LANGUAGE_ENGLISH)
            assert quoted in prose(draft, LANGUAGE_ARABIC)


class TestTheRealValidatorStillAcceptsIt:
    def test_a_percentage_claim_survives_validation(self) -> None:
        # `_assert_grounded_numbers` grounds a `%`-suffixed figure against the
        # request's `percents`, not its `numbers`. Quoting the ratio's digits
        # with a percent sign attached would be refused, which is the point.
        request, draft = drafted()

        validate(draft, request=request)


class TestARateIsNotAPercentage:
    """The classification, exercised over the sets themselves.

    `basket_items_per_transaction` reaches no narrative today -- `_plan` reads
    `facts`, `series` and `comparisons`, and the `RRA-008` families are none of
    those. Asserting over `RATE_METRICS` rather than over one name means the
    guard holds for whatever joins the set, and the day a family becomes a fact
    it is already covered.
    """

    def _entry(self, metric: str) -> dict:
        # Shaped as `narrative._stated` leaves a ratio fact: both renderings
        # present, because the request computes the percentage for every
        # ratio-kind fact whether or not the metric is a proportion.
        return {
            "metric": metric,
            "unit_kind": "ratio",
            "value": "3825.0000",
            "value_percent": "382500.0000",
        }

    def test_the_sets_are_populated(self) -> None:
        assert RATE_METRICS and PERCENTAGE_METRICS

    def test_a_rate_is_quoted_as_the_rate_it_is(self) -> None:
        for metric in RATE_METRICS:
            assert _fact_figure(self._entry(metric)) == "3825.0000"

    def test_a_proportion_is_quoted_as_a_percentage(self) -> None:
        for metric in PERCENTAGE_METRICS:
            assert _fact_figure(self._entry(metric)) == "382500.0000%"

    def test_an_unclassified_ratio_keeps_its_supplied_value(self) -> None:
        # Neither set names it, so nothing here knows it is a proportion. The
        # bare value is the honest answer; inventing a unit is not.
        assert _fact_figure(self._entry("some_unclassified_ratio")) == "3825.0000"

    def test_a_proportion_with_no_supplied_percentage_falls_back(self) -> None:
        # `_stated` skips `value_percent` when the value will not parse. The
        # narrator must not synthesize one to fill the gap.
        entry = {"metric": next(iter(PERCENTAGE_METRICS)), "value": "0.5589"}

        assert _fact_figure(entry) == "0.5589"
