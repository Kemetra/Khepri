"""The commercial HTTP surface (`R7-05`).

Authorized by `KHEPRI-DEC-022` §2. Every refusal in this file must be byte-identical: `FR-025`
requires that a caller cannot distinguish "not authorized" from "does not exist", and a test
checking each response against a literal would pass even if two causes diverged. The comparisons
here are therefore response-to-response.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import SCOPE_FAILURE, AuthenticationFailed, ScopeAccessDenied
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlOrganizationStore
from khepri.rca.switching import OrganizationSwitcher
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from tests.rca_lifecycle_support import NOW, factory_fixture  # noqa: F401 -- fixture
from tests.test_r703_live_authorization_on_resume import (  # noqa: F401 -- fixture re-export
    Journey,
    _account,
    _rca_sessions,
    journey_fixture,
)
from tests.test_r703_live_authorization_on_resume import _resolver as _r703_resolver


def test_an_unwired_app_declares_no_commercial_routes() -> None:
    """`KHEPRI-DEC-022` §3 forbids a beta-mode change, and this is how that is met.

    With no services the group is never declared, so a beta-only deployment has no commercial
    surface at all rather than one that exists and refuses.
    """
    app = FastAPI()
    add_commercial_routes(app, services=None, clock=lambda: NOW)

    paths = {getattr(route, "path", "") for route in app.routes}

    assert not any(path.startswith("/api/v1/commercial") for path in paths)


@dataclass
class _StubContext:
    account_id: str
    organization_id: str | None


class _StubResolver:
    """Returns a fixed context, or raises whatever it was given."""

    def __init__(
        self, context: _StubContext | None = None, raises: Exception | None = None
    ) -> None:
        self._context = context or _StubContext("acct-1", "org-1")
        self._raises = raises
        self.calls: list[tuple[str, str, str | None]] = []

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _StubContext:
        self.calls.append(("for_request", token, organization_id))
        if self._raises is not None:
            raise self._raises
        return self._context

    def resolve(self, token: str, *, now: object = None) -> _StubContext:
        """Defined deliberately, so mutant 1 fails an assertion rather than an `AttributeError`.

        If this method did not exist, swapping `for_request` for `resolve` in the handler would
        raise `AttributeError` and the test would "die" without ever checking the property it claims
        to check. A mutant killed for the wrong reason proves nothing.
        """
        self.calls.append(("resolve", token, None))
        if self._raises is not None:
            raise self._raises
        return self._context


@dataclass
class _StubSession:
    session_id: str


class _StubBridge:
    def __init__(
        self, session: _StubSession | None = None, raises: Exception | None = None
    ) -> None:
        self._session = session
        self._raises = raises

    def open(self, *, account_id: str, organization_id: str, now: object) -> _StubSession:
        if self._raises is not None:
            raise self._raises
        return self._session or _StubSession("sess-1")

    def resume(
        self, *, account_id: str, organization_id: str, session_id: str, now: object
    ) -> _StubSession | None:
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

    response = client.get("/api/v1/commercial/analyses/sess-9", cookies={"khepri_session": "tok"})

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


_REFUSALS = [
    pytest.param(
        _StubResolver(raises=AuthenticationFailed("no")), _StubBridge(), id="auth-failed"
    ),
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

    response = client.get("/api/v1/commercial/analyses/sess-9", cookies={"khepri_session": "tok"})

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


def test_the_web_app_declares_the_commercial_group() -> None:
    """The wiring exists and reaches the routes.

    `runtime_stack()` in `tests/test_runtime_wiring.py` is a plain function, **not** a pytest
    fixture -- it is called directly and builds against `AwsClientStub`. Importing it rather than
    writing a second stack builder keeps one definition of the production graph under test.
    """
    from khepri.runtime.wiring import build_web_app
    from tests.test_runtime_wiring import runtime_stack

    app = build_web_app(runtime_stack())

    paths = {getattr(route, "path", "") for route in app.routes}

    assert "/api/v1/commercial/analyses" in paths
    assert "/api/v1/commercial/analyses/{session_id}" in paths


def test_commercial_services_holds_a_real_resolver_and_bridge() -> None:
    from khepri.runtime.wiring import build_commercial_services
    from tests.test_runtime_wiring import runtime_stack

    services = build_commercial_services(runtime_stack())

    assert isinstance(services, CommercialServices)
    assert services.resolver is not None
    assert services.bridge is not None


class _RealServices:
    """`CommercialServices` built from `R7-03`'s journey, so the route drives the real graph.

    Reuses `Journey` rather than rebuilding it: it already provides two owners (`FR-013` refuses to
    demote a final owner, so a one-owner fixture would fail on an invariant that is not
    authorization), separate RCA and RRA databases (`FR-039` independence), and an analysis opened
    through the production path.
    """

    def __init__(self, journey: Journey) -> None:
        self.journey = journey

    def client(self) -> TestClient:
        app = FastAPI()
        add_commercial_routes(
            app,
            services=CommercialServices(
                resolver=_r703_resolver(self.journey.factory),
                bridge=self.journey.bridge,
            ),
            clock=lambda: NOW,
        )
        return TestClient(app)

    def get(self, token: str, session_id: str) -> object:
        return self.client().get(
            f"/api/v1/commercial/analyses/{session_id}", cookies={"khepri_session": token}
        )

    def post(self, token: str) -> object:
        return self.client().post(
            "/api/v1/commercial/analyses", cookies={"khepri_session": token}
        )


def test_a_member_opens_and_resumes_through_the_route(journey: Journey) -> None:
    """The fixture reaches RRA, so a later refusal cannot be a journey that never got there."""
    services = _RealServices(journey)

    opened = services.post(journey.member_token)
    assert opened.status_code == 201

    resumed = services.get(journey.member_token, opened.json()["session_id"])
    assert resumed.status_code == 200
    assert resumed.json() == {"session_id": opened.json()["session_id"]}


def test_a_revoked_member_cannot_resume_through_the_route(journey: Journey) -> None:
    """`FR-030` at the HTTP layer: the route does not cache the decision.

    `R7-03` proved the bridge re-resolves. This proves the handler does not hold a context across
    calls or skip the resolver on a second request.
    """
    services = _RealServices(journey)
    assert services.get(journey.member_token, journey.session_id).status_code == 200

    journey.revoke_membership_row(journey.member)

    assert services.get(journey.member_token, journey.session_id).status_code == 404
    assert journey.analysis_exists(), "the refusal must be authorization, not deletion"


def test_a_disabled_account_cannot_resume_through_the_route(journey: Journey) -> None:
    """`FR-008`: no dependence on session expiry. No time passes in this test."""
    services = _RealServices(journey)
    assert services.get(journey.member_token, journey.session_id).status_code == 200

    journey.disable(journey.member)

    assert services.get(journey.member_token, journey.session_id).status_code == 404
    assert journey.analysis_exists()


def test_a_demoted_owner_can_still_resume_through_the_route(journey: Journey) -> None:
    """The negative case, and it is what keeps the guard from being a blanket refusal.

    A demoted owner is still a member, so they keep access. A suite of only refusals would pass
    against a route that refused everyone.
    """
    services = _RealServices(journey)

    journey.demote(journey.second)

    resumed = services.get(journey.second_token, journey.session_id)
    assert resumed.status_code == 200, "a demoted owner is still a member and keeps access"


def test_another_organizations_analysis_is_indistinguishable_from_an_absent_one(
    journey: Journey,
) -> None:
    """`FR-025`, at the HTTP layer.

    An actor outside the organization gets exactly what a nonexistent identifier returns. The two
    responses are compared to each other: asserting `404` twice would pass even if one grew a body
    naming the owner.
    """
    outsider = _account(journey.factory, "outsider@example.test")
    other = OrganizationService(SqlOrganizationStore(journey.factory)).create_organization(
        "Other", outsider, now=NOW
    )
    token = _rca_sessions(journey.factory).create(outsider, now=NOW)
    OrganizationSwitcher(
        _rca_sessions(journey.factory), SqlOrganizationStore(journey.factory)
    ).switch(token, other.organization_id, now=NOW)

    services = _RealServices(journey)
    foreign = services.get(token, journey.session_id)
    absent = services.get(token, "does-not-exist")

    assert (foreign.status_code, foreign.content) == (absent.status_code, absent.content)
    assert journey.analysis_exists()
