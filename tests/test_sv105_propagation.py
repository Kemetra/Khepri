"""`SV1-05` — exact projected values, propagation completeness, stated emptiness.

Authority: active `RRA-014` `FR-139` (projected values and versions equal the
source records), `FR-140` (every refusal, caveat, qualifier, evidence value and
governed evidence absence survives), `FR-142` (an admitted empty result follows
the definition's own rule and never widens), and `FR-138`'s prohibition.

Two disciplines the plan names for this slice.

**Coverage is asserted against the governing declaration, never against a second
projection.** Two projections compared with each other agree when a qualifier is
missing from both -- `C1-04`'s fix was importing causes from the source module
rather than retyping them, and the caveat assertions below import
`definitions.CAVEAT_CODES` for the same reason.

**The arithmetic scan must be able to fail.** A scan scoped to a hand-written
module list reproduces the drift it exists to catch, and a scan over an empty
glob passes trivially. It walks the whole package and asserts it saw files.
"""

from __future__ import annotations

import ast
import pathlib
from decimal import Decimal

import pytest

from khepri.rra import definitions
from khepri.rra.bundle import (
    NARRATIVE_OMITTED,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    BundleIdentity,
    CitedEvidence,
    CitedFigure,
    ReportBundle,
    Section,
    StatedCaveat,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.semantic_views import compatibility, contracts, projection, refusals, registry

#: Every operator and builtin `FR-138` bars from a projection path.
_ARITHMETIC_OPERATORS = (
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.MatMult,
)
_BANNED_CALLS = ("sum", "round", "min", "max", "abs")

_OVERVIEW = registry.define_view("ExecutiveOverviewView")
_BRANCH = registry.define_view("BranchPerformanceView")

#: A scale a re-rounding projection would destroy. `Decimal("500.50")` and
#: `Decimal("500.5")` are `==`, so equality alone cannot catch a quantize --
#: the scale is what does.
_EXACT = Decimal("500.50")


def _identity() -> BundleIdentity:
    """Provenance with every version the projection must carry back."""
    return BundleIdentity(
        package_version="rra004.package.v1",
        formula_version="rra004.formula.v1",
        mapping_version="rra004.mapping.v1",
        narrative_version="rra005.narrative.v1",
        profile_digest="0" * 64,
        source_sha256_hex="1" * 64,
        monetary_precision=2,
        row_count=3,
    )


def _figure(metric: str, value: Decimal | None, label: str | None = None) -> CitedFigure:
    """One cited figure carrying an exact `Decimal` and no section placement."""
    return CitedFigure(
        figure_id=f"fig_{metric}_{label or 'none'}",
        citation_id=f"cit_{metric}",
        fact_id="fct_000000000000000000000000",
        metric=metric,
        unit_kind="monetary",
        kind="value",
        section="overview",
        label=label,
        value=value,
        renderings={LANGUAGE_ENGLISH: "500.50", LANGUAGE_ARABIC: "٥٠٠٫٥٠"},
    )


def _evidence(citation_id: str, *, complete: bool) -> CitedEvidence:
    """A cited evidence record, either fully stated or stating its absences."""
    if complete:
        return CitedEvidence(
            citation_id=citation_id,
            metric="revenue",
            unit_kind="monetary",
            formula_version="rra004.formula.v1",
            precision=2,
            inputs=("fct_a",),
            provenance=(("subject", "v1"),),
        )
    return CitedEvidence(
        citation_id=citation_id,
        metric="revenue",
        unit_kind="monetary",
        formula_version="rra004.formula.v1",
        precision=None,
        inputs=None,
        provenance=None,
    )


def _bundle(
    figures: tuple[CitedFigure, ...],
    caveats: tuple[StatedCaveat, ...] = (),
    evidence: tuple[CitedEvidence, ...] = (),
) -> ReportBundle:
    """A single-population bundle carrying exactly what a test needs.

    The overview section indexes every figure, because `ReportBundle` refuses a
    bundle whose sections and figures disagree about placement. Derived from the
    figures rather than supplied beside them, so a test can vary the figures
    without also maintaining the index.
    """
    return ReportBundle(
        identity=_identity(),
        figures=figures,
        caveats=caveats,
        narrative_state=NARRATIVE_OMITTED,
        sections=(
            Section(
                section_id=SECTION_OVERVIEW,
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(figure.figure_id for figure in figures),
                chart=None,
            ),
        ),
        evidence=evidence,
    )


def _request(definition: contracts.SemanticViewDefinition, **overrides: object):
    """A request valid for `definition`, so a test can vary one field."""
    fields: dict[str, object] = {
        "view_id": definition.view_id,
        "view_version": definition.view_version,
        "metrics": (),
        "dimensions": (),
        "filters": (),
    }
    return compatibility.SemanticViewRequest(**(fields | overrides))  # type: ignore[arg-type]


def test_a_projected_value_is_the_source_decimal_scale_and_all() -> None:
    """`FR-139` -- equal, same type, same scale. A quantize anywhere fails here.

    Equality alone would not catch a re-rounding: `Decimal("500.50")` equals
    `Decimal("500.5")`. The scale is what a quantize destroys, so the scale is
    what is asserted.
    """
    figure = _figure("revenue", _EXACT)
    outcome = projection.project(_request(_OVERVIEW), (_bundle((figure,)),))

    assert outcome.admitted
    assert outcome.projection is not None
    row = outcome.projection.rows[0]
    value = row[outcome.projection.fields.index("value")]

    assert value == figure.value
    assert value is figure.value, "the source object itself must reach the row"
    assert isinstance(value, Decimal)
    assert value.as_tuple().exponent == _EXACT.as_tuple().exponent


def test_every_governed_version_is_carried_back_from_the_source() -> None:
    """`FR-139` -- versions equal the source records, never recomputed."""
    bundle = _bundle((_figure("revenue", _EXACT),))
    outcome = projection.project(_request(_OVERVIEW), (bundle,))

    assert outcome.projection is not None
    versions = outcome.projection.versions
    assert versions["package"] == bundle.identity.package_version
    assert versions["formula"] == bundle.identity.formula_version
    assert versions["mapping"] == bundle.identity.mapping_version
    assert versions["bundle"] == bundle.bundle_version
    assert versions["view"] == _OVERVIEW.view_version


def test_every_source_caveat_survives_projection() -> None:
    """`FR-140` -- none may be suppressed.

    The codes are checked against `definitions.CAVEAT_CODES`, the governing
    declaration, rather than against a second projection: two projections agree
    when a caveat is missing from both, which is `C1-04`'s failure exactly.
    """
    codes = tuple(sorted(definitions.CAVEAT_CODES))
    assert codes, "the governing declaration must not be empty"
    stated = tuple(StatedCaveat(code=code, section=None) for code in codes)
    outcome = projection.project(
        _request(_OVERVIEW), (_bundle((_figure("revenue", _EXACT),), caveats=stated),)
    )

    assert outcome.projection is not None
    assert outcome.projection.caveats == stated
    assert {caveat.code for caveat in outcome.projection.caveats} == set(codes)


def test_a_governed_evidence_absence_survives_as_an_absence() -> None:
    """`FR-140` -- an absence is never converted into an ordinary value.

    Two things are asserted, because either alone is weak: the `None` reaches the
    result as `None`, *and* the absence is named. A missing key and "the record
    says there is none" are different answers and must look different.
    """
    absent = _evidence("cit_revenue", complete=False)
    outcome = projection.project(
        _request(_OVERVIEW),
        (_bundle((_figure("revenue", _EXACT),), evidence=(absent,)),),
    )

    assert outcome.projection is not None
    carried = outcome.projection.evidence[0]
    assert carried.precision is None
    assert carried.inputs is None
    assert carried.provenance is None
    assert set(outcome.projection.evidence_absences) == {
        ("cit_revenue", projection.ABSENCE_PRECISION),
        ("cit_revenue", projection.ABSENCE_INPUTS),
        ("cit_revenue", projection.ABSENCE_PROVENANCE),
    }


def test_a_stated_evidence_value_is_named_in_no_absence() -> None:
    """The absence list must not be a blanket one, or it says nothing."""
    outcome = projection.project(
        _request(_OVERVIEW),
        (
            _bundle(
                (_figure("revenue", _EXACT),), evidence=(_evidence("cit_revenue", complete=True),)
            ),
        ),
    )

    assert outcome.projection is not None
    assert outcome.projection.evidence_absences == ()


def test_a_field_the_source_does_not_state_is_an_absence_not_a_dropped_column() -> None:
    """`FR-140` and `FR-134` together.

    `ExecutiveOverviewView` publishes a `population` column and
    `RenderableBundle` carries no population qualifier at all. The column stays
    in the published order and its value is `None`: dropping it would change the
    view's output order, which is part of its identity.
    """
    outcome = projection.project(_request(_OVERVIEW), (_bundle((_figure("revenue", _EXACT),)),))

    assert outcome.projection is not None
    assert outcome.projection.fields == _OVERVIEW.output_field_order
    assert "population" in outcome.projection.fields
    assert outcome.projection.rows[0][outcome.projection.fields.index("population")] is None
    assert outcome.projection.population_qualifiers == ()


def test_rows_follow_the_published_output_field_order() -> None:
    """`FR-134` -- output order is part of view identity, so it is read not sorted."""
    outcome = projection.project(_request(_OVERVIEW), (_bundle((_figure("revenue", _EXACT),)),))

    assert outcome.projection is not None
    assert outcome.projection.fields == _OVERVIEW.output_field_order
    assert len(outcome.projection.rows[0]) == len(_OVERVIEW.output_field_order)


def test_an_empty_result_states_the_definitions_own_rule_and_does_not_widen() -> None:
    """`FR-142` -- the whole of it, in one case.

    The same request with its filter removed must return a *different, non-empty*
    result. Without that half, a projection that silently dropped the filter
    would pass: both runs would be non-empty and the empty case would never
    arise.
    """
    bundle = _bundle((_figure("revenue_by_store", _EXACT, label="riyadh-01"),))
    filtered = _request(_BRANCH, filters=(("store", "no-such-branch"),))
    unfiltered = _request(_BRANCH)

    empty = projection.project(filtered, (bundle,))
    widened = projection.project(unfiltered, (bundle,))

    assert empty.projection is not None and widened.projection is not None
    assert empty.projection.is_empty is True
    assert empty.projection.rows == ()
    assert empty.projection.empty_rule == _BRANCH.empty_result_rule
    assert widened.projection.is_empty is False
    assert widened.projection.rows != empty.projection.rows


def test_an_empty_result_still_carries_its_versions_and_caveats() -> None:
    """`FR-140` does not pause because the result is empty."""
    stated = (StatedCaveat(code=sorted(definitions.CAVEAT_CODES)[0], section=None),)
    bundle = _bundle((_figure("revenue_by_store", _EXACT, label="riyadh-01"),), caveats=stated)
    outcome = projection.project(
        _request(_BRANCH, filters=(("store", "no-such-branch"),)), (bundle,)
    )

    assert outcome.projection is not None
    assert outcome.projection.is_empty is True
    assert outcome.projection.caveats == stated
    assert outcome.projection.versions["view"] == _BRANCH.view_version


def test_an_incompatible_request_refuses_before_any_projection() -> None:
    """`FR-137`/`FR-141` -- the refusal carries no projection at all."""
    outcome = projection.project(
        _request(_OVERVIEW, metrics=("no_such_metric",)), (_bundle((_figure("revenue", _EXACT),)),)
    )

    assert outcome.refused
    assert outcome.projection is None
    assert outcome.refusal is not None
    assert outcome.refusal.cause == refusals.CAUSE_UNKNOWN_METRIC


def test_an_unknown_view_refuses_rather_than_raising() -> None:
    """The registry raises `UnknownView`; the port answers a governed refusal."""
    request = compatibility.SemanticViewRequest(view_id="NoSuchView", view_version="v1")
    outcome = projection.project(request, (_bundle((_figure("revenue", _EXACT),)),))

    assert outcome.refused
    assert outcome.refusal is not None
    assert outcome.refusal.cause == refusals.CAUSE_UNKNOWN_VIEW


@pytest.mark.parametrize("sources", [(), ("not-a-bundle",), ("a", "b")])
def test_a_source_that_is_not_one_governed_bundle_refuses(sources: tuple[object, ...]) -> None:
    """`FR-136` fails closed: no source, a foreign object, or more than one."""
    outcome = projection.project(_request(_OVERVIEW), sources)

    assert outcome.refused
    assert outcome.refusal is not None
    assert outcome.refusal.cause == refusals.CAUSE_INCOMPATIBLE_SOURCE_SHAPE


def test_the_effective_request_states_every_dimension_and_filter() -> None:
    """`FR-137` -- requested and definition-fixed alike, visible in the result."""
    request = _request(_BRANCH, filters=(("store", "riyadh-01"),))
    outcome = projection.project(
        request, (_bundle((_figure("revenue_by_store", _EXACT, label="riyadh-01"),)),)
    )

    assert outcome.effective is not None
    assert outcome.effective.requested_filters == request.filters
    assert outcome.effective.fixed_filters == _BRANCH.fixed_filters
    assert outcome.effective.dimensions == _BRANCH.dimension_allowlist


def _package_sources() -> tuple[pathlib.Path, ...]:
    """Every module in the semantic-views package, found rather than listed."""
    package = pathlib.Path(projection.__file__).parent
    return tuple(sorted(package.glob("*.py")))


def test_no_module_in_the_package_performs_arithmetic() -> None:
    """`FR-138` -- no arithmetic, aggregation, ranking, top-N or thresholding.

    Walked over the whole package rather than a named module list: a scan scoped
    to a list reproduces the drift it exists to catch. The file count is asserted
    because a scan over an empty glob passes while proving nothing.
    """
    sources = _package_sources()
    assert len(sources) >= 5, f"the scan found too few files to be scanning anything: {sources}"

    offenders: list[str] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            offenders += _arithmetic_in(node, path.name)
    assert offenders == [], f"the package computes: {offenders}"


def _arithmetic_in(node: ast.AST, filename: str) -> list[str]:
    """Any arithmetic, banned builtin, ranking key or slice on one node."""
    return (
        _binary_operator(node, filename)
        + _banned_call(node, filename)
        + _ranking_or_slice(node, filename)
    )


def _binary_operator(node: ast.AST, filename: str) -> list[str]:
    """`a + b` and its siblings, which no projection may perform."""
    if not isinstance(node, ast.BinOp):
        return []
    if not isinstance(node.op, _ARITHMETIC_OPERATORS):
        return []
    return [f"{filename}:{node.lineno}: {type(node.op).__name__}"]


def _banned_call(node: ast.AST, filename: str) -> list[str]:
    """`sum`, `round` and the other aggregating builtins."""
    if not isinstance(node, ast.Call):
        return []
    if not isinstance(node.func, ast.Name):
        return []
    if node.func.id not in _BANNED_CALLS:
        return []
    return [f"{filename}:{node.lineno}: {node.func.id}()"]


def _ranking_or_slice(node: ast.AST, filename: str) -> list[str]:
    """`sorted(key=...)`, which ranks, and a slice, which can implement top-N."""
    if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
        return [f"{filename}:{node.lineno}: slice"]
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        return []
    if node.func.id != "sorted":
        return []
    return [f"{filename}:{node.lineno}: sorted(key=)" for kw in node.keywords if kw.arg == "key"]
