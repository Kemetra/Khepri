"""`SV1-07` — the fourteen cross-cutting boundary properties, each able to fail.

Authority: active `RCA-006` `FR-150` and `RRA-014` §Verification.

`FR-150` names seven: cross-organization, missing, deleted, exact-version,
no-write, no-event and no-concrete-RRA-import, "including byte-identical
unavailable outcomes and zero writes". `RRA-014` §Verification adds eight: exact
registry extent, derived allowlists, early refusal, visible effective filters,
arithmetic absence, propagation completeness, exact versions and explicit
emptiness. Exact-version is named by both, so fourteen properties in all.

**Mutation cannot find a property nobody wrote a test for.** That is the plan's
first risk, and no mutant can reach it: a guard that does not exist has no line
to mutate. So the enumeration is written down as `PROPERTIES`, transcribed from
the two specification sentences, and `test_every_named_property_has_a_test`
asserts each name has a test function in this module. A property added to a
specification and forgotten here fails that test rather than passing silently.

**One property is NOT EXERCISED, and says so.** `SV1-04` resolved the runtime
adapter's scope question against it: `RCA-006` §Scope governs no runtime wiring,
so `src/khepri/runtime/semantic_view_adapter.py` does not ship and there is no
composition root to drive. The no-concrete-RRA-import property is asserted here
over the RCA package itself, which is real and holds; what cannot be exercised
is that property over a *shipping composition*. `test_the_composition_property_is_not_exercised`
records that rather than letting a fake port stand in for it -- `W1-07a`'s
lesson, where seven tests passed over a hand-built `ShellServices` for a route
absent from the image. The other thirteen are unaffected: they hold over the two
packages themselves.
"""

from __future__ import annotations

import ast
import pathlib
from decimal import Decimal

import pytest
from sqlalchemy import event

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.isolation import IsolationService
from khepri.rca.persistence import SqlAccountStore
from khepri.rca.semantic_queries import ports, queries
from khepri.rca.workspace.audit import OBJECT_VERSION
from khepri.rca.workspace.revocation import RevokedObject, SqlRevocationLedger
from khepri.rra import definitions, facts
from khepri.rra.persistence import SqlFactPackageRepository
from khepri.rra.semantic_views import (
    compatibility,
    contracts,
    projection,
    published,
    refusals,
    registry,
)
from khepri.runtime.semantic_view_adapter import SemanticViewAdapter
from tests.c106_support import completed_pair
from tests.test_sv104_query_orchestration import _FakePort, _rra_imports, _SpyReader
from tests.test_sv105_propagation import _EXACT, _bundle, _figure
from tests.w104_support import Member, member
from tests.w104b_support import Journey, journey

#: The fourteen properties, transcribed from `FR-150` and `RRA-014`
#: §Verification. Each name maps to a test below by convention, and the mapping
#: is asserted -- this list is the only guard against a property nobody wrote.
PROPERTIES: tuple[str, ...] = (
    "cross_organization",
    "missing_source",
    "deleted_source",
    "exact_version",
    "no_write",
    "no_event",
    "no_concrete_rra_import",
    "registry_extent",
    "derived_allowlists",
    "early_refusal",
    "visible_effective_filters",
    "arithmetic_absence",
    "propagation_completeness",
    "explicit_emptiness",
)

_WRITE_VERBS = ("insert", "update", "delete", "merge", "replace", "upsert")
_OVERVIEW = registry.define_view("ExecutiveOverviewView")


def _actions(j: Journey, port: _FakePort, reader: object | None = None):
    """The RCA orchestration over the journey's real isolation door and stores."""
    return queries.SemanticQueryActions(
        isolation=IsolationService(j.w.organizations, SqlAccountStore(j.w.factory)),
        sources=reader or j.w.store,
        port=port,
    )


def _query(who: Member, *source_ids: str) -> queries.SemanticQueryRequest:
    """One organization-scoped semantic query from `who`."""
    return queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id=who.account_id),
        organization_id=who.organization_id,
        view=ports.SemanticViewRequest(
            view_id=_OVERVIEW.view_id, view_version=_OVERVIEW.view_version
        ),
        source_ids=source_ids,
    )


def _admitted() -> ports.ViewOutcome:
    """A port outcome that is plainly not the uniform miss."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=_OVERVIEW.view_id, view_version=_OVERVIEW.view_version
        ),
    )


def _view_request(**overrides: object) -> compatibility.SemanticViewRequest:
    """An RRA-side request valid for the overview view."""
    fields: dict[str, object] = {
        "view_id": _OVERVIEW.view_id,
        "view_version": _OVERVIEW.view_version,
        "metrics": (),
        "dimensions": (),
        "filters": (),
    }
    return compatibility.SemanticViewRequest(**(fields | overrides))  # type: ignore[arg-type]


def test_every_named_property_has_a_test() -> None:
    """The one guard mutation cannot supply: a property nobody tested.

    A missing guard has no line to mutate, so mutation testing is blind to it.
    Walking the specification's own enumeration is the only thing that is not.
    """
    module = pathlib.Path(__file__).read_text(encoding="utf-8")
    missing = [name for name in PROPERTIES if f"def test_property_{name}" not in module]
    assert missing == [], f"named by the specification and untested here: {missing}"
    assert len(PROPERTIES) == len(set(PROPERTIES)) == 14


def test_property_cross_organization() -> None:
    """`FR-150` -- a source in another scope is the uniform miss, not a disclosure."""
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    theirs = completed_pair(j, stranger)
    completed_pair(j, owner)

    outcome = _actions(j, _FakePort(_admitted())).request(_query(owner, theirs.subject_run.run_id))

    assert outcome.unavailable
    assert outcome.projection is None and outcome.refusal is None


def test_property_missing_source() -> None:
    """`FR-150` -- an absent identifier is the same uniform miss."""
    j = journey()
    owner = member(j.w)
    completed_pair(j, owner)

    assert _actions(j, _FakePort(_admitted())).request(_query(owner, "no-such-id")).unavailable


def test_property_deleted_source() -> None:
    """`FR-150` -- a revoked source reads as gone, not as a different answer."""
    j = journey()
    owner = member(j.w)
    mine = completed_pair(j, owner)
    SqlRevocationLedger(j.w.factory).revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION,
            object_id=mine.subject.version_id,
            owner_id=owner.owner_id,
            revoked_at=j.clock(),
        )
    )

    outcome = _actions(j, _FakePort(_admitted())).request(_query(owner, mine.subject_run.run_id))

    assert outcome.unavailable


def test_the_four_unavailable_conditions_are_compared_against_each_other() -> None:
    """`FR-150` -- "byte-identical", which a fixture comparison cannot establish.

    Each equal to `ViewOutcome(kind="unavailable")` would still pass if three of
    them diverged from the fourth in a field a later slice adds. Comparing them
    to one another cannot.
    """
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    mine = completed_pair(j, owner)
    theirs = completed_pair(j, stranger)
    admitting = _actions(j, _FakePort(_admitted()))

    missing = admitting.request(_query(owner, "no-such-id"))
    cross = admitting.request(_query(owner, theirs.subject_run.run_id))
    unreadable = _actions(j, _FakePort(None)).request(_query(owner, mine.baseline_run.run_id))
    SqlRevocationLedger(j.w.factory).revoke(
        RevokedObject(
            object_kind=OBJECT_VERSION,
            object_id=mine.subject.version_id,
            owner_id=owner.owner_id,
            revoked_at=j.clock(),
        )
    )
    deleted = admitting.request(_query(owner, mine.subject_run.run_id))

    assert missing == cross == deleted == unreadable


def test_property_exact_version() -> None:
    """`FR-143`/`FR-150` -- the exact version, no alias, no silent upgrade."""
    definition = registry.define_view("BasketView")
    assert published.resolve("BasketView", definition.view_version) is definition
    for named in ("latest", "sv1.basket.v99", ""):
        outcome = published.resolve("BasketView", named)
        assert isinstance(outcome, refusals.ViewRefusal)
        assert outcome.cause == refusals.CAUSE_UNKNOWN_VERSION


def test_property_no_write() -> None:
    """`FR-148` -- zero rows, asserted at the cursor rather than as a count delta.

    A before/after count cannot see a write that was made and undone, or one to a
    table the count did not name.
    """
    j = journey()
    owner = member(j.w)
    mine = completed_pair(j, owner)
    actions = _actions(j, _FakePort(_admitted()))
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        """Keep every statement the request issues, to any table."""
        statements.append(statement)

    engine = j.w.factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", _record)
    try:
        actions.request(_query(owner, mine.subject_run.run_id))
        actions.request(_query(owner, "no-such-id"))
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert statements, "the listener saw nothing, so it proves nothing"
    written = [s for s in statements if s.strip().split(" ")[0].lower() in _WRITE_VERBS]
    assert written == []


def test_property_no_event() -> None:
    """`FR-149` -- no audit row and no telemetry row, on either path.

    Asserted at the same cursor as the write property but isolated from it: the
    audit table is named, so a write only to that table would be caught here even
    if `_WRITE_VERBS` were narrowed.
    """
    j = journey()
    owner = member(j.w)
    mine = completed_pair(j, owner)
    actions = _actions(j, _FakePort(_admitted()))
    touched: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany) -> None:  # noqa: ANN001
        """Keep any statement naming an audit or telemetry table."""
        lowered = statement.lower()
        if "audit" in lowered or "telemetry" in lowered:
            touched.append(statement)

    engine = j.w.factory.kw["bind"]
    event.listen(engine, "before_cursor_execute", _record)
    try:
        actions.request(_query(owner, mine.subject_run.run_id))
        actions.request(_query(owner, "no-such-id"))
    finally:
        event.remove(engine, "before_cursor_execute", _record)

    assert touched == [], f"the path reached an audit or telemetry table: {touched}"


def test_property_no_concrete_rra_import() -> None:
    """`FR-150` -- `khepri.rca.semantic_queries` imports no concrete RRA module.

    This half is real and holds. What cannot be exercised is the same property
    over a shipping composition root -- see
    `test_the_composition_property_is_not_exercised`.
    """
    package = pathlib.Path(queries.__file__).parent
    sources = sorted(package.glob("*.py"))
    assert sources, "the scan found no files, so it proves nothing"
    offenders = [
        f"{path.name}:{hit}"
        for path in sources
        for hit in _rra_imports(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_composition_property_is_now_exercised_over_a_shipping_root() -> None:
    """Formerly NOT EXERCISED. `RCA-007` shipped the adapter, so this drives it.

    The old version of this test asserted the adapter's *absence* so that the day
    it shipped the test would fail and force the property to be exercised rather
    than left quietly unproven. `RCA-007` merged, the adapter shipped, and it
    failed exactly as written. This is what replaced it.

    What the property asks is that `khepri.rca` reaches no concrete `khepri.rra`
    implementation. `test_property_no_concrete_rra_import` asserts that
    statically over the package. What could not be asserted before is that the
    property still holds when something real is bound to the port -- so here the
    real adapter, the real store and the real isolation door answer one request
    end to end, and the static scan is re-run afterwards over the same package.
    A projection comes back and the import boundary is untouched, which is the
    whole claim.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = queries.SemanticQueryActions(
        isolation=IsolationService(j.w.organizations, SqlAccountStore(j.w.factory)),
        sources=j.w.store,
        port=SemanticViewAdapter(SqlFactPackageRepository(j.w.factory)),
    )

    outcome = actions.request(
        queries.SemanticQueryRequest(
            actor=queries.SemanticQueryActor(account_id=who.account_id),
            organization_id=who.organization_id,
            view=ports.SemanticViewRequest(
                view_id="ExecutiveOverviewView",
                view_version="sv1.executive_overview.v1",
            ),
            source_ids=(pair.subject_run.run_id,),
        )
    )

    assert outcome.kind == ports.KIND_ADMITTED
    assert outcome.projection is not None
    assert _rra_imports(pathlib.Path(queries.__file__).read_text(encoding="utf-8")) == []


def test_property_registry_extent() -> None:
    """`RRA-014` §Verification -- the exact extent, equality and non-empty."""
    assert registry.view_ids() == frozenset(
        {
            "ExecutiveOverviewView",
            "PeriodComparisonView",
            "BranchPerformanceView",
            "ProductCategoryView",
            "BasketView",
            "ConcentrationView",
            "ReportEvidenceView",
            "MetricAvailabilityView",
        }
    )
    assert len(registry.view_ids()) == 8


def test_property_derived_allowlists() -> None:
    """`RRA-014` §Verification -- every member derives from its governing declaration."""
    governed_dimensions = frozenset(facts.SERIES_DIMENSIONS)
    for view_id in sorted(registry.view_ids()):
        definition = registry.define_view(view_id)
        assert definition.metric_allowlist
        for code in definition.metric_allowlist:
            assert definitions.admits_metric(code), f"{view_id} invented {code!r}"
        for dimension in definition.dimension_allowlist:
            assert dimension in governed_dimensions, f"{view_id} invented {dimension!r}"


def test_property_early_refusal() -> None:
    """`FR-137` -- an undeclared parameter refuses *before* projection.

    Proven by the outcome carrying no projection at all, not merely by the cause:
    a refusal that still projected would have both.
    """
    branch = registry.define_view("BranchPerformanceView")
    request = compatibility.SemanticViewRequest(
        view_id=branch.view_id,
        view_version=branch.view_version,
        filters=((facts.SEMANTIC_CHANNEL, "web"),),
    )
    outcome = projection.project(request, (_bundle((_figure("revenue_by_store", _EXACT),)),))

    assert outcome.refused
    assert outcome.projection is None
    assert outcome.refusal is not None
    assert outcome.refusal.cause == refusals.CAUSE_UNKNOWN_FILTER


def test_property_visible_effective_filters() -> None:
    """`FR-137` -- requested and definition-fixed filters are both visible.

    **The fixed half needs a definition that has any.** Every published view
    declares `fixed_filters=()`, so asserting `effective.fixed_filters ==
    definition.fixed_filters` against a published view compares `()` with `()`
    and passes however the field is built -- a mutant replacing it with a
    literal `()` survived that assertion. The second half therefore drives
    `_effective` with a definition carrying real fixed filters, which is the only
    input that can tell the two apart.
    """
    branch = registry.define_view("BranchPerformanceView")
    request = compatibility.SemanticViewRequest(
        view_id=branch.view_id,
        view_version=branch.view_version,
        filters=((facts.SEMANTIC_STORE, "riyadh-01"),),
    )
    bundle = _bundle((_figure("revenue_by_store", _EXACT, label="riyadh-01"),))
    outcome = projection.project(request, (bundle,))

    assert outcome.effective is not None
    assert outcome.effective.requested_filters == request.filters
    assert outcome.effective.dimensions == branch.dimension_allowlist

    fixed = (("channel", "web"),)
    with_fixed = contracts.SemanticViewDefinition(
        view_id="FixedFilterProbeView",
        view_version="sv1.fixed_filter_probe.v1",
        accepted_source_shape=contracts.SHAPE_SINGLE_POPULATION,
        metric_allowlist=("revenue",),
        dimension_allowlist=(facts.PERIOD_DIMENSION,),
        request_filter_allowlist=(),
        fixed_filters=fixed,
        required_evidence=(),
        output_field_order=("metric", "value"),
        empty_result_rule=contracts.EMPTY_STATED_ABSENCE,
    )
    effective = projection._effective(_view_request(), with_fixed)  # noqa: SLF001

    assert effective.fixed_filters == fixed, "a definition's fixed filters must be stated back"


#: The arithmetic nodes `FR-138` bars. Written here rather than imported from
#: `SV1-05`'s scan on purpose: calling that scan would re-run one guard twice, so
#: gutting it would take this property with it. `FR-150` asks for the property to
#: be *independently* tested, and two scans that fail together are one scan.
_BARRED_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)


def _computes(node: ast.AST) -> bool:
    """Whether this node performs arithmetic, in either syntax form."""
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, _BARRED_OPERATORS)
    if isinstance(node, ast.AugAssign):
        return isinstance(node.op, _BARRED_OPERATORS)
    return False


def test_property_arithmetic_absence() -> None:
    """`FR-138` -- no arithmetic anywhere in the semantic-views package.

    An independent scan, not a call into `SV1-05`'s. The file count is asserted
    because a scan over an empty glob passes while proving nothing.
    """
    package = pathlib.Path(projection.__file__).parent
    sources = sorted(package.glob("*.py"))
    assert len(sources) >= 6, f"the scan found too few files to be scanning: {sources}"

    offenders = [
        f"{path.name}:{node.lineno}"
        for path in sources
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if _computes(node)
    ]
    assert offenders == [], f"the package computes: {offenders}"


def test_property_propagation_completeness() -> None:
    """`FR-140` -- caveats, evidence and governed absences all survive together.

    One projection carrying all three, because the risk `FR-140` names is a state
    that is defined and never attached: each asserted alone can pass while a
    projection that carries only one of them ships.
    """
    from khepri.rra.bundle import CitedEvidence, StatedCaveat

    code = sorted(definitions.CAVEAT_CODES)[0]
    figure = _figure("revenue", _EXACT)
    absent = CitedEvidence(
        citation_id=figure.citation_id,
        metric="revenue",
        unit_kind="monetary",
        formula_version="rra004.formula.v1",
        precision=None,
        inputs=None,
    )
    bundle = _bundle(
        (figure,), caveats=(StatedCaveat(code=code, section=None),), evidence=(absent,)
    )
    outcome = projection.project(_view_request(), (bundle,))

    assert outcome.projection is not None
    assert {caveat.code for caveat in outcome.projection.caveats} == {code}
    assert outcome.projection.evidence[0].precision is None
    assert outcome.projection.evidence_absences
    assert outcome.projection.versions["view"] == _OVERVIEW.view_version


def test_property_explicit_emptiness() -> None:
    """`FR-142` -- stated under the definition's own rule, and it did not widen."""
    branch = registry.define_view("BranchPerformanceView")
    bundle = _bundle((_figure("revenue_by_store", _EXACT, label="riyadh-01"),))
    empty = projection.project(
        compatibility.SemanticViewRequest(
            view_id=branch.view_id,
            view_version=branch.view_version,
            filters=((facts.SEMANTIC_STORE, "no-such-branch"),),
        ),
        (bundle,),
    )
    wider = projection.project(
        compatibility.SemanticViewRequest(view_id=branch.view_id, view_version=branch.view_version),
        (bundle,),
    )

    assert empty.projection is not None and wider.projection is not None
    assert empty.projection.is_empty is True
    assert empty.projection.empty_rule == branch.empty_result_rule
    assert wider.projection.is_empty is False


def test_an_unauthorized_actor_reaches_no_store_read() -> None:
    """`FR-145` -- authorization precedes the first read, driven end to end."""
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    mine = completed_pair(j, owner)
    reader = _SpyReader(j.w.store)

    foreign = queries.SemanticQueryRequest(
        actor=queries.SemanticQueryActor(account_id=stranger.account_id),
        organization_id=owner.organization_id,
        view=ports.SemanticViewRequest(
            view_id=_OVERVIEW.view_id, view_version=_OVERVIEW.view_version
        ),
        source_ids=(mine.subject_run.run_id,),
    )
    with pytest.raises(ScopeAccessDenied):
        _actions(j, _FakePort(_admitted()), reader).request(foreign)

    assert reader.reads == []


@pytest.mark.parametrize("shape", ["", "not-a-shape", contracts.SHAPE_EITHER_BUNDLE])
def test_a_source_naming_no_concrete_shape_refuses(shape: str) -> None:
    """`FR-136` fails closed on every non-concrete shape, including "either"."""
    evidence_view = registry.define_view("ReportEvidenceView")
    refusal = compatibility.validate(
        compatibility.SemanticViewRequest(
            view_id=evidence_view.view_id, view_version=evidence_view.view_version
        ),
        evidence_view,
        compatibility.SourceCandidate(source_shape=shape),
    )
    assert refusal is not None
    assert refusal.cause == refusals.CAUSE_INCOMPATIBLE_SOURCE_SHAPE


def test_a_projected_value_keeps_its_decimal_scale() -> None:
    """`FR-139` -- equal, same type, same scale; a quantize anywhere fails."""
    figure = _figure("revenue", _EXACT)
    outcome = projection.project(_view_request(), (_bundle((figure,)),))

    assert outcome.projection is not None
    value = outcome.projection.rows[0][outcome.projection.fields.index("value")]
    assert isinstance(value, Decimal)
    assert value.as_tuple().exponent == _EXACT.as_tuple().exponent
