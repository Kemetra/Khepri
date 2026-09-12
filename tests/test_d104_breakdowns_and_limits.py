"""`D1-04` -- the four breakdowns, the limits surface, and the route `D1-03` deferred.

Authority: active `RCA-008` `FR-159`, `FR-163`, `FR-165`, `FR-167`, with `FR-046`
and `FR-050` for the route.

The read models are driven through a fake port, as `D1-02`'s and `D1-03`'s were:
what is under test is the *selection*, and a real projection would put a pipeline
between the inputs and the choice. The route is driven over HTTP, because what is
under test there is the opposite -- that the address exists exactly when the
collaborator does, and that a scope disagreement reaches the uniform refusal.

**`FR-167` is asserted negatively and three ways**, because it is the one
requirement in this slice that a passing implementation can violate silently: the
shapes carry no availability field, a row cannot carry one because it is named by
its own projection's published fields, and the module names neither the
availability view nor any of its literals.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.organizations import Organization
from khepri.rca.semantic_queries import ports
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.decision import breakdowns, card, limits, seam
from khepri.rra.semantic_views import registry
from khepri.runtime import shell_decisions
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes

LANGUAGES = ("en", "ar")
NOW = datetime(2026, 9, 11, tzinfo=UTC)

_BRANCH_FIELDS = ("store", "metric", "value", "population")
_PRODUCT_FIELDS = ("dimension", "member", "metric", "value", "population")
_BASKET_FIELDS = ("metric", "value", "population", "versions")
_CONCENTRATION_FIELDS = ("dimension", "metric", "value", "population")
_OVERVIEW_FIELDS = ("metric", "value", "population", "versions")
_AVAILABILITY_FIELDS = ("metric", "availability", "reason", "versions")

#: Each breakdown reader, with the identity and published fields it must read.
_BREAKDOWNS = (
    (breakdowns.read_branches, seam.BRANCH_PERFORMANCE, _BRANCH_FIELDS),
    (breakdowns.read_products, seam.PRODUCT_CATEGORY, _PRODUCT_FIELDS),
    (breakdowns.read_basket, seam.BASKET, _BASKET_FIELDS),
    (breakdowns.read_concentration, seam.CONCENTRATION, _CONCENTRATION_FIELDS),
)


class _ScriptedPort:
    """Answers per `view_id`, so one surface can admit one read and miss the other.

    `FR-165` makes each read independently authorized and independently able to
    answer unavailable; a port that answered uniformly could not express that.
    """

    def __init__(self, outcomes: dict[str, ports.ViewOutcome | None]) -> None:
        """Answer each view with what it was scripted to answer."""
        self.outcomes = outcomes
        self.requests: list[ports.SemanticViewRequest] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome | None:
        """Record the request verbatim, and answer as scripted."""
        self.requests.append(request)
        return self.outcomes.get(request.view_id)


class _FakeIsolation:
    """One owner id for any pair; scoping is not what the read-model cases test."""

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """One owner id; scoping is not what the read-model cases are testing."""
        return f"owner-of-{organization_id}"


class _FakeSources:
    """A source reader that always finds the run, so the port decides every answer."""

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        """A source the fake port never inspects."""
        return object()


def _port(outcomes: dict[str, ports.ViewOutcome | None]) -> _ScriptedPort:
    """A port scripted per view, kept so a case can read back what was asked."""
    return _ScriptedPort(outcomes)


def _actions(port: _ScriptedPort) -> SemanticQueryActions:
    """The real orchestration over a fake door and a scripted port."""
    return SemanticQueryActions(_FakeIsolation(), _FakeSources(), port)


@dataclasses.dataclass(frozen=True, slots=True)
class _Published:
    """What a scripted projection publishes besides its rows.

    Grouped rather than spelled as two more parameters, for the reason
    `DecisionRead` and `DecisionFrame` are: the flat form carries five arguments
    and CodeScene reads a fifth as an Excess Number of Function Arguments. This
    programme has paid that finding four times now, the fourth here.
    """

    caveats: tuple[object, ...] = ()
    is_empty: bool = False


#: A projection that publishes nothing besides its rows. A module-level
#: singleton rather than a call in the default, which `B008` bars: it is frozen,
#: so the one instance cannot pick up a caller's qualification.
_PUBLISHES_NOTHING = _Published()


def _projection(
    view: seam.ViewIdentity,
    fields: tuple[str, ...],
    rows: tuple[tuple[object, ...], ...],
    published: _Published = _PUBLISHES_NOTHING,
) -> ports.ViewOutcome:
    """An admitted outcome carrying one view's rows in its published field order."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=view.view_id,
            view_version=view.view_version,
            fields=fields,
            rows=rows,
            caveats=published.caveats,
            is_empty=published.is_empty,
        ),
    )


def _request(**kw: object) -> breakdowns.BreakdownRequest:
    """One member asking over one run; `filters` travels in the keywords."""
    return breakdowns.BreakdownRequest(
        organization_id="org-1", account_id="acct-1", source_id="run-1", **kw  # type: ignore[arg-type]
    )


def _read(
    reader: object, view: seam.ViewIdentity, outcome: ports.ViewOutcome | None, **kw: object
) -> breakdowns.BreakdownReading:
    """One breakdown read against a port scripted to answer that view alone."""
    port = _port({view.view_id: outcome})
    return reader(_actions(port), _request(**kw))  # type: ignore[operator]


# --- FR-160: each breakdown reads its own view, at its own literal version ----


@pytest.mark.parametrize("reader,view,fields", _BREAKDOWNS)
def test_each_breakdown_reads_only_its_own_view_at_its_pinned_version(
    reader: object, view: seam.ViewIdentity, fields: tuple[str, ...]
) -> None:
    """`FR-160` -- named exactly, and no second view fetched to fill anything in."""
    port = _port({view.view_id: _projection(view, fields, ())})
    reader(_actions(port), _request())  # type: ignore[operator]
    assert [asked.view_id for asked in port.requests] == [view.view_id]
    assert port.requests[0].view_version == view.view_version


@pytest.mark.parametrize("reader,view,fields", _BREAKDOWNS)
def test_each_breakdown_names_no_metric_so_the_view_selects(
    reader: object, view: seam.ViewIdentity, fields: tuple[str, ...]
) -> None:
    """`FR-135` -- an empty selection asks for the definition's own published one."""
    port = _port({view.view_id: _projection(view, fields, ())})
    reader(_actions(port), _request())  # type: ignore[operator]
    assert port.requests[0].metrics == ()
    assert port.requests[0].dimensions == ()


# --- FR-159: a row is its projection's own, named and passed through ----------


def test_a_branch_row_carries_exactly_the_fields_the_view_published() -> None:
    """`FR-159` -- select, order, group for layout. Nothing renamed, nothing added."""
    reading = _read(
        breakdowns.read_branches,
        seam.BRANCH_PERFORMANCE,
        _projection(seam.BRANCH_PERFORMANCE, _BRANCH_FIELDS, (("store-a", "revenue", "7", "c"),)),
    )
    assert reading.rows[0].values == {
        "store": "store-a",
        "metric": "revenue",
        "value": "7",
        "population": "c",
    }


def test_a_product_row_carries_its_own_five_fields() -> None:
    """The four views publish four field orders; a row is named by its own."""
    reading = _read(
        breakdowns.read_products,
        seam.PRODUCT_CATEGORY,
        _projection(
            seam.PRODUCT_CATEGORY, _PRODUCT_FIELDS, (("category", "drinks", "revenue", "7", "c"),)
        ),
    )
    assert tuple(name for name, _value in reading.rows[0].cells) == _PRODUCT_FIELDS


def test_a_row_of_the_wrong_width_raises_rather_than_truncating() -> None:
    """A projection narrower than its field order would lose a governed field."""
    with pytest.raises(ValueError):
        _read(
            breakdowns.read_branches,
            seam.BRANCH_PERFORMANCE,
            _projection(seam.BRANCH_PERFORMANCE, _BRANCH_FIELDS, (("store-a", "revenue"),)),
        )


# --- FR-163: the two empty rules, on the same page ---------------------------


def test_the_breakdowns_report_both_governed_empty_rules() -> None:
    """`FR-163` -- S-3 and S-4 state no rows; S-5's two views state absence."""
    rules = {}
    for reader, view, fields in _BREAKDOWNS:
        reading = _read(reader, view, _projection(view, fields, (), _Published(is_empty=True)))
        rules[view.view_id] = reading.empty_rule
    assert rules[seam.BRANCH_PERFORMANCE.view_id] == seam.EMPTY_STATED_NO_ROWS
    assert rules[seam.PRODUCT_CATEGORY.view_id] == seam.EMPTY_STATED_NO_ROWS
    assert rules[seam.BASKET.view_id] == seam.EMPTY_STATED_ABSENCE
    assert rules[seam.CONCENTRATION.view_id] == seam.EMPTY_STATED_ABSENCE
    assert seam.EMPTY_STATED_NO_ROWS != seam.EMPTY_STATED_ABSENCE


def test_a_store_filter_that_matched_nothing_is_not_a_refusal() -> None:
    """`FR-163` -- "nothing matched what you asked" is not "we could not compute this"."""
    reading = _read(
        breakdowns.read_branches,
        seam.BRANCH_PERFORMANCE,
        _projection(seam.BRANCH_PERFORMANCE, _BRANCH_FIELDS, (), _Published(is_empty=True)),
        filters=(("store", "store-z"),),
    )
    assert reading.status == ports.KIND_ADMITTED
    assert reading.refusal is None
    assert reading.empty_rule == seam.EMPTY_STATED_NO_ROWS


def test_a_non_empty_projection_reports_no_empty_rule() -> None:
    """The rule is the absence's, so a populated reading carries none."""
    reading = _read(
        breakdowns.read_basket,
        seam.BASKET,
        _projection(seam.BASKET, _BASKET_FIELDS, (("basket_size", "3", "c", ()),)),
    )
    assert reading.empty_rule is None


# --- FR-137 and FR-166: a filter is passed through, never dropped ------------


def test_a_filter_reaches_the_seam_verbatim() -> None:
    """`FR-137`/`FR-166` -- an unsupported filter refuses; it never gets dropped."""
    asked = (("store", "store-a"), ("product", "sku-1"))
    port = _port({seam.BRANCH_PERFORMANCE.view_id: ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE)})
    breakdowns.read_branches(_actions(port), _request(filters=asked))
    assert port.requests[0].filters == asked


# --- FR-165: S-5 is one surface and two independent reads --------------------


@pytest.mark.parametrize("admitted", ["basket", "concentration"])
def test_the_basket_surface_renders_the_half_that_answered(admitted: str) -> None:
    """`FR-165` -- partial success rather than failing whole, either way round."""
    answers = {
        seam.BASKET.view_id: _projection(
            seam.BASKET, _BASKET_FIELDS, (("basket_size", "3", "c", ()),)
        ),
        seam.CONCENTRATION.view_id: _projection(
            seam.CONCENTRATION, _CONCENTRATION_FIELDS, (("category", "top_share", "4", "c"),)
        ),
    }
    missing = "concentration" if admitted == "basket" else "basket"
    view = {"basket": seam.BASKET, "concentration": seam.CONCENTRATION}
    answers[view[missing].view_id] = ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE)
    surface = breakdowns.read_basket_surface(
        _actions(_port(answers)),
        _request(),
    )
    assert getattr(surface, admitted).rows
    assert getattr(surface, missing).rows == ()
    assert getattr(surface, missing).status == ports.KIND_UNAVAILABLE


def test_an_unavailable_half_says_nothing_about_why() -> None:
    """`FR-165` -- the unavailable outcome is content-free."""
    surface = breakdowns.read_basket_surface(
        _actions(_port({})),
        _request(),
    )
    for half in (surface.basket, surface.concentration):
        assert half.status == ports.KIND_UNAVAILABLE
        assert half.refusal is None
        assert half.caveats == ()


# --- FR-167: no breakdown figure carries a four-state availability -----------


def test_no_breakdown_shape_has_an_availability_field() -> None:
    """`FR-167` -- `MetricAvailabilityView` publishes no series metric."""
    for shape in (breakdowns.BreakdownReading, breakdowns.BreakdownRow, breakdowns.BasketSurface):
        named = {field.name for field in dataclasses.fields(shape)}
        assert "availability" not in named, shape
        assert "reason" not in named, shape


@pytest.mark.parametrize("reader,view,fields", _BREAKDOWNS)
def test_a_breakdown_row_can_only_carry_what_its_view_published(
    reader: object, view: seam.ViewIdentity, fields: tuple[str, ...]
) -> None:
    """`FR-167` -- so a four-state availability cannot be attached even by accident."""
    row = tuple("x" for _name in fields)
    reading = _read(reader, view, _projection(view, fields, (row,)))
    assert set(reading.rows[0].values) == set(fields)
    assert "availability" not in reading.rows[0].values


def test_the_breakdown_module_names_no_availability_at_all() -> None:
    """`FR-167` -- none may be *synthesized* from the core metric it aggregates.

    Read from the AST rather than the file text so the requirement can be
    explained in this module's own prose without the explanation tripping it.
    """
    tree = _tree(breakdowns)
    assert "METRIC_AVAILABILITY" not in _identifiers(tree)
    assert not _literals(tree) & {
        card.AVAILABILITY_AVAILABLE,
        card.AVAILABILITY_PARTIAL,
        card.AVAILABILITY_UNAVAILABLE,
    }


# --- S-6: one view of its own, and everything else already fetched -----------


def _limits_request(**kw: object) -> limits.LimitsRequest:
    """One S-6 request; what the page already fetched travels as `gathered`."""
    return limits.LimitsRequest(
        organization_id="org-1", account_id="acct-1", source_id="run-1", **kw  # type: ignore[arg-type]
    )


def _availability(rows: tuple[tuple[object, ...], ...]) -> ports.ViewOutcome:
    """S-6's own view, admitted, in its published field order."""
    return _projection(seam.METRIC_AVAILABILITY, _AVAILABILITY_FIELDS, rows)


def test_the_limits_surface_reads_exactly_one_view() -> None:
    """`RCA-008`'s source map: `MetricAvailabilityView`, and nothing else fetched."""
    port = _port({seam.METRIC_AVAILABILITY.view_id: _availability(())})
    limits.read_limits(_actions(port), _limits_request())
    assert [asked.view_id for asked in port.requests] == [seam.METRIC_AVAILABILITY.view_id]


def test_the_limits_surface_publishes_the_governed_four_state() -> None:
    """S-6 is where an availability may be stated, because S-6 is where one is published."""
    port = _port(
        {
            seam.METRIC_AVAILABILITY.view_id: _availability(
                (("revenue", card.AVAILABILITY_PARTIAL, "one input missing", ()),)
            )
        }
    )
    reading = limits.read_limits(_actions(port), _limits_request())
    assert reading.availabilities[0].metric == "revenue"
    assert reading.availabilities[0].availability == card.AVAILABILITY_PARTIAL
    assert reading.availabilities[0].reason == "one input missing"


def test_the_limits_surface_collects_caveats_without_reading_anything_again() -> None:
    """`FR-168`/`FR-135` -- the caveats are the surfaces' own, already fetched."""
    gathered = (
        (
            "branches",
            _projection(
                seam.BRANCH_PERFORMANCE,
                _BRANCH_FIELDS,
                (),
                _Published(caveats=("currency_not_declared",)),
            ),
        ),
    )
    port = _port({seam.METRIC_AVAILABILITY.view_id: _availability(())})
    reading = limits.read_limits(_actions(port), _limits_request(gathered=gathered))
    assert [asked.view_id for asked in port.requests] == [seam.METRIC_AVAILABILITY.view_id]
    assert reading.surfaces[0].surface == "branches"
    assert reading.surfaces[0].caveats == ("currency_not_declared",)


def test_the_limits_surface_carries_a_gathered_refusal_whole() -> None:
    """`FR-164` -- the governed wording is the surface's to render, so keep it intact."""
    refusal = ports.ViewRefusal(cause="unsupported_filter")
    gathered = (("products", ports.ViewOutcome(kind=ports.KIND_REFUSED, refusal=refusal)),)
    port = _port({seam.METRIC_AVAILABILITY.view_id: _availability(())})
    reading = limits.read_limits(_actions(port), _limits_request(gathered=gathered))
    assert reading.surfaces[0].status == ports.KIND_REFUSED
    assert reading.surfaces[0].refusal is refusal


def test_a_gathered_refusal_leaks_none_of_its_projections_caveats() -> None:
    """The kind decides on this side too: a refused read qualified no figure.

    `ViewOutcome` admits a refusal that also carries a projection, and reporting
    that projection's caveats here would qualify figures no reader was shown.
    """
    refused = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(cause="unsupported_filter"),
        projection=ports.ViewProjection(
            view_id=seam.BRANCH_PERFORMANCE.view_id,
            view_version=seam.BRANCH_PERFORMANCE.view_version,
            fields=_BRANCH_FIELDS,
            caveats=("currency_not_declared",),
        ),
    )
    port = _port({seam.METRIC_AVAILABILITY.view_id: _availability(())})
    reading = limits.read_limits(
        _actions(port), _limits_request(gathered=(("branches", refused),))
    )
    assert reading.surfaces[0].caveats == ()


def test_a_gathered_unavailable_surface_says_nothing_about_why() -> None:
    """`FR-165` -- content-free, on the surface that exists to report limits."""
    gathered = (("basket", ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE)),)
    port = _port({seam.METRIC_AVAILABILITY.view_id: _availability(())})
    reading = limits.read_limits(_actions(port), _limits_request(gathered=gathered))
    assert reading.surfaces[0].status == ports.KIND_UNAVAILABLE
    assert reading.surfaces[0].refusal is None
    assert reading.surfaces[0].caveats == ()


# --- the dispatch rule, carried from D1-02 and D1-03 -------------------------


def _contradictory(view: seam.ViewIdentity, fields: tuple[str, ...]) -> ports.ViewOutcome:
    """A refusal that also carries a projection. `ViewOutcome` admits one."""
    return ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=ports.ViewRefusal(cause="unsupported_filter"),
        projection=ports.ViewProjection(
            view_id=view.view_id,
            view_version=view.view_version,
            fields=fields,
            rows=(tuple("x" for _name in fields),),
        ),
    )


@pytest.mark.parametrize("reader,view,fields", _BREAKDOWNS)
def test_a_refused_breakdown_carrying_a_projection_is_still_refused(
    reader: object, view: seam.ViewIdentity, fields: tuple[str, ...]
) -> None:
    """The kind decides, never the payload: `ViewOutcome` has no validation."""
    reading = _read(reader, view, _contradictory(view, fields))
    assert reading.status == ports.KIND_REFUSED
    assert reading.rows == ()
    assert reading.refusal is not None


def test_a_refused_limits_read_carrying_a_projection_is_still_refused() -> None:
    """The same rule, on S-6's own read."""
    port = _port(
        {
            seam.METRIC_AVAILABILITY.view_id: _contradictory(
                seam.METRIC_AVAILABILITY, _AVAILABILITY_FIELDS
            )
        }
    )
    reading = limits.read_limits(_actions(port), _limits_request())
    assert reading.status == ports.KIND_REFUSED
    assert reading.availabilities == ()


def test_the_dispatch_rule_has_exactly_one_definition() -> None:
    """It is the seam's, because four read models now depend on it."""
    assert seam.admitted_projection(ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE)) is None
    assert not hasattr(card, "_admitted_projection")


# --- the static scans, over the two modules this slice adds ------------------


def _tree(module: object) -> ast.Module:
    """The module's own source as a tree, read from where it was imported from."""
    return ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))  # type: ignore[attr-defined]


def _identifiers(tree: ast.Module) -> set[str]:
    """Every name and attribute the module reads, whatever it was imported as."""
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    return names | {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}


def _literals(tree: ast.Module) -> set[str]:
    """Every string constant in the tree.

    The **tree** and not the file text, so the module under scan can explain the
    requirement it is scanned for in prose without the explanation tripping it:
    a comment is not in the tree at all, and a docstring reaches here as one
    constant holding the whole document, which no one-word governed term can
    equal. A first pass excluded docstrings by identity and scored a cyclomatic
    9 against a threshold of 9 for machinery that could never change an answer.
    """
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


@pytest.mark.parametrize("module", [breakdowns, limits])
def test_the_new_read_models_derive_nothing(module: object) -> None:
    """`FR-159` -- a surface that computes is a defect, whatever the arithmetic's size."""
    tree = _tree(module)
    called = {
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert not called & {"sum", "min", "max", "round", "abs", "sorted", "len"}


# --- the route D1-03 deferred ------------------------------------------------


class _Context:
    """A resolved actor in one organization, as `ActorResolver` answers one."""

    def __init__(self, organization_id: str | None = "org-acme") -> None:
        """One owner of `org-acme` unless the case names another scope."""
        self.account_id = "acct-1"
        self.organization_id = organization_id
        self.role = "owner"

    @property
    def is_owner(self) -> bool:
        """Owner everywhere; the decision surface is a read and never asks."""
        return True


class _StubResolver:
    """The scope door, answering one context or raising what the case supplies."""

    def __init__(
        self, context: _Context | None = None, raises: Exception | None = None
    ) -> None:
        """Hold the one context this resolver answers with, or what it raises."""
        self._context = context or _Context()
        self._raises = raises

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        """The session's context, or the failure this case was built to drive."""
        if self._raises is not None:
            raise self._raises
        return self._context

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:  # pragma: no cover
        """Never reached: nothing on this surface is owner-gated."""
        raise AssertionError("the decision surface is a read")


class _StubOrganizations:
    """One membership, so the frame resolves rather than the chooser rendering."""

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        """The one organization every case in this file acts in."""
        return [
            Organization._from_storage(
                organization_id="org-acme", name="Acme", created_at=NOW
            )
        ]


class _StubDecisions:
    """One admitted overview and one governed availability, for any request."""

    def request(self, asked: object) -> ports.ViewOutcome:
        """S-6's governed four-state for its own view, and S-1's figures otherwise."""
        if asked.view.view_id == seam.METRIC_AVAILABILITY.view_id:  # type: ignore[attr-defined]
            return _availability((("revenue", card.AVAILABILITY_AVAILABLE, None, ()),))
        return _projection(
            seam.EXECUTIVE_OVERVIEW, _OVERVIEW_FIELDS, (("revenue", "700.00", "complete", ()),)
        )


def _shell(*, decisions: object | None, raises: Exception | None = None) -> TestClient:
    """A shell wired with the decision collaborator the case asks for, and a session."""
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(raises=raises),
            organizations=_StubOrganizations(),
            decisions=decisions,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _address(organization: str = "org-acme", language: str = "en") -> str:
    """The decision surface's address for one completed run."""
    return f"{SHELL_PREFIX}/{language}/{organization}/decisions/run-a"


def test_a_shell_without_the_collaborator_declares_no_decision_address() -> None:
    """`FR-046` -- unknown rather than a surface that exists and refuses."""
    body = _shell(decisions=None).get(_address()).text
    assert shell_decisions.DECISION_COPY["en"]["title"] not in body


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_member_reaches_the_decision_surface_in_the_page_language(language: str) -> None:
    """`FR-171` -- the governed figures, named in the language the address carries."""
    response = _shell(decisions=_StubDecisions()).get(_address(language=language))
    assert response.status_code == 200
    assert shell_decisions.DECISION_COPY[language]["title"] in response.text
    assert "700.00" in response.text


def test_the_route_states_the_comparison_surface_is_unreachable() -> None:
    """`FR-170` -- held open visibly on the surface a reader can actually reach."""
    body = _shell(decisions=_StubDecisions()).get(_address()).text
    assert shell_decisions.COMPARISON_UNREACHABLE["en"] in body


def test_an_address_naming_another_organization_gets_the_uniform_refusal() -> None:
    """`FR-042`/`FR-050` -- scope comes from the session, never from the address."""
    body = _shell(decisions=_StubDecisions()).get(_address(organization="org-other")).text
    assert "700.00" not in body
    assert shell_decisions.DECISION_COPY["en"]["title"] not in body


def test_an_unresolvable_session_gets_the_uniform_refusal() -> None:
    """`FR-050` -- one surface absorbs every cause a reader must not tell apart."""
    body = _shell(decisions=_StubDecisions(), raises=ScopeAccessDenied()).get(_address()).text
    assert "700.00" not in body


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_language_control_points_at_an_address_the_route_serves(language: str) -> None:
    """`FR-054` scenario 11 / `FR-171` -- the switch keeps the surface, run and all.

    Review on `#448` found `DecisionFrame.source_id` defaulting to `""`, which
    rendered the control pointing at `/{organization}/decisions/` -- an address
    `add_decision_routes` does not serve. Following the link is the assertion:
    a tail that drops the run answers `unavailable` and shows no figure.
    """
    client = _shell(decisions=_StubDecisions())
    body = client.get(_address(language=language)).text
    href = re.search(r'class="frame-language"\s+href="([^"]+)"', body)
    assert href is not None, "the decision surface rendered no language control"
    switched = client.get(href.group(1))
    assert switched.status_code == 200
    assert "700.00" in switched.text
    assert shell_decisions.DECISION_COPY["ar" if language == "en" else "en"]["title"] in (
        switched.text
    )


def test_a_decision_frame_must_name_the_run_it_renders() -> None:
    """Review on `#448`: the frameless render path carried the same defect.

    `DecisionFrame.source_id` had a default of `""`, so `render_decisions` could
    emit the language control beside a tail with no run on it. Requiring the
    field removes the state instead of hiding the control in it -- this surface
    renders exactly one completed run, so a frame naming none was never valid.
    """
    from khepri.runtime.shell_api import shell_environment

    with pytest.raises(TypeError):
        shell_decisions.DecisionFrame(  # type: ignore[call-arg]
            language="en", organization_id="org-acme", prefix=SHELL_PREFIX
        )

    # The explicit empty, refused for the same reason the omission is (`#448`, second
    # round). Dropping the default answers the frame that forgets its run; it does not
    # answer the one that names `""`, whose tail is `/decisions/` -- an address the
    # router 404s, having no run segment to match.
    with pytest.raises(ValueError):
        shell_decisions.DecisionFrame(
            language="en", organization_id="org-acme", prefix=SHELL_PREFIX, source_id=""
        )

    # And the organization half of the same address: `//decisions/run-a` is 404ed
    # for the same reason, so guarding only the run would close half an invariant.
    with pytest.raises(ValueError):
        shell_decisions.DecisionFrame(
            language="en", organization_id="", prefix=SHELL_PREFIX, source_id="run-a"
        )

    body = shell_decisions.render_decisions(
        shell_environment(),
        card.read_cards(
            _actions(
                _port(
                    {
                        seam.EXECUTIVE_OVERVIEW.view_id: _projection(
                            seam.EXECUTIVE_OVERVIEW, _OVERVIEW_FIELDS, (("revenue", "7", "c", ()),)
                        )
                    }
                )
            ),
            card.CardsRequest(
                organization_id="org-acme", account_id="acct-1", source_id="run-a"
            ),
        ),
        shell_decisions.DecisionFrame(
            language="en",
            organization_id="org-acme",
            prefix=SHELL_PREFIX,
            source_id="run-a",
        ),
    )
    href = re.search(r'class="frame-language"\s+href="([^"]+)"', body)
    assert href is not None
    assert href.group(1).endswith("/org-acme/decisions/run-a")


def test_the_period_comparison_source_is_still_unreachable() -> None:
    """`FR-170` -- carried from `D1-03`; removed by the slice that binds the source."""
    two = registry.define_view(seam.PERIOD_COMPARISON.view_id)
    one = registry.define_view(seam.BASKET.view_id)
    assert two.accepted_source_shape != one.accepted_source_shape
