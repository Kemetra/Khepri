"""Authorized semantic-query orchestration (`SV1-04`; `RCA-006` `FR-145`--`FR-149`).

`RCA-006` §Request flow: authorize the actor and organization, load every named
source through that organization's opaque scope, hand the scoped sources and the
explicit request to the injected `RRA-014` protocol, and return its outcome. This
module decides *who may ask* and *which rows they may see*; every definition,
refusal, projection and empty rule is the port's.

`comparisons.py`'s `ComparisonActions` is the precedent, with two deliberate
subtractions that are this specification's whole character:

**No audit store, and no `unit_of_work`.** `ComparisonActions` writes exactly one
audit event per request; `FR-149` admits "no new audit or product-telemetry
event, counter, access record, or content-bearing log", and `FR-148` no row,
object, artifact, cache, preference, history entry, tombstone, or deletion
evidence. So the write path is not guarded here -- it is *absent*. Nothing in
this module opens a transaction, and `ScopedSourceReader` gives it no method that
could.

**Nothing is logged.** `FR-149` also bars request parameters and result content
from existing logs, so this module emits no log line at all: a debug line naming
a view and a source identifier is exactly the content-bearing log it names.

The uniform miss is structural rather than assembled. `FR-146` requires that
"absent, deleted, corrupt, or cross-scope sources return the same content-free
unavailable outcome without identifying which condition held", and
`get_analysis_run(run_id, owner_id)` already answers `None` for an absent row, a
tombstoned or revoked one, and one belonging to another scope alike. The fourth,
a source the RRA half cannot read, arrives as the port's own `None`. All four
reach one `ViewOutcome(kind=KIND_UNAVAILABLE)` built by one function, so they
cannot drift apart into distinguishable answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from khepri.rca.isolation import IsolationService
from khepri.rca.semantic_queries.ports import (
    KIND_UNAVAILABLE,
    SemanticViewPort,
    SemanticViewRequest,
    ViewOutcome,
)
from khepri.rca.workspace.contracts import AnalysisRun

__all__ = [
    "ScopedSourceReader",
    "SemanticQueryActions",
    "SemanticQueryActor",
    "SemanticQueryRequest",
]


@dataclass(frozen=True, slots=True)
class SemanticQueryActor:
    """The RCA identifier that stops at `resolve_scope` (`FR-145`).

    `ComparisonActor`'s shape: an account identifier and nothing else. The
    organization is named by the request rather than carried here, because one
    account may act in more than one and the pair is what `RCA-001` resolves.
    """

    account_id: str


@dataclass(frozen=True, slots=True)
class SemanticQueryRequest:
    """One exact view version over named sources in one organization (`FR-145`).

    `source_ids` is ordered and may name more than one: `RRA-014`'s
    two-population views read a pair. Order is the caller's and is preserved into
    the port, because which source is subject and which is baseline is a
    distinction the projection needs and this module must not invent.
    """

    actor: SemanticQueryActor
    organization_id: str
    view: SemanticViewRequest
    source_ids: tuple[str, ...] = ()


class ScopedSourceReader(Protocol):
    """The one read this orchestration may perform.

    A Protocol with a single reader rather than the concrete
    `SqlWorkspaceRecordStore`, following `ComparisonCandidate`'s discipline one
    layer up: `FR-148` requires zero writes, and the cheapest way to prove a
    module writes nothing is to hand it nothing that can write. `FR-150` still
    wants the assertion tested, and it is -- but the structure is what makes the
    assertion hard to falsify later.
    """

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> AnalysisRun | None: ...


def _unavailable() -> ViewOutcome:
    """The one content-free miss (`FR-146`). Built here so every path is identical."""
    return ViewOutcome(kind=KIND_UNAVAILABLE)


class SemanticQueryActions:
    """Request one semantic view over scoped sources (`FR-145`--`FR-149`)."""

    def __init__(
        self,
        isolation: IsolationService,
        sources: ScopedSourceReader,
        port: SemanticViewPort,
    ) -> None:
        self._isolation = isolation
        self._sources = sources
        self._port = port

    def request(self, request: SemanticQueryRequest) -> ViewOutcome:
        """One query, derived at read time, writing nothing and recording nothing.

        Authorization comes first and unconditionally: `FR-145` requires the actor
        and organization resolve "before reading a source or invoking RRA", so
        `resolve_scope` runs ahead of the first store read rather than beside it.
        It raises `ScopeAccessDenied` for an actor who may not act here, which is
        `ComparisonActions`' behaviour and is distinct from the unavailable
        outcome: a source that is missing is an answer, and an actor who may not
        ask is not.
        """
        owner_id = self._isolation.resolve_scope(request.actor.account_id, request.organization_id)
        scoped = self._scoped_sources(request.source_ids, owner_id)
        if scoped is None:
            return _unavailable()
        projected = self._port.project(request.view, scoped)
        return _unavailable() if projected is None else projected

    def _scoped_sources(
        self, source_ids: tuple[str, ...], owner_id: str
    ) -> tuple[object, ...] | None:
        """Every named source under this scope, or `None` if any one of them misses.

        All-or-nothing on purpose. `FR-147` passes "only successfully scoped
        governed sources", and a partial tuple would let a two-population view
        project over one population -- a narrower answer than the reader asked
        for, delivered as though it were the answer.
        """
        loaded: list[object] = []
        for source_id in source_ids:
            run = self._sources.get_analysis_run(source_id, owner_id)
            if run is None:
                return None
            loaded.append(run)
        return tuple(loaded)
