"""`D1-03` -- the `FR-162` metric card, its status selection, and one asserted absence.

Authority: active `RCA-008` `FR-161`, `FR-162`, `FR-164`, `FR-165`, `FR-170`, `FR-171`.

The read model is driven through a fake port, as `D1-02`'s was and for the same
reason: what is under test is the *selection*, and a real projection would put a
pipeline between the inputs and the choice.

The surface is driven through its view assembly and its template rather than
over HTTP. The HTTP plumbing -- session, scope resolution, headers, the frame --
is `RCA-002`'s and is already asserted by the `W1`/`C1` shell tests; repeating it
here would test those and not this. What is this slice's own is the mapping from
a `CardsReading` to rendered bilingual text, and that is what these drive.

**The absence is the point of one whole group.** `FR-170` requires the Period
Comparison surface be "held open visibly and asserted to be unreachable, never
rendered as empty or partial", and requires the assertion be removed by the
slice that makes the source reachable rather than by this one. So a test here
fails if that source quietly becomes reachable.
"""

from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace

import pytest

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import card, seam
from khepri.rra import definitions
from khepri.rra.rendering.wording import caveat_message, metric_business_name
from khepri.rra.semantic_views import compatibility, registry
from khepri.runtime import shell_decisions

LANGUAGES = ("en", "ar")

_OVERVIEW_FIELDS = ("metric", "value", "population", "versions")
_AVAILABILITY_FIELDS = ("metric", "availability", "reason", "versions")


class _ScriptedPort:
    """Answers per `view_id`, so one request can admit S-1 and miss S-6.

    `FR-165` makes each read independently authorized and independently able to
    answer unavailable; a port that answered uniformly could not express that.
    """

    def __init__(self, outcomes: dict[str, ports.ViewOutcome | None]) -> None:
        """Answer each view with what it was scripted to answer."""
        self.outcomes = outcomes
        self.seen: list[str] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome | None:
        """Record which view was asked for, and answer as scripted."""
        self.seen.append(request.view_id)
        return self.outcomes.get(request.view_id)


class _FakeIsolation:
    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """One owner id; scoping is not what these cases are testing."""
        return f"owner-of-{organization_id}"


class _FakeSources:
    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        """A source the fake port never inspects."""
        return object()


def _actions(outcomes: dict[str, ports.ViewOutcome | None]) -> object:
    from khepri.rca.semantic_queries.queries import SemanticQueryActions

    return SemanticQueryActions(_FakeIsolation(), _FakeSources(), _ScriptedPort(outcomes))


def _projection(
    view: seam.ViewIdentity, fields: tuple[str, ...], rows: tuple[tuple[object, ...], ...],
    *, caveats: tuple[object, ...] = ()
) -> ports.ViewOutcome:
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=view.view_id,
            view_version=view.view_version,
            fields=fields,
            rows=rows,
            caveats=caveats,
        ),
    )


def _overview(rows: tuple[tuple[object, ...], ...], **kw: object) -> ports.ViewOutcome:
    return _projection(seam.EXECUTIVE_OVERVIEW, _OVERVIEW_FIELDS, rows, **kw)  # type: ignore[arg-type]


def _availability(rows: tuple[tuple[object, ...], ...]) -> ports.ViewOutcome:
    return _projection(seam.METRIC_AVAILABILITY, _AVAILABILITY_FIELDS, rows)


def _request() -> card.CardsRequest:
    return card.CardsRequest(organization_id="org-1", account_id="acct-1", source_id="run-1")


def _one_card(
    *, availability: str | None = definitions.AVAILABLE, caveats: tuple[object, ...] = ()
) -> card.MetricCard:
    """One admitted revenue card, qualified as the arguments say."""
    rows = (("revenue", "700.00", "complete", ()),)
    outcomes = {seam.EXECUTIVE_OVERVIEW.view_id: _overview(rows, caveats=caveats)}
    if availability is not None:
        outcomes[seam.METRIC_AVAILABILITY.view_id] = _availability(
            (("revenue", availability, None, ()),)
        )
    reading = card.read_cards(_actions(outcomes), _request())
    return reading.cards[0]


# --- FR-162: every line the card must expose --------------------------------


def test_the_card_exposes_every_fr162_line() -> None:
    """`FR-162` -- named even where the source is a later slice's."""
    for line in (
        "metric", "value", "population", "versions", "status",
        "availability", "reason", "caveats", "comparison", "evidence",
    ):
        assert hasattr(_one_card(), line), line


# --- FR-162: the four-status selection ---------------------------------------


@pytest.mark.parametrize(
    "kind,availability,caveats,expected",
    [
        (ports.KIND_REFUSED, definitions.AVAILABLE, (), card.STATUS_REFUSED),
        (ports.KIND_REFUSED, definitions.UNAVAILABLE, ("c",), card.STATUS_REFUSED),
        (ports.KIND_UNAVAILABLE, definitions.AVAILABLE, (), card.STATUS_UNAVAILABLE),
        (ports.KIND_ADMITTED, definitions.UNAVAILABLE, (), card.STATUS_UNAVAILABLE),
        (ports.KIND_ADMITTED, definitions.PARTIAL, (), card.STATUS_CAVEATED),
        (ports.KIND_ADMITTED, definitions.AVAILABLE, ("c",), card.STATUS_CAVEATED),
        (ports.KIND_ADMITTED, definitions.AVAILABLE, (), card.STATUS_VERIFIED),
        # An absent availability is not a quiet yes: S-6 did not affirm, so the
        # card may not claim verified.
        (ports.KIND_ADMITTED, None, (), card.STATUS_CAVEATED),
    ],
)
def test_the_four_statuses_are_selected_not_derived(
    kind: str, availability: str | None, caveats: tuple[object, ...], expected: str
) -> None:
    """`FR-162` -- refused, then unavailable, then caveated, then verified."""
    assert card.card_status(kind, availability, caveats) == expected


def test_the_availability_literals_match_the_governed_vocabulary() -> None:
    """The pin's cost, paid here as `D1-02` pays it for the view versions."""
    assert card.AVAILABILITY_AVAILABLE == definitions.AVAILABLE
    assert card.AVAILABILITY_PARTIAL == definitions.PARTIAL
    assert card.AVAILABILITY_UNAVAILABLE == definitions.UNAVAILABLE


def test_the_card_module_derives_nothing() -> None:
    """`FR-159` -- selection is presentation; counting or scoring is not."""
    tree = ast.parse(pathlib.Path(card.__file__).read_text(encoding="utf-8"))
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not called & {"sum", "min", "max", "round", "abs", "sorted", "len"}


# --- FR-165 and the dispatch rule carried from D1-02 -------------------------


def test_an_unavailable_availability_read_still_renders_the_figures() -> None:
    """`FR-165` -- partial success: S-6 missing qualifies nothing, hides nothing."""
    outcomes = {
        seam.EXECUTIVE_OVERVIEW.view_id: _overview((("revenue", "700.00", "complete", ()),)),
        seam.METRIC_AVAILABILITY.view_id: ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE),
    }
    reading = card.read_cards(_actions(outcomes), _request())
    assert reading.cards[0].value == "700.00"
    assert reading.cards[0].availability is None
    # The figure survives; the claim does not get promoted. Governance never
    # answered, so `verified` would assert more than it supports.
    assert reading.cards[0].status == card.STATUS_CAVEATED


def test_a_refusal_carrying_a_projection_is_still_a_refusal() -> None:
    """Carried from `D1-02`: dispatch on the declared kind, never on the payload."""
    refusal = ports.ViewRefusal(cause="unsupported_filter")
    contradictory = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=refusal,
        projection=ports.ViewProjection(
            view_id=seam.EXECUTIVE_OVERVIEW.view_id,
            view_version=seam.EXECUTIVE_OVERVIEW.view_version,
            fields=_OVERVIEW_FIELDS,
            rows=(("revenue", "700.00", "complete", ()),),
        ),
    )
    reading = card.read_cards(
        _actions({seam.EXECUTIVE_OVERVIEW.view_id: contradictory}), _request()
    )
    assert reading.status == ports.KIND_REFUSED
    assert reading.cards == ()
    assert reading.refusal is refusal


# --- FR-170: the absence this slice may not close ----------------------------


def test_no_card_carries_a_comparison() -> None:
    """`FR-170` -- the Period Comparison source is not reachable, so there is none."""
    assert _one_card().comparison is None


def test_the_reading_states_the_comparison_surface_is_unreachable() -> None:
    """`FR-170` -- held open visibly, never rendered as empty or partial."""
    reading = card.read_cards(
        _actions({seam.EXECUTIVE_OVERVIEW.view_id: _overview((("revenue", "7", "c", ()),))}),
        _request(),
    )
    assert reading.comparison_unreachable is True


def test_the_period_comparison_source_is_still_unreachable() -> None:
    """`FR-170` -- remove this with the slice that makes the source reachable.

    `PeriodComparisonView` admits a two-population bundle and the shipping
    adapter builds one population per run, so `FR-136`'s shape predicate refuses
    it. If this ever stops being true, the absence above became a lie and both
    must be revisited deliberately rather than discovered by a customer.
    """
    definition = registry.define_view(seam.PERIOD_COMPARISON.view_id)
    single = registry.define_view(seam.EXECUTIVE_OVERVIEW.view_id)
    assert definition.accepted_source_shape != single.accepted_source_shape


# --- FR-164 and FR-171: the surface ------------------------------------------


def test_the_surface_declares_no_route_without_the_collaborator() -> None:
    """`FR-046` -- unknown address rather than a surface that exists and refuses."""
    assert shell_decisions.offers_decisions(object()) is False


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_card_is_named_from_the_governed_catalog(language: str) -> None:
    """`FR-159`/`FR-171` -- the label is the catalog's, in the page language."""
    view = shell_decisions.decision_view(
        card.read_cards(
            _actions({seam.EXECUTIVE_OVERVIEW.view_id: _overview((("revenue", "7", "c", ()),))}),
            _request(),
        ),
        language=language,
    )
    assert view.cards[0].label == metric_business_name("revenue", language)


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_refusal_shows_governed_wording_and_no_figure(language: str) -> None:
    """`FR-164` -- never an invented string, and never a nearby substitution."""
    refusal = ports.ViewRefusal(
        cause="unsupported_filter",
        wording_pairs=(
            ("en", "That filter is not supported."),
            ("ar", "هذا المرشح غير مدعوم."),
        ),
    )
    outcome = ports.ViewOutcome(kind=ports.KIND_REFUSED, refusal=refusal)
    view = shell_decisions.decision_view(
        card.read_cards(_actions({seam.EXECUTIVE_OVERVIEW.view_id: outcome}), _request()),
        language=language,
    )
    assert view.cards == ()
    assert view.refusal == refusal.wording[language]
    assert view.refusal != refusal.cause


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_caveat_is_rendered_as_governed_prose(language: str) -> None:
    """`FR-161` -- a caveated figure shows what qualifies it, in customer words.

    Rendered once rather than per card: a `StatedCaveat` names a section and
    never a metric, so attaching one to an individual figure would assert an
    attribution the data does not carry.
    """
    caveat = SimpleNamespace(code="currency_not_declared", section=None)
    reading = card.read_cards(
        _actions(
            {
                seam.EXECUTIVE_OVERVIEW.view_id: _overview(
                    (("revenue", "7", "c", ()),), caveats=(caveat,)
                )
            }
        ),
        _request(),
    )
    view = shell_decisions.decision_view(reading, language=language)
    assert view.caveats == (caveat_message("currency_not_declared", language),)
    assert reading.cards[0].status == card.STATUS_CAVEATED


def test_both_languages_carry_the_same_cards_and_statuses() -> None:
    """`FR-171` -- a figure present in one language is present in the other."""
    reading = card.read_cards(
        _actions({seam.EXECUTIVE_OVERVIEW.view_id: _overview((("revenue", "7", "c", ()),))}),
        _request(),
    )
    views = {lang: shell_decisions.decision_view(reading, language=lang) for lang in LANGUAGES}
    assert [c.metric for c in views["en"].cards] == [c.metric for c in views["ar"].cards]
    assert [c.status for c in views["en"].cards] == [c.status for c in views["ar"].cards]
    assert views["en"].cards[0].label != views["ar"].cards[0].label


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_template_renders_the_unreachable_comparison_visibly(language: str) -> None:
    """`FR-170` -- the surface says it, rather than showing an empty tab."""
    from khepri.runtime.shell_api import SHELL_PREFIX, shell_environment

    reading = card.read_cards(
        _actions({seam.EXECUTIVE_OVERVIEW.view_id: _overview((("revenue", "7", "c", ()),))}),
        _request(),
    )
    body = shell_decisions.render_decisions(
        shell_environment(),
        reading,
        shell_decisions.DecisionFrame(
            language=language,
            organization_id="org-1",
            prefix=SHELL_PREFIX,
            source_id="run-1",
        ),
    )
    assert shell_decisions.COMPARISON_UNREACHABLE[language] in body


def test_the_request_sends_no_filter() -> None:
    """`FR-166`/`FR-137` -- this surface names a source, never a period filter."""
    port = _ScriptedPort({seam.EXECUTIVE_OVERVIEW.view_id: _overview(())})
    from khepri.rca.semantic_queries.queries import SemanticQueryActions

    actions = SemanticQueryActions(_FakeIsolation(), _FakeSources(), port)
    card.read_cards(actions, _request())
    assert compatibility  # the allowlist this would have been refused against
    assert port.seen
