"""Starting an analysis from the shell and entering the journey (`R8-06`).

Authorized by `RCA-002`. The roadmap says "embed **or** route"; this routes, and the reason is
structural rather than preferential.

**The journey pages are static shells.** `page(request, language, step)` takes no session and
renders a template; the browser then fetches `/api/v1/beta/journey`, and *that* is what reads the
beta cookie. So there is nothing to embed -- the workflow already lives behind an API the shell
would have to reproduce -- and routing to it is the whole integration.

**Two cookies, and the paths are deliberate.** The commercial cookie is `khepri_session`; the beta
one is `khepri_beta_session` scoped to `/api/v1/beta`, which is exactly where the journey's XHR
goes. Verified empirically before writing this: a cookie on that path reaches
`/api/v1/beta/journey` and does *not* reach `/beta/en/upload`, which is correct because the page
does not read it.

**`CommercialBridge.open` already writes a real `BetaSessionRow`** (`open_commercial_session_row`),
so a commercially-opened analysis is readable by the journey's reader without any new persistence.
This slice mints nothing and stores nothing; it sets the transport the journey already expects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import ScopeAccessDenied
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.session_cookie import SESSION_COOKIE as BETA_COOKIE
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes

NOW = datetime(2026, 8, 22, tzinfo=UTC)


@dataclass
class _Context:
    account_id: str
    organization_id: str | None
    role: str | None = "member"

    @property
    def is_owner(self) -> bool:
        return self.role == "owner"


class _StubResolver:
    def __init__(
        self, context: _Context | None = None, raises: Exception | None = None
    ) -> None:
        self._context = context or _Context("acct-1", "org-acme")
        self._raises = raises

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        if self._raises is not None:
            raise self._raises
        return self._context

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:
        if self._raises is not None:
            raise self._raises
        return self._context


@dataclass
class _Opened:
    session_id: str


class _StubBridge:
    """Records the scope it was asked to open in, so `FR-042` is asserted on the call."""

    def __init__(self, raises: Exception | None = None) -> None:
        self._raises = raises
        self.opened: list[tuple[str, str]] = []

    def open(self, *, account_id: str, organization_id: str, now: object) -> _Opened:
        if self._raises is not None:
            raise self._raises
        self.opened.append((account_id, organization_id))
        return _Opened("ses_a-new-analysis")


class _StubOrganizations:
    def organizations_for_account(self, account_id: str) -> list[object]:
        return [object()]

    def memberships_for_organization(self, organization_id: str) -> list[object]:
        return []


def _shell(
    *, context: _Context | None = None, raises: Exception | None = None,
    bridge: _StubBridge | None = None,
) -> tuple[TestClient, _StubBridge]:
    bridge = bridge or _StubBridge()
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(context, raises),
            organizations=_StubOrganizations(),
            bridge=bridge,
        ),
        clock=lambda: NOW,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, "a-commercial-session")
    return client, bridge


class TestStartingAnAnalysis:
    def test_it_opens_an_analysis_in_the_resolved_scope(self) -> None:
        client, bridge = _shell(context=_Context("acct-1", "org-acme"))

        client.post(f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False)

        assert bridge.opened == [("acct-1", "org-acme")]

    def test_it_redirects_into_the_journey(self) -> None:
        client, _ = _shell()

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False
        )

        assert response.status_code == 303
        assert response.headers["location"] == "/beta/en/upload"

    def test_it_carries_the_language_into_the_journey(self) -> None:
        """`FR-047`: the rendering language is a property of the address, across the boundary too.

        Entering an Arabic shell and landing on an English journey would break parity at exactly
        the handoff.
        """
        client, _ = _shell()

        response = client.post(
            f"{SHELL_PREFIX}/ar/org-acme/analyses", follow_redirects=False
        )

        assert response.headers["location"] == "/beta/ar/upload"

    def test_it_sets_the_beta_cookie_the_journey_reads(self) -> None:
        client, _ = _shell()

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False
        )

        cookie = response.headers["set-cookie"]
        assert f"{BETA_COOKIE}=ses_a-new-analysis" in cookie
        assert "Path=/api/v1/beta" in cookie

    def test_the_beta_cookie_carries_every_transport_control(self) -> None:
        """The same flags the redeem endpoint sets. A weaker cookie here would be a downgrade
        reachable by taking the commercial route instead of the invitation one."""
        client, _ = _shell()

        cookie = client.post(
            f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False
        ).headers["set-cookie"]

        assert "HttpOnly" in cookie
        assert "Secure" in cookie
        assert "SameSite=strict" in cookie.replace("samesite", "SameSite")


class TestRefusals:
    def test_a_refused_actor_opens_nothing(self) -> None:
        """The DENY effect, not the exception: no analysis exists afterwards."""
        client, bridge = _shell(raises=ScopeAccessDenied())

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False
        )

        assert response.status_code == 404
        assert bridge.opened == []

    def test_a_refused_actor_is_set_no_beta_cookie(self) -> None:
        """A cookie set on the refusal path would hand an unauthorized caller a session."""
        client, _ = _shell(raises=ScopeAccessDenied())

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False
        )

        assert BETA_COOKIE not in response.headers.get("set-cookie", "")

    def test_a_bridge_refusal_is_the_same_response(self) -> None:
        """`resolve_scope` refuses inside `open`, and that refusal must not look different."""
        client, _ = _shell(bridge=_StubBridge(raises=ScopeAccessDenied()))

        response = client.post(
            f"{SHELL_PREFIX}/en/org-acme/analyses", follow_redirects=False
        )

        assert response.status_code == 404

    def test_an_unwired_bridge_declares_no_entry_route(self) -> None:
        """A beta-only deployment has no commercial entry rather than one that refuses."""
        app = FastAPI()
        add_shell_routes(
            app,
            services=ShellServices(
                resolver=_StubResolver(), organizations=_StubOrganizations()
            ),
            clock=lambda: NOW,
        )

        paths = {getattr(route, "path", "") for route in app.routes}

        assert f"{SHELL_PREFIX}/{{language}}/{{organization}}/analyses" not in paths
