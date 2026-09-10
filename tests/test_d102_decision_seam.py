"""`D1-02` -- the decision read path, its version literals, and what it may not do.

Authority: active `RCA-008` `FR-159`, `FR-160`, `FR-163`, `FR-165`, `FR-168`.

Two kinds of test live here and they answer different risks.

The **behavioural** ones drive `read_overview` through a fake port, because
`D1-02` ships no route and there is nothing to drive end to end: `RCA-008`
§Scope admits the read models, and `D1-03` is the first slice with a surface.
What they prove is that an outcome survives into a reading unchanged -- an
unavailable one carrying no reason, a refusal carrying its governed wording.

The **static** ones read `decision/`'s own AST. `FR-159` says "a surface that
computes is a defect, not a feature, whatever the arithmetic's size", and a
prohibition that size-independent cannot be held by review. `SV1-04` set this
precedent for the no-RRA-import rule; this widens it to arithmetic, to raw-row
access, and to `FR-160`'s ban on resolving a version at read time.

The source-map test is the one that keeps the literals honest: `FR-160` requires
a `view_version` be a literal in the reading module, and the cost of a literal is
that it can go stale. So every identity here is asserted against what
`RRA-014`'s registry actually publishes. A republication fails this test, which
is exactly the visibility `FR-160` says a republication must have.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import overview, seam
from khepri.rra.semantic_views.registry import define_view, view_ids

#: Names whose result is a figure derived on this side of the seam (`FR-159`).
_DERIVING_CALLS = ("sum", "min", "max", "round", "abs", "sorted")

#: `FR-160` -- resolving a version at read time is the `latest` alias by another
#: spelling. Named here rather than in the requirement's prose so the ban is
#: mechanical.
_REGISTRY_LOOKUPS = ("published_versions", "published_history", "view_ids", "define_view")

#: `FR-159` "may not read raw rows", and `RCA-006`'s package boundary: the RCA
#: side calls a Protocol and never imports a concrete RRA implementation.
_BARRED_IMPORTS = (
    "khepri.rra",
    "khepri.rca.workspace.store",
    "khepri.rca.workspace.persistence",
)

#: Arithmetic operators. `FR-159` bars sum, average, difference and percentage
#: alike, and the operator is the smallest thing all four have in common.
_ARITHMETIC = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)

_DECISION_DIR = pathlib.Path(seam.__file__).parent


def _decision_modules() -> tuple[pytest.param, ...]:
    """Every module under `decision/`, parsed and named. Discovered, never listed.

    A listed set of files would pass while a ninth module quietly computed.
    """
    return tuple(
        pytest.param(path.name, ast.parse(path.read_text(encoding="utf-8")), id=path.name)
        for path in sorted(_DECISION_DIR.glob("*.py"))
    )


def _called_names(tree: ast.Module) -> tuple[str, ...]:
    """Every name this module calls, by either `f(...)` or `x.f(...)`.

    One collector for three prohibitions. Extracted rather than repeated in
    each test because CodeScene counts nested blocks per function, and the
    inline form put a conditional inside a loop in every one of them.
    """
    return tuple(
        node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    )


def _operators(tree: ast.Module) -> tuple[ast.operator, ...]:
    """Every binary and augmented-assignment operator this module applies."""
    return tuple(
        node.op for node in ast.walk(tree) if isinstance(node, ast.BinOp | ast.AugAssign)
    )


def _imported_names(tree: ast.Module) -> tuple[str, ...]:
    """Every module name this module imports, by either statement form."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return tuple(names)


class _FakePort:
    """A `SemanticViewPort` answering as told, and recording what it was handed.

    Recording is the point for the metrics test: what matters is not what came
    back but that the request named no metric, leaving the selection to the
    view.
    """

    def __init__(self, outcome: ports.ViewOutcome | None) -> None:
        """Answer with `outcome` every time, and keep each request."""
        self.outcome = outcome
        self.requests: list[ports.SemanticViewRequest] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome | None:
        """Record the request and answer as constructed."""
        self.requests.append(request)
        return self.outcome


class _FakeIsolation:
    """`resolve_scope` only. This path may do nothing else with an identity."""

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """One owner id, deterministic and uninteresting."""
        return f"owner-of-{organization_id}"


class _FakeSources:
    """One run that always resolves, so scoping is not what a case is testing."""

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        """A source object the port never inspects."""
        return object()


def _actions(outcome: ports.ViewOutcome | None) -> tuple[object, _FakePort]:
    """A `SemanticQueryActions` wired to fakes, and the port to interrogate."""
    from khepri.rca.semantic_queries.queries import SemanticQueryActions

    port = _FakePort(outcome)
    return SemanticQueryActions(_FakeIsolation(), _FakeSources(), port), port


def _request() -> overview.OverviewRequest:
    """The one S-1 request every behavioural case uses."""
    return overview.OverviewRequest(
        organization_id="org-1", account_id="acct-1", source_id="run-1"
    )


def _projection(
    rows: tuple[tuple[object, ...], ...], *, is_empty: bool = False
) -> ports.ViewOutcome:
    """An admitted outcome over S-1's published field order."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.EXECUTIVE_OVERVIEW.view_id,
            view_version=seam.EXECUTIVE_OVERVIEW.view_version,
            fields=("metric", "value", "population", "versions"),
            rows=rows,
            is_empty=is_empty,
        ),
    )


def test_decision_views_are_exactly_the_eight_published_views() -> None:
    """`FR-160` -- the closed registry, and no ninth identity invented here."""
    assert {identity.view_id for identity in seam.DECISION_VIEWS} == set(view_ids())


@pytest.mark.parametrize("identity", seam.DECISION_VIEWS, ids=lambda i: i.view_id)
def test_each_identity_matches_what_the_registry_publishes(identity: seam.ViewIdentity) -> None:
    """`FR-160`/`FR-163` -- the literal's cost is staleness, so it is pinned here.

    A registry republication fails this, which is the visibility `FR-160`
    requires a republication to have.
    """
    published = define_view(identity.view_id)
    assert identity.view_version == published.view_version
    assert identity.empty_rule == published.empty_result_rule


def test_every_view_version_is_a_string_literal_in_the_module() -> None:
    """`FR-160` -- a literal constant, not a call result and not an f-string."""
    tree = ast.parse(pathlib.Path(seam.__file__).read_text(encoding="utf-8"))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for identity in seam.DECISION_VIEWS:
        assert identity.view_version in literals


@pytest.mark.parametrize("name,tree", _decision_modules())
def test_no_decision_module_resolves_a_version_at_read_time(name: str, tree: ast.Module) -> None:
    """`FR-160` -- enumeration is the `latest` alias reached by another spelling."""
    for called in _called_names(tree):
        assert called not in _REGISTRY_LOOKUPS, f"{name}: {called}"


@pytest.mark.parametrize("name,tree", _decision_modules())
def test_no_decision_module_performs_arithmetic(name: str, tree: ast.Module) -> None:
    """`FR-159` -- "whatever the arithmetic's size", so the operator is the test."""
    for operator in _operators(tree):
        assert not isinstance(operator, _ARITHMETIC), f"{name}: {type(operator).__name__}"


@pytest.mark.parametrize("name,tree", _decision_modules())
def test_no_decision_module_derives_a_figure_by_call(name: str, tree: ast.Module) -> None:
    """`FR-159` -- ranking and aggregation arrive as builtins, not as operators.

    `sorted` is barred with the rest: `FR-134` makes output order part of view
    identity, so a read model that reorders has replaced a published decision
    with a local one.
    """
    for called in _called_names(tree):
        assert called not in _DERIVING_CALLS, f"{name}: {called}"
        assert called != "sort", f"{name}: sort"


@pytest.mark.parametrize("name,tree", _decision_modules())
def test_no_decision_module_reaches_rra_or_raw_rows(name: str, tree: ast.Module) -> None:
    """`FR-159` "may not read raw rows", and `RCA-006`'s package boundary."""
    for imported in _imported_names(tree):
        assert not imported.startswith(_BARRED_IMPORTS), f"{name}: {imported}"


def test_the_request_names_no_metric_so_the_view_selects() -> None:
    """`FR-135` -- an empty selection is the view's own, never a retyped list.

    `compatibility.py` : "An empty `metrics` or `dimensions` asks for the
    definition's own published selection rather than for nothing."
    """
    actions, port = _actions(_projection(()))
    overview.read_overview(actions, _request())
    assert port.requests[0].metrics == ()
    assert port.requests[0].dimensions == ()


def test_the_request_names_the_pinned_version_exactly() -> None:
    """`FR-160` -- the version reaching the port is S-1's literal."""
    actions, port = _actions(_projection(()))
    overview.read_overview(actions, _request())
    assert port.requests[0].view_id == seam.EXECUTIVE_OVERVIEW.view_id
    assert port.requests[0].view_version == seam.EXECUTIVE_OVERVIEW.view_version


def test_an_unavailable_read_is_content_free() -> None:
    """`FR-165` -- "may say a part is unavailable and may never say why"."""
    actions, _ = _actions(ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE))
    reading = overview.read_overview(actions, _request())
    assert reading.status == ports.KIND_UNAVAILABLE
    assert reading.figures == ()
    assert not hasattr(reading, "reason")


def test_a_refusal_is_carried_intact_for_governed_wording() -> None:
    """`FR-164` -- the surface renders `ViewRefusal.wording`, so it must survive."""
    refusal = ports.ViewRefusal(
        cause="unsupported_filter", wording_pairs=(("en", "No."), ("ar", "لا."))
    )
    actions, _ = _actions(ports.ViewOutcome(kind=ports.KIND_REFUSED, refusal=refusal))
    reading = overview.read_overview(actions, _request())
    assert reading.status == ports.KIND_REFUSED
    assert reading.refusal is refusal
    assert reading.figures == ()


def test_an_admitted_projection_becomes_figures_in_source_order() -> None:
    """`FR-159` -- select and pass through; the order is the projection's."""
    rows = (("revenue", "700.00", "complete", ()), ("units", "12", "complete", ()))
    actions, _ = _actions(_projection(rows))
    reading = overview.read_overview(actions, _request())
    assert reading.status == ports.KIND_ADMITTED
    assert tuple(figure.metric for figure in reading.figures) == ("revenue", "units")
    assert reading.figures[0].value == "700.00"
    assert reading.figures[0].population == "complete"


def test_the_two_empty_rules_are_distinct_and_both_are_represented() -> None:
    """`FR-163` -- different findings with different remedies."""
    assert seam.EMPTY_STATED_ABSENCE != seam.EMPTY_STATED_NO_ROWS
    rules = {identity.empty_rule for identity in seam.DECISION_VIEWS}
    assert rules == {seam.EMPTY_STATED_ABSENCE, seam.EMPTY_STATED_NO_ROWS}


def test_an_empty_projection_reports_its_own_views_empty_rule() -> None:
    """`FR-163` -- "a surface that renders both as an empty table misstates"."""
    actions, _ = _actions(_projection((), is_empty=True))
    reading = overview.read_overview(actions, _request())
    assert reading.figures == ()
    assert reading.empty_rule == seam.EXECUTIVE_OVERVIEW.empty_rule


def test_a_non_empty_projection_reports_no_empty_rule() -> None:
    """`FR-163` -- the rule qualifies an absence and must not qualify a figure."""
    actions, _ = _actions(_projection((("revenue", "700.00", "complete", ()),)))
    reading = overview.read_overview(actions, _request())
    assert reading.empty_rule is None


def test_a_row_of_the_wrong_width_raises_rather_than_truncating() -> None:
    """Layout is `strict=True`: a silent truncation would drop a governed field."""
    actions, _ = _actions(_projection((("revenue", "700.00"),)))
    with pytest.raises(ValueError):
        overview.read_overview(actions, _request())
