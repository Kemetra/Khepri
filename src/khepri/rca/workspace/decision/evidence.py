"""S-9 -- the evidence drawer (`D1-05`; active `RCA-008`).

Skeleton only: the shapes exist so the RED cases fail on behaviour rather than
on collection. `read_drawer` is implemented in the GREEN step.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import ViewRefusal
from khepri.rca.semantic_queries.queries import SemanticQueryActions

__all__ = [
    "DrawerReading",
    "DrawerRequest",
    "EvidenceItem",
    "MetricDefinitionView",
    "read_drawer",
]


@dataclass(frozen=True, slots=True)
class MetricDefinitionView:
    """The definition half: `RRA-011`'s catalog entry for one metric."""

    code: str
    formula_version: str
    description: str


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """The figure half: one row of `ReportEvidenceView`, in its published order."""

    figure: object
    evidence: object
    provenance: object
    absence: object


@dataclass(frozen=True, slots=True)
class DrawerReading:
    """The drawer as a surface renders it: two halves, each named by its source."""

    status: str
    definition: MetricDefinitionView | None = None
    items: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    absences: tuple[str, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None


@dataclass(frozen=True, slots=True)
class DrawerRequest:
    """Who is asking, over which run, about which figure, in which language."""

    organization_id: str
    account_id: str
    source_id: str
    metric: str
    language: str


def read_drawer(
    actions: SemanticQueryActions, request: DrawerRequest
) -> DrawerReading:
    """Not implemented yet -- the GREEN step builds this."""
    raise NotImplementedError
