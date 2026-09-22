"""The governed refusals a shell route answers with its one uniform unavailable surface (#520).

A shell route checks its actor at a gate (`require_owner`, `for_request`) and then calls a service
that may refuse *again* -- a store that will not take the write, or a scope door re-resolved after
a membership was revoked. Those second refusals are the same denial the gate gives, and `RCA-001`
`FR-025` and `RCA-002` `FR-050` require them to reach the reader as the identical unavailable
surface rather than as a server error that tells them something happened.

**One named table rather than an `except` per route.** The report routes learned this first:
`_REPORT_REFUSALS` in `khepri.rra.report_api` exists because a mapping restated in each handler
drifts, one copy at a time. The shell has one refusal surface and no status to choose, so its
table is a tuple of types, used as `except SHELL_REFUSALS:`.

**Not `Exception`, deliberately.** An error this table does not name fails closed as a server
error, for `_refusal_for`'s reason: a failure nothing here governs is a fault to investigate, not
a refusal to render, and a broad `except` would silently absorb every future defect into the page
a reader is told means "unavailable".

**Only the types reachable from the routes that use it today:**

- `InvitationOperationFailed` -- `InvitationService.issue` when the store refuses the write.
- `ScopeAccessDenied` -- `IsolationService.resolve_scope`, which raises nothing else, when the
  decision surface's view reads re-resolve a scope the gate had admitted.

**Pending (#537):** `RoleChangeFailed` and `OrganizationCreationFailed` are `ValueError`s, so no
`PermissionError` handler catches them. No shell route calls the services that raise them yet;
when those surfaces are wired, their types must be added here, or a refused role change or
organization creation will reach the reader as a 500.
"""

from __future__ import annotations

from khepri.rca.errors import InvitationOperationFailed, ScopeAccessDenied

SHELL_REFUSALS: tuple[type[Exception], ...] = (
    InvitationOperationFailed,
    ScopeAccessDenied,
)

__all__ = ["SHELL_REFUSALS"]
