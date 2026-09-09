"""The semantic-view definition record (`SV1-02`; `RRA-014` `FR-134`, `FR-136`).

`RRA-014` §Semantic view contract names ten fields and deliberately declines to
choose their Python types: "This specification defines neither their Python types
nor their implementation representation; `SV1-02` does so only within this
contract." This module is that choice. It holds no view and no lookup, so a reader can see
the shape without reading the eight definitions that use it, and its only
behaviour is refusing a record `RRA-014` does not admit: `FR-136`'s source
shapes, `FR-142`'s empty rules, and `FR-134`'s rule that a changed field is a
new version. A vocabulary constant that nothing checks is a comment, and a
record whose identity says "immutable" while a second record can claim the same
identity with different content is immutable in name only.

Every collection field is a `tuple`, never a `list` or a `dict`. `FR-134` makes
output order part of view identity: "changing any admitted source, field, metric,
dimension, filter, evidence requirement, empty rule, or output order creates a new
version." A mutable collection could be reordered after publication without the
version moving, and a mapping's iteration order is an implementation detail rather
than a published one.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

__all__ = [
    "ADMITTED_SOURCE_SHAPES",
    "EMPTY_RULES",
    "EMPTY_STATED_ABSENCE",
    "EMPTY_STATED_NO_ROWS",
    "SHAPE_EITHER_BUNDLE",
    "SHAPE_SINGLE_POPULATION",
    "SHAPE_TWO_POPULATION",
    "SemanticViewDefinition",
    "ViewDefinitionRefused",
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

#: The two fields `FR-134` calls identity. Every other contract field is one it
#: names as version-moving, which is why the semantics below are derived by
#: exclusion rather than listed: a field added to the record joins the compared
#: set with no edit here, and a field this module forgot to list cannot quietly
#: become mutable-in-place.
_IDENTITY_FIELDS = frozenset({"view_id", "view_version"})

#: What each published `(view_id, view_version)` was first constructed with.
#: `FR-134` makes a differing reconstruction a defect rather than an update, and
#: `frozen=True` cannot see it: it blocks assignment to an existing record, not a
#: second record -- `dataclasses.replace(published, metric_allowlist=...)` keeps
#: the identity and changes the meaning. Process-global on purpose, because the
#: claim `FR-134` makes is about the identity, not about one call site.
_PUBLISHED_SEMANTICS: dict[tuple[str, str], tuple[tuple[str, object], ...]] = {}


class ViewDefinitionRefused(ValueError):
    """A record `RRA-014` does not admit, refused where it is constructed.

    Follows `facts.FactsRefused`. Raised at construction rather than at query
    time because an unadmitted source shape, an unknown empty rule, and a
    silently-reversioned field are publication defects: no request the customer
    made can produce one, and a registry that carries one is already wrong
    before the first query arrives.
    """


def _refuse_unadmitted(field: str, value: str, admitted: frozenset[str]) -> None:
    """Refuse a contract field whose value is outside its published vocabulary."""
    if value not in admitted:
        raise ViewDefinitionRefused(f"{field}={value!r} is not one of {sorted(admitted)}")


def _semantics(definition: SemanticViewDefinition) -> tuple[tuple[str, object], ...]:
    """Every field `FR-134` makes version-moving, paired with its value."""
    return tuple(
        (field.name, getattr(definition, field.name))
        for field in fields(definition)
        if field.name not in _IDENTITY_FIELDS
    )


def _claim_identity(definition: SemanticViewDefinition) -> None:
    """Refuse a second record claiming a published identity with other content.

    Reconstructing the identical record is admitted -- an import is not an edit
    -- so this compares rather than merely detecting a repeat.
    """
    identity = (definition.view_id, definition.view_version)
    semantics = _semantics(definition)
    if _PUBLISHED_SEMANTICS.setdefault(identity, semantics) != semantics:
        raise ViewDefinitionRefused(
            f"{identity[0]} {identity[1]} is already published with different "
            "fields; FR-134 makes any such change a new version"
        )


@dataclass(frozen=True, slots=True)
class SemanticViewDefinition:
    """One immutable, versioned selection and projection over governed facts.

    The ten fields are `RRA-014` §Semantic view contract's, in its order. The
    record computes nothing: a view "selects existing metrics, dimensions,
    filters, and evidence requirements" and "cannot define a new formula", so a
    definition that could compute something would be the wrong shape for the
    contract it represents. `__post_init__` is the one exception and is not a
    computation -- it refuses a record no `RRA-014` requirement admits.
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

    def __post_init__(self) -> None:
        """Refuse at construction what `RRA-014` does not admit."""
        _refuse_unadmitted(
            "accepted_source_shape", self.accepted_source_shape, ADMITTED_SOURCE_SHAPES
        )
        _refuse_unadmitted("empty_result_rule", self.empty_result_rule, EMPTY_RULES)
        _claim_identity(self)
