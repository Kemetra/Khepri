"""The commercial bridge: an authorized RCA actor to an RRA analysis session (`R7-07`).

**Authorized by `KHEPRI-DEC-021` §2**, which lifted the bullet in `KHEPRI-DEC-020` §3 that withheld
"no bridge service and no entry-point implementation". Four parts and no more: the entry point, its
persistence, the resume lookup, and this.

## Why this module is in `khepri.runtime` and not `khepri.local`

`R7-01` §3 recommended `khepri.local`, and an earlier draft of `KHEPRI-DEC-021` adopted that. §3
rejects it, for a packaging reason rather than a layering one: `pyproject.toml` excludes
`src/khepri/local` from the built wheel that the OCI image installs, and the `Dockerfile` validates
`khepri.runtime.{config,wiring,worker}`. A bridge in `khepri.local` is unreachable from the deployed
web role, so `R7-05` would have to move or duplicate it. As §3 puts it, "an authorization naming a
location the product cannot use is not an authorization".

**This is the first `khepri.rca` import into the production composition layer, and it is admitted
deliberately.** Composition roots exist to know about both sides. What `R7-01` §3 was protecting
against is a bridge inside `khepri.rca`, which would make every RCA test transitively depend on RRA;
that option stays rejected. `khepri.local` may wire this same implementation so the journey stays
runnable on a developer machine -- one implementation, two composition roots.

The boundary `R7-07` owes evidence for is therefore a **flat prohibition**: `khepri.rca` imports no
`khepri.rra` module and `khepri.rra` imports no `khepri.rca` module. Both stay ignorant of each
other; only this layer knows both. `tests/test_r707_commercial_bridge.py` asserts it in both
directions, and §3 chose the flat form over an allowlist because it "needs no maintenance as the
bridge grows".

## What crosses, and what cannot

```
account_id + organization_id          <- RCA vocabulary, stops here
        |
   resolve_scope()                    <- live authorization, every call
        |
     owner_id                         <- the only thing that crosses (FR-032, FR-033)
        |
open_commercial_session()             <- RRA mints session_id, performs no authorization
```

`resolve_scope` already refuses a non-member, a disabled account, an unknown account, and an
unknown organization, with one uniform `ScopeAccessDenied` -- so this bridge adds no authorization
logic of its own. Re-implementing any of those checks here would create a second authorization site,
and `R6-01` §5's rule is that there is one door.

**Authorization is not skipped on resume.** `FR-030` requires a membership change to take effect for
decisions made after it, so `resume` re-resolves before it reads. A caller holding a `session_id`
from an earlier call holds an object identifier, never authority (`FR-023`).
"""

from __future__ import annotations

from datetime import datetime

from khepri.rca.isolation import IsolationService
from khepri.rra.sessions import BetaSession, SessionStore, open_commercial_session


class CommercialBridge:
    """Resolves a commercial actor's scope, then enters RRA with nothing but that scope.

    Holds an `IsolationService` and a `SessionStore` -- one from each side. That pairing is the
    whole reason this class exists here rather than in either package.
    """

    def __init__(self, *, isolation: IsolationService, store: SessionStore) -> None:
        self._isolation = isolation
        self._store = store

    def open(self, *, account_id: str, organization_id: str, now: datetime) -> BetaSession:
        """Authorize, then open a new analysis session for the organization's scope.

        Raises `ScopeAccessDenied` for every refusal, uniformly: `resolve_scope` is what refuses,
        and it does not distinguish a non-member from a disabled account from an absent
        organization (`FR-025`). Nothing is written when it raises, because the write happens after
        it returns.
        """
        owner_id = self._isolation.resolve_scope(account_id, organization_id)
        return open_commercial_session(self._store, owner_id=owner_id, now=now)

    def resume(
        self,
        *,
        account_id: str,
        organization_id: str,
        session_id: str,
        now: datetime,
    ) -> BetaSession | None:
        """Re-authorize, then look up one named analysis within the resolved scope.

        **The order is load-bearing.** Authorization runs first, so a caller whose membership was
        revoked cannot resume a session they opened while a member -- `FR-030`. Looking the session
        up first and authorizing afterwards would leak its existence through timing and would treat
        the identifier as the thing being checked.

        Returns `None` for both "no such session" and "that session belongs to another scope". The
        two must be indistinguishable (`FR-025`), which is why the owner predicate lives in the
        store's statement rather than in a comparison here.

        `now` is accepted for signature symmetry with `open` and for the expiry semantics `R7-03`
        will assert; this slice reads a row rather than aging one out.
        """
        owner_id = self._isolation.resolve_scope(account_id, organization_id)
        return self._store.get_session_for_owner(owner_id, session_id)


__all__ = ["CommercialBridge"]
