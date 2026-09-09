"""Curated semantic views over governed facts (`SV1`; `RRA-014`).

A semantic view is an immutable, versioned selection and projection over facts
another governed contract already published. It defines no formula, fact,
population, metric or business calculation; it preserves refusals, caveats,
populations, evidence and governed versions; and it fails closed on an unknown
or incompatible request.

`SV1-02` publishes the closed eight-view registry and the definition record;
`SV1-03` the closed refusal set and the early-refusal validator; `SV1-05` the
projection that selects, orders and propagates; `SV1-06` the published version
history and its exact-version resolver.
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
from khepri.rra.semantic_views.projection import (
    EffectiveRequest,
    ViewOutcome,
    ViewProjection,
    project,
)
from khepri.rra.semantic_views.published import (
    PUBLISHED_DIGESTS,
    definition_digest,
    published_history,
    published_versions,
    resolve,
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
    "PUBLISHED_DIGESTS",
    "REFUSAL_CAUSES",
    "EffectiveRequest",
    "SemanticViewDefinition",
    "SemanticViewRequest",
    "SourceCandidate",
    "UnknownView",
    "ViewDefinitionRefused",
    "ViewOutcome",
    "ViewProjection",
    "ViewRefusal",
    "define_view",
    "definition_digest",
    "project",
    "published_history",
    "published_versions",
    "resolve",
    "refusal_wording",
    "validate",
    "view_ids",
]
