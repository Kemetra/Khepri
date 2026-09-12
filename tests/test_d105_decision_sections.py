"""`D1-05` -- the four breakdown surfaces the evidence drawer hangs from.

Authority: active `RCA-008` `FR-161`, `FR-163`, `FR-164`, `FR-165`, `FR-167`,
`FR-168`, `FR-171`.

`D1-04` shipped `breakdowns.py`, `limits.py` and the decision route and rendered
none of them: the template carried S-1's cards and nothing else. So its own
acceptance criterion -- "the two governed empty rules render differently **on
the same surface**" -- was asserted on a `BreakdownReading` and reached no
reader, and `D1-05`'s acceptance, that the drawer is reachable from every figure
on S-1, S-3, S-4 and S-5, named three surfaces that did not exist.

**Everything here is asserted against a rendered page**, and that is the point
of the file. Each of these can still fail with a green read model: two empty
rules collapsing into one sentence, a row losing its drawer, a breakdown figure
acquiring a four-state availability it may not have (`FR-167`), S-5's two reads
failing together, or a view being read once per figure instead of once per page.

The read model, the card's evidence action and the drawer itself are
`test_d105_evidence_drawer.py`. Splitting them is CodeScene's finding acted on
rather than argued with: what a read model selects and what a page renders are
different subjects with different failure modes.
"""

from __future__ import annotations

import re

import pytest

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import card, seam
from khepri.rra import definitions as catalog
from khepri.rra.semantic_views import registry
from khepri.runtime import shell_decisions
from tests import d105_support as support

#: Every section this surface renders, and the empty rule each one's view states.
_SECTIONS = (
    (shell_decisions.SECTION_BRANCHES, seam.BRANCH_PERFORMANCE),
    (shell_decisions.SECTION_PRODUCTS, seam.PRODUCT_CATEGORY),
    (shell_decisions.SECTION_BASKET, seam.BASKET),
    (shell_decisions.SECTION_CONCENTRATION, seam.CONCENTRATION),
)

support.UNAVAILABLE = ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE)


def _full_surface() -> dict[str, ports.ViewOutcome]:
    """Every view this surface reads, each admitted with figures on it."""
    return {
        seam.EXECUTIVE_OVERVIEW.view_id: support.overview(),
        seam.METRIC_AVAILABILITY.view_id: support.availability(
            (("revenue", card.AVAILABILITY_AVAILABLE, None, ()),)
        ),
        seam.REPORT_EVIDENCE.view_id: support.evidence_outcome(
            (support.STATED, support.UNSTATED), support.UNSTATED_ABSENCES
        ),
        seam.BRANCH_PERFORMANCE.view_id: support.breakdown(
            seam.BRANCH_PERFORMANCE,
            support.BRANCH_FIELDS,
            (("store-a", "revenue_by_store", "700.00", "complete"),),
        ),
        seam.PRODUCT_CATEGORY.view_id: support.breakdown(
            seam.PRODUCT_CATEGORY,
            support.PRODUCT_FIELDS,
            (("category", "drinks", "revenue_by_category", "120.00", "complete"),),
        ),
        seam.BASKET.view_id: support.breakdown(
            seam.BASKET,
            support.BASKET_FIELDS,
            (("basket_attach_rate", "0.25", "complete", ()),),
        ),
        seam.CONCENTRATION.view_id: support.breakdown(
            seam.CONCENTRATION,
            support.CONCENTRATION_FIELDS,
            (("product", "concentration_top_decile_share", "0.60", "complete"),),
        ),
    }


class _SurfaceDecisions:
    """Every view scripted independently, recording what the surface asked for."""

    def __init__(self, outcomes: dict[str, ports.ViewOutcome]) -> None:
        """Hold the scripted answers, and the log the isolation cases read back."""
        self.outcomes = outcomes
        self.asked: list[str] = []

    def request(self, asked: object) -> ports.ViewOutcome:
        """Answer as scripted; a view with no script is content-free unavailable."""
        view_id = asked.view.view_id  # type: ignore[attr-defined]
        self.asked.append(view_id)
        return self.outcomes.get(view_id, support.UNAVAILABLE)


def _surface(outcomes: dict[str, ports.ViewOutcome]) -> _SurfaceDecisions:
    """A decision collaborator scripted for one page."""
    return _SurfaceDecisions(outcomes)


def _rendered(decisions: _SurfaceDecisions, language: str = "en") -> str:
    """That page, rendered through the route in one language."""
    return support.client(decisions).get(support.address(language)).text


@pytest.mark.parametrize("section,view", _SECTIONS)
def test_the_surface_renders_a_section_for_every_governed_breakdown(
    section: str, view: seam.ViewIdentity
) -> None:
    """`D1-04`'s read models reach a reader at last: S-3, S-4, S-5a and S-5b."""
    body = _rendered(_surface(_full_surface()))
    assert shell_decisions.SECTION_COPY["en"][section] in body
    assert f'data-section="{section}"' in body


def test_the_governed_availability_is_reachable_beside_the_figure_it_qualifies() -> None:
    """S-6 under `FR-161`, which is why it is not a section of its own.

    "Availability, caveats and refusals are reachable from the surface carrying
    the figure they qualify and are **not deferred to a terminal page**." So S-6
    renders *distributed*: the four-state sits in the card's own row, and each
    section states its own caveats and refusal. A consolidated limits section
    would be a second read of `MetricAvailabilityView` on a page whose cards
    already carry it -- the duplication `FR-168` and `FR-135` both bar.
    """
    body = _rendered(_surface(_full_surface()))
    cards = re.findall(r'<li class="decision-card".*?</li>', body, flags=re.S)
    qualified = [one for one in cards if card.AVAILABILITY_AVAILABLE in one]
    assert qualified, "no card carried the governed availability beside its figure"


def test_the_availability_view_is_read_once_for_the_whole_surface() -> None:
    """`FR-168`/`FR-135` -- one read of S-6, however many figures it qualifies."""
    decisions = _surface(_full_surface())
    _rendered(decisions)
    assert decisions.asked.count(seam.METRIC_AVAILABILITY.view_id) == 1


def test_the_two_governed_empty_rules_render_distinguishably_on_one_page() -> None:
    """`FR-163`, and `D1-04`'s own acceptance criterion driven through a page.

    A store filter naming a store with no sales is `stated_no_rows` and is not a
    refused measure; a source that published no basket value states absence. A
    surface rendering both as an empty table would misstate the customer's data.
    """
    outcomes = _full_surface()
    outcomes[seam.BRANCH_PERFORMANCE.view_id] = support.breakdown(
        seam.BRANCH_PERFORMANCE, support.BRANCH_FIELDS, (), is_empty=True
    )
    outcomes[seam.BASKET.view_id] = support.breakdown(
        seam.BASKET, support.BASKET_FIELDS, (), is_empty=True
    )
    body = _rendered(_surface(outcomes))
    no_rows = shell_decisions.EMPTY_WORDING["en"][seam.EMPTY_STATED_NO_ROWS]
    absence = shell_decisions.EMPTY_WORDING["en"][seam.EMPTY_STATED_ABSENCE]
    assert no_rows != absence
    assert no_rows in body
    assert absence in body


def test_every_breakdown_figure_can_reach_its_own_drawer() -> None:
    """`FR-161` -- reachable from the surface carrying the figure, on all four."""
    body = _rendered(_surface(_full_surface()))
    # Two cards on S-1 and one row in each of the four breakdowns.
    assert body.count('class="decision-drawer"') == 6


def test_a_breakdown_row_carries_no_four_state_availability() -> None:
    """`FR-167`, negatively -- and no surface may synthesize one either."""
    body = _rendered(_surface(_full_surface()))
    rows = re.findall(r'<li class="decision-row".*?</li>', body, flags=re.S)
    assert rows
    assert not [row for row in rows if "decision-availability" in row]


def test_the_basket_surface_renders_the_half_that_answered() -> None:
    """`FR-165` -- one surface, two reads, and neither ordering privileged."""
    outcomes = _full_surface()
    outcomes.pop(seam.CONCENTRATION.view_id)
    body = _rendered(_surface(outcomes))
    assert "0.25" in body
    assert shell_decisions.DECISION_COPY["en"]["unavailable"] in body


def test_a_refused_breakdown_shows_the_governed_wording_and_no_figure() -> None:
    """`FR-164` -- `RRA-014`'s own bilingual wording, never an invented sentence."""
    outcomes = _full_surface()
    outcomes[seam.PRODUCT_CATEGORY.view_id] = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(
            cause="view_unsupported_filter",
            wording_pairs=(("en", "That filter is not supported."), ("ar", "غير مدعوم.")),
        ),
    )
    body = _rendered(_surface(outcomes))
    assert "That filter is not supported." in body
    assert "drinks" not in body


def test_a_drawer_with_no_evidence_read_behind_it_says_unavailable_not_absent() -> None:
    """`FR-165` -- and the difference between "none was cited" and "we did not look".

    `read_cards` returns before reading S-9 when S-1 is refused, so a page can
    carry breakdown figures with no evidence reading behind them at all. A drawer
    that then claimed the analysis cited no evidence would be asserting something
    the page never checked; the content-free unavailable is the true answer.
    """
    outcomes = _full_surface()
    outcomes[seam.EXECUTIVE_OVERVIEW.view_id] = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(
            cause="view_incompatible_source_shape",
            wording_pairs=(("en", "That source is the wrong shape."), ("ar", "شكل غير صالح.")),
        ),
    )
    decisions = _surface(outcomes)
    body = _rendered(decisions)
    assert decisions.asked.count(seam.REPORT_EVIDENCE.view_id) == 0
    assert shell_decisions.DECISION_COPY["en"]["evidence_unavailable"] in body
    assert shell_decisions.DECISION_COPY["en"]["evidence_absent"] not in body


def test_the_evidence_view_is_read_once_for_the_whole_surface() -> None:
    """`FR-168` -- no cache, and one read rather than one per figure."""
    decisions = _surface(_full_surface())
    _rendered(decisions)
    assert decisions.asked.count(seam.REPORT_EVIDENCE.view_id) == 1


@pytest.mark.parametrize("language", support.LANGUAGES)
def test_the_sections_state_the_same_thing_in_both_languages(language: str) -> None:
    """`FR-171` -- same sections, same rows, same drawers in both."""
    body = _rendered(_surface(_full_surface()), language)
    assert body.count('class="decision-drawer"') == 6
    assert body.count('class="decision-row"') == 4
    for section, _view in _SECTIONS:
        assert shell_decisions.SECTION_COPY[language][section] in body


def test_every_section_heading_exists_in_both_governed_languages() -> None:
    """`FR-171` -- a heading present in one language and absent in the other is a gap."""
    assert set(shell_decisions.SECTION_COPY["en"]) == set(
        shell_decisions.SECTION_COPY["ar"]
    )
    assert set(shell_decisions.EMPTY_WORDING["en"]) == set(
        shell_decisions.EMPTY_WORDING["ar"]
    )


def test_every_breakdown_metric_is_one_the_catalog_can_define() -> None:
    """The drawer reads `RRA-011` for every figure, so every figure must be in it.

    `describe_metric` raises `UnknownCode` rather than falling back, and a raw
    code is never a fallback either -- so a view publishing a metric the catalog
    does not admit would reach a customer as a 500 rather than as a surface. The
    contract already holds; this is the check that keeps it holding, in the same
    spirit as pinning a literal and asserting it against its source.
    """
    for _section, view in _SECTIONS:
        published = registry.define_view(view.view_id)
        for metric in published.metric_allowlist:
            assert catalog.admits_metric(metric), (
                f"{view.view_id} publishes {metric!r}, which `RRA-011` cannot define"
            )
            assert catalog.describe_metric(metric, "en")
            assert catalog.describe_metric(metric, "ar")


def test_the_empty_wording_covers_exactly_the_two_governed_rules() -> None:
    """`FR-163` -- two rules, two sentences, and no third invented here."""
    governed = {seam.EMPTY_STATED_NO_ROWS, seam.EMPTY_STATED_ABSENCE}
    assert set(shell_decisions.EMPTY_WORDING["en"]) == governed
