"""Curated semantic views over governed facts (`SV1`; `RRA-014`).

A semantic view is an immutable, versioned selection and projection over facts
another governed contract already published. It defines no formula, fact,
population, metric or business calculation; it preserves refusals, caveats,
populations, evidence and governed versions; and it fails closed on an unknown
or incompatible request.

`SV1-02` publishes the closed eight-view registry and the definition record;
`SV1-03` the closed refusal set and the early-refusal validator. Projection
(`SV1-05`) and published-version resolution (`SV1-06`) join this package as
their slices land.
"""

from __future__ import annotations

from khepri.rra.semantic_views.compatibility import (
    SemanticViewRequest,
    SourceCandidate,
    validate,
)
from khepri.rra.semantic_views.contracts import (
    ADMITTED_SOURCE_SHAPES,
    EMPTY_RULES,
    SemanticViewDefinition,
    ViewDefinitionRefused,
)
from khepri.rra.semantic_views.refusals import (
    REFUSAL_CAUSES,
    ViewRefusal,
    refusal_wording,
)
from khepri.rra.semantic_views.registry import UnknownView, define_view, view_ids

__all__ = [
    "ADMITTED_SOURCE_SHAPES",
    "EMPTY_RULES",
    "REFUSAL_CAUSES",
    "SemanticViewDefinition",
    "SemanticViewRequest",
    "SourceCandidate",
    "UnknownView",
    "ViewDefinitionRefused",
    "ViewRefusal",
    "define_view",
    "refusal_wording",
    "validate",
    "view_ids",
]
