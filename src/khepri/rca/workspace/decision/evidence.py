"""S-9 -- the evidence drawer's figure half (`D1-05`; active `RCA-008`).

**The drawer is two halves from two authorities, and this is one of them.**
`RRA-011`'s catalog supplies the *definition* half -- a metric's business name,
what it means, and the governed version of the contract that computes it -- and
`FR-159` admits that because it is structure rather than a figure. `khepri.rca`
may not import `khepri.rra`, so the catalog is read on the surface, exactly as
`card.py` leaves the metric's label to be. This module supplies the other half:
what the governed records say about the figure a reader is looking at.

**The join is by metric, off the evidence records, because the view publishes no
metric column.** `ReportEvidenceView`'s `output_field_order` is
`("figure", "evidence", "provenance", "absence")` -- figure identifier and
citation -- so its *rows* cannot be joined to a card. `ViewProjection.evidence`
can: one `CitedEvidence` per distinct citation, each naming its metric, unit
kind, formula version, precision, inputs and provenance. Both are parts of one
projection, so `FR-159` is satisfied either way; the records are simply the part
that states a metric. The rows are still read, for the figure identifiers each
citation appears against.

**Provenance comes from the record and not from the column of that name.**
`RRA-014`'s `_FIELD_READERS` gives `figure` and `evidence` readers and gives
`provenance` and `absence` none, so both project as `None` -- "a field no member
of `RenderableBundle` states, an absence and not a blank". That is `RRA-014`'s
projection and `RCA-008` §Exclusions bars changing it, so this module reads the
half that is stated and `test_d105_evidence_drawer` asserts the two columns stay
absences: the day they gain readers, that assertion fails and this module is
looked at rather than left double-sourcing one figure.

**An evidence absence is data, never a refusal.** `D1-01` §4 established that
every published view's `required_evidence` is `()` at v1 and that this is not an
oversight for D1 to correct: `FR-141` makes a *required*-but-absent evidence code
a refusal cause, and the v1 registry requires none. So an absence arrives on an
admitted projection, is carried here as an admitted reading, and no `ViewRefusal`
is constructed anywhere on that path.

**No filter is sent, and that is this view's contract rather than a choice.**
`ReportEvidenceView`'s `request_filter_allowlist` is `()`, so a drawer that
forwarded the surface's filters would get `FR-137`'s refusal on every figure it
was opened on. `EvidenceRequest` therefore has no `filters` field to forward,
which puts the absence on the type rather than in a caller's discipline.

**The effective request is not kept here, and the first draft of this module kept
it.** `FR-162` requires a card expose "the effective filters and period", and
`ViewOutcome.effective` is `FR-137`'s "what actually applied". But the filters a
*card* states are the ones that applied to the card's own figure, which is S-1's
read and not this one; carrying S-9's here as well would have put two effective
requests on one surface with one of them rendered. `CardsReading.effective` is
the one, and the period is on neither: `FR-166` makes the period a source
selector, so the period a surface states is the run it is addressed by.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import (
    KIND_ADMITTED,
    ViewProjection,
    ViewRefusal,
)
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision.seam import (
    REPORT_EVIDENCE,
    DecisionRead,
    admitted_projection,
    read,
)

__all__ = [
    "EvidenceAction",
    "EvidenceEntry",
    "EvidenceReading",
    "EvidenceRequest",
    "read_evidence",
]


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    """What the governed records state about one cited figure.

    Every field is the record's own. `None` on `precision`, `inputs` or
    `provenance` means *no retained record states this*, which `CitedEvidence`'s
    own docstring is emphatic about and which `absences` then names positively --
    `FR-140` distinguishes "the record says there is none" from "this projection
    dropped it", and only a positive statement carries that difference.

    `figures` is which of the view's rows cite this record, grouped for layout
    and nothing more.
    """

    citation: str
    metric: str
    unit_kind: object = None
    formula_version: object = None
    precision: object | None = None
    inputs: object | None = None
    provenance: object | None = None
    figures: tuple[str, ...] = field(default_factory=tuple)
    absences: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EvidenceAction:
    """`FR-162`'s evidence action for one metric: what opening the drawer shows.

    `entries` is a tuple and not one entry because nothing guarantees a metric is
    cited exactly once, and picking one of several would choose a citation on the
    reader's behalf. An empty tuple means this projection cited nothing for this
    metric -- a different answer from `unavailable`, which means S-9 could not be
    read at all (`FR-165`, content-free).
    """

    metric: str
    entries: tuple[EvidenceEntry, ...] = field(default_factory=tuple)
    unavailable: bool = False


@dataclass(frozen=True, slots=True)
class EvidenceReading:
    """One S-9 read, in the shape a drawer renders.

    `refusal` is whole rather than flattened to a message, for `FR-164`'s reason:
    the governed bilingual wording is the surface's to render in the page
    language.
    """

    status: str
    entries: tuple[EvidenceEntry, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None
    empty_rule: str | None = None

    def for_metric(self, metric: str) -> EvidenceAction:
        """This metric's action: its own entries, or the content-free absence.

        Selection over what was already read, so a card gains its action without
        a second read -- which `FR-168` bars and which would be a different run's
        evidence the moment anything changed underneath.
        """
        if self.status != KIND_ADMITTED:
            return EvidenceAction(metric=metric, unavailable=True)
        return EvidenceAction(
            metric=metric,
            entries=tuple(entry for entry in self.entries if entry.metric == metric),
        )


@dataclass(frozen=True, slots=True)
class EvidenceRequest:
    """Who is asking, in which organization, over which completed run.

    No `filters` field: `ReportEvidenceView` admits none, so there is nothing for
    a caller to supply and nothing for this module to drop. See the module
    docstring -- the absence is on the type on purpose.
    """

    organization_id: str
    account_id: str
    source_id: str


def read_evidence(
    actions: SemanticQueryActions, request: EvidenceRequest
) -> EvidenceReading:
    """Read S-9 for one run. Selects, groups for layout, and computes nothing.

    Dispatching on the declared kind rather than on the payload is carried from
    `D1-02`: `ViewOutcome` still has no kind-to-payload validation, so a refused
    outcome carrying a projection would otherwise render its rows under an
    admitted status.
    """
    outcome = read(actions, _spec(request))
    projection = admitted_projection(outcome)
    if projection is None:
        return EvidenceReading(status=outcome.kind, refusal=outcome.refusal)
    return EvidenceReading(
        status=KIND_ADMITTED,
        entries=_entries(projection),
        empty_rule=REPORT_EVIDENCE.empty_rule if projection.is_empty else None,
    )


def _spec(request: EvidenceRequest) -> DecisionRead:
    """One read of S-9 for this request. No metric named, and no filter sent."""
    return DecisionRead(
        organization_id=request.organization_id,
        account_id=request.account_id,
        identity=REPORT_EVIDENCE,
        source_ids=(request.source_id,),
    )


def _entries(projection: ViewProjection) -> tuple[EvidenceEntry, ...]:
    """One entry per cited record, in the projection's own order."""
    figures = _figures_by_citation(projection)
    absences = _absences_by_citation(projection)
    return tuple(
        _entry(record, figures.get(_citation_of(record), ()), absences)
        for record in projection.evidence
    )


def _entry(
    record: object,
    figures: tuple[str, ...],
    absences: dict[str, tuple[str, ...]],
) -> EvidenceEntry:
    """One record as the drawer reads it. Every value is the record's own."""
    citation = _citation_of(record)
    return EvidenceEntry(
        citation=citation,
        metric=str(getattr(record, "metric", "")),
        unit_kind=getattr(record, "unit_kind", None),
        formula_version=getattr(record, "formula_version", None),
        precision=getattr(record, "precision", None),
        inputs=getattr(record, "inputs", None),
        provenance=getattr(record, "provenance", None),
        figures=figures,
        absences=absences.get(citation, ()),
    )


def _citation_of(record: object) -> str:
    """The citation a record is filed under, as a string key."""
    return str(getattr(record, "citation_id", ""))


def _figures_by_citation(projection: ViewProjection) -> dict[str, tuple[str, ...]]:
    """Which figure identifiers each citation appears against, from the rows.

    The rows are read through the view's published field order rather than by
    position, for the reason `BreakdownRow` is: `FR-134` makes that order part of
    view identity, and a reader indexing by position would keep a second copy of
    it.
    """
    grouped: dict[str, list[str]] = {}
    for row in projection.rows:
        named = dict(zip(projection.fields, row, strict=True))
        grouped.setdefault(str(named.get("evidence", "")), []).append(
            str(named.get("figure", ""))
        )
    return {citation: tuple(figures) for citation, figures in grouped.items()}


def _absences_by_citation(projection: ViewProjection) -> dict[str, tuple[str, ...]]:
    """The governed absences each citation states, grouped for layout.

    `evidence_absences` arrives as `(citation, kind)` pairs -- `RRA-014` builds
    them that way and the adapter hands the outcome back unchanged -- even though
    `RCA-006`'s port annotates the field more narrowly. `RCA-008` §Exclusions bars
    editing either module, so this reads the shape that is actually produced and
    `test_d105_evidence_drawer` asserts it against the projector itself.
    """
    grouped: dict[str, list[str]] = {}
    for stated in projection.evidence_absences:
        citation, kind = stated
        grouped.setdefault(str(citation), []).append(str(kind))
    return {citation: tuple(kinds) for citation, kinds in grouped.items()}
