# R7-06 Commercial E2E and Consent Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a commercial actor a way to consent, then prove end-to-end that the commercial surface closes every `RCA-001` requirement `R7` moves.

**Architecture:** One route is added to the existing `commercial_api.py` route group, following the two handlers already there: resolve the cookie through `for_request`, confirm the named analysis belongs to the resolved scope through `CommercialBridge.resume`, then call the existing `InvitationService.record_consent`. `CommercialServices` grows a third field for the consent recorder. Evidence lives in one new test module reusing `R7-03`'s `Journey` fixture.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.x, pytest. Existing: `AuthorizationResolver.for_request`, `CommercialBridge.resume`, `InvitationService.record_consent` (`rra/sessions.py:177`), `ConsentVersion` (`rra/api.py:48`), `_not_found()` (`runtime/commercial_api.py`).

**Spec:** `docs/superpowers/specs/2026-08-21-r7-06-commercial-e2e-design.md` (committed this branch)

## Global Constraints

Every task's requirements implicitly include these. Copied from `KHEPRI-DEC-023` §2/§3 and `KHEPRI-DEC-022` §2 (carried forward by `-023` §1); none may be renegotiated during implementation.

- **The route calls `for_request`, never `resolve`.** `organization_id=None`; no route accepts an organization.
- **`bridge.resume` runs before anything is written.** It is the scope check, not a redundant read.
- **Reuse `InvitationService.record_consent`.** Add no consent logic; `require_upload_consent` stays the single enforcement point and is **not** called from the route.
- **Every refusal is the same empty-body `404`** via the existing `_not_found()`. **No `409`**, no `403`, no distinguishing body. Absent, another scope's, expired, and missing-cookie are indistinguishable.
- **Consenting twice is not an error.** Refusing it would require distinguishing "already consented" from "not yours".
- **`204 No Content` on success**, matching the beta route.
- **Token from `CommercialSessionCookie` only.**
- **No schema change, no migration, no `redeem` change, no beta-route change, no change to `require_upload_consent`, no UI, no `RCA-001` amendment.**
- **`R7-04`'s beta regressions must stay green unmodified.**
- **Run tests with `./.venv/Scripts/python.exe -m pytest`** (full suite takes ~3.5 min — use a timeout above 240s). Do not run `ruff format`. Commit with `git -c commit.gpgsign=false commit -F -`.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/khepri/runtime/commercial_api.py` | **Modify.** Add `ConsentRequest` model, a third `CommercialServices` field, and the consent route. |
| `src/khepri/runtime/wiring.py` | **Modify.** Pass the consent recorder into `CommercialServices` in `build_commercial_services`. |
| `tests/test_r706_commercial_e2e.py` | **Create.** Five evidence groups plus the `FR-024` absence test. |
| `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` | **Modify.** §16 `R7` row → `MERGED`. |

Four tasks: the route (with its unit tests), the E2E evidence, the mutant verification, the roadmap row. A reviewer can reject any one while approving its neighbours.

---

### Task 1: The consent route

**Files:**
- Modify: `src/khepri/runtime/commercial_api.py`
- Modify: `src/khepri/runtime/wiring.py`
- Test: `tests/test_r706_commercial_e2e.py`

**Interfaces:**
- Consumes: `CommercialServices(resolver, bridge)` and `add_commercial_routes(app, *, services, clock)` from `R7-05`; `_not_found() -> Response`; `InvitationService.record_consent(session_id, *, consent_version, now) -> BetaSession`.
- Produces: `CommercialServices(resolver, bridge, consent)` — a **third field**, so every existing construction site must be updated. `ConsentRequest` pydantic model with one field `consent_version: ConsentVersion`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_r706_commercial_e2e.py`:

```python
"""Commercial end-to-end evidence and the consent route (`R7-06`).

Authorized by `KHEPRI-DEC-023` §2. This is the last task in `R7`.

Every refusal asserted here must be byte-identical, and the comparisons are response-to-response
rather than each against a literal: a suite checking `404` twice would pass even if one cause grew a
body. `FR-024` is asserted as an **absence** rather than a behaviour, because no commercial route
accepts an organization and a test named for it that passed on a missing parameter could not fail.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.persistence import SqlOrganizationStore
from khepri.rra.sessions import InvitationService
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from tests.rca_lifecycle_support import NOW, factory_fixture  # noqa: F401 -- fixture
from tests.test_r703_live_authorization_on_resume import (  # noqa: F401 -- fixture re-export
    Journey,
    _account,
    _rca_sessions,
    journey_fixture,
)
from tests.test_r703_live_authorization_on_resume import _resolver as _r703_resolver


def _client(journey: Journey) -> TestClient:
    """The real graph: `R7-03`'s journey wired through the production route group."""
    app = FastAPI()
    add_commercial_routes(
        app,
        services=CommercialServices(
            resolver=_r703_resolver(journey.factory),
            bridge=journey.bridge,
            consent=InvitationService(journey.rra_store),
        ),
        clock=lambda: NOW,
    )
    return TestClient(app)


def test_a_member_can_consent_to_their_own_analysis(journey: Journey) -> None:
    """The route exists, authorizes, and records through the existing service."""
    response = _client(journey).post(
        f"/api/v1/commercial/analyses/{journey.session_id}/consent",
        json={"consent_version": "v1"},
        cookies={"khepri_session": journey.member_token},
    )

    assert response.status_code == 204
    assert response.content == b""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -v`
Expected: FAIL with `TypeError: CommercialServices.__init__() got an unexpected keyword argument 'consent'`

- [ ] **Step 3: Add the third field and the request model**

In `src/khepri/runtime/commercial_api.py`, add to the imports:

```python
from pydantic import BaseModel, ConfigDict, StringConstraints
from typing import Annotated

from khepri.rra.sessions import InvitationService
```

Add the constrained type and model beside `AnalysisResponse`:

```python
ConsentVersion = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class ConsentRequest(BaseModel):
    """Mirrors `rra/api.py:65`'s model deliberately.

    `min_length=1` after stripping is what keeps `record_consent`'s `ValueError` unreachable: that
    exception is not a `PermissionError`, so it would escape the handler's `except PermissionError`
    as a `500`. Pydantic refuses an empty version with a `422` before the service is called.
    """

    model_config = ConfigDict(extra="forbid")

    consent_version: ConsentVersion
```

Extend the dataclass:

```python
@dataclass(frozen=True, slots=True)
class CommercialServices:
    """The collaborators, one from each side, paired only here."""

    resolver: AuthorizationResolver
    bridge: CommercialBridge
    consent: InvitationService
```

- [ ] **Step 4: Run test to verify it fails differently**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -v`
Expected: FAIL with `404` — the model and field exist, the route does not.

- [ ] **Step 5: Implement the route**

Append inside `add_commercial_routes`, after `resume_analysis`:

```python
    @app.post(
        f"{COMMERCIAL_PREFIX}/analyses/{{session_id}}/consent",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def record_analysis_consent(
        session_id: str,
        payload: ConsentRequest,
        session: CommercialSessionCookie = None,
    ) -> Response:
        """Authorize, confirm the analysis is in scope, then record consent.

        **The `resume` call is the scope check, not a redundant read.** Recording consent against a
        caller-supplied `session_id` without it would let one organization write to another
        organization's analysis, which is the `FR-023` violation the resume path exists to prevent.
        `KHEPRI-DEC-023` §2 names it for that reason.

        **Consenting twice is deliberately not an error.** Refusing it would require distinguishing
        "already consented" from "not yours", and a caller able to tell those apart learns that an
        analysis exists in a scope they cannot reach.

        `SessionExpired` and `ConsentRequired` both derive from `PermissionError`
        (`rra/sessions.py:17`, `:21`), so the same `except` that covers authorization covers expiry
        and no second branch is needed.
        """
        if session is None:
            return _not_found()
        now = clock()
        try:
            context = services.resolver.for_request(session, organization_id=None, now=now)
            scoped = services.bridge.resume(
                account_id=context.account_id,
                organization_id=context.organization_id,
                session_id=session_id,
                now=now,
            )
            if scoped is None:
                return _not_found()
            services.consent.record_consent(
                scoped.session_id,
                consent_version=payload.consent_version,
                now=now,
            )
        except PermissionError:
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Add `"ConsentRequest"` and `"ConsentVersion"` to `__all__`, keeping it alphabetically ordered.

**Note:** `record_consent` is called with `scoped.session_id` — the value the bridge returned — not
the raw path parameter. They are equal, and using the returned one makes the data dependency on the
scope check explicit rather than incidental.

- [ ] **Step 6: Run test to verify it passes**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Update the production wiring**

`CommercialServices` gained a required field, so `build_commercial_services` no longer constructs.
In `src/khepri/runtime/wiring.py`, add to the imports:

```python
from khepri.rra.sessions import InvitationService
```

**`InvitationService` is already imported at `wiring.py:57`** for `SessionServices`, so add no
import -- a duplicate is a ruff failure. Then in `build_commercial_services`, add the third
argument:

```python
    return CommercialServices(
        resolver=AuthorizationResolver(actors, organizations),
        bridge=CommercialBridge(
            isolation=IsolationService(organizations, accounts),
            store=SqlSessionStore(stack.factory),
        ),
        consent=InvitationService(SqlSessionStore(stack.factory)),
    )
```

`SqlSessionStore` here is the **RRA** class (imported unaliased at the top of `wiring.py`), the same
one the bridge takes. The RCA store is `SqlRcaSessionStore`.

- [ ] **Step 8: Verify the wiring and the unwired guard**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r705_commercial_http_surface.py tests/test_r706_commercial_e2e.py -q`
Expected: PASS. `R7-05`'s `test_the_web_app_declares_the_commercial_group` exercises
`build_commercial_services`, so a missed wiring update fails there.

If `test_an_unwired_app_declares_no_commercial_routes` fails, the null guard was disturbed — restore
it rather than changing the test.

- [ ] **Step 9: Verify the gates**

Run: `./.venv/Scripts/khepri-gov.exe validate && ./.venv/Scripts/python.exe -m ruff check .`
Expected: `Governance validation passed.` and `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add src/khepri/runtime/commercial_api.py src/khepri/runtime/wiring.py tests/test_r706_commercial_e2e.py
git -c commit.gpgsign=false commit -F - <<'MSG'
feat(r7): add the commercial consent route (R7-06)

`KHEPRI-DEC-023` §2 authorized it because `FR-038` was false: consent is
enforced at the service layer so it already bound a commercial actor, but
the only route recording it read the beta cookie, so every commercial
upload failed closed forever.

The route adds no consent logic -- it reuses `record_consent`, which
already takes a plain `session_id`. `bridge.resume` runs before the write
and is the scope check: without it one organization could write consent
onto another's analysis. `record_consent` receives the session the bridge
returned rather than the raw path parameter, so the data dependency on
that check is explicit.

`ConsentRequest` mirrors the beta model, and its `min_length=1` keeps
`record_consent`'s `ValueError` unreachable -- that exception is not a
`PermissionError` and would otherwise escape as a `500`.

Consenting twice is deliberately not an error: refusing it would require
distinguishing "already consented" from "not yours".
MSG
```

---

### Task 2: End-to-end evidence

**Files:**
- Modify: `tests/test_r706_commercial_e2e.py`

**Interfaces:**
- Consumes: `_client(journey)` and the fixtures from Task 1.
- Produces: no production symbols.

Five groups, one per spec §3 subsection. Each closes named requirements.

- [ ] **Step 1: Cross-organization read and mutation (spec §3.1 — `FR-023`, `FR-034`)**

```python
def _outsider(journey: Journey) -> str:
    """An account in a different organization, with a live session switched into it."""
    from khepri.rca.organizations import OrganizationService
    from khepri.rca.switching import OrganizationSwitcher

    account = _account(journey.factory, "outsider@example.test")
    other = OrganizationService(SqlOrganizationStore(journey.factory)).create_organization(
        "Other", account, now=NOW
    )
    token = _rca_sessions(journey.factory).create(account, now=NOW)
    OrganizationSwitcher(
        _rca_sessions(journey.factory), SqlOrganizationStore(journey.factory)
    ).switch(token, other.organization_id, now=NOW)
    return token


def test_a_foreign_analysis_is_indistinguishable_from_an_absent_one(journey: Journey) -> None:
    """Scenario 14. Compared response-to-response, not each against a literal."""
    client = _client(journey)
    token = _outsider(journey)

    foreign = client.get(
        f"/api/v1/commercial/analyses/{journey.session_id}",
        cookies={"khepri_session": token},
    )
    absent = client.get(
        "/api/v1/commercial/analyses/ses_nope", cookies={"khepri_session": token}
    )

    assert (foreign.status_code, foreign.content) == (absent.status_code, absent.content)
    assert journey.analysis_exists()


def test_a_foreign_consent_write_changes_nothing(journey: Journey) -> None:
    """Scenario 15: denied, and **no state changes in either organization**.

    The state assertion is the point. A refused write and a successful one can both return `404` if
    the scope check sits after the write, so asserting only the status would not distinguish them.
    """
    client = _client(journey)
    token = _outsider(journey)

    refused = client.post(
        f"/api/v1/commercial/analyses/{journey.session_id}/consent",
        json={"consent_version": "v-foreign"},
        cookies={"khepri_session": token},
    )

    assert refused.status_code == 404
    with journey.rra_factory() as database:
        import sqlalchemy as sa

        stored = database.scalar(
            sa.text("SELECT consent_version FROM rra_beta_sessions WHERE session_id = :s"),
            {"s": journey.session_id},
        )
    assert stored is None, "a foreign consent write must leave the analysis untouched"
```

- [ ] **Step 2: Run and confirm they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -v`
Expected: PASS (3 passed)

If `test_a_foreign_consent_write_changes_nothing` fails because `stored` is `"v-foreign"`, the scope
check is not gating the write — fix the route, never the assertion.

- [ ] **Step 3: An account with no membership (spec §3.2 — `FR-028`)**

```python
def test_an_account_with_no_membership_authenticates_but_is_denied(journey: Journey) -> None:
    """Scenario 18. `FR-028` requires authentication to SUCCEED and every action to be denied.

    The first assertion is what makes this a `FR-028` test rather than a login test: without it the
    case would pass against a system that simply rejected the account.
    """
    account = _account(journey.factory, "nomember@example.test")
    token = _rca_sessions(journey.factory).create(account, now=NOW)

    context = _r703_resolver(journey.factory).resolve(token, now=NOW)
    assert context.account_id == account, "authentication must succeed"
    assert context.organization_id is None, "with no active organization"

    client = _client(journey)
    opened = client.post("/api/v1/commercial/analyses", cookies={"khepri_session": token})
    resumed = client.get(
        f"/api/v1/commercial/analyses/{journey.session_id}",
        cookies={"khepri_session": token},
    )

    assert opened.status_code == 404
    assert (resumed.status_code, resumed.content) == (opened.status_code, opened.content)
```

- [ ] **Step 4: The canonical checkpoint and the `FR-024` absence (spec §3.3, §3.6)**

```python
def _commercial_handlers() -> dict[str, object]:
    """Every route handler declared by the commercial group, by name.

    Built by declaring the group onto a throwaway app and reading its routes, so the inventory comes
    from what FastAPI actually registered rather than from a source scan that a rename would defeat.
    """
    from khepri.runtime.commercial_api import COMMERCIAL_PREFIX

    app = FastAPI()
    add_commercial_routes(
        app,
        services=CommercialServices(resolver=object(), bridge=object(), consent=object()),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )
    return {
        route.endpoint.__name__: route.endpoint
        for route in app.routes
        if getattr(route, "path", "").startswith(COMMERCIAL_PREFIX)
    }


def test_every_commercial_handler_passes_the_canonical_checkpoint() -> None:
    """`FR-021`, `FR-026`. An action that does not pass the checkpoint must be unreachable.

    The emptiness assertion is not decoration: an inventory that found no handlers would satisfy
    every claim about the handlers it found.
    """
    import inspect

    handlers = _commercial_handlers()

    assert handlers, "no commercial handlers were registered; this test proves nothing"
    for name, handler in handlers.items():
        source = inspect.getsource(handler)
        assert "for_request(" in source, f"{name} does not pass the canonical checkpoint"
        assert "resolver.resolve(" not in source, f"{name} calls resolve, which §2 forbids"


def test_no_commercial_handler_accepts_an_organization() -> None:
    """`FR-024`, satisfied by ABSENCE and asserted as such.

    `FR-024` requires a request whose actor and named organization scope disagree to fail closed.
    No commercial route accepts an organization, so that request cannot be constructed here. A test
    named for `FR-024` that passed because the parameter does not exist would be a test that cannot
    fail; this asserts the absence itself, which is the property that makes it unreachable.
    """
    import inspect

    handlers = _commercial_handlers()

    assert handlers, "no commercial handlers were registered; this test proves nothing"
    for name, handler in handlers.items():
        parameters = set(inspect.signature(handler).parameters)
        assert "organization_id" not in parameters, f"{name} accepts an organization"
        assert "organization" not in parameters, f"{name} accepts an organization"
```

- [ ] **Step 5: Run and confirm they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -v`
Expected: PASS (6 passed)

- [ ] **Step 6: Scope mapping and the durable organization (spec §3.4 — `FR-009`, `FR-031`)**

```python
def test_two_analyses_of_one_organization_share_its_scope(journey: Journey) -> None:
    """`FR-031`: the isolation scope is the organization's, not the session's or the actor's."""
    from khepri.rca.isolation import IsolationService
    from khepri.rca.persistence import SqlAccountStore

    client = _client(journey)
    first = client.post(
        "/api/v1/commercial/analyses", cookies={"khepri_session": journey.member_token}
    ).json()["session_id"]
    second = client.post(
        "/api/v1/commercial/analyses", cookies={"khepri_session": journey.member_token}
    ).json()["session_id"]

    assert first != second, "each analysis is its own session"

    expected = IsolationService(
        SqlOrganizationStore(journey.factory), SqlAccountStore(journey.factory)
    ).resolve_scope(journey.member, journey.organization_id)
    for session_id in (first, second):
        stored = journey.rra_store.get_session(session_id)
        assert stored is not None
        assert stored.owner_id == expected


def test_another_member_of_the_organization_resumes_the_same_analysis(journey: Journey) -> None:
    """`FR-009`: the organization is a durable scope distinct from the accounts acting in it."""
    client = _client(journey)
    opened = client.post(
        "/api/v1/commercial/analyses", cookies={"khepri_session": journey.member_token}
    ).json()["session_id"]

    resumed = client.get(
        f"/api/v1/commercial/analyses/{opened}",
        cookies={"khepri_session": journey.first_token},
    )

    assert resumed.status_code == 200, "the analysis belongs to the organization, not its opener"
```

- [ ] **Step 7: FR-038, all four clauses (spec §3.5)**

```python
def test_a_commercial_actor_cannot_upload_before_consenting(journey: Journey) -> None:
    """`FR-038` clause 1, both halves.

    The refusal alone would pass against a route that never records consent at all -- which is
    exactly the defect `KHEPRI-DEC-023` was written to fix -- so the accepted case after consenting
    is what makes this evidence rather than a restatement of the bug.
    """
    from khepri.rra.sessions import ConsentRequired, require_upload_consent

    before = journey.rra_store.get_session(journey.session_id)
    assert before is not None
    try:
        require_upload_consent(before, now=NOW)
    except ConsentRequired:
        pass
    else:  # pragma: no cover - the guard must refuse an unconsented session
        raise AssertionError("an unconsented commercial session must refuse upload")

    consented = _client(journey).post(
        f"/api/v1/commercial/analyses/{journey.session_id}/consent",
        json={"consent_version": "v1"},
        cookies={"khepri_session": journey.member_token},
    )
    assert consented.status_code == 204

    after = journey.rra_store.get_session(journey.session_id)
    assert after is not None
    require_upload_consent(after, now=NOW)  # must not raise


def test_the_report_path_never_branches_on_actor_kind() -> None:
    """`FR-038` clauses 2-4, proved structurally rather than assumed.

    Disclosure, reconciliation/provenance and Arabic/English parity hold for a commercial actor
    because the pipeline keys on `SessionScope(owner_id, session_id)` and has no actor-kind concept.
    Re-asserting beta's rendering per actor kind would duplicate its suite; what needs proving is
    that the actor kind never enters.

    The emptiness assertion guards the scan: a glob matching nothing satisfies every claim about
    what it matched.
    """
    from pathlib import Path

    # The report path itself, named explicitly. Scanning all of `khepri/rra` would need an
    # exclusion list -- `sessions.py` and `persistence.py` both name the commercial entry point,
    # authorized by `KHEPRI-DEC-021` §2 -- and an exclusion list is what drifts. Naming the pipeline
    # is the narrower claim and the one `FR-038` actually needs.
    report_path = [
        Path("src/khepri/rra/report_services.py"),
        Path("src/khepri/rra/report_publication.py"),
        Path("src/khepri/rra/report_artifacts.py"),
        Path("src/khepri/rra/pipeline.py"),
        Path("src/khepri/rra/bundle.py"),
        *sorted(Path("src/khepri/rra/analysis").rglob("*.py")),
        *sorted(Path("src/khepri/rra/rendering").rglob("*.py")),
    ]
    present = [p for p in report_path if p.exists()]

    assert len(present) == len(report_path), (
        f"a named report-path module is missing: {[p.as_posix() for p in report_path if not p.exists()]}; "
        "the scan would silently skip it"
    )
    assert present, "the scan matched no report modules; it proves nothing"
    offenders = [
        p.as_posix() for p in present if "commercial" in p.read_text(encoding="utf-8")
    ]
    assert offenders == [], (
        "a report-path module distinguishes a commercial actor; it must be actor-kind-free for "
        "FR-038's disclosure, provenance and language-parity clauses to hold by shared "
        "implementation rather than by assumption"
    )
```

**Note on scoping:** the scan names the report path rather than excluding the entry point.
`sessions.py` and `persistence.py` both mention the commercial session by design
(`KHEPRI-DEC-021` §2 authorized `open_commercial_session` and its store row), so an all-of-`rra`
scan would need an exclusion list that drifts as the package grows. The missing-module assertion is
what keeps the explicit list honest: a renamed pipeline module fails loudly instead of being skipped.
If an offender is ever reported, read it before touching this test -- a genuine actor-kind branch in
the pipeline is a finding, not a test to relax.

- [ ] **Step 8: Run the module and the neighbours**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py tests/test_r705_commercial_http_surface.py tests/test_r704_beta_preservation.py -q`
Expected: PASS. `R7-04` must pass **unmodified**.

- [ ] **Step 9: Run the full suite**

Run: `./.venv/Scripts/python.exe -m pytest -q` (timeout above 240s)
Expected: all pass. If `R6-05`'s matrix tripwire fails, update **only its consumer inventory** —
`KHEPRI-DEC-022` §2's fourth bullet, carried forward by `-023` §1, says consent gets no new matrix
row.

- [ ] **Step 10: Commit**

```bash
git add tests/test_r706_commercial_e2e.py
git -c commit.gpgsign=false commit -F - <<'MSG'
test(r7): prove the commercial surface end to end (R7-06)

Five groups against the real resolver, bridge and database, closing
`FR-009`, `FR-021`, `FR-026`, `FR-028`, `FR-031`, `FR-034` and `FR-038`.

The cross-organization mutation case asserts the stored consent version is
unchanged, not merely that the response was `404`: a refused write and a
successful one both return `404` if the scope check sits after the write.

`FR-028` asserts authentication SUCCEEDS before asserting the routes
refuse -- without that the case would pass against a system that rejected
the account outright.

`FR-024` is asserted as an absence. No commercial route accepts an
organization, so an actor/named-scope disagreement cannot be constructed;
a test named for it that passed on a missing parameter could not fail, so
the assertion is the absence itself.

`FR-038`'s consent clause asserts both halves -- refused before, accepted
after -- because the refusal alone would pass against the very defect
`KHEPRI-DEC-023` fixed. Its three parity clauses are proved structurally:
no RRA module outside the entry point distinguishes a commercial actor, so
they hold by shared implementation rather than by assumption.

Both structural scans carry emptiness assertions.
MSG
```

---

### Task 3: Verify the mutants

**Files:** none committed — this task applies and reverts changes, then records results.

**Interfaces:** none.

`#231` records the cost of shipping an evidence suite with no mutation evidence. For each: copy the
file, apply the change, run the named test, confirm it FAILS, restore the copy. **Check the mutant
actually introduces the defect before concluding a test is weak** — a malformed mutant proves
nothing.

- [ ] **Step 1: Mutant 1 — drop the scope check**

In `commercial_api.py`'s consent handler, replace the `scoped = services.bridge.resume(...)` block
and its `if scoped is None` guard with `scoped = None` removed entirely, calling
`services.consent.record_consent(session_id, ...)` on the raw path parameter instead.

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -k foreign_consent -v`
Expected: **FAIL** — `stored` is `"v-foreign"`, so the assertion that a foreign write changes nothing
fires. Restore the file.

- [ ] **Step 2: Mutant 2 — `409` for an already-consented analysis**

Add a pre-read to the consent handler that returns `Response(status_code=409)` when
`scoped.consent_version is not None`.

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -k "consent" -v`
Expected: **FAIL** on the second consent in the `FR-038` test. Restore the file.

- [ ] **Step 3: Mutant 3 — `resolve` instead of `for_request`**

In the consent handler only, change `for_request(session, organization_id=None, now=now)` to
`resolve(session, now=now)`.

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -k checkpoint -v`
Expected: **FAIL** — the checkpoint scan finds a handler without `for_request(`. Restore the file.

- [ ] **Step 4: Mutant 4 — the pipeline scan finds nothing**

In `test_the_report_path_never_branches_on_actor_kind`, replace the `report_path` list with `[]`.

Run: `./.venv/Scripts/python.exe -m pytest tests/test_r706_commercial_e2e.py -k actor_kind -v`
Expected: **FAIL** on the emptiness assertion, **not** on the offenders assertion. Restore the file.

- [ ] **Step 5: Confirm the tree is clean**

Run: `git status --porcelain`
Expected: empty. No `.bak` files, no leftover mutants. If anything shows, restore it before
proceeding.

---

### Task 4: Flip the roadmap row to MERGED

**Files:**
- Modify: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` (§16 `R7` row)

**Interfaces:** none — docs-only.

This is the transition only a final slice performs.

- [ ] **Step 1: Read the current row**

Run: `git grep -n "R7 Commercial RRA bridge" docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md`

It currently ends `**R7-06 is now the next task** and is the program's last.` and its status cell
reads `READY_FOR_IMPLEMENTATION`.

- [ ] **Step 2: Rewrite the row**

Change the status cell to `MERGED`. Replace the trailing clause with a record of `R7-06`: the consent
route and why it was product work rather than tests (`FR-038` was false, per `KHEPRI-DEC-023`), the
requirements this slice closed, the four verified mutants, and — stated explicitly — that **`FR-024`
is satisfied by absence rather than by test**, and that `FR-008`/`FR-022`/`FR-023`/`FR-025` closed in
`R7-05` rather than here. Do not claim the program proved all twelve at once.

Keep the row one line with four pipe-delimited cells.

- [ ] **Step 3: Verify row integrity and the status vocabulary**

```bash
./.venv/Scripts/python.exe -c "
import io
L=io.open('docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md',encoding='utf-8').read().split(chr(10))
r=[l for l in L if l.startswith('| R7 Commercial RRA bridge')]
assert len(r)==1, f'rows {len(r)}'
assert r[0].count('|')==4, f'cells {r[0].count(chr(124))}'
assert r[0].split('|')[2].strip()=='MERGED', r[0].split('|')[2]
assert 'is now the next task' not in r[0], 'stale next-task clause survives'
print('[OK] row is MERGED and intact')
"
```

`MERGED` is one of §15's eight admitted statuses (`README`/§15 lists them) — confirm by grepping
`grep -n 'MERGED' docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md | head -3` and seeing it used by
other programs.

- [ ] **Step 4: Verify the gates**

Run: `./.venv/Scripts/khepri-gov.exe validate && ./.venv/Scripts/python.exe -m ruff check .`
Expected: both pass.

- [ ] **Step 5: Commit**

```bash
git add docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md
git -c commit.gpgsign=false commit -F - <<'MSG'
docs(r0): mark R7 merged with R7-06 complete (R7-06)

`R7-06` is the program's last task, so this performs the transition only a
final slice performs. Folded into this PR because §16 is the one document
a slice's DoD never touches.

The row states which requirements closed where rather than claiming the
program proved twelve at once: four closed in `R7-05`, seven here, and
`FR-024` is satisfied by absence rather than by test.
MSG
```

---

## Self-Review

**1. Spec coverage.** §1 (why product code) → Task 1's commit message and the record it cites. §2
(the route) → Task 1. §3.1 → Task 2 step 1; §3.2 → step 3; §3.3 and §3.6 → step 4; §3.4 → step 6;
§3.5 → step 7. §4 (mutants) → Task 3. §5 (what changes state) → Task 2 steps 8–9. §6 (DoD) → Task 4.
§7's non-goals are excluded by construction: no task adds a most-recent list, a UI, report-content
assertions, or touches `#231`.

**2. Placeholder scan.** Every code step carries runnable code. Task 4 step 2 describes the row's
content rather than quoting it, because the row must embed facts (which mutants passed) that only
exist after Tasks 1–3 run; its integrity check in step 3 is executable.

**3. Type consistency.** `CommercialServices(resolver, bridge, consent)` is defined in Task 1 step 3
and used with all three fields in Task 1 step 1, Task 1 step 7, and Task 2 step 4. `ConsentRequest`
carries one field `consent_version`, matching the JSON body `{"consent_version": ...}` in every test.
`_client(journey)` is defined once in Task 1 step 1 and reused throughout Task 2.
`_commercial_handlers()` is defined once in Task 2 step 4 and used by both tests there.
`journey.rra_store` and `journey.rra_factory` are `R7-03` fixture attributes, verified present.

**Known risks flagged for the executor:**

- **`inspect.getsource` on a closure** — the handlers are nested functions inside
  `add_commercial_routes`. `getsource` works on them, but if it raises `OSError` under any runner,
  substitute reading `commercial_api.py` and parsing handler bodies with `ast`, keeping both
  assertions and the emptiness check.
- **`CommercialServices(resolver=object(), ...)`** in `_commercial_handlers` relies on the route
  declaration not touching the services at import time. It does not — they are used inside handler
  bodies — but if declaration ever validates them, pass the real journey collaborators instead.
