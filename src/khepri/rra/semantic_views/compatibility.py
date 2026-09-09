"""Whether a request may be projected, and the one cause when it may not.

`SV1-03`; `RRA-014` `FR-137` and `FR-141`.

**One cause, not a list**, and the checks are ordered so the first match returns
-- `C1-02`'s `analysis/compatibility.py` is the shape precedent, for the reason
it records: "a refusal naming two leaves a caller unable to say which to fix."

**The order is `FR-141`'s own enumeration** -- view, version, metric, dimension,
filter, source shape, evidence -- and not a judgement made here. The one ordering
the specification does not merely list but *requires* coincides with it: a
version belongs to a view, and an allowlist belongs to a version, so a metric
checked before the version is resolved is checked against the wrong allowlist.
Evidence sits last on the same logic read forwards: it is the only cause that
says the request was well-formed and the source simply lacks something, and
reporting it over a malformed request would send a reader looking for evidence
for a request that could never have run. A test asserts this order, so a
reordering fails rather than quietly changing which cause a caller sees.

**This module is handed no rows.** `SourceCandidate` carries the source's shape
and the evidence codes it holds, and nothing else -- following
`ComparisonCandidate`, which is "a projection rather than the `FactPackage`
itself: this module decides admissibility and must not be able to read a
figure". `FR-137` requires refusal *before* projection; a validator that could
read a value could return one.
"""

from __future__ import annotations

from dataclasses import dataclass

from khepri.rra.semantic_views.contracts import (
    SHAPE_EITHER_BUNDLE,
    SemanticViewDefinition,
)
from khepri.rra.semantic_views.refusals import (
    CAUSE_INCOMPATIBLE_SOURCE_SHAPE,
    CAUSE_MISSING_REQUIRED_EVIDENCE,
    CAUSE_UNKNOWN_DIMENSION,
    CAUSE_UNKNOWN_FILTER,
    CAUSE_UNKNOWN_METRIC,
    CAUSE_UNKNOWN_VERSION,
    CAUSE_UNKNOWN_VIEW,
    ViewRefusal,
    refuse,
)

__all__ = [
    "Admission",
    "SemanticViewRequest",
    "SourceCandidate",
    "validate",
]


@dataclass(frozen=True, slots=True)
class SemanticViewRequest:
    """The explicit request: exact identity, explicit selection, explicit filters.

    `FR-143` -- the version is named exactly and there is no `latest`, so it is
    never defaulted. `FR-137` -- every requested filter is named here, so the
    result can state it back.

    `filters` is an ordered tuple of pairs and never a mapping: `FR-137` requires
    every effective filter be visible in request *and* result, and a mapping's
    iteration order is an implementation detail rather than a published one.

    An empty `metrics` or `dimensions` asks for the definition's own published
    selection rather than for nothing. `FR-141` still names *unknown metric* and
    *unknown dimension* as causes, which is why a request may name them at all:
    a request that could not name a metric could never name an unknown one, and
    the cause would be unreachable.
    """

    view_id: str
    view_version: str
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    filters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    """What admission reads about the sources, and nothing that could be projected.

    `source_shape` is always one concrete shape. `SHAPE_EITHER_BUNDLE` is a
    *definition*-side value meaning "both are admitted"; no source is ever both,
    so a candidate naming it would be describing a source that does not exist.
    """

    source_shape: str
    evidence_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Admission:
    """One request, the definition it named, and what its sources offer.

    `definition` is `None` exactly when the registry publishes no view under the
    requested `view_id`. Resolution is the caller's -- `registry.define_view`
    raises `UnknownView` -- and the judgement is here, so that all seven of
    `FR-141`'s causes are decided by one ordered table rather than split between
    a lookup that raises and a validator that returns.
    """

    request: SemanticViewRequest
    definition: SemanticViewDefinition | None
    candidate: SourceCandidate


def _unknown_view(admission: Admission) -> bool:
    """No published view under this identifier.

    Also catches a definition resolved for some *other* view: a caller that
    looked up the wrong record has named a view this definition cannot answer
    for, which is the same refusal from the reader's side.
    """
    definition = admission.definition
    return definition is None or definition.view_id != admission.request.view_id


def _unknown_version(admission: Admission) -> bool:
    """The view exists; this version of it is not the published one (`FR-143`)."""
    definition = admission.definition
    return definition is not None and definition.view_version != admission.request.view_version


def _unknown_metric(admission: Admission) -> bool:
    """A requested metric is outside this version's `metric_allowlist`."""
    definition = admission.definition
    return definition is not None and not set(admission.request.metrics) <= set(
        definition.metric_allowlist
    )


def _unknown_dimension(admission: Admission) -> bool:
    """A requested dimension is outside this version's `dimension_allowlist`."""
    definition = admission.definition
    return definition is not None and not set(admission.request.dimensions) <= set(
        definition.dimension_allowlist
    )


def _unknown_filter(admission: Admission) -> bool:
    """A requested filter parameter is outside `request_filter_allowlist`.

    The parameter is read, never the value: `request_filter_allowlist` admits
    which parameters may be named, and which values they may take is the
    customer's data rather than a published vocabulary.
    """
    definition = admission.definition
    if definition is None:
        return False
    named = {parameter for parameter, _ in admission.request.filters}
    return not named <= set(definition.request_filter_allowlist)


def _incompatible_source_shape(admission: Admission) -> bool:
    """The source is not a shape this definition admits (`FR-136`).

    A definition naming `SHAPE_EITHER_BUNDLE` admits both concrete shapes -- that
    is what the value means -- so it can never raise this cause.
    """
    definition = admission.definition
    if definition is None or definition.accepted_source_shape == SHAPE_EITHER_BUNDLE:
        return False
    return definition.accepted_source_shape != admission.candidate.source_shape


def _missing_required_evidence(admission: Admission) -> bool:
    """The definition requires evidence the source does not carry (`FR-141`)."""
    definition = admission.definition
    return definition is not None and not set(definition.required_evidence) <= set(
        admission.candidate.evidence_codes
    )


#: Every cause `FR-141` names, in the order that specification enumerates them.
#:
#: A table rather than a chain of `if`s, following `C1-02`: seven sequential
#: branches score against the complexity gate, and the order -- the meaningful
#: part -- is a list to audit rather than control flow to trace.
_PREDICATES: tuple[tuple[str, object], ...] = (
    (CAUSE_UNKNOWN_VIEW, _unknown_view),
    (CAUSE_UNKNOWN_VERSION, _unknown_version),
    (CAUSE_UNKNOWN_METRIC, _unknown_metric),
    (CAUSE_UNKNOWN_DIMENSION, _unknown_dimension),
    (CAUSE_UNKNOWN_FILTER, _unknown_filter),
    (CAUSE_INCOMPATIBLE_SOURCE_SHAPE, _incompatible_source_shape),
    (CAUSE_MISSING_REQUIRED_EVIDENCE, _missing_required_evidence),
)


def validate(
    request: SemanticViewRequest,
    definition: SemanticViewDefinition | None,
    candidate: SourceCandidate,
) -> ViewRefusal | None:
    """The first refusal cause for this request, or `None` when all seven hold.

    Returns the refusal rather than raising it: `FR-141` requires a *stable
    contract refusal* the caller states back to the reader, and an exception
    would make the seam's `ViewOutcome` carry a Python traceback's shape instead.
    """
    admission = Admission(request=request, definition=definition, candidate=candidate)
    cause = next(
        (cause for cause, holds in _PREDICATES if holds(admission)),  # type: ignore[operator]
        None,
    )
    return None if cause is None else refuse(cause)
