"""Organization semantic-query orchestration (`SV1`; `RCA-006`).

An authenticated owner or member requests one exact semantic-view version over
sources in one organization. This package scopes and loads those sources and
calls an injected `RRA-014` protocol; it retains nothing and records nothing.

`SV1-04` declares the seam (`ports.py`) and the orchestration (`queries.py`).
The composition root that binds a concrete `RRA-014` implementation to
`SemanticViewPort` is **not** here and is not yet authorized -- see `ports.py`
and the `SV1` allocation plan.
"""

from __future__ import annotations

from khepri.rca.semantic_queries.ports import (
    KIND_ADMITTED,
    KIND_REFUSED,
    KIND_UNAVAILABLE,
    EffectiveRequest,
    SemanticViewPort,
    SemanticViewRequest,
    ViewOutcome,
    ViewProjection,
    ViewRefusal,
)
from khepri.rca.semantic_queries.queries import (
    ScopedSourceReader,
    SemanticQueryActions,
    SemanticQueryActor,
    SemanticQueryRequest,
)

__all__ = [
    "KIND_ADMITTED",
    "KIND_REFUSED",
    "KIND_UNAVAILABLE",
    "EffectiveRequest",
    "ScopedSourceReader",
    "SemanticQueryActions",
    "SemanticQueryActor",
    "SemanticQueryRequest",
    "SemanticViewPort",
    "SemanticViewRequest",
    "ViewOutcome",
    "ViewProjection",
    "ViewRefusal",
]
