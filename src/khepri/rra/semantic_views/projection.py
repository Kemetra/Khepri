"""Selecting, ordering and propagating governed facts (`SV1-05`).

`RRA-014` `FR-139`, `FR-140`, `FR-142`, and `FR-138`'s prohibition.

**This module computes nothing.** `FR-138` bars "arithmetic, aggregation,
grouping into a new fact, ranking, scoring, normalization, top-N, thresholding,
or raw-row access", and the shape here is built so that reading the code shows
it: every output field is produced by a reader in `_FIELD_READERS` that performs
one attribute access and returns what it found. There is no operator, no `sum`,
no `round`, no `sorted(key=...)` and no slice in the projection path, and
`tests/test_sv105_propagation.py` scans the package to keep it that way.

**A value is the source's own object, not a copy of its digits.**
`CitedFigure.value` is a `Decimal` and reaches the row as that same `Decimal`.
`FR-139` requires projected values "equal the source records" with "no
re-rounding": quantizing to a precision this module chose would produce a number
no governed record states, and `2.50` and `2.5` are equal numbers whose
`Decimal` scale a reader can see.

**An absence is an answer.** `FR-140` keeps "governed evidence absence" intact
"rather than converting it to an ordinary value", and `CitedEvidence` already
models it: `precision`, `inputs` and `provenance` are `None` when no retained
record states them. Those `None`s travel unchanged and are additionally named in
`ViewProjection.evidence_absences`, so a reader can tell "the record says there
is none" from "this projection dropped the key".

**Two things this module cannot state, recorded rather than improvised.**

`RenderableBundle` -- the shape `FR-136` admits -- exposes `identity`, `figures`,
`caveats`, `narrative_state`, `sections`, `narrative` and `evidence`, and no
population qualifier. Population codes live on `FactPackage` and `Fact`, which no
governed member of the bundle surfaces. Several published views nonetheless name
`population` in their `output_field_order`. That field therefore projects as an
absence, which is the honest answer and the one `FR-140` prescribes: the source
states no population here, so the projection says so rather than inventing one
or silently dropping the column. `ViewProjection.population_qualifiers` is empty
for the same reason. Widening `RenderableBundle`, or reaching past it to the
package, is an `RRA-006`/`RRA-014` question and not a slice's to decide.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from khepri.rra.bundle import CitedEvidence, CitedFigure, StatedCaveat
from khepri.rra.renderable import RenderableBundle
from khepri.rra.semantic_views.compatibility import (
    SemanticViewRequest,
    SourceCandidate,
    validate,
)
from khepri.rra.semantic_views.contracts import (
    SHAPE_SINGLE_POPULATION,
    SHAPE_TWO_POPULATION,
    SemanticViewDefinition,
)
from khepri.rra.semantic_views.refusals import CAUSE_UNKNOWN_VIEW, ViewRefusal
from khepri.rra.semantic_views.registry import UnknownView, define_view

__all__ = [
    "KIND_ADMITTED",
    "KIND_REFUSED",
    "ABSENCE_INPUTS",
    "ABSENCE_PRECISION",
    "ABSENCE_PROVENANCE",
    "EffectiveRequest",
    "ViewOutcome",
    "ViewProjection",
    "project",
]

#: The outcome kinds this module can produce. There is no `unavailable` here:
#: `FR-146`'s uniform miss is the RCA half's, built in one place there, and a
#: projection that could produce it would be a second place.
KIND_ADMITTED = "admitted"
KIND_REFUSED = "refused"

#: The governed absences `CitedEvidence` models, named so a result can state
#: which one it carries. `RRA-013`: `None` means "no retained record states
#: this", never a lookup that failed.
ABSENCE_PRECISION = "precision"
ABSENCE_INPUTS = "inputs"
ABSENCE_PROVENANCE = "provenance"

#: The source shape a bundle is, by the identity it carries. `CrossVersionBundle`
#: names two populations; `ReportBundle` one. Read from the bundle's own
#: `bundle_version` rather than by `isinstance`, so a bundle satisfying
#: `RenderableBundle` from another module is classified by what it declares.
_TWO_POPULATION_MARKER = "crossversion"


@dataclass(frozen=True, slots=True)
class EffectiveRequest:
    """`FR-137` -- what actually applied, requested and definition-fixed alike."""

    dimensions: tuple[str, ...] = ()
    requested_filters: tuple[tuple[str, str], ...] = ()
    fixed_filters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ViewProjection:
    """`FR-139`/`FR-140` -- projected values plus everything that must survive.

    `version_pairs` is ordered pairs behind a `versions` property, for
    `ViewRefusal`'s reason: `frozen=True` freezes the reference and not a mapping
    behind it, and `FR-139` requires these equal the source records.
    """

    view_id: str
    view_version: str
    fields: tuple[str, ...] = ()
    rows: tuple[tuple[object, ...], ...] = ()
    version_pairs: tuple[tuple[str, str], ...] = ()
    caveats: tuple[StatedCaveat, ...] = ()
    population_qualifiers: tuple[str, ...] = ()
    evidence: tuple[CitedEvidence, ...] = ()
    evidence_absences: tuple[tuple[str, str], ...] = ()
    is_empty: bool = False
    empty_rule: str | None = None

    @property
    def versions(self) -> dict[str, str]:
        """Mapping, package, formula, narrative and bundle versions, as read."""
        return dict(self.version_pairs)


@dataclass(frozen=True, slots=True)
class ViewOutcome:
    """An admitted projection or a governed refusal, never both."""

    kind: str
    refusal: ViewRefusal | None = None
    projection: ViewProjection | None = None
    effective: EffectiveRequest | None = field(default=None)

    @property
    def admitted(self) -> bool:
        """A projection the reader may see."""
        return self.kind == KIND_ADMITTED

    @property
    def refused(self) -> bool:
        """A governed view refusal (`FR-141`), carrying no partial result."""
        return self.kind == KIND_REFUSED


#: The members `RenderableBundle` declares and this module reads. Checked before
#: a source is called a bundle at all: a `bundle_version` alone is not a bundle,
#: and classifying on it let an incomplete object past validation and into
#: `AttributeError` -- a crash where `Constitution V` requires a refusal.
_REQUIRED_MEMBERS = ("identity", "figures", "caveats", "evidence", "bundle_version")


def _shape_of(source: object) -> str:
    """Which concrete source shape this bundle is (`FR-136`).

    An object missing any member `RenderableBundle` declares, or carrying no
    version, answers a name no definition admits -- and the shape predicate
    refuses it. So an unrecognized source fails closed rather than being guessed
    at, and never reaches the projection to raise there.
    """
    if any(not hasattr(source, member) for member in _REQUIRED_MEMBERS):
        return "unrecognized_source"
    version = source.bundle_version  # type: ignore[attr-defined]
    if not isinstance(version, str) or not version:
        return "unrecognized_source"
    if _TWO_POPULATION_MARKER in version:
        return SHAPE_TWO_POPULATION
    return SHAPE_SINGLE_POPULATION


def _evidence_absences(evidence: tuple[CitedEvidence, ...]) -> tuple[tuple[str, str], ...]:
    """Every governed absence the cited evidence states, by citation.

    Named rather than inferred from a missing key: `FR-140` distinguishes "the
    record says there is none" from "this projection dropped it", and only a
    positive statement can carry that difference to a reader.
    """
    absences: list[tuple[str, str]] = []
    for record in evidence:
        absences.extend(_absences_of(record))
    return tuple(absences)


def _absences_of(record: CitedEvidence) -> list[tuple[str, str]]:
    """The absences one evidence record states, in a stable order."""
    stated = (
        (ABSENCE_PRECISION, record.precision),
        (ABSENCE_INPUTS, record.inputs),
        (ABSENCE_PROVENANCE, record.provenance),
    )
    return [(record.citation_id, name) for name, value in stated if value is None]


def _versions_of(
    bundle: RenderableBundle,
    definition: SemanticViewDefinition,
    figures: tuple[CitedFigure, ...],
) -> tuple[tuple[str, str], ...]:
    """Every governed version the result must carry (`FR-139`).

    Read off the bundle's own identity, never recomputed. The view version is the
    definition's, which is the one version the source does not know about.
    """
    identity = bundle.identity
    named = (
        ("package", getattr(identity, "package_version", None)),
        ("formula", getattr(identity, "formula_version", None)),
        ("mapping", getattr(identity, "mapping_version", None)),
        ("narrative", getattr(identity, "narrative_version", None)),
        ("bundle", bundle.bundle_version),
        ("view", definition.view_version),
    )
    stated = tuple((name, value) for name, value in named if isinstance(value, str))
    return (*stated, *_family_versions(bundle, figures))


def _family_versions(
    bundle: RenderableBundle, figures: tuple[CitedFigure, ...]
) -> tuple[tuple[str, str], ...]:
    """The analysis-family version behind each projected figure (`FR-139`).

    `FR-139` names *family* alongside mapping, package, formula, bundle and view,
    and `identity.formula_version` is the **package** formula -- the wrong answer
    for a derived figure, whose family version `CitedEvidence.formula_version`
    carries. Reading only the identity omitted the family entirely.

    Keyed by section rather than by one `family` entry, because a bundle spans
    several: one key would collapse comparison and growth into whichever was seen
    last, and a version silently overwritten is worse than one absent.
    """
    by_citation = {record.citation_id: record.formula_version for record in bundle.evidence}
    sections: dict[str, str] = {}
    for figure in figures:
        version = by_citation.get(figure.citation_id)
        if isinstance(version, str):
            sections.setdefault(f"family:{figure.section}", version)
    return tuple(sections.items())


def _metric(figure: CitedFigure, _bundle: RenderableBundle) -> object:
    """The figure's governed metric code."""
    return figure.metric


def _value(figure: CitedFigure, _bundle: RenderableBundle) -> object:
    """The figure's own `Decimal`, unrounded and unconverted (`FR-139`)."""
    return figure.value


def _label(figure: CitedFigure, _bundle: RenderableBundle) -> object:
    """The customer's own category name, or `None` where the figure has none."""
    return figure.label


def _figure_id(figure: CitedFigure, _bundle: RenderableBundle) -> object:
    """The identifier addressing this cell."""
    return figure.figure_id


def _citation(figure: CitedFigure, _bundle: RenderableBundle) -> object:
    """The identifier naming the fact the reader is pointed at."""
    return figure.citation_id


def _unstated(_figure: CitedFigure, _bundle: RenderableBundle) -> object:
    """A field no member of `RenderableBundle` states -- an absence, not a blank.

    `population` is the case that forced this. Several published views name it in
    `output_field_order`, and the bundle carries no population qualifier at all;
    `FR-140` says an absence survives as an absence, so the column is present and
    its value is `None` rather than the column being dropped or filled.
    """
    return None


#: How each published output field is read. One attribute access per field, so
#: `FR-138`'s prohibition is visible in the shape rather than only asserted: a
#: reader that computed something would stand out against every other row here.
#:
#: A field absent from this table is read by `_unstated`, which is deliberate
#: rather than a fallback: `output_field_order` is part of view identity
#: (`FR-134`) and a view may publish a column the admitted source shape does not
#: state, which is an absence to report and not a reason to refuse.
_FIELD_READERS: dict[str, Callable[[CitedFigure, RenderableBundle], object]] = {
    "metric": _metric,
    "value": _value,
    "label": _label,
    "member": _label,
    "store": _label,
    "dimension": _label,
    "figure": _figure_id,
    "evidence": _citation,
}


def _row(
    figure: CitedFigure, bundle: RenderableBundle, fields: tuple[str, ...]
) -> tuple[object, ...]:
    """One figure as one row, in the view's published field order (`FR-134`)."""
    return tuple(_FIELD_READERS.get(name, _unstated)(figure, bundle) for name in fields)


def _matches(figure: CitedFigure, filters: tuple[tuple[str, str], ...]) -> bool:
    """Whether this figure is inside every requested filter.

    A filter names a dimension and a member, and the only member a
    `RenderableBundle` states per figure is `CitedFigure.label`. So a filter
    matches when the figure carries that label. This is selection -- comparing
    two governed values -- and not a computation.

    Two filters naming different dimensions therefore match nothing, because one
    figure carries one label. That is a real limit of what the admitted source
    shape states, and it fails *closed*: the reader gets a stated empty result
    under the definition's own empty rule, never a widened one.
    """
    return all(figure.label == member for _dimension, member in filters)


def _admitted_figures(
    bundle: RenderableBundle,
    definition: SemanticViewDefinition,
    request: SemanticViewRequest,
) -> tuple[CitedFigure, ...]:
    """The figures this request asked for and this view admits, in source order.

    A request naming metrics gets those metrics and no others. Reading the
    allowlist unconditionally returned every measure the *view* admits, which is
    wider than what the reader asked for -- the widening this specification
    exists to prevent, arriving through the selector rather than through a
    dropped filter. `validate` has already refused any metric outside the
    allowlist, so an empty tuple is "the view's own selection" and never "none".

    Selection, never ranking: the order is the source's and no key reorders it,
    because `FR-138` bars ranking and `FR-134` makes output order part of view
    identity rather than something computed per request.
    """
    requested, filters = request.metrics, request.filters
    allowed = frozenset(requested or definition.metric_allowlist)
    return tuple(
        figure
        for figure in bundle.figures
        if figure.metric in allowed and _matches(figure, filters)
    )


def _resolve(view_id: str) -> SemanticViewDefinition | None:
    """The published definition, or `None` when the registry publishes no such view.

    `SV1-06` replaces this one call with its history-aware resolver, which is why
    the lookup is a function here rather than inline: the seam exists so that
    widening what can be resolved does not change `project`'s signature.
    """
    try:
        return define_view(view_id)
    except UnknownView:
        return None


def _candidate(sources: tuple[object, ...]) -> SourceCandidate:
    """What admission may read about the sources, and nothing projectable.

    A request naming no source, or more than one bundle, answers a shape no
    definition admits: `FR-136` admits *a* governed bundle, and picking one of
    several would choose a population on the reader's behalf.
    """
    if len(sources) != 1:
        return SourceCandidate(source_shape="unrecognized_source")
    source = sources[0]
    codes = tuple(record.citation_id for record in getattr(source, "evidence", ()))
    return SourceCandidate(source_shape=_shape_of(source), evidence_codes=codes)


def _projection(
    request: SemanticViewRequest,
    definition: SemanticViewDefinition,
    bundle: RenderableBundle,
) -> ViewProjection:
    """Select, order and propagate -- the whole of what this module does."""
    figures = _admitted_figures(bundle, definition, request)
    fields = definition.output_field_order
    return ViewProjection(
        view_id=definition.view_id,
        view_version=definition.view_version,
        fields=fields,
        rows=tuple(_row(figure, bundle, fields) for figure in figures),
        version_pairs=_versions_of(bundle, definition, figures),
        caveats=bundle.caveats,
        population_qualifiers=(),
        evidence=bundle.evidence,
        evidence_absences=_evidence_absences(bundle.evidence),
        is_empty=not figures,
        empty_rule=definition.empty_result_rule,
    )


def _effective(
    request: SemanticViewRequest, definition: SemanticViewDefinition
) -> EffectiveRequest:
    """`FR-137` -- every dimension and filter that applied, requested or fixed."""
    return EffectiveRequest(
        dimensions=request.dimensions or definition.dimension_allowlist,
        requested_filters=request.filters,
        fixed_filters=definition.fixed_filters,
    )


def project(request: SemanticViewRequest, sources: tuple[object, ...]) -> ViewOutcome:
    """One semantic view over one governed bundle, or the refusal that stops it.

    The unresolved-definition branch is a guard rather than an assertion.
    `validate` refuses an unknown view before anything else, so it should be
    unreachable -- and `Constitution V` says fail closed rather than trust that,
    because an `assert` states the same belief while disappearing under `-O` and
    an assertion is not a governed refusal a reader can be shown.

    Validation runs first and unconditionally (`FR-137`, `FR-141`). Emptiness is
    decided *after* projecting, because `FR-142` makes an admitted empty result a
    result: the request was valid, the source was read, and no admitted figure
    was there. It carries the definition's own `empty_result_rule` and never
    widens -- no filter is dropped and no dimension substituted to find rows.
    """
    definition = _resolve(request.view_id)
    candidate = _candidate(sources)
    refusal = validate(request, definition, candidate)
    if refusal is not None:
        return ViewOutcome(kind=KIND_REFUSED, refusal=refusal)
    if definition is None:
        return ViewOutcome(kind=KIND_REFUSED, refusal=ViewRefusal(CAUSE_UNKNOWN_VIEW))
    bundle: RenderableBundle = sources[0]  # type: ignore[assignment]
    return ViewOutcome(
        kind=KIND_ADMITTED,
        projection=_projection(request, definition, bundle),
        effective=_effective(request, definition),
    )
