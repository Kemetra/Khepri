"""Authorized comparison orchestration (`C1-06`; `RCA-005` `FR-130`--`FR-133`).

`RCA-005` §Comparison orchestration admits requesting, reaching and auditing a
comparison of two dataset versions in one organization. §Comparison retention
keeps the result a read-time value: this module writes no comparison table, no
artifact binding and no retention row. Every figure and every `RRA-008` refusal
cause is assembled by the injected port; this module decides who may ask, that
the pair is exactly two ordered versions, and that one content-free audit event
is written (`FR-133`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import sessionmaker

from khepri.rca.isolation import IsolationService
from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    AuditActor,
    WorkspaceAuditEvent,
)
from khepri.rca.workspace.audit_persistence import SqlWorkspaceAuditStore
from khepri.rca.workspace.store import SqlWorkspaceRecordStore
from khepri.rca.workspace.unit_of_work import unit_of_work

__all__ = [
    "ComparisonActions",
    "ComparisonActor",
    "ComparisonAssembly",
    "ComparisonOutcome",
    "ComparisonRefusal",
    "ComparisonRequest",
    "ComparisonStores",
    "ComparisonSurfaces",
    "KIND_ADMITTED",
    "KIND_REFUSED",
    "KIND_UNAVAILABLE",
    "OrderedVersionIds",
]

KIND_ADMITTED = "admitted"
KIND_REFUSED = "refused"
KIND_UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ComparisonActor:
    """The RCA identifier that stops at `resolve_scope` (`FR-042`)."""

    account_id: str


@dataclass(frozen=True, slots=True)
class ComparisonRequest:
    """Exactly two ordered version identifiers in one organization (`FR-130`).

    `extra_version_ids` exists only so a caller naming three or more versions
    can be refused before any version store read (`FR-130`). It is not an N-way
    comparison input.
    """

    actor: ComparisonActor
    organization_id: str
    subject_version_id: str
    baseline_version_id: str
    extra_version_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OrderedVersionIds:
    """The two identifiers after the pairwise shape has already been accepted."""

    subject_version_id: str
    baseline_version_id: str


@dataclass(frozen=True, slots=True)
class ComparisonRefusal:
    """A governed refusal: the `RRA-008` cause and its bilingual wording."""

    cause: str
    wording: dict[str, str]


@dataclass(frozen=True, slots=True)
class ComparisonSurfaces:
    """The three surfaces rendered in this request, retained nowhere."""

    claims: dict[str, object]
    html: dict[str, str]
    pdf: dict[str, bytes]
    excel: bytes
    subject_run_id: str
    baseline_run_id: str


@dataclass(frozen=True, slots=True)
class ComparisonOutcome:
    """Admitted surfaces, an `RRA-008` refusal, or the uniform isolation miss."""

    kind: str
    refusal: ComparisonRefusal | None = None
    surfaces: ComparisonSurfaces | None = None
    bundle: object | None = None

    @property
    def admitted(self) -> bool:
        return self.kind == KIND_ADMITTED

    @property
    def refused(self) -> bool:
        return self.kind == KIND_REFUSED

    @property
    def unavailable(self) -> bool:
        return self.kind == KIND_UNAVAILABLE


@dataclass(frozen=True, slots=True)
class ComparisonStores:
    """The workspace rows this action may read, and the audit trail it writes."""

    workspace: SqlWorkspaceRecordStore
    audit: SqlWorkspaceAuditStore
    factory: sessionmaker


class ComparisonAssembly(Protocol):
    """The RRA half, injected so this package never imports `khepri.rra`."""

    def unordered_refusal(self) -> ComparisonRefusal: ...

    def assemble_pair(
        self, owner_id: str, pair: OrderedVersionIds, *, now: datetime
    ) -> ComparisonOutcome | None: ...


def _unavailable() -> ComparisonOutcome:
    return ComparisonOutcome(kind=KIND_UNAVAILABLE)


def _refused(refusal: ComparisonRefusal) -> ComparisonOutcome:
    return ComparisonOutcome(kind=KIND_REFUSED, refusal=refusal)


def _has_extra_versions(request: ComparisonRequest) -> bool:
    return bool(request.extra_version_ids)


def _is_self_pair(request: ComparisonRequest) -> bool:
    return request.subject_version_id == request.baseline_version_id


def _shape_refused(request: ComparisonRequest) -> bool:
    if _has_extra_versions(request):
        return True
    return _is_self_pair(request)


def _ordered(request: ComparisonRequest) -> OrderedVersionIds:
    return OrderedVersionIds(request.subject_version_id, request.baseline_version_id)


def _either_missing(subject: object | None, baseline: object | None) -> bool:
    if subject is None:
        return True
    return baseline is None


class ComparisonActions:
    """Request a two-population comparison (`FR-130`--`FR-133`)."""

    def __init__(
        self,
        isolation: IsolationService,
        stores: ComparisonStores,
        assembly: ComparisonAssembly,
    ) -> None:
        self._isolation = isolation
        self._stores = stores
        self._assembly = assembly

    def request(self, request: ComparisonRequest, *, now: datetime) -> ComparisonOutcome:
        """One comparison, derived at read time, with exactly one audit event."""
        if _shape_refused(request):
            return self._refuse_shape(request, now=now)
        actor = self._actor(request)
        return self._scoped(request, actor, now)

    def _actor(self, request: ComparisonRequest) -> AuditActor:
        owner_id = self._isolation.resolve_scope(request.actor.account_id, request.organization_id)
        return AuditActor(owner_id=owner_id, actor_account_id=request.actor.account_id)

    def _refuse_shape(self, request: ComparisonRequest, *, now: datetime) -> ComparisonOutcome:
        outcome = _refused(self._assembly.unordered_refusal())
        self._audit(self._actor(request), outcome, now)
        return outcome

    def _scoped(
        self, request: ComparisonRequest, actor: AuditActor, now: datetime
    ) -> ComparisonOutcome:
        pair = _ordered(request)
        workspace = self._stores.workspace
        subject = workspace.get_dataset_version(pair.subject_version_id, actor.owner_id)
        baseline = workspace.get_dataset_version(pair.baseline_version_id, actor.owner_id)
        if _either_missing(subject, baseline):
            outcome = _unavailable()
            self._audit(actor, outcome, now)
            return outcome
        assembled = self._assembly.assemble_pair(actor.owner_id, pair, now=now)
        outcome = _unavailable() if assembled is None else assembled
        self._audit(actor, outcome, now)
        return outcome

    def _audit(self, actor: AuditActor, outcome: ComparisonOutcome, now: datetime) -> None:
        event = _audit_event(actor, outcome, now)
        with unit_of_work(self._stores.factory):
            self._stores.audit.record(event)


def _audit_event(
    actor: AuditActor, outcome: ComparisonOutcome, now: datetime
) -> WorkspaceAuditEvent:
    if outcome.admitted:
        return WorkspaceAuditEvent.completed(actor, ACTION_RUN_COMPLETED, None, now=now)
    return WorkspaceAuditEvent.refused(actor, ACTION_RUN_FAILED, None, now=now)
