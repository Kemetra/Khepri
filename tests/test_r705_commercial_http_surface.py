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
from khepri.runtime.commercial_api import CommercialServices, add_commercial_routes
from tests.rca_lifecycle_support import NOW


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
