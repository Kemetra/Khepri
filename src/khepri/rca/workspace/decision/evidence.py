"""S-9 -- the evidence drawer (`D1-05`; active `RCA-008`).

`RCA-008`'s source map gives this surface two halves from two authorities, and
keeping them apart is the whole shape of the module:

**The definition half is `RRA-011`'s catalog** -- the code, its governed formula
version, and its bilingual description, read per code through the
`MetricDefinitions` Protocol below. `FR-159` admits it because a definition is
*structure*, not a figure: nothing here computes or selects a value. The catalog
fails closed on an unrecognized code (`UnknownCode`), and that propagates rather
than being softened into an empty drawer -- a drawer that opened blank on a bad
code would be indistinguishable from a metric that genuinely has no evidence.

The Protocol exists because `khepri.rca` may not import `khepri.rra` (`R7-01`
§3), which the repo-wide scan and `test_d102_decision_seam.py` both enforce. The
first draft of this module imported the catalog directly and both caught it.

**The figure half is one `ReportEvidenceView` projection**, read through the same
seam every other decision surface uses. No copy of the catalog is kept beside it:
a second copy is the second truth `FR-135` bars.

**An evidence absence is data, and never a refusal.** `ViewProjection` carries
`evidence_absences` on an *admitted* projection, which is the governed way to say
the record states there is none. `D1-01` section 4 established that every view's
`required_evidence` is `()` at v1 deliberately, and `FR-141` makes a
required-but-absent code a refusal *cause* -- so mapping an absence onto a
refusal here would tell a customer the view refused when it did not. The drawer
reports the absence beside whatever figures the projection did carry.

**The drawer is never a page of its own** (`FR-161`): it is reachable from every
figure in one action and has no route, which is why this module adds neither a
route nor a `ShellServices` collaborator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from khepri.rca.semantic_queries.ports import ViewRefusal
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision.seam import (
    REPORT_EVIDENCE,
    DecisionRead,
    admitted_projection,
    read,
)

__all__ = [
    "DrawerReading",
    "DrawerRequest",
    "EvidenceItem",
    "MetricDefinitionView",
    "MetricDefinitions",
    "read_drawer",
]


class MetricDefinitions(Protocol):
    """The catalog read this drawer may perform, owned by the consumer.

    A Protocol rather than the concrete catalog because `khepri.rca` may not
    import `khepri.rra` (`R7-01` section 3, `RCA-006`'s boundary). The adapter is
    `khepri.runtime.metric_definitions.CatalogDefinitions`, bound where the
    composition root binds every other collaborator.

    Two reads and no write, so the cheapest proof this module records nothing is
    that it holds nothing that can.
    """

    def formula_version(self, code: str) -> str:
        """The governed version of the contract that computes this metric."""
        ...  # pragma: no cover -- Protocol

    def describe(self, code: str, language: str) -> str:
        """The metric's governed description in one of the two languages."""
        ...  # pragma: no cover -- Protocol


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


def _definition(
    catalog: MetricDefinitions, metric: str, language: str
) -> MetricDefinitionView:
    """The catalog's entry for one metric, in the page language.

    `UnknownCode` propagates. `RRA-011` requires a lookup to fail closed, and a
    definition invented for an unrecognized code would be indistinguishable from
    a real one.
    """
    return MetricDefinitionView(
        code=metric,
        formula_version=catalog.formula_version(metric),
        description=catalog.describe(metric, language),
    )


def _item(cell: dict[str, object]) -> EvidenceItem:
    """One evidence row, named by the view's published field order."""
    return EvidenceItem(
        figure=cell["figure"],
        evidence=cell["evidence"],
        provenance=cell["provenance"],
        absence=cell["absence"],
    )


def read_drawer(
    actions: SemanticQueryActions,
    request: DrawerRequest,
    *,
    definitions: MetricDefinitions,
) -> DrawerReading:
    """The definition, then the figures, each kept under its own authority.

    The definition is resolved first and deliberately: it is the half that can
    refuse the whole drawer (`UnknownCode`), and resolving it after a successful
    read would spend a governed query on a figure no reader may be shown.
    """
    definition = _definition(definitions, request.metric, request.language)
    outcome = read(
        actions,
        DecisionRead(
            organization_id=request.organization_id,
            account_id=request.account_id,
            identity=REPORT_EVIDENCE,
            source_ids=(request.source_id,),
        ),
    )
    projection = admitted_projection(outcome)
    if projection is None:
        return DrawerReading(
            status=outcome.kind, definition=definition, refusal=outcome.refusal
        )
    return DrawerReading(
        status=outcome.kind,
        definition=definition,
        items=tuple(
            _item(dict(zip(projection.fields, row, strict=True)))
            for row in projection.rows
        ),
        absences=projection.evidence_absences,
    )
