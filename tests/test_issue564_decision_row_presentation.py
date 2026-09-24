"""#564 item 4 -- the decision surface prints no machine token (`RCA-008`).

Authority: active `RCA-008` `FR-162` (a card exposes its population), `FR-164`
(governed wording, never a bare code), `FR-167` (a breakdown figure is qualified by
its own projection's population), `RRA-014` `FR-140` (an absence stays an
absence, not an ordinary value), `RCA-010 FR-199` (`dir="auto"` on a
customer-controlled value) and Product principle 5 (machine vocabulary never
reaches a customer). The owner's `#564` decision (2026-09-24): "If the raw tokens
reach real runtime UI, fix them under the appropriate `RCA-008` authority."

**Driven over the real projector, not the stub.** `_StubDecisions` showed
`revenue  700.00  complete  ()`, which hid the real shape: over
`ReportBundle.of(package())` every row printed its metric code
(`revenue_by_store`) and the population absence as the text `None`, and every
card printed `None` for its population too.
"""

from __future__ import annotations

import re

import pytest

from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision import card
from khepri.rca.workspace.decision.breakdowns import BreakdownReading, BreakdownRow
from khepri.rca.workspace.decision.card import CardsReading, CardsRequest, MetricCard
from khepri.rca.workspace.decision.controls import ControlSelection
from khepri.rra import facts
from khepri.rra.bundle import ReportBundle
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.runtime import shell_decisions
from khepri.runtime.shell_api import shell_environment
from khepri.runtime.shell_controls import CONTROL_COPY
from tests.test_issue519_semantic_view_readers import (
    _Isolation,
    _ProjectingPort,
    _Sources,
)
from tests.test_rra006_bundle import package

_LANGUAGES = (LANGUAGE_ENGLISH, LANGUAGE_ARABIC)
_SELECTION = ControlSelection(source_id="run-1")


def _bundle() -> ReportBundle:
    return ReportBundle.of(package())


def _render(language: str) -> str:
    actions = SemanticQueryActions(_Isolation(), _Sources(), _ProjectingPort(_bundle()))
    readings = shell_decisions.read_surface(
        actions,
        CardsRequest(organization_id="org-1", account_id="acct-1", source_id="run-1"),
        selection=_SELECTION,
    )
    return shell_decisions.render_decisions(
        shell_environment(),
        readings,
        shell_decisions.DecisionFrame(
            language=language, prefix="/app", organization_id="org-1", source_id="run-1"
        ),
        shell_decisions.DecisionControls(selection=_SELECTION, sources=()),
    )


def _cells(markup: str) -> list[tuple[str, str]]:
    """`(name, text)` for every breakdown cell and every card population line."""
    cells = re.findall(r'data-cell="([^"]+)"[^>]*>([^<]*)<', markup)
    cells += [
        ("population", text)
        for text in re.findall(r'data-line="population">([^<]*)<', markup)
    ]
    return [(name, text.strip()) for name, text in cells]


#: Codes a customer must never read: every metric the bundle states and every
#: dimension the series views name. Derived from the source, never the render.
def _codes() -> frozenset[str]:
    return frozenset(
        {figure.metric for figure in _bundle().figures} | set(facts.SERIES_DIMENSIONS)
    )


@pytest.mark.parametrize("language", _LANGUAGES)
def test_no_cell_or_card_prints_a_code_or_a_python_none(language: str) -> None:
    codes = _codes()
    assert "revenue_by_store" in codes and "category" in codes
    cells = _cells(_render(language))
    assert len(cells) >= 8, "the real render produced too few cells to measure"

    leaked = [(name, text) for name, text in cells if text in codes or text == "None"]
    assert leaked == []


@pytest.mark.parametrize("language", _LANGUAGES)
def test_an_absent_population_is_named_as_not_stated(language: str) -> None:
    """`FR-140`: the absence survives as the governed "not stated", not as a blank."""
    not_stated = shell_decisions.DECISION_COPY[language]["not_stated"]
    populations = [text for name, text in _cells(_render(language)) if name == "population"]

    assert populations, "no population line rendered, so this proves nothing"
    assert set(populations) == {not_stated}


@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_dimension_is_named_in_the_page_language(language: str) -> None:
    dimensions = [text for name, text in _cells(_render(language)) if name == "dimension"]
    named = {
        CONTROL_COPY[language][dimension]
        for dimension in ("product", "category")
    }

    assert dimensions, "no dimension cell rendered, so this proves nothing"
    assert set(dimensions) <= named


@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_customer_named_member_carries_dir_auto(language: str) -> None:
    """`RCA-010 FR-199`: a branch or member name is customer-controlled."""
    markup = _render(language)
    tags = re.findall(r'<span class="decision-cell"[^>]*data-cell="(?:store|member)"[^>]*>', markup)

    assert tags, "no branch or member cell rendered, so this proves nothing"
    assert all('dir="auto"' in tag for tag in tags)


# --- Fail closed: a cell with no governed word is never withheld (review on #564) ---


def _row(**cells: object) -> BreakdownRow:
    return BreakdownRow(cells=tuple(cells.items()))


def _section_of(*rows: BreakdownRow, language: str = LANGUAGE_ENGLISH) -> object:
    reading = BreakdownReading(view_id="BranchPerformanceView", status="admitted", rows=rows)
    return shell_decisions._section("branches", reading, language, None)


@pytest.mark.parametrize(
    "cells",
    [
        {"store": "Cairo", "metric": "revenue_by_store", "value": 1, "population": "sales_posted"},
        {"dimension": "channel", "member": "Web", "metric": "revenue_by_store", "value": 1},
        {"store": "Cairo", "value": 1, "kind": "rows"},
    ],
    ids=["stated-population-code", "unmapped-dimension", "unknown-field"],
)
def test_an_unpresentable_cell_makes_its_section_unavailable_not_partial(
    cells: dict[str, object],
) -> None:
    """`RRA-014 FR-140`/`FR-141`, `RCA-008 FR-165`: no suppression, no code, no partial row."""
    section = _section_of(_row(**cells))

    assert section.unavailable is True
    assert section.rows == ()


def test_a_card_stating_a_population_code_makes_the_cards_unavailable() -> None:
    stated = MetricCard(
        metric="revenue",
        value="500.00",
        population="sales_posted",
        versions=(),
        status=card.STATUS_VERIFIED,
        availability=card.AVAILABILITY_AVAILABLE,
    )
    reading = CardsReading(status="admitted", cards=(stated,))
    view = shell_decisions.decision_view(reading, language=LANGUAGE_ENGLISH)

    assert view.unavailable is True
    assert view.cards == ()


@pytest.mark.parametrize("language", _LANGUAGES)
def test_a_rows_versions_are_stated_in_its_drawer_as_governed_pairs(language: str) -> None:
    versions = (("view", "sv1.basket.v1"), ("formula", "rra004.formula.v1"))
    section = _section_of(
        _row(metric="basket_attach_rate", value=1, population=None, versions=versions),
        language=language,
    )
    (row,) = section.rows

    assert row.versions == "view sv1.basket.v1, formula rra004.formula.v1"
    assert all(name != "versions" for name, _value in row.cells)
