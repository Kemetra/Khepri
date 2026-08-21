# R7-05 Commercial HTTP Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose two commercial HTTP routes that reach an RRA analysis session only through the canonical authorization resolver, refusing every failure identically.

**Architecture:** A new route module in the composition root (`khepri/runtime/commercial_api.py`) declares a route group via the repo's `add_*_routes(app, *, services, clock)` seam. Each handler resolves the cookie token through `AuthorizationResolver.for_request(organization_id=None)`, then calls `CommercialBridge`. Both `AuthenticationFailed` and `ScopeAccessDenied` derive from `PermissionError`, so one `except PermissionError` produces the byte-identical `404` that `FR-025` requires.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, pytest. Existing: `AuthorizationResolver` (`khepri/rca/authorization_resolution.py`), `CommercialBridge` (`khepri/runtime/bridge.py`), `CommercialSessionCookie` (`khepri/rca/session_cookie.py:44`).

**Spec:** `docs/superpowers/specs/2026-08-21-r7-05-commercial-http-surface-design.md` (merged `f7aa78c`)

## Global Constraints

Every task's requirements implicitly include these. All are copied from `KHEPRI-DEC-022` §2/§3 and the spec; none may be renegotiated during implementation.

- **The endpoint calls `for_request`, never `resolve`.** `require_owner` is not used.
- **`for_request` is called with `organization_id=None`.** No route accepts an organization in path, query, or body.
- **The token comes from `CommercialSessionCookie` only** — never a body or query field.
- **Every refusal is `404` with an empty body.** No `401`, no `403`, no distinguishing body, no distinguishing header.
- **No authorization logic in the route.** `for_request` and `resolve_scope` are the only two checks.
- **`R6-01` §3.1 gains no new row.** The matrix tripwire's row count is unchanged.
- **`R6-08`'s tripwire is replaced, not relaxed.** Widening its allowlist while keeping its name is forbidden.
- **No schema change, no migration, no `redeem` change, no UI, no beta-mode change.**
- **Route prefix is `/api/v1/commercial`**, beside `/api/v1/beta`, not nested inside it.
- **Run tests with `./.venv/Scripts/python.exe -m pytest`.** Do not run `ruff format` (no CI format gate). Commit with `git -c commit.gpgsign=false commit -F -` (1Password signing is blocked).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/khepri/runtime/commercial_api.py` | **Create.** `CommercialServices` dataclass, `add_commercial_routes`, two handlers, the shared refusal helper. |
| `src/khepri/runtime/wiring.py` | **Modify.** Build the RCA service graph (first time in production) and pass `CommercialServices` into `build_web_app`. |
| `tests/test_r705_commercial_http_surface.py` | **Create.** Five evidence groups plus the three mutant-killing tests. |
| `tests/test_rca001_resolver_chokepoint.py` | **Modify.** Delete `test_the_resolver_has_no_production_consumer_yet`; add its inverse with an emptiness assertion. |
| `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` | **Modify.** §16 `R7` row: record `R7-05` merged, name `R7-06` next. |

Five tasks. Task 1 is the module with no wiring (unit-testable in isolation), Task 2 the wiring, Task 3 the security evidence, Task 4 the tripwire replacement, Task 5 the roadmap row. A reviewer can reject any one while approving its neighbours.

---

### Task 1: The route module

**Files:**
- Create: `src/khepri/runtime/commercial_api.py`
- Test: `tests/test_r705_commercial_http_surface.py`

**Interfaces:**
- Consumes: `CommercialBridge` from `khepri.runtime.bridge` (methods `open(*, account_id, organization_id, now) -> BetaSession` and `resume(*, account_id, organization_id, session_id, now) -> BetaSession | None`); `AuthorizationResolver.for_request(token, *, organization_id=None, now) -> AuthorizationContext`; `CommercialSessionCookie` from `khepri.rca.session_cookie`.
- Produces: `CommercialServices(resolver, bridge)` frozen dataclass and `add_commercial_routes(app, *, services, clock) -> None`. Task 2 imports both by these exact names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_r705_commercial_http_surface.py`. This first test asserts the null guard, because it is the requirement that keeps beta deployments untouched.

```python
"""The commercial HTTP surface (`R7-05`).

Authorized by `KHEPRI-DEC-022` §2. Every refusal in this file must be byte-identical: `FR-025`
requires that a caller cannot distinguish "not authorized" from "does not exist", and a test
checking each response against a literal would pass even if two causes diverged. The comparisons
here are therefore response-to-response.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.runtime.commercial_api import add_commercial_routes
from tests.rca_lifecycle_support import NOW


def test_an_unwired_app_declares_no_commercial_routes() -> None:
    """`KHEPRI-DEC-022` §3 forbids a beta-mode change, and this is how that is met.

    With no services the group is never declared, so a beta-only deployment has no commercial
    surface at all rather than one that exists and refuses.
    """
    app = FastAPI()
    add_commercial_routes(app, services=None, clock=lambda: NOW)

    paths = {route.path for route in app.routes}

    assert not any(path.startswith("/api/v1/commercial") for path in paths)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.runtime.commercial_api'`

- [ ] **Step 3: Write minimal implementation**

Create `src/khepri/runtime/commercial_api.py`:

```python
"""The commercial HTTP surface: an authorized RCA actor to an RRA analysis (`R7-05`).

**Authorized by `KHEPRI-DEC-022` §2**, which lifted `KHEPRI-DEC-021` §5's "No endpoint" bullet and
fixed four things this module may not depart from: `for_request` rather than `resolve`, the cookie
as the only token source, `R6-08`'s tripwire replaced rather than relaxed, and no new `R6-01` §3.1
row.

## Why this module is in `khepri.runtime`

`R7-07` asserts a flat prohibition in both directions -- `khepri.rca` imports no `khepri.rra`
module and `khepri.rra` imports no `khepri.rca` module. A route module needs `AuthorizationResolver`
(RCA) and `CommercialBridge` (which holds both), so an RRA-side module would pull `khepri.rca` into
that package and fail that test. The composition root is the one layer allowed to know both sides,
and it is what the built wheel ships.

## Every refusal is one `404`

`AuthenticationFailed` and `ScopeAccessDenied` both derive from `PermissionError`
(`rca/errors.py:33`, `:37`), so a single handler covers both and the uniformity is structural
rather than a convention two branches must remember. A missing analysis returns the same thing,
because `resume` returning `None` and a refusal must be indistinguishable (`FR-025`).

**No organization is named in a request.** `for_request` is called with `organization_id=None`, so
the session's active organization is used. `KHEPRI-DEC-022` §2 requires any request-named
organization be compared; this satisfies it by admitting no such parameter, so there is no path on
which the comparison could be skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.session_cookie import CommercialSessionCookie
from khepri.runtime.bridge import CommercialBridge

COMMERCIAL_PREFIX = "/api/v1/commercial"


@dataclass(frozen=True, slots=True)
class CommercialServices:
    """The two collaborators, one from each side, paired only here."""

    resolver: AuthorizationResolver
    bridge: CommercialBridge


class AnalysisResponse(BaseModel):
    session_id: str


def _not_found() -> HTTPException:
    """The single refusal. Empty body, no detail, no distinguishing header.

    Returned for a missing cookie, an expired or revoked session, a non-member, a disabled
    account, an unknown organization, an absent analysis, and another scope's analysis. A caller
    able to tell these apart enumerates organizations one probe at a time, which `FR-004` and
    `FR-022` forbid and `R6-03` already closed on the switch path.
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def add_commercial_routes(
    app: FastAPI,
    *,
    services: CommercialServices | None,
    clock: Callable[[], datetime],
) -> None:
    """Declare the commercial route group, or declare nothing at all.

    The null guard is load-bearing: unwired, the routes do not exist, so `KHEPRI-DEC-022` §3's
    no-beta-change requirement is met structurally rather than by a test asserting nothing moved.
    """
    if services is None:
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Write the failing test for the two routes**

Append to `tests/test_r705_commercial_http_surface.py`. `_Stub*` classes stand in for the real
collaborators so this task tests the route contract without a database; Task 3 drives the real graph.

```python
from dataclasses import dataclass as _dc

from khepri.rca.errors import SCOPE_FAILURE, AuthenticationFailed, ScopeAccessDenied
from khepri.runtime.commercial_api import CommercialServices


@_dc
class _StubContext:
    account_id: str
    organization_id: str | None


class _StubResolver:
    """Returns a fixed context, or raises whatever it was given."""

    def __init__(self, context: _StubContext | None = None, raises: Exception | None = None) -> None:
        self._context = context or _StubContext("acct-1", "org-1")
        self._raises = raises
        self.calls: list[tuple[str, str | None]] = []

    def for_request(self, token, *, organization_id=None, now):
        self.calls.append(("for_request", token, organization_id))
        if self._raises is not None:
            raise self._raises
        return self._context

    def resolve(self, token, *, now):
        """Defined deliberately, so mutant 1 fails an assertion rather than an `AttributeError`.

        If this method did not exist, swapping `for_request` for `resolve` in the handler would
        raise `AttributeError` and the test would "die" without ever checking the property it
        claims to check. A mutant killed for the wrong reason proves nothing.
        """
        self.calls.append(("resolve", token, None))
        if self._raises is not None:
            raise self._raises
        return self._context


@_dc
class _StubSession:
    session_id: str


class _StubBridge:
    def __init__(self, session: _StubSession | None = None, raises: Exception | None = None) -> None:
        self._session = session
        self._raises = raises

    def open(self, *, account_id, organization_id, now):
        if self._raises is not None:
            raise self._raises
        return self._session or _StubSession("sess-1")

    def resume(self, *, account_id, organization_id, session_id, now):
        if self._raises is not None:
            raise self._raises
        return self._session


def _client(resolver: object, bridge: object) -> TestClient:
    app = FastAPI()
    add_commercial_routes(
        app,
        services=CommercialServices(resolver=resolver, bridge=bridge),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return TestClient(app)


def test_opening_an_analysis_returns_its_identifier() -> None:
    client = _client(_StubResolver(), _StubBridge(_StubSession("sess-9")))

    response = client.post("/api/v1/commercial/analyses", cookies={"khepri_session": "tok"})

    assert response.status_code == 201
    assert response.json() == {"session_id": "sess-9"}


def test_resuming_a_known_analysis_returns_it() -> None:
    client = _client(_StubResolver(), _StubBridge(_StubSession("sess-9")))

    response = client.get(
        "/api/v1/commercial/analyses/sess-9", cookies={"khepri_session": "tok"}
    )

    assert response.status_code == 200
    assert response.json() == {"session_id": "sess-9"}


def test_the_resolver_is_called_with_no_organization() -> None:
    """The mutant this kills: passing a request value as `organization_id`.

    `organization_id=None` is what makes the session's active organization authoritative. A route
    that sourced it from the request would put a caller-supplied identifier on the authorization
    path, which `R6-01` §5 forbids.
    """
    resolver = _StubResolver()
    client = _client(resolver, _StubBridge(_StubSession("sess-9")))

    client.post("/api/v1/commercial/analyses", cookies={"khepri_session": "tok"})

    assert resolver.calls == [("for_request", "tok", None)]
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: 3 FAIL with `404` (routes not declared yet); 1 PASS

- [ ] **Step 7: Implement the two routes**

Append inside `add_commercial_routes`, after the `if services is None: return` guard:

```python
    @app.post(
        f"{COMMERCIAL_PREFIX}/analyses",
        response_model=AnalysisResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def open_analysis(session: CommercialSessionCookie = None) -> AnalysisResponse:
        """Authorize the caller, then open an analysis in their active organization's scope."""
        if session is None:
            raise _not_found()
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=None, now=now)
            opened = services.bridge.open(
                account_id=context.account_id,
                organization_id=context.organization_id,
                now=now,
            )
        except PermissionError as refusal:
            raise _not_found() from refusal
        return AnalysisResponse(session_id=opened.session_id)

    @app.get(
        f"{COMMERCIAL_PREFIX}/analyses/{{session_id}}",
        response_model=AnalysisResponse,
    )
    def resume_analysis(
        session_id: str, session: CommercialSessionCookie = None
    ) -> AnalysisResponse:
        """Re-authorize, then read one analysis within the resolved scope.

        `session_id` is an object identifier and confers nothing (`FR-023`). The bridge re-resolves
        before it reads and keeps the owner predicate in the store's statement, so this handler
        adds no check of its own.
        """
        if session is None:
            raise _not_found()
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=None, now=now)
            resumed = services.bridge.resume(
                account_id=context.account_id,
                organization_id=context.organization_id,
                session_id=session_id,
                now=now,
            )
        except PermissionError as refusal:
            raise _not_found() from refusal
        if resumed is None:
            raise _not_found()
        return AnalysisResponse(session_id=resumed.session_id)
```

Add to the end of the module:

```python
__all__ = ["COMMERCIAL_PREFIX", "AnalysisResponse", "CommercialServices", "add_commercial_routes"]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: PASS (4 passed)

- [ ] **Step 9: Write the uniform-refusal matrix test**

Append. This is the test the `403` mutant must die against.

```python
import pytest

_REFUSALS = [
    pytest.param(_StubResolver(raises=AuthenticationFailed("no")), _StubBridge(), id="auth-failed"),
    pytest.param(
        _StubResolver(raises=ScopeAccessDenied(SCOPE_FAILURE)), _StubBridge(), id="not-a-member"
    ),
    pytest.param(
        _StubResolver(), _StubBridge(raises=ScopeAccessDenied(SCOPE_FAILURE)), id="scope-denied"
    ),
    pytest.param(_StubResolver(), _StubBridge(None), id="absent-analysis"),
]


@pytest.mark.parametrize(("resolver", "bridge"), _REFUSALS)
def test_every_refusal_looks_the_same(resolver: object, bridge: object) -> None:
    """One parametrized case, so a new refusal cause cannot be added without a row here."""
    client = _client(resolver, bridge)

    response = client.get(
        "/api/v1/commercial/analyses/sess-9", cookies={"khepri_session": "tok"}
    )

    assert response.status_code == 404
    assert response.content == b""


def test_a_missing_cookie_is_refused_identically_to_a_denied_scope() -> None:
    """Compared response-to-response, not each against a literal.

    A test asserting `404` for both would still pass if one grew a body. Comparing the two is what
    holds them together.
    """
    absent = _client(_StubResolver(), _StubBridge(None)).get(
        "/api/v1/commercial/analyses/sess-9", cookies={"khepri_session": "tok"}
    )
    no_cookie = _client(_StubResolver(), _StubBridge(None)).get(
        "/api/v1/commercial/analyses/sess-9"
    )

    assert (absent.status_code, absent.content) == (no_cookie.status_code, no_cookie.content)
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: PASS (10 passed)

If `test_every_refusal_looks_the_same` fails on `response.content == b""`, FastAPI is serialising
`HTTPException`'s default detail. Pass an explicit empty response instead — return
`Response(status_code=404)` from a handler rather than raising — and keep the assertion; do not
weaken the assertion to accommodate a body.

- [ ] **Step 11: Verify the gates**

Run: `./.venv/Scripts/khepri-gov.exe validate && ./.venv/Scripts/python.exe -m ruff check .`
Expected: `Governance validation passed.` and `All checks passed!`

- [ ] **Step 12: Commit**

```bash
git add src/khepri/runtime/commercial_api.py tests/test_r705_commercial_http_surface.py
git -c commit.gpgsign=false commit -F - <<'MSG'
feat(r7): add the commercial route group behind the canonical resolver (R7-05)

Two routes, both reaching `CommercialBridge` only through
`for_request(organization_id=None)`. No organization is accepted in a
path, query, or body, so there is no path on which the comparison
`KHEPRI-DEC-022` §2 requires could be skipped.

Every refusal is one `404` with an empty body. Both `AuthenticationFailed`
and `ScopeAccessDenied` derive from `PermissionError`, so one handler
covers them and the uniformity is structural rather than two branches
remembering to agree. The matrix test is parametrized so a new cause
cannot be added without a row, and one case compares two responses to
each other rather than each against a literal.

The null-services guard is load-bearing: unwired, the routes are never
declared, so §3's no-beta-change requirement is met structurally.

Not wired into the production graph yet -- that is the next slice.
MSG
```

---

### Task 2: Wire it into the production graph

**Files:**
- Modify: `src/khepri/runtime/wiring.py`
- Test: `tests/test_r705_commercial_http_surface.py`

**Interfaces:**
- Consumes: `CommercialServices` and `add_commercial_routes` from Task 1.
- Produces: `build_commercial_services(stack) -> CommercialServices`, and `build_web_app` now declaring the commercial group.

**Note:** `build_stack` currently builds **no RCA services at all** — it is entirely RRA plus S3. This task constructs the RCA graph in production for the first time, so it is more than one line.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_r705_commercial_http_surface.py`:

```python
from khepri.runtime.wiring import build_commercial_services


def test_the_web_app_declares_the_commercial_group() -> None:
    """The wiring exists and reaches the routes.

    `runtime_stack()` in `tests/test_runtime_wiring.py:46` is a plain function, **not** a pytest
    fixture -- it is called directly and builds against `AwsClientStub`. Import it rather than
    writing a second stack builder.
    """
    from tests.test_runtime_wiring import runtime_stack

    from khepri.runtime.wiring import build_web_app

    app = build_web_app(runtime_stack())

    paths = {route.path for route in app.routes}

    assert "/api/v1/commercial/analyses" in paths
    assert "/api/v1/commercial/analyses/{session_id}" in paths


def test_commercial_services_holds_a_real_resolver_and_bridge() -> None:
    from tests.test_runtime_wiring import runtime_stack

    services = build_commercial_services(runtime_stack())

    assert isinstance(services, CommercialServices)
    assert services.resolver is not None
    assert services.bridge is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -k wired -v`
Expected: FAIL with `ImportError: cannot import name 'build_commercial_services'`

`runtime_stack` is a function, not a fixture, so it takes no pytest parameter — it must be
called as `runtime_stack()`. Do not add a second stack builder; `test_runtime_wiring.py` already
owns the one that stubs S3.

- [ ] **Step 3: Implement the wiring**

Add these imports to `src/khepri/runtime/wiring.py`:

```python
from khepri.rca.actor_resolution import ActorResolver
from khepri.rca.authorization_resolution import AuthorizationResolver
from khepri.rca.isolation import IsolationService
from khepri.rca.lifecycle import LifecycleService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.session_persistence import SqlSessionStore as SqlRcaSessionStore
from khepri.runtime.bridge import CommercialBridge
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
```

**There is a name collision, and it matters.** `wiring.py` already imports RRA's `SqlSessionStore`
(`wiring.py:35`, used at `:121`), so the RCA one is aliased to `SqlRcaSessionStore` above. The
bridge's `store=` argument takes the **RRA** class, unaliased; `ActorResolver` takes the RCA one. A
bare `SqlSessionStore` in this function resolves to the RRA class correctly but by accident, so both
are spelled distinctly below.

Add this function above `build_web_app`:

```python
def build_commercial_services(stack: RuntimeStack) -> CommercialServices:
    """Build the RCA half of the graph and pair it with the bridge.

    This is the first place `khepri.rca` is constructed in the production composition root.
    `KHEPRI-DEC-021` §3 admits the import here deliberately: a composition root exists to know
    about both sides, and what the boundary forbids is a bridge *inside* either package.

    The store construction mirrors `tests/test_r703_live_authorization_on_resume.py:107-117`, which
    is the shape `R7-03` proved the two live gates against.
    """
    accounts = SqlAccountStore(stack.factory)
    organizations = SqlOrganizationStore(stack.factory)
    actors = ActorResolver(
        SqlRcaSessionStore(stack.factory),
        LifecycleService(accounts, organizations),
    )
    return CommercialServices(
        resolver=AuthorizationResolver(actors, organizations),
        bridge=CommercialBridge(
            isolation=IsolationService(organizations, accounts),
            store=SqlSessionStore(stack.factory),
        ),
    )
```

Then in `build_web_app`, capture the app and declare the group:

```python
def build_web_app(stack: RuntimeStack) -> FastAPI:
    app = create_app(
        service=stack.services.invitations,
        clock=stack.clock,
        intake_service=stack.services.intake,
        deletion_service=stack.services.deletion,
        profiling_service=stack.services.profiling,
        package_service=stack.services.packages,
        report_services=build_report_services(stack),
        journey_services=JourneyServices(reader=SqlJourneyReader(stack.factory)),
    )
    add_commercial_routes(
        app,
        services=build_commercial_services(stack),
        clock=stack.clock,
    )
    return app
```

Add `"build_commercial_services"` to `__all__`, keeping it alphabetically ordered.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Confirm beta routes are untouched**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r704_beta_preservation.py -v`
Expected: PASS, with **no edits to that file**. `KHEPRI-DEC-022` §3 requires `R7-04`'s regressions
stay green unmodified. If one fails, the wiring changed beta behaviour — fix the wiring, never the
regression test.

- [ ] **Step 6: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: `test_the_resolver_has_no_production_consumer_yet` **FAILS**. This is correct and
expected — a production consumer now exists, which is exactly what that tripwire watches for.
Task 4 replaces it. Note any other failure and stop.

- [ ] **Step 7: Commit**

```bash
git add src/khepri/runtime/wiring.py tests/test_r705_commercial_http_surface.py
git -c commit.gpgsign=false commit -F - <<'MSG'
feat(r7): wire the commercial route group into the web role (R7-05)

`build_stack` built no RCA services, so this constructs that half of the
graph in the production composition root for the first time. The store
construction mirrors `R7-03`'s test helper, which is the shape the two
live gates were proved against.

`R6-08`'s `test_the_resolver_has_no_production_consumer_yet` now fails by
design: a production consumer exists. `KHEPRI-DEC-022` §2 requires it be
replaced rather than relaxed, which is the next commit.

`R7-04`'s beta regressions pass unmodified.
MSG
```

---

### Task 3: Security evidence against the real graph

**Files:**
- Modify: `tests/test_r705_commercial_http_surface.py`

**Interfaces:**
- Consumes: everything from Tasks 1–2, plus the `factory` fixture from `tests.rca_lifecycle_support`.
- Produces: no production symbols.

Task 1's tests use stubs and prove the route contract. These drive the real resolver, bridge and
database, and prove the properties `FR-025` and `FR-030` require.

- [ ] **Step 1: Write the cross-organization test**

Append. Build the journey with the same helpers `tests/test_r703_live_authorization_on_resume.py`
uses (`_resolver`, `_isolation`, `_account`, and the `factory` fixture) — read that file's lines
107–130 and reuse its construction rather than writing a second one.

```python
def test_another_organizations_analysis_is_indistinguishable_from_an_absent_one(
    factory,
) -> None:
    """`FR-025`, at the HTTP layer.

    Actor B resumes actor A's analysis and gets exactly what a nonexistent identifier returns. The
    two responses are compared to each other: asserting `404` twice would pass even if one grew a
    body that named the owner.
    """
    # Build two organizations, each with one member, using the R7-03 helpers.
    # Open an analysis as A, then attempt it as B.
    foreign = client_b.get(f"/api/v1/commercial/analyses/{a_session_id}", cookies=b_cookie)
    absent = client_b.get("/api/v1/commercial/analyses/does-not-exist", cookies=b_cookie)

    assert (foreign.status_code, foreign.content) == (absent.status_code, absent.content)
```

- [ ] **Step 2: Write the live-authorization tests**

```python
def test_a_revoked_member_cannot_resume_through_the_route(factory) -> None:
    """`FR-030` at the HTTP layer: the route does not cache the decision.

    `R7-03` proved the bridge re-resolves. This proves the handler does not hold a context across
    calls or skip the resolver on a second request.
    """


def test_a_disabled_account_cannot_resume_through_the_route(factory) -> None:
    """`FR-008`: no dependence on session expiry. No time passes in this test."""


def test_a_demoted_owner_can_still_resume_through_the_route(factory) -> None:
    """The negative case, and it is what keeps the guard from being a blanket refusal.

    A demoted owner is still a member, so they keep access. A test suite with only refusals would
    pass against a route that refused everyone.
    """
```

Fill each body using the R7-03 journey helpers; the docstrings state exactly what each must assert.

- [ ] **Step 3: Run tests to verify they fail, then pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py -v`
Expected: the four new tests fail while unwritten, then pass once each body is filled. The
demoted-owner test must pass with a **`200`**, not a `404`; if it 404s, the guard is refusing a
member and the bug is in the route or wiring, not the test.

- [ ] **Step 4: Verify the three mutants**

For each, apply the change, run the named test, confirm it FAILS, then revert. **Check the mutant
actually introduces the defect before concluding anything** — a malformed mutant proves nothing
(`#231` records this).

| Mutant | Apply | Expected to fail |
|---|---|---|
| 1 | In `commercial_api.py`, change `for_request` to `resolve` (drop the `organization_id` kwarg) | `test_the_resolver_is_called_with_no_organization` -- it must fail on the recorded call name, **not** on `AttributeError`. `_StubResolver` defines `resolve` for exactly this reason. |
| 2 | Change `HTTP_404_NOT_FOUND` to `HTTP_403_FORBIDDEN` in `_not_found` | `test_every_refusal_looks_the_same` and `test_a_missing_cookie_is_refused_identically_to_a_denied_scope` |
| 3 | Delete the `if services is None: return` guard | `test_an_unwired_app_declares_no_commercial_routes` |

Record the surviving/killed result for each in the commit message. If any mutant survives, the test
is weak — fix the test, not the mutant.

- [ ] **Step 5: Commit**

```bash
git add tests/test_r705_commercial_http_surface.py
git -c commit.gpgsign=false commit -F - <<'MSG'
test(r7): prove the commercial surface refuses uniformly and live (R7-05)

Four journeys against the real resolver, bridge and database rather than
stubs: a foreign organization's analysis is byte-identical to an absent
one, a revoked member and a disabled account are refused mid-session, and
a demoted owner still resumes -- the negative case that keeps the guard
from being a blanket refusal.

Three mutants verified, each killed by a named test: `for_request` to
`resolve`, `404` to `403`, and dropping the null-services guard.
MSG
```

---

### Task 4: Replace `R6-08`'s tripwire

**Files:**
- Modify: `tests/test_rca001_resolver_chokepoint.py:465` (delete `test_the_resolver_has_no_production_consumer_yet`)

**Interfaces:** none — test-only.

`KHEPRI-DEC-022` §2: replaced, **not relaxed**. Widening its allowlist while keeping its name would
leave the name asserting something false.

- [ ] **Step 1: Read the existing test and its helpers**

Run: `sed -n '455,495p' tests/test_rca001_resolver_chokepoint.py`

Note `_production_sources()` and `_relative()` — the replacement reuses both.

- [ ] **Step 2: Delete the old test and write its inverse**

Replace the whole `test_the_resolver_has_no_production_consumer_yet` function with:

```python
    def test_the_only_resolver_consumer_is_the_commercial_route_module(self) -> None:
        """The tripwire, now confirmatory rather than preventative (`KHEPRI-DEC-022` §2).

        `R7-05` filled the room the previous version guarded: `commercial_api.py` consumes
        `AuthorizationResolver`. The claim is now that it is the *only* consumer, so a second
        handler reaching the resolver directly -- the bypass this has always watched for -- fails
        here.

        The emptiness assertion is not decoration. A scan that finds nothing passes every
        assertion about what it found, so without it this test would go green if
        `_production_sources` ever stopped matching the tree.
        """
        importers = sorted(
            _relative(path)
            for path in _production_sources()
            if _relative(path) != "khepri/rca/authorization_resolution.py"
            and "AuthorizationResolver" in path.read_text(encoding="utf-8")
        )

        assert importers, "the scan found no files at all -- _production_sources is not matching"
        assert importers == ["khepri/runtime/commercial_api.py"]
```

Match the surrounding class's indentation and the exact predicate the original used for
`_production_sources` / `_relative`.

- [ ] **Step 3: Run the file**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_rca001_resolver_chokepoint.py -v`
Expected: PASS, with no `test_the_resolver_has_no_production_consumer_yet` in the output.

- [ ] **Step 4: Mutation-check the emptiness assertion**

Temporarily make `_production_sources()` return `[]`. Run the test. It must FAIL on the emptiness
assertion, not pass. Revert.

This is the guard-that-cannot-see-the-new-surface shape: a scan finding nothing must fail, never
pass quietly.

- [ ] **Step 5: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: all pass. If `R6-05`'s matrix tripwire fails, update **only its consumer inventory** —
`KHEPRI-DEC-022` §2's fourth bullet says it gets no new matrix row.

- [ ] **Step 6: Commit**

```bash
git add tests/test_rca001_resolver_chokepoint.py
git -c commit.gpgsign=false commit -F - <<'MSG'
test(r6): flip the resolver tripwire from preventative to confirmatory (R7-05)

`test_the_resolver_has_no_production_consumer_yet` guarded an empty room
and said so in its docstring. `R7-05` filled it, so the test is deleted
and replaced per `KHEPRI-DEC-022` §2 -- relaxing it while keeping its name
would leave the name asserting something false.

The replacement claims `commercial_api.py` is the only production
consumer, and carries an emptiness assertion: a scan that matched nothing
would otherwise satisfy every claim about what it found. Verified by
stubbing the scan to return nothing and confirming the test fails.
MSG
```

---

### Task 5: Reconcile the roadmap row

**Files:**
- Modify: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` (§16 `R7` row, ~line 1489)

**Interfaces:** none — docs-only.

§16 is the one document a slice's DoD never touches, which is how it went stale twice already
(`#228` → `#230`). This task exists so it does not happen a third time.

- [ ] **Step 1: Read the current row**

Run: `git grep -n "R7 Commercial RRA bridge" docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`

The row currently ends with **"`R7-05` is now the next task**, and `R7-06` follows it." That clause
is what this replaces.

- [ ] **Step 2: Update the row**

Replace that clause with a record of what landed: `R7-05` merged at ⟨this PR's squash sha⟩, the
module it added (`khepri/runtime/commercial_api.py`), the four `KHEPRI-DEC-022` §2 bounds it
honoured, the three verified mutants, `R6-08`'s tripwire flipped from preventative to confirmatory,
and `R6-01` §3.1 unchanged. State which of the twelve `RCA-001` requirements are **reached** versus
**closed** — do not claim closure the tests do not show. End by naming `R7-06` next.

Keep the row a single line with four pipe-delimited cells and the status `READY_FOR_IMPLEMENTATION`
(`R7-06` is still open, so the program is not `MERGED`).

- [ ] **Step 3: Verify row integrity**

```bash
./.venv/Scripts/python.exe -c "
import io
L=io.open('docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md',encoding='utf-8').read().split(chr(10))
r=[l for l in L if l.startswith('| R7 Commercial RRA bridge')]
assert len(r)==1, f'rows: {len(r)}'
assert r[0].count('|')==4, f'cells: {r[0].count(chr(124))}'
assert 'is now the next task' not in r[0] or 'R7-06' in r[0]
print('[OK] row intact')
"
```

- [ ] **Step 4: Verify the gates**

Run: `./.venv/Scripts/khepri-gov.exe validate && ./.venv/Scripts/python.exe -m ruff check .`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md
git -c commit.gpgsign=false commit -F - <<'MSG'
docs(r0): reconcile the R7 row with R7-05 merged (R7-05)

Folded into this PR rather than left to a follow-up: §16 is the one
document a slice's DoD never touches, and it went stale twice already.

Records what the slice proved rather than that it landed, states which of
the twelve `RCA-001` requirements are reached versus closed, and names
`R7-06` next.
MSG
```

---

## Self-Review

**1. Spec coverage.** Every section of the design note maps to a task: §1–2 (module, seam) → Task 1;
§3–5 (routes, no organization, authorization path) → Task 1; §6 (uniform `404`) → Task 1 steps 9–10
and Task 3; §7 groups 1–4 → Tasks 1 and 3; §7 group 5 (tripwire) → Task 4; §7's mutation requirement
→ Task 3 step 4 and Task 4 step 4. §8's non-goals are excluded by construction — no task adds
pagination, a payload beyond `session_id`, or a UI.

**2. Placeholder scan.** Task 3's step 1–2 bodies are deliberately partial: they give the docstring,
the assertion shape, and a pointer to the R7-03 helpers to reuse rather than duplicating ~100 lines
of journey construction. Every other step carries runnable code. Task 5's row text is described
rather than written because it must embed a squash SHA that does not exist until the PR merges.

**3. Type consistency.** `CommercialServices(resolver, bridge)` is defined in Task 1 and consumed
under that exact name in Task 2. `add_commercial_routes(app, *, services, clock)` is consistent in
both. `build_commercial_services(stack)` is defined and exported once. `AnalysisResponse.session_id`
is the only response field in both routes. `_not_found()` is the single refusal constructor.

**Known risk flagged for the executor:** `HTTPException` may serialise a default `detail` body,
which would break the `response.content == b""` assertion. Task 1 step 10 names the fix (return
`Response(status_code=404)` instead of raising) and forbids the wrong fix (weakening the assertion).
