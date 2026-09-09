"""The semantic-view definition record (`SV1-02`; `RRA-014` `FR-134`, `FR-136`).

`RRA-014` §Semantic view contract names ten fields and deliberately declines to
choose their Python types: "This specification defines neither their Python types
nor their implementation representation; `SV1-02` does so only within this
contract." This module is that choice, and nothing more -- it holds no view, no
lookup and no behaviour, so a reader can see the shape without reading the eight
definitions that use it.

Every collection field is a `tuple`, never a `list` or a `dict`. `FR-134` makes
output order part of view identity: "changing any admitted source, field, metric,
dimension, filter, evidence requirement, empty rule, or output order creates a new
version." A mutable collection could be reordered after publication without the
version moving, and a mapping's iteration order is an implementation detail rather
than a published one.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "ADMITTED_SOURCE_SHAPES",
    "EMPTY_RULES",
    "EMPTY_STATED_ABSENCE",
    "EMPTY_STATED_NO_ROWS",
    "SHAPE_EITHER_BUNDLE",
    "SHAPE_SINGLE_POPULATION",
    "SHAPE_TWO_POPULATION",
    "SemanticViewDefinition",
]

#: A governed single-population bundle -- `RRA-006`'s `ReportBundle`.
SHAPE_SINGLE_POPULATION = "single_population_bundle"

#: A governed two-population bundle -- `RRA-006` §Two-population bundle's
#: `CrossVersionBundle`, the sibling `C1-05` shipped.
SHAPE_TWO_POPULATION = "two_population_bundle"

#: Both, admitted only where their projection contract is identical (`FR-136`).
#: The two bundles satisfy one read-only Protocol, `renderable.RenderableBundle`,
#: which is what makes "identical" checkable rather than asserted: a view naming
#: this shape may read only members that Protocol declares.
SHAPE_EITHER_BUNDLE = "either_bundle"

#: The exact source shapes `FR-136` admits. A definition naming anything else is
#: refused at construction rather than at query time, because an unadmitted shape
#: is a publication defect and not a request the customer made.
ADMITTED_SOURCE_SHAPES: frozenset[str] = frozenset(
    {SHAPE_SINGLE_POPULATION, SHAPE_TWO_POPULATION, SHAPE_EITHER_BUNDLE}
)

#: The admitted request matched no row. `FR-142`: the result "never widens to
#: unfiltered data, a nearby dimension, another version, or a partial result",
#: so an empty result is stated as empty and carries the effective request that
#: produced it.
EMPTY_STATED_NO_ROWS = "stated_no_rows"

#: The governed source itself published no value for this view's metrics -- a
#: refused or unavailable measure rather than a filter that matched nothing.
#: Distinct from `EMPTY_STATED_NO_ROWS` because the reader's question differs:
#: "nothing matched what you asked" is not "we could not compute this".
EMPTY_STATED_ABSENCE = "stated_absence"

#: Every empty rule a definition may state (`FR-142`).
EMPTY_RULES: frozenset[str] = frozenset({EMPTY_STATED_NO_ROWS, EMPTY_STATED_ABSENCE})


@dataclass(frozen=True, slots=True)
class SemanticViewDefinition:
    """One immutable, versioned selection and projection over governed facts.

    The ten fields are `RRA-014` §Semantic view contract's, in its order. The
    record carries no method: a view "selects existing metrics, dimensions,
    filters, and evidence requirements" and "cannot define a new formula", so a
    definition that could compute something would be the wrong shape for the
    contract it represents.
    """

    #: Immutable identity (`FR-134`). Names the view, never the version.
    view_id: str

    #: Immutable version (`FR-134`). Requests name it exactly; `FR-143` admits no
    #: `latest` alias and no silent upgrade, so this is never defaulted.
    view_version: str

    #: One member of `ADMITTED_SOURCE_SHAPES` (`FR-136`).
    accepted_source_shape: str

    #: The metrics this view may project. Members are governed codes read from
    #: `definitions.METRIC_CODES`' sources -- `FR-135` forbids retyping them as a
    #: second truth, so `registry.py` derives every member rather than listing it.
    metric_allowlist: tuple[str, ...]

    #: The dimensions this view may be keyed by, from `facts.SERIES_DIMENSIONS`.
    dimension_allowlist: tuple[str, ...]

    #: The filters a request may name. A parameter absent from this tuple refuses
    #: before projection (`FR-137`) rather than being silently dropped.
    request_filter_allowlist: tuple[str, ...]

    #: Filters the definition applies whatever the request says. Ordered pairs,
    #: not a mapping, so the result can state them back in a published order
    #: (`FR-137`: every effective filter is visible in request and result).
    fixed_filters: tuple[tuple[str, str], ...]

    #: Evidence this view requires. Absence is a refusal cause (`FR-141`), never
    #: a quietly missing key -- `FR-140` keeps a governed evidence absence intact
    #: through projection instead of converting it to an ordinary value.
    required_evidence: tuple[str, ...]

    #: The published field order (`FR-134`). Part of identity: reordering it is a
    #: new version, which is why the projection reads this rather than sorting.
    output_field_order: tuple[str, ...]

    #: One member of `EMPTY_RULES` (`FR-142`).
    empty_result_rule: str
