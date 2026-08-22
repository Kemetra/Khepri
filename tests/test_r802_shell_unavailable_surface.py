"""The commercial shell base and the shared unavailable surface (`R8-02`).

Authorized by `RCA-002`, `active` at `488e1ae`. Each test names the `RCA-002` scenario it verifies.

**Why refusals are compared response-to-response.** `FR-050` collapses five distinct states into
one surface, and a test checking each against a literal would pass even after two causes diverged.
`test_r705_commercial_http_surface.py` established the pattern and this file follows it.

**`FR-050` and `FR-052` are two tests on purpose.** `RCA-002` `FR-052` says so in as many words:
one requires several inputs to produce one indistinguishable output, the other constrains what any
single output may contain. A shell leaking the object's type in all five collapsed states would
still be perfectly indistinguishable across them, so the comparison test alone proves nothing about
content.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.errors import AuthenticationFailed, ScopeAccessDenied
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rra.journey.security import SECURITY_HEADERS
from khepri.runtime.shell_api import (
    SHELL_ASSETS,
    SHELL_PREFIX,
    ShellServices,
    add_shell_routes,
)

NOW = "2026-08-22T00:00:00Z"

#: Every path this slice delivers. `RCA-002` implementation precondition 3 requires the first slice
#: to name its surfaces and assert the absence of the others; this constant is that declaration in
#: executable form.
DELIVERED_PATHS = {
    f"{SHELL_PREFIX}/{{path:path}}",
    f"{SHELL_ASSETS}/{{name}}",
    # `R8-05b`'s two mutating routes. Added here deliberately rather than by relaxing the
    # assertion: this tripwire fires whenever the shell's reachable surface grows, which is the
    # decision it exists to force.
    f"{SHELL_PREFIX}/{{language}}/{{organization}}/team/invitations",
    f"{SHELL_PREFIX}/{{language}}/{{organization}}/team/invitations/{{invitation}}/revoke",
    # `R8-06`'s journey entry. Only declared when a bridge is wired, which is why
    # `test_it_declares_every_surface_when_fully_wired` exists below: a conditionally registered
    # route is invisible to a scan that never enables it.
    f"{SHELL_PREFIX}/{{language}}/{{organization}}/analyses",
}


@dataclass
class _StubContext:
    account_id: str
    organization_id: str | None
    role: str | None = "member"


class _StubOrganizations:
    """No memberships by default, so every R8-02 case still reaches a refusal or the
    no-membership surface rather than a switcher this slice did not deliver."""

    def __init__(self, organizations: list[object] | None = None) -> None:
        self._organizations = organizations or []

    def organizations_for_account(self, account_id: str) -> list[object]:
        return self._organizations


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
        """Defined so a `for_request`->`resolve` mutant dies on an assertion, not `AttributeError`.

        A mutant killed for the wrong reason proves nothing.
        """
        self.calls.append(("resolve", token, None))
        if self._raises is not None:
            raise self._raises
        return self._context


def _client(
    *,
    resolver: _StubResolver | None = None,
    services: ShellServices | None | str = "default",
) -> TestClient:
    app = FastAPI()
    if services == "default":
        services = ShellServices(
            resolver=resolver or _StubResolver(),
            organizations=_StubOrganizations(),
        )
    add_shell_routes(app, services=services, clock=lambda: NOW)
    return TestClient(app)


class TestScope:
    """`RCA-002` implementation precondition 3."""

    def test_it_declares_only_the_surfaces_this_slice_delivers(self) -> None:
        """An unimplemented surface is proven absent rather than merely unwritten.

        The emptiness assertion is load-bearing: without it a renamed router would make this pass
        by enumerating nothing, which is exactly how a scan self-disarms.
        """
        app = FastAPI()
        add_shell_routes(
            app,
            services=ShellServices(
                resolver=_StubResolver(), organizations=_StubOrganizations()
            ),
            clock=lambda: NOW,
        )

        shell_paths = {
            path
            for route in app.routes
            if (path := getattr(route, "path", "")).startswith(SHELL_PREFIX)
        }

        assert shell_paths, "the scan found no shell routes, so it proves nothing"
        assert shell_paths <= DELIVERED_PATHS

    def test_it_declares_every_surface_when_fully_wired(self) -> None:
        """The surface set asserted in the configuration production actually runs.

        The scan above builds `ShellServices` with no bridge and no invitation gateway, so the
        conditionally registered routes never appear in it -- an honest scan of a configuration
        that is not the deployed one. This asserts the full set, so a new conditional route
        cannot slip in behind a null guard.
        """
        app = FastAPI()
        add_shell_routes(
            app,
            services=ShellServices(
                resolver=_StubResolver(),
                organizations=_StubOrganizations(),
                invitations=object(),
                bridge=object(),
            ),
            clock=lambda: NOW,
        )

        shell_paths = {
            path
            for route in app.routes
            if (path := getattr(route, "path", "")).startswith(SHELL_PREFIX)
        }

        assert shell_paths, "the scan found no shell routes, so it proves nothing"
        assert shell_paths == DELIVERED_PATHS

    def test_an_unwired_app_declares_no_shell_routes(self) -> None:
        """A beta-only deployment has no shell at all, rather than one that exists and refuses."""
        app = FastAPI()
        add_shell_routes(app, services=None, clock=lambda: NOW)

        paths = {getattr(route, "path", "") for route in app.routes}

        assert not any(path.startswith(SHELL_PREFIX) for path in paths)


class TestAssets:
    """The shell serves its own assets; `/beta/assets/` does not reach this prefix."""

    def test_it_serves_the_shell_stylesheet(self) -> None:
        response = _client().get(f"{SHELL_ASSETS}/shell.css")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/css")

    def test_an_unlisted_asset_is_not_served(self) -> None:
        """An allowlist, not a directory listing: a file is served by being named, not by
        arriving in the package."""
        response = _client().get(f"{SHELL_ASSETS}/journey.css")

        assert response.status_code == 404

    def test_an_asset_name_cannot_escape_the_allowlist(self) -> None:
        """The name is matched against a `dict`, never joined onto a path from the request."""
        response = _client().get(f"{SHELL_ASSETS}/../../etc/passwd")

        assert response.status_code == 404


class TestScenario8UnknownPath:
    """`FR-046`: an unknown path resolves to the shared unavailable surface."""

    def test_an_unknown_path_renders_the_unavailable_surface(self) -> None:
        response = _client(resolver=_StubResolver(raises=AuthenticationFailed())).get(
            f"{SHELL_PREFIX}/en/no-such-surface"
        )

        assert response.status_code == 404
        assert "unavailable" in response.text.lower()


class TestScenario5And2Indistinguishability:
    """`FR-050`, `FR-051`: several causes, one response."""

    def test_every_refusal_cause_produces_one_identical_response(self) -> None:
        """Compared response-to-response, never against a literal.

        `AuthenticationFailed` stands for absent, unknown, expired, and revoked sessions;
        `ScopeAccessDenied` for an actor who is not a member of the organization asked for.
        """
        absent = _client(
            services=ShellServices(
                resolver=_StubResolver(raises=None), organizations=_StubOrganizations()
            )
        ).get(
            f"{SHELL_PREFIX}/en/acme/analyses"
        )
        unauthenticated = _client(resolver=_StubResolver(raises=AuthenticationFailed())).get(
            f"{SHELL_PREFIX}/en/acme/analyses"
        )
        foreign = _client(resolver=_StubResolver(raises=ScopeAccessDenied())).get(
            f"{SHELL_PREFIX}/en/acme/analyses"
        )

        assert unauthenticated.status_code == foreign.status_code == absent.status_code
        assert unauthenticated.text == foreign.text == absent.text

    def test_a_refusal_never_names_the_organization_it_was_asked_about(self) -> None:
        """`FR-051`. Naming it is the natural thing for an error page to do, and is the leak."""
        response = _client(resolver=_StubResolver(raises=ScopeAccessDenied())).get(
            f"{SHELL_PREFIX}/en/a-very-distinctive-org-slug/analyses"
        )

        assert "a-very-distinctive-org-slug" not in response.text


class TestScenario21SingleDenialContent:
    """`FR-052`: what one denial may contain, examined without comparison.

    Separate from the test above by requirement, not by preference. The comparison test passes even
    when every response leaks the same field.
    """

    def test_one_denial_examined_alone_carries_no_object_detail(self) -> None:
        response = _client(resolver=_StubResolver(raises=ScopeAccessDenied())).get(
            f"{SHELL_PREFIX}/en/acme/analyses/an-object-identifier"
        )

        body = response.text.lower()
        assert "an-object-identifier" not in body
        for disclosure in ("expired", "deleted", "revoked", "not a member", "does not exist"):
            assert disclosure not in body


class TestScenario18And22Headers:
    """`FR-043`, `FR-045`: headers attached explicitly, on the error surface too."""

    def test_the_error_surface_carries_every_security_header(self) -> None:
        """`FR-043`. The happy path proves nothing here: nothing global attaches these, so the
        refusal path is exactly where an omission would hide."""
        response = _client(resolver=_StubResolver(raises=AuthenticationFailed())).get(
            f"{SHELL_PREFIX}/en/acme/analyses"
        )

        for header, value in SECURITY_HEADERS.items():
            assert response.headers[header] == value

    def test_the_shell_policy_is_the_journey_policy(self) -> None:
        """`FR-045`. Imported rather than restated: a second copy of the dict is a second
        definition of the policy, and two definitions drift."""
        response = _client(resolver=_StubResolver(raises=AuthenticationFailed())).get(
            f"{SHELL_PREFIX}/en/acme/analyses"
        )

        assert response.headers["Cache-Control"] == "private, no-store"
        assert "'unsafe-inline'" not in response.headers["Content-Security-Policy"]


class TestNoSecondResolutionPath:
    """`FR-041`: the shell introduces no second actor, membership, or scope resolution path."""

    def test_the_shell_resolves_through_the_canonical_checkpoint(self) -> None:
        """`for_request`, never `resolve`, and never a reader of its own.

        Asserted on the recorded call name rather than on an outcome, because a handler calling
        `resolve` would still return a page.
        """
        resolver = _StubResolver()
        client = _client(resolver=resolver)
        client.cookies.set(SESSION_COOKIE, "a-session-token")
        client.get(f"{SHELL_PREFIX}/en/acme/analyses")

        assert [call[0] for call in resolver.calls] == ["for_request"]

    def test_the_shell_names_no_organization_in_the_resolution(self) -> None:
        """`FR-042`: the session's active organization decides scope, never the path.

        `organization_id=None` means there is no parameter on which the comparison could be
        skipped.
        """
        resolver = _StubResolver()
        client = _client(resolver=resolver)
        client.cookies.set(SESSION_COOKIE, "a-session-token")
        client.get(f"{SHELL_PREFIX}/en/some-org/analyses")

        assert resolver.calls[0][2] is None
