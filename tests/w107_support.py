"""Shared setup for `W1-07a`'s deletion tests.

Setup runs through **production verbs** -- the journey submits, the worker settles, the store
seals -- rather than shaping rows directly. Raw setup exempts the transition it skips, so a mutant
of the bypassed verb survives every test built on it; that lesson is recorded against this repo more
than once.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from khepri.rca.workspace.audit import WorkspaceAuditEvent
from khepri.rca.workspace.revocation import SqlRevocationLedger
from khepri.runtime.shell_api import SHELL_PREFIX
from tests.w104_support import Member
from tests.w104b_support import Journey, journey
from tests.w106_support import completed_run, submitted

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def sealed_version(j: Journey, who: Member, *, with_run: bool = False) -> tuple[Any, Any]:
    """A dataset version this scope holds, optionally with a completed run over it.

    Both are produced by the real journey: `submitted` admits and attests an upload, and
    `completed_run` drives the worker through settlement.
    """
    if with_run:
        run, _job_id, _session_id = completed_run(j, who)
        (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
        return version, run
    submitted(j, who)
    (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
    return version, None


def audit_events_for(j: Journey, owner_id: str) -> tuple[WorkspaceAuditEvent, ...]:
    """Every workspace audit event in one scope, oldest first."""
    return j.w.audit.events_for_scope(owner_id)


def uploads_for(j: Journey, owner_id: str) -> tuple[Any, ...]:
    """Every upload row still held by this scope, read as the store reads them."""
    from sqlalchemy import select

    from khepri.rra.persistence import UploadRow

    with j.w.factory() as database:
        return tuple(database.scalars(select(UploadRow).where(UploadRow.owner_id == owner_id)))


def deletion_jobs_for(j: Journey, owner_id: str) -> tuple[str, ...]:
    """Every `RRA` deletion job this scope has begun, by identifier."""
    from sqlalchemy import select

    from khepri.rra.persistence import DeletionJobRow

    with j.w.factory() as database:
        return tuple(
            database.scalars(
                select(DeletionJobRow.deletion_id).where(DeletionJobRow.owner_id == owner_id)
            )
        )


def deletion_service(j: Journey) -> Any:
    """The deletion service composed as the runtime composes it (`R7-01` §3: the RCA store and the
    RRA deletion path meet here, in `khepri.runtime`, and not inside either package)."""
    from khepri.rra.deletion import DeletionService
    from khepri.rra.persistence import SqlDeletionRepository
    from khepri.runtime.workspace_deletion import WorkspaceDeletion

    return WorkspaceDeletion(
        store=j.w.store,
        audit=j.w.audit,
        ledger=SqlRevocationLedger(j.w.factory),
        content=DeletionService(
            sessions=j.w.sessions,
            deletions=SqlDeletionRepository(j.w.factory),
            objects=j.w.objects,
        ),
        factory=j.w.factory,
    )


def delete_address(
    who: Member, version_id: str, language: str = "en", *, organization: str | None = None
) -> str:
    """The deletion address. `organization` overrides the segment, so a test can name one the
    session does not resolve to -- `FR-042` scenario 3."""
    named = organization or who.organization_id
    return f"{SHELL_PREFIX}/{language}/{named}/data/{version_id}/delete"


class _RefusingOwnerGate:
    """A resolver that resolves the session but refuses the owner gate.

    `w105_support.StubResolver` answers the same context from `for_request` and `require_owner`,
    so no test built on it can tell the two apart -- a route that dropped the owner gate entirely
    passes every one of them. This models the one difference that matters: a real member of the
    organization, who is not its owner.
    """

    def __init__(self, context: Any) -> None:
        self._context = context

    def for_request(self, token: str, *, organization_id: str | None, now: object) -> Any:
        return self._context

    def require_owner(self, token: str, *, organization_id: str, now: object) -> Any:
        raise PermissionError("Resource is unavailable.")


def shell_with_deletion(
    j: Journey,
    who: Member,
    *,
    organization_of: Member | None = None,
    wired: bool = True,
    owner: bool = True,
) -> Any:
    """A shell whose deletion service is wired (or deliberately not).

    `organization_of` lets a member act inside another member's organization, which is how the
    owner-only refusal is driven through the real route rather than by calling the gate.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from khepri.rca.session_cookie import SESSION_COOKIE
    from khepri.runtime.shell_api import ShellServices, add_shell_routes
    from tests.w106_support import HTTPS, services_over

    acting_in = organization_of or who
    base = services_over(j, acting_in)
    services = ShellServices(
        resolver=_RefusingOwnerGate(base.resolver.for_request("", organization_id=None, now=None))
        if not owner
        else base.resolver,
        organizations=base.organizations,
        invitations=base.invitations,
        bridge=base.bridge,
        records=base.records,
        isolation=base.isolation,
        provenance=base.provenance,
        deletion=deletion_service(j) if wired else None,
    )
    app = FastAPI()
    add_shell_routes(app, services=services, clock=j.clock)
    client = TestClient(app, base_url=HTTPS)
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


__all__ = [
    "LATER",
    "NOW",
    "audit_events_for",
    "delete_address",
    "deletion_jobs_for",
    "deletion_service",
    "journey",
    "sealed_version",
    "shell_with_deletion",
    "uploads_for",
]
