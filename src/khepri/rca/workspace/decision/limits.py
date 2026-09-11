"""S-6 -- Exceptions, Caveats and Refusals (`D1-04`; active `RCA-008`).

`RCA-008`'s source map gives this surface "`MetricAvailabilityView`, and each
projection's own caveats". Both halves are here and they arrive by different
routes, which is the whole shape of the module:

**The governed four-state is read, once.** `MetricAvailabilityView` is the only
published view that states `available`/`partial`/`unavailable` with a reason, and
S-6 is the surface entitled to state it -- per metric, never per store, product
or category, which is `FR-167` and is `breakdowns.py`'s side of the same rule.

**The caveats and refusals are not read at all.** They are the other surfaces'
own outcomes, already fetched, handed here as they stand. Re-reading them would
be the pre-aggregation `FR-168` bars and the second truth `FR-135` bars, and the
caveats would be a different run's the moment anything moved between the two
reads. So `LimitsRequest` carries what the page already holds and this module
performs exactly one read of its own.

**Why this surface is second in the narrative and could not be built second.**
`D1-01` §3 recorded it: S-6 reads every other surface's limits, so it cannot
exist before they produce any. `D1-02`'s allocation plan states the ordering rule
it follows -- "a surface can only be qualified by a limit that some surface
already produces".

Nothing here says *why* a part was unavailable. `FR-165` makes the unavailable
outcome content-free: a surface "may say a part is unavailable and may never say
why", and the limits surface is the one place where a why would look most like a
service to the reader.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from khepri.rca.semantic_queries.ports import KIND_ADMITTED, ViewOutcome, ViewRefusal
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision.seam import (
    METRIC_AVAILABILITY,
    DecisionRead,
    admitted_projection,
    read,
)

__all__ = [
    "LimitsReading",
    "LimitsRequest",
    "MetricLimit",
    "SurfaceLimit",
    "read_limits",
]


@dataclass(frozen=True, slots=True)
class MetricLimit:
    """One metric's governed availability and the reason published with it.

    `availability` and `reason` are `object` rather than narrowed strings for
    `OverviewFigure`'s reason: the cell is whatever the governed source
    published, and coercing it here would be the first derivation.

    This is the **only** shape under this specification that carries an
    availability, and `FR-167` is why there is only one: the view behind it
    publishes no series metric, so no per-store, per-product or per-category
    figure may be given one.
    """

    metric: str
    availability: object
    reason: object


@dataclass(frozen=True, slots=True)
class SurfaceLimit:
    """What one already-fetched surface read published about its own figures.

    Named by surface because that is the attribution the data carries: a
    `StatedCaveat` names a section and never a metric, so a caveat is the
    reading's and not any one figure's.

    There is no `reason` field. An unavailable surface says it is unavailable
    (`FR-165`), and the refusal it does carry is `RRA-014`'s own `ViewRefusal`,
    kept whole so `FR-164`'s governed bilingual wording survives to the renderer.
    """

    surface: str
    status: str
    caveats: tuple[object, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None


@dataclass(frozen=True, slots=True)
class LimitsReading:
    """S-6 as a surface renders it: the four-state, then every surface's limits.

    `status` and `refusal` belong to this surface's own single read. A refused or
    unavailable availability read leaves `availabilities` empty and leaves the
    gathered surface limits untouched, which is `FR-165` again: the reads are
    independent, so one missing does not take the others with it.
    """

    status: str
    availabilities: tuple[MetricLimit, ...] = field(default_factory=tuple)
    surfaces: tuple[SurfaceLimit, ...] = field(default_factory=tuple)
    refusal: ViewRefusal | None = None
    empty_rule: str | None = None


@dataclass(frozen=True, slots=True)
class LimitsRequest:
    """Who is asking, over which run, and what the page already fetched.

    `gathered` is ordered pairs of surface name and the outcome that surface
    already received -- never a mapping, for `ViewRefusal.wording`'s reason: the
    order a limits surface lists its exceptions in is a presentation decision,
    and a mapping's iteration order is an implementation detail rather than a
    published one.
    """

    organization_id: str
    account_id: str
    source_id: str
    gathered: tuple[tuple[str, ViewOutcome], ...] = field(default_factory=tuple)


def _limit(cell: dict[str, object]) -> MetricLimit:
    """One availability row, named by the view's published field order."""
    return MetricLimit(
        metric=str(cell["metric"]),
        availability=cell["availability"],
        reason=cell["reason"],
    )


def _surface_limit(surface: str, outcome: ViewOutcome) -> SurfaceLimit:
    """One already-fetched outcome, as the limits surface reports it.

    The kind decides and never the payload, so a refused outcome that also
    carries a projection reports its refusal and none of that projection's
    caveats -- which would otherwise qualify figures no reader was shown.
    """
    projection = admitted_projection(outcome)
    caveats = () if projection is None else projection.caveats
    return SurfaceLimit(
        surface=surface,
        status=outcome.kind,
        caveats=caveats,
        refusal=outcome.refusal,
    )


def read_limits(actions: SemanticQueryActions, request: LimitsRequest) -> LimitsReading:
    """Read S-6's one view and report it beside what the page already holds."""
    surfaces = tuple(
        _surface_limit(surface, outcome) for surface, outcome in request.gathered
    )
    outcome = read(
        actions,
        DecisionRead(
            organization_id=request.organization_id,
            account_id=request.account_id,
            identity=METRIC_AVAILABILITY,
            source_ids=(request.source_id,),
        ),
    )
    projection = admitted_projection(outcome)
    if projection is None:
        return LimitsReading(
            status=outcome.kind, surfaces=surfaces, refusal=outcome.refusal
        )
    return LimitsReading(
        status=KIND_ADMITTED,
        availabilities=tuple(
            _limit(dict(zip(projection.fields, row, strict=True)))
            for row in projection.rows
        ),
        surfaces=surfaces,
        empty_rule=METRIC_AVAILABILITY.empty_rule if projection.is_empty else None,
    )
